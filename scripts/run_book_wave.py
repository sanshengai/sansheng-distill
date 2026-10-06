#!/usr/bin/env python3
"""Validate and constrain book jobs before invoking an existing project wave runner.

This checks execution scope, not book truth or semantic quality. No provider,
credential or concurrency implementation is duplicated here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SAFE_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$')
PRODUCTION = {'source_prepare', 'write', 'derive', 'render', 'functional_check', 'targeted_repair'}
OPERATIONS = PRODUCTION | {'content_review', 'external_check'}
BASE_PROMPT = '''【书籍任务执行边界】
原书事实、案例和作者观点作为来源接受；不得逐条查真假、替原书做科学审判或生成整书核查清单。
写作保留作者的论证、关键故事中的行动与转折、条件和反例；作者观点、转引者观点与编者归纳分清。
不能为凑字数编情节、替作者升华、虚构对话或强造反方。原文未给的信息不补猜。
除本任务明确列出的例外，不联网补查；不要建议下一轮全书复审。
'''


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def compile_manifest(plan):
    if not isinstance(plan, dict) or set(plan) != {'run_id', 'book_contract', 'jobs'}:
        raise ValueError('需要单一清单 run_id/book_contract/jobs；缺少执行契约不得派发')
    if not isinstance(plan['run_id'], str) or not SAFE_ID.fullmatch(plan['run_id']):
        raise ValueError('run_id 非法')
    contract = plan['book_contract']
    required = {'schema', 'book_facts', 'review_mode', 'exceptions'}
    if not isinstance(contract, dict) or not required <= set(contract) or set(contract) - required - {'review_authorization'}:
        raise ValueError('book_contract 字段不完整或含未知字段')
    if contract['schema'] != 'book-wave-contract-v1' or contract['book_facts'] != 'accept_as_source':
        raise ValueError('书籍事实必须 accept_as_source，不接受自动全书外查')
    mode = contract['review_mode']
    if not isinstance(mode, str) or mode not in {'production_only', 'requested_review'}:
        raise ValueError('review_mode 必须 production_only/requested_review')
    if mode == 'requested_review' and not nonempty(contract.get('review_authorization')):
        raise ValueError('内容审阅需要用户明确授权的范围；学科标签不构成授权')
    if mode == 'production_only' and contract.get('review_authorization'):
        raise ValueError('production_only 不得同时申报内容审核授权')
    if not isinstance(contract['exceptions'], list):
        raise ValueError('exceptions 必须为列表')
    exceptions = {}
    for exception in contract['exceptions']:
        if not isinstance(exception, dict):
            raise ValueError('外查例外必须为对象')
        kind = exception.get('kind')
        fields = {'id', 'kind', 'claim', 'source_location'}
        fields |= {'change_reason', 'current_source'} if kind == 'dated_update' else {'user_authorization'}
        if not isinstance(kind, str) or kind not in {'dated_update', 'authorized_external_check'} or set(exception) != fields:
            raise ValueError('外查仅允许具体年代更新或用户明确授权的具体对象')
        if not all(nonempty(exception.get(k)) for k in fields):
            raise ValueError('外查例外缺具体主张、位置、变化线索或授权')
        eid = exception['id']
        if not SAFE_ID.fullmatch(eid) or eid in exceptions:
            raise ValueError('外查例外 id 非法或重复')
        exceptions[eid] = exception
    jobs = plan['jobs']
    if not isinstance(jobs, list) or not 1 <= len(jobs) <= 128:
        raise ValueError('jobs 必须为非空列表，最多128项')
    compiled = []
    seen = set()
    for job in jobs:
        if not isinstance(job, dict):
            raise ValueError('job 必须为对象')
        required = {'job_id', 'book_id', 'operation', 'task'}
        if not required <= set(job) or set(job) - required - {'image_data_uri', 'issue', 'exception_id'}:
            raise ValueError('job 字段缺失或含未知字段')
        jid = job['job_id']
        if not isinstance(jid, str) or not SAFE_ID.fullmatch(jid) or jid in seen:
            raise ValueError('job_id 非法或重复')
        seen.add(jid)
        if not nonempty(job['book_id']) or not nonempty(job['task']):
            raise ValueError(f'{jid}: book_id/task 为空')
        op = job['operation']
        if not isinstance(op, str) or op not in OPERATIONS:
            raise ValueError(f'{jid}: 未知操作 {op}')
        if op == 'content_review' and mode != 'requested_review':
            raise ValueError(f'{jid}: production_only 禁止内容审阅，包括来源忠实度整轮复审')
        if op == 'targeted_repair' and not nonempty(job.get('issue')):
            raise ValueError(f'{jid}: 定点修复必须指明已发现的制作缺陷')
        eid = job.get('exception_id')
        if op == 'external_check' and (not isinstance(eid, str) or eid not in exceptions):
            raise ValueError(f'{jid}: 外查任务没有获准的具体例外')
        if op != 'external_check' and eid is not None:
            raise ValueError(f'{jid}: 只有外查任务可引用例外')
        prompt = BASE_PROMPT + f'本任务：{op}；书籍：{job["book_id"]}。\n'
        if mode == 'production_only':
            prompt += '本批禁止内容审阅；并行只做生产及明确制作故障修复，不输出审稿建议。\n'
        if op == 'content_review':
            prompt += '允许的一次内容审阅范围：' + contract['review_authorization'] + '；仅查蒸馏稿的表达与遗漏，不审判原书。\n'
        if op == 'targeted_repair':
            prompt += '只修这个已知缺陷：' + job['issue'] + '；其余内容不重写。\n'
        if op == 'external_check':
            prompt += '唯一外查例外（不得扩至整书）：' + json.dumps(exceptions[eid], ensure_ascii=False) + '\n'
        task = prompt + '\n【实际任务与材料】\n' + job['task']
        if len(task.encode('utf-8')) > 1_048_576:
            raise ValueError(f'{jid}: 实际任务超过项目执行器1MiB上限；须完整分片，不静默截断')
        row = {'job_id': jid, 'task': task}
        if 'image_data_uri' in job:
            if not nonempty(job['image_data_uri']):
                raise ValueError(f'{jid}: image_data_uri 为空')
            row['image_data_uri'] = job['image_data_uri']
        compiled.append(row)
    return {'run_id': plan['run_id'], 'jobs': compiled}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--project-runner', type=Path)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--gateway', choices=['coding', 'agent'])
    parser.add_argument('--model')
    parser.add_argument('--max-workers', type=int)
    parser.add_argument('--max-output-tokens', type=int, default=8192)
    parser.add_argument('--timeout', type=int, default=900)
    parser.add_argument('--reasoning-effort', choices=['minimal', 'low', 'medium', 'high'])
    parser.add_argument('--thinking-disabled', action='store_true')
    parser.add_argument('--job-ids')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    try:
        raw = args.manifest.read_bytes()
        plan = json.loads(raw)
        compiled = compile_manifest(plan)
        if args.job_ids:
            chosen = set(args.job_ids.split(','))
            if not chosen <= {j['job_id'] for j in compiled['jobs']}:
                raise ValueError('重试 job-ids 不在本清单内')
            compiled['jobs'] = [j for j in compiled['jobs'] if j['job_id'] in chosen]
            if not compiled['jobs']:
                raise ValueError('空重试范围')
        if args.dry_run:
            print(f'[book-wave] PASS: {len(compiled["jobs"])} jobs; 未调用模型，不证明内容质量')
            return 0
        if not args.project_runner or not args.project_runner.is_file() or not args.output_dir:
            raise ValueError('实际派发须指定存在的项目执行器和新输出目录')
        if not args.gateway or not args.model or args.max_workers is None or not 1 <= args.max_workers <= 12:
            raise ValueError('实际派发须显式指定套餐、模型和1..12路并发，不借默认模型')
        if args.output_dir.exists():
            raise ValueError('输出目录已存在，拒绝重复覆盖；失败仅用新目录重试对应job')
    except (ValueError, OSError) as exc:
        print(f'[book-wave] REJECT: {exc}', file=sys.stderr)
        return 2
    # The underlying project runner remains responsible for credentials/global slots.
    with tempfile.TemporaryDirectory(prefix='book-wave-') as scratch:
        prepared = Path(scratch) / 'jobs.json'
        prepared.write_text(json.dumps(compiled, ensure_ascii=False), encoding='utf-8')
        command = [sys.executable, str(args.project_runner), '--manifest', str(prepared),
                   '--output-dir', str(args.output_dir), '--gateway', args.gateway,
                   '--model', args.model, '--max-workers', str(args.max_workers),
                   '--max-output-tokens', str(args.max_output_tokens), '--timeout', str(args.timeout)]
        if args.reasoning_effort:
            command += ['--reasoning-effort', args.reasoning_effort]
        if args.thinking_disabled:
            command += ['--thinking-disabled']
        result = subprocess.run(command)
        if args.output_dir.is_dir():
            receipt = {'schema': 'book-wave-execution-v1', 'contract': plan['book_contract'],
                       'manifest_sha256': hashlib.sha256(raw).hexdigest(), 'runner_exit_code': result.returncode,
                       'jobs': [{'job_id': j['job_id'],
                                 'book_id': next(x['book_id'] for x in plan['jobs'] if x['job_id'] == j['job_id']),
                                 'operation': next(x['operation'] for x in plan['jobs'] if x['job_id'] == j['job_id']),
                                 'task_sha256': hashlib.sha256(j['task'].encode()).hexdigest()}
                                for j in compiled['jobs']]}
            with (args.output_dir / 'book-wave-execution.json').open('x', encoding='utf-8') as handle:
                json.dump(receipt, handle, ensure_ascii=False, indent=2)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())

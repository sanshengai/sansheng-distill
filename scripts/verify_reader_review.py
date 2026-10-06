"""Validate source-bound reader review records; never manufacture a review signature."""
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

KINDS = {'source_fidelity', 'material_omission', 'author_attribution', 'unsupported_addition',
         'dated_update', 'external_truth_check', 'style'}


def validate_review_scope(data):
    if not isinstance(data, dict) or not data:
        return ['[review-scope] 范围不得为空']
    errors = []
    if data.get('schema') != 'book-review-scope-v1':
        errors.append('[review-scope] schema 必须为 book-review-scope-v1')
    if data.get('book_facts') != 'accept_as_source':
        errors.append('[review-scope] 原书事实默认接受；不能将书籍蒸馏改为全书真假核验')
    exceptions = data.get('exceptions')
    items = data.get('items')
    if not isinstance(exceptions, list) or not isinstance(items, list) or not items:
        return errors + ['[review-scope] exceptions 必须为数组；items 任务/裁决范围不得为空']
    by_id = {}
    for row in exceptions:
        if not isinstance(row, dict):
            errors.append('[review-scope] 例外必须为对象')
            continue
        key = row.get('id')
        if not isinstance(key, str) or not key.strip() or key in by_id:
            errors.append('[review-scope] 例外 id 缺失或重复')
        else:
            by_id[key] = row
        if row.get('kind') not in {'dated_update', 'external_truth_check'}:
            errors.append('[review-scope] 例外仅允许过时更新或用户明确授权的定项外查')
        fields = ['claim', 'source_location']
        fields += ['change_reason', 'current_source'] if row.get('kind') == 'dated_update' else ['user_authorization']
        for field in fields:
            if not isinstance(row.get(field), str) or not row[field].strip():
                errors.append(f'[review-scope] 例外缺 {field}：书龄或学科标签本身不是外查许可')
    ids = set()
    for row in items:
        if not isinstance(row, dict):
            errors.append('[review-scope] 任务/意见必须为对象')
            continue
        key, kind = row.get('id'), row.get('kind')
        if not isinstance(key, str) or not key.strip() or key in ids:
            errors.append('[review-scope] 任务/意见 id 缺失或重复')
        if isinstance(key, str):
            ids.add(key)
        if kind not in KINDS:
            errors.append('[review-scope] 未知范围类别；不能用笼统事实核查绕过范围')
        if kind in {'dated_update', 'external_truth_check'}:
            exception = by_id.get(row.get('exception_id'))
            if not exception or exception.get('kind') != kind:
                errors.append(f'[review-scope] {key} 无对应定项外查例外')
        if kind == 'style' and row.get('blocking') is not False:
            errors.append('[review-scope] 次要措辞意见不得阻断交付或触发重审')
    return errors



def sha256(data):
    return hashlib.sha256(data).hexdigest()


def validate_reader_review(distill_path, source_path, receipt_path):
    errors = []
    if not source_path:
        return ["[reader] 必须提供 --source，不能脱离来源签收"]
    try:
        raw = Path(distill_path).read_bytes()
        source = Path(source_path).read_bytes()
        data = json.loads(raw)
        receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
        if not isinstance(receipt, dict) or not isinstance(data, dict):
            raise ValueError("正文与收据必须为对象")
    except (OSError, ValueError, TypeError) as exc:
        return [f"[reader] 审阅记录不可读取: {exc}"]
    if data.get("quality_profile") != "reader":
        errors.append("[reader] 正文未显式选择 reader 档")
    if not source.strip():
        errors.append("[reader] 来源不得为空")
    if receipt.get("schema") not in {"reader-review-v1", "reader-review-v2"}:
        errors.append("[reader] 审阅记录 schema 必须为 reader-review-v2（v1仅兼容旧收据）")
    if receipt.get("schema") == "reader-review-v2":
        errors.extend(validate_review_scope(receipt.get("review_scope")))
    for key, expected in (("distill_sha256", sha256(raw)), ("source_sha256", sha256(source))):
        if receipt.get(key) != expected:
            errors.append(f"[reader] {key} 与当前输入不符")
    for key in ("authorization", "reviewer", "reviewed_at", "review_evidence"):
        if not isinstance(receipt.get(key), str) or not receipt[key].strip():
            errors.append(f"[reader] 缺 {key}")
    try:
        reviewed_at = datetime.fromisoformat(receipt.get("reviewed_at", "").replace("Z", "+00:00"))
        if reviewed_at.tzinfo is None:
            raise ValueError("时间必须带时区")
    except (ValueError, TypeError, AttributeError):
        errors.append("[reader] reviewed_at 必须为带时区的 ISO 时间")
    # Counts must be actual integers: False is not a signed zero.
    if type(receipt.get("unresolved_material_errors")) is not int or receipt["unresolved_material_errors"] != 0:
        errors.append("[reader] 未解决实质错误必须明确为整数 0")
    chapters = data.get("chapters")
    rows = receipt.get("chapters")
    if not isinstance(chapters, list) or not chapters or not isinstance(rows, list) or not rows:
        return errors + ["[reader] 正文与章节审阅集合均不得为空"]
    ids = [str(ch.get("no")) for ch in chapters if isinstance(ch, dict)]
    row_ids = [str(row.get("no")) for row in rows if isinstance(row, dict)]
    if len(ids) != len(chapters) or len(set(ids)) != len(ids) or "None" in ids:
        errors.append("[reader] 正文章节身份缺失或重复")
    if len(row_ids) != len(rows) or len(set(row_ids)) != len(row_ids) or set(ids) != set(row_ids):
        errors.append("[reader] 章节审阅集合缺项、多项或重复")
    by_no = {str(row.get("no")): row for row in rows if isinstance(row, dict)}
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        no = str(chapter.get("no"))
        body = chapter.get("narrative")
        if not isinstance(body, str) or not re.search(r"[^\W_]", body, re.UNICODE):
            errors.append(f"[reader] 第{no}章正文为空或无有效文字")
            continue
        row = by_no.get(no, {})
        if row.get("narrative_sha256") != sha256(body.encode("utf-8")):
            errors.append(f"[reader] 第{no}章正文哈希不符")
        if row.get("fidelity") != "reviewed" or not isinstance(row.get("evidence"), str) or not row["evidence"].strip():
            errors.append(f"[reader] 第{no}章未完成来源忠实审阅或缺证据定位")
        coverage = row.get("coverage")
        if not isinstance(coverage, dict):
            errors.append(f"[reader] 第{no}章缺主论证/案例/反例/限制审阅")
            continue
        for facet in ("argument", "cases", "counterexamples", "limits"):
            check = coverage.get(facet)
            if not isinstance(check, dict):
                errors.append(f"[reader] 第{no}章缺 {facet} 审阅")
                continue
            allowed = {"reviewed"} if facet == "argument" else {"reviewed", "not_applicable"}
            if check.get("status") not in allowed or not isinstance(check.get("note"), str) or not check["note"].strip():
                errors.append(f"[reader] 第{no}章 {facet} 未审或缺裁决依据")
    return errors

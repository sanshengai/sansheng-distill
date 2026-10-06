"""Reject scope expansion in book review tasks and findings, without judging book truth."""
import argparse
import json
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scope', type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.scope.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        print(f'[review-scope] 无法读取范围: {exc}')
        return 1
    errors = validate_review_scope(data)
    for error in errors:
        print(error)
    if not errors:
        print('[review-scope] PASS：仅证明申报范围合规，不证明语义或事实正确')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())

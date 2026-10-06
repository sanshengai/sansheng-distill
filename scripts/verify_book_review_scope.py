"""Reject scope expansion in book review tasks and findings, without judging book truth."""
import argparse
import json
from pathlib import Path

from verify_reader_review import validate_review_scope


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

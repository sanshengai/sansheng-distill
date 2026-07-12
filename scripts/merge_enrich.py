#!/usr/bin/env python3
"""组装 enrich.json(纯拼接,替代 Opus 组装 agent)。
用法: python merge_enrich.py <slug> [--data-root <读书蒸馏>]
读 {书目录}/_enrich_author.json(取 author_page)+ _enrich_web.json(取 similar_page/views_page/reviews/cross_book_external),
合并成 enrich.json 五键,并清理多余转义反斜杠引号(\\" -> 中文引号)。
"""
import json, re, sys, os

def clean(o):
    if isinstance(o, str):
        # 成对 \"短语\" -> 中文引号,残单 \" -> 直引号
        o = re.sub(r'\\"(.*?)\\"', lambda m: '“' + m.group(1) + '”', o)
        return o.replace('\\"', '"')
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [clean(v) for v in o]
    return o

def main():
    if len(sys.argv) < 2:
        print('用法: python merge_enrich.py <slug> [--data-root <读书蒸馏>]', file=sys.stderr)
        sys.exit(2)
    slug = sys.argv[1]
    data_root = os.environ.get('DISTILL_DATA_DIR', './distill-data')
    if '--data-root' in sys.argv:
        data_root = sys.argv[sys.argv.index('--data-root') + 1]
    base = os.path.join(data_root, slug)

    ap = os.path.join(base, '_enrich_author.json')
    wp = os.path.join(base, '_enrich_web.json')
    if not (os.path.exists(ap) and os.path.exists(wp)):
        print('缺 _enrich_author.json 或 _enrich_web.json', file=sys.stderr); sys.exit(1)
    a = json.load(open(ap, encoding='utf-8'))
    w = json.load(open(wp, encoding='utf-8'))

    enrich = {}
    enrich['author_page'] = a.get('author_page', a)
    for k in ['similar_page', 'views_page', 'reviews', 'cross_book_external']:
        v = w.get(k)
        # cross_book_external 若被多包一层解开
        if k == 'cross_book_external' and isinstance(v, dict) and 'cross_book_external' in v:
            v = v['cross_book_external']
        enrich[k] = v
    enrich = clean(enrich)

    json.dump(enrich, open(os.path.join(base, 'enrich.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('enrich.json 五键:')
    for k in ['author_page', 'similar_page', 'views_page', 'reviews', 'cross_book_external']:
        v = enrich.get(k)
        n = '' if v is None else (f' items={len(v.get("items", []))}' if k == 'similar_page' and isinstance(v, dict)
                                  else f' topics={len(v.get("topics", []))}' if k == 'views_page' and isinstance(v, dict)
                                  else f' {len(v)}条' if isinstance(v, list) else ' OK')
        print(f"  {k}: {'null(降级)' if v is None else 'OK' + n}")
    missing = [k for k in ['author_page', 'similar_page', 'views_page', 'reviews', 'cross_book_external'] if k not in enrich]
    sys.exit(1 if missing else 0)

if __name__ == '__main__':
    main()

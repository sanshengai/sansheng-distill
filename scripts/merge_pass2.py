#!/usr/bin/env python3
"""合并 Pass2 各章 narrative+excerpts 进 distill.json(纯转录,替代 Opus 合并 agent)。
用法: python merge_pass2.py <slug> [--data-root <读书蒸馏>]
读 {书目录}/_pass2_{no}.json(每章 {no,narrative,excerpts}),清理标签残留后填进 distill.chapters。
action_chain[].detail 不在此处理(改由合成阶段直接产出)。
"""
import json, re, sys, glob, os

def main():
    if len(sys.argv) < 2:
        print('用法: python merge_pass2.py <slug> [--data-root <读书蒸馏>]', file=sys.stderr)
        sys.exit(2)
    slug = sys.argv[1]
    data_root = os.environ.get('DISTILL_DATA_DIR', './distill-data')
    if '--data-root' in sys.argv:
        data_root = sys.argv[sys.argv.index('--data-root') + 1]
    base = os.path.join(data_root, slug)
    dp = os.path.join(base, 'distill.json')
    d = json.load(open(dp, encoding='utf-8'))
    chap = {c['no']: c for c in d['chapters']}

    tag = re.compile(r'(&lt;/?(?:narrative|invoke)&gt;|</?(?:narrative|invoke)>)')
    # v2 Pass合一产物 _ch_*.json 优先;回退 v1 的 _pass2_*.json
    files = sorted(glob.glob(os.path.join(base, '_ch_*.json'))) or sorted(glob.glob(os.path.join(base, '_pass2_*.json')))
    if not files:
        print('未找到 _ch_*.json 或 _pass2_*.json', file=sys.stderr); sys.exit(1)
    filled = []
    for f in files:
        ch = json.load(open(f, encoding='utf-8'))
        no = ch.get('no')
        if no in chap:
            narr = tag.split(ch.get('narrative', ''))[0].rstrip()
            chap[no]['narrative'] = narr
            chap[no]['excerpts'] = ch.get('excerpts', [])
            filled.append(no)
    json.dump(d, open(dp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    empty = [c['no'] for c in d['chapters'] if not c['narrative'].strip()]
    print(f'合并完成: 填 {sorted(filled)} | 待补: {empty if empty else "无"}')
    bad = False
    for c in d['chapters']:
        n = len(re.sub(r'\s', '', c['narrative']))
        over = [len(re.sub(r'\s', '', e['text'])) for e in c['excerpts'] if len(re.sub(r'\s', '', e['text'])) > 150]
        flag = ''
        if n < 800: flag += ' narr<800!'; bad = True
        if not c['excerpts']: flag += ' 无excerpts!'; bad = True
        if over: flag += f' 超版权{over}!'; bad = True
        print(f"  第{c['no']}章 narr={n}字 exc={len(c['excerpts'])}条{flag}")
    sys.exit(1 if (empty or bad) else 0)

if __name__ == '__main__':
    main()

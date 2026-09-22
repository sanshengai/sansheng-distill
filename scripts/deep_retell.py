#!/usr/bin/env python3
"""深读重述（试点，2026-09-22）：把一本书按节切开，让模型用自己的话把每一节完整讲一遍（保留六到七成内容），
再合回一份 deepread.json，并做机械核对（连续雷同、数字有据、篇幅比）。

用法：
  python3 deep_retell.py split   <书目录> --mode toc-cn|vertical            → <书目录>/_deepread/units.json
  python3 deep_retell.py build   <书目录> --book "书名" --author "作者" [--claims <pack>/claims.json --source-prefix source:slug --exclude-source source:slug:0018]
                                                                        → <书目录>/_deepread/jobs.json（喂 run_coding_plan_wave.py）
  python3 deep_retell.py collect <书目录> --out-dir <runner 输出目录>        → <书目录>/deepread.json + 核对报告
  python3 deep_retell.py render  <书目录> --book "书名" --author "作者"      → <书目录>/deepread-pilot.html
切法：toc-cn = 「一、」大章 + 「1.」小节（店长日记这类）；vertical = epub 把标题竖排成单字行（因为独特这类），
「李翔：/王宁：」这种说话人标签会被识别成访谈节。
"""
import argparse, collections, glob, html, json, os, re, sys, tempfile

D = lambda book: os.path.join(book, '_deepread')

# ---------- split ----------
def split_toc_cn(lines):
    """目录里「一、大章」「1.小节」的书：先从目录抄下标题清单，正文里只认与清单逐字相同的行做标题
    （正文里的「一、目标与现实」「1.为什么会……」这类列表项不算）。"""
    part_re = re.compile(r'^([一二三四五六七八九十]+)、(.+)$'); sec_re = re.compile(r'^(\d{1,2})\.([^\d].*)$')
    toc_i = next((i for i, l in enumerate(lines) if l.strip() == '目录'), 0)
    toc = []  # [(kind, title)]
    for l in lines[toc_i + 1:]:
        t = l.strip()
        if not t:
            if toc: break
            continue
        if part_re.match(t): toc.append(('part', t))
        elif sec_re.match(t): toc.append(('sec', t))
        elif toc: break
    if not toc: raise SystemExit('目录里没识别出「一、」「1.」结构')
    want = [t for _, t in toc]
    body_start = next(i for i, l in enumerate(lines) if i > toc_i + len(toc) and l.strip() == want[0])
    units = []; part = None; cur = None; k = 0
    for i in range(body_start, len(lines)):
        l = lines[i].strip()
        if k < len(toc) and l == toc[k][1]:
            if toc[k][0] == 'part': part = part_re.match(l).group(2).strip(); cur = None
            else:
                cur = {'no': len(units) + 1, 'part': part, 'title': sec_re.match(l).group(2).strip(), 'kind': 'narrative', 'lines': []}
                units.append(cur)
            k += 1; continue
        if cur is not None and l: cur['lines'].append(l)
    for u in units: u['text'] = '\n'.join(u.pop('lines'))
    if k < len(toc): print(f'⚠ 目录 {len(toc)} 条，正文只对上 {k} 条', file=sys.stderr)
    return units


def split_vertical(lines, part_re_s=None, sec_re_s=None):
    heads = []; i = 0
    while i < len(lines):
        if len(lines[i].strip()) == 1:
            j = i
            while j < len(lines) and len(lines[j].strip()) == 1: j += 1
            if j - i >= 2:
                t = ''.join(l.strip() for l in lines[i:j]); t2 = re.sub(r'(李翔|王宁)：$', '', t)
                # 纯数字 / 无汉字的单字行串（页码、目录点）不算标题
                if t2 and t2 not in ('李翔', '王宁') and re.search(r'[\u4e00-\u9fff]', t2): heads.append((i, j, t2, t != t2))
            i = j
        else: i += 1
    units = []; part = None
    if part_re_s or sec_re_s:  # 有层级正则：只认匹配 sec 的标题做节，匹配 part 的做部，其余标题并回正文
        pr = re.compile(part_re_s) if part_re_s else None; sr = re.compile(sec_re_s) if sec_re_s else None
        cur = None
        for k, (ln, end_head, title, interview) in enumerate(heads):
            end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
            body = [l.strip() for l in lines[end_head:end] if l.strip()]
            if pr and pr.match(title): part = title; cur = None; continue
            if sr and sr.match(title):
                cur = {'no': len(units) + 1, 'part': part or '', 'title': title, 'kind': 'narrative', 'lines': []}; units.append(cur)
                cur['lines'] += body; continue
            if cur is not None: cur['lines'] += [title] + body  # 更低层级的小标题并回正文
        for u in units: u['text'] = '\n'.join(u.pop('lines'))
        units = [u for u in units if len(u['text']) >= 300]
        for k, u in enumerate(units, 1): u['no'] = k
        return units
    for k, (ln, end_head, title, interview) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        body = [l.strip() for l in lines[end_head:end] if l.strip()]
        text = '\n'.join(body)
        if len(text) < 200 and not interview:  # 篇名页：只有标题
            part = title; continue
        if re.match(r'^版权', title): continue
        units.append({'no': len(units) + 1, 'part': part or '', 'title': title, 'kind': 'interview' if interview else 'narrative', 'text': text})
    return units


PART_DEFAULT = r'^(第[一二三四五六七八九十百\d]+[章篇部]|引子|序章|附录|后记|尾声|前言|自序|推荐序|结语)'


def split_toc_list(lines, part_re_s=PART_DEFAULT, junk=('封面', '扉页', '版权页', '目录', '版权信息')):
    """书开头是一整块目录清单（没有「目录」两个字）：先取顶部连续短行做清单，正文里与清单逐字相同的行才是标题。
    分「部」用 part_re；清单里其他行是节。"""
    part_re = re.compile(part_re_s)
    short = lambda l: 0 < len(l.strip()) <= 40 and not l.strip().startswith('〔图字')  # 标题可以带「！」，只按长度判
    toc = []; i = 0
    for j, l in enumerate(lines[:300]):  # 书里有「目录」两个字时，从它之后开始扫清单（前面是书名 / 作者 / 版权）
        if l.strip() in ('目录', '目 录', 'CONTENTS', 'Contents'): i = j + 1; break
    while i < len(lines) and (short(lines[i]) or not lines[i].strip() or lines[i].strip().startswith('〔图字')):
        t = lines[i].strip()
        if t and t not in junk and not t.startswith('〔图字'): toc.append(t)
        i += 1
    if len(toc) < 5: raise SystemExit('顶部目录清单太短，换个切法')
    # 正文里的小标题有时只写冒号前半截（目录「缘起：我为什么离开北大」→ 正文「缘起：」），两种写法都认
    want = {}
    for t in toc:
        want[t] = t
        for alias in (t.split('：')[0] + '：', t.split('：')[0], t.split('：', 1)[-1]):
            if len(alias) >= 2: want.setdefault(alias, t)
    body_start = i
    units = []; part = None; cur = None
    for j in range(body_start, len(lines)):
        l = lines[j].strip()
        if l in want:
            t = want[l]
            if part_re.match(t): part = re.sub(r'\s+', ' ', t); cur = None
            else:
                cur = {'no': len(units) + 1, 'part': part or '', 'title': t, 'kind': 'narrative', 'lines': []}; units.append(cur)
            continue
        if cur is not None and l: cur['lines'].append(l)
    for u in units: u['text'] = '\n'.join(u.pop('lines'))
    units = [u for u in units if len(u['text']) >= 300]
    for k, u in enumerate(units, 1): u['no'] = k
    return units


def split_chapter_subhead(lines, part_re_s=r'^第[一二三四五六七八九十]+章', max_head=22, sec_re_s=None):
    """「第X章」之下没有编号小节，只有短行小标题（以慢制胜这类）：章内 ≤max_head 字、不以标点结尾的行当节标题；太短的节并入前一节。"""
    part_re = re.compile(part_re_s)
    hits = {}
    for i, l in enumerate(lines):
        if part_re.match(l.strip()) and len(l.strip()) <= 40: hits.setdefault(l.strip(), []).append(i)
    # 章名在目录里出现一次、正文里出现一次：按「正文那一次」取——即每个章名的最后一次，
    # 但要求它们彼此递增且间距够大（章正文至少 20 行），否则退回第一次之后的那一次。
    starts = sorted(v[-1] for v in hits.values())
    if len(starts) > 1 and min(b - a for a, b in zip(starts, starts[1:])) < 20:
        starts = sorted(v[0] for v in hits.values())
    if not starts: raise SystemExit('没找到「第X章」')
    units = []
    for k, st in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(lines)
        part = re.sub(r'\s+', ' ', lines[st].strip()); cur = None
        for j in range(st + 1, end):
            l = lines[j].strip()
            if not l: continue
            is_head = re.match(sec_re_s, l) if sec_re_s else (1 < len(l) <= max_head and not re.search(r'[。！？；，、：…”」）)]$', l) and l != '注' and not l.startswith('〔图字'))
            if is_head:
                cur = {'no': len(units) + 1, 'part': part, 'title': l, 'kind': 'narrative', 'lines': []}; units.append(cur); continue
            if cur is None:
                cur = {'no': len(units) + 1, 'part': part, 'title': part, 'kind': 'narrative', 'lines': []}; units.append(cur)
            cur['lines'].append(l)
    for u in units: u['text'] = '\n'.join(u.pop('lines'))
    merged = []
    for u in units:
        if merged and len(u['text']) < 600 and merged[-1]['part'] == u['part']: merged[-1]['text'] += '\n' + u['text']
        else: merged.append(u)
    merged = [u for u in merged if len(u['text']) >= 300]
    for k, u in enumerate(merged, 1): u['no'] = k
    return merged


TPL_ESSAY = """你是一位讲书的作者。下面是《%(book)s》（%(author)s）%(where)s的原文，这是一本分析型的书。请用你自己的话把这一节的内容完整地重新讲一遍，讲给没读过这本书的读者听。
要求：
1. 保留原文六到七成的内容：作者的每个论点、支撑它的案例（案例要整段讲完：时间、人、做了什么、结果）、数字、比较、作者自己的判断和保留意见。只删重复、过渡和口号，不把一个案例压成一句话，不把论证压成结论。
2. 像讲书一样连贯：顺着作者的论证推进，段与段之间有「因为 / 所以 / 但是」的衔接；不罗列要点，不用「首先 / 其次」，不写「本节讲了」式总结。
3. 全文第三人称（「作者」或作者姓名），作者的判断写成「作者认为」；不添加原文没有的事实、案例、数字，不替作者补充论据。
4. 分成 2–5 个小节，每个小节一个论点或一个案例，给一个 8–16 字的小标题（说清作者主张什么或讲了什么事，不用「之道」「的力量」「启示」这类词），再给 3–5 个关键词。
5. 每个小节最多放一句原话，逐字照抄、加引号，不超过 150 字，只在非原话不可时用；除此之外不得有连续 30 字与原文相同。
6. 简体中文，破折号用 --，不出现「本章」「本节」「原文」「作者写道」这类字眼。
7. 原文每段前有段号（如 [P12]）。每个小节写完后列出它覆盖了哪些段号（covers）；原文里你没有写进任何小节的段，逐段列进 skipped 并写明原因（只允许三种：他人作品的引文 / 纯过渡或口号 / 与前文重复）。不许静默跳过。
%(side)s
只输出 JSON：{"sections":[{"title":"…","keywords":["…"],"paragraphs":["…","…"],"quote":"原话或空字符串","covers":["P1","P2"]}],"skipped":[{"id":"P7","why":"…"}]}，不要解释，不要 markdown 围栏。
--- 原文开始 ---
%(text)s"""


# ---------- 旁证 ----------
def trigrams(s):
    s = re.sub(r'[^一-鿿A-Za-z0-9]', '', s)
    return {s[i:i + 3] for i in range(len(s) - 2)}


def side_evidence(units, claims_path, prefix, exclude, top=6):
    rows = json.load(open(claims_path, encoding='utf-8'))['claims']
    titles = {}; kinds = {}
    try:
        src = json.load(open(os.path.join(os.path.dirname(claims_path), 'sources.json'), encoding='utf-8'))
        for s in (src['sources'] if isinstance(src, dict) else src): titles[s['id']] = s.get('title', ''); kinds[s['id']] = s.get('type', '')
    except Exception: pass
    NARR = {'book', 'memoir', 'biography', 'feature', 'long-form', 'interview', 'oral-history', 'diary', 'speech', 'case-study', 'transcript'}
    # 只拿叙事型来源做旁证：年报 / 招股书是数字不是记载，写成「另一本书《…年报》」会很怪
    pool = [c for c in rows if any(s.startswith(prefix) and s not in exclude and kinds.get(s) in NARR for s in (c.get('source_refs') or []))]
    for u in units:
        tg = trigrams(u['text']); scored = []
        for c in pool:
            ct = trigrams(c['text'] + (c.get('quote') or ''))
            if len(ct) < 6: continue
            hit = len(tg & ct)
            if hit >= 6: scored.append((hit / len(ct), hit, c))
        scored.sort(key=lambda x: (-x[0], -x[1]))
        u['side'] = [{'id': c['id'], 'source': titles.get((c.get('source_refs') or [''])[0], ''), 'text': c['text'], 'quote': (c.get('quote') or '')[:200]} for _, _, c in scored[:top]]
    return units


# ---------- build ----------
TPL_NARR = '''你是一位讲故事的作者。下面是《%(book)s》（%(author)s）%(where)s的原文。请用你自己的话把这一节完整地重新讲一遍，讲给一个没读过这本书的读者听。
要求：
1. 保留原文六到七成的内容：发生了什么、什么时候、在哪儿、谁、做了什么、说了什么（对话改成转述或短引），数字、金额、人数、日期原样保留；作者当时的想法与情绪也要写出来（写成「他当时觉得……」）。只删重复、过渡与空话，不删故事，不把一件事压成一句话。
2. 像讲故事一样连贯：按事情发生的顺序推进，段与段之间有时间和因果的衔接；不罗列要点，不用「首先 / 其次」，不写总结句，不写「这一节告诉我们」。
3. 全文用第三人称讲%(who)s，作者自己的判断写成「他认为」；不添加原文没有的事实、人物、数字；原文没写的心理活动不猜。
4. 分成 2–5 个小节，每个小节讲一件事，给一个 8–16 字的事件式小标题（说发生了什么，不用「之道」「的力量」「启示」这类词），再给 3–5 个关键词（人名 / 地点 / 物件 / 数字，读者扫一眼就知道这节讲什么）。
5. 每个小节最多放一句原话，逐字照抄原文、加引号，不超过 150 字，只在这句话非原话不可时用；除此之外不得有连续 30 字与原文相同。
6. 简体中文，破折号用 --，不出现「本章」「本节」「原文」「作者写道」这类字眼；「专家点评」段落若有，压成一段「%(commentator)s在点评里说……」放在最后一个小节。
7. 原文每段前有段号（如 [P12]）。每个小节写完后列出它覆盖了哪些段号（covers）；原文里你没有写进任何小节的段，逐段列进 skipped 并写明原因（只允许三种：他人作品的引文或歌词 / 纯过渡或客套 / 与前文重复）。不许静默跳过。
%(side)s
只输出 JSON：{"sections":[{"title":"…","keywords":["…"],"paragraphs":["…","…"],"quote":"原话或空字符串","covers":["P1","P2"]}],"skipped":[{"id":"P7","why":"…"}]}，不要解释，不要 markdown 围栏。
--- 原文开始 ---
%(text)s'''

TPL_INTV = '''你是一位讲故事的作者。下面是《%(book)s》（%(author)s）里一段访谈实录，%(where)s，李翔提问、王宁回答。请把这段问答改写成第三人称的连贯叙述：王宁怎么看这件事、举了什么例子、给了什么数字、为什么这样想，讲给没读过这本书的读者听。
要求：
1. 保留原文六到七成的内容：他的观点、理由、例子、数字、时间、人名、公司名原样保留；提问只当引子（「被问到……时，他说……」），不逐条照搬问答。只删客套、重复和过渡，不把一个观点压成一句话。
2. 像讲故事一样连贯：观点之间用他的逻辑串起来，段与段之间有衔接；不罗列要点，不用「首先 / 其次」，不写总结句。
3. 全文第三人称（「王宁」/「他」），不添加原文没有的事实与数字，不替他补充没说过的解释。
4. 分成 2–5 个小节，每个小节一个话题，给一个 8–16 字的小标题（说他讲了什么，不用「之道」「的力量」「启示」这类词），再给 3–5 个关键词。
5. 每个小节最多放一句原话，逐字照抄、加引号，不超过 150 字，只在非原话不可时用；除此之外不得有连续 30 字与原文相同。
6. 简体中文，破折号用 --，不出现「本章」「本节」「原文」「访谈」这类字眼。
7. 原文每段前有段号（如 [P12]）。每个小节写完后列出它覆盖了哪些段号（covers）；原文里你没有写进任何小节的段，逐段列进 skipped 并写明原因（只允许三种：他人作品的引文 / 纯客套或过渡 / 与前文重复）。不许静默跳过。
%(side)s
只输出 JSON：{"sections":[{"title":"…","keywords":["…"],"paragraphs":["…","…"],"quote":"原话或空字符串","covers":["P1","P2"]}],"skipped":[{"id":"P7","why":"…"}]}，不要解释，不要 markdown 围栏。
--- 原文开始 ---
%(text)s'''


def build(book, args):
    units = json.load(open(os.path.join(D(book), 'units.json'), encoding='utf-8'))
    jobs = []
    for u in units:
        side = ''
        if u.get('side'):
            side = '旁证（其他书或报道对相关事情的记载；只有和本节讲的确实是同一件事时才用，最多用 2 条，写成「《…》里也记着……」或「据《…》的报道……」并写明书名 / 报道名；对不上就忽略）：\n' + '\n'.join(f"- 《{s['source'][:20]}》：{s['text'][:160]}" for s in u['side'])
        where = f"「{u['part']}」下的「{u['title']}」" if u['part'] else f"「{u['title']}」"
        tpl = {'interview': TPL_INTV, 'essay': TPL_ESSAY}.get(u['kind'], TPL_NARR)
        numbered = '\n'.join(f'[P{i + 1}] {line}' for i, line in enumerate(u['text'].split('\n')))
        task = tpl % dict(book=args.book, author=args.author, where=where, who=args.who, commentator=args.commentator, side=side, text=numbered)
        jobs.append({'job_id': f"u{u['no']:03d}", 'task': task})
    out = os.path.join(D(book), 'jobs.json')
    json.dump({'run_id': 'deep-retell', 'jobs': jobs}, open(out, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'{len(jobs)} jobs → {out}；最长 {max(len(j["task"]) for j in jobs):,} 字符')


# ---------- collect + check ----------
def _fix_inner_quotes(s):
    """字符串值里未转义的英文双引号（书名、引语）成对换成「」；只处理 "paragraphs" 数组与 "title"/"quote" 值。"""
    def fix_text(t):
        out, open_ = [], False
        for ch in t:
            if ch == '"': out.append('「' if not open_ else '」'); open_ = not open_
            else: out.append(ch)
        return ''.join(out)
    # 逐个字符串字面量扫描：以 " 开头，遇到 ",  "] "} 结尾模式才算结束
    res = []; i = 0; n = len(s)
    while i < n:
        if s[i] == '"':
            j = i + 1; buf = []
            while j < n:
                if s[j] == '\\' and j + 1 < n: buf.append(s[j:j + 2]); j += 2; continue
                if s[j] == '"':
                    k = j + 1
                    while k < n and s[k] in ' \n\r\t': k += 1
                    if k >= n or s[k] in ',]}:': break
                buf.append(s[j]); j += 1
            res.append('"' + fix_text(''.join(buf)) + '"'); i = j + 1
        else: res.append(s[i]); i += 1
    return ''.join(res)


def loads(s):
    s = s.strip(); s = re.sub(r'^```(?:json)?\s*|\s*```$', '', s)
    try: return json.loads(s)
    except json.JSONDecodeError:
        for tail in (']}', '"}]}', '"]}]}'):
            try: return json.loads(s + tail)
            except json.JSONDecodeError: pass
        try: return json.loads(_fix_inner_quotes(s))
        except json.JSONDecodeError: pass
    raise ValueError('bad json')


def longest_common_run(a, b, minlen=30):
    """a 里与 b 连续相同 ≥ minlen 的片段（去空白后比）。"""
    a2 = re.sub(r'\s', '', a); b2 = re.sub(r'\s', '', b)
    hits = []; i = 0
    while i + minlen <= len(a2):
        seg = a2[i:i + minlen]
        if seg in b2:
            j = i + minlen
            while j < len(a2) and a2[i:j + 1] in b2: j += 1
            hits.append(a2[i:j]); i = j
        else: i += 1
    return hits


def _atomic_collect_json(path, value):
    """完整序列化成功后才替换，失败不截断现有正式文件。"""
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=os.path.dirname(path),
                                         prefix='.collect-', suffix='.tmp', delete=False) as handle:
            tmp = handle.name
            json.dump(value, handle, ensure_ascii=False, indent=1)
            handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp and os.path.exists(tmp): os.unlink(tmp)


def _collect_sections(data):
    """只规范合法单段字符串；不丢弃或猜补损坏的正文结构。"""
    if not isinstance(data, dict) or not isinstance(data.get('sections'), list) or not data['sections']:
        raise ValueError('sections 必须是非空数组')
    for i, sec in enumerate(data['sections'], 1):
        if not isinstance(sec, dict) or not isinstance(sec.get('title'), str) or not sec['title'].strip():
            raise ValueError(f'section {i} 缺合法标题')
        if 'skipped' in sec or sec.get('paragraphs2'):
            raise ValueError(f'section {i} 元数据混入正文或含未归并 paragraphs2')
        paragraphs = sec.get('paragraphs')
        if isinstance(paragraphs, str): paragraphs = [paragraphs]
        if not isinstance(paragraphs, list) or not paragraphs or any(
                not isinstance(p, str) or not p.strip() for p in paragraphs):
            raise ValueError(f'section {i} paragraphs 必须是非空文本数组或单段文本')
        if len(paragraphs) >= 20 and sum(len(p.strip()) <= 1 for p in paragraphs) / len(paragraphs) >= .9:
            raise ValueError(f'section {i} 疑似正文被拆成单字')
        sec['paragraphs'] = paragraphs
        for field in ('covers', 'keywords'):
            value = sec.get(field)
            if value is not None and (not isinstance(value, list) or any(not isinstance(x, str) for x in value)):
                raise ValueError(f'section {i} {field} 必须是文本数组')
        if sec.get('quote') is not None and not isinstance(sec['quote'], str):
            raise ValueError(f'section {i} quote 必须是文本')
    skipped = data.get('skipped')
    if skipped is not None and (not isinstance(skipped, list) or any(
            not isinstance(x, dict) or not isinstance(x.get('id'), str) or
            not isinstance(x.get('why'), str) or not x['why'].strip() for x in skipped)):
        raise ValueError('skipped 必须逐项声明 id 和非空 why')
    return data['sections']


def collect(book, args):
    diagnostics = os.path.join(D(book), 'collect-diagnostics.json')
    def reject(issues):
        _atomic_collect_json(diagnostics, {'status': 'rejected', 'formal_output_replaced': False, 'issues': issues})
        print('🔴 collect 拒绝覆盖正式 deepread.json；诊断：' + diagnostics, file=sys.stderr)
        raise SystemExit(2)
    try:
        with open(os.path.join(D(book), 'units.json'), encoding='utf-8') as handle:
            units = json.load(handle)
        if not isinstance(units, list) or not units: raise ValueError('units 必须是非空数组')
        seen = set()
        for u in units:
            if not isinstance(u, dict) or type(u.get('no')) is not int or u['no'] < 1 or u['no'] in seen:
                raise ValueError('units 含非法或重复编号')
            seen.add(u['no'])
            if any(not isinstance(u.get(k), str) for k in ('part', 'title', 'kind', 'text')) or not u['text'].strip():
                raise ValueError(f"u{u['no']:03d} 源文本或元数据无效")
    except (OSError, ValueError) as exc:
        reject([{'code': 'invalid_units', 'detail': str(exc)}])
    out = {'book': args.book, 'author': args.author, 'units': []}
    report = []; missing = []; badjson = []; issues = []
    for u in units:
        f = os.path.join(args.out_dir, f"u{u['no']:03d}.response.txt")
        for alt in (args.out_dir + '-rw2', args.out_dir + '-rw'):  # 重写轮的产物优先
            f2 = os.path.join(alt, f"u{u['no']:03d}.response.txt")
            if os.path.exists(f2):
                try: loads(open(f2, encoding='utf-8').read()); f = f2; break
                except ValueError: pass
        if not os.path.exists(f):
            report.append(f"u{u['no']:03d} 缺产物"); missing.append(u['no'])
            issues.append({'code': 'missing_response', 'unit': u['no'], 'path': f}); continue
        try: d = loads(open(f, encoding='utf-8').read())
        except ValueError:
            report.append(f"u{u['no']:03d} JSON 坏"); badjson.append(u['no'])
            issues.append({'code': 'bad_json', 'unit': u['no'], 'path': f}); continue
        try: secs = _collect_sections(d)
        except ValueError as exc:
            report.append(f"u{u['no']:03d} 正文结构坏：{exc}")
            issues.append({'code': 'invalid_sections', 'unit': u['no'], 'path': f, 'detail': str(exc)}); continue
        def tidy(p):
            p = re.sub(r'《([^《》（）]+)（[^）]*）》', r'《\1》', p)  # 旁证书名带的「（作者，年份）」很累赘：《何以泡泡玛特（林开平，2025）》→《何以泡泡玛特》
            p = re.sub(r"'([^'\n]{1,40})'", r'「\1」', p)          # 模型为躲 JSON 转义用的英文单引号 → 「」
            p = re.sub(r'\s*——\s*|\s*—\s*', ' -- ', p)              # 转述正文破折号统一 --（宪法 / distill 机检口径）
            return p
        for sec in secs:
            sec['paragraphs'] = [tidy(p) for p in sec.get('paragraphs', [])]
        text_out = '\n'.join(p for s in secs for p in s.get('paragraphs', []))
        quotes = [s.get('quote') or '' for s in secs]
        # 1) 连续雷同（引号内豁免：把引用原话从输出里挖掉再比）
        body = text_out
        for q in quotes:
            if q: body = body.replace(q, '')
        runs = longest_common_run(body, u['text'], 30)
        # 2) 数字有据
        nums = set(re.findall(r'\d[\d,.]*', re.sub(r'《[^》]*》', '', text_out))); src_nums = set(re.findall(r'\d[\d,.]*', u['text'] + ' '.join(s['text'] + s.get('quote', '') for s in u.get('side', []))))
        bad_nums = sorted(n for n in nums if n not in src_nums and len(n) >= 2)
        # 3) 引文逐字
        bad_q = [q[:30] for q in quotes if q and re.sub(r'\s', '', q) not in re.sub(r'\s', '', u['text'])]
        for sec in secs:  # 不是逐字的「原话」一律不展示：宁可少一句引文，不冒充原话
            if sec.get('quote') and re.sub(r'\s', '', sec['quote']) not in re.sub(r'\s', '', u['text']): sec['quote'] = ''
        ratio = len(re.sub(r'\s', '', text_out)) / max(1, len(re.sub(r'\s', '', u['text'])))
        # 反向覆盖率（一页 deep-prose §六）：源段按段号，模型逐小节声明 covers，跳过的必须在 skipped 里给理由；
        # 声明还要过弱重合核实（三字组重合 <0.12 视为假声明），防「全都说覆盖了」
        src_lines = u['text'].split('\n'); ot = trigrams(text_out)
        valid = {f'P{i + 1}' for i, l in enumerate(src_lines) if len(l.strip()) >= 40}
        claimed = {c for sec in secs for c in (sec.get('covers') or []) if c in valid}
        fake = set()
        for pid in claimed:
            pt = trigrams(src_lines[int(pid[1:]) - 1])
            if pt and len(pt & ot) / len(pt) < 0.12: fake.add(pid)
        covered = claimed - fake
        skipped = {x.get('id'): (x.get('why') or '') for x in (d.get('skipped') or []) if isinstance(x, dict) and x.get('id') in valid}
        unaccounted = sorted(valid - covered - set(skipped), key=lambda x: int(x[1:]))
        coverage = len(covered) / max(1, len(valid))
        cov_info = {'paragraphs': len(valid), 'covered': len(covered), 'coverage': round(coverage, 2), 'fake_claims': sorted(fake, key=lambda x: int(x[1:])),
                    'skipped': [{'id': k, 'why': v, 'text': src_lines[int(k[1:]) - 1][:60]} for k, v in skipped.items()],
                    'unaccounted': [{'id': k, 'text': src_lines[int(k[1:]) - 1][:60]} for k in unaccounted]}
        u2 = {k: u[k] for k in ('no', 'part', 'title', 'kind')}
        u2.update({'src_chars': len(u['text']), 'out_chars': len(text_out), 'ratio': round(ratio, 2), 'sections': secs,
                   'check': {'verbatim_runs': [r[:40] for r in runs], 'unsupported_numbers': bad_nums, 'bad_quotes': bad_q}, 'coverage': cov_info})
        out['units'].append(u2)
        flag = ('雷同%d ' % len(runs) if runs else '') + ('无据数字%s ' % bad_nums[:4] if bad_nums else '') + ('引文不符%d ' % len(bad_q) if bad_q else '')
        flag += (f"覆盖{coverage:.0%}(漏{len(unaccounted)}) " if coverage < 0.7 or unaccounted else '') + (f"假声明{len(fake)}" if fake else '')
        report.append(f"u{u['no']:03d} {u['title'][:14]:16} 原 {len(u['text']):5} → 出 {len(text_out):5} ({ratio:.2f}) 小节 {len(secs)}  {flag}")
    print('\n'.join(report))
    if issues: reject(issues)
    _atomic_collect_json(os.path.join(book, 'deepread.json'), out)
    _atomic_collect_json(diagnostics, {'status': 'accepted', 'formal_output_replaced': True, 'units': len(out['units']), 'issues': []})
    tot_in = sum(u['src_chars'] for u in out['units']); tot_out = sum(u['out_chars'] for u in out['units'])
    P = sum(u['coverage']['paragraphs'] for u in out['units']); C = sum(u['coverage']['covered'] for u in out['units'])
    print(f"单元 {len(out['units'])}/{len(units)} 节；" + f"合计 原 {tot_in:,} → 出 {tot_out:,}（{tot_out / max(1, tot_in):.2f}）；雷同 {sum(len(u['check']['verbatim_runs']) for u in out['units'])} 处，无据数字 {sum(len(u['check']['unsupported_numbers']) for u in out['units'])} 个，引文不符 {sum(len(u['check']['bad_quotes']) for u in out['units'])} 条；"
          f"源段覆盖 {C}/{P}（{C / max(1, P):.0%}），登记跳过 {sum(len(u['coverage']['skipped']) for u in out['units'])} 段，未交代 {sum(len(u['coverage']['unaccounted']) for u in out['units'])} 段，假声明 {sum(len(u['coverage']['fake_claims']) for u in out['units'])}")


# ---------- render ----------
CSS = '''
:root{--bg:#faf8f4;--fg:#1f1d1a;--muted:#6b665e;--line:#e6e1d8;--accent:#8a3b1e;--card:#fff;--kw:#efe9df}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#171513;--fg:#ece7de;--muted:#a39d92;--line:#2e2a25;--accent:#e0956f;--card:#1f1c19;--kw:#2a2622}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:17px/1.85 "PingFang SC","Noto Serif SC",serif;padding:0 16px 80px}
main{max-width:760px;margin:0 auto}h1{font-size:28px;line-height:1.3;margin:40px 0 4px}.by{color:var(--muted);margin:0 0 6px}
.lede{color:var(--muted);font-size:15px;margin:0 0 28px}
.part{margin:34px 0 10px;font-size:13px;letter-spacing:.14em;color:var(--accent);text-transform:uppercase}
details.unit{border-top:1px solid var(--line);padding:6px 0}details.unit>summary{list-style:none;cursor:pointer;display:flex;gap:12px;align-items:baseline;padding:12px 0}
details.unit>summary::-webkit-details-marker{display:none}.unit-no{color:var(--muted);font-variant-numeric:tabular-nums;min-width:2.2em;font-size:14px}
.unit-t{font-weight:600;font-size:19px}.unit-kw{margin-left:auto;text-align:right;color:var(--muted);font-size:13px;max-width:45%%}
details.sec{margin:6px 0 6px 2.2em;padding:0 0 0 14px;border-left:2px solid var(--line)}details.sec>summary{cursor:pointer;list-style:none;padding:8px 0}
details.sec>summary::-webkit-details-marker{display:none}.sec-t{font-weight:600}.kw{display:inline-block;background:var(--kw);border-radius:4px;padding:0 7px;margin:0 4px 4px 0;font-size:13px;color:var(--muted)}
.sec p{margin:10px 0;text-align:justify}blockquote{margin:14px 0;padding:6px 16px;border-left:3px solid var(--accent);color:var(--fg);background:var(--card);font-size:16px}
.meta{font-size:13px;color:var(--muted);margin:8px 0 0 2.2em}.toolbar{position:sticky;top:0;background:var(--bg);padding:10px 0;border-bottom:1px solid var(--line);font-size:14px;display:flex;gap:16px;align-items:center;z-index:2}
.toolbar button{font:inherit;font-size:13px;white-space:nowrap;background:none;border:1px solid var(--line);border-radius:6px;padding:3px 9px;color:var(--fg);cursor:pointer}
.stat{color:var(--muted);margin-left:auto;font-size:13px}
'''


def render(book, args):
    d = json.load(open(os.path.join(book, 'deepread.json'), encoding='utf-8'))
    parts = collections.OrderedDict()
    for u in d['units']: parts.setdefault(u['part'] or '正文', []).append(u)
    tot_out = sum(u['out_chars'] for u in d['units']); tot_in = sum(u['src_chars'] for u in d['units'])
    h = [f'<!doctype html><html lang="zh-Hans"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(d["book"])} · 深读</title><style>{CSS.replace("%%", "%")}</style></head><body><main>']
    h.append(f'<div class="toolbar"><button onclick="document.querySelectorAll(\'details.unit\').forEach(x=>x.open=true)">全部展开</button><button onclick="document.querySelectorAll(\'details\').forEach(x=>x.open=false)">全部收起</button><span class="stat">重述 {tot_out:,} 字 / 原书 {tot_in:,} 字</span></div>')
    h.append(f'<h1>{html.escape(d["book"])}</h1><p class="by">{html.escape(d["author"])} · 深读重述试点</p><p class="lede">收起时只看节名和关键词，点开一节看这件事的来龙去脉，再点小节看细部。引号里的是原话，其余是重述。</p>')
    for part, us in parts.items():
        h.append(f'<div class="part">{html.escape(part)}</div>')
        for u in us:
            kws = []
            for s in u['sections']:
                for k in s.get('keywords', []):
                    if k not in kws: kws.append(k)
            kws.sort(key=lambda k: bool(re.search(r'\d{4}年|\d{1,2}月\d{1,2}日', k)))  # 收起态先给人 / 地 / 物，日期靠后
            h.append(f'<details class="unit"><summary><span class="unit-no">{u["no"]}</span><span class="unit-t">{html.escape(u["title"])}</span><span class="unit-kw">{html.escape("・".join(kws[:6]))}</span></summary>')
            for s in u['sections']:
                h.append(f'<details class="sec" open><summary><span class="sec-t">{html.escape(s.get("title", ""))}</span><br>' + ''.join(f'<span class="kw">{html.escape(k)}</span>' for k in s.get('keywords', [])) + '</summary>')
                paras = s.get('paragraphs', []); q = s.get('quote') or ''
                at = len(paras) - 1
                if q and paras:  # 引文挂在与它最像的那一段后面（按三字组重合），不再一律放小节末尾脱离语境
                    qt = trigrams(q); scores = [len(qt & trigrams(p)) for p in paras]
                    at = max(range(len(paras)), key=lambda i: scores[i]) if max(scores) > 0 else len(paras) - 1
                for i, p in enumerate(paras):
                    h.append(f'<p>{html.escape(p)}</p>')
                    if q and i == at: h.append(f'<blockquote>{html.escape(q)}</blockquote>')
                h.append('</details>')
            cov = u.get('coverage') or {}
            h.append(f'<div class="meta">原文 {u["src_chars"]:,} 字 → 重述 {u["out_chars"]:,} 字' + (f' · 源段覆盖 {cov["coverage"]:.0%}' if cov else '') + '</div></details>')
    h.append(f'<p class="lede" style="margin-top:40px">本页是《{html.escape(d["book"])}》（{html.escape(d["author"])}）的重述，不是原文：事件、人物、数字、时间来自原书，文字是重新讲的；引号内为原书原话；标注「《…》里也记着」的是其他书或报道的记载。要读原文请买原书。</p>')
    h.append('</main></body></html>')
    out = os.path.join(book, 'deepread-pilot.html')
    open(out, 'w', encoding='utf-8').write('\n'.join(h)); print('→', out)


REWRITE_NOTE = """
⚠ 上一版稿子有下面这些问题，这次必须改掉：
%(problems)s
改法：保留同样的事件、顺序、数字和细节，但这些句子必须换成你自己的说法（换句式、换词、拆并句子），引号外任何地方不得再有连续 30 字与原文相同；引号里的原话必须逐字照抄原文。
"""


def rewrite(book, args):
    """对机检不过的节重派一轮：整节重写，附上被点名的雷同片段。产物写到 <out-dir>-rw/ 后用 collect --out-dir 合并（collect 会优先读 -rw 目录）。"""
    d = json.load(open(os.path.join(book, 'deepread.json'), encoding='utf-8'))
    m = json.load(open(os.path.join(D(book), 'jobs.json'), encoding='utf-8'))
    tasks = {j['job_id']: j['task'] for j in m['jobs']}
    units = json.load(open(os.path.join(D(book), 'units.json'), encoding='utf-8'))
    done = {u['no'] for u in d['units']}
    jobs = []
    for u in units:
        jid = f"u{u['no']:03d}"; probs = []
        cur = next((x for x in d['units'] if x['no'] == u['no']), None)
        if cur is None: probs.append('- 上一版输出不是合法 JSON')
        else:
            c = cur['check']
            if len(c['verbatim_runs']) >= args.min_runs: probs += [f"- 连续照抄原文：「{r}…」" for r in c['verbatim_runs'][:12]]
            if c['bad_quotes']: probs += [f"- 引号里的「原话」在原文里找不到：「{q}…」" for q in c['bad_quotes']]
            if c['unsupported_numbers']: probs += [f"- 原文里没有的数字：{c['unsupported_numbers']}"]
            if cur['ratio'] < 0.55: probs.append(f"- 太短：只有原文的 {cur['ratio']:.0%}，删掉的故事要补回来（目标六到七成）")
            cov = cur.get('coverage') or {}
            miss = cov.get('unaccounted', []) + [{'id': x, 'text': ''} for x in cov.get('fake_claims', [])]
            if cov and (cov.get('coverage', 1) < 0.7 or miss):
                probs.append(f"- 源段覆盖只有 {cov.get('coverage', 0):.0%}；下面这些段没有写进任何小节（或声明覆盖了其实没写）：" + '、'.join(m['id'] for m in miss[:20]) + "——要么写进去，要么在 skipped 里逐段说明原因")
        if not probs: continue
        if len(probs) == 1 and probs[0].startswith('- 源段覆盖') and (cur.get('coverage') or {}).get('coverage', 0) >= 0.7 and args.min_runs > 1: continue
        task = tasks[jid].replace('--- 原文开始 ---', REWRITE_NOTE % dict(problems='\n'.join(probs)) + '\n--- 原文开始 ---', 1)
        jobs.append({'job_id': jid, 'task': task})
    out = os.path.join(D(book), 'jobs-rw.json')
    json.dump({'run_id': 'deep-retell-rw', 'jobs': jobs}, open(out, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'{len(jobs)} 节重派 → {out}')


def glance(book, args):
    """速览层导出（一页 deep-prose §八 的检验法）：把全部节名 / 小节标题 / 关键词单独排成一页，
    交给没读过正文的人——能不能讲出这本书发生了什么？不能就是速览层没写好。"""
    d = json.load(open(os.path.join(book, 'deepread.json'), encoding='utf-8'))
    out = [f"# {d['book']} · 速览层（{sum(len(u['sections']) for u in d['units'])} 个小节）", '']
    part = None
    for u in d['units']:
        if u['part'] != part: part = u['part']; out.append(f"\n## {part or '正文'}")
        out.append(f"### {u['no']}. {u['title']}")
        for sec in u['sections']: out.append(f"- {sec.get('title', '')}  ｜ {'・'.join(sec.get('keywords', [])[:4])}")
    path = os.path.join(book, 'deepread-glance.md')
    open(path, 'w', encoding='utf-8').write('\n'.join(out) + '\n'); print('→', path)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('cmd'); ap.add_argument('book')
    ap.add_argument('--mode', default='toc-cn'); ap.add_argument('--book', dest='book_title', default=''); ap.add_argument('--author', default='')
    ap.add_argument('--who', default='作者'); ap.add_argument('--commentator', default='点评人')
    ap.add_argument('--claims'); ap.add_argument('--source-prefix', default=''); ap.add_argument('--exclude-source', action='append', default=[])
    ap.add_argument('--out-dir'); ap.add_argument('--min-runs', type=int, default=1)
    ap.add_argument('--part-regex'); ap.add_argument('--sec-regex'); ap.add_argument('--kind', help='整本书的默认体裁：narrative|essay（访谈节由切法自动标 interview）')
    a = ap.parse_args(); a.book = a.book_title
    os.makedirs(D(a.book_dir if hasattr(a, 'book_dir') else sys.argv[2]), exist_ok=True)
    book = sys.argv[2]
    if a.cmd == 'split':
        lines = open(os.path.join(book, 'book.txt'), encoding='utf-8').read().split('\n')
        if a.mode == 'toc-cn': units = split_toc_cn(lines)
        elif a.mode == 'vertical': units = split_vertical(lines, a.part_regex, a.sec_regex)
        elif a.mode == 'toc-list': units = split_toc_list(lines, a.part_regex or PART_DEFAULT)
        elif a.mode == 'chapter-subhead': units = split_chapter_subhead(lines, a.part_regex or r'^第[一二三四五六七八九十]+章', sec_re_s=a.sec_regex)
        else: raise SystemExit('未知 --mode')
        if a.kind:
            for u in units:
                if u['kind'] == 'narrative': u['kind'] = a.kind
        if a.claims: units = side_evidence(units, a.claims, a.source_prefix, set(a.exclude_source))
        json.dump(units, open(os.path.join(D(book), 'units.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f"{len(units)} units；字数 {sum(len(u['text']) for u in units):,}；旁证 {sum(len(u.get('side', [])) for u in units)} 条")
        for u in units[:80]: print(f"  {u['no']:3} [{u['kind'][:4]}] {u['part'][:10]:12} {u['title'][:22]:24} {len(u['text']):6} 字 旁证 {len(u.get('side', []))}")
    elif a.cmd == 'build': build(book, a)
    elif a.cmd == 'collect': collect(book, a)
    elif a.cmd == 'render': render(book, a)
    elif a.cmd == 'rewrite': rewrite(book, a)
    elif a.cmd == 'glance': glance(book, a)


if __name__ == '__main__':
    main()

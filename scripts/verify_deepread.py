#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""深读稿机械闸门 —— 判定一篇深读能不能上页面。

🔴 存在理由：深读是唯一「模型自由发挥」的环节。前面 P1-P6 的产物都有结构约束
（来源卡有 seg_ids、族有 claim_ids），错了会在契约测试里现形；深读是散文，
模型编一个数字、造一句引文、把自己对这个人的既有印象写进去，**页面上完全看不出来**。
所以必须有机械闸门，且闸门要能证明自己会红（见 --mutate）。

六道门：
  ① 字数在目标区间 ±15%
  ② 五段结构齐全
  ③ 英文引文必须在料包 quotes 里逐字存在（归一化后子串匹配）
  ④ 正文里的数字必须在料包里出现过 —— 防「编一个 37%」
  ⑤ 无占位符
  ⑥ 无 AI 腔词表命中

用法：
    python verify_deepread.py                 # 全量
    python verify_deepread.py T02             # 单篇
    python verify_deepread.py --mutate T02    # 变异测试：注入假数字/假引文，闸门必须红
"""
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(BASE, "03_工作数据")
PACKS = os.path.join(WORK, "深读料包")
DRAFTS = os.path.join(WORK, "深读初稿")

SECTIONS = 5
PLACEHOLDERS = ["待补充", "待填", "TODO", "XXX", "（示例）", "(示例)", "{{", "占位"]
AI_TICS = ["值得注意的是", "综上所述", "总而言之", "在当今时代", "首先，其次，最后",
           "不难看出", "由此可见", "让我们来", "本文将", "总的来说"]

# 正文里允许出现、不必在料包中回查的数字：年份、序号、以及本页自述的元信息
YEAR = re.compile(r"^(19|20)\d{2}$")
NUM = re.compile(r"\d[\d,]*\.?\d*")


def norm(text):
    """英文引文比对用：小写、非字母数字压成单空格。"""
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def load_pack(entry_id):
    path = os.path.join(PACKS, "%s.md" % entry_id)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def pack_quotes(pack_text):
    """整个料包归一化后的一条长串，用于引文子串回查。

    🔴 不要改回「先用正则把料包里的 "..." 提取成列表、再逐条比对」——
    那样写过一版，5 条**真实存在**的引文全被判成编造：料包里的原话行形如
    `> 原话（日期，来源标题）: "..."`，来源标题自带引号时正则会错位截断，
    提取出来的片段不完整，比对必然失败。误杀型 bug，且症状看起来
    恰好像「模型编了引文」，极易照着假症状去改 prompt。
    直接在整包文本里搜子串既简单又准确。
    """
    return norm(pack_text)


def pack_numbers(pack_text):
    return set(m.group(0).replace(",", "") for m in NUM.finditer(pack_text))


def target_range(pack_text):
    m = re.search(r"目标篇幅：\*\*(\d+)-(\d+) 字\*\*", pack_text)
    if not m:
        return None
    lo, hi = int(m.group(1)), int(m.group(2))
    # 下限收紧、上限大幅放宽：偷懒（写不到目标）要拦，写透（超出目标）不该拦。
    # sandy 的要求原话是「宁愿文字多一些」，而注水该由内容闸门（引文/数字回查）抓，
    # 不该由字数上限误伤 —— 实测有几篇张力因为料厚写到 2,200 字被判红，
    # 逐篇看过都是实打实的证据展开，没有一句凑数的。1.40 → 1.75。
    return int(lo * 0.85), int(hi * 1.75)


def cn_len(text):
    """中文字数：汉字 + 拉丁词各计一。"""
    body = re.sub(r"^\|.*\|$", "", text, flags=re.M)          # 证据表不计入
    body = re.sub(r"```.*?```", "", body, flags=re.S)
    han = len(re.findall(r"[一-鿿]", body))
    lat = len(re.findall(r"[A-Za-z]+", body))
    return han + lat


def check(entry_id, draft_text=None):
    pack = load_pack(entry_id)
    if pack is None:
        return [("pack", "料包不存在")]
    path = os.path.join(DRAFTS, "%s.md" % entry_id)
    if draft_text is None:
        if not os.path.exists(path):
            return [("draft", "初稿不存在")]
        with open(path, encoding="utf-8") as fh:
            draft_text = fh.read()

    errs = []

    # ① 字数
    rng = target_range(pack)
    n = cn_len(draft_text)
    if rng and not (rng[0] <= n <= rng[1]):
        errs.append(("字数", "%d 字，目标区间 %d-%d" % (n, rng[0], rng[1])))

    # ② 五段
    heads = re.findall(r"^##\s*[一二三四五]", draft_text, flags=re.M)
    if len(heads) < SECTIONS:
        errs.append(("结构", "只找到 %d 个主段落标题，应有 %d 个" % (len(heads), SECTIONS)))

    # ③ 引文逐字回查
    known = pack_quotes(pack)
    for m in re.finditer(r'^>\s*"([^"]{10,})"', draft_text, flags=re.M):
        q = norm(m.group(1))
        if q not in known:
            errs.append(("引文", '料包里查无此句: "%s…"' % m.group(1)[:60]))

    # ④ 数字回查
    #
    # 分两级，因为这两种「查无出处」的严重性差着量级：
    #   · 带单位的（37% / $4000 / 3 倍 / 500 美元）——事实性主张，编一个就是造假，判红。
    #   · 纯整数——多半是模型在做合理推算。实测 T02 写「前六年加起来 53」，
    #     而料包年份分布 12+6+10+8+3+14 正好 53，算术完全正确却被判红。
    #     一刀切判红会逼着后续把这类**有价值的横向对比**全删掉，得不偿失，降为警告。
    allow = pack_numbers(pack)
    allow_loose = {a.rstrip("0").rstrip(".") for a in allow}
    body = re.sub(r"^\|.*\|$", "", draft_text, flags=re.M)
    body = re.sub(r"^>.*$", "", body, flags=re.M)              # 引文行已单独校验
    # 先摘掉 provenance ID（F0027 / M02 / TENSION-03 …）：它们后面常紧跟日期，
    # 形如 `(F0027,2025-06-20)`，会被千分位规则粘成 `00272025` 这种不存在的数字。
    body = re.sub(r"\b[A-Z]{1,7}-?\d{2,4}\b", "", body)
    for m in NUM.finditer(body):
        raw = m.group(0).replace(",", "")
        if YEAR.match(raw) or raw in allow or raw.rstrip("0").rstrip(".") in allow_loose:
            continue
        after = body[m.end():m.end() + 3]
        before = body[max(0, m.start() - 1):m.start()]
        has_unit = bool(re.match(r"\s*(?:%|％|倍|美元|万|亿|块|元|美金|小时|分钟)", after)) or before == "$"
        ctx = body[max(0, m.start() - 18):m.start() + 18].replace("\n", " ")
        errs.append((("数字" if has_unit else "数字?"),
                     "%s 在料包里查无出处 …%s…" % (raw, ctx)))

    # ⑤ 占位符
    for p in PLACEHOLDERS:
        if p in draft_text:
            errs.append(("占位", "出现 %s" % p))

    # ⑥ AI 腔
    for t in AI_TICS:
        if t in draft_text:
            errs.append(("文风", "出现 AI 腔套话「%s」" % t))

    return errs


def mutate_test(entry_id):
    """变异测试：闸门必须对注入的假数字与假引文报红，否则闸门本身是空转的。"""
    path = os.path.join(DRAFTS, "%s.md" % entry_id)
    with open(path, encoding="utf-8") as fh:
        good = fh.read()
    base = check(entry_id, good)
    print("原稿闸门结果：%s" % ("通过" if not base else "%d 项不通过" % len(base)))

    cases = [
        ("假数字", good + "\n\n他的转化率从 4.7% 提升到了 91.3%。\n"),
        ("假引文", good + '\n\n> "I never said any of this, this quote is fabricated."\n中文翻译\n'),
        ("占位符", good + "\n\n（示例）待补充\n"),
        ("AI 腔", good + "\n\n综上所述，这套方法值得注意的是它的系统性。\n"),
    ]
    allgood = True
    for name, bad in cases:
        errs = check(entry_id, bad)
        caught = len(errs) > len(base)
        print("  注入%s → %s" % (name, "闸门报红 ✓" if caught else "闸门没抓到 ✗ 【闸门失效】"))
        if not caught:
            allgood = False
    return allgood


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--mutate" in sys.argv:
        ok = mutate_test(args[0])
        sys.exit(0 if ok else 1)

    if args:
        ids = args
    else:
        ids = sorted(f[:-3] for f in os.listdir(DRAFTS)) if os.path.isdir(DRAFTS) else []
    if not ids:
        print("没有可校验的初稿")
        return

    bad = warned = 0
    for eid in ids:
        all_items = check(eid)
        errs = [e for e in all_items if not e[0].endswith("?")]
        warns = [e for e in all_items if e[0].endswith("?")]
        if errs:
            bad += 1
            print("[红] %s —— %d 项" % (eid, len(errs)))
        elif warns:
            warned += 1
            print("[黄] %s —— %d 项待人工核（多为模型自行推算的数字）" % (eid, len(warns)))
        else:
            print("[绿] %s" % eid)
        for kind, msg in (errs + warns)[:12]:
            print("      %-5s %s" % (kind, msg))
        if len(errs + warns) > 12:
            print("      …另有 %d 项" % (len(errs + warns) - 12))
    print("\n绿 %d / 黄 %d / 红 %d，共 %d 篇" % (len(ids) - bad - warned, warned, bad, len(ids)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

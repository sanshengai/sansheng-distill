#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把深读初稿导出成网站数据包（按页面分片）。

分片理由：深读总量约 12 万字。全塞进人物主页会让单个 HTML 到 600KB，
所以按 tab 拆成四个独立页面，每页只 import 自己那一份 JSON：

    deepread-system.json      11 个系统层 + 8 张桥接卡
    deepread-models.json      19 个行动模型
    deepread-themes.json      13 个主题
    deepread-trajectory.json  6 个时段 + 10 条张力 + 6 条谱系

正文以 Markdown 原文入库，页面构建时用 @astrojs/markdown-remark 渲染
（项目已有依赖，不额外引包，也不用手写转换器）。

🔴 导出前强制过闸门：verify_deepread.py 判红的条目不许进包。
深读是全管线里唯一「模型自由发挥」的环节，页面上看不出真假。
"""
import json
import os
import re
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(BASE, "03_工作数据")
DRAFTS = os.path.join(WORK, "深读初稿")
# slug 从人物项目目录名自动推断，DISTILL_SLUG 可覆盖。加新人物时这个脚本零改动。
SLUG = os.environ.get("DISTILL_SLUG") or os.path.basename(BASE).strip().lower().replace(" ", "-")
WEB = os.path.join(
    os.path.dirname(os.path.dirname(BASE)),
    "个人网站", "web", "src", "data", "creator-distill", SLUG,
)

# 页面分片：page_key -> 收哪几类条目（顺序即页面上的呈现顺序）
PAGES = {
    "system": ["layer", "bridge"],
    "models": ["model"],
    "themes": ["theme"],
    "trajectory": ["phase", "tension", "lineage"],
}

TYPE_LABEL = {
    "layer": "系统层", "bridge": "桥接", "model": "行动模型",
    "theme": "主题", "phase": "时段", "tension": "张力", "lineage": "谱系",
}


def cn_len(text):
    body = re.sub(r"^\|.*\|$", "", text, flags=re.M)
    return len(re.findall(r"[一-鿿]", body)) + len(re.findall(r"[A-Za-z]+", body))


QUOTE_LINE = re.compile(r'(^>\s*)"([^"\n]*)"', re.M)


def escape_md_in_quotes(md):
    """转义引文行里的 Markdown 特殊字符。

    🔴 起因：一条原话是 `Treat your team like sh*t, and they will treat your clients
    like sh*t.` —— 两个星号之间的整段被 Markdown 当成**斜体**，页面上星号直接消失，
    引文不再逐字。这类冲突只在原话恰好含 * _ [ ] ` 时才触发，
    平时 320 条都好好的，唯独这一条烂掉，且看起来只是「排版有点怪」。
    """
    def repl(m):
        body = m.group(2)
        for ch in "\\*_[]`":
            body = body.replace(ch, "\\" + ch)
        return m.group(1) + '"' + body + '"'

    return QUOTE_LINE.sub(repl, md)


def hard_break_quotes(md):
    """让引文块里的「原话 / 译文 / 出处」三行真的分三行显示。

    🔴 Markdown 会把 blockquote 内的连续行合并成一个段落（软换行），
    页面上渲染出来是「"when you focus on one thing…" 当你把全部精力押在一件事上，
    你就让失败变得没道理。 ——2023 年 8 月」全挤在一段里 ——
    而这一页最该被看清的就是引文。行尾补 CommonMark 的反斜杠硬换行；
    用 `\\` 而不是「两个空格」，后者会被各种 trim 掉，属于会静默失效的写法。
    """
    lines = md.split("\n")
    out = []
    for i, line in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if line.startswith(">") and nxt.startswith(">") and not line.rstrip().endswith("\\"):
            line = line.rstrip() + " \\"
        out.append(line)
    return "\n".join(out)


def build_facts(web_dir):
    """每个条目的「结构提要」——深读页上排在长文前面的那几行。

    不是冗余：读者从目录直接跳到某一层时，需要先知道这层是干什么的，
    否则上来就是 2000 字论证会没有着落。主页那份结构图仍然保留，
    两处的用途不同（主页看全局关系，深读页看单条上下文）。
    """
    arch = json.load(open(os.path.join(web_dir, "architecture.json"), encoding="utf-8"))
    facts = {}
    layer_name = {l["layer_id"]: l["name"] for l in arch["system_layers"]}
    for l in arch["system_layers"]:
        facts[l["layer_id"]] = [
            ("这一层干什么", l.get("function", "")),
            ("输入", " · ".join(l.get("inputs") or [])),
            ("机制", l.get("mechanism", "")),
            ("输出", " · ".join(l.get("outputs") or [])),
            ("边界", "；".join(l.get("boundaries") or [])),
        ]
    for i, br in enumerate(arch.get("bridges") or []):
        bid = br.get("bridge_id") or "BR%02d" % (i + 1)
        facts[bid] = [
            ("从哪到哪", "%s → %s" % (layer_name.get(br.get("from_layer"), ""),
                                  layer_name.get(br.get("to_layer"), ""))),
            ("这张卡说什么", br.get("claim", "")),
        ]
    for m in json.load(open(os.path.join(web_dir, "models.json"), encoding="utf-8"))["models"]:
        facts[m.get("model_id", "")] = [
            ("解决什么问题", m.get("problem", "")),
            ("最小动作", " → ".join(m.get("steps") or [])),
            ("为什么有效", m.get("mechanism", "")),
            ("常见失败", "；".join(m.get("failure_modes") or [])),
            ("适用边界", "；".join(m.get("boundaries") or [])),
        ]
    for t in json.load(open(os.path.join(web_dir, "themes.json"), encoding="utf-8"))["themes"]:
        facts[t["theme_id"]] = [
            ("中心问题", t.get("central_question", "")),
            ("核心论点", t.get("core_thesis", "")),
            ("规模", "%s 个观点族 / %s 条证据" % (t.get("family_count", "?"), t.get("claim_count", "?"))),
        ]
    for t in json.load(open(os.path.join(web_dir, "tensions.json"), encoding="utf-8"))["tensions"]:
        facts[t["tension_id"]] = [
            ("A 面", t.get("side_a", "")),
            ("B 面", t.get("side_b", "")),
            ("为什么要紧", t.get("why_it_matters", "")),
        ]
    for p in json.load(open(os.path.join(web_dir, "timeline.json"), encoding="utf-8"))["phases"]:
        facts[p["phase_id"]] = [
            ("时段", "%s – %s" % (p.get("period_start"), p.get("period_end"))),
            ("主导焦点", " · ".join(p.get("dominant_focus") or [])),
            ("新出现或加强", " · ".join(p.get("new_or_intensified") or [])),
        ] + ([("证据强度提示", p["caution"])] if p.get("caution") else [])
    for i, li in enumerate(json.load(open(os.path.join(web_dir, "lineages.json"), encoding="utf-8"))["lineages"]):
        facts[li.get("lineage_id") or "LIN%02d" % (i + 1)] = [
            ("上游", li.get("upstream", "")),
            ("关系判定", li.get("classification", "")),
        ]
    return {k: [(a, b) for a, b in v if b] for k, v in facts.items() if k}


def main():
    manifest = json.load(open(os.path.join(WORK, "深读清单.json"), encoding="utf-8"))
    entries = {e["id"]: e for e in manifest["entries"]}

    env = {**os.environ, "PYTHONUTF8": "1"}

    # 中文标点闸门：半角标点不影响任何数据校验，但页面上会挤成一团。
    # 实测同一批 agent 会分裂成两派习惯，33/71 篇全篇半角 —— 必然复发，所以卡在导出前。
    punct = subprocess.run([sys.executable, os.path.join(BASE, "07_工具", "normalize_punct.py"), "--check"],
                           capture_output=True, text=True, encoding="utf-8", env=env)
    if punct.returncode != 0:
        print(punct.stdout)
        print("[中止] 先跑 normalize_punct.py 修中文标点，再导出。")
        return 1

    # 防幻觉闸门：红的一律不进包
    proc = subprocess.run([sys.executable, os.path.join(BASE, "07_工具", "verify_deepread.py")],
                          capture_output=True, text=True, encoding="utf-8", env=env)
    red = set(re.findall(r"^\[红\] (\S+)", proc.stdout or "", flags=re.M))
    if red:
        print("[闸门] %d 篇判红，不进包：%s" % (len(red), ", ".join(sorted(red))))

    facts = build_facts(WEB)
    by_page = {k: [] for k in PAGES}
    missing, exported = [], 0
    for eid, meta in entries.items():
        path = os.path.join(DRAFTS, "%s.md" % eid)
        if not os.path.exists(path):
            missing.append(eid)
            continue
        if eid in red:
            continue
        with open(path, encoding="utf-8") as fh:
            body = hard_break_quotes(escape_md_in_quotes(fh.read().strip()))
        page = next((p for p, types in PAGES.items() if meta["type"] in types), None)
        if page is None:
            continue
        by_page[page].append({
            "entry_id": eid,
            "type": meta["type"],
            "type_label": TYPE_LABEL.get(meta["type"], meta["type"]),
            "title": meta["title"],
            "words": cn_len(body),
            "facts": [{"label": a, "text": b} for a, b in facts.get(eid, [])],
            "body_md": body,
        })
        exported += 1

    order = {t: i for i, t in enumerate(sum(PAGES.values(), []))}
    for page, items in by_page.items():
        # 页内按类型分组，组内保持清单顺序（层 B1→B7→P1→P4，模型 M01→M19）
        idx = {e["id"]: i for i, e in enumerate(manifest["entries"])}
        items.sort(key=lambda x: (order.get(x["type"], 99), idx.get(x["entry_id"], 999)))
        out = {
            "slug": SLUG,
            "page": page,
            "count": len(items),
            "words": sum(i["words"] for i in items),
            "entries": items,
        }
        dest = os.path.join(WEB, "deepread-%s.json" % page)
        with open(dest, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)
        print("  deepread-%-11s %2d 篇 / %6s 字 / %6.1f KB"
              % (page + ".json", len(items), f"{out['words']:,}",
                 os.path.getsize(dest) / 1024))

    # 轻量索引：人物主页只需要「有几篇/多少字」来渲染深读入口。
    # 🔴 主页绝不能 import 上面那四个数据包 —— 那会把 12 万字正文全打进主页 HTML，
    # 拆页就白拆了。这份索引只有几百字节。
    # entry_ids：给人物主页判断「这张卡片有没有深读、能不能挂入口」。
    # 主页绝不能 import 那四个大包，所以这份 id 清单必须在索引里（73 个 id 不到 1KB）。
    index = {
        "slug": SLUG,
        "pages": {p: {"count": len(v), "words": sum(i["words"] for i in v)}
                  for p, v in by_page.items() if v},
        "entry_ids": sorted(i["entry_id"] for v in by_page.values() for i in v),
        "total_words": sum(sum(i["words"] for i in v) for v in by_page.values()),
        "total_count": exported,
    }
    with open(os.path.join(WEB, "deepread-index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=1)
    print("  deepread-index.json  %d 页入口 / %.1f KB"
          % (len(index["pages"]), os.path.getsize(os.path.join(WEB, "deepread-index.json")) / 1024))

    print("\n导出 %d 篇，共 %s 字" % (exported, f"{sum(sum(i['words'] for i in v) for v in by_page.values()):,}"))
    if missing:
        print("[!] 缺初稿 %d 篇：%s" % (len(missing), ", ".join(sorted(missing)[:20])))
    return 1 if (missing or red) else 0


if __name__ == "__main__":
    sys.exit(main())

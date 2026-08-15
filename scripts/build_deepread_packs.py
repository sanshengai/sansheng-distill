#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为每个可深读条目打一份「材料包」，供 P6.5 深读写作使用。

背景（2026-08-15）：Hormozi 页上线后发现的架构级缺陷 —— 管线单向收敛，
2726 条证据 → 1596 族 → 11 层抽象结论，收敛途中案例、数字、推演全丢了，
页面每个点只剩 67-298 字，读者想深读一个点时无处可读。

这个脚本反向把料捞回来。七类条目各走各的关联路径：

    层 / 模型 / 桥   family_ids  → families → claims → 原话
    主题             theme_id    → 按主题筛 families（T01 有 161 个族）
    张力             evidence_a_ids / evidence_b_ids 直接就是 claim_id，正反双方各取
    时段             evidence_ids → claims
    谱系             自带 upstream/adaptation 文字，另按 track 补相关族

🔴 每包必须带 provenance（family_id / 证据数 / 来源数 / 年份跨度），因为深读稿的
机械闸门要拿这些回查：写进深读的数字必须能在料包里找到出处，否则就是模型编的。
"""
import json
import os
import re
import sys
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(BASE, "03_工作数据")
# slug 从人物项目目录名自动推断（「Alex Hormozi」→ alex-hormozi，「Dan Koe」→ dan-koe），
# 目录名与 slug 不一致时用 DISTILL_SLUG 环境变量覆盖。加新人物时这个脚本零改动。
SLUG = os.environ.get("DISTILL_SLUG") or os.path.basename(BASE).strip().lower().replace(" ", "-")
WEB = os.path.join(
    os.path.dirname(os.path.dirname(BASE)),
    "个人网站", "web", "src", "data", "creator-distill", SLUG,
)
OUT = os.path.join(WORK, "深读料包")


def jload(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def jlines(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


FAMS = {f["family_id"]: f for f in jlines(os.path.join(WORK, "families.jsonl"))}
CLAIMS = {c["claim_id"]: c for c in jlines(os.path.join(WORK, "claims.jsonl"))}
SOURCES = {s["source_id"]: s for s in jload(os.path.join(WEB, "sources.json"))["sources"]}


def fam_block(fid):
    """一个族的完整料：正文 + 证据规模 + 年份跨度 + 一条已核实原话。"""
    f = FAMS.get(fid)
    if not f:
        return None
    quotes = []
    for cid in f.get("claim_ids") or []:
        c = CLAIMS.get(cid)
        if c and c.get("quote_verified") and c.get("quote_en"):
            src = SOURCES.get(c.get("source_id")) or {}
            quotes.append({
                "en": c["quote_en"],
                "date": c.get("published_at", ""),
                "source_title": src.get("title") or src.get("title_zh") or c.get("source_id"),
                "source_id": c.get("source_id"),
            })
    return {
        "family_id": fid,
        "kind": f.get("kind"),
        "statement": f.get("statement_zh", ""),
        "evidence": len(f.get("claim_ids") or []),
        "sources": f.get("source_count", 0),
        "first": (f.get("first_seen") or "")[:7],
        "last": (f.get("last_seen") or "")[:7],
        "years": sorted(set(f.get("years") or [])),
        "quotes": quotes[:3],
    }


def render_fams(blocks, title="挂载的观点族"):
    if not blocks:
        return ""
    out = ["## %s（%d 个）\n" % (title, len(blocks))]
    # 证据多的排前面 —— 写作时优先用交叉验证过的观点，单证据的当补充
    for b in sorted(blocks, key=lambda x: -x["evidence"]):
        out.append("### %s · %s ｜ 证据 %d 条 / 来源 %d 个 / %s ~ %s"
                   % (b["family_id"], b["kind"], b["evidence"], b["sources"], b["first"], b["last"]))
        out.append(b["statement"])
        for q in b["quotes"]:
            out.append('> 原话（%s，%s）: "%s"' % (q["date"], q["source_title"][:44], q["en"]))
        out.append("")
    return "\n".join(out)


def claim_block(cid):
    c = CLAIMS.get(cid)
    if not c:
        return None
    src = SOURCES.get(c.get("source_id")) or {}
    return {
        "claim_id": cid, "text": c.get("text_zh", ""), "kind": c.get("kind"),
        "date": c.get("published_at", ""), "status": c.get("source_status"),
        "quote": c.get("quote_en") if c.get("quote_verified") else "",
        "source_title": src.get("title") or src.get("title_zh") or c.get("source_id"),
    }


def render_claims(blocks, title):
    if not blocks:
        return ""
    out = ["## %s（%d 条）\n" % (title, len(blocks))]
    for b in sorted(blocks, key=lambda x: x["date"]):
        out.append("- **%s**（%s / %s）%s" % (b["claim_id"], b["date"], b["kind"], b["text"]))
        if b["quote"]:
            out.append('  > "%s" —— %s' % (b["quote"], b["source_title"][:44]))
    out.append("")
    return "\n".join(out)


def year_hist(fids):
    hist = defaultdict(int)
    for fid in fids:
        f = FAMS.get(fid)
        if not f:
            continue
        for y in f.get("years") or []:
            hist[str(y)] += 1
    return dict(sorted(hist.items()))


def write_pack(entry_id, kind, title, header_lines, body, target_words):
    os.makedirs(OUT, exist_ok=True)
    text = "\n".join([
        "# 深读料包 · %s" % title,
        "",
        "- 条目类型：**%s**　条目 ID：`%s`" % (kind, entry_id),
        "- 目标篇幅：**%s 字**" % target_words,
    ] + header_lines + ["", "---", "", body])
    path = os.path.join(OUT, "%s.md" % entry_id)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path, len(text)


def main():
    arch = jload(os.path.join(WEB, "architecture.json"))
    models = jload(os.path.join(WEB, "models.json"))["models"]
    themes = jload(os.path.join(WEB, "themes.json"))["themes"]
    tensions = jload(os.path.join(WEB, "tensions.json"))["tensions"]
    lineages = jload(os.path.join(WEB, "lineages.json"))["lineages"]
    phases = jload(os.path.join(WEB, "timeline.json"))["phases"]
    tension_titles = [t["title"] for t in tensions]
    track_name = {t["track_id"]: t["name"] for t in arch.get("tracks") or []}

    manifest = []

    # ── 系统层 ──────────────────────────────────────────────
    #
    # 🔴 层只挂 7-10 个族，而它所属主题动辄上百个族（T01 有 161 个）。只发挂载族的话，
    # 写深读时会**够不着本层最有说服力的材料**——实测：手写 B2_offer 样本时用到的
    # 「健身房该收 $167-$225」出自 F0257，属于同一主题却没挂在这一层上，闸门直接判为
    # 「料包里查无出处」。所以按挂载族的 theme_id 分布找出本层的主导主题，
    # 再补进这些主题下证据数最高、尚未挂载的族，标注为「同主题补充材料」。
    for layer in arch["system_layers"]:
        fids = layer.get("family_ids") or []
        blocks = [b for b in (fam_block(f) for f in fids) if b]
        theme_hits = defaultdict(int)
        for fid in fids:
            f = FAMS.get(fid)
            if f and f.get("theme_id"):
                theme_hits[f["theme_id"]] += 1
        main_themes = [t for t, _ in sorted(theme_hits.items(), key=lambda kv: -kv[1])[:2]]
        extra_pool = [f for f in FAMS.values()
                      if f.get("theme_id") in main_themes and f["family_id"] not in set(fids)]
        extra_pool.sort(key=lambda f: (-len(f.get("claim_ids") or []), -f.get("source_count", 0)))
        extra = [b for b in (fam_block(f["family_id"]) for f in extra_pool[:14]) if b]
        head = [
            "- 所属轨：%s" % track_name.get(layer.get("track"), layer.get("track") or "单轨"),
            "",
            "## 这一层现在页面上的内容（%d 字，深读要在此之上展开，不是复述）" % (
                len(layer.get("function", "")) + len(layer.get("mechanism", ""))),
            "- **功能**：%s" % layer.get("function", ""),
            "- **输入**：%s" % " · ".join(layer.get("inputs") or []),
            "- **机制**：%s" % layer.get("mechanism", ""),
            "- **输出**：%s" % " · ".join(layer.get("outputs") or []),
            "- **边界**：%s" % "；".join(layer.get("boundaries") or []),
            "",
            "## 年份分布（用来写「他这些年改了什么」）",
            "`%s`" % json.dumps(year_hist(fids), ensure_ascii=False),
        ]
        body = render_fams(blocks, "本层挂载的观点族（骨架）")
        if extra:
            body += "\n" + render_fams(
                extra, "同主题补充材料（%s，可用来举证与展开，但别喧宾夺主）"
                % " / ".join(main_themes))
        p, n = write_pack(layer["layer_id"], "系统层", layer["name"], head, body, "2000-2500")
        manifest.append({"id": layer["layer_id"], "type": "layer", "title": layer["name"],
                         "pack": p, "pack_chars": n, "fams": len(blocks) + len(extra),
                         "evidence": sum(b["evidence"] for b in blocks + extra),
                         "target": "2000-2500"})

    # ── 主题（材料最厚：按 theme_id 反查全部族，取证据数 Top 40）──
    for th in themes:
        tid = th["theme_id"]
        pool = [f for f in FAMS.values() if f.get("theme_id") == tid]
        pool.sort(key=lambda f: (-len(f.get("claim_ids") or []), -f.get("source_count", 0)))
        top = pool[:40]
        blocks = [b for b in (fam_block(f["family_id"]) for f in top) if b]
        head = [
            "- 所属轨：%s" % track_name.get(th.get("track"), th.get("track") or ""),
            "- 全库规模：**%d 个族 / %d 条证据**（本包给出证据数最高的 %d 个族）"
            % (th.get("family_count", len(pool)), th.get("claim_count", 0), len(top)),
            "",
            "## 这个主题现在页面上的内容",
            "- **中心问题**：%s" % th.get("central_question", ""),
            "- **核心论点**：%s" % th.get("core_thesis", ""),
            "- **别名**：%s" % " / ".join(th.get("aliases") or []),
            "- **不含**：%s" % " / ".join(th.get("exclusion_rules") or []),
            "",
            "## 年份分布",
            "`%s`" % json.dumps(year_hist([f["family_id"] for f in pool]), ensure_ascii=False),
        ]
        p, n = write_pack(tid, "主题", th["name_zh"], head,
                          render_fams(blocks, "证据最厚的观点族"), "2500-3500")
        manifest.append({"id": tid, "type": "theme", "title": th["name_zh"], "pack": p,
                         "pack_chars": n, "fams": len(blocks),
                         "evidence": sum(b["evidence"] for b in blocks), "target": "2500-3500"})

    # ── 行动模型 ────────────────────────────────────────────
    for i, m in enumerate(models):
        mid = m.get("model_id") or "M%02d" % (i + 1)
        blocks = [b for b in (fam_block(f) for f in (m.get("family_ids") or [])) if b]
        head = [
            "- 所属轨：%s" % track_name.get(m.get("track"), m.get("track") or "单轨"),
            "",
            "## 这个模型现在页面上的内容",
            "- **解决的问题**：%s" % m.get("problem", ""),
            "- **步骤**：%s" % " → ".join(m.get("steps") or []),
            "- **为什么有效**：%s" % m.get("mechanism", ""),
            "- **常见失败**：%s" % "；".join(m.get("failure_modes") or []),
            "- **适用边界**：%s" % "；".join(m.get("boundaries") or []),
        ]
        p, n = write_pack(mid, "行动模型", m["name"], head, render_fams(blocks), "1200-1500")
        manifest.append({"id": mid, "type": "model", "title": m["name"], "pack": p,
                         "pack_chars": n, "fams": len(blocks),
                         "evidence": sum(b["evidence"] for b in blocks), "target": "1200-1500"})

    # ── 张力（正反双方各有 claim 级证据，天然适合深读）──────
    for t in tensions:
        a = [b for b in (claim_block(c) for c in (t.get("evidence_a_ids") or [])) if b]
        b_ = [b for b in (claim_block(c) for c in (t.get("evidence_b_ids") or [])) if b]
        head = [
            "- 判定状态：`%s`" % t.get("status", ""),
            "",
            "## 这条张力现在页面上的内容",
            "- **A 面**：%s" % t.get("side_a", ""),
            "- **B 面**：%s" % t.get("side_b", ""),
            "- **为什么要紧**：%s" % t.get("why_it_matters", ""),
            "- **编辑判断**：%s" % t.get("editorial_assessment", ""),
        ]
        body = render_claims(a, "A 面的一手证据") + "\n" + render_claims(b_, "B 面的一手证据")
        p, n = write_pack(t["tension_id"], "张力", t["title"], head, body, "1200-1500")
        manifest.append({"id": t["tension_id"], "type": "tension", "title": t["title"], "pack": p,
                         "pack_chars": n, "fams": 0, "evidence": len(a) + len(b_),
                         "target": "1200-1500"})

    # ── 时段 ────────────────────────────────────────────────
    for ph in phases:
        cl = [b for b in (claim_block(c) for c in (ph.get("evidence_ids") or [])) if b]
        head = [
            "- 时段：**%s – %s**" % (ph.get("period_start"), ph.get("period_end")),
            "",
            "## 这一段现在页面上的内容",
            "- **主导焦点**：%s" % " · ".join(ph.get("dominant_focus") or []),
            "- **延续下来的**：%s" % " · ".join(ph.get("stable_carry_over") or []),
            "- **新出现或加强的**：%s" % " · ".join(ph.get("new_or_intensified") or []),
            "- **事业/产品信号**：%s" % " · ".join(ph.get("career_product_signals") or []),
            "- **注意**：%s" % (ph.get("caution") or "无"),
        ]
        p, n = write_pack(ph["phase_id"], "时段", ph["label"], head,
                          render_claims(cl, "这一段的一手证据"), "1500-1800")
        manifest.append({"id": ph["phase_id"], "type": "phase", "title": ph["label"], "pack": p,
                         "pack_chars": n, "fams": 0, "evidence": len(cl), "target": "1500-1800"})

    # ── 桥接 ────────────────────────────────────────────────
    layer_name = {l["layer_id"]: l["name"] for l in arch["system_layers"]}
    for i, br in enumerate(arch.get("bridges") or []):
        bid = br.get("bridge_id") or "BR%02d" % (i + 1)
        blocks = [b for b in (fam_block(f) for f in (br.get("family_ids") or [])) if b]
        # 🔴 标题用「起点层 → 终点层」，不要截断 claim。
        # 早先取 `claim[:24]`，目录里出现的是「…不是话术问题——他说那种「」这种
        # 断在半句话中间、还拖着一个孤立引号的东西。桥接卡的本质就是两层的连接，
        # 层名对既完整又能一眼看出它连的是哪两块。
        from_name = layer_name.get(br.get("from_layer"), br.get("from_layer"))
        to_name = layer_name.get(br.get("to_layer"), br.get("to_layer"))
        bridge_title = "%s → %s" % (from_name, to_name)
        head = [
            "- 桥接方向：**%s**" % bridge_title,
            "",
            "## 这张桥接卡现在页面上的内容",
            br.get("claim", ""),
        ]
        p, n = write_pack(bid, "桥接", bridge_title, head, render_fams(blocks), "700-900")
        manifest.append({"id": bid, "type": "bridge", "title": bridge_title, "pack": p,
                         "pack_chars": n, "fams": len(blocks),
                         "evidence": sum(b["evidence"] for b in blocks), "target": "700-900"})

    # ── 谱系（自带文字，另按检索词补料）──────────────────────
    # 谱系不挂 family_ids，只补 adaptation 一段文字的话包只有 291 字符，写出来
    # 必然靠模型自己的既有知识填（「Dan Kennedy 是谁」），那是幻觉高发区。
    # 所以从 name/adaptation 里提检索词，去族库里把他**自己讲过**的相关内容捞回来，
    # 让深读能落在一手证据上，而不是落在模型对这位上游人物的印象上。
    for i, li in enumerate(lineages):
        lid = li.get("lineage_id") or "LIN%02d" % (i + 1)
        # 🔴 检索词不能用 `[一-鿿]{2,4}` 直接从标题切 —— 中文没有词边界，
        # 「一致性原则 → CTA 连环」会被切成「一致性原」+「连环」这种废词，
        # 一个族都捞不到（实测 LIN04 料包因此是空的）。改用滑动窗口穷举 2-4 字子串，
        # 再靠「命中词数」排序把噪音压下去：真正相关的族会同时命中好几个窗口。
        # 英文 token 单列，CTA / Dan Kennedy 这类专名是最有效的检索词。
        source_text = li.get("name", "") + " " + li.get("adaptation", "") + " " + li.get("upstream", "")
        keys = set(re.findall(r"[A-Za-z][A-Za-z']{2,}", source_text))
        for run in re.findall(r"[一-鿿]+", li.get("name", "")):
            for n in (2, 3, 4):
                for i in range(len(run) - n + 1):
                    keys.add(run[i:i + n])
        keys.update(re.findall(r"「([^」]{2,10})」", li.get("adaptation", "")))
        keys = {k for k in keys if len(k) >= 2 and k not in {"他的", "自己", "这个", "那句", "the", "and", "for"}}
        hits = {}
        for f in FAMS.values():
            st = f.get("statement_zh", "")
            score = sum(1 for k in keys if k in st)
            if score:
                hits[f["family_id"]] = (score, len(f.get("claim_ids") or []))
        top = sorted(hits, key=lambda k: (-hits[k][0], -hits[k][1]))[:10]
        blocks = [b for b in (fam_block(f) for f in top) if b]
        head = [
            "- 上游：**%s**　分类：%s" % (li.get("upstream", ""), li.get("classification", "")),
            "- 参考链接：%s" % (li.get("source_url") or "无"),
            "- 检索词：%s" % " / ".join(sorted(keys)),
            "",
            "## 这条谱系现在页面上的内容",
            "- **他怎么改造的**：%s" % li.get("adaptation", ""),
        ]
        p, n = write_pack(lid, "谱系", li.get("name", ""), head,
                          render_fams(blocks, "他自己讲过的相关内容（按检索词命中）"), "700-900")
        manifest.append({"id": lid, "type": "lineage", "title": li.get("name", ""), "pack": p,
                         "pack_chars": n, "fams": len(blocks),
                         "evidence": sum(b["evidence"] for b in blocks), "target": "700-900"})

    with open(os.path.join(WORK, "深读清单.json"), "w", encoding="utf-8") as fh:
        json.dump({"entries": manifest, "tension_titles": tension_titles},
                  fh, ensure_ascii=False, indent=2)

    by = defaultdict(lambda: [0, 0, 0])
    for e in manifest:
        by[e["type"]][0] += 1
        by[e["type"]][1] += e["pack_chars"]
        by[e["type"]][2] += e["evidence"]
    print("料包 %d 份 → %s" % (len(manifest), OUT))
    for k, (n, ch, ev) in by.items():
        print("  %-8s %2d 份 | 料 %7d 字符 | 均 %6d | 证据 %4d" % (k, n, ch, ch // n, ev))
    total = sum(e["pack_chars"] for e in manifest)
    print("  合计料 %s 字符（约 %.0fK token 输入）" % (f"{total:,}", total / 1.6 / 1000))
    thin = [e for e in manifest if e["pack_chars"] < 900]
    if thin:
        print("  [!] 料偏薄（<900 字符）%d 份：%s" % (len(thin), ", ".join(e["id"] for e in thin)))


if __name__ == "__main__":
    main()

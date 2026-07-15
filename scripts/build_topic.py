#!/usr/bin/env python3
"""多书「主题聚合专题」聚合器 -- 只读各书 distill.json + knowledge-index.json 做确定性集合运算聚合成 topic.json。

绝不重蒸:只读 distill.json / knowledge-index.json(不碰 book.txt/raw),脚本内禁跑 LLM / 禁联网。
契约唯一权威: sansheng-distill/references/topic-craft.md (§2 schema / §3 契约 / §4 派生规则 / §6 enrich)。

用法:
  python build_topic.py --topic "主题名" --data-root <读书蒸馏> --manual <m.json> [--index <i.json>] [--enrich <e.json>] --out <topic.json> [--force]

成员圈定只认 manual.members(显式 slug 列表);--data-root 用于定位 {slug}/distill.json 与默认 <data-root>/knowledge-index.json。
exit: 0 正常 / 2 输入或防覆盖问题 / 3 触发门槛未达(有效成员 <3)。

破折号一律 --(非中文长破折号);禁 datetime.now(生成时戳由主控事后补)。
"""
import argparse
import json
import re
import sys
from pathlib import Path

# Windows 管道默认 cp936,打中文 JSON 前必须强制 UTF-8(本仓库跨脚本契约)
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

AGGREGATOR_VERSION = "1"
MIN_MEMBERS = 3  # 触发门槛(topic-craft §0):同主题 <3 本不生成
CERTAINTY_VALUES = ("book_explicit", "cross_book_synthesis", "general_knowledge")

PUNCT_RE = re.compile(r"[\s　-〿＀-￯,.!?;:\"'`()\[\]{}<>/\\|~@#$%^&*_+=·、,。!?;:「」『』（）【】]")


def norm(s: str) -> str:
    """规范化:去标点空白、小写(concept 名跨源匹配用)。"""
    if not s:
        return ""
    return PUNCT_RE.sub("", str(s)).lower()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- 收集

def collect_members(manual, data_root, warnings):
    """按 manual.members(显式 slug)逐个加载 distill.json;缺失剔除 + warning。返回 [(slug, distill_dict)]。"""
    members = manual.get("members") or []
    if not isinstance(members, list):
        print("manual.members 必须是 slug 列表", file=sys.stderr)
        sys.exit(2)
    out = []
    seen = set()
    for slug in members:
        if not slug or slug in seen:
            continue
        seen.add(slug)
        p = Path(data_root) / str(slug) / "distill.json"
        if not p.is_file():
            warnings.append(f"成员 {slug} 的 distill.json 缺失({p}),已剔除")
            continue
        try:
            out.append((slug, load_json(p)))
        except (json.JSONDecodeError, OSError) as e:
            warnings.append(f"成员 {slug} 的 distill.json 解析失败({e}),已剔除")
    return out


def load_index_concepts(index_path):
    """加载 knowledge-index.json → {norm(concept): {concept, one_liner, by_slug:{slug:entry}, relations:set}}。缺失/空 → {}。"""
    if not index_path or not Path(index_path).is_file():
        return {}
    try:
        idx = load_json(Path(index_path))
    except Exception:
        return {}
    concepts = idx.get("concepts") if isinstance(idx, dict) else None
    if not concepts:
        return {}
    out = {}
    for c in concepts:
        name = c.get("concept")
        if not name:
            continue
        by_slug = {}
        relations = set()
        for e in c.get("entries", []) or []:
            s = e.get("book_slug")
            if s:
                by_slug[s] = e
            if e.get("relation"):
                relations.add(e["relation"])
        out[norm(name)] = {"concept": name, "one_liner": c.get("one_liner", ""),
                           "by_slug": by_slug, "relations": relations}
    return out


# --------------------------------------------------------------------------- 派生

def derive_books(members, manual):
    """🤖 直取 distill 元数据 + 合并 manual.book_meta(one_liner/role_in_topic)+ 从 schools 反推 school_id。"""
    book_meta = manual.get("book_meta") or {}
    # slug -> school_id(反推:书落在哪个 school.members)
    school_of = {}
    for sc in manual.get("schools", []) or []:
        for s in sc.get("members", []) or []:
            school_of.setdefault(s, sc.get("id"))
    out = []
    for slug, d in members:
        meta = book_meta.get(slug, {}) or {}
        one_liner = meta.get("one_liner")
        if not one_liner:  # 回退 distill 的餐巾纸/核心问句
            napkin = d.get("napkin") or {}
            one_liner = napkin.get("one_liner") or d.get("core_question") or ""
        out.append({
            "slug": slug,
            "title": d.get("title"),
            "book_type": d.get("book_type"),
            "pub_year": d.get("pub_year"),
            "stakes": d.get("stakes", "normal"),
            "school_id": school_of.get(slug),
            "one_liner": one_liner,
            "role_in_topic": meta.get("role_in_topic"),
        })
    return out


def resolve_schools(manual, member_set, title_of, warnings):
    """✍️ 流派纯 manual;校验 members⊆成员、补 color_idx、解析 anchor_book title。"""
    out = []
    for i, sc in enumerate(manual.get("schools", []) or []):
        name = sc.get("name")
        if not name:
            warnings.append(f"school[{i}] 缺 name,已跳过")
            continue
        mem = [s for s in (sc.get("members") or []) if s in member_set]
        bad = [s for s in (sc.get("members") or []) if s not in member_set]
        for s in bad:
            warnings.append(f"school「{name}」的成员 {s} 不在 members 集,已剔除")
        anchor = sc.get("anchor_book")
        if anchor and anchor not in member_set:
            warnings.append(f"school「{name}」anchor_book {anchor} 不在 members 集")
            anchor = None
        out.append({
            "id": sc.get("id") or f"s{i + 1}",
            "name": name,
            "claim": sc.get("claim", ""),
            "members": mem,
            "anchor_book": anchor,
            "anchor_title": title_of.get(anchor) if anchor else None,
            "color_idx": sc.get("color_idx") if isinstance(sc.get("color_idx"), int) else i,
        })
    return out


def _member_slug(m):
    """position member 可为 'slug' 或 {'slug':..,'stance':..,'quote':..,'anchor':..}。"""
    return m if isinstance(m, str) else (m.get("slug") if isinstance(m, dict) else None)


def resolve_disputes(manual, index_concepts, member_set, warnings):
    """🔶 每条 dispute:从 index 摊各 slug 立场 + 判 index_relation(§4.3)。parallel 剔除。"""
    out = []
    for i, d in enumerate(manual.get("disputes", []) or []):
        q = d.get("question")
        if not q:
            warnings.append(f"dispute[{i}] 缺 question,已跳过")
            continue
        did = d.get("id") or f"d{i + 1}"
        concept = d.get("concept")
        ic = index_concepts.get(norm(concept)) if concept else None
        if concept and ic is None:
            warnings.append(f"dispute「{q}」的 concept「{concept}」在 knowledge-index 找不到,立场全靠 manual 内联")

        positions = []
        pos_ok = True
        for pi, pos in enumerate(d.get("positions", []) or []):
            label = pos.get("label")
            books = []
            for m in pos.get("members", []) or []:
                slug = _member_slug(m)
                if not slug:
                    continue
                if slug not in member_set:
                    warnings.append(f"dispute「{q}」position「{label}」的 {slug} 不在 members 集,已剔除")
                    continue
                # 立场优先 index,回退 manual 内联
                entry = ic["by_slug"].get(slug) if ic else None
                inline = m if isinstance(m, dict) else {}
                stance = inline.get("stance") or (entry.get("stance") if entry else "")
                quote = inline.get("quote") or (entry.get("quote") if entry else "")
                anchor = inline.get("anchor") or (entry.get("anchor") if entry else "")
                if not stance:
                    warnings.append(f"dispute「{q}」的 {slug} 无 stance(index 无该 concept-slug 且 manual 未内联)")
                books.append({"slug": slug, "stance": stance, "quote": quote, "anchor": anchor})
            if not books:
                pos_ok = False
            positions.append({"label": label, "books": books})

        # index_relation 判定(§4.3)
        has_contra = bool(ic and "CONTRADICTS" in ic["relations"])
        curated = bool(d.get("curated")) or (len(positions) >= 2 and pos_ok)
        if has_contra:
            rel = "CONTRADICTS"
        elif curated:
            rel = "curated"
        else:
            rel = "parallel"

        if rel == "parallel":
            warnings.append(f"dispute「{q}」判为 parallel(松散并列,非真交锋),已从分歧矩阵剔除")
            continue

        out.append({
            "id": did, "question": q, "axis": d.get("axis", ""),
            "concept": concept, "index_relation": rel,
            "positions": positions, "note": d.get("note"),
        })
    return out


def _pull_certainty(slug, anchor, members_by_slug):
    """dimensions cell 缺 certainty 时:从该 distill 的 decision_rules/core_ideas 拉;
    优先 anchor 精确匹配,否则若全书 certainty 单一取值则用之,再否则 book_explicit。"""
    d = members_by_slug.get(slug)
    if not d:
        return "book_explicit"
    items = list(d.get("decision_rules", []) or []) + list(d.get("core_ideas", []) or [])
    # anchor 精确匹配
    if anchor:
        for it in items:
            if it.get("anchor") and norm(it["anchor"]) == norm(anchor) and it.get("certainty") in CERTAINTY_VALUES:
                return it["certainty"]
    # 全书单一 certainty
    seen = {it.get("certainty") for it in items if it.get("certainty") in CERTAINTY_VALUES}
    if len(seen) == 1:
        return next(iter(seen))
    return "book_explicit"


def resolve_dimensions(manual, member_set, members_by_slug, warnings):
    """✍️🔶 维度对照表:name/value 纯 manual;certainty 缺则拉 distill;校验 slug∈成员 + certainty 合法。"""
    out = []
    for i, dim in enumerate(manual.get("dimensions", []) or []):
        name = dim.get("name")
        if not name:
            warnings.append(f"dimension[{i}] 缺 name,已跳过")
            continue
        cells = []
        for cell in dim.get("cells", []) or []:
            slug = cell.get("slug")
            if slug not in member_set:
                warnings.append(f"维度「{name}」cell 的 {slug} 不在 members 集,已剔除")
                continue
            cert = cell.get("certainty")
            if cert is None:
                cert = _pull_certainty(slug, cell.get("anchor"), members_by_slug)
            elif cert not in CERTAINTY_VALUES:
                warnings.append(f"维度「{name}」的 {slug} certainty「{cert}」∉ 三枚举,改 book_explicit")
                cert = "book_explicit"
            cells.append({"slug": slug, "value": cell.get("value", ""),
                          "certainty": cert, "anchor": cell.get("anchor", "")})
        if not cells:
            warnings.append(f"维度「{name}」无有效 cell,已跳过")
            continue
        out.append({"id": dim.get("id") or f"dim{i + 1}", "name": name,
                    "note": dim.get("note", ""), "cells": cells})
    return out


def resolve_consensus(manual, member_set, warnings):
    con = manual.get("consensus") or {}
    if not con:
        return None
    agreements = []
    for a in con.get("agreements", []) or []:
        if not a.get("text"):
            continue
        books = [s for s in (a.get("books") or []) if s in member_set]
        agreements.append({"text": a["text"], "books": books})
    caveats = [{"text": c.get("text", "")} for c in (con.get("caveats") or []) if c.get("text")]
    if not agreements and not caveats:
        return None
    return {"agreements": agreements, "caveats": caveats}


def resolve_reading_guide(manual, member_set, warnings):
    out = []
    for g in manual.get("reading_guide", []) or []:
        slug = g.get("slug")
        if slug and slug not in member_set:
            warnings.append(f"reading_guide 的 {slug} 不在 members 集,已剔除")
            continue
        out.append({"slug": slug, "why": g.get("why", "")})
    return out


# --------------------------------------------------------------------------- 组装

def build_topic_json(members, manual, enrich, index_concepts):
    warnings = []
    member_set = {slug for slug, _ in members}
    members_by_slug = {slug: d for slug, d in members}
    books = derive_books(members, manual)
    title_of = {b["slug"]: b["title"] for b in books}

    schools = resolve_schools(manual, member_set, title_of, warnings)
    disputes = resolve_disputes(manual, index_concepts, member_set, warnings)
    dimensions = resolve_dimensions(manual, member_set, members_by_slug, warnings)
    consensus = resolve_consensus(manual, member_set, warnings)
    reading_guide = resolve_reading_guide(manual, member_set, warnings)

    # 缺 manual 认知字段 → 记 warning(脚本不臆造)
    if not manual.get("intro"):
        warnings.append("manual 缺 intro(定位卡无导语)")
    if not manual.get("schools"):
        warnings.append("manual 缺 schools(无分类地图)")
    if not manual.get("disputes"):
        warnings.append("manual 缺 disputes(无分歧矩阵 -- 主题聚合的核心增量)")
    if not manual.get("dimensions"):
        warnings.append("manual 缺 dimensions(无维度对照表)")
    if not manual.get("verdict"):
        warnings.append("manual 缺 verdict(无「怎么选」收口)")

    ext = (enrich or {}).get("external_debate")

    doc = {
        "topic": manual.get("topic"),
        "slug": manual.get("slug"),
        "subtitle": manual.get("subtitle"),
        "intro": manual.get("intro"),
        "verdict": manual.get("verdict"),
        "books": books,
        "schools": schools,
        "disputes": disputes,
        "dimensions": dimensions,
        "consensus": consensus,
        "reading_guide": reading_guide,
        "external_debate": ext,
        "_provenance": {
            "generated_from": [slug for slug, _ in members],
            "topic_slug": manual.get("slug"),
            "member_count": len(members),
            "school_count": len(schools),
            "dispute_count": len(disputes),
            "aggregator_version": AGGREGATOR_VERSION,
            "warnings": warnings,
        },
    }
    return doc, warnings


def summarize(doc):
    disp = doc["disputes"]
    rc = {}
    for d in disp:
        rc[d["index_relation"]] = rc.get(d["index_relation"], 0) + 1
    return {
        "topic": doc["topic"],
        "books": len(doc["books"]),
        "schools": len(doc["schools"]),
        "disputes_total": len(disp),
        "disputes_by_relation": rc,
        "dimensions": len(doc["dimensions"]),
        "dimension_cells": sum(len(d["cells"]) for d in doc["dimensions"]),
        "consensus": bool(doc["consensus"]),
        "reading_guide": len(doc["reading_guide"]),
        "external_debate": bool(doc["external_debate"]),
        "_warnings": doc["_provenance"]["warnings"],
    }


def main():
    ap = argparse.ArgumentParser(description="多书主题聚合器(只读 distill.json + knowledge-index,确定性)")
    ap.add_argument("--topic", help="主题名(仅记录/校验;成员圈定只认 manual.members)")
    ap.add_argument("--data-root", required=True, help="读书蒸馏根目录(定位 {slug}/distill.json 与 knowledge-index.json)")
    ap.add_argument("--index", help="knowledge-index.json 路径(默认 <data-root>/knowledge-index.json)")
    ap.add_argument("--manual", help="topic.manual.json 路径")
    ap.add_argument("--enrich", help="topic.enrich.json 路径")
    ap.add_argument("--out", required=True, help="输出 topic.json 路径")
    ap.add_argument("--force", action="store_true", help="防覆盖栏:manual 缺失且 out 已存在时强制重建")
    a = ap.parse_args()

    out_path = Path(a.out)
    manual_path = Path(a.manual) if a.manual else None
    manual_present = bool(manual_path and manual_path.is_file())

    # 防覆盖栏(§3③):out 已存在 且 manual 文件缺失 且 无 --force → 拒跑
    if out_path.exists() and not manual_present and not a.force:
        print(f"防覆盖:{out_path} 已存在但 manual 文件缺失,拒绝重建(会丢人工归类);确认请加 --force",
              file=sys.stderr)
        return 2

    manual = load_json(manual_path) if manual_present else {}
    warnings0 = []
    members = collect_members(manual, a.data_root, warnings0)

    # 触发门槛(§3②):有效成员 <3 → 不生成
    if len(members) < MIN_MEMBERS:
        print(f"触发门槛未达:有效成员仅 {len(members)} 本(需 >={MIN_MEMBERS}),不生成主题聚合页", file=sys.stderr)
        return 3

    enrich = {}
    if a.enrich and Path(a.enrich).is_file():
        enrich = load_json(Path(a.enrich))

    # 索引路径:显式 --index 优先,否则默认 <data-root>/knowledge-index.json
    index_path = a.index
    if not index_path:
        cand = Path(a.data_root) / "knowledge-index.json"
        if cand.is_file():
            index_path = str(cand)
    index_concepts = load_index_concepts(index_path)

    doc, _ = build_topic_json(members, manual, enrich, index_concepts)
    # collect_members 的 warning 并入 provenance
    doc["_provenance"]["warnings"] = warnings0 + doc["_provenance"]["warnings"]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")

    print(json.dumps(summarize(doc), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

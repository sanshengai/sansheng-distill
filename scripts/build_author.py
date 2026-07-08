#!/usr/bin/env python3
"""多书作者「思想演变」聚合器 -- 只读各书 distill.json 做确定性集合运算聚合成 author.json。

绝不重蒸:只读 distill.json(不碰 book.txt/raw),脚本内禁跑 LLM / 禁联网。
契约唯一权威: sansheng-distill/references/author-craft.md (§2 schema / §3 契约 / §4 派生规则 / §6 enrich)。

用法:
  python build_author.py --author "名" --data-root <读书蒸馏> --manual <m.json> --enrich <e.json> --out <author.json> [--force]
  python build_author.py --inputs "<glob 指向若干 distill.json>" --manual <m.json> --enrich <e.json> --out <author.json> [--force]

exit: 0 正常 / 2 输入或防覆盖问题 / 3 触发门槛未达(该作者 <2 部已蒸)。

破折号一律 --(非中文长破折号);pub_year 缺的书进 _warnings 且不进时间线;禁 datetime.now(生成时戳由主控事后补)。
"""
import argparse
import difflib
import glob as globmod
import json
import re
import sys
from pathlib import Path

# Windows 管道默认 cp936,打中文 JSON 前必须强制 UTF-8(本仓库跨脚本契约)
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

AGGREGATOR_VERSION = "1"

# 概念换手率 Jaccard 距离阈值(§4.1)
JACCARD_BOUNDARY = 0.6
# core_question 主题变:去停用词后关键词字集相似度低于此 → 判为换题(§4.1「简单判」)
QUESTION_SIM_BOUNDARY = 0.4
# 年份断档 > 此年数 → 时期边界
YEAR_GAP_BOUNDARY = 4
# 母题聚类:规范化字符串相似度 >= 此值视为同一 idea(§4.2)
MOTIF_SIM = 0.85

# core_question 关键词提取用的停用字(功能字 + 疑问框架字),纯确定性、不依赖分词
STOP_CHARS = set("的了在是和与也就都而及或如何为对把被让使这那有一个之其所到并从每很以能会要将且不再让好么吗呢真正日复")
PUNCT_RE = re.compile(r"[\s　-〿＀-￯,.!?;:\"'`()\[\]{}<>/\\|~@#$%^&*_+=-]")
# 立场语义对立的判据标记(§4.3「简单判:stance 串差异大 + 否定/对立词」)
OPPOSITION_MARKERS = ("不是", "而非", "并非", "不再", "相反", "反而", "却", "不", "非")


def norm(s: str) -> str:
    """规范化:去标点空白、小写(§4.2 母题聚类 / tensions / critique 匹配共用)。"""
    if not s:
        return ""
    return PUNCT_RE.sub("", str(s)).lower()


def sim(a: str, b: str) -> float:
    """规范化后 difflib 相似度。"""
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def keyword_chars(q: str) -> set:
    """core_question 去停用字 + 去标点后的内容字集(用于主题变判定)。"""
    return {c for c in str(q) if c not in STOP_CHARS and not PUNCT_RE.match(c)}


def jaccard_sim(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    u = a | b
    return len(a & b) / len(u) if u else 1.0


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- 收集

def collect_distills(args):
    """返回 (distills, warnings)。distills 是 dict 列表。"""
    paths = []
    if args.inputs:
        paths = [Path(p) for p in sorted(globmod.glob(args.inputs))]
    elif args.author and args.data_root:
        for p in sorted(Path(args.data_root).glob("*/distill.json")):
            try:
                d = load_json(p)
            except (json.JSONDecodeError, OSError):
                continue
            if str(d.get("author", "")).strip() == str(args.author).strip():
                paths.append(p)
    else:
        print("必须提供 --inputs 或 (--author + --data-root)", file=sys.stderr)
        sys.exit(2)

    distills = []
    for p in paths:
        try:
            distills.append(load_json(p))
        except (json.JSONDecodeError, OSError) as e:
            print(f"跳过无法解析的 distill: {p} ({e})", file=sys.stderr)
    return distills


# --------------------------------------------------------------------------- 派生

def sort_books(distills):
    """按 pub_year 升序;缺 pub_year 的另列,返回 (timeline_books, missing_slugs)。"""
    timeline = [d for d in distills if isinstance(d.get("pub_year"), int)]
    timeline.sort(key=lambda d: d["pub_year"])
    missing = [d.get("slug", "?") for d in distills if not isinstance(d.get("pub_year"), int)]
    return timeline, missing


def load_author_index(index_path, author_slugs, slug_year):
    """§4.4「走现成跨书 5-tag 索引」:从 knowledge-index.json 取该作者各书已登记概念的**跨书对齐**。
    各书蒸馏 Step4 已把同义概念归并到同一 canonical(SUPPORTS/REFINES/... 挂同一 entry),
    这里直接复用该对齐,避免 concept_graph 靠各书原始概念名(措辞不同)漏并。
    返回 [{concept, concept_en, appearances:[{slug,year,stance,one_liner,anchor}]}](仅含 author 书出现的概念);
    索引缺失/空 -> None(调用方回退原字符串匹配,保合成 fixture 行为不变)。"""
    if not index_path or not Path(index_path).is_file():
        return None
    try:
        idx = load_json(Path(index_path))
    except Exception:
        return None
    concepts = idx.get("concepts") if isinstance(idx, dict) else None
    if not concepts:
        return None
    out = []
    for c in concepts:
        name = c.get("concept")
        if not name:
            continue
        canon_one = c.get("one_liner", "")
        apps = []
        for e in c.get("entries", []) or []:
            s = e.get("book_slug")
            if s in author_slugs and slug_year.get(s) is not None:
                apps.append({"slug": s, "year": slug_year.get(s),
                             "stance": e.get("stance", ""), "one_liner": canon_one,
                             "anchor": e.get("anchor", "")})
        if apps:
            apps.sort(key=lambda a: (a["year"], a["slug"] or ""))
            out.append({"concept": name, "concept_en": c.get("concept_en", ""), "appearances": apps})
    return out or None


def derive_concept_graph(books, manual, index_canon=None):
    """§4.4:nodes(去重概念 + 生命周期 status + appearances)+ edges(persist/drift 自动 + derive 读 manual)。
    index_canon 有值(走跨书索引)-> 按 canonical 对齐建节点(跨书正确合并);
    无(fixture / 无索引)-> 回退各书原始概念名字符串去重。"""
    earliest = books[0]["pub_year"]
    latest = books[-1]["pub_year"]

    if index_canon:
        # concept_en 兜底:从各书 distill 概念名精确匹配补
        en_map = {}
        for d in books:
            for c in d.get("concepts", []):
                nm = c.get("concept")
                if nm and c.get("concept_en"):
                    en_map[norm(nm)] = c["concept_en"]
        nodes = []
        lane_by_year = {}  # first_year -> 该列已排概念数(lane 按列计数,DAG 才不会因全局序号被拉得又高又疏)
        for item in index_canon:
            apps = item["appearances"]
            fy = min(a["year"] for a in apps)
            ly = max(a["year"] for a in apps)
            status = "dropped" if ly != latest else ("persist" if fy == earliest else "new")
            lane = lane_by_year.get(fy, 0)
            lane_by_year[fy] = lane + 1
            nodes.append({
                "id": f"c{len(nodes) + 1}",
                "concept": item["concept"],
                "concept_en": item.get("concept_en") or en_map.get(norm(item["concept"]), ""),
                "first_year": fy,
                "last_year": ly,
                "lane": lane,
                "status": status,
                "appearances": [{"slug": a["slug"], "year": a["year"],
                                 "one_liner": a.get("one_liner", ""), "stance": a.get("stance", "")}
                                for a in apps],
            })
        by_name = {n["concept"]: n for n in nodes}
        edges = []
        for n in nodes:
            apps = n["appearances"]
            for k in range(len(apps) - 1):
                a, b = apps[k], apps[k + 1]
                changed = norm(a["stance"]) != norm(b["stance"]) or norm(a["one_liner"]) != norm(b["one_liner"])
                edges.append({"from": n["id"], "to": n["id"],
                              "type": "drift" if changed else "persist",
                              "label": "立场漂移" if changed else "",
                              "book_pair": [a["slug"], b["slug"]]})
        for de in manual.get("derive_edges", []) or []:
            f, t = by_name.get(de.get("from")), by_name.get(de.get("to"))
            if not f or not t:
                continue
            edges.append({"from": f["id"], "to": t["id"], "type": "derive",
                          "label": de.get("label", ""), "book_pair": None})
        return {"nodes": nodes, "edges": edges}

    order = []           # 概念名首现顺序 -> node id
    node = {}            # concept -> node dict
    for d in books:
        for c in d.get("concepts", []):
            name = c.get("concept")
            if not name:
                continue
            if name not in node:
                order.append(name)
                node[name] = {
                    "id": f"c{len(order)}",
                    "concept": name,
                    "concept_en": c.get("concept_en", ""),
                    "first_year": d["pub_year"],
                    "last_year": d["pub_year"],
                    "lane": len(order) - 1,      # 首现顺序简单分层(§4.4 允许)
                    "status": None,
                    "appearances": [],
                }
            n = node[name]
            n["last_year"] = d["pub_year"]
            n["appearances"].append({
                "slug": d.get("slug"),
                "year": d["pub_year"],
                "one_liner": c.get("one_liner", ""),
                "stance": c.get("stance", ""),
            })

    # 生命周期 status:未进最晚书 = dropped;首现于非最早书 = new;贯穿至今 = persist
    for name in order:
        n = node[name]
        present_in_latest = n["last_year"] == latest
        if not present_in_latest:
            n["status"] = "dropped"
        elif n["first_year"] == earliest:
            n["status"] = "persist"
        else:
            n["status"] = "new"

    nodes = [node[name] for name in order]

    # 边:同概念相邻出现 -> stance/one_liner 变则 drift(立场漂移),否则 persist
    edges = []
    for name in order:
        n = node[name]
        apps = n["appearances"]
        for k in range(len(apps) - 1):
            a, b = apps[k], apps[k + 1]
            changed = norm(a["stance"]) != norm(b["stance"]) or norm(a["one_liner"]) != norm(b["one_liner"])
            edges.append({
                "from": n["id"],
                "to": n["id"],
                "type": "drift" if changed else "persist",
                "label": "立场漂移" if changed else "",
                "book_pair": [a["slug"], b["slug"]],
            })

    # derive 边(§4.4 读 manual.derive_edges;schema 无此编码,由人工提供)
    for de in manual.get("derive_edges", []) or []:
        f, t = node.get(de.get("from")), node.get(de.get("to"))
        if not f or not t:
            continue
        edges.append({
            "from": f["id"],
            "to": t["id"],
            "type": "derive",
            "label": de.get("label", ""),
            "book_pair": None,
        })

    return {"nodes": nodes, "edges": edges}


def derive_motifs(books, manual=None, index_canon=None):
    """§4.2:母题=跨书复现的主题红线。
    优先:manual.motif_groups(人工把跨书对齐概念归成 3-4 条母题)+ index_canon -> 按组算 appears_in;
    回退:core_ideas(+mental_models)跨书 difflib 聚类(措辞相近才并,赫拉利这类措辞各异的书会偏空)。"""
    manual = manual or {}
    groups = manual.get("motif_groups") or []
    if groups and index_canon:
        canon_by_name = {it["concept"]: it for it in index_canon}
        motifs = []
        for g in groups:
            label = g.get("label")
            if not label:
                continue
            appears = {}  # slug -> {year, cnt}
            for cn in g.get("concepts", []) or []:
                it = canon_by_name.get(cn)
                if not it:
                    continue
                for a in it["appearances"]:
                    s = a["slug"]
                    rec = appears.setdefault(s, {"year": a["year"], "cnt": 0})
                    rec["cnt"] += 1
            if len(appears) < 2:
                continue  # 单书不成母题(§4.2)
            ap = []
            for s, v in appears.items():
                primary = v["cnt"] >= 2
                ap.append({"slug": s, "year": v["year"],
                           "prominence": 0.8 if primary else 0.5, "primary": primary})
            ap.sort(key=lambda x: (x["year"], x["slug"] or ""))
            years = [a["year"] for a in ap]
            status = g.get("status") or ("persistent" if all(a["primary"] for a in ap) else "refined")
            motifs.append({"id": f"m{len(motifs) + 1}", "label": label,
                           "statement": g.get("statement", label), "status": status,
                           "span": [min(years), max(years)], "color_idx": len(motifs),
                           "appears_in": ap})
        if motifs:
            return motifs

    # 稳定顺序收集所有 idea 实例
    items = []
    for d in books:
        for ci in d.get("core_ideas", []):
            idea = ci.get("idea")
            if idea:
                items.append({"idea": idea, "slug": d.get("slug"), "year": d["pub_year"],
                              "primary": bool(ci.get("primary"))})
        for mm in d.get("mental_models", []):
            model = mm.get("model")
            if model:
                items.append({"idea": model, "slug": d.get("slug"), "year": d["pub_year"],
                              "primary": bool(mm.get("primary"))})

    clusters = []  # 每个 = {"rep": 首个 idea 文本, "members": [item...]}
    for it in items:
        placed = False
        for cl in clusters:
            if norm(it["idea"]) == norm(cl["rep"]) or sim(it["idea"], cl["rep"]) >= MOTIF_SIM:
                cl["members"].append(it)
                placed = True
                break
        if not placed:
            clusters.append({"rep": it["idea"], "members": [it]})

    motifs = []
    for cl in clusters:
        books_in = sorted({m["slug"] for m in cl["members"]})
        if len(books_in) < 2:
            continue  # singleton 不进
        appears = []
        seen_slug = {}
        for m in sorted(cl["members"], key=lambda x: (x["year"], x["slug"] or "")):
            # 同书同 motif 只取一次(以 primary 优先)
            if m["slug"] in seen_slug:
                if m["primary"] and not seen_slug[m["slug"]]["primary"]:
                    seen_slug[m["slug"]].update({"primary": True, "prominence": 0.8})
                continue
            entry = {"slug": m["slug"], "year": m["year"],
                     "prominence": 0.8 if m["primary"] else 0.5, "primary": m["primary"]}
            appears.append(entry)
            seen_slug[m["slug"]] = entry
        years = [a["year"] for a in appears]
        status = "persistent" if all(a["primary"] for a in appears) else "refined"
        motifs.append({
            "id": None,
            "label": cl["rep"],
            "statement": cl["rep"],
            "status": status,
            "span": [min(years), max(years)],
            "color_idx": None,
            "appears_in": appears,
        })

    # 按首现年排序,分配 id / color_idx
    motifs.sort(key=lambda m: (m["span"][0], m["label"]))
    for i, m in enumerate(motifs):
        m["id"] = f"m{i + 1}"
        m["color_idx"] = i
    return motifs


def derive_periods(books, manual):
    """§4.1:相邻两书按 概念换手 Jaccard>0.6 / core_question 换题 / book_type 变 / 年份断档>N 切边界。命名读 manual。"""
    names = manual.get("period_names", {}) or {}
    themes = manual.get("period_themes", {}) or {}

    def cset(d):
        return {c.get("concept") for c in d.get("concepts", []) if c.get("concept")}

    boundaries = {}  # 索引 i(在 book[i] 前切) -> 触发信号
    for i in range(1, len(books)):
        prev, cur = books[i - 1], books[i]
        signal = None
        cp, cc = cset(prev), cset(cur)
        jd = 1 - jaccard_sim(cp, cc)  # 换手距离
        if jd > JACCARD_BOUNDARY:
            signal = "概念换手>0.6"
        elif jaccard_sim(keyword_chars(prev.get("core_question", "")),
                         keyword_chars(cur.get("core_question", ""))) < QUESTION_SIM_BOUNDARY:
            signal = "question换题"
        elif prev.get("book_type") != cur.get("book_type"):
            signal = "genre变"
        elif cur["pub_year"] - prev["pub_year"] > YEAR_GAP_BOUNDARY:
            signal = "年份断档"
        if signal:
            boundaries[i] = signal

    # 据边界切段
    periods = []
    seg_start = 0
    seg_signal = "起始"
    for i in range(1, len(books) + 1):
        if i == len(books) or i in boundaries:
            seg = books[seg_start:i]
            pid = f"p{len(periods) + 1}"
            years = [b["pub_year"] for b in seg]
            periods.append({
                "id": pid,
                "name": names.get(pid),
                "theme": themes.get(pid),
                "year_range": [min(years), max(years)],
                "books": [b.get("slug") for b in seg],
                "boundary_signal": seg_signal,
                "color_idx": len(periods),
            })
            if i < len(books):
                seg_start = i
                seg_signal = boundaries[i]
    # slug -> period_id
    slug_period = {}
    for p in periods:
        for s in p["books"]:
            slug_period[s] = p["id"]
    return periods, slug_period


def derive_turns(books, manual, enrich):
    """§4.3:相邻年共享概念 stance 语义对立 -> 候选(verdict 从 enrich 同概念 shift 取,无 -> null);合并 enrich.shifts。"""
    te = (enrich.get("thought_evolution") or {})
    shifts = te.get("shifts", []) or []
    notes = manual.get("turns_note", {}) or {}

    # enrich shift 按 concept 索引(供候选查 verdict/external)
    shift_by_concept = {}
    for sh in shifts:
        c = sh.get("concept")
        if c:
            shift_by_concept.setdefault(c, sh)

    raw = []  # (source_priority, year, concept, turn-partial)

    # 1) enrich.shifts 直接并入(高幻觉区的「真」转向,带 verdict/external)
    for sh in shifts:
        fr, to = sh.get("from", {}) or {}, sh.get("to", {}) or {}
        try:
            fy = int(fr.get("year"))
        except (TypeError, ValueError):
            fy = None
        try:
            ty = int(to.get("year"))
        except (TypeError, ValueError):
            ty = None
        raw.append({
            "_src": 0, "_year": ty if ty is not None else (fy or 0), "concept": sh.get("concept"),
            "motif_id": None,
            "from": {"book": fr.get("book"), "year": fy, "stance": fr.get("stance"),
                     "distill_slug": fr.get("distill_slug")},
            "to": {"book": to.get("book"), "year": ty, "stance": to.get("stance"),
                   "distill_slug": to.get("distill_slug")},
            "trigger_field": sh.get("trigger_field", "concepts.stance"),
            "verdict": sh.get("verdict"),
            "external": sh.get("external", []) or [],
        })
    enrich_concepts = {sh.get("concept") for sh in shifts}

    # 2) 确定性候选:相邻书共享概念,stance 语义对立(去重同概念,保留最早一次转变)
    cand_seen = set()
    for i in range(len(books) - 1):
        a, b = books[i], books[i + 1]
        ca = {c.get("concept"): c for c in a.get("concepts", []) if c.get("concept")}
        cb = {c.get("concept"): c for c in b.get("concepts", []) if c.get("concept")}
        for name in ca:
            if name in cb and name not in cand_seen and name not in enrich_concepts:
                sa, sb = ca[name].get("stance", ""), cb[name].get("stance", "")
                differ = norm(sa) != norm(sb)
                opposed = any(m in sa or m in sb for m in OPPOSITION_MARKERS)
                if differ and opposed:
                    cand_seen.add(name)
                    match = shift_by_concept.get(name)
                    raw.append({
                        "_src": 1, "_year": b["pub_year"], "concept": name, "motif_id": None,
                        "from": {"book": a.get("title"), "year": a["pub_year"], "stance": sa,
                                 "distill_slug": a.get("slug")},
                        "to": {"book": b.get("title"), "year": b["pub_year"], "stance": sb,
                               "distill_slug": b.get("slug")},
                        "trigger_field": "concepts.stance",
                        "verdict": (match or {}).get("verdict") if match else None,
                        "external": (match or {}).get("external", []) if match else [],
                    })

    # 排序:同年内 enrich 优先(拿低 id),再按概念名;分配 id + 挂 note
    raw.sort(key=lambda t: (t["_year"], t["_src"], t["concept"] or ""))
    turns = []
    for i, t in enumerate(raw):
        tid = f"t{i + 1}"
        turns.append({
            "id": tid,
            "year": t["_year"],
            "concept": t["concept"],
            "motif_id": t["motif_id"],
            "from": t["from"],
            "to": t["to"],
            "trigger_field": t["trigger_field"],
            "note": notes.get(tid),
            "verdict": t["verdict"],  # None = 无外证(渲染层跳过,不删)
            "external": t["external"],
        })
    return turns


def derive_persistent_tensions(books):
    """§persistent_tensions:tensions (a,b) 跨书规范化匹配,复现 >=2 书。"""
    groups = []  # {"a","b","note","books":set}
    for d in books:
        for t in d.get("tensions", []):
            a, b = t.get("a"), t.get("b")
            if not a or not b:
                continue
            key = frozenset((norm(a), norm(b)))
            found = None
            for g in groups:
                if g["_key"] == key:
                    found = g
                    break
            if found:
                found["books"].add(d.get("slug"))
            else:
                groups.append({"_key": key, "a": a, "b": b, "note": t.get("note", ""),
                               "books": {d.get("slug")}})
    out = []
    for g in groups:
        if len(g["books"]) >= 2:
            out.append({"a": g["a"], "b": g["b"], "note": g["note"],
                        "books": sorted(g["books"])})
    return out


def derive_recurring_critique(books):
    """§recurring_critique:blind_spots 语义/规范化去重复现 >=2 书;era_limits 每条挂其书 pub_year(I5)。"""
    # blind_spots 跨书聚类
    bgroups = []  # {"text","books":set}
    for d in books:
        for bs in (d.get("critique", {}) or {}).get("blind_spots", []) or []:
            found = None
            for g in bgroups:
                if norm(bs) == norm(g["text"]) or sim(bs, g["text"]) >= MOTIF_SIM:
                    found = g
                    break
            if found:
                found["books"].add(d.get("slug"))
            else:
                bgroups.append({"text": bs, "books": {d.get("slug")}})
    blind_spots = [{"text": g["text"], "books": sorted(g["books"])}
                   for g in bgroups if len(g["books"]) >= 2]

    # era_limits:每条挂 pub_year + slug(I5),不去重
    era_limits = []
    for d in books:
        for el in (d.get("critique", {}) or {}).get("era_limits", []) or []:
            era_limits.append({"text": el, "year": d["pub_year"], "slug": d.get("slug")})

    return {"blind_spots": blind_spots, "era_limits": era_limits}


def derive_influences(books, manual):
    """§influences.upstream:cross_domain[].name 频次 >=2 播种;downstream 人工补(留 manual 或空)。"""
    counts = {}
    meta = {}
    for d in books:
        for cd in d.get("cross_domain", []):
            name = cd.get("name")
            if not name:
                continue
            counts[name] = counts.get(name, 0) + 1
            meta.setdefault(name, cd.get("note", ""))
    upstream = [{"name": n, "via": meta.get(n, "")} for n in sorted(counts) if counts[n] >= 2]
    # manual 可补师承 upstream / downstream
    for u in manual.get("influences_upstream", []) or []:
        if not any(x["name"] == u.get("name") for x in upstream):
            upstream.append({"name": u.get("name"), "via": u.get("via", "")})
    downstream = manual.get("influences_downstream", []) or []
    return {"upstream": upstream, "downstream": downstream}


def derive_signature_lines(books):
    """§signature_lines(I6):各书 quotes[].featured===true 汇总去重,带 slug/year,按年排。"""
    out = []
    seen = set()
    for d in books:
        for q in d.get("quotes", []):
            if q.get("featured") is True:
                text = q.get("text", "")
                k = norm(text)
                if k in seen:
                    continue
                seen.add(k)
                out.append({"text": text, "slug": d.get("slug"), "year": d["pub_year"]})
    out.sort(key=lambda x: x["year"])
    return out


def derive_genre_arc(books):
    """§genre_arc:book_type 按 pub_year 序列。"""
    return [{"year": d["pub_year"], "book_type": d.get("book_type"), "slug": d.get("slug")}
            for d in books]


def build_books(books, slug_period, manual):
    roles = manual.get("role_in_evolution", {}) or {}
    return [{
        "slug": d.get("slug"),
        "title": d.get("title"),
        "book_type": d.get("book_type"),
        "pub_year": d["pub_year"],
        "period_id": slug_period.get(d.get("slug")),
        "role_in_evolution": roles.get(d.get("slug")),
    } for d in books]


# --------------------------------------------------------------------------- 组装

def build_author_json(distills, manual, enrich, index_path=None):
    books, missing = sort_books(distills)
    warnings = []
    for slug in missing:
        warnings.append(f"书 {slug} 缺 pub_year,已排除出时间线")

    author_slugs = {b.get("slug") for b in books}
    slug_year = {b.get("slug"): b.get("pub_year") for b in books}
    index_canon = load_author_index(index_path, author_slugs, slug_year)
    if index_path and index_canon is None:
        warnings.append("跨书索引缺失/为空,concept_graph 与 motifs 回退字符串匹配(概念图可能偏空)")

    concept_graph = derive_concept_graph(books, manual, index_canon)
    motifs = derive_motifs(books, manual, index_canon)
    periods, slug_period = derive_periods(books, manual)
    turns = derive_turns(books, manual, enrich)
    persistent_tensions = derive_persistent_tensions(books)
    recurring_critique = derive_recurring_critique(books)
    influences = derive_influences(books, manual)
    signature_lines = derive_signature_lines(books)
    genre_arc = derive_genre_arc(books)
    books_out = build_books(books, slug_period, manual)

    # 缺 manual 认知字段 -> 记 warning(脚本不臆造)
    if not manual.get("period_names"):
        warnings.append("manual 缺 period_names,时期未命名")
    if not manual.get("bio"):
        warnings.append("manual 缺 bio")
    if not manual.get("core_sentence"):
        warnings.append("manual 缺 core_sentence")
    if not manual.get("evolution_summary"):
        warnings.append("manual 缺 evolution_summary")
    if not manual.get("evolution_verdict"):
        warnings.append("manual 缺 evolution_verdict(③板块无结论徽章,建议补 stance+headline)")
    if not (manual.get("bio") or {}).get("background"):
        warnings.append("manual.bio 缺 background(定位卡左栏只有 one_liner 一句话,建议补详实背景段)")

    te = enrich.get("thought_evolution") or {}
    author_name = (books[0].get("author") if books else None) or manual.get("author")

    doc = {
        "author": author_name,
        "slug": manual.get("slug"),
        "aliases": manual.get("aliases", []),
        "bio": manual.get("bio"),
        "core_sentence": manual.get("core_sentence"),
        "books": books_out,
        "periods": periods,
        "motifs": motifs,
        "turns": turns,
        "concept_graph": concept_graph,
        "persistent_tensions": persistent_tensions,
        "recurring_critique": recurring_critique,
        "influences": influences,
        "signature_lines": signature_lines,
        "genre_arc": genre_arc,
        "reading_path": manual.get("reading_path", []),
        "evolution_summary": manual.get("evolution_summary"),
        "evolution_verdict": manual.get("evolution_verdict"),
        "consistency_note": te.get("consistency_note"),
        "_provenance": {
            "generated_from": [b.get("slug") for b in books],
            "pub_years": [b["pub_year"] for b in books],
            "aggregator_version": AGGREGATOR_VERSION,
            "warnings": warnings,
        },
    }
    return doc, warnings


def summarize(doc):
    turns = doc["turns"]
    vc = {}
    for t in turns:
        vc[t["verdict"]] = vc.get(t["verdict"], 0) + 1
    return {
        "books": len(doc["books"]),
        "periods": len(doc["periods"]),
        "motifs": len(doc["motifs"]),
        "turns_total": len(turns),
        "turns_by_verdict": {("null" if k is None else k): v for k, v in vc.items()},
        "concept_nodes": len(doc["concept_graph"]["nodes"]),
        "concept_edges": len(doc["concept_graph"]["edges"]),
        "persistent_tensions": len(doc["persistent_tensions"]),
        "recurring_blind_spots": len(doc["recurring_critique"]["blind_spots"]),
        "era_limits": len(doc["recurring_critique"]["era_limits"]),
        "influences_upstream": len(doc["influences"]["upstream"]),
        "influences_downstream": len(doc["influences"]["downstream"]),
        "signature_lines": len(doc["signature_lines"]),
        "genre_arc": len(doc["genre_arc"]),
        "_warnings": doc["_provenance"]["warnings"],
    }


def main():
    ap = argparse.ArgumentParser(description="多书作者思想演变聚合器(只读 distill.json,确定性)")
    ap.add_argument("--author", help="作者名(配 --data-root 扫描分组)")
    ap.add_argument("--data-root", help="读书蒸馏根目录(扫 */distill.json 按 author 分组)")
    ap.add_argument("--inputs", help="glob 指向若干 distill.json(优先于 --author)")
    ap.add_argument("--index", help="knowledge-index.json 路径(默认取 <data-root>/knowledge-index.json;缺失则回退字符串匹配)")
    ap.add_argument("--manual", help="author.manual.json 路径")
    ap.add_argument("--enrich", help="author.enrich.json 路径")
    ap.add_argument("--out", required=True, help="输出 author.json 路径")
    ap.add_argument("--force", action="store_true", help="防覆盖栏:manual 缺失且 out 已存在时强制重建")
    a = ap.parse_args()

    out_path = Path(a.out)
    manual_path = Path(a.manual) if a.manual else None
    manual_present = bool(manual_path and manual_path.is_file())

    # 防覆盖栏(§3③):out 已存在 且 manual 文件缺失 且 无 --force -> 拒跑
    if out_path.exists() and not manual_present and not a.force:
        print(f"防覆盖:{out_path} 已存在但 manual 文件缺失,拒绝重建(会丢人工/外证);确认请加 --force",
              file=sys.stderr)
        return 2

    # 收集
    distills = collect_distills(a)

    # 触发门槛(§3②):<2 部 -> 不生成
    if len(distills) < 2:
        print(f"触发门槛未达:该作者仅 {len(distills)} 部已蒸(需 >=2),不生成演变页", file=sys.stderr)
        return 3

    manual = load_json(manual_path) if manual_present else {}
    enrich = {}
    if a.enrich and Path(a.enrich).is_file():
        enrich = load_json(Path(a.enrich))

    # 索引路径:显式 --index 优先,否则默认 <data-root>/knowledge-index.json
    index_path = a.index
    if not index_path and a.data_root:
        cand = Path(a.data_root) / "knowledge-index.json"
        if cand.is_file():
            index_path = str(cand)

    doc, _ = build_author_json(distills, manual, enrich, index_path=index_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")

    summary = summarize(doc)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

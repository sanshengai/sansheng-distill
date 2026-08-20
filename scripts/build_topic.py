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
from urllib.parse import unquote, urlsplit

# Windows 管道默认 cp936,打中文 JSON 前必须强制 UTF-8(本仓库跨脚本契约)
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

AGGREGATOR_VERSION = "2"
MIN_MEMBERS = 3  # 触发门槛(topic-craft §0):同主题 <3 本不生成
CERTAINTY_VALUES = ("book_explicit", "cross_book_synthesis", "general_knowledge", "unverified")
EVIDENCE_STATUS_VALUES = (
    "supported", "mixed", "contested", "not_supported", "not_testable", "unverified"
)
QUESTION_TYPE_VALUES = (
    "conceptual", "descriptive", "causal", "predictive", "intervention", "methodological", "normative"
)
SCHOOL_KIND_VALUES = ("theoretical", "methodological", "applied", "mixed")

PUNCT_RE = re.compile(r"[\s　-〿＀-￯,.!?;:\"'`()\[\]{}<>/\\|~@#$%^&*_+=·、,。!?;:「」『』（）【】]")


def norm(s: str) -> str:
    """规范化:去标点空白、小写(concept 名跨源匹配用)。"""
    if not s:
        return ""
    return PUNCT_RE.sub("", str(s)).lower()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def is_http_url(value) -> bool:
    """不联网，但必须能被 URL parser 解出 http(s) scheme + 非空 host。"""
    if not isinstance(value, str):
        return False
    raw = value.strip()
    if not raw or any(ch.isspace() for ch in raw):
        return False
    try:
        parsed = urlsplit(raw)
        host = parsed.hostname
        parsed.port
    except (TypeError, ValueError):
        return False
    return parsed.scheme.lower() in {"http", "https"} and bool(host and host.strip("."))


def normalize_web_url(value):
    """只接受站内根相对深链；非法值 fail-closed。"""
    if not isinstance(value, str):
        return None
    raw = value
    if (not raw or raw != raw.strip() or not raw.startswith("/") or raw.startswith("//") or "\\" in raw
            or any(ch.isspace() or ord(ch) < 32 for ch in raw)):
        return None
    path_only = raw.split("?", 1)[0].split("#", 1)[0]
    for _ in range(3):
        decoded = unquote(path_only)
        if decoded == path_only:
            break
        path_only = decoded
    if (path_only.startswith("//") or "\\" in path_only
            or any(ch.isspace() or ord(ch) < 32 for ch in path_only)
            or any(part in {".", ".."} for part in path_only.split("/"))):
        return None
    return raw


# --------------------------------------------------------------------------- 收集

def collect_members(manual, data_root, warnings):
    """按 manual.members 逐个加载 distill.json；显式成员异常一律 fail-closed。"""
    members = manual.get("members") or []
    if not isinstance(members, list):
        raise ValueError("manual.members 必须是 slug 列表")
    out = []
    seen = set()
    for slug in members:
        if (not isinstance(slug, str) or not slug or slug.strip() != slug
                or slug in {".", ".."} or "/" in slug or "\\" in slug
                or any(ch.isspace() or ord(ch) < 32 for ch in slug)):
            raise ValueError(f"manual.members 含非法 slug: {slug!r}")
        if slug in seen:
            continue
        seen.add(slug)
        p = Path(data_root) / slug / "distill.json"
        if not p.is_file():
            raise ValueError(f"成员 {slug} 的 distill.json 缺失({p})")
        try:
            distill = load_json(p)
        except (json.JSONDecodeError, OSError) as e:
            raise ValueError(f"成员 {slug} 的 distill.json 解析失败({e})") from e
        if distill.get("slug") != slug:
            raise ValueError(
                f"成员路径 {slug} 内 distill.slug={distill.get('slug')!r} 不一致"
            )
        out.append((slug, distill))
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

def validate_school_contract(manual, member_set):
    """在派生 books.school_ids 前拒绝重复 school id 与 book_meta 孤儿引用。

    通过报错停止生成，避免“先从原始 schools 反推，再在 resolve_schools
    里丢掉无效 school”导致 topic.json 出现无对应 school 的孤儿 ID。
    """
    errors = []
    schools = manual.get("schools", []) or []
    if not isinstance(schools, list):
        return ["manual.schools 必须是数组"]
    ids = set()
    explicit_members = {}
    anchors = {}
    for index, school in enumerate(schools):
        if not isinstance(school, dict):
            errors.append(f"manual.schools[{index}] 必须是对象")
            continue
        sid = school.get("id") or f"s{index + 1}"
        if not isinstance(sid, str) or not sid.strip():
            errors.append(f"manual.schools[{index}].id 必须是非空字符串")
            continue
        if sid in ids:
            errors.append(f"manual.schools 的 id {sid!r} 重复")
        ids.add(sid)
        if not isinstance(school.get("name"), str) or not school["name"].strip():
            errors.append(f"manual.school {sid!r} 缺非空 name(否则解析时会产生孤儿 school_id)")
        members = school.get("members") or []
        if not isinstance(members, list):
            errors.append(f"manual.school {sid!r}.members 必须是数组")
            members = []
        valid_members = []
        seen_members = set()
        for slug in members:
            if not isinstance(slug, str) or not slug:
                errors.append(f"manual.school {sid!r}.members 只能含非空字符串")
                continue
            if slug in seen_members:
                errors.append(f"manual.school {sid!r}.members 含重复成员 {slug!r}")
            seen_members.add(slug)
            if slug not in member_set:
                errors.append(f"manual.school {sid!r}.members 引用非成员 slug {slug!r}")
            else:
                valid_members.append(slug)
        explicit_members.setdefault(sid, set()).update(valid_members)
        anchor = school.get("anchor_book")
        if anchor is not None and (not isinstance(anchor, str) or not anchor):
            errors.append(f"manual.school {sid!r}.anchor_book 必须是非空字符串或省略")
        elif anchor is not None:
            anchors[sid] = anchor
            if anchor not in member_set:
                errors.append(f"manual.school {sid!r}.anchor_book 引用非成员 slug {anchor!r}")

    book_meta = manual.get("book_meta") or {}
    if not isinstance(book_meta, dict):
        errors.append("manual.book_meta 必须是对象")
        return errors
    meta_members = {}
    for slug, meta in book_meta.items():
        if not isinstance(meta, dict):
            errors.append(f"manual.book_meta[{slug!r}] 必须是对象")
            continue
        if slug not in member_set:
            continue  # 非成员 meta 不进产物，仍交给既有 warning/人工清理流程。
        refs = meta.get("school_ids")
        if refs is None and meta.get("school_id") is not None:
            refs = [meta.get("school_id")]
        if refs is None:
            continue
        if not isinstance(refs, list) or any(not isinstance(x, str) or not x for x in refs):
            errors.append(f"manual.book_meta[{slug!r}].school_ids 必须是非空字符串数组")
            continue
        if len(refs) != len(set(refs)):
            errors.append(f"manual.book_meta[{slug!r}].school_ids 含重复引用")
        for sid in refs:
            if sid not in ids:
                errors.append(f"manual.book_meta[{slug!r}].school_ids 引用不存在的 school {sid!r}")
            else:
                meta_members.setdefault(sid, set()).add(slug)
    for sid, anchor in anchors.items():
        resolved_members = explicit_members.get(sid, set()) | meta_members.get(sid, set())
        if anchor in member_set and anchor not in resolved_members:
            errors.append(f"manual.school {sid!r}.anchor_book {anchor!r} 未包含在该 school.members/book_meta 引用中")
    return errors


def derive_books(members, manual, schools=None, warnings=None):
    """🤖 直取 distill 元数据 + 合并 manual.book_meta(one_liner/role_in_topic)
    + 从**已解析** schools 反推 school_ids(按 schools 顺序有序去重)。
    ``schools=None`` 只保留给纯函数旧调用；正式 build 必须传 resolve_schools 产物。"""
    book_meta = manual.get("book_meta") or {}
    warnings = warnings if warnings is not None else []
    # slug -> school_ids(同一本书可属于多个研究传统/分析镜头)
    school_of = {}
    source_schools = (manual.get("schools", []) or []) if schools is None else schools
    for i, sc in enumerate(source_schools):
        school_id = sc.get("id") or f"s{i + 1}"
        for s in sc.get("members", []) or []:
            ids = school_of.setdefault(s, [])
            if school_id not in ids:
                ids.append(school_id)
    out = []
    for slug, d in members:
        meta = book_meta.get(slug, {}) or {}
        one_liner = meta.get("one_liner")
        if not one_liner:  # 回退 distill 的餐巾纸/核心问句
            napkin = d.get("napkin") or {}
            one_liner = napkin.get("one_liner") or d.get("core_question") or ""
        row = {
            "slug": slug,
            "title": d.get("title"),
            "book_type": d.get("book_type"),
            "pub_year": d.get("pub_year"),
            "stakes": d.get("stakes", "normal"),
            "school_ids": school_of.get(slug, []),
            "one_liner": one_liner,
            "role_in_topic": meta.get("role_in_topic"),
        }
        raw_url = meta.get("web_url")
        web_url = normalize_web_url(raw_url)
        if web_url:
            row["web_url"] = web_url
        elif raw_url is not None:
            warnings.append(f"book_meta.{slug}.web_url 非法,已剔除")
        out.append(row)
    return out


def resolve_schools(manual, member_set, title_of, warnings):
    """✍️ 分类纯 manual;校验 members⊆成员、补 color_idx、解析 anchor_book title。

    kind/evidence_status 使用 topic-craft 的锁定枚举；book_meta.school_ids
    (及旧 school_id) 与 schools[].members 做并集，保证双向回指一致。
    """
    meta_members = {}
    for slug, meta in (manual.get("book_meta") or {}).items():
        if slug not in member_set or not isinstance(meta, dict):
            continue
        refs = meta.get("school_ids")
        if refs is None and meta.get("school_id") is not None:
            refs = [meta.get("school_id")]
        for sid in refs or []:
            meta_members.setdefault(sid, []).append(slug)
    out = []
    for i, sc in enumerate(manual.get("schools", []) or []):
        name = sc.get("name")
        if not name:
            warnings.append(f"school[{i}] 缺 name,已跳过")
            continue
        sid = sc.get("id") or f"s{i + 1}"
        mem = []
        for slug in list(sc.get("members") or []) + meta_members.get(sid, []):
            if slug in member_set and slug not in mem:
                mem.append(slug)
        bad = [s for s in (sc.get("members") or []) if s not in member_set]
        for s in bad:
            warnings.append(f"school「{name}」的成员 {s} 不在 members 集,已剔除")
        anchor = sc.get("anchor_book")
        if anchor and anchor not in member_set:
            warnings.append(f"school「{name}」anchor_book {anchor} 不在 members 集")
            anchor = None
        kind = sc.get("kind")
        if kind is not None and kind not in SCHOOL_KIND_VALUES:
            warnings.append(f"school「{name}」kind「{kind}」∉ {SCHOOL_KIND_VALUES},已置空")
            kind = None
        evidence_status = sc.get("evidence_status")
        if evidence_status is not None and evidence_status not in EVIDENCE_STATUS_VALUES:
            warnings.append(
                f"school「{name}」evidence_status「{evidence_status}」∉ "
                f"{EVIDENCE_STATUS_VALUES},已置空"
            )
            evidence_status = None
        out.append({
            "id": sid,
            "name": name,
            "kind": kind,
            "evidence_status": evidence_status,
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


def _normalize_adjudication(value, label, warnings):
    """外部研究裁决归一化为四字段对象。

    旧字符串按兼容契约视为未核定的书内观点；对象中任一必需字段缺失/非法时，
    使用明确的「尚未核定」降级文案并记 warning，不臆造科学结论。
    """
    if value is None:
        return None
    if isinstance(value, str):
        if value.strip():
            return {
                "status": "unverified",
                "book_view": value.strip(),
                "research_view": "尚无外部证据裁决",
                "boundary_conditions": "尚未核定",
            }
        warnings.append(f"dispute「{label}」adjudication 为空字符串,已置空")
        return None
    if not isinstance(value, dict):
        warnings.append(f"dispute「{label}」adjudication 必须是对象或字符串,已置空")
        return None
    status = value.get("status")
    if status not in EVIDENCE_STATUS_VALUES:
        warnings.append(
            f"dispute「{label}」adjudication.status「{status}」∉ "
            f"{EVIDENCE_STATUS_VALUES},改 unverified"
        )
        status = "unverified"
    defaults = {
        "book_view": "见上方书间立场",
        "research_view": "尚无外部证据裁决",
        "boundary_conditions": "尚未核定",
    }
    out = {"status": status}
    for key, fallback in defaults.items():
        item = value.get(key)
        if not isinstance(item, str) or not item.strip():
            warnings.append(f"dispute「{label}」adjudication.{key} 必须是非空字符串,已降级")
            out[key] = fallback
        else:
            out[key] = item.strip()
    return out


def _normalize_sources(value, label, warnings):
    """外部证据来源归一化为 URL 字符串或含 url 的对象；非 http(s) 项不进入产物。"""
    if value is None:
        return []
    if not isinstance(value, list):
        warnings.append(f"dispute「{label}」sources 必须是数组,已置空")
        return []
    out = []
    for i, source in enumerate(value):
        if isinstance(source, str):
            if is_http_url(source):
                out.append(source.strip())
            else:
                warnings.append(f"dispute「{label}」sources[{i}] 不是合法 http(s) URL,已剔除")
            continue
        if isinstance(source, dict):
            url = source.get("url")
            if is_http_url(url):
                item = dict(source)
                item["url"] = url.strip()
                out.append(item)
            else:
                warnings.append(f"dispute「{label}」sources[{i}].url 不是合法 http(s) URL,已剔除")
            continue
        warnings.append(f"dispute「{label}」sources[{i}] 类型非法,已剔除")
    return out


def resolve_disputes(manual, index_concepts, member_set, warnings):
    """🔶 每条 dispute:从 index 摊各 slug 立场 + 判 index_relation(§4.3)。parallel 剔除。

    positions/index_relation 只描述「书间立场」；question_type/adjudication/sources 独立承载
    「外部研究怎么判」。两层不相互冒充。
    """
    out = []
    for i, d in enumerate(manual.get("disputes", []) or []):
        if d.get("parallel") is True:
            continue  # 显式平行对照由 resolve_parallel_comparisons 单独承载
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

        question_type = d.get("question_type")
        if question_type is not None and question_type not in QUESTION_TYPE_VALUES:
            warnings.append(
                f"dispute「{q}」question_type「{question_type}」∉ {QUESTION_TYPE_VALUES},已置空"
            )
            question_type = None
        adjudication = _normalize_adjudication(d.get("adjudication"), q, warnings)
        sources = _normalize_sources(d.get("sources"), q, warnings)
        if adjudication and not sources:
            warnings.append(f"dispute「{q}」有 adjudication 但无合法 sources,外部研究结论待补出处")

        out.append({
            "id": did, "question": q, "axis": d.get("axis", ""),
            "concept": concept, "index_relation": rel,
            "question_type": question_type,
            "positions": positions, "note": d.get("note"),
            "adjudication": adjudication,
            "sources": sources,
        })
    return out


def resolve_parallel_comparisons(manual, index_concepts, member_set, warnings):
    """解析显式平行对照；复用立场/外证归一化，但绝不进入 disputes。

    可从 parallel_comparisons[] 声明，也可把旧 disputes[] 项标记 parallel:true 后迁移。
    每项至少须有两个非空立场列，否则 fail-closed 跳过。
    """
    specs = list(manual.get("parallel_comparisons", []) or [])
    specs.extend(d for d in (manual.get("disputes", []) or []) if d.get("parallel") is True)
    out = []
    seen_ids = set()
    for i, spec in enumerate(specs):
        clone = dict(spec)
        clone.pop("parallel", None)
        clone["curated"] = True
        clone["id"] = clone.get("id") or f"p{i + 1}"
        if clone["id"] in seen_ids:
            warnings.append(f"parallel_comparison id「{clone['id']}」重复,已跳过后项")
            continue
        seen_ids.add(clone["id"])
        resolved = resolve_disputes(
            {"disputes": [clone]}, index_concepts, member_set, warnings
        )
        if not resolved:
            continue
        item = resolved[0]
        populated = sum(
            1 for pos in item.get("positions", [])
            if any(book.get("stance") for book in (pos.get("books") or []))
        )
        if populated < 2:
            warnings.append(
                f"parallel_comparison「{item.get('question')}」有效立场不足 2 列,已跳过"
            )
            continue
        item["index_relation"] = "parallel"
        out.append(item)
    return out


def _anchor_matches(slug, anchor, members_by_slug):
    """锚点是否在该书 decision_rules/core_ideas 中精确出现（忽略标点/空白）。"""
    if not anchor:
        return False
    d = members_by_slug.get(slug)
    if not d:
        return False
    items = list(d.get("decision_rules", []) or []) + list(d.get("core_ideas", []) or [])
    return any(it.get("anchor") and norm(it["anchor"]) == norm(anchor) for it in items)


def resolve_dimensions(manual, member_set, members_by_slug, warnings):
    """✍️🔶 维度对照表:name/value 纯 manual;校验 slug∈成员 + certainty + 原书锚点。

    certainty 必须由 manual 显式声明；缺失时不再从全书或同锚点项推断，直接 unverified。
    """
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
                cert = "unverified"
                warnings.append(f"维度「{name}」的 {slug} 缺 certainty,改 unverified")
            elif cert not in CERTAINTY_VALUES:
                warnings.append(f"维度「{name}」的 {slug} certainty「{cert}」非法,改 unverified")
                cert = "unverified"
            elif cert != "unverified" and not _anchor_matches(slug, cell.get("anchor"), members_by_slug):
                warnings.append(
                    f"维度「{name}」的 {slug} anchor「{cell.get('anchor', '')}」无法回指原书,改 unverified"
                )
                cert = "unverified"
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
    school_errors = validate_school_contract(manual, member_set)
    if school_errors:
        raise ValueError("; ".join(school_errors))
    title_of = {slug: data.get("title") for slug, data in members}
    schools = resolve_schools(manual, member_set, title_of, warnings)
    books = derive_books(members, manual, schools=schools, warnings=warnings)
    disputes = resolve_disputes(manual, index_concepts, member_set, warnings)
    parallel_declared = ("parallel_comparisons" in manual or any(
        d.get("parallel") is True for d in (manual.get("disputes", []) or [])
    ))
    parallel_comparisons = (
        resolve_parallel_comparisons(manual, index_concepts, member_set, warnings)
        if parallel_declared else []
    )
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
    if parallel_declared:
        doc["parallel_comparisons"] = parallel_comparisons
        doc["_provenance"]["parallel_comparison_count"] = len(parallel_comparisons)
    return doc, warnings


def summarize(doc):
    disp = doc["disputes"]
    rc = {}
    for d in disp:
        rc[d["index_relation"]] = rc.get(d["index_relation"], 0) + 1
    summary = {
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
    if "parallel_comparisons" in doc:
        summary["parallel_comparisons"] = len(doc["parallel_comparisons"])
    return summary


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
    try:
        members = collect_members(manual, a.data_root, warnings0)
    except ValueError as exc:
        print(f"manual schema 错误:{exc}", file=sys.stderr)
        return 2

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

    try:
        doc, _ = build_topic_json(members, manual, enrich, index_concepts)
    except ValueError as exc:
        print(f"manual schema 错误:{exc}", file=sys.stderr)
        return 2
    # collect_members 的 warning 并入 provenance
    doc["_provenance"]["warnings"] = warnings0 + doc["_provenance"]["warnings"]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")

    print(json.dumps(summarize(doc), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

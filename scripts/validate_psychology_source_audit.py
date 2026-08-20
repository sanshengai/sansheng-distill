#!/usr/bin/env python3
"""心理学蒸馏原文审计闸（psychology-source-audit-v1）。

验证器分成两层：``validate_source_audit_data`` 只吃内存对象，便于单测；
``validate_source_audit_file`` 负责把同书目录中的四份输入安全装载并核 SHA-256。
任何结构异常都返回违规列表，不把异常当作通过。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "psychology-source-audit-v1"
CLAIM_MAP_SCHEMA_VERSION = "psychology-claim-coverage-v1"
INPUT_ROLES = ("source", "distill", "claim_map", "enrich")
SEGMENT_KINDS = frozenset({
    "acknowledgments", "appendix", "backmatter", "chapter", "conclusion",
    "epilogue", "front_matter", "frontmatter", "index", "notes", "part",
    "preface", "references",
})
TARGET_KINDS = frozenset({"claim", "chapter_narrative", "quote", "excerpt", "audit_flag"})
FACETS = frozenset({"claim", "mechanism", "case", "experiment", "number", "boundary", "verbatim"})
SUPPORT_VALUES = frozenset({"direct", "partial", "contradicted"})
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
LINE_RANGE_RE = re.compile(r"^L(\d{6})-L(\d{6})$")
ANCHOR_CHAPTER_RE = re.compile(r"第\s*(\d+)\s*章")


def _error(message: str) -> str:
    return f"[source-audit] {message}"


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _compact(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def _heading_key(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).lower()
    normalized = normalized.replace("\u00ad", "").replace("’", "'").replace("‘", "'")
    normalized = normalized.replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", "", normalized)


def _chapter_marker(line: str, chapter_no: int) -> bool:
    value = _heading_key(line)
    return value in {str(chapter_no), f"chapter{chapter_no}", f"第{chapter_no}章"}


def _heading_occurs_near_start(
    source_lines: list[str], start: int, end: int, heading: str,
    chapter_no: int | None,
) -> bool:
    window = list(source_lines[start - 1:min(end, start + 63)])
    if chapter_no is not None:
        window = [line for line in window if not _chapter_marker(line, chapter_no)]
    return _heading_key(heading) in _heading_key("\n".join(window))


def _parse_line_range(value: Any, label: str, errors: list[str]) -> tuple[int, int] | None:
    if not isinstance(value, str):
        errors.append(_error(f"{label} 必须是 L000001-L000002 格式字符串"))
        return None
    match = LINE_RANGE_RE.fullmatch(value.strip())
    if not match:
        errors.append(_error(f"{label}={value!r} 非 L000001-L000002 格式"))
        return None
    start, end = (int(match.group(1)), int(match.group(2)))
    if start < 1 or end < start:
        errors.append(_error(f"{label}={value!r} 倒置或越过第 1 行"))
        return None
    return start, end


def _anchor_chapter(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    match = ANCHOR_CHAPTER_RE.search(value)
    return int(match.group(1)) if match else None


def _chapter_id(chapter_no: int) -> str:
    return f"ch{chapter_no:02d}"


def _quote_id(index: int) -> str:
    return f"q{index:02d}"


def _excerpt_id(chapter_no: int, index: int) -> str:
    return f"{_chapter_id(chapter_no)}:e{index:02d}"


def _is_book_relative_file(value: Any) -> bool:
    """只接受同书目录下的单个相对文件名，不接受目录、绝对路径或 ``..``。"""
    if not _nonempty(value):
        return False
    raw = value.strip()
    path = Path(raw)
    return not path.is_absolute() and len(path.parts) == 1 and path.name not in {".", ".."}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _claim_text(section: str, item: Mapping[str, Any]) -> str:
    if section == "core_ideas":
        fields = ("idea", "claim", "title", "explain")
    else:
        fields = ("when", "do", "because", "claim", "title")
    return " ".join(str(item.get(field) or "").strip() for field in fields if _nonempty(item.get(field)))


def _extract_final_claims(distill: Any, errors: list[str]) -> dict[str, dict[str, Any]]:
    claims: dict[str, dict[str, Any]] = {}
    if not isinstance(distill, dict):
        errors.append(_error("distill 输入顶层非对象"))
        return claims
    for section in ("core_ideas", "decision_rules"):
        items = distill.get(section)
        if not isinstance(items, list):
            errors.append(_error(f"distill.{section} 必须是数组"))
            continue
        for index, item in enumerate(items):
            label = f"distill.{section}[{index}]"
            if not isinstance(item, dict):
                errors.append(_error(f"{label} 非对象"))
                continue
            claim_id = item.get("claim_id")
            if not _nonempty(claim_id):
                errors.append(_error(f"{label}.claim_id 缺失或为空"))
                continue
            claim_id = claim_id.strip()
            if claim_id in claims:
                errors.append(_error(f"最终 claim_id={claim_id!r} 重复"))
                continue
            claims[claim_id] = {
                "section": section,
                "item": item,
                "text": _claim_text(section, item),
                "anchor_chapter": _anchor_chapter(item.get("anchor")),
            }
    return claims


def _extract_chapters(distill: Any, errors: list[str]) -> dict[int, dict[str, Any]]:
    chapters: dict[int, dict[str, Any]] = {}
    if not isinstance(distill, dict):
        return chapters
    items = distill.get("chapters")
    if not isinstance(items, list) or not items:
        errors.append(_error("distill.chapters 必须是非空数组"))
        return chapters
    for index, item in enumerate(items):
        label = f"distill.chapters[{index}]"
        if not isinstance(item, dict):
            errors.append(_error(f"{label} 非对象"))
            continue
        chapter_no = item.get("no")
        if not _positive_int(chapter_no):
            errors.append(_error(f"{label}.no 必须是正整数"))
            continue
        if chapter_no in chapters:
            errors.append(_error(f"distill 章号 {chapter_no} 重复"))
            continue
        chapters[chapter_no] = item
    return chapters


def _validate_inputs(audit: dict[str, Any], actual_hashes: Mapping[str, str],
                     source_text: str, errors: list[str]) -> None:
    inputs = audit.get("inputs")
    if not isinstance(inputs, dict):
        errors.append(_error("inputs 必须是对象，且含 source/distill/claim_map/enrich"))
        return
    missing = sorted(set(INPUT_ROLES) - set(inputs))
    extra = sorted(set(inputs) - set(INPUT_ROLES))
    if missing or extra:
        errors.append(_error(f"inputs 键必须精确为 {list(INPUT_ROLES)}；缺 {missing}，多 {extra}"))
    for role in INPUT_ROLES:
        descriptor = inputs.get(role)
        label = f"inputs.{role}"
        if not isinstance(descriptor, dict):
            errors.append(_error(f"{label} 必须是对象"))
            continue
        if not _is_book_relative_file(descriptor.get("path")):
            errors.append(_error(f"{label}.path 只允许同书目录的单个相对文件名"))
        declared = descriptor.get("sha256")
        if not isinstance(declared, str) or not SHA256_RE.fullmatch(declared):
            errors.append(_error(f"{label}.sha256 必须是 64 位小写十六进制"))
        elif actual_hashes.get(role) != declared:
            errors.append(_error(
                f"{label}.sha256 漂移：审计={declared}，当前={actual_hashes.get(role) or '无法读取'}"
            ))
    source_descriptor = inputs.get("source") if isinstance(inputs.get("source"), dict) else {}
    line_count = source_descriptor.get("line_count")
    actual_line_count = len(source_text.splitlines())
    if not isinstance(line_count, int) or isinstance(line_count, bool) or line_count < 1:
        errors.append(_error("inputs.source.line_count 必须是正整数"))
    elif line_count != actual_line_count:
        errors.append(_error(
            f"inputs.source.line_count 漂移：审计={line_count}，当前={actual_line_count}"
        ))


def _validate_segments(audit: dict[str, Any], source_text: str,
                       chapters: Mapping[int, dict[str, Any]], errors: list[str]) \
        -> tuple[dict[str, dict[str, Any]], dict[int, dict[str, Any]]]:
    source_lines = source_text.splitlines()
    raw_segments = audit.get("segments")
    if not isinstance(raw_segments, list) or not raw_segments:
        errors.append(_error("segments 必须是非空数组"))
        return {}, {}
    by_id: dict[str, dict[str, Any]] = {}
    by_chapter: dict[int, dict[str, Any]] = {}
    previous_end = 0
    for index, raw in enumerate(raw_segments):
        label = f"segments[{index}]"
        if not isinstance(raw, dict):
            errors.append(_error(f"{label} 非对象"))
            continue
        segment_id = raw.get("id")
        if not _nonempty(segment_id):
            errors.append(_error(f"{label}.id 缺失或为空"))
            segment_id = f"<invalid-{index}>"
        else:
            segment_id = segment_id.strip()
        if segment_id in by_id:
            errors.append(_error(f"segment id={segment_id!r} 重复"))
        raw_kind = raw.get("kind")
        kind = raw_kind if isinstance(raw_kind, str) else "<invalid-kind>"
        chapter_no = raw.get("chapter_no")
        if kind not in SEGMENT_KINDS:
            errors.append(_error(f"{label}.kind={raw_kind!r} 非法，应为 {sorted(SEGMENT_KINDS)}"))
        parsed_range = _parse_line_range(raw.get("line_range"), f"{label}.line_range", errors)
        if parsed_range:
            start, end = parsed_range
            if start != previous_end + 1:
                errors.append(_error(
                    f"{label}.line_range 不连续：应从 L{previous_end + 1:06d} 开始，实际 L{start:06d}"
                ))
            previous_end = end
            if end > len(source_lines):
                errors.append(_error(f"{label}.line_range 终点 {end} 超出 source {len(source_lines)} 行"))
            heading = raw.get("heading_excerpt")
            if not _nonempty(heading):
                errors.append(_error(f"{label}.heading_excerpt 缺失或为空"))
            elif start <= len(source_lines) and not _heading_occurs_near_start(
                source_lines,
                start,
                min(end, len(source_lines)),
                heading,
                chapter_no if kind == "chapter" and _positive_int(chapter_no) else None,
            ):
                errors.append(_error(
                    f"{label}.heading_excerpt 未在分段起始 64 行内规范化命中"
                ))
        if kind == "chapter":
            if not _positive_int(chapter_no):
                errors.append(_error(f"{label}.chapter_no 必须是正整数"))
            else:
                expected_id = _chapter_id(chapter_no)
                if segment_id != expected_id:
                    errors.append(_error(f"{label}.id 应为稳定章 ID {expected_id!r}"))
                if chapter_no in by_chapter:
                    errors.append(_error(f"chapter_no={chapter_no} 有重复 segment"))
                by_chapter[chapter_no] = raw | {"_range": parsed_range}
        elif chapter_no is not None:
            errors.append(_error(f"{label} 非 chapter segment 不得声明 chapter_no"))
        by_id[segment_id] = raw | {"_range": parsed_range}
    if previous_end != len(source_lines):
        errors.append(_error(
            f"segments 未连续覆盖 source 全部行：最后到 L{previous_end:06d}，source 共 {len(source_lines)} 行"
        ))
    expected_chapters = set(chapters)
    actual_chapters = set(by_chapter)
    if expected_chapters != actual_chapters:
        errors.append(_error(
            f"chapter segments 与 distill.chapters 不精确一致；缺 {sorted(expected_chapters - actual_chapters)}，"
            f"多 {sorted(actual_chapters - expected_chapters)}"
        ))
    return by_id, by_chapter


def _extract_claim_map(claim_map: Any, audit_slug: Any, final_claim_ids: set[str],
                       errors: list[str]) -> dict[str, dict[str, Any]]:
    flags: dict[str, dict[str, Any]] = {}
    if not isinstance(claim_map, dict):
        errors.append(_error("claim_map 输入顶层非对象"))
        return flags
    if claim_map.get("schema_version") != CLAIM_MAP_SCHEMA_VERSION:
        errors.append(_error(
            f"claim_map.schema_version 必须是 {CLAIM_MAP_SCHEMA_VERSION!r}"
        ))
    if _nonempty(audit_slug) and claim_map.get("book_slug") != audit_slug:
        errors.append(_error("claim_map.book_slug 与 source-audit.book_slug 不一致"))
    entries = claim_map.get("entries")
    if not isinstance(entries, list):
        errors.append(_error("claim_map.entries 必须是数组"))
        return flags
    for index, entry in enumerate(entries):
        label = f"claim_map.entries[{index}]"
        if not isinstance(entry, dict):
            errors.append(_error(f"{label} 非对象"))
            continue
        group = entry.get("source_group")
        source_claim_id = entry.get("source_claim_id")
        if not _nonempty(group) or not _nonempty(source_claim_id):
            errors.append(_error(f"{label} 缺非空 source_group/source_claim_id"))
            continue
        target_id = f"{group.strip()}:{source_claim_id.strip()}"
        if target_id in flags:
            errors.append(_error(f"claim_map audit flag={target_id!r} 重复"))
            continue
        _parse_line_range(entry.get("line_range"), f"{label}.line_range", errors)
        disposition = entry.get("disposition")
        final_claim_id = entry.get("final_claim_id")
        if disposition == "mapped":
            if final_claim_id not in final_claim_ids:
                errors.append(_error(f"{label} mapped 到不存在的 final_claim_id={final_claim_id!r}"))
        elif disposition == "excluded":
            if final_claim_id is not None:
                errors.append(_error(f"{label} excluded 时 final_claim_id 必须为 null"))
        else:
            errors.append(_error(f"{label}.disposition={disposition!r} 非 mapped|excluded"))
        flags[target_id] = entry
    return flags


def _expected_verbatim_targets(chapters: Mapping[int, dict[str, Any]], distill: Any,
                               errors: list[str]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    quote_targets: dict[str, dict[str, Any]] = {}
    excerpt_targets: dict[str, dict[str, Any]] = {}
    quotes = distill.get("quotes") if isinstance(distill, dict) else None
    if not isinstance(quotes, list):
        errors.append(_error("distill.quotes 必须是数组"))
        quotes = []
    for index, item in enumerate(quotes, 1):
        if not isinstance(item, dict) or not _nonempty(item.get("text")):
            errors.append(_error(f"distill.quotes[{index - 1}] 非对象或 text 为空"))
            continue
        quote_targets[_quote_id(index)] = item
    for chapter_no, chapter in chapters.items():
        excerpts = chapter.get("excerpts")
        if not isinstance(excerpts, list):
            errors.append(_error(f"distill 第{chapter_no}章 excerpts 必须是数组"))
            continue
        for index, item in enumerate(excerpts, 1):
            if not isinstance(item, dict) or not _nonempty(item.get("text")):
                errors.append(_error(f"distill 第{chapter_no}章 excerpts[{index - 1}] 非对象或 text 为空"))
                continue
            excerpt_targets[_excerpt_id(chapter_no, index)] = item | {"_chapter_no": chapter_no}
    return quote_targets, excerpt_targets


def _target_assertion_text(kind: str, target_id: str, *, claims, chapters, quote_targets,
                           excerpt_targets, audit_flags) -> str:
    if kind == "claim":
        return str((claims.get(target_id) or {}).get("text") or "")
    if kind == "chapter_narrative":
        match = re.fullmatch(r"ch(\d+)", target_id)
        chapter = chapters.get(int(match.group(1))) if match else None
        return str((chapter or {}).get("narrative") or "")
    if kind == "quote":
        return str((quote_targets.get(target_id) or {}).get("text") or "")
    if kind == "excerpt":
        return str((excerpt_targets.get(target_id) or {}).get("text") or "")
    if kind == "audit_flag":
        return str((audit_flags.get(target_id) or {}).get("reason") or "")
    return ""


def _record_target_exists(kind: str, target_id: str, *, claims, narrative_ids,
                          quote_targets, excerpt_targets, audit_flags) -> bool:
    tables = {
        "claim": claims,
        "chapter_narrative": narrative_ids,
        "quote": quote_targets,
        "excerpt": excerpt_targets,
        "audit_flag": audit_flags,
    }
    return target_id in tables.get(kind, {})


def validate_source_audit_data(
    audit: Any,
    *,
    source_text: str,
    distill: Any,
    claim_map: Any,
    enrich: Any,
    actual_hashes: Mapping[str, str],
) -> list[str]:
    """纯数据验证入口；不读文件、不联网，返回全部可确定的违规。"""
    errors: list[str] = []
    if not isinstance(audit, dict):
        return [_error("source-audit.json 顶层必须是对象")]
    if audit.get("schema_version") != SCHEMA_VERSION:
        errors.append(_error(f"schema_version 必须是 {SCHEMA_VERSION!r}"))
    audit_slug = audit.get("book_slug")
    if not _nonempty(audit_slug):
        errors.append(_error("book_slug 缺失或为空"))
    if isinstance(distill, dict):
        if distill.get("slug") != audit_slug:
            errors.append(_error("book_slug 与 distill.slug 不一致"))
        profile = distill.get("domain_profile")
        if not isinstance(profile, dict) or profile.get("domain") != "psychology":
            errors.append(_error("distill 必须声明 domain_profile.domain='psychology'"))
    _validate_inputs(audit, actual_hashes, source_text, errors)

    chapters = _extract_chapters(distill, errors)
    claims = _extract_final_claims(distill, errors)
    segment_by_id, segment_by_chapter = _validate_segments(audit, source_text, chapters, errors)
    audit_flags = _extract_claim_map(claim_map, audit_slug, set(claims), errors)
    quote_targets, excerpt_targets = _expected_verbatim_targets(chapters, distill, errors)

    evidence_claims = None
    if isinstance(enrich, dict) and isinstance(enrich.get("evidence_page"), dict):
        evidence_claims = enrich["evidence_page"].get("claims")
    if not isinstance(evidence_claims, dict):
        errors.append(_error("enrich.evidence_page.claims 必须是对象"))
        evidence_claims = {}
    if set(evidence_claims) != set(claims):
        errors.append(_error(
            "evidence claim_id 与最终 claims 不精确一致；"
            f"缺 {sorted(set(claims) - set(evidence_claims))}，多 {sorted(set(evidence_claims) - set(claims))}"
        ))

    narrative_ids = {_chapter_id(chapter_no): chapter for chapter_no, chapter in chapters.items()}
    source_lines = source_text.splitlines()
    records = audit.get("records")
    if not isinstance(records, list):
        errors.append(_error("records 必须是数组"))
        records = []
    record_ids: set[str] = set()
    records_by_target: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    claim_source_chapters: dict[str, set[int]] = defaultdict(set)
    for index, record in enumerate(records):
        label = f"records[{index}]"
        if not isinstance(record, dict):
            errors.append(_error(f"{label} 非对象"))
            continue
        record_id = record.get("id")
        if not _nonempty(record_id):
            errors.append(_error(f"{label}.id 缺失或为空"))
        elif record_id.strip() in record_ids:
            errors.append(_error(f"record id={record_id.strip()!r} 重复"))
        else:
            record_ids.add(record_id.strip())
        target = record.get("target")
        if not isinstance(target, dict):
            errors.append(_error(f"{label}.target 必须是对象"))
            continue
        raw_kind, target_id = target.get("kind"), target.get("id")
        kind = raw_kind if isinstance(raw_kind, str) else "<invalid-kind>"
        if kind not in TARGET_KINDS:
            errors.append(_error(f"{label}.target.kind={raw_kind!r} 非法，应为 {sorted(TARGET_KINDS)}"))
        if not _nonempty(target_id):
            errors.append(_error(f"{label}.target.id 缺失或为空"))
            continue
        target_id = target_id.strip()
        if not _record_target_exists(
            kind, target_id, claims=claims, narrative_ids=narrative_ids,
            quote_targets=quote_targets, excerpt_targets=excerpt_targets, audit_flags=audit_flags,
        ):
            errors.append(_error(f"{label}.target={kind}:{target_id} 不存在于最终产物/claim-map"))
        records_by_target[(kind, target_id)].append(record)

        raw_facet = record.get("facet")
        facet = raw_facet if isinstance(raw_facet, str) else "<invalid-facet>"
        if facet not in FACETS:
            errors.append(_error(f"{label}.facet={raw_facet!r} 非法，应为 {sorted(FACETS)}"))
        raw_support = record.get("support")
        support = raw_support if isinstance(raw_support, str) else "<invalid-support>"
        if support not in SUPPORT_VALUES:
            errors.append(_error(f"{label}.support={raw_support!r} 非法，应为 {sorted(SUPPORT_VALUES)}"))
        if kind in {"quote", "excerpt"} and facet != "verbatim":
            errors.append(_error(f"{label} 的 quote/excerpt facet 必须是 'verbatim'"))
        if kind in {"quote", "excerpt"} and support != "direct":
            errors.append(_error(f"{label} 的 quote/excerpt support 必须是 'direct'"))

        segment_id = record.get("source_segment")
        segment = segment_by_id.get(segment_id) if _nonempty(segment_id) else None
        if segment is None:
            errors.append(_error(f"{label}.source_segment={segment_id!r} 不存在"))
        parsed_range = _parse_line_range(record.get("line_range"), f"{label}.line_range", errors)
        if segment is not None and parsed_range and segment.get("_range"):
            start, end = parsed_range
            segment_start, segment_end = segment["_range"]
            if start < segment_start or end > segment_end:
                errors.append(_error(
                    f"{label}.line_range 不在 source_segment={segment_id!r} 的章内范围"
                ))
            if end <= len(source_lines):
                excerpt = record.get("source_excerpt")
                if not _nonempty(excerpt):
                    errors.append(_error(f"{label}.source_excerpt 缺失或为空"))
                elif len(_compact(excerpt)) > 150:
                    errors.append(_error(f"{label}.source_excerpt 去空白后超过 150 字"))
                else:
                    range_text = "\n".join(source_lines[start - 1:end])
                    if _compact(excerpt) not in _compact(range_text):
                        errors.append(_error(f"{label}.source_excerpt 未在声明 line_range 内逐字命中"))
        elif not _nonempty(record.get("source_excerpt")):
            errors.append(_error(f"{label}.source_excerpt 缺失或为空"))

        assertion = record.get("assertion")
        if not _nonempty(assertion):
            errors.append(_error(f"{label}.assertion 缺失或为空"))

        segment_chapter = segment.get("chapter_no") if isinstance(segment, dict) else None
        if kind == "chapter_narrative" and segment_id != target_id:
            errors.append(_error(f"{label} narrative 来源 segment 必须等于 target.id={target_id!r}"))
        if kind == "claim" and _positive_int(segment_chapter) and support in {"direct", "partial"}:
            claim_source_chapters[target_id].add(segment_chapter)
        if kind == "audit_flag" and target_id in audit_flags:
            expected_range = audit_flags[target_id].get("line_range")
            if record.get("line_range") != expected_range:
                errors.append(_error(f"{label}.line_range 与 claim-map 的 audit flag 范围不一致"))

        final_item = quote_targets.get(target_id) if kind == "quote" else excerpt_targets.get(target_id)
        if final_item is not None:
            if record.get("source_excerpt") != final_item.get("text"):
                errors.append(_error(f"{label}.source_excerpt 与最终 {kind}.text 不逐字一致"))
            final_range = final_item.get("line_range")
            if _nonempty(final_range) and record.get("line_range") != final_range:
                errors.append(_error(f"{label}.line_range 与最终 {kind}.line_range 不一致"))
            expected_chapter = final_item.get("_chapter_no") or _anchor_chapter(final_item.get("anchor"))
            if expected_chapter and segment_chapter != expected_chapter:
                errors.append(_error(f"{label} 的来源章与最终 {kind}.anchor 不一致"))

    for claim_id, claim in claims.items():
        supporting = [r for r in records_by_target[("claim", claim_id)]
                      if isinstance(r.get("support"), str)
                      and r.get("support") in {"direct", "partial"}]
        if not supporting:
            errors.append(_error(f"最终 claim_id={claim_id!r} 至少需要 1 条 direct/partial 来源记录"))
        anchor_chapter = claim.get("anchor_chapter")
        if anchor_chapter is None:
            errors.append(_error(f"最终 claim_id={claim_id!r} 的 anchor 未声明第N章"))
        elif supporting and anchor_chapter not in claim_source_chapters.get(claim_id, set()):
            errors.append(_error(f"最终 claim_id={claim_id!r} 没有来自其 anchor 第{anchor_chapter}章的来源记录"))

    for chapter_no in sorted(chapters):
        target_id = _chapter_id(chapter_no)
        narrative_records = [r for r in records_by_target[("chapter_narrative", target_id)]
                             if isinstance(r.get("support"), str)
                             and r.get("support") in {"direct", "partial"}]
        facets = {r.get("facet") for r in narrative_records
                  if isinstance(r.get("facet"), str) and r.get("facet") in FACETS}
        if len(narrative_records) < 2 or len(facets) < 2:
            errors.append(_error(
                f"第{chapter_no}章 narrative 至少需要 2 条 direct/partial 且 facet 不同的来源记录"
            ))

    exact_targets = {
        "quote": quote_targets,
        "excerpt": excerpt_targets,
        "audit_flag": audit_flags,
    }
    for kind, targets in exact_targets.items():
        for target_id in targets:
            count = len(records_by_target[(kind, target_id)])
            if count != 1:
                errors.append(_error(f"{kind} target={target_id!r} 的来源记录须精确为 1，当前 {count}"))

    return errors


def validate_source_audit_file(
    audit_path: str | Path,
    *,
    expected_paths: Mapping[str, str | Path] | None = None,
) -> list[str]:
    """装载并验证同书目录 ``source-audit.json``；所有读取/解析故障均 fail-closed。"""
    path = Path(audit_path)
    errors: list[str] = []
    if path.name != "source-audit.json":
        errors.append(_error("审计文件名必须是 source-audit.json"))
    if not path.is_file():
        return errors + [_error(f"缺同书目录 source-audit.json: {path}")]
    try:
        audit = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return errors + [_error(f"source-audit.json 解析失败: {exc}")]
    if not isinstance(audit, dict):
        return errors + [_error("source-audit.json 顶层必须是对象")]

    book_dir = path.parent.resolve()
    inputs = audit.get("inputs") if isinstance(audit.get("inputs"), dict) else {}
    role_paths: dict[str, Path] = {}
    actual_hashes: dict[str, str] = {}
    payloads: dict[str, Any] = {"source": "", "distill": None, "claim_map": None, "enrich": None}
    for role in INPUT_ROLES:
        descriptor = inputs.get(role) if isinstance(inputs.get(role), dict) else {}
        raw = descriptor.get("path")
        if not _is_book_relative_file(raw):
            errors.append(_error(f"inputs.{role}.path 只允许同书目录的单个相对文件名"))
            continue
        candidate = (book_dir / raw.strip()).resolve()
        if candidate.parent != book_dir:
            errors.append(_error(f"inputs.{role}.path 解析后逃逸同书目录"))
            continue
        role_paths[role] = candidate
        if not candidate.is_file():
            errors.append(_error(f"inputs.{role}.path 指向文件不存在: {raw!r}"))
            continue
        expected = (expected_paths or {}).get(role)
        if expected is not None and candidate != Path(expected).resolve():
            errors.append(_error(
                f"inputs.{role}.path 未绑定本次 verify 使用的文件: {raw!r}"
            ))
        try:
            actual_hashes[role] = sha256_file(candidate)
            if role == "source":
                payloads[role] = candidate.read_text(encoding="utf-8")
            else:
                payloads[role] = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(_error(f"inputs.{role} 无法读取/解析: {exc}"))

    try:
        errors.extend(validate_source_audit_data(
            audit,
            source_text=payloads["source"] if isinstance(payloads["source"], str) else "",
            distill=payloads["distill"],
            claim_map=payloads["claim_map"],
            enrich=payloads["enrich"],
            actual_hashes=actual_hashes,
        ))
    except Exception as exc:  # 最终保险：坏输入不能因验证器异常而绕过门禁。
        errors.append(_error(f"验证器内部拒绝异常输入: {type(exc).__name__}: {exc}"))
    # 保序去重，避免 wrapper 与纯函数对同一坏 path 重复刷屏。
    return list(dict.fromkeys(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="验证 psychology-source-audit-v1 原文审计账本")
    parser.add_argument("audit", type=Path, help="同书目录 source-audit.json")
    args = parser.parse_args()
    errors = validate_source_audit_file(args.audit)
    print("\n".join(errors) if errors else "全部通过")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

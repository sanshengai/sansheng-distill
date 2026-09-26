#!/usr/bin/env python3
"""Audit a frozen, traceable book-source / knowledge-ledger / deep-reading contract.

Usage: python3 book_coverage.py --book-dir PATH
Inputs (schema_version=1): book.txt, source-map.json, content-ledger.json,
and deepread.json. Writes coverage-report.json atomically in the same directory.
Exit 0: structural coverage plus signed source/semantic reviews pass; exit 2:
machine validation fails; exit 3: source interpretation or manual review pending.

The immutable inventory digest must be frozen before drafting. Complete declared
coverage requires >=90% of effective items, >=80% in each effective source chapter,
and 100% of critical items; partial items never count as complete. Hashes bind
source locations, assets and reviewed bodies, but do not establish semantic truth.
A reviewer must actually verify meaning, exclusions and image interpretation.
This tool never signs approvals, invokes a model, or treats word overlap as proof.

Public helpers: sha256, canonical_sha256, inventory_sha256, review_sha256,
figure_inventory_sha256, figure_review_sha256, audit_book and main. Additional
schema metadata (including inventory_amendments) cannot waive these checks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

VERSION = 1
INVENTORY_FIELDS = ("id", "type", "chapter", "source_paragraph_ids", "critical", "statement")
ITEM_TYPES = {"claim", "definition", "reasoning", "evidence", "case", "method", "limitation", "counterexample", "figure", "appendix"}
STATUSES = {"covered", "partial", "missing", "excluded"}
LIMITATIONS = [
    "机器只核验来源位置、集合、冻结摘要、正文存在及声明覆盖比例，不判断正文是否真正解释了知识项。",
    "semantic_review 是主控实际审阅的记录，不是本工具生成的结论；不得用模型自评代替主控签署。",
    "冻结摘要只能检测相对于给定基线的变化，不能证明起稿前盘点在语义上完整，或防止同时重写基线。",
    "本工具不验证网页 DOM、图表视觉内容、著作权、事实正确性或已上线状态。",
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_sha256(value) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def inventory_sha256(items: list[dict]) -> str:
    """Freeze before drafting. Status, targets and reviews may subsequently change."""
    rows = [{key: item.get(key) for key in INVENTORY_FIELDS} for item in items]
    for row in rows:
        if isinstance(row["source_paragraph_ids"], list):
            row["source_paragraph_ids"] = sorted(row["source_paragraph_ids"])
    return canonical_sha256(sorted(rows, key=lambda row: str(row["id"])))


def review_sha256(item: dict, units: list[dict]) -> str:
    """Digest the exact declared disposition and analysis being manually reviewed."""
    targets = set(item.get("target_ids", []))
    return canonical_sha256({
        "inventory": {key: item.get(key) for key in INVENTORY_FIELDS},
        "status": item.get("status"),
        "exclusion_reason": item.get("exclusion_reason", ""),
        "target_ids": sorted(targets),
        "units": sorted([unit for unit in units if unit.get("id") in targets], key=lambda unit: unit["id"]),
    })


def figure_inventory_sha256(source_map: dict) -> str:
    """Bind a manual figure-inventory attestation to this source and asset list."""
    fields = ("id", "chapter", "section", "source_paragraph_ids", "asset_path", "sha256", "disposition", "exclusion_reason")
    return canonical_sha256({"source": source_map.get("source"), "figures": [
        {key: figure.get(key) for key in fields} for figure in source_map.get("figures", [])]})


def figure_review_sha256(figure: dict) -> str:
    return canonical_sha256({"asset_sha256": figure.get("sha256"), "text": figure.get("interpretation", {}).get("text", "")})


def nonempty(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def analysis_present(value) -> bool:
    if not nonempty(value):
        return False
    clean = re.sub(r"<[^>]*>|[\s#*_`~\-]", "", value)
    return bool(clean) and not re.fullmatch(r"[\[【]?(?:图片|图像|图表|image|figure)(?::[^\]】]*)?[\]】]?", clean, re.I)


def unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def audit_book(book_dir: Path) -> dict:
    errors: list[dict] = []
    warnings: list[dict] = []
    hashes = {}
    source_reviews = {"figure_inventory_complete": False, "figures": [], "unresolved_placeholders": [], "figure_items_without_assets": []}
    coverage_targets_met = False
    pending_source_item_ids = set()

    def fail(code, location, message):
        errors.append({"code": code, "location": location, "message": message})

    def result(metrics=None, reviews=None):
        machine_pass = not errors
        semantic_complete = bool(reviews) and all(row["complete"] for row in reviews)
        source_complete = source_reviews["figure_inventory_complete"] and not source_reviews["unresolved_placeholders"] and not source_reviews["figure_items_without_assets"] and all(row["complete"] for row in source_reviews["figures"])
        return {
            "schema_version": VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "book_dir": book_dir.name,
            "input_sha256": hashes,
            "machine_pass": machine_pass,
            "semantic_review_complete": semantic_complete,
            "source_review_complete": source_complete,
            "coverage_targets_met": coverage_targets_met,
            "coverage_gate_state": "failed" if not machine_pass else "pending_source_review" if not coverage_targets_met and pending_source_item_ids else "passed" if coverage_targets_met else "incomplete",
            "release_ready": machine_pass and coverage_targets_met and semantic_complete and source_complete,
            "coverage_basis": "declared covered items with structural source/target mappings; uninterpreted figure items excluded from complete numerator; semantic decisions reported separately",
            "thresholds": {"book": 0.90, "chapter": 0.80, "critical": 1.0},
            "metrics": metrics or {},
            "semantic_reviews": reviews or [],
            "source_reviews": source_reviews,
            "pending_source_item_ids": sorted(pending_source_item_ids),
            "errors": errors,
            "warnings": warnings,
            "limitations": LIMITATIONS,
        }

    def load(name):
        try:
            raw = (book_dir / name).read_bytes()
            hashes[name] = sha256(raw)
            doc = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_json)
            if not isinstance(doc, dict) or doc.get("schema_version") != VERSION:
                raise ValueError("expected object with schema_version=1")
            return doc
        except (OSError, ValueError, UnicodeError) as exc:
            fail("input_invalid", name, str(exc))
            return {}

    source_map = load("source-map.json")
    ledger = load("content-ledger.json")
    deepread = load("deepread.json")
    try:
        raw = (book_dir / "book.txt").read_bytes()
        hashes["book.txt"] = sha256(raw)
        text = raw.decode("utf-8")  # Preserve CRLF: spans address decoded bytes exactly.
    except (OSError, UnicodeError) as exc:
        fail("input_invalid", "book.txt", str(exc))
        return result()
    if not text.strip():
        fail("empty_source", "book.txt", "source must contain non-whitespace text")
    source = source_map.get("source", {})
    if not isinstance(source, dict) or source.get("path") != "book.txt" or source.get("sha256") != hashes["book.txt"]:
        fail("source_hash", "source-map.source", "path must be book.txt and SHA256 must match original bytes")

    def rows(doc, field, location):
        value = doc.get(field)
        if not isinstance(value, list):
            fail("schema", location, "expected array")
            return []
        if any(not isinstance(row, dict) for row in value):
            fail("schema", location, "all array entries must be objects")
            return [row for row in value if isinstance(row, dict)]
        return value

    chapters = rows(source_map, "chapters", "source-map.chapters")
    sections = rows(source_map, "sections", "source-map.sections")
    paragraphs = rows(source_map, "paragraphs", "source-map.paragraphs")
    items = rows(ledger, "items", "content-ledger.items")
    units = rows(deepread, "units", "deepread.units")
    figures = rows(source_map, "figures", "source-map.figures") if "figures" in source_map else []

    def index(records, location):
        mapping = {}
        for n, record in enumerate(records):
            rid = record.get("id")
            if not nonempty(rid):
                fail("invalid_id", f"{location}[{n}]", "id must be a nonblank string")
            elif rid in mapping:
                fail("duplicate_id", location, f"duplicate id {rid}")
            else:
                mapping[rid] = record
        return mapping

    ci, si, pi, ii, ui, fi = [index(r, name) for r, name in [
        (chapters, "chapters"), (sections, "sections"), (paragraphs, "paragraphs"), (items, "items"), (units, "units"), (figures, "figures")]]
    # Reject malformed shape before using IDs as dictionary keys or sets.
    for records, label in [(chapters, "chapters"), (sections, "sections"), (paragraphs, "paragraphs"), (items, "items"), (units, "units"), (figures, "figures")]:
        for record in records:
            for field in ("chapter", "section", "type", "status", "kind", "disposition"):
                if field in record and not isinstance(record[field], str):
                    fail("schema", f"{label}.{record.get('id')}.{field}", "expected string")
            for field in ("source_paragraph_ids", "target_ids"):
                if field in record and (not isinstance(record[field], list) or any(not nonempty(value) for value in record[field])):
                    fail("schema", f"{label}.{record.get('id')}.{field}", "expected array of nonblank string ids")
    if any(error["code"] in {"invalid_id", "schema", "input_invalid"} for error in errors):
        return result()
    if not chapters or not sections or not paragraphs:
        fail("empty_source_map", "source-map", "chapters, sections and paragraphs must all be nonempty")
    if not items:
        fail("empty_ledger", "content-ledger.items", "empty denominator cannot pass")
    try:
        if source_map.get("ledger_inventory_sha256") != inventory_sha256(items):
            fail("inventory_drift", "source-map.ledger_inventory_sha256", "immutable ledger fields differ from the pre-draft baseline")
    except (TypeError, ValueError):
        fail("inventory_invalid", "items", "inventory fields cannot be canonicalized")

    spans = {}
    for records, label in [(chapters, "chapters"), (sections, "sections"), (paragraphs, "paragraphs")]:
        valid = []
        for n, record in enumerate(records):
            rid = record.get("id", f"#{n}")
            loc = f"{label}.{rid}"
            start, end = record.get("start"), record.get("end")
            if type(start) is not int or type(end) is not int or not (0 <= start < end <= len(text)):
                fail("invalid_span", loc, "span must be integers 0 <= start < end <= len(book text)")
                continue
            spans[(label, rid)] = (start, end)
            valid.append((start, end, rid))
            if not text[start:end].strip():
                fail("empty_span", loc, "span must locate non-whitespace source text")
            if label == "paragraphs" and record.get("sha256") != sha256(text[start:end].encode("utf-8")):
                fail("paragraph_hash", loc, "paragraph SHA256 does not match the addressed source slice")
            disposition = record.get("disposition" if label == "paragraphs" else "kind")
            if disposition not in {"effective", "excluded"}:
                fail("disposition", loc, "kind/disposition must be effective or excluded")
            if disposition == "excluded" and not nonempty(record.get("exclusion_reason")):
                fail("unexplained_exclusion", loc, "excluded source requires a reason")
        previous_end = 0
        for start, end, rid in sorted(valid):
            if start < previous_end:
                fail("overlapping_source", f"{label}.{rid}", "source spans may not overlap within a level")
            if text[previous_end:start].strip():
                fail("unmapped_source", label, f"non-whitespace source has no destination at [{previous_end},{start})")
            previous_end = max(previous_end, end)
        if text[previous_end:].strip():
            fail("unmapped_source", label, f"non-whitespace source has no destination at [{previous_end},{len(text)})")

    def contained(child_label, child, parent_label, parent_id):
        span = spans.get((child_label, child.get("id")))
        parent = spans.get((parent_label, parent_id))
        if not span or not parent or not (parent[0] <= span[0] < span[1] <= parent[1]):
            fail("source_parent", f"{child_label}.{child.get('id')}", f"source position does not belong to {parent_label}.{parent_id}")

    for section in sections:
        cid = section.get("chapter")
        contained("sections", section, "chapters", cid)
        if cid in ci and ci[cid].get("kind") == "excluded" and section.get("kind") != "excluded":
            fail("excluded_parent", f"sections.{section.get('id')}", "excluded chapter cannot contain an effective section")
        if not any(p.get("section") == section.get("id") for p in paragraphs):
            fail("empty_section", f"sections.{section.get('id')}", "section has no paragraph destinations")
    for paragraph in paragraphs:
        cid, sid = paragraph.get("chapter"), paragraph.get("section")
        contained("paragraphs", paragraph, "chapters", cid)
        contained("paragraphs", paragraph, "sections", sid)
        if sid not in si or si[sid].get("chapter") != cid:
            fail("source_chapter", f"paragraphs.{paragraph.get('id')}", "section and paragraph chapter differ")
        if ((cid in ci and ci[cid].get("kind") == "excluded") or (sid in si and si[sid].get("kind") == "excluded")) and paragraph.get("disposition") != "excluded":
            fail("excluded_parent", f"paragraphs.{paragraph.get('id')}", "excluded source container cannot contain an effective paragraph")

    def ids(record, field, location, required=False):
        values = record.get(field)
        if not isinstance(values, list) or any(not nonempty(value) for value in values):
            fail("schema", f"{location}.{field}", "expected array of nonblank string ids")
            return []
        if len(set(values)) != len(values):
            fail("duplicate_reference", f"{location}.{field}", "duplicate ids would count one destination repeatedly")
        if required and not values:
            fail("empty_reference", f"{location}.{field}", "at least one id is required")
        return values

    valid_units = set()
    for unit in units:
        loc = f"units.{unit.get('id')}"
        before = len(errors)
        cid = unit.get("chapter")
        if cid not in ci or ci[cid].get("kind") != "effective":
            fail("target_chapter", loc, "target must belong to an effective source chapter")
        body = unit.get("body")
        if not analysis_present(body):
            fail("empty_body", loc, "an ID or markup without analysis body cannot count")
        for pid in ids(unit, "source_paragraph_ids", loc, True):
            if pid not in pi or pi[pid].get("chapter") != cid:
                fail("target_source_chapter", loc, f"source {pid} is missing or belongs to another chapter")
            elif pi[pid].get("disposition") != "effective":
                fail("target_excluded_source", loc, f"source {pid} is excluded from knowledge content")
        if len(errors) == before:
            valid_units.add(unit.get("id"))

    source_destinations = defaultdict(set)
    covered = set()
    signatures = set()
    reviews = []
    excluded_items = []
    for item in items:
        iid, cid, status = item.get("id"), item.get("chapter"), item.get("status")
        loc = f"items.{iid}"
        before = len(errors)
        if cid not in ci or ci[cid].get("kind") != "effective":
            fail("item_chapter", loc, "item must belong to an effective source chapter")
        if item.get("type") not in ITEM_TYPES or not nonempty(item.get("statement")) or type(item.get("critical")) is not bool:
            fail("item_inventory", loc, "type, substantive statement and boolean critical are required")
        if status not in STATUSES:
            fail("item_status", loc, "unknown item status")
        pids = ids(item, "source_paragraph_ids", loc, True)
        tids = ids(item, "target_ids", loc, status == "covered")
        for pid in pids:
            if pid not in pi or pi[pid].get("chapter") != cid:
                fail("item_source_chapter", loc, f"source {pid} is missing or belongs to another chapter")
            elif status != "excluded" and pi[pid].get("disposition") != "effective":
                fail("item_excluded_source", loc, f"effective item points to excluded source {pid}")
            source_destinations[pid].add(iid)
        for tid in tids:
            if tid not in ui:
                fail("dangling_target", loc, f"target {tid} does not exist")
            elif tid not in valid_units or ui[tid].get("chapter") != cid:
                fail("invalid_target", loc, f"target {tid} is invalid or belongs to another chapter")
        if status == "covered":
            mapped = {pid for tid in tids if tid in ui for pid in ui[tid].get("source_paragraph_ids", []) if isinstance(pid, str)}
            if not set(pids).issubset(mapped):
                fail("target_source_mapping", loc, "covered item source paragraphs are absent from its actual target units")
        if status == "excluded":
            if item.get("critical"):
                fail("critical_excluded", loc, "critical knowledge cannot be excluded")
            if not nonempty(item.get("exclusion_reason")):
                fail("unexplained_exclusion", loc, "excluded item requires a reason")
            excluded_items.append({"id": iid, "reason": item.get("exclusion_reason", "")})
        if status in {"partial", "missing"} and not nonempty(item.get("exclusion_reason")):
            fail("unexplained_gap", loc, "partial/missing item must explain the outstanding gap in exclusion_reason")
        signature = (str(cid), str(item.get("type")), tuple(sorted(pids)), re.sub(r"\s+", "", str(item.get("statement", ""))))
        if signature in signatures:
            fail("duplicate_item", loc, "identical knowledge item would inflate the denominator/numerator")
        signatures.add(signature)
        if status == "covered" and len(errors) == before:
            covered.add(iid)
        review = item.get("semantic_review", {})
        complete = isinstance(review, dict) and review.get("decision") == "approved" and nonempty(review.get("reviewer")) and nonempty(review.get("rationale"))
        if complete:
            try:
                complete = review.get("reviewed_content_sha256") == review_sha256(item, units)
            except (TypeError, ValueError):
                complete = False
        reviews.append({"id": iid, "complete": complete, "decision": review.get("decision", "pending") if isinstance(review, dict) else "pending", "reviewer": review.get("reviewer", "") if isinstance(review, dict) else ""})

    for paragraph in paragraphs:
        if paragraph.get("disposition") == "effective" and not source_destinations[paragraph.get("id")]:
            fail("paragraph_without_item", f"paragraphs.{paragraph.get('id')}", "effective source paragraph has no frozen ledger destination")

    inventory_review = source_map.get("figure_inventory_review", {})
    if isinstance(inventory_review, dict):
        source_reviews["figure_inventory_complete"] = (
            inventory_review.get("decision") == "approved" and nonempty(inventory_review.get("reviewer"))
            and nonempty(inventory_review.get("rationale"))
            and inventory_review.get("reviewed_inventory_sha256") == figure_inventory_sha256(source_map))
    mapped_figure_paragraphs = set()
    structurally_mapped_covered = covered.copy()
    for figure in figures:
        loc = f"figures.{figure.get('id')}"
        cid, sid = figure.get("chapter"), figure.get("section")
        if cid not in ci or sid not in si or si[sid].get("chapter") != cid:
            fail("figure_source", loc, "figure chapter/section must belong to the source inventory")
        pids = ids(figure, "source_paragraph_ids", loc, True)
        mapped_figure_paragraphs.update(pids)
        for pid in pids:
            if pid not in pi or pi[pid].get("chapter") != cid or pi[pid].get("section") != sid:
                fail("figure_source", loc, f"figure source paragraph {pid} belongs to another section/chapter or is absent")
        if figure.get("disposition") not in {"effective", "excluded"}:
            fail("disposition", loc, "figure disposition must be effective or excluded")
        if figure.get("disposition") == "excluded" and not nonempty(figure.get("exclusion_reason")):
            fail("unexplained_exclusion", loc, "excluded figure requires a reason")
        asset = figure.get("asset_path")
        asset_valid = False
        if not nonempty(asset):
            fail("figure_asset", loc, "asset_path must identify a real local file; absolute private paths are permitted only in private provenance")
        else:
            try:
                asset_file = Path(asset) if Path(asset).is_absolute() else book_dir / asset
                asset_valid = sha256(asset_file.read_bytes()) == figure.get("sha256")
                if not asset_valid:
                    fail("figure_asset", loc, "figure asset SHA256 differs from the frozen inventory")
            except OSError as exc:
                fail("figure_asset", loc, str(exc))
        interpretation = figure.get("interpretation", {})
        if not isinstance(interpretation, dict):
            interpretation = {}
        complete = figure.get("disposition") == "excluded" and asset_valid
        if figure.get("disposition") == "effective":
            linked = [item for item in items if item.get("type") == "figure" and item.get("chapter") == cid and set(pids).issubset(set(item.get("source_paragraph_ids", []))) and item.get("id") in covered]
            if not analysis_present(interpretation.get("text")):
                for item in linked:
                    pending_source_item_ids.add(item["id"])
                    covered.discard(item["id"])
            complete = bool(linked) and asset_valid and analysis_present(interpretation.get("text")) and interpretation.get("decision") == "approved" and nonempty(interpretation.get("reviewer")) and nonempty(interpretation.get("rationale")) and interpretation.get("reviewed_content_sha256") == figure_review_sha256(figure)
        source_reviews["figures"].append({"id": figure.get("id"), "complete": complete, "disposition": figure.get("disposition"), "decision": interpretation.get("decision", "pending")})
    placeholder_pattern = re.compile(r"\[(?:图片|图像|图表|image|figure)(?:\]|[:：\s])|【(?:图片|图像|图表)|〔图字[:：]|<img\b", re.I)
    for paragraph in paragraphs:
        span = spans.get(("paragraphs", paragraph.get("id")))
        if paragraph.get("disposition") == "effective" and span and (paragraph.get("content_kind") in {"figure", "figure_placeholder"} or placeholder_pattern.search(text[span[0]:span[1]])) and paragraph.get("id") not in mapped_figure_paragraphs:
            source_reviews["unresolved_placeholders"].append(paragraph.get("id"))
            for iid in source_destinations[paragraph.get("id")]:
                pending_source_item_ids.add(iid)
                covered.discard(iid)
    for item in [item for item in items if item.get("type") == "figure" and item.get("status") != "excluded"]:
        if not any(figure.get("disposition") == "effective" and set(figure.get("source_paragraph_ids", [])).issubset(set(item.get("source_paragraph_ids", []))) for figure in figures):
            source_reviews["figure_items_without_assets"].append(item.get("id"))
            pending_source_item_ids.add(item.get("id"))
            covered.discard(item.get("id"))
    for unit in units:
        if not any(unit.get("id") in item.get("target_ids", []) for item in items):
            warnings.append({"code": "unlinked_unit", "id": unit.get("id"), "message": "analysis unit is not linked from the ledger and counts toward no coverage item"})

    effective = [item for item in items if item.get("status") != "excluded"]

    def measure(group, membership=None):
        membership = covered if membership is None else membership
        count = sum(item.get("id") in membership for item in group)
        return {"effective_items": len(group), "covered_items": count, "ratio": count / len(group) if group else None,
                "status_counts": dict(Counter(str(item.get("status")) for item in group)),
                "incomplete_ids": [item.get("id") for item in group if item.get("id") not in membership]}

    book = measure(effective)
    critical = measure([item for item in effective if item.get("critical") is True])
    chapter_metrics = {cid: measure([item for item in effective if item.get("chapter") == cid]) for cid, chapter in ci.items() if chapter.get("kind") == "effective"}
    type_metrics = {kind: measure([item for item in effective if item.get("type") == kind]) for kind in sorted(ITEM_TYPES) if any(item.get("type") == kind for item in effective)}
    mapped_book = measure(effective, structurally_mapped_covered)
    if not effective:
        fail("empty_denominator", "book", "no effective information items")
    elif mapped_book["covered_items"] * 10 < mapped_book["effective_items"] * 9:
        fail("book_coverage", "book", "complete structural coverage must be at least 90%")
    for cid, metric in chapter_metrics.items():
        mapped_chapter = measure([item for item in effective if item.get("chapter") == cid], structurally_mapped_covered)
        if not metric["effective_items"]:
            fail("empty_chapter_denominator", f"chapters.{cid}", "effective chapter has no effective ledger items")
        elif mapped_chapter["covered_items"] * 5 < metric["effective_items"] * 4:
            fail("chapter_coverage", f"chapters.{cid}", "complete structural coverage must be at least 80%")
    mapped_critical = measure([item for item in effective if item.get("critical") is True], structurally_mapped_covered)
    if not critical["effective_items"]:
        fail("empty_critical_denominator", "critical", "management-book inventory must identify at least one core proposition or limiting condition before drafting")
    elif mapped_critical["covered_items"] != critical["effective_items"]:
        fail("critical_coverage", "critical", "all critical items require complete coverage")
    coverage_targets_met = bool(effective) and book["covered_items"] * 10 >= book["effective_items"] * 9 and all(m["effective_items"] and m["covered_items"] * 5 >= m["effective_items"] * 4 for m in chapter_metrics.values()) and critical["covered_items"] == critical["effective_items"]
    metrics = {"book": book, "chapters": chapter_metrics, "types": type_metrics, "critical": critical,
               "ledger_items_before_exclusions": len(items), "ledger_items_after_exclusions": len(effective),
               "excluded_items": excluded_items,
               "source_paragraphs": len(paragraphs), "effective_paragraphs": sum(p.get("disposition") == "effective" for p in paragraphs),
               "excluded_paragraphs": [{"id": p.get("id"), "reason": p.get("exclusion_reason", "")} for p in paragraphs if p.get("disposition") == "excluded"],
               "mapped_effective_paragraphs": sum(p.get("disposition") == "effective" and bool(source_destinations[p.get("id")]) for p in paragraphs),
               "source_characters": len(text), "analysis_characters": sum(len(u.get("body", "")) for u in units if isinstance(u.get("body"), str))}
    return result(metrics, reviews)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book-dir", required=True, type=Path)
    args = parser.parse_args()
    if not args.book_dir.is_dir():
        parser.error("--book-dir must be an existing directory")
    report = audit_book(args.book_dir)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=args.book_dir, prefix=".coverage-", suffix=".tmp", delete=False) as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(args.book_dir / "coverage-report.json")
    print(json.dumps({key: report[key] for key in ("machine_pass", "semantic_review_complete", "source_review_complete", "release_ready")}, ensure_ascii=False))
    for error in report["errors"][:8]:
        print(f"{error['code']}: {error['location']}: {error['message']}")
    print(f"report: {args.book_dir / 'coverage-report.json'}")
    return 0 if report["release_ready"] else 2 if not report["machine_pass"] else 3


if __name__ == "__main__":
    raise SystemExit(main())

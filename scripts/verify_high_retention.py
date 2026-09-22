#!/usr/bin/env python3
"""Full legacy page validation plus live coverage and reviewed short apparatus.

This entry never signs reviews. An optional short-apparatus-review.json binds
all six source/content inputs; only its individually approved, genuinely short
non-primary sections may replace the legacy 800-character G9 requirement.
All other legacy/source/browser checks still run on the complete book.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys


INPUTS = ("book.txt", "source-map.json", "content-ledger.json", "deepread.json",
          "config.json", "distill.json")
ROLES = {"source_apparatus", "editorial_context"}


def load_module(name, filename):
    scripts = str(Path(__file__).resolve().parent)
    added = scripts not in sys.path
    if added:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        if added:
            sys.path.remove(scripts)
    return module


COVERAGE = load_module("high_retention_coverage", "book_coverage.py")
LEGACY = load_module("high_retention_legacy", "verify_page.py")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(data, dict), f"{path.name}: expected object")
    return data


def input_hashes(directory):
    return {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in INPUTS}


def nonempty_text(text):
    return isinstance(text, str) and any(char.isalnum() for char in text)


def indexed(rows, key, label):
    require(isinstance(rows, list) and rows, f"{label}: empty collection")
    require(all(isinstance(row, dict) and key in row for row in rows),
            f"{label}: missing identity")
    result = {row[key]: row for row in rows}
    require(len(result) == len(rows), f"{label}: duplicate identity")
    return result


def mapping(config, distill, source, deepread):
    configured = indexed(config.get("chapters"), "no", "config chapters")
    chapters = indexed(distill.get("chapters"), "no", "distill chapters")
    units = indexed(deepread.get("units"), "id", "deepread units")
    original = indexed(source.get("chapters"), "id", "source chapters")
    effective = {key for key, row in original.items() if row.get("kind") == "effective"}
    require(set(configured) == set(chapters), "config/distill chapter set mismatch")
    require({c.get("source_chapter_id") for c in configured.values()} == effective,
            "config does not map every effective source chapter")
    seen = []
    for no, row in configured.items():
        cid = row["source_chapter_id"]
        require(chapters[no].get("source_chapter_id") == cid,
                f"chapter {no}: distill source mapping mismatch")
        ids = row.get("deepread_unit_ids")
        require(isinstance(ids, list) and ids, f"chapter {no}: no deepread units")
        for uid in ids:
            require(uid in units and units[uid].get("chapter") == cid,
                    f"chapter {no}: invalid deepread unit {uid}")
        seen.extend(ids)
    require(len(seen) == len(set(seen)) and set(seen) == set(units),
            "deepread unit set is omitted or multiply mapped")
    return configured, chapters, original, units


def accepted_apparatus(directory, data, fresh_coverage, mapped):
    path = directory / "short-apparatus-review.json"
    if not path.exists():
        return []
    receipt = read_json(path)
    require(receipt.get("schema_version") == 1, "short apparatus: invalid schema")
    require(receipt.get("input_sha256") == input_hashes(directory),
            "short apparatus: reviewed input hashes are stale or incomplete")
    require(fresh_coverage.get("release_ready") is True,
            "short apparatus: current source/semantic coverage is not approved")
    entries = indexed(receipt.get("entries"), "no", "short apparatus reviews")
    configured, chapters, original, units = mapped
    accepted = []
    for no, review in entries.items():
        require(type(no) is int and no in configured, "short apparatus: unknown chapter")
        cfg, chapter = configured[no], chapters[no]
        cid = cfg["source_chapter_id"]
        source_chapter = original[cid]
        require(review.get("source_chapter_id") == cid, "short apparatus: chapter mismatch")
        require(review.get("decision") == "approved" and
                nonempty_text(review.get("reviewer")) and nonempty_text(review.get("rationale")),
                "short apparatus: explicit manual review required")
        require(cfg.get("source_role") in ROLES and
                source_chapter.get("source_scope") == "non_primary" and
                source_chapter.get("kind") == "effective",
                "short apparatus: primary content cannot use a short-section rule")
        source_review = source_chapter.get("classification_review", {})
        require(source_review.get("decision") == "approved" and
                nonempty_text(source_review.get("reviewer")) and
                nonempty_text(source_review.get("rationale")),
                "short apparatus: source classification has not been reviewed")
        start, end = source_chapter.get("start"), source_chapter.get("end")
        text = data["book.txt"]
        require(type(start) is int and type(end) is int and 0 <= start < end <= len(text),
                "short apparatus: invalid source span")
        actual = text[start:end]
        source_length = len(re.sub(r"\s", "", actual))
        require(nonempty_text(actual) and source_length < 800,
                "short apparatus: source is empty, punctuation only, or not short")
        body = chapter.get("narrative", "")
        body_length = len(re.sub(r"\s", "", body))
        require(nonempty_text(body) and 0 < body_length < 800,
                "short apparatus: narrative is empty or does not need this exception")
        items = [item for item in data["content-ledger.json"]["items"] if item.get("chapter") == cid]
        require(items and all(item.get("status") == "covered" for item in items),
                "short apparatus: every knowledge obligation must be fully covered")
        ids = review.get("knowledge_item_ids")
        require(isinstance(ids, list) and len(ids) == len(set(ids)) and
                set(ids) == {item["id"] for item in items},
                "short apparatus: reviewed knowledge set mismatch")
        for item in items:
            require(item.get("target_ids") and all(
                uid in cfg["deepread_unit_ids"] and units[uid].get("chapter") == cid
                for uid in item["target_ids"]), "short apparatus: foreign or missing target")
        accepted.append({"no": no, "source_chapter_id": cid,
                         "source_chars": source_length, "narrative_chars": body_length,
                         "knowledge_items": len(items), "reviewer": review["reviewer"]})
    return accepted


def dom_errors(html, mapped):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    configured, chapters, _, units = mapped
    errors = []
    expected = {f"ch-{no}" for no in configured}
    actual = [section.get("id") for section in soup.select("section.bd-chapter")]
    if len(actual) != len(expected) or set(actual) != expected:
        errors.append("[high-retention DOM] reading chapter set differs from inputs")
    elements = soup.select("details.bd-deep-unit")
    if len(elements) != len(units) or {e.get("id") for e in elements} != set(units):
        errors.append("[high-retention DOM] deepread unit set differs from inputs")
    def comparable(value):
        return re.sub(r"\s", "", value.replace("——", "--").replace("—", "--").replace("―", "--"))
    for no, cfg in configured.items():
        parent = soup.find("section", id=f"ch-{no}")
        if parent is None:
            continue
        for selector, field in ((".ch-narrative", "narrative"), (".ch-summary", "summary")):
            nodes = parent.select(selector)
            if len(nodes) != 1 or comparable(nodes[0].get_text()) != comparable(chapters[no].get(field, "")):
                errors.append(f"[high-retention DOM] chapter {no}: {field} differs from reviewed input")
        for uid in cfg["deepread_unit_ids"]:
            found = parent.find_all("details", id=uid)
            if len(found) != 1:
                errors.append(f"[high-retention DOM] {uid}: missing or duplicated in chapter {no}")
                continue
            body = found[0].select_one(".deep-unit-body")
            if body is None or comparable(body.get_text()) != comparable(units[uid]["body"]):
                errors.append(f"[high-retention DOM] {uid}: body differs from reviewed input")
    return errors


def audit(directory, interact=True, screenshot=None):
    directory = Path(directory)
    data = {name: ((directory / name).read_bytes().decode("utf-8") if name == "book.txt"
                   else read_json(directory / name)) for name in INPUTS}
    config, distill = data["config.json"], data["distill.json"]
    slug = config.get("slug", "")
    require(isinstance(slug, str) and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug),
            "config: invalid slug")
    page = directory / f"{slug}.html"
    html = page.read_text(encoding="utf-8")
    enrich = read_json(directory / "enrich.json")
    errors = LEGACY.lint_html(html, distill, enrich)
    errors += LEGACY.lint_source_grounding(distill, data["book.txt"])
    coverage = COVERAGE.audit_book(directory)
    if coverage.get("release_ready") is not True:
        errors.append("[high-retention] freshly recomputed coverage is not approved")
    accepted = []
    try:
        mapped = mapping(config, distill, data["source-map.json"], data["deepread.json"])
        errors += dom_errors(html, mapped)
        accepted = accepted_apparatus(directory, data, coverage, mapped)
    except (ValueError, KeyError, TypeError) as exc:
        errors.append(f"[high-retention] {exc}")
    # Exact, chapter-specific G9 messages only. Never remove any other violation.
    permitted = {f'[distill] 第{x["no"]}章 narrative {x["narrative_chars"]} 字 < 800(G9 详实度)'
                 for x in accepted}
    errors = [error for error in errors if error not in permitted]
    if interact:
        evidence = enrich.get("evidence_page", {}).get("claims", {})
        errors += LEGACY.smoke(page, screenshot, distill, evidence)
    return {"schema_version": 1, "passed": not errors,
            "browser_checked": interact, "input_sha256": input_hashes(directory),
            "coverage_recomputed": True, "accepted_short_apparatus": accepted,
            "errors": errors, "scope": "Source/content/page checks only; not website deployment or a substitute for visual and semantic review."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book-dir", type=Path, required=True)
    parser.add_argument("--skip-interact", action="store_true")
    parser.add_argument("--screenshot")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        report = audit(args.book_dir, not args.skip_interact, args.screenshot)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        report = {"schema_version": 1, "passed": False, "errors": [str(exc)]}
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

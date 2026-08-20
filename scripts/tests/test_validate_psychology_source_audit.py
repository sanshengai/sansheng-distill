import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from validate_psychology_source_audit import (  # noqa: E402
    validate_source_audit_data,
    validate_source_audit_file,
)


SOURCE_LINES = [
    "前言",
    "本审计说明",
    "第1章 第一章标题",
    "系统会自动作出快速判断。",
    "案例显示先看见线索再作答。",
    "第2章 第二章标题",
    "结构化清单可以减少遗漏。",
    "边界是在高风险情境中仍需专业判断。",
]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record(record_id, kind, target_id, segment, line_range, excerpt, assertion,
            facet, support="direct"):
    return {
        "id": record_id,
        "target": {"kind": kind, "id": target_id},
        "facet": facet,
        "source_segment": segment,
        "line_range": line_range,
        "source_excerpt": excerpt,
        "assertion": assertion,
        "support": support,
    }


def audit_fixture(tmp_path: Path):
    source_text = "\n".join(SOURCE_LINES) + "\n"
    distill = {
        "slug": "psych-book",
        "domain_profile": {"domain": "psychology"},
        "core_ideas": [{
            "claim_id": "fast-judgment", "claim_type": "descriptive",
            "idea": "系统会自动作出快速判断", "anchor": "第1章",
        }],
        "decision_rules": [{
            "claim_id": "use-checklist", "claim_type": "intervention",
            "when": "高风险情境", "do": "使用结构化清单",
            "because": "可以减少遗漏", "anchor": "第2章",
        }],
        "chapters": [
            {
                "no": 1, "title": "第一章标题", "anchor": "第1章",
                "narrative": "系统会自动作出快速判断，因此需要理解机制。案例显示线索会先影响作答。",
                "excerpts": [{
                    "text": SOURCE_LINES[3], "anchor": "第1章",
                    "line_range": "L000004-L000004",
                }],
            },
            {
                "no": 2, "title": "第二章标题", "anchor": "第2章",
                "narrative": "结构化清单可以减少遗漏，但高风险情境仍需专业判断。",
                "excerpts": [{
                    "text": SOURCE_LINES[6], "anchor": "第2章",
                    "line_range": "L000007-L000007",
                }],
            },
        ],
        "quotes": [{"text": SOURCE_LINES[4], "anchor": "第1章"}],
    }
    claim_map = {
        "schema_version": "psychology-claim-coverage-v1",
        "book_slug": "psych-book",
        "entries": [
            {
                "source_group": "g1", "source_claim_id": "fast-candidate",
                "line_range": "L000004-L000004", "reason": "快速判断需外证",
                "disposition": "mapped", "final_claim_id": "fast-judgment",
            },
            {
                "source_group": "g2", "source_claim_id": "boundary-candidate",
                "line_range": "L000008-L000008", "reason": "边界候选未进入最终主张",
                "disposition": "excluded", "final_claim_id": None,
            },
        ],
    }
    enrich = {
        "evidence_page": {
            "as_of": "2026-08-20",
            "claims": {"fast-judgment": {}, "use-checklist": {}},
        }
    }
    files = {
        "source": ("book.txt", source_text),
        "distill": ("distill.json", distill),
        "claim_map": ("claim-coverage.json", claim_map),
        "enrich": ("enrich.json", enrich),
    }
    for role, (name, payload) in files.items():
        path = tmp_path / name
        if role == "source":
            path.write_text(payload, encoding="utf-8")
        else:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    audit = {
        "schema_version": "psychology-source-audit-v1",
        "book_slug": "psych-book",
        "inputs": {
            role: {
                "path": name,
                "sha256": _sha(tmp_path / name),
                **({"line_count": len(SOURCE_LINES)} if role == "source" else {}),
            }
            for role, (name, _) in files.items()
        },
        "segments": [
            {
                "id": "frontmatter", "kind": "frontmatter",
                "line_range": "L000001-L000002", "heading_excerpt": "前言",
            },
            {
                "id": "ch01", "kind": "chapter", "chapter_no": 1,
                "line_range": "L000003-L000005", "heading_excerpt": "第1章 第一章标题",
            },
            {
                "id": "ch02", "kind": "chapter", "chapter_no": 2,
                "line_range": "L000006-L000008", "heading_excerpt": "第2章 第二章标题",
            },
        ],
        "records": [
            _record("claim:fast", "claim", "fast-judgment", "ch01", "L000004-L000004",
                    SOURCE_LINES[3], "系统会自动作出快速判断", "claim"),
            _record("claim:checklist", "claim", "use-checklist", "ch02", "L000007-L000007",
                    SOURCE_LINES[6], "使用结构化清单", "claim"),
            _record("narrative:ch01:mechanism", "chapter_narrative", "ch01", "ch01",
                    "L000004-L000004", SOURCE_LINES[3], "系统会自动作出快速判断", "mechanism"),
            _record("narrative:ch01:case", "chapter_narrative", "ch01", "ch01",
                    "L000005-L000005", SOURCE_LINES[4], "案例显示线索会先影响作答", "case"),
            _record("narrative:ch02:mechanism", "chapter_narrative", "ch02", "ch02",
                    "L000007-L000007", SOURCE_LINES[6], "结构化清单可以减少遗漏", "mechanism"),
            _record("narrative:ch02:boundary", "chapter_narrative", "ch02", "ch02",
                    "L000008-L000008", SOURCE_LINES[7], "高风险情境仍需专业判断", "boundary"),
            _record("quote:q01", "quote", "q01", "ch01", "L000005-L000005",
                    SOURCE_LINES[4], SOURCE_LINES[4], "verbatim"),
            _record("excerpt:ch01:e01", "excerpt", "ch01:e01", "ch01", "L000004-L000004",
                    SOURCE_LINES[3], SOURCE_LINES[3], "verbatim"),
            _record("excerpt:ch02:e01", "excerpt", "ch02:e01", "ch02", "L000007-L000007",
                    SOURCE_LINES[6], SOURCE_LINES[6], "verbatim"),
            _record("audit:g1:fast", "audit_flag", "g1:fast-candidate", "ch01",
                    "L000004-L000004", SOURCE_LINES[3], "快速判断需外证", "claim"),
            _record("audit:g2:boundary", "audit_flag", "g2:boundary-candidate", "ch02",
                    "L000008-L000008", SOURCE_LINES[7], "边界候选未进入最终主张", "boundary"),
        ],
    }
    audit_path = tmp_path / "source-audit.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit, source_text, distill, claim_map, enrich, audit_path


def _pure(audit, source_text, distill, claim_map, enrich, actual_hashes=None):
    return validate_source_audit_data(
        audit,
        source_text=source_text,
        distill=distill,
        claim_map=claim_map,
        enrich=enrich,
        actual_hashes=actual_hashes or {role: audit["inputs"][role]["sha256"] for role in (
            "source", "distill", "claim_map", "enrich"
        )},
    )


def test_source_audit_clean_passes_pure_and_file_layers(tmp_path):
    audit, source, distill, claim_map, enrich, path = audit_fixture(tmp_path)
    assert _pure(audit, source, distill, claim_map, enrich) == []
    assert validate_source_audit_file(path, expected_paths={
        "source": tmp_path / "book.txt",
        "distill": tmp_path / "distill.json",
        "enrich": tmp_path / "enrich.json",
    }) == []


def test_source_audit_rejects_hash_and_line_count_drift(tmp_path):
    audit, source, distill, claim_map, enrich, _ = audit_fixture(tmp_path)
    actual_hashes = {role: audit["inputs"][role]["sha256"] for role in (
        "source", "distill", "claim_map", "enrich"
    )}
    audit["inputs"]["source"]["sha256"] = "0" * 64
    audit["inputs"]["source"]["line_count"] += 1
    errors = _pure(audit, source, distill, claim_map, enrich, actual_hashes)
    assert any("source.sha256 漂移" in error for error in errors)
    assert any("source.line_count 漂移" in error for error in errors)


@pytest.mark.parametrize("bad_path", ["../book.txt", "nested/book.txt", "C:\\outside\\book.txt"])
def test_source_audit_paths_are_same_book_relative_files_only(tmp_path, bad_path):
    audit, *_rest, path = audit_fixture(tmp_path)
    audit["inputs"]["source"]["path"] = bad_path
    path.write_text(json.dumps(audit, ensure_ascii=False), encoding="utf-8")
    errors = validate_source_audit_file(path)
    assert any("source.path" in error and "同书目录" in error for error in errors)


def test_source_audit_segments_must_be_contiguous_and_heading_must_hit_start_line(tmp_path):
    audit, source, distill, claim_map, enrich, _ = audit_fixture(tmp_path)
    audit["segments"][1]["line_range"] = "L000004-L000005"
    audit["segments"][2]["heading_excerpt"] = "不存在的章头"
    errors = _pure(audit, source, distill, claim_map, enrich)
    assert any("不连续" in error for error in errors)
    assert any("heading_excerpt" in error and "逐字命中" in error for error in errors)


def test_source_audit_records_reject_duplicate_unknown_cross_chapter_and_false_excerpt(tmp_path):
    audit, source, distill, claim_map, enrich, _ = audit_fixture(tmp_path)
    audit["records"][1]["id"] = audit["records"][0]["id"]
    audit["records"][0]["target"]["id"] = "missing-claim"
    audit["records"][2]["line_range"] = "L000007-L000007"
    audit["records"][3]["source_excerpt"] = "并不存在的原文"
    errors = _pure(audit, source, distill, claim_map, enrich)
    assert any("record id" in error and "重复" in error for error in errors)
    assert any("missing-claim" in error and "不存在" in error for error in errors)
    assert any("不在 source_segment" in error for error in errors)
    assert any("未在声明 line_range 内逐字命中" in error for error in errors)


def test_source_audit_allows_assertion_paraphrase_and_cross_line_verbatim(tmp_path):
    audit, source, distill, claim_map, enrich, _ = audit_fixture(tmp_path)
    audit["records"][0]["assertion"] = "模型对来源的短述，不要求复制最终文案"
    joined = SOURCE_LINES[3] + SOURCE_LINES[4]
    distill["quotes"][0]["text"] = joined
    quote_record = next(record for record in audit["records"] if record["target"] == {
        "kind": "quote", "id": "q01",
    })
    quote_record["line_range"] = "L000004-L000005"
    quote_record["source_excerpt"] = joined
    quote_record["assertion"] = "跨行原文"
    assert _pure(audit, source, distill, claim_map, enrich) == []


def test_source_audit_requires_each_final_claim_and_two_narrative_facets(tmp_path):
    audit, source, distill, claim_map, enrich, _ = audit_fixture(tmp_path)
    audit["records"] = [
        record for record in audit["records"]
        if record["target"] != {"kind": "claim", "id": "use-checklist"}
        and record["id"] != "narrative:ch02:boundary"
    ]
    errors = _pure(audit, source, distill, claim_map, enrich)
    assert any("use-checklist" in error and "至少需要 1 条" in error for error in errors)
    assert any("第2章 narrative" in error and "facet 不同" in error for error in errors)


def test_source_audit_quotes_excerpts_and_claim_map_flags_are_one_to_one(tmp_path):
    audit, source, distill, claim_map, enrich, _ = audit_fixture(tmp_path)
    audit["records"] = [record for record in audit["records"] if record["id"] != "quote:q01"]
    duplicate_excerpt = copy.deepcopy(next(
        record for record in audit["records"] if record["id"] == "excerpt:ch01:e01"
    ))
    duplicate_excerpt["id"] = "excerpt:ch01:e01:duplicate"
    audit["records"].append(duplicate_excerpt)
    audit["records"] = [
        record for record in audit["records"] if record["id"] != "audit:g2:boundary"
    ]
    errors = _pure(audit, source, distill, claim_map, enrich)
    assert any("quote target='q01'" in error and "当前 0" in error for error in errors)
    assert any("excerpt target='ch01:e01'" in error and "当前 2" in error for error in errors)
    assert any("audit_flag target='g2:boundary-candidate'" in error and "当前 0" in error for error in errors)


def test_source_audit_claim_map_and_evidence_coverage_are_exact(tmp_path):
    audit, source, distill, claim_map, enrich, _ = audit_fixture(tmp_path)
    claim_map["entries"][0]["final_claim_id"] = "phantom-claim"
    enrich["evidence_page"]["claims"].pop("use-checklist")
    enrich["evidence_page"]["claims"]["phantom-claim"] = {}
    errors = _pure(audit, source, distill, claim_map, enrich)
    assert any("mapped 到不存在" in error and "phantom-claim" in error for error in errors)
    assert any("evidence claim_id" in error and "use-checklist" in error and "phantom-claim" in error
               for error in errors)


def test_source_audit_malformed_nested_types_fail_closed(tmp_path):
    audit, source, distill, claim_map, enrich, path = audit_fixture(tmp_path)
    audit["records"][0]["target"]["kind"] = []
    path.write_text(json.dumps(audit, ensure_ascii=False), encoding="utf-8")
    errors = validate_source_audit_file(path)
    assert errors
    assert any("拒绝异常输入" in error or "target.kind" in error for error in errors)

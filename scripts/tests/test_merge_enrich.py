"""merge_enrich.py：五键兼容 + 心理学第六键条件保留。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from merge_enrich import BASE_KEYS, merge_payload


def _author():
    return {"author_page": {"name": "测试作者"}}


def _web(**extra):
    payload = {
        "similar_page": {"items": []},
        "views_page": {"topics": []},
        "reviews": None,
        "cross_book_external": {"cross_book_external": [{"title": "外部书"}]},
    }
    payload.update(extra)
    return payload


def test_legacy_merge_stays_five_keys():
    merged = merge_payload(_author(), _web())
    assert tuple(merged) == BASE_KEYS
    assert "evidence_page" not in merged
    assert merged["cross_book_external"] == [{"title": "外部书"}]


def test_psychology_evidence_page_is_preserved_as_sixth_key():
    evidence = {"as_of": "2026-08-20", "claims": {"claim-1": {"status": "supported"}}}
    merged = merge_payload(_author(), _web(evidence_page=evidence))
    assert tuple(merged) == BASE_KEYS + ("evidence_page",)
    assert merged["evidence_page"] == evidence


def test_explicit_null_evidence_page_is_not_silently_dropped():
    merged = merge_payload(_author(), _web(evidence_page=None))
    assert "evidence_page" in merged
    assert merged["evidence_page"] is None

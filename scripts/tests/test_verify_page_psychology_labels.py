"""心理学现行中文标签的正例与拒绝反例。"""
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_page import _research_has_status, _research_has_replication_status

STATUSES = {
    "supported": "站得住", "mixed": "证据混杂", "contested": "有争议",
    "not_supported": "没能复现", "not_testable": "无法检验",
}
REPLICATIONS = {
    "replicated": "已复现", "mixed": "部分复现", "failed": "未能复现",
    "not_attempted": "尚未检验", "not_applicable": "不适用",
}

@pytest.mark.parametrize("match, labels", [
    (_research_has_status, STATUSES),
    (_research_has_replication_status, REPLICATIONS),
])
def test_canonical_labels_match_only_correct_status(match, labels):
    for status, label in labels.items():
        assert match(label, status)
        assert not match("", status)
        assert not match("这里没有状态标签", status)
        for other_status, other_label in labels.items():
            if other_status != status:
                assert not match(other_label, status)

from verify_page import _has_source_note, lint_distill_schema, lint_html
from test_verify_page import distill, page

@pytest.mark.parametrize("cls", ["src-note", "deep-unit-source"])
def test_source_note_requires_real_nonempty_element(cls):
    assert _has_source_note(f'<p class="{cls}">原书位置：第十章</p>')
    assert not _has_source_note(f'<p class="{cls}"> </p>')
    assert not _has_source_note(f'<!-- <p class="{cls}">出处</p> -->')
    assert not _has_source_note(f'<style>.{cls}{{display:block}}</style>')
    assert not _has_source_note(f'<p class="{cls}" hidden>出处</p>')
    assert not _has_source_note(f'<p class="{cls}" style="display: none">出处</p>')


def test_actual_html_consumer_accepts_reader_source_and_rejects_missing():
    html = page().replace('class="src-note"', 'class="deep-unit-source"')
    assert not any("常显出处" in x for x in lint_html(html))
    assert any("常显出处" in x for x in lint_html(page(no_srcnote=True).replace('class="src-note"', 'class="removed-source"')))


def test_only_explicit_reader_empty_quote_array_is_allowed():
    assert lint_distill_schema(distill(quality_profile="reader", quotes=[])) == []
    for profile in (None, "strict", "guide"):
        assert any("quotes" in x for x in lint_distill_schema(distill(quality_profile=profile, quotes=[])))
    for value in (None, "", {}):
        assert any("quotes" in x for x in lint_distill_schema(distill(quality_profile="reader", quotes=value)))
    data = distill(quality_profile="reader")
    del data["quotes"]
    assert any("quotes" in x for x in lint_distill_schema(data))
    assert lint_distill_schema({})

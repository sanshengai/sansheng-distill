"""build_topic.py 聚合器单测:确定性派生 / index_relation 三档 / certainty 校验 / 门槛 / 防覆盖。"""
import sys
import json
import re
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent))
import build_topic as bt


def _distill(slug, **over):
    d = {"slug": slug, "title": slug.upper(), "book_type": "工具", "pub_year": 2010,
         "stakes": "high", "napkin": {"one_liner": "一句定位"}, "core_question": "问",
         "decision_rules": [{"certainty": "book_explicit", "anchor": "第1章"}],
         "core_ideas": [{"idea": "x", "certainty": "book_explicit", "anchor": "第1章"}]}
    d.update(over)
    return d


def _members(n=3):
    return [(f"b{i}", _distill(f"b{i}", pub_year=2000 + i)) for i in range(n)]


def _manual(**over):
    m = {"topic": "T", "slug": "t", "members": ["b0", "b1", "b2"],
         "schools": [{"id": "s1", "name": "派一", "kind": "applied", "evidence_status": "mixed",
                      "members": ["b0"], "anchor_book": "b0"},
                     {"id": "s2", "name": "派二", "kind": "theoretical", "evidence_status": "contested",
                      "members": ["b1", "b2"], "anchor_book": "b1"}],
         "disputes": [{"id": "d1", "question": "Q?", "concept": "C", "question_type": "causal",
                       "positions": [{"label": "L1", "members": ["b0"]},
                                     {"label": "L2", "members": ["b1"]}],
                       "adjudication": {
                           "status": "mixed", "book_view": "两书相反",
                           "research_view": "外部结果混合", "boundary_conditions": "依任务而变",
                       },
                       "sources": ["https://example.org/synthesis"]}],
         "dimensions": [{"name": "维度", "cells": [{"slug": "b0", "value": "3月"}]}]}
    m.update(over)
    return m


def _idx_contra():
    return {bt.norm("C"): {"concept": "C", "one_liner": "",
            "by_slug": {"b0": {"stance": "可训练", "quote": "q", "anchor": "第1章", "relation": "CONTRADICTS"},
                        "b1": {"stance": "不可训练", "relation": "NEW_CONCEPT"}},
            "relations": {"CONTRADICTS", "NEW_CONCEPT"}}}


# ---------------------------------------------------------------- 纯函数派生
def test_derive_books_school_reverse_and_oneliner_fallback():
    members = [("b0", _distill("b0", napkin={"one_liner": "L0"}))]
    m = {"members": ["b0"], "schools": [{"id": "s1", "members": ["b0"]}], "book_meta": {}}
    out = bt.derive_books(members, m)
    assert out[0]["school_ids"] == ["s1"]        # 从 schools 反推
    assert out[0]["one_liner"] == "L0"           # 缺 book_meta 回退 napkin


def test_derive_books_school_ids_ordered_deduplicated():
    members = [("b0", _distill("b0"))]
    m = {"members": ["b0"], "schools": [
        {"id": "lens-a", "members": ["b0", "b0"]},
        {"id": "lens-b", "members": ["b0"]},
        {"id": "lens-a", "members": ["b0"]},
    ]}
    out = bt.derive_books(members, m)
    assert out[0]["school_ids"] == ["lens-a", "lens-b"]
    assert "school_id" not in out[0]


def test_derive_books_preserves_only_valid_explicit_web_url():
    members = [("b0", _distill("b0")), ("b1", _distill("b1"))]
    warnings = []
    out = bt.derive_books(members, {
        "book_meta": {
            "b0": {"web_url": "/library/work-a.html"},
            "b1": {"web_url": "https://evil.example/book"},
        }
    }, warnings=warnings)
    assert out[0]["web_url"] == "/library/work-a.html"
    assert "web_url" not in out[1]
    assert any("web_url 非法" in item for item in warnings)


@pytest.mark.parametrize("value", [
    " /library/work-a.html", "/library/%252e%252e/private.html",
    "/%252f%252fevil.example/work", "/library\\work-a.html",
])
def test_book_web_url_rejects_ambiguous_or_encoded_unsafe_paths(value):
    assert bt.normalize_web_url(value) is None


def test_resolve_disputes_contradicts_and_stance_pulled():
    out = bt.resolve_disputes(_manual(), _idx_contra(), {"b0", "b1", "b2"}, [])
    assert len(out) == 1
    assert out[0]["index_relation"] == "CONTRADICTS"
    b0 = out[0]["positions"][0]["books"][0]
    assert b0["stance"] == "可训练" and b0["anchor"] == "第1章"   # 立场从 index 摊


def test_resolve_disputes_curated_when_no_index_contradicts():
    m = _manual(disputes=[{"id": "d1", "question": "Q?", "concept": None,
        "positions": [{"label": "L1", "members": [{"slug": "b0", "stance": "s0"}]},
                      {"label": "L2", "members": [{"slug": "b1", "stance": "s1"}]}]}])
    out = bt.resolve_disputes(m, {}, {"b0", "b1", "b2"}, [])
    assert out[0]["index_relation"] == "curated"


def test_resolve_disputes_scientific_layer_normalized_and_sources_filtered():
    m = _manual(disputes=[{
        "id": "d1", "question": "Q?", "concept": None, "question_type": "causal",
        "positions": [
            {"label": "L1", "members": [{"slug": "b0", "stance": "s0"}]},
            {"label": "L2", "members": [{"slug": "b1", "stance": "s1"}]},
        ],
        "adjudication": {
            "status": "mixed", "book_view": "书间观点不同",
            "research_view": "现有研究结果混合", "boundary_conditions": "仅适用于成人样本",
        },
        "sources": [
            "https://example.org/review",
            {"title": "Meta", "url": "https://example.org/meta"},
            "ftp://example.org/bad",
            "https:///missing-host",
        ],
    }])
    w = []
    out = bt.resolve_disputes(m, {}, {"b0", "b1", "b2"}, w)
    assert out[0]["question_type"] == "causal"
    assert out[0]["adjudication"] == {
        "status": "mixed", "book_view": "书间观点不同",
        "research_view": "现有研究结果混合", "boundary_conditions": "仅适用于成人样本",
    }
    assert out[0]["sources"] == [
        "https://example.org/review", {"title": "Meta", "url": "https://example.org/meta"}
    ]
    assert any("ftp" in x or "sources[2]" in x for x in w)
    assert any("sources[3]" in x for x in w)


def test_resolve_disputes_old_string_adjudication_gets_honest_defaults():
    m = _manual(disputes=[{
        "id": "d1", "question": "Q?", "concept": None,
        "positions": [
            {"label": "L1", "members": [{"slug": "b0", "stance": "s0"}]},
            {"label": "L2", "members": [{"slug": "b1", "stance": "s1"}]},
        ],
        "adjudication": "两本书都声称自己更准",
    }])
    out = bt.resolve_disputes(m, {}, {"b0", "b1", "b2"}, [])
    assert out[0]["adjudication"] == {
        "status": "unverified",
        "book_view": "两本书都声称自己更准",
        "research_view": "尚无外部证据裁决",
        "boundary_conditions": "尚未核定",
    }


def test_resolve_disputes_bad_question_type_and_adjudication_warns_and_downgrades():
    m = _manual(disputes=[{
        "id": "d1", "question": "Q?", "concept": None, "question_type": "opinion",
        "positions": [
            {"label": "L1", "members": [{"slug": "b0", "stance": "s0"}]},
            {"label": "L2", "members": [{"slug": "b1", "stance": "s1"}]},
        ],
        "adjudication": {"status": "certain", "book_view": "", "research_view": "r"},
    }])
    w = []
    out = bt.resolve_disputes(m, {}, {"b0", "b1", "b2"}, w)
    assert out[0]["question_type"] is None
    assert out[0]["adjudication"] == {
        "status": "unverified", "book_view": "见上方书间立场",
        "research_view": "r", "boundary_conditions": "尚未核定",
    }
    assert any("question_type" in x for x in w)
    assert any("adjudication.status" in x for x in w)


def test_resolve_disputes_parallel_dropped():
    m = _manual(disputes=[{"id": "d1", "question": "Q?", "concept": None,
        "positions": [{"label": "L1", "members": [{"slug": "b0", "stance": "s0"}]}]}])  # 单派
    w = []
    out = bt.resolve_disputes(m, {}, {"b0", "b1", "b2"}, w)
    assert out == []
    assert any("parallel" in x for x in w)


def test_explicit_parallel_is_routed_out_of_disputes_and_keeps_scientific_fields():
    real = _manual()["disputes"][0]
    parallel = dict(real)
    parallel.update({"id": "p1", "question": "互补问题", "parallel": True, "curated": False})
    m = _manual(disputes=[real, parallel])

    doc, _ = bt.build_topic_json(_members(3), m, {}, _idx_contra())

    assert [d["id"] for d in doc["disputes"]] == ["d1"]
    assert [d["id"] for d in doc["parallel_comparisons"]] == ["p1"]
    comparison = doc["parallel_comparisons"][0]
    assert comparison["index_relation"] == "parallel"
    assert comparison["question_type"] == "causal"
    assert comparison["adjudication"]["research_view"] == "外部结果混合"
    assert comparison["sources"] == ["https://example.org/synthesis"]
    assert doc["_provenance"]["dispute_count"] == 1
    assert doc["_provenance"]["parallel_comparison_count"] == 1


def test_parallel_comparison_without_two_stance_columns_fails_closed():
    m = _manual(disputes=[{
        "id": "p1", "question": "只有一边", "parallel": True,
        "positions": [
            {"label": "有立场", "members": [{"slug": "b0", "stance": "s0"}]},
            {"label": "空立场", "members": [{"slug": "b1"}]},
        ],
    }])
    warnings = []
    out = bt.resolve_parallel_comparisons(m, {}, {"b0", "b1", "b2"}, warnings)
    assert out == []
    assert any("有效立场不足 2 列" in item for item in warnings)


def test_resolve_dimensions_missing_certainty_never_inferred_from_matching_anchor():
    mbs = {"b0": _distill("b0")}   # 即使同 anchor 原项是 book_explicit 也不代填
    m = _manual(dimensions=[{"name": "D", "cells": [{"slug": "b0", "value": "v", "anchor": "第1章"}]}])
    w = []
    out = bt.resolve_dimensions(m, {"b0", "b1", "b2"}, mbs, w)
    assert out[0]["cells"][0]["certainty"] == "unverified"
    assert any("缺 certainty" in x for x in w)


def test_resolve_dimensions_bad_certainty_coerced():
    m = _manual(dimensions=[{"name": "D", "cells": [{"slug": "b0", "value": "v", "certainty": "guess"}]}])
    w = []
    out = bt.resolve_dimensions(m, {"b0", "b1", "b2"}, {"b0": _distill("b0")}, w)
    assert out[0]["cells"][0]["certainty"] == "unverified"
    assert any("certainty" in x for x in w)


def test_resolve_dimensions_missing_or_mismatched_anchor_is_unverified():
    m = _manual(dimensions=[{"name": "D", "cells": [
        {"slug": "b0", "value": "v0"},
        {"slug": "b1", "value": "v1", "certainty": "book_explicit", "anchor": "第99章"},
    ]}])
    w = []
    out = bt.resolve_dimensions(
        m, {"b0", "b1", "b2"}, {"b0": _distill("b0"), "b1": _distill("b1")}, w
    )
    assert [c["certainty"] for c in out[0]["cells"]] == ["unverified", "unverified"]
    assert len([x for x in w if "unverified" in x]) == 2


def test_resolve_schools_member_out_of_set_dropped():
    m = _manual(schools=[{"id": "s1", "name": "派", "members": ["b0", "zzz"], "anchor_book": "b0"}])
    w = []
    out = bt.resolve_schools(m, {"b0", "b1", "b2"}, {"b0": "甲"}, w)
    assert "zzz" not in out[0]["members"]
    assert any("zzz" in x for x in w)


def test_resolve_schools_kind_and_evidence_status_passthrough_and_validate():
    m = _manual(schools=[
        {"id": "s1", "name": "研究传统", "kind": "theoretical", "evidence_status": "mixed",
         "members": ["b0"], "anchor_book": "b0"},
        {"id": "s2", "name": "坏数据", "kind": [], "evidence_status": "certain",
         "members": ["b1"], "anchor_book": "b1"},
    ])
    w = []
    out = bt.resolve_schools(m, {"b0", "b1", "b2"}, {"b0": "甲", "b1": "乙"}, w)
    assert out[0]["kind"] == "theoretical" and out[0]["evidence_status"] == "mixed"
    assert out[1]["kind"] is None and out[1]["evidence_status"] is None
    assert any("kind" in x for x in w) and any("evidence_status" in x for x in w)


def test_build_topic_json_shape_and_provenance():
    doc, w = bt.build_topic_json(_members(3), _manual(), {}, _idx_contra())
    assert doc["_provenance"]["member_count"] == 3
    assert doc["_provenance"]["school_count"] == 2
    assert doc["_provenance"]["dispute_count"] == 1
    assert len(doc["books"]) == 3
    assert "parallel_comparisons" not in doc  # 旧 topic 未声明新 schema 时语义零变化


def test_topic_template_routes_all_book_links_and_separates_parallel_cards():
    html = (Path(__file__).parents[2] / "templates" / "topic-page-skeleton.html").read_text(
        encoding="utf-8"
    )
    assert "book.web_url" in html
    assert 'id="parallels-host"' in html
    assert "function renderParallels()" in html
    assert "class: 'cmp-card'" in html


def test_topic_template_browser_smoke_renders_one_dispute_three_parallel_and_routes():
    from playwright.sync_api import sync_playwright

    path = Path(__file__).parents[2] / "templates" / "topic-page-skeleton.html"
    html = path.read_text(encoding="utf-8")
    match = re.search(
        r'(<script type="application/json" id="topic-data">)\s*(.*?)\s*(</script>)',
        html, re.S,
    )
    fixture = json.loads(match.group(2))
    slug = fixture["books"][0]["slug"]
    fixture["books"][0]["web_url"] = "/library/work-a.html"
    fixture["books"][1]["web_url"] = "//evil.example/work-b.html"
    real = fixture["disputes"][0]
    fixture["disputes"] = [real]
    fixture["parallel_comparisons"] = []
    for i in range(3):
        comparison = json.loads(json.dumps(real, ensure_ascii=False))
        comparison.update({"id": f"p{i + 1}", "question": f"平行对照 {i + 1}",
                           "index_relation": "parallel"})
        fixture["parallel_comparisons"].append(comparison)
    rendered = html[:match.start()] + match.group(1) + "\n" + json.dumps(
        fixture, ensure_ascii=False
    ) + "\n" + match.group(3) + html[match.end():]

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_content(rendered)
        page.wait_for_function("window.__topicReady === true")
        assert page.locator(".dsp-card").count() == 1
        assert page.locator(".cmp-card").count() == 3
        layer_titles = page.locator(".dsp-card .dsp-layer-title").all_text_contents()
        assert layer_titles == ["原书怎么说", "外部研究怎么说", "适用边界与风险"]
        assert page.locator('a[href="/library/work-a.html"]').count() > 0
        assert page.locator(f'a[href="../{slug}/{slug}.html"]').count() == 0
        assert page.locator('a[href^="//evil.example/"]').count() == 0
        browser.close()


def test_build_topic_rejects_duplicate_school_ids_before_derivation():
    m = _manual()
    m["schools"].append({"id": "s1", "name": "重名派", "members": ["b2"]})
    with pytest.raises(ValueError, match="id 's1' 重复"):
        bt.build_topic_json(_members(3), m, {}, _idx_contra())


@pytest.mark.parametrize("book_meta,needle", [
    ({"b0": {"school_ids": ["ghost"]}}, "不存在的 school 'ghost'"),
    ({"b0": {"school_ids": ["s1", "s1"]}}, "重复引用"),
])
def test_build_topic_rejects_orphan_or_duplicate_book_school_refs(book_meta, needle):
    m = _manual(book_meta=book_meta)
    with pytest.raises(ValueError, match=needle):
        bt.build_topic_json(_members(3), m, {}, _idx_contra())


@pytest.mark.parametrize("members,anchor,needle", [
    (["b0", "ghost"], "b0", "引用非成员 slug 'ghost'"),
    (["b0", "b0"], "b0", "重复成员 'b0'"),
    (["b0"], "b1", "未包含在该 school.members/book_meta 引用中"),
])
def test_build_topic_rejects_orphan_duplicate_or_detached_school_members(members, anchor, needle):
    m = _manual(schools=[{
        "id": "s1", "name": "派一", "kind": "applied", "evidence_status": "mixed",
        "members": members, "anchor_book": anchor,
    }])
    with pytest.raises(ValueError, match=needle):
        bt.build_topic_json(_members(3), m, {}, _idx_contra())


# ---------------------------------------------------------------- main 集成(门槛 / 防覆盖)
def _write_distill(root, slug):
    d = root / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "distill.json").write_text(json.dumps(_distill(slug), ensure_ascii=False), encoding="utf-8")


def test_collect_members_fails_closed_for_missing_or_mismatched_explicit_member(tmp_path):
    _write_distill(tmp_path, "b0")
    with pytest.raises(ValueError, match="成员 b1 .*缺失"):
        bt.collect_members({"members": ["b0", "b1"]}, tmp_path, [])

    wrong_dir = tmp_path / "b1"
    wrong_dir.mkdir()
    (wrong_dir / "distill.json").write_text(
        json.dumps(_distill("other"), ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="distill.slug='other' 不一致"):
        bt.collect_members({"members": ["b0", "b1"]}, tmp_path, [])


def test_collect_members_fails_closed_for_corrupt_json(tmp_path):
    folder = tmp_path / "b0"
    folder.mkdir()
    (folder / "distill.json").write_text("{broken", encoding="utf-8")

    with pytest.raises(ValueError, match="成员 b0 .*解析失败"):
        bt.collect_members({"members": ["b0"]}, tmp_path, [])


@pytest.mark.parametrize("bad", ["../b1", "b1/child", " b1", 7, None])
def test_collect_members_rejects_unsafe_explicit_slug(tmp_path, bad):
    with pytest.raises(ValueError, match="非法 slug"):
        bt.collect_members({"members": [bad]}, tmp_path, [])


def test_main_under_3_members_exit3(tmp_path, monkeypatch):
    for s in ("b0", "b1"):
        _write_distill(tmp_path, s)
    manual = tmp_path / "topic.manual.json"
    manual.write_text(json.dumps({"topic": "T", "slug": "t", "members": ["b0", "b1"]}, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "topic.json"
    monkeypatch.setattr(sys, "argv", ["build_topic.py", "--topic", "T", "--data-root", str(tmp_path),
                                      "--manual", str(manual), "--out", str(out)])
    assert bt.main() == 3


def test_main_full_run_then_anti_overwrite(tmp_path, monkeypatch):
    for s in ("b0", "b1", "b2"):
        _write_distill(tmp_path, s)
    manual = tmp_path / "topic.manual.json"
    manual.write_text(json.dumps(_manual(), ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "topic.json"
    monkeypatch.setattr(sys, "argv", ["build_topic.py", "--topic", "T", "--data-root", str(tmp_path),
                                      "--manual", str(manual), "--out", str(out)])
    assert bt.main() == 0
    assert out.exists()
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["_provenance"]["member_count"] == 3
    # 防覆盖:out 存在 + manual 缺失 + 无 --force → exit 2
    manual.unlink()
    monkeypatch.setattr(sys, "argv", ["build_topic.py", "--data-root", str(tmp_path), "--out", str(out)])
    assert bt.main() == 2

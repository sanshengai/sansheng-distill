"""build_author.py 新聚合契约：显式成员、精确母题、合著限定与站内深链。"""
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import build_author as ba


def _distill(slug, author, year, concepts=None, **over):
    data = {
        "slug": slug,
        "title": slug.upper(),
        "author": author,
        "book_type": "论说",
        "pub_year": year,
        "core_question": "人如何判断",
        "concepts": concepts or [],
        "core_ideas": [],
        "mental_models": [],
    }
    data.update(over)
    return data


def _write_distill(root, data):
    folder = root / data["slug"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "distill.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )


def test_collect_explicit_member_slugs_includes_coauthor_and_excludes_stray(tmp_path):
    solo = _distill("work-a", "作者甲", 2011)
    coauthored = _distill("work-b", "作者甲、合著者乙", 2021)
    stray = _distill("work-c", "作者甲", 2015)
    for data in (solo, coauthored, stray):
        _write_distill(tmp_path, data)
    args = SimpleNamespace(inputs=None, author="作者甲", data_root=str(tmp_path))

    explicit = ba.collect_distills(args, {"member_slugs": ["work-a", "work-b"]}, [])
    legacy = ba.collect_distills(args, {}, [])

    assert [d["slug"] for d in explicit] == ["work-a", "work-b"]
    assert [d["slug"] for d in legacy] == ["work-a", "work-c"]


@pytest.mark.parametrize("bad", ["../work-b", "work-b/child", " work-b", 7, None])
def test_collect_explicit_member_slugs_rejects_unsafe_values(tmp_path, bad):
    args = SimpleNamespace(inputs=None, author="作者甲", data_root=str(tmp_path))
    with pytest.raises(ValueError, match="非法 slug"):
        ba.collect_distills(args, {"member_slugs": [bad]}, [])


def test_collect_explicit_member_slugs_fails_closed_for_missing_or_mismatch(tmp_path):
    args = SimpleNamespace(inputs=None, author="作者甲", data_root=str(tmp_path))
    with pytest.raises(ValueError, match="成员 work-a .*缺失"):
        ba.collect_distills(args, {"member_slugs": ["work-a"]}, [])

    _write_distill(tmp_path, _distill("other-work", "作者甲", 2011))
    expected_dir = tmp_path / "work-a"
    expected_dir.mkdir()
    (expected_dir / "distill.json").write_text(
        json.dumps(_distill("other-work", "作者甲", 2011), ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="distill.slug='other-work' 不一致"):
        ba.collect_distills(args, {"member_slugs": ["work-a"]}, [])


def test_collect_explicit_member_slugs_fails_closed_for_corrupt_json(tmp_path):
    folder = tmp_path / "work-a"
    folder.mkdir()
    (folder / "distill.json").write_text("{broken", encoding="utf-8")
    args = SimpleNamespace(inputs=None, author="作者甲", data_root=str(tmp_path))

    with pytest.raises(ValueError, match="成员 work-a .*解析失败"):
        ba.collect_distills(args, {"member_slugs": ["work-a"]}, [])


def test_partial_index_is_completed_only_by_manual_exact_concepts_and_keeps_edge_note(tmp_path):
    books = [
        _distill("work-a", "作者甲", 2011, [
            {"concept": "概念甲", "one_liner": "第一种解释", "stance": "立场甲"},
            {"concept": "概念乙", "one_liner": "第二种解释", "stance": "立场乙"},
        ]),
        _distill("work-b", "作者甲、合著者乙", 2021, [
            {"concept": "概念丙", "one_liner": "第三种解释", "stance": "立场丙"},
            {"concept": "概念丁", "one_liner": "第四种解释", "stance": "立场丁"},
        ]),
    ]
    index = tmp_path / "knowledge-index.json"
    index.write_text(json.dumps({"concepts": [{
        "concept": "概念甲", "one_liner": "第一种解释",
        "entries": [{"book_slug": "work-a", "stance": "立场甲"}],
    }]}, ensure_ascii=False), encoding="utf-8")
    note = "《作品乙》是合著，不能把全部观点归为作者甲个人。"
    manual = {
        "author": "作者甲", "slug": "author-a", "member_slugs": ["work-a", "work-b"],
        "motif_groups": [{
            "label": "母题甲", "statement": "从解释甲到解释丙",
            "concepts": ["概念甲", "概念丙"],
        }],
        "derive_edges": [{"from": "概念甲", "to": "概念丙", "label": "关系甲", "note": note}],
        "period_names": {"p1": "时期"}, "bio": {"background": "背景"},
        "core_sentence": "一句话", "evolution_summary": "连续扩展",
        "evolution_verdict": {"stance": "continuous", "headline": "连续"},
    }

    doc, _ = ba.build_author_json(books, manual, {}, index_path=index)

    assert doc["author"] == "作者甲"
    assert [m["label"] for m in doc["motifs"]] == ["母题甲"]
    assert [a["slug"] for a in doc["motifs"][0]["appears_in"]] == ["work-a", "work-b"]
    derive = [e for e in doc["concept_graph"]["edges"] if e["type"] == "derive"]
    assert len(derive) == 1 and derive[0]["note"] == note

    # index 后续补齐新书时，显式母题的落地结果保持一致。
    index.write_text(json.dumps({"concepts": [
        {
            "concept": "概念甲", "one_liner": "第一种解释",
            "entries": [{"book_slug": "work-a", "stance": "立场甲"}],
        },
        {
            "concept": "概念丙", "one_liner": "第三种解释",
            "entries": [{"book_slug": "work-b", "stance": "立场丙"}],
        },
    ]}, ensure_ascii=False), encoding="utf-8")
    completed, _ = ba.build_author_json(books, manual, {}, index_path=index)
    assert completed["motifs"] == doc["motifs"]
    assert [e["note"] for e in completed["concept_graph"]["edges"] if e["type"] == "derive"] == [note]


def test_explicit_motif_groups_fail_closed_without_exact_cross_book_hits():
    books = [
        _distill("a", "A", 2000, [], core_ideas=[{"idea": "相似母题", "primary": True}]),
        _distill("b", "A、B", 2001, [], core_ideas=[{"idea": "相似母题", "primary": True}]),
    ]
    manual = {
        "member_slugs": ["a", "b"],
        "motif_groups": [{"label": "人工母题", "concepts": ["不存在的概念"]}],
    }
    warnings = []
    exact = ba.merge_manual_exact_concepts(books, manual, None)

    assert ba.derive_motifs(books, manual, exact, warnings) == []
    assert any("未做模糊补齐" in item for item in warnings)


def test_book_web_url_is_conditional_and_fail_closed():
    books = [_distill("a", "A", 2000), _distill("b", "A", 2001)]
    warnings = []
    out = ba.build_books(books, {}, {
        "book_meta": {
            "a": {"web_url": "/library/work-a.html"},
            "b": {"web_url": "https://evil.example/book"},
        }
    }, warnings)

    assert out[0]["web_url"] == "/library/work-a.html"
    assert "web_url" not in out[1]
    assert any("web_url 非法" in item for item in warnings)


@pytest.mark.parametrize("value", [
    " /library/work-a.html", "/library/%252e%252e/private.html",
    "/%252f%252fevil.example/work", "/library\\work-a.html",
])
def test_book_web_url_rejects_ambiguous_or_encoded_unsafe_paths(value):
    assert ba.normalize_web_url(value) is None


def test_author_template_uses_explicit_routes_and_renders_derive_notes():
    html = (Path(__file__).parents[2] / "templates" / "author-page-skeleton.html").read_text(
        encoding="utf-8"
    )
    assert "book.web_url" in html
    assert 'id="dag-notes"' in html
    assert "e.type === 'derive' && e.note" in html


def test_author_template_browser_smoke_shows_note_and_routes_every_link():
    from playwright.sync_api import sync_playwright

    path = Path(__file__).parents[2] / "templates" / "author-page-skeleton.html"
    html = path.read_text(encoding="utf-8")
    match = re.search(
        r'(<script type="application/json" id="author-data">)\s*(.*?)\s*(</script>)',
        html, re.S,
    )
    fixture = json.loads(match.group(2))
    slug = fixture["books"][0]["slug"]
    fixture["books"][0]["web_url"] = "/library/work-a.html"
    fixture["books"][1]["web_url"] = "//evil.example/work-b.html"
    derive = next(edge for edge in fixture["concept_graph"]["edges"] if edge["type"] == "derive")
    derive["note"] = "合著限定必须完整显示。"
    rendered = html[:match.start()] + match.group(1) + "\n" + json.dumps(
        fixture, ensure_ascii=False
    ) + "\n" + match.group(3) + html[match.end():]

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_content(rendered)
        page.wait_for_function("window.__authorReady === true")
        assert page.locator(".dag-note", has_text="合著限定必须完整显示").is_visible()
        assert page.locator('a[href="/library/work-a.html"]').count() > 0
        assert page.locator(f'a[href="../{slug}/{slug}.html"]').count() == 0
        assert page.locator('a[href^="//evil.example/"]').count() == 0
        browser.close()

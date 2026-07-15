"""build_topic.py 聚合器单测:确定性派生 / index_relation 三档 / certainty 校验 / 门槛 / 防覆盖。"""
import sys
import json
from pathlib import Path
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
         "schools": [{"id": "s1", "name": "派一", "members": ["b0"], "anchor_book": "b0"},
                     {"id": "s2", "name": "派二", "members": ["b1", "b2"], "anchor_book": "b1"}],
         "disputes": [{"id": "d1", "question": "Q?", "concept": "C",
                       "positions": [{"label": "L1", "members": ["b0"]},
                                     {"label": "L2", "members": ["b1"]}]}],
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
    assert out[0]["school_id"] == "s1"           # 从 schools 反推
    assert out[0]["one_liner"] == "L0"           # 缺 book_meta 回退 napkin


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


def test_resolve_disputes_parallel_dropped():
    m = _manual(disputes=[{"id": "d1", "question": "Q?", "concept": None,
        "positions": [{"label": "L1", "members": [{"slug": "b0", "stance": "s0"}]}]}])  # 单派
    w = []
    out = bt.resolve_disputes(m, {}, {"b0", "b1", "b2"}, w)
    assert out == []
    assert any("parallel" in x for x in w)


def test_resolve_dimensions_certainty_default_pull():
    mbs = {"b0": _distill("b0")}   # 全 book_explicit
    m = _manual(dimensions=[{"name": "D", "cells": [{"slug": "b0", "value": "v", "anchor": "第1章"}]}])
    out = bt.resolve_dimensions(m, {"b0", "b1", "b2"}, mbs, [])
    assert out[0]["cells"][0]["certainty"] == "book_explicit"


def test_resolve_dimensions_bad_certainty_coerced():
    m = _manual(dimensions=[{"name": "D", "cells": [{"slug": "b0", "value": "v", "certainty": "guess"}]}])
    w = []
    out = bt.resolve_dimensions(m, {"b0", "b1", "b2"}, {"b0": _distill("b0")}, w)
    assert out[0]["cells"][0]["certainty"] == "book_explicit"
    assert any("certainty" in x for x in w)


def test_resolve_schools_member_out_of_set_dropped():
    m = _manual(schools=[{"id": "s1", "name": "派", "members": ["b0", "zzz"], "anchor_book": "b0"}])
    w = []
    out = bt.resolve_schools(m, {"b0", "b1", "b2"}, {"b0": "甲"}, w)
    assert "zzz" not in out[0]["members"]
    assert any("zzz" in x for x in w)


def test_build_topic_json_shape_and_provenance():
    doc, w = bt.build_topic_json(_members(3), _manual(), {}, _idx_contra())
    assert doc["_provenance"]["member_count"] == 3
    assert doc["_provenance"]["school_count"] == 2
    assert doc["_provenance"]["dispute_count"] == 1
    assert len(doc["books"]) == 3


# ---------------------------------------------------------------- main 集成(门槛 / 防覆盖)
def _write_distill(root, slug):
    d = root / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "distill.json").write_text(json.dumps(_distill(slug), ensure_ascii=False), encoding="utf-8")


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

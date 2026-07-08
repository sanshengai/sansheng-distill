import json, subprocess, sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "update_index.py"

def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, encoding="utf-8")

def w(p, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")

def entry(slug="b1", **kw):
    e = {"book_slug": slug, "book_title": "书一", "stance": "支持",
         "anchor": "第1章", "quote": "…"}
    e.update(kw); return e

def test_query_missing_index_returns_empty(tmp_path):
    r = run("query", "--index", str(tmp_path / "idx.json"))
    assert r.returncode == 0
    assert json.loads(r.stdout) == {"version": 1, "concepts": []}

def test_register_new_concept(tmp_path):
    idx = tmp_path / "idx.json"; mg = tmp_path / "m.json"
    w(mg, [{"concept": "安全边际", "relation": "NEW_CONCEPT",
            "one_liner": "留出犯错余量", "entry": entry()}])
    r = run("register", "--index", str(idx), "--merge", str(mg))
    assert r.returncode == 0
    data = json.loads(idx.read_text(encoding="utf-8"))
    assert data["concepts"][0]["concept"] == "安全边际"
    assert data["concepts"][0]["entries"][0]["relation"] == "NEW_CONCEPT"

def test_supports_appends_to_existing(tmp_path):
    idx = tmp_path / "idx.json"; mg = tmp_path / "m.json"
    w(idx, {"version": 1, "concepts": [{"concept": "安全边际", "one_liner": "x",
            "entries": [dict(entry(), relation="NEW_CONCEPT")]}]})
    w(mg, [{"concept": "安全边际", "relation": "SUPPORTS", "entry": entry(slug="b2")}])
    r = run("register", "--index", str(idx), "--merge", str(mg))
    assert r.returncode == 0
    data = json.loads(idx.read_text(encoding="utf-8"))
    assert len(data["concepts"][0]["entries"]) == 2

def test_bad_relation_rejected(tmp_path):
    idx = tmp_path / "idx.json"; mg = tmp_path / "m.json"
    w(mg, [{"concept": "X", "relation": "AGREES", "entry": entry()}])
    r = run("register", "--index", str(idx), "--merge", str(mg))
    assert r.returncode == 1 and "relation" in r.stderr

def test_new_concept_name_clash_rejected(tmp_path):
    idx = tmp_path / "idx.json"; mg = tmp_path / "m.json"
    w(idx, {"version": 1, "concepts": [{"concept": "复利", "one_liner": "", "entries": [dict(entry(), relation="NEW_CONCEPT")]}]})
    w(mg, [{"concept": "复利", "relation": "NEW_CONCEPT", "one_liner": "", "entry": entry(slug="b2")}])
    assert run("register", "--index", str(idx), "--merge", str(mg)).returncode == 1

def test_non_new_on_missing_concept_rejected(tmp_path):
    idx = tmp_path / "idx.json"; mg = tmp_path / "m.json"
    w(mg, [{"concept": "不存在", "relation": "REFINES", "entry": entry()}])
    assert run("register", "--index", str(idx), "--merge", str(mg)).returncode == 1

def test_same_book_needs_force_and_is_idempotent(tmp_path):
    idx = tmp_path / "idx.json"; mg = tmp_path / "m.json"
    w(idx, {"version": 1, "concepts": [{"concept": "复利", "one_liner": "",
            "entries": [dict(entry(), relation="NEW_CONCEPT", stance="旧立场")]}]})
    w(mg, [{"concept": "复利", "relation": "REFINES", "entry": entry(stance="新立场")}])
    assert run("register", "--index", str(idx), "--merge", str(mg)).returncode == 2  # 同书 b1 再登记
    r = run("register", "--index", str(idx), "--merge", str(mg), "--force")
    assert r.returncode == 0
    data = json.loads(idx.read_text(encoding="utf-8"))
    ents = data["concepts"][0]["entries"]
    assert len(ents) == 1 and ents[0]["stance"] == "新立场"  # 覆盖而非累加

def test_dry_run_writes_nothing(tmp_path):
    idx = tmp_path / "idx.json"; mg = tmp_path / "m.json"
    w(mg, [{"concept": "X", "relation": "NEW_CONCEPT", "one_liner": "", "entry": entry()}])
    r = run("register", "--index", str(idx), "--merge", str(mg), "--dry-run")
    assert r.returncode == 0 and not idx.exists()

def test_register_creates_bak(tmp_path):
    idx = tmp_path / "idx.json"; mg = tmp_path / "m.json"
    w(idx, {"version": 1, "concepts": []})
    w(mg, [{"concept": "X", "relation": "NEW_CONCEPT", "one_liner": "", "entry": entry()}])
    assert run("register", "--index", str(idx), "--merge", str(mg)).returncode == 0
    assert (tmp_path / "idx.json.bak").exists()

def test_register_video_source_type(tmp_path):
    idx = tmp_path / "idx.json"; mg = tmp_path / "m.json"
    w(mg, [{"concept": "刻意练习", "relation": "NEW_CONCEPT", "one_liner": "",
            "entry": entry(source_type="video_series")}])
    r = run("register", "--index", str(idx), "--merge", str(mg))
    assert r.returncode == 0
    data = json.loads(idx.read_text(encoding="utf-8"))
    assert data["concepts"][0]["entries"][0]["source_type"] == "video_series"

def test_backward_compat_no_source_type(tmp_path):
    idx = tmp_path / "idx.json"; mg = tmp_path / "m.json"
    # 老格式索引:已有概念,其 entry 无 source_type 字段
    w(idx, {"version": 1, "concepts": [{"concept": "安全边际", "one_liner": "x",
            "entries": [dict(entry(), relation="NEW_CONCEPT")]}]})
    # register 一个也不带 source_type 的 SUPPORTS(新书 slug,追加而非覆盖)
    w(mg, [{"concept": "安全边际", "relation": "SUPPORTS", "entry": entry(slug="b2")}])
    r = run("register", "--index", str(idx), "--merge", str(mg))
    assert r.returncode == 0
    data = json.loads(idx.read_text(encoding="utf-8"))
    ents = {e["book_slug"]: e for e in data["concepts"][0]["entries"]}
    assert "source_type" not in ents["b1"]  # 老 entry 不被强改
    assert "source_type" not in ents["b2"]  # 新 entry 缺省也不写

def test_illegal_source_type_exit1(tmp_path):
    idx = tmp_path / "idx.json"; mg = tmp_path / "m.json"
    w(mg, [{"concept": "X", "relation": "NEW_CONCEPT", "one_liner": "",
            "entry": entry(source_type="podcast")}])
    r = run("register", "--index", str(idx), "--merge", str(mg))
    assert r.returncode == 1 and "source_type" in r.stderr

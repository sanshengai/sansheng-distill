"""jev_merge_claims / jev_support_check：阈值边界、字面预合并、baseline 对照、fail-open、不许直连、不改产物。全部离线。"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(REPO / "_ops" / "jev"))
import jev_merge_claims as jm  # noqa: E402
import jev_support_check as js  # noqa: E402
client_available = (REPO / "_ops" / "jev" / "client.py").exists()
if client_available:
    import client as jc  # noqa: E402

CLAIMS = [
    {"claim_id": "c1", "theme_id": "T1", "text_zh": "教育是资产投资，价值等于目标收入与当前收入的差额"},
    {"claim_id": "c2", "theme_id": "T1", "text_zh": "教育是一种资产投资，其价值等于目标收入与当前收入的差额，而不是看学费金额"},
    {"claim_id": "c3", "theme_id": "T1", "text_zh": "花五万美元学一门年入百万的技能，每推迟一年损失九十五万"},
    {"claim_id": "c4", "theme_id": "T1", "text_zh": "健身房低价引流活动六周内无法带来净增长"},
    {"claim_id": "c5", "theme_id": "T2", "text_zh": "教育是资产投资，价值等于目标收入与当前收入的差额"},
]
FAMILIES = [{"family_id": "F1", "claim_ids": ["c1", "c2", "c3"]}, {"family_id": "F2", "claim_ids": ["c4"]}, {"family_id": "F3", "claim_ids": ["c5"]}]


def _client(monkeypatch, tmp_path, site, ask):
    monkeypatch.setenv("JEV_LEDGER_DIR", str(tmp_path / "ledger"))
    monkeypatch.setenv("JEV_ENV_FILE", str(tmp_path / "no.env"))
    monkeypatch.setenv("TYPESAFE_API_KEY", "k")
    jev = jc.JevClient(site)
    monkeypatch.setattr(jev, "ask", ask)
    return jev


def _ledger(tmp_path, site):
    return [json.loads(l) for l in next((tmp_path / "ledger").glob(f"*/{site}.jsonl")).read_text().splitlines()]


# ---------- merge ----------
@pytest.mark.parametrize("noul,expected", [(0.69, False), (0.70, True), (0.95, True), (0.5, False)])
def test_merge_noul_boundary(noul, expected):
    assert jm.is_same(noul) is expected


def test_lexical_pass_premerges_and_keeps_gray_within_theme():
    groups, gray = jm.lexical_pass(CLAIMS, premerge=0.5, min_dice=0.05)
    assert groups == [["c1", "c2"]]                       # 近乎逐字 → 字面族
    assert all(a != "c5" and b != "c5" for _, a, b in gray)  # c5 与 c1 逐字相同但跨主题：不配对
    assert all(d < 0.5 for d, _, _ in gray) and gray == sorted(gray, key=lambda t: -t[0])


def test_baseline_from_families_and_lexical():
    idx = jm.family_index(FAMILIES)
    assert jm.baseline_of("c1", "c3", idx) == "same" and jm.baseline_of("c1", "c4", idx) == "different"
    assert jm.baseline_of("c1", "zz", idx) == "unknown" and jm.baseline_of("c1", "c3", None) == "different"


def test_select_pairs_balanced_and_capped():
    gray = [(0.3, "c1", "c3"), (0.2, "c1", "c4"), (0.15, "c2", "c4"), (0.1, "c3", "c4")]
    picked = jm.select_pairs(gray, max_pairs=2, sample="balanced", fam_idx=jm.family_index(FAMILIES))
    assert len(picked) == 2 and {jm.baseline_of(a, b, jm.family_index(FAMILIES)) for _, a, b in picked} == {"same", "different"}
    assert jm.select_pairs(gray, max_pairs=3, sample="top", fam_idx=None) == gray[:3]


@pytest.mark.skipif(not client_available, reason="接入层不在本仓（独立仓单跑）")
def test_merge_run_shadow_logs_and_suggests(monkeypatch, tmp_path):
    nouls = {("c1", "c3"): 0.2, ("c2", "c3"): 0.3, ("c1", "c4"): 0.05, ("c2", "c4"): 0.05, ("c3", "c4"): 0.9}
    def ask(**kw):
        return jc.JevResult(ok=True, mode="shadow", answers={"same_claim": {"noul": nouls[(kw["meta"]["a"], kw["meta"]["b"])]}}, input_tokens=60)
    jev = _client(monkeypatch, tmp_path, jm.SITE_ID, ask)
    doc = jm.run(CLAIMS, jev, families=FAMILIES, premerge=0.5, min_dice=0.0, max_pairs=10, concurrency=2)
    assert doc["lexical_families"] == [["c1", "c2"]] and doc["asked"] == 5 and doc["errors"] == 0
    assert doc["jev_same"] == 1 and doc["suggested_families"] == [["c1", "c2"], ["c3", "c4"]]
    # baseline 对照：c1/c3、c2/c3 Gemini 同族但 Jev 判不同 → 分歧 2；c3/c4 异族 Jev 判同 → 分歧 1；两条一致
    assert doc["baseline_pairs"] == 5 and doc["agree_with_baseline"] == 2
    rows = _ledger(tmp_path, jm.SITE_ID)
    assert len(rows) == 5 and all({"baseline", "jev"} <= set(r["meta"]) for r in rows)
    c34 = next(r for r in rows if r["meta"]["a"] == "c3" and r["meta"]["b"] == "c4")["meta"]
    assert (c34["baseline"], c34["jev"]) == ("different", "same")


@pytest.mark.skipif(not client_available, reason="接入层不在本仓（独立仓单跑）")
def test_merge_run_call_errors_counted_not_raised(monkeypatch, tmp_path):
    jev = _client(monkeypatch, tmp_path, jm.SITE_ID, lambda **kw: jc.JevResult(ok=False, mode="shadow", error="HTTP 500"))
    doc = jm.run(CLAIMS, jev, premerge=0.5, min_dice=0.0, max_pairs=10)
    assert doc["errors"] == 5 and doc["asked"] == 0 and doc["suggested_families"] == [["c1", "c2"]]  # 字面族仍在，Jev 一条没加


def test_merge_cli_fail_open_without_key_writes_nothing(tmp_path):
    claims = tmp_path / "claims.jsonl"; claims.write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in CLAIMS), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("TYPESAFE_API_KEY")}
    env.update(JEV_ENV_FILE=str(tmp_path / "no.env"), JEV_LEDGER_DIR=str(tmp_path / "ledger"))
    out = tmp_path / "suggest.json"
    proc = subprocess.run([sys.executable, str(SCRIPTS / "jev_merge_claims.py"), "--claims", str(claims), "--out", str(out)], env=env, capture_output=True, text=True)
    assert proc.returncode == 0 and ("无 key" in proc.stdout or "缺失" in proc.stdout) and not out.exists()
    assert claims.read_text(encoding="utf-8").count("\n") == len(CLAIMS) - 1  # 输入产物一字未动


# ---------- support ----------
RECORDS = [
    {"id": "r1", "facet": "claim", "source_excerpt": "系统1和系统2只是我杜撰出来的角色", "assertion": "系统1和系统2是作者明确声明杜撰的虚构框架", "support": "direct"},
    {"id": "r2", "facet": "number", "source_excerpt": "依次出生的4个婴儿", "assertion": "连续出生六个婴儿", "support": "partial"},
    {"id": "r3", "facet": "claim", "source_excerpt": "自我损耗能通过注射葡萄糖缓解", "assertion": "葡萄糖对自我损耗没有作用", "support": "direct"},
    {"id": "r4", "facet": "verbatim", "source_excerpt": "原话", "assertion": "原话", "support": "direct"},
]
AUDIT_FLAG = {"id": "af1", "facet": "claim", "target": {"kind": "audit_flag", "id": "g1:x"}, "source_excerpt": "原文", "assertion": "需外证复核", "support": "direct"}


def test_select_records_keeps_minority_first_and_filters_facet():
    picked = js.select_records(RECORDS, max_n=2, facet=None)
    ids = [r["id"] for r in picked]
    assert len(ids) == 2 and "r2" in ids and ids == sorted(ids, key=lambda i: int(i[1:]))  # 少数类必入选，保持原序
    assert [r["id"] for r in js.select_records(RECORDS, max_n=10, facet="claim")] == ["r1", "r3"]
    assert js.select_records(RECORDS, max_n=1, facet="verbatim") == [RECORDS[3]]
    assert AUDIT_FLAG not in js.select_records(RECORDS + [AUDIT_FLAG], max_n=10, facet=None)                              # 审计备注默认跳过
    assert AUDIT_FLAG in js.select_records(RECORDS + [AUDIT_FLAG], max_n=10, facet=None, include_audit_flags=True)  # 显式要才核


@pytest.mark.skipif(not client_available, reason="接入层不在本仓（独立仓单跑）")
def test_support_run_confusion_and_disagreements(monkeypatch, tmp_path):
    answers = {"r1": "direct", "r2": "partial", "r3": "contradicted", "r4": "bogus"}
    def ask(**kw):
        c = answers[kw["meta"]["id"]]
        return jc.JevResult(ok=True, mode="shadow", answers={"support": {"choice": c, "confidence": 0.8, "probabilities": {c: 0.8}}}, input_tokens=40)
    jev = _client(monkeypatch, tmp_path, js.SITE_ID, ask)
    doc = js.run(RECORDS, jev, concurrency=2)
    assert doc["asked"] == 3 and doc["errors"] == 1 and doc["agree_with_baseline"] == 2
    assert doc["confusion_baseline_x_jev"]["direct"]["contradicted"] == 1
    assert [d["id"] for d in doc["disagreements"]] == ["r3"]
    rows = _ledger(tmp_path, js.SITE_ID)
    assert len(rows) == 4 and {r["meta"]["jev"] for r in rows} == {"direct", "partial", "contradicted", "invalid"}
    assert all(r["meta"]["baseline"] in js.SUPPORT_LEVELS for r in rows)


def test_support_cli_fail_open_without_key_does_not_touch_audit(tmp_path):
    audit = tmp_path / "source-audit.json"
    audit.write_text(json.dumps({"schema_version": "psychology-source-audit-v1", "records": RECORDS}, ensure_ascii=False), encoding="utf-8")
    before = audit.read_bytes()
    env = {k: v for k, v in os.environ.items() if not k.startswith("TYPESAFE_API_KEY")}
    env.update(JEV_ENV_FILE=str(tmp_path / "no.env"), JEV_LEDGER_DIR=str(tmp_path / "ledger"))
    out = tmp_path / "check.json"
    proc = subprocess.run([sys.executable, str(SCRIPTS / "jev_support_check.py"), "--audit", str(audit), "--out", str(out)], env=env, capture_output=True, text=True)
    assert proc.returncode == 0 and not out.exists() and audit.read_bytes() == before


def test_no_direct_api_calls_outside_client():
    for name in ("jev_merge_claims.py", "jev_support_check.py"):
        src = (SCRIPTS / name).read_text(encoding="utf-8")
        assert "typesafe.ai" not in src and "urllib" not in src, name

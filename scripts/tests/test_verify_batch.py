"""verify_batch 项目级参数传播回归。"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))
import verify_batch as vb


def _artifacts(root: Path, slug: str):
    book = root / slug
    book.mkdir()
    (book / "distill.json").write_text(
        json.dumps({"slug": slug, "chapters": []}, ensure_ascii=False), encoding="utf-8"
    )
    (book / f"{slug}.html").write_text('<html lang="zh"></html>', encoding="utf-8")


def test_check_one_default_keeps_legacy_command_and_psychology_propagates(tmp_path, monkeypatch):
    _artifacts(tmp_path, "legacy-book")
    commands = []

    def fake_run(cmd, **kwargs):
        commands.append(cmd)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(vb.subprocess, "run", fake_run)
    assert vb.check_one(tmp_path, "legacy-book", fast=True)["ok"]
    assert "--require-domain" not in commands[-1]
    assert "--source" not in commands[-1]

    (tmp_path / "legacy-book" / "book.txt").write_text("原书正文", encoding="utf-8")
    (tmp_path / "legacy-book" / "source-audit.json").write_text("{}", encoding="utf-8")
    assert vb.check_one(tmp_path, "legacy-book", fast=True, required_domain="psychology")["ok"]
    index = commands[-1].index("--require-domain")
    assert commands[-1][index:index + 2] == ["--require-domain", "psychology"]
    source_index = commands[-1].index("--source")
    assert commands[-1][source_index:source_index + 2] == [
        "--source", str(tmp_path / "legacy-book" / "book.txt")
    ]


def test_strict_batch_requires_book_text_before_invoking_verifier(tmp_path, monkeypatch):
    _artifacts(tmp_path, "missing-source")

    def must_not_run(*args, **kwargs):
        raise AssertionError("缺 book.txt 时不应调起 verify_page")

    monkeypatch.setattr(vb.subprocess, "run", must_not_run)
    result = vb.check_one(tmp_path, "missing-source", fast=True, required_domain="psychology")
    assert not result["ok"]
    assert any("缺 book.txt" in blocker and "--source" in blocker for blocker in result["blockers"])


def test_strict_batch_blocks_missing_profile_while_default_path_stays_legacy(tmp_path, monkeypatch):
    _artifacts(tmp_path, "missing-profile")
    (tmp_path / "missing-profile" / "book.txt").write_text("原书正文", encoding="utf-8")
    (tmp_path / "missing-profile" / "source-audit.json").write_text("{}", encoding="utf-8")

    def domain_aware_run(cmd, **kwargs):
        if "--require-domain" in cmd:
            return SimpleNamespace(
                returncode=1,
                stdout="[distill] 严格域 psychology 要求完整 domain_profile，当前缺失(G23)\n",
                stderr="",
            )
        return SimpleNamespace(returncode=0, stdout="全部通过\n", stderr="")

    monkeypatch.setattr(vb.subprocess, "run", domain_aware_run)
    assert vb.check_one(tmp_path, "missing-profile", fast=True)["ok"]
    strict = vb.check_one(tmp_path, "missing-profile", fast=True, required_domain="psychology")
    assert not strict["ok"]
    assert any("严格域 psychology" in blocker for blocker in strict["blockers"])


def test_strict_batch_requires_source_audit_before_invoking_verifier(tmp_path, monkeypatch):
    _artifacts(tmp_path, "missing-audit")
    (tmp_path / "missing-audit" / "book.txt").write_text("原书正文", encoding="utf-8")

    def must_not_run(*args, **kwargs):
        raise AssertionError("缺 source-audit.json 时不应调起 verify_page")

    monkeypatch.setattr(vb.subprocess, "run", must_not_run)
    result = vb.check_one(tmp_path, "missing-audit", fast=True, required_domain="psychology")
    assert not result["ok"]
    assert any("缺 source-audit.json" in blocker and "hash" in blocker for blocker in result["blockers"])

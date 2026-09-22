"""CLI regressions; all source and model fixtures live in tempfile directories."""
import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "check_deep_retell.py"
TEXT = "张红超在二〇一〇年带着弟弟张红甫开设新店。他解释说，新增四百四十六家门店并不等于门店总数只有四百四十六家。"


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class DeepRetellAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="deep-retell-audit-test-")
        self.root = Path(self.temp.name)
        self.book = self.root / "book"
        self.raw = self.book / "_deepread"
        self.responses = self.raw / "out"
        self.source = {"no": 1, "part": "第一章", "title": "开店", "kind": "narrative", "text": TEXT}
        self.section = {"title": "兄弟开店", "paragraphs": [TEXT], "quote": "", "covers": ["P1"]}
        self.output = {"book": "测试", "units": [{"no": 1, "part": "第一章", "title": "开店", "kind": "narrative", "sections": [self.section]}]}
        dump(self.raw / "units.json", [self.source])
        dump(self.raw / "jobs.json", {"run_id": "fixture", "jobs": [{"job_id": "u001", "task": "rewrite"}]})
        dump(self.book / "deepread.json", self.output)
        (self.book / "book.txt").write_text(TEXT, encoding="utf-8")
        dump(self.responses / "u001.response.txt", {"sections": [self.section]})
        self.sequence = 0

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)

    def verify(self, extra=()):
        self.sequence += 1
        path = self.root / f"verify-{self.sequence}.json"
        proc = self.cli("verify", "--book", self.book, "--responses", self.responses, "--out", path, *extra)
        return proc, json.loads(path.read_text()) if path.exists() else {}

    def prepare(self, *extra):
        self.sequence += 1
        path = self.root / f"sample-{self.sequence}"
        proc = self.cli("prepare", "--book", self.book, "--generation-responses", self.responses, "--out-dir", path, *extra)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return path

    def test_valid_inputs_and_stale_source_output_and_mapping(self):
        mapping = self.root / "mapping.json"
        dump(mapping, {"mode": "full", "entries": [{"output_no": 1, "source_nos": [1], "job_id": "u001"}], "excluded_sources": []})
        proc, report = self.verify(("--mapping", mapping))
        self.assertEqual(proc.returncode, 0, report)
        path = self.root / f"verify-{self.sequence}.json"
        self.assertEqual(self.cli("check-report", "--report", path).returncode, 0)
        for file in [self.book / "book.txt", self.book / "deepread.json", mapping, self.responses / "u001.response.txt"]:
            before = file.read_bytes()
            file.write_bytes(before + b" ")
            changed = self.cli("check-report", "--report", path)
            self.assertEqual(changed.returncode, 1, changed.stdout)
            file.write_bytes(before)

    def test_empty_source_and_empty_output_fail(self):
        for file, payload in [(self.raw / "units.json", []), (self.book / "deepread.json", {"units": []})]:
            before = file.read_bytes()
            dump(file, payload)
            proc, report = self.verify()
            self.assertEqual(proc.returncode, 1, report)
            self.assertFalse(report["passed"])
            file.write_bytes(before)
        (self.book / "book.txt").write_text("")
        self.assertEqual(self.verify()[0].returncode, 1)

    def test_missing_duplicate_unknown_units_fail(self):
        original = self.output["units"][0]
        for units in [[], [original, original], [{**original, "no": 2}]]:
            dump(self.book / "deepread.json", {"units": units})
            self.assertEqual(self.verify()[0].returncode, 1)

    def test_missing_and_duplicate_expected_jobs_fail(self):
        dump(self.raw / "jobs.json", {"run_id": "fixture", "jobs": []})
        self.assertEqual(self.verify()[0].returncode, 1)
        job = {"job_id": "u001", "task": "rewrite"}
        dump(self.raw / "jobs.json", {"run_id": "fixture", "jobs": [job, job]})
        self.assertEqual(self.verify()[0].returncode, 1)

    def test_missing_invalid_and_unknown_generation_response_fail(self):
        response = self.responses / "u001.response.txt"
        before = response.read_bytes()
        response.unlink()
        self.assertEqual(self.verify()[0].returncode, 1)
        response.write_text("{broken}")
        self.assertEqual(self.verify()[0].returncode, 1)
        response.write_bytes(before)
        dump(self.responses / "u999.response.txt", {"sections": [self.section]})
        self.assertEqual(self.verify()[0].returncode, 1)

    def test_responses_not_checked_is_not_green(self):
        path = self.root / "without-responses.json"
        proc = self.cli("verify", "--book", self.book, "--out", path)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("generation_responses_not_checked", path.read_text())

    def test_wrong_source_and_unfounded_coverage_fail(self):
        (self.book / "book.txt").write_text("另一本完全无关的书")
        self.assertEqual(self.verify()[0].returncode, 1)
        (self.book / "book.txt").write_text(TEXT)
        self.output["units"][0]["sections"][0]["paragraphs"] = ["完全不存在的公园与海洋故事。"]
        dump(self.book / "deepread.json", self.output)
        proc, report = self.verify()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("coverage_claim_needs_review", str(report))
        self.output["units"][0]["sections"][0]["covers"] = ["P999"]
        dump(self.book / "deepread.json", self.output)
        self.assertIn("unknown_coverage_locator", str(self.verify()[1]))

    def test_explicit_selected_mapping_is_not_full(self):
        source2 = {**self.source, "no": 2}
        dump(self.raw / "units.json", [self.source, source2])
        mapping = self.root / "mapping.json"
        dump(mapping, {"mode": "selected", "entries": [{"output_no": 1, "source_nos": [1], "job_id": "u001"}],
                       "excluded_sources": [{"no": 2, "reason": "精选导读不含此节", "reviewer": "main_agent"}]})
        proc, report = self.verify(("--mapping", mapping))
        self.assertEqual(proc.returncode, 0, report)
        self.assertEqual(report["mapping_mode"], "selected")

    def test_cover_ranges_expand_and_validate_against_source(self):
        self.source["text"] = TEXT + "\n第二段是书中明确存在的短段。\n第三段也是书中明确存在的短段。"
        dump(self.raw / "units.json", [self.source])
        (self.book / "book.txt").write_text(self.source["text"])
        section = self.output["units"][0]["sections"][0]
        for covers in [["P1-P3"], ["u001:P1-P3"], ["u001:P1-u001:P3"]]:
            section["covers"] = covers
            dump(self.book / "deepread.json", self.output)
            self.assertEqual(self.verify()[0].returncode, 0, covers)
        for bad in ["P1-P4", "P3-P1", "P0-P1", "u001:P1-u002:P3", "u999:P1-P2", "P1-P999999999"]:
            section["covers"] = [bad]
            dump(self.book / "deepread.json", self.output)
            proc, report = self.verify()
            self.assertEqual(proc.returncode, 1, bad)
            self.assertIn("unknown_coverage_locator", str(report), bad)

    def test_character_arrays_and_metadata_fail_and_are_deferred(self):
        self.output["units"][0]["sections"] += [
            {**self.section, "paragraphs": list(TEXT)},
            {"skipped": [{"id": "P1", "why": "test"}], "paragraphs": []},
            {**self.section, "paragraphs": []}]
        dump(self.book / "deepread.json", self.output)
        proc, report = self.verify()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("character_fragmented_paragraphs", str(report))
        self.assertIn("metadata_in_sections", str(report))
        folder = self.prepare("--all")
        plan = json.loads((folder / "plan.json").read_text())
        self.assertEqual(plan["total_sections"], 4)
        self.assertEqual(plan["selected_count"], 1)
        self.assertEqual(len(plan["deferred_structural_sections"]), 3)
        manifest = json.loads((folder / "manifest-001.json").read_text())
        self.assertEqual([x["job_id"] for x in manifest["jobs"]], ["u001-s01"])

    def test_prepare_is_runner_compatible_bounded_and_no_overwrite(self):
        self.output["units"][0]["sections"] = [self.section.copy() for _ in range(129)]
        dump(self.book / "deepread.json", self.output)
        folder = self.prepare("--all")
        manifests = [json.loads(p.read_text()) for p in sorted(folder.glob("manifest-*.json"))]
        self.assertEqual([len(m["jobs"]) for m in manifests], [128, 1])
        self.assertTrue(all(set(m) == {"run_id", "jobs"} for m in manifests))
        ids = [j["job_id"] for m in manifests for j in m["jobs"]]
        self.assertEqual(len(set(ids)), 129)
        self.assertEqual(self.cli("prepare", "--book", self.book, "--out-dir", folder).returncode, 2)

    def test_semantic_collect_missing_duplicate_fabricated_and_pending(self):
        plan = self.prepare("--section", "u001-s01") / "plan.json"
        responses = self.root / "semantic"
        responses.mkdir()
        out = self.root / "missing.json"
        proc = self.cli("collect", "--plan", plan, "--responses", responses, "--out", out)
        self.assertEqual(proc.returncode, 1)
        valid = {"section_id": "u001-s01", "findings": []}
        dump(responses / "u001-s01.response.txt", valid)
        out = self.root / "pending.json"
        self.assertEqual(self.cli("collect", "--plan", plan, "--responses", responses, "--out", out).returncode, 0)
        report = json.loads(out.read_text())
        self.assertFalse(report["passed"])
        self.assertEqual(report["status"], "awaiting_human_review")
        duplicate = self.root / "semantic2"
        dump(duplicate / "u001-s01.response.txt", valid)
        self.assertEqual(self.cli("collect", "--plan", plan, "--responses", responses, "--responses", duplicate,
                                  "--out", self.root / "dup.json").returncode, 1)
        dump(responses / "u001-s01.response.txt", {"section_id": "u001-s01", "findings": [{
            "type": "person", "severity": "major", "source_refs": ["u001:P1"], "output_ref": "O1",
            "source_quote": "原文中并不存在", "output_quote": "张红超", "reason": "错人"}]})
        self.assertEqual(self.cli("collect", "--plan", plan, "--responses", responses,
                                  "--out", self.root / "fabricated.json").returncode, 1)

    def test_side_evidence_requires_exact_task_id_and_exact_nonempty_excerpt(self):
        self.source["side"] = [{"id": "claim:fixture:1", "text": "大区、办事处和经销商各获授权一千箱。",
                                "quote": "办事处和经销商各获授权一千箱。"}]
        dump(self.raw / "units.json", [self.source])
        # A real-looking external catalog must never expand the task's evidence scope.
        dump(self.book / "claims.json", [{"id": "claim:outside-task:9", "text": "任务外真实旁证"}])
        plan = self.prepare("--all") / "plan.json"
        responses = self.root / "side-semantic"
        finding = {"type": "attribution", "severity": "minor", "source_refs": ["claim:fixture:1"],
                   "output_ref": "O1", "source_quote": "大区、办事处", "output_quote": "张红超", "reason": "核对旁证"}
        cases = [("text-valid", {}, 0),
                 ("quote-valid", {"source_quote": "办事处和经销商各获授权一千箱。"}, 0),
                 ("unknown-id", {"source_refs": ["claim:invented:7"]}, 1),
                 ("outside-task-id", {"source_refs": ["claim:outside-task:9"], "source_quote": "任务外真实旁证"}, 1),
                 ("empty-quote", {"source_quote": ""}, 1),
                 ("whitespace-quote", {"source_quote": "  "}, 1),
                 ("wrong-quote", {"source_quote": "原文没有的两千箱"}, 1),
                 ("wrong-id-right-quote", {"source_refs": ["claim:fixture:2"]}, 1)]
        for name, change, expected in cases:
            with self.subTest(name=name):
                dump(responses / "u001-s01.response.txt", {"section_id": "u001-s01", "findings": [{**finding, **change}]})
                out = self.root / (name + ".json")
                result = self.cli("collect", "--plan", plan, "--responses", responses, "--out", out)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                report = json.loads(out.read_text())
                self.assertFalse(report["passed"])
                if expected:
                    self.assertIn("invalid_semantic_response", str(report["errors"]))

    def test_human_decision_binding_and_no_automatic_repair(self):
        original = (self.book / "deepread.json").read_bytes()
        plan = self.prepare("--section", "u001-s01") / "plan.json"
        responses = self.root / "semantic"
        dump(responses / "u001-s01.response.txt", {"section_id": "u001-s01", "findings": [{
            "type": "person", "severity": "major", "source_refs": ["u001:P1"], "output_ref": "O1",
            "source_quote": "张红超", "output_quote": "张红超", "reason": "测试模型误报"}]})
        initial = self.root / "initial.json"
        self.assertEqual(self.cli("collect", "--plan", plan, "--responses", responses, "--out", initial).returncode, 0)
        report = json.loads(initial.read_text())
        decision = self.root / "decisions.json"
        decisions = {"audit_hash": report["audit_hash"], "reviewer": {"kind": "main_agent", "id": "test-reviewer"},
                     "reviewed_sections": ["u001-s01"], "resolutions": [{"finding_id": "u001-s01-f01",
                     "disposition": "false_positive", "reason": "人名一致，未发生换人"}]}
        dump(decision, decisions)
        final = self.root / "reviewed.json"
        self.assertEqual(self.cli("collect", "--plan", plan, "--responses", responses, "--decisions", decision, "--out", final).returncode, 0)
        self.assertTrue(json.loads(final.read_text())["passed"])
        self.assertFalse(json.loads(final.read_text())["whole_book_certified"])
        self.assertEqual((self.book / "deepread.json").read_bytes(), original)
        decisions["audit_hash"] = "wrong"
        dump(decision, decisions)
        self.assertEqual(self.cli("collect", "--plan", plan, "--responses", responses, "--decisions", decision,
                                  "--out", self.root / "stale.json").returncode, 1)

    def test_plan_stale_and_report_overwrite_refused(self):
        plan = self.prepare("--all") / "plan.json"
        (self.book / "book.txt").write_text(TEXT + "修改")
        response = self.root / "semantic"
        dump(response / "u001-s01.response.txt", {"section_id": "u001-s01", "findings": []})
        out = self.root / "stale.json"
        self.assertEqual(self.cli("collect", "--plan", plan, "--responses", response, "--out", out).returncode, 1)
        self.assertEqual(json.loads(out.read_text())["status"], "stale")
        self.assertEqual(self.cli("collect", "--plan", plan, "--responses", response, "--out", out).returncode, 2)

    def test_model_receipt_must_match_task_and_response(self):
        folder = self.prepare("--all")
        job = json.loads((folder / "manifest-001.json").read_text())["jobs"][0]
        responses = self.root / "semantic"
        responses.mkdir()
        answer = json.dumps({"section_id": "u001-s01", "findings": []})
        (responses / "u001-s01.response.txt").write_text(answer + "\n")
        meta = {"task_sha256": hashlib.sha256(job["task"].encode()).hexdigest(),
                "response_sha256": hashlib.sha256(answer.encode()).hexdigest()}
        dump(responses / "u001-s01.meta.json", meta)
        self.assertEqual(self.cli("collect", "--plan", folder / "plan.json", "--responses", responses,
                                  "--out", self.root / "receipt-valid.json").returncode, 0)
        for key in ["task_sha256", "response_sha256"]:
            bad = {**meta, key: "wrong"}
            dump(responses / "u001-s01.meta.json", bad)
            self.assertEqual(self.cli("collect", "--plan", folder / "plan.json", "--responses", responses,
                                      "--out", self.root / f"receipt-bad-{key}.json").returncode, 1)


if __name__ == "__main__":
    unittest.main()

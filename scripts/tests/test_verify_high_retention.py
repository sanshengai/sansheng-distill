"""Run the public audit/CLI on invented books in clean temporary directories.

The source/coverage fixture and the complete static legacy page fixture are
reused from this public repository. No real book, private path, API or browser
is required. Test attestations describe invented inputs, not semantic approval
of production content. Static cases run the real legacy G9/G14/source checks;
the one browser-dispatch test mocks only smoke and verifies its call boundary.
"""
from __future__ import annotations

from html import escape
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1]
ENTRY = SCRIPTS / "verify_high_retention.py"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


AUDITOR = module("high_retention_under_test", ENTRY)
COVERAGE_FIXTURE = module("high_retention_coverage_fixture", Path(__file__).with_name("test_book_coverage.py"))
LEGACY_FIXTURE = module("high_retention_page_fixture", Path(__file__).with_name("test_verify_page.py"))


def fixture():
    docs = COVERAGE_FIXTURE.fixture()
    source = docs["source-map.json"]
    chapters, configured = [], []
    for no in (1, 2):
        cid = f"c{no:02}"
        source_chapter = next(row for row in source["chapters"] if row["id"] == cid)
        source_chapter.update(
            source_scope="primary" if no == 1 else "non_primary",
            classification_review={"decision": "approved", "reviewer": "invented-fixture-reviewer",
                                   "rationale": "Synthetic test classification, not a real book approval."},
        )
        ids = [unit["id"] for unit in docs["deepread.json"]["units"] if unit["chapter"] == cid]
        configured.append({"no": no, "source_chapter_id": cid, "deepread_unit_ids": ids,
                           "source_role": "primary" if no == 1 else "source_apparatus"})
        paragraph = next(p for p in source["paragraphs"] if p["chapter"] == cid)
        quote = docs["book.txt"][paragraph["start"]:paragraph["end"]].strip()
        narrative = ("\n\n".join(f"第{i}项说明强调核对不同任务条件与反馈，再按实际情境决定是否行动。" for i in range(35))
                     if no == 1 else "这段来源附记说明协作的前提与贡献归属。独立判断仍需要核实输入，不能仅以沟通次数推断判断质量。")
        chapters.append({"no": no, "source_chapter_id": cid,
                         "title": "核实输入才有可靠的协作" if no == 1 else "来源附记保留贡献归属",
                         "summary": f"阅读部分{no}解释输入与反馈的关系。", "narrative": narrative,
                         "anchor": f"第{no}章", "excerpts": [{"text": quote, "anchor": f"第{no}章·原文位置"}]})
    docs["config.json"] = {"slug": "invented-book", "chapters": configured}
    docs["distill.json"] = LEGACY_FIXTURE.distill(slug="invented-book", chapters=chapters)
    docs["distill.json"]["quotes"][0].update(text=chapters[0]["excerpts"][0]["text"], anchor="第1章")
    docs["enrich.json"] = {"author_page": {}, "views_page": {}, "reviews": []}
    return docs


def html_page(docs):
    blocks = []
    units = {unit["id"]: unit for unit in docs["deepread.json"]["units"]}
    config = {chapter["no"]: chapter for chapter in docs["config.json"]["chapters"]}
    for ch in docs["distill.json"]["chapters"]:
        details = "".join(
            f'<details class="bd-deep-unit" id="{uid}"><summary>分析</summary>'
            f'<div class="deep-unit-body"><p>{escape(units[uid]["body"])}</p></div></details>'
            for uid in config[ch["no"]]["deepread_unit_ids"]
        )
        narrative = "".join(f"<p>{escape(p)}</p>" for p in ch["narrative"].split("\n\n"))
        blocks.append(f'<section class="bd-chapter" id="ch-{ch["no"]}" data-source="第{ch["no"]}章">'
                      f'<h3>{escape(ch["title"])}</h3><p class="ch-summary">{escape(ch["summary"])}</p>'
                      f'<div class="ch-narrative">{narrative}</div>{details}'
                      '<p class="src-note">来源位置</p></section>')
    page = LEGACY_FIXTURE.page(chapters="".join(blocks))
    # The legacy helper predates the rich-shell static check. These signatures
    # make this a complete static fixture, not a browser-interaction fixture.
    shell = ('<div class="theme-picker"><button type="button">主题</button></div>'
             '<button type="button" data-mm="fit">适配</button>'
             '<script>function initMindmap() {} function initHashRouter() {}</script>')
    return page.replace("</body>", shell + "</body>")


def write_docs(directory, docs):
    for name, value in docs.items():
        raw = value.encode("utf-8") if isinstance(value, str) else json.dumps(value, ensure_ascii=False).encode("utf-8")
        (directory / name).write_bytes(raw)


def fixture_receipt(directory, docs):
    """Fabricate approval only for the isolated synthetic test fixture."""
    return {"schema_version": 1, "input_sha256": AUDITOR.input_hashes(directory), "entries": [{
        "no": 2, "source_chapter_id": "c02", "decision": "approved",
        "reviewer": "invented-fixture-reviewer", "rationale": "Test-only short source appendix.",
        "knowledge_item_ids": [item["id"] for item in docs["content-ledger.json"]["items"] if item["chapter"] == "c02"],
    }]}


def replace_source_chars(docs, transform):
    """Change source content without moving its existing spans, then rehash it."""
    text = docs["book.txt"]
    chapter = next(c for c in docs["source-map.json"]["chapters"] if c["id"] == "c02")
    start, end = chapter["start"], chapter["end"]
    replacement = transform(text[start:end])
    assert len(replacement) == end - start
    text = text[:start] + replacement + text[end:]
    docs["book.txt"] = text
    source = docs["source-map.json"]
    source["source"]["sha256"] = AUDITOR.COVERAGE.sha256(text.encode())
    for paragraph in source["paragraphs"]:
        paragraph["sha256"] = AUDITOR.COVERAGE.sha256(text[paragraph["start"]:paragraph["end"]].encode())
    # Do not introduce an unrelated source-quote error in these negative cases.
    docs["distill.json"]["chapters"][1]["excerpts"] = []
    COVERAGE_FIXTURE.sign_fixture(docs)


class HighRetentionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="public-high-retention-test-")
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.docs = fixture()

    def prepare(self, receipt=True):
        write_docs(self.directory, self.docs)
        (self.directory / "invented-book.html").write_text(html_page(self.docs), encoding="utf-8")
        if receipt:
            self.sign_receipt()

    def sign_receipt(self):
        (self.directory / "short-apparatus-review.json").write_text(
            json.dumps(fixture_receipt(self.directory, self.docs), ensure_ascii=False), encoding="utf-8")

    def sync(self, resign=False):
        write_docs(self.directory, self.docs)
        if resign:
            self.sign_receipt()

    def cli(self, expected=1):
        report_path = self.directory / "result.json"
        process = subprocess.run([sys.executable, "-B", str(ENTRY), "--book-dir", str(self.directory),
                                  "--skip-interact", "--report", str(report_path)],
                                 cwd=self.directory, capture_output=True, text=True, timeout=30)
        self.assertEqual(process.returncode, expected, process.stdout + process.stderr)
        report = json.loads(process.stdout)
        self.assertEqual(report, json.loads(report_path.read_text()))
        self.assertEqual(report["passed"], expected == 0)
        return report

    def rejected(self, reason):
        report = self.cli()
        self.assertTrue(any(reason in error for error in report["errors"]), report)
        return report

    def test_real_legacy_positive_and_short_g9_only(self):
        self.prepare()
        raw = AUDITOR.LEGACY.lint_html((self.directory / "invented-book.html").read_text(),
                                     self.docs["distill.json"], self.docs["enrich.json"])
        self.assertEqual(len(raw), 1, raw)
        self.assertIn("(G9 详实度)", raw[0])
        report = self.cli(0)
        self.assertFalse(report["browser_checked"])
        self.assertTrue(report["coverage_recomputed"])
        self.assertEqual([entry["no"] for entry in report["accepted_short_apparatus"]], [2])

    def test_primary_source_cannot_self_label_as_apparatus(self):
        self.docs["source-map.json"]["chapters"][-1]["source_scope"] = "primary"
        self.prepare()
        self.rejected("primary content cannot")

    def test_changed_scope_invalidates_existing_receipt(self):
        self.prepare()
        self.docs["source-map.json"]["chapters"][-1]["source_scope"] = "primary"
        self.sync()
        self.rejected("hashes are stale")

    def test_empty_source_cannot_pass_with_fresh_fixture_receipt(self):
        replace_source_chars(self.docs, lambda value: " " * len(value))
        self.prepare()
        self.rejected("freshly recomputed coverage")

    def test_punctuation_only_source_cannot_pass(self):
        replace_source_chars(self.docs, lambda value: "。" * len(value))
        self.prepare()
        # Coverage structural hashes alone accept punctuation; this extra gate must reject it.
        self.assertTrue(AUDITOR.COVERAGE.audit_book(self.directory)["release_ready"])
        self.rejected("punctuation only")

    def test_bad_source_hash_is_rejected_even_with_fresh_receipt(self):
        self.docs["source-map.json"]["source"]["sha256"] = "0" * 64
        self.prepare()
        self.rejected("freshly recomputed coverage")

    def test_bad_source_span_is_rejected_even_with_fresh_receipt(self):
        self.docs["source-map.json"]["chapters"][-1]["end"] += 1
        self.prepare()
        self.rejected("freshly recomputed coverage")

    def test_one_partial_appendix_item_rejected_despite_global_thresholds(self):
        item = self.docs["content-ledger.json"]["items"][-1]
        item.update(status="partial", exclusion_reason="Synthetic missing detail.")
        COVERAGE_FIXTURE.sign_fixture(self.docs)
        self.prepare()
        coverage = AUDITOR.COVERAGE.audit_book(self.directory)
        self.assertTrue(coverage["release_ready"], coverage)
        self.assertEqual(coverage["metrics"]["book"]["ratio"], .9)
        self.rejected("every knowledge obligation must be fully covered")

    def test_old_semantic_signature_rejected_with_fresh_input_receipt(self):
        self.docs["deepread.json"]["units"][-1]["body"] += "追加了尚未审阅的判断。"
        self.prepare()
        self.rejected("freshly recomputed coverage")

    def test_no_receipt_leaves_real_legacy_g9_failure(self):
        self.prepare(receipt=False)
        report = self.rejected("(G9 详实度)")
        self.assertEqual(report["accepted_short_apparatus"], [])

    def test_changed_narrative_invalidates_receipt(self):
        self.prepare()
        self.docs["distill.json"]["chapters"][-1]["narrative"] += "这是没有重新审过的一句。"
        self.sync()
        self.rejected("hashes are stale")

    def test_deleted_both_reading_mappings_cannot_hide_source_chapter(self):
        self.prepare()
        self.docs["config.json"]["chapters"].pop()
        self.docs["distill.json"]["chapters"].pop()
        self.sync(resign=True)
        self.rejected("every effective source chapter")

    def test_deleted_single_mapping_is_rejected(self):
        self.prepare()
        self.docs["config.json"]["chapters"].pop()
        self.sync(resign=True)
        self.rejected("config/distill chapter set mismatch")

    def test_forged_old_coverage_report_is_never_trusted(self):
        self.docs["content-ledger.json"]["items"] = []
        self.prepare()
        (self.directory / "coverage-report.json").write_text(json.dumps({"release_ready": True}))
        self.rejected("freshly recomputed coverage")

    def test_g9_approval_does_not_suppress_real_g14(self):
        self.docs["distill.json"]["chapters"][-1]["excerpts"] = []
        self.prepare()
        report = self.rejected("(G14 每章 ≥1)")
        self.assertEqual(len(report["accepted_short_apparatus"]), 1)
        self.assertFalse(any("(G9" in error for error in report["errors"]))

    def test_g9_approval_does_not_suppress_real_source_error(self):
        self.docs["distill.json"]["chapters"][-1]["excerpts"][0]["text"] = "这是一句完全不在合成来源里的引文。"
        self.prepare()
        report = self.rejected("excerpt 未在原文命中")
        self.assertEqual(len(report["accepted_short_apparatus"]), 1)

    def test_reviewed_knowledge_set_cannot_omit_one_obligation(self):
        self.prepare()
        receipt = fixture_receipt(self.directory, self.docs)
        receipt["entries"][0]["knowledge_item_ids"].pop()
        (self.directory / "short-apparatus-review.json").write_text(json.dumps(receipt))
        self.rejected("reviewed knowledge set mismatch")

    def test_empty_or_punctuation_narrative_is_not_an_appendix(self):
        for narrative in ("", "  。；？！  "):
            with self.subTest(narrative=narrative):
                self.docs["distill.json"]["chapters"][-1]["narrative"] = narrative
                self.prepare()
                self.rejected("narrative is empty")

    def test_dom_cannot_omit_reviewed_deep_body(self):
        self.prepare()
        path = self.directory / "invented-book.html"
        old = escape(self.docs["deepread.json"]["units"][-1]["body"])
        path.write_text(path.read_text().replace(old, ""))
        self.rejected("body differs from reviewed input")

    def test_dom_must_contain_reviewed_narrative(self):
        self.prepare()
        path = self.directory / "invented-book.html"
        old = escape(self.docs["distill.json"]["chapters"][-1]["narrative"])
        path.write_text(path.read_text().replace(old, "旧的未审正文。"))
        self.rejected("narrative")

    def test_dom_must_contain_reviewed_summary(self):
        self.prepare()
        path = self.directory / "invented-book.html"
        old = escape(self.docs["distill.json"]["chapters"][-1]["summary"])
        path.write_text(path.read_text().replace(old, "旧的未审摘要。"))
        self.rejected("summary")

    def test_crlf_source_uses_original_character_coordinates(self):
        original = self.docs["book.txt"]
        text = original.replace("\n", "\r\n")
        source = self.docs["source-map.json"]
        for group in ("chapters", "sections", "paragraphs"):
            for row in source[group]:
                for key in ("start", "end"):
                    row[key] += original[:row[key]].count("\n")
        for paragraph in source["paragraphs"]:
            paragraph["sha256"] = AUDITOR.COVERAGE.sha256(text[paragraph["start"]:paragraph["end"]].encode())
        source["source"]["sha256"] = AUDITOR.COVERAGE.sha256(text.encode())
        self.docs["book.txt"] = text
        COVERAGE_FIXTURE.sign_fixture(self.docs)
        self.prepare()
        self.assertTrue(AUDITOR.COVERAGE.audit_book(self.directory)["release_ready"])
        self.cli(0)

    def test_browser_dispatch_keeps_complete_distill_and_errors(self):
        self.prepare()
        with patch.object(AUDITOR.LEGACY, "smoke", return_value=["synthetic browser failure"]) as smoke:
            report = AUDITOR.audit(self.directory)
        self.assertFalse(report["passed"])
        self.assertTrue(report["browser_checked"])
        self.assertIn("synthetic browser failure", report["errors"])
        self.assertEqual(len(smoke.call_args.args[2]["chapters"]), 2)


if __name__ == "__main__":
    unittest.main()

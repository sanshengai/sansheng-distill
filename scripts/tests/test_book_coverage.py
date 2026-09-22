#!/usr/bin/env python3
"""Behavioral tests execute the shipped CLI against isolated, invented sources."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CANONICAL_SCRIPT = Path(__file__).resolve().parents[1] / "book_coverage.py"
SCRIPT = CANONICAL_SCRIPT
SPEC = importlib.util.spec_from_file_location("book_coverage_tested", SCRIPT)
COVERAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COVERAGE)


def fixture():
    text = "示例版权页，仅供测试。\n"
    source = {"schema_version": 1, "chapters": [{"id": "c00", "title": "版权", "start": 0, "end": len(text), "kind": "excluded", "exclusion_reason": "测试排版及版权信息，无管理知识"}],
              "sections": [{"id": "s000", "chapter": "c00", "title": "版权", "start": 0, "end": len(text), "kind": "excluded", "exclusion_reason": "测试版权信息"}],
              "paragraphs": [{"id": "p0000", "chapter": "c00", "section": "s000", "start": 0, "end": len(text), "sha256": COVERAGE.sha256(text.encode()), "disposition": "excluded", "exclusion_reason": "测试版权信息"}]}
    items, units = [], []
    for chapter_number in range(1, 3):
        chapter_id = f"c{chapter_number:02}"
        chapter_start = len(text)
        for section_number in range(1, 6):
            n = (chapter_number - 1) * 5 + section_number
            sid, pid, iid, uid = f"s{n:03}", f"p{n:04}", f"i{n:04}", f"u{n:04}"
            paragraph = f"测试章节{chapter_number}观点{section_number}：当任务需要多人协同，应明确责任与反馈；限制条件为信息必须可核实。\n"
            start = len(text)
            text += paragraph
            source["sections"].append({"id": sid, "chapter": chapter_id, "title": f"观点{section_number}", "start": start, "end": len(text), "kind": "effective"})
            source["paragraphs"].append({"id": pid, "chapter": chapter_id, "section": sid, "start": start, "end": len(text), "sha256": COVERAGE.sha256(paragraph.encode()), "disposition": "effective"})
            items.append({"id": iid, "type": "limitation" if n == 1 else "claim", "chapter": chapter_id, "source_paragraph_ids": [pid], "critical": n == 1,
                          "statement": f"独立知识项{n}：信息可核实是协同决策的边界条件。", "status": "covered", "target_ids": [uid], "exclusion_reason": ""})
            units.append({"id": uid, "chapter": chapter_id, "source_paragraph_ids": [pid], "body": f"分析单元{n}。明确责任使反馈可以追溯到具体任务；如果信息本身无法核实，重复沟通不会自然提高判断质量。因此需要先验证输入，再使用协同机制。"})
        source["chapters"].append({"id": chapter_id, "title": f"测试章节{chapter_number}", "start": chapter_start, "end": len(text), "kind": "effective"})
    source["source"] = {"path": "book.txt", "sha256": COVERAGE.sha256(text.encode())}
    source["figures"] = []
    source["ledger_inventory_sha256"] = COVERAGE.inventory_sha256(items)
    docs = {"book.txt": text, "source-map.json": source, "content-ledger.json": {"schema_version": 1, "items": items}, "deepread.json": {"schema_version": 1, "units": units}}
    sign_fixture(docs)
    return docs


def sign_fixture(docs):
    """Fixture attestation only; production CLI cannot approve a semantic review."""
    for item in docs["content-ledger.json"]["items"]:
        item["semantic_review"] = {"reviewer": "test-fixture-author", "decision": "approved", "rationale": "人工编写的测试夹具，已核对示例来源、状态及分析，不是生产书籍审阅。", "reviewed_content_sha256": COVERAGE.review_sha256(item, docs["deepread.json"]["units"])}
    docs["source-map.json"]["figure_inventory_review"] = {"reviewer": "test-fixture-author", "decision": "approved", "rationale": "人工编写的测试资料已核图表库存。", "reviewed_inventory_sha256": COVERAGE.figure_inventory_sha256(docs["source-map.json"])}


def add_figure(docs):
    asset = '<svg xmlns="http://www.w3.org/2000/svg"><text>输入 → 核查 → 决策</text></svg>'
    docs["figure.svg"] = asset
    figure = {"id": "f001", "chapter": "c01", "section": "s001", "source_paragraph_ids": ["p0001"], "asset_path": "figure.svg", "sha256": COVERAGE.sha256(asset.encode()), "disposition": "effective", "interpretation": {"text": "", "decision": "pending", "reviewer": "", "rationale": ""}}
    docs["source-map.json"]["figures"] = [figure]
    docs["content-ledger.json"]["items"][0]["type"] = "figure"
    docs["source-map.json"]["ledger_inventory_sha256"] = COVERAGE.inventory_sha256(docs["content-ledger.json"]["items"])
    sign_fixture(docs)
    return figure


class CoverageCLI(unittest.TestCase):
    def test_public_script_runs_standalone_in_isolated_python(self):
        with tempfile.TemporaryDirectory(prefix="standalone-book-coverage-") as temp:
            directory = Path(temp)
            script = directory / "book_coverage.py"
            script.write_bytes(CANONICAL_SCRIPT.read_bytes())
            for name, value in fixture().items():
                (directory / name).write_bytes(value.encode() if isinstance(value, str) else json.dumps(value, ensure_ascii=False).encode())
            process = subprocess.run([sys.executable, "-I", "-B", str(script), "--book-dir", str(directory)], cwd=directory, capture_output=True, text=True, timeout=20)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            self.assertTrue(json.loads((directory / "coverage-report.json").read_text())["release_ready"])

    def test_amendment_metadata_cannot_waive_inventory_drift(self):
        docs = fixture()
        docs["content-ledger.json"]["items"].pop(0)
        docs["source-map.json"]["inventory_amendments"] = [{"decision": "approved", "reason": "This fabricated metadata must not waive the frozen hash check.", "old_sha256": docs["source-map.json"]["ledger_inventory_sha256"], "new_sha256": COVERAGE.inventory_sha256(docs["content-ledger.json"]["items"])}]
        self.run_case(docs, 2, "inventory_drift")

    def run_case(self, docs, expected, code=None):
        with tempfile.TemporaryDirectory(prefix="book-coverage-test-") as temp:
            directory = Path(temp)
            for name, value in docs.items():
                (directory / name).write_bytes(value.encode() if isinstance(value, str) else json.dumps(value, ensure_ascii=False).encode())
            process = subprocess.run([sys.executable, "-B", str(SCRIPT), "--book-dir", str(directory)], capture_output=True, text=True, timeout=20)
            self.assertEqual(process.returncode, expected, process.stdout + process.stderr)
            self.assertTrue((directory / "coverage-report.json").exists(), process.stderr)
            report = json.loads((directory / "coverage-report.json").read_text())
            if code:
                self.assertIn(code, [error["code"] for error in report["errors"]], report)
            return report

    def test_complete_positive_and_excluded_front_matter(self):
        report = self.run_case(fixture(), 0)
        self.assertTrue(report["release_ready"])
        self.assertEqual(report["metrics"]["book"]["ratio"], 1)
        self.assertNotIn("c00", report["metrics"]["chapters"])
        self.assertEqual(report["metrics"]["effective_paragraphs"], 10)

    def test_empty_ledger_cannot_pass(self):
        docs = fixture()
        docs["content-ledger.json"]["items"] = []
        self.run_case(docs, 2, "empty_ledger")

    def test_deleted_critical_limitation_breaks_frozen_inventory(self):
        docs = fixture()
        docs["content-ledger.json"]["items"].pop(0)
        self.run_case(docs, 2, "inventory_drift")

    def test_missing_critical_fails_even_at_ninety_percent(self):
        docs = fixture()
        item = docs["content-ledger.json"]["items"][0]
        item.update(status="missing", target_ids=[], exclusion_reason="关键限制尚未说明")
        sign_fixture(docs)
        report = self.run_case(docs, 2, "critical_coverage")
        self.assertEqual(report["metrics"]["book"]["ratio"], .9)

    def test_deleted_whole_source_section_is_detected(self):
        docs = fixture()
        docs["source-map.json"]["sections"].pop(2)
        docs["source-map.json"]["paragraphs"].pop(2)
        docs["content-ledger.json"]["items"].pop(1)
        report = self.run_case(docs, 2, "unmapped_source")
        self.assertFalse(report["release_ready"])

    def test_id_without_body_fails(self):
        docs = fixture()
        docs["deepread.json"]["units"][0]["body"] = "  <p></p> ### "
        self.run_case(docs, 2, "empty_body")

    def test_source_from_wrong_chapter_fails(self):
        docs = fixture()
        docs["content-ledger.json"]["items"][0]["source_paragraph_ids"] = ["p0006"]
        self.run_case(docs, 2, "item_source_chapter")

    def test_source_paragraph_wrong_chapter_fails(self):
        docs = fixture()
        docs["source-map.json"]["paragraphs"][1]["chapter"] = "c02"
        self.run_case(docs, 2, "source_parent")

    def test_duplicate_item_id_fails(self):
        docs = fixture()
        docs["content-ledger.json"]["items"].append(copy.deepcopy(docs["content-ledger.json"]["items"][0]))
        self.run_case(docs, 2, "duplicate_id")

    def test_duplicate_knowledge_with_new_id_still_fails(self):
        docs = fixture()
        clone = copy.deepcopy(docs["content-ledger.json"]["items"][0])
        clone["id"] = "i-duplicate"
        docs["content-ledger.json"]["items"].append(clone)
        docs["source-map.json"]["ledger_inventory_sha256"] = COVERAGE.inventory_sha256(docs["content-ledger.json"]["items"])
        self.run_case(docs, 2, "duplicate_item")

    def test_fake_source_position_fails(self):
        docs = fixture()
        docs["source-map.json"]["paragraphs"][1]["start"] += 8
        self.run_case(docs, 2, "paragraph_hash")

    def test_dangling_target_fails(self):
        docs = fixture()
        docs["content-ledger.json"]["items"][0]["target_ids"] = ["nonexistent"]
        self.run_case(docs, 2, "dangling_target")

    def test_existing_body_with_wrong_source_mapping_fails(self):
        docs = fixture()
        docs["content-ledger.json"]["items"][0]["target_ids"] = ["u0002"]
        self.run_case(docs, 2, "target_source_mapping")

    def test_unexplained_source_exclusion_fails(self):
        docs = fixture()
        docs["source-map.json"]["paragraphs"][0]["exclusion_reason"] = ""
        self.run_case(docs, 2, "unexplained_exclusion")

    def test_partial_is_not_full_coverage(self):
        docs = fixture()
        docs["content-ledger.json"]["items"][-1].update(status="partial", exclusion_reason="仍缺适用条件")
        sign_fixture(docs)
        report = self.run_case(docs, 0)
        self.assertEqual(report["metrics"]["book"]["covered_items"], 9)
        self.assertEqual(report["metrics"]["chapters"]["c02"]["ratio"], .8)

    def test_book_below_ninety_percent_fails(self):
        docs = fixture()
        for item in (docs["content-ledger.json"]["items"][4], docs["content-ledger.json"]["items"][9]):
            item.update(status="partial", exclusion_reason="尚未解释机制")
        sign_fixture(docs)
        self.run_case(docs, 2, "book_coverage")

    def test_empty_effective_chapter_fails(self):
        docs = fixture()
        for item in docs["content-ledger.json"]["items"][5:]:
            item.update(status="excluded", exclusion_reason="测试排除全部项目")
        sign_fixture(docs)
        self.run_case(docs, 2, "empty_chapter_denominator")

    def test_machine_pass_never_auto_approves_semantics(self):
        docs = fixture()
        for item in docs["content-ledger.json"]["items"]:
            item["semantic_review"] = {"decision": "pending"}
        report = self.run_case(docs, 3)
        self.assertTrue(report["machine_pass"])
        self.assertFalse(report["semantic_review_complete"])
        self.assertFalse(report["release_ready"])

    def test_changed_analysis_invalidates_preexisting_review(self):
        docs = fixture()
        docs["deepread.json"]["units"][0]["body"] += "新增加未经审阅的断言。"
        report = self.run_case(docs, 3)
        self.assertTrue(report["machine_pass"])
        self.assertFalse(report["semantic_reviews"][0]["complete"])

    def test_changed_source_file_fails(self):
        docs = fixture()
        docs["book.txt"] += "未经登记的有实质意义附录。"
        self.run_case(docs, 2, "source_hash")

    def test_repeated_source_reference_fails(self):
        docs = fixture()
        docs["content-ledger.json"]["items"][0]["source_paragraph_ids"] *= 2
        self.run_case(docs, 2, "duplicate_reference")

    def test_empty_book_and_map_fail(self):
        docs = fixture()
        docs["book.txt"] = " \n"
        docs["source-map.json"].update(chapters=[], sections=[], paragraphs=[])
        self.run_case(docs, 2, "empty_source")

    def test_effective_paragraph_without_any_ledger_destination_fails(self):
        docs = fixture()
        docs["content-ledger.json"]["items"].pop(4)
        docs["source-map.json"]["ledger_inventory_sha256"] = COVERAGE.inventory_sha256(docs["content-ledger.json"]["items"])
        self.run_case(docs, 2, "paragraph_without_item")

    def test_effective_figure_without_meaning_blocks_release(self):
        docs = fixture()
        add_figure(docs)
        report = self.run_case(docs, 3)
        self.assertTrue(report["machine_pass"])
        self.assertTrue(report["semantic_review_complete"])
        self.assertFalse(report["source_review_complete"])
        self.assertFalse(report["source_reviews"]["figures"][0]["complete"])
        self.assertEqual(report["metrics"]["book"]["covered_items"], 9)
        self.assertEqual(report["metrics"]["critical"]["covered_items"], 0)
        self.assertFalse(report["coverage_targets_met"])
        self.assertEqual(report["coverage_gate_state"], "pending_source_review")

    def test_effective_figure_with_reviewed_interpretation_passes(self):
        docs = fixture()
        figure = add_figure(docs)
        figure["interpretation"] = {"text": "图中的三个节点按方向连接，先对输入做可核实性检查，再将通过检查的信息用于决策；它并不主张信息越多就必然越好。", "reviewer": "test-fixture-author", "decision": "approved", "rationale": "已人工查看本测试 SVG，并核对三个节点及两条方向关系。"}
        figure["interpretation"]["reviewed_content_sha256"] = COVERAGE.figure_review_sha256(figure)
        self.run_case(docs, 0)

    def test_changed_figure_asset_fails(self):
        docs = fixture()
        add_figure(docs)
        docs["figure.svg"] += "changed"
        self.run_case(docs, 2, "figure_asset")

    def test_uninventoried_image_placeholder_blocks_release(self):
        docs = fixture()
        docs["source-map.json"]["paragraphs"][1]["content_kind"] = "figure_placeholder"
        report = self.run_case(docs, 3)
        self.assertEqual(report["source_reviews"]["unresolved_placeholders"], ["p0001"])

    def test_no_figure_inventory_attestation_blocks_release(self):
        docs = fixture()
        docs["source-map.json"].pop("figure_inventory_review")
        report = self.run_case(docs, 3)
        self.assertFalse(report["source_reviews"]["figure_inventory_complete"])

    def test_malformed_id_type_rejected_with_report(self):
        docs = fixture()
        docs["content-ledger.json"]["items"][0]["chapter"] = []
        self.run_case(docs, 2, "schema")

    def test_figure_item_cannot_pass_without_asset_inventory(self):
        docs = fixture()
        docs["content-ledger.json"]["items"][0]["type"] = "figure"
        docs["source-map.json"]["ledger_inventory_sha256"] = COVERAGE.inventory_sha256(docs["content-ledger.json"]["items"])
        sign_fixture(docs)
        report = self.run_case(docs, 3)
        self.assertEqual(report["source_reviews"]["figure_items_without_assets"], ["i0001"])
        self.assertEqual(report["metrics"]["book"]["covered_items"], 9)

    def test_literal_image_placeholder_in_source_is_detected(self):
        docs = fixture()
        p = docs["source-map.json"]["paragraphs"][1]
        marker = "〔图字:00008〕"
        text = docs["book.txt"]
        text = text[:p["start"]] + marker + text[p["start"] + len(marker):]
        docs["book.txt"] = text
        docs["source-map.json"]["source"]["sha256"] = COVERAGE.sha256(text.encode())
        p["sha256"] = COVERAGE.sha256(text[p["start"]:p["end"]].encode())
        sign_fixture(docs)
        report = self.run_case(docs, 3)
        self.assertEqual(report["source_reviews"]["unresolved_placeholders"], ["p0001"])

    def test_absolute_private_asset_path_is_supported(self):
        docs = fixture()
        figure = add_figure(docs)
        with tempfile.TemporaryDirectory(prefix="private-source-") as temp:
            asset = Path(temp) / "figure.svg"
            asset.write_text(docs["figure.svg"])
            figure["asset_path"] = str(asset)
            sign_fixture(docs)
            report = self.run_case(docs, 3)
            self.assertTrue(report["machine_pass"])

    def test_figure_interpretation_placeholder_does_not_count(self):
        docs = fixture()
        figure = add_figure(docs)
        figure["interpretation"] = {"text": "[图片]", "reviewer": "test-fixture-author", "decision": "approved", "rationale": "此签名不能让占位变成图意。"}
        figure["interpretation"]["reviewed_content_sha256"] = COVERAGE.figure_review_sha256(figure)
        report = self.run_case(docs, 3)
        self.assertEqual(report["metrics"]["book"]["covered_items"], 9)

    def test_weak_chapter_cannot_hide_behind_book_ninety_percent(self):
        docs = fixture()
        source = docs["source-map.json"]
        boundary = source["paragraphs"][3]["start"]
        source["chapters"][1]["end"] = boundary
        source["chapters"][2]["start"] = boundary
        for paragraph in source["paragraphs"][3:6]:
            paragraph["chapter"] = "c02"
        for section in source["sections"][3:6]:
            section["chapter"] = "c02"
        for item in docs["content-ledger.json"]["items"][2:5]:
            item["chapter"] = "c02"
        for unit in docs["deepread.json"]["units"][2:5]:
            unit["chapter"] = "c02"
        docs["content-ledger.json"]["items"][1].update(status="partial", exclusion_reason="仍缺方法边界")
        source["ledger_inventory_sha256"] = COVERAGE.inventory_sha256(docs["content-ledger.json"]["items"])
        sign_fixture(docs)
        report = self.run_case(docs, 2, "chapter_coverage")
        self.assertEqual(report["metrics"]["book"]["ratio"], .9)
        self.assertEqual(report["metrics"]["chapters"]["c01"]["ratio"], .5)

    def test_empty_critical_inventory_is_not_vacuously_complete(self):
        docs = fixture()
        docs["content-ledger.json"]["items"][0]["critical"] = False
        docs["source-map.json"]["ledger_inventory_sha256"] = COVERAGE.inventory_sha256(docs["content-ledger.json"]["items"])
        sign_fixture(docs)
        self.run_case(docs, 2, "empty_critical_denominator")


if __name__ == "__main__":
    unittest.main()

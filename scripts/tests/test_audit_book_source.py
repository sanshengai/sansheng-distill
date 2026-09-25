import importlib.util
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "audit_book_source.py"
SPEC = importlib.util.spec_from_file_location("audit_book_source", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SourceAuditTest(unittest.TestCase):
    def test_missing_printed_pages_and_duplicate_scan_are_flagged(self):
        a = "这是第一段经营分析，有独立细节。" * 12
        b = "这是五年计划的论证，有企业案例。" * 12
        result = MODULE.inspect_pages([f"{a}\n145", f"{b}\n148", f"{b}\n148", "新章节" * 25 + "\n149"])
        self.assertEqual(result["printed_page_jumps"][0]["printed_before"], 145)
        self.assertTrue(any(x["pdf_pages"] == [2, 3] for x in result["near_duplicate_pages"]))

    def test_empty_document_and_low_text_are_visible(self):
        self.assertEqual(MODULE.inspect_pages([])["errors"], ["PDF has no pages"])
        self.assertEqual(MODULE.inspect_pages(["封面"])["low_text_pages"][0]["pdf_page"], 1)


if __name__ == "__main__":
    unittest.main()

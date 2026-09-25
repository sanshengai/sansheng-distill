#!/usr/bin/env python3
"""Read-only PDF preflight: flag printed-page jumps, repeated scans, and sparse pages.

This is a triage tool. A clean report does not certify completeness; a flagged
page must be compared with the actual scan before any editorial decision.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path


def normalize(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKC", text) if c.isalnum())


def printed_number(text: str) -> int | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    candidates = []
    for line in lines[:4] + lines[-5:]:
        m = re.fullmatch(r"(?:[-—·•]\s*)?([1-9]\d{0,3})(?:\s*[-—·•])?", line)
        if m:
            candidates.append(int(m.group(1)))
    return candidates[-1] if candidates else None


def inspect_pages(texts: list[str], *, min_chars: int = 80, duplicate_ratio: float = .90) -> dict:
    if not texts:
        return {"page_count": 0, "printed_page_jumps": [], "near_duplicate_pages": [],
                "low_text_pages": [], "errors": ["PDF has no pages"]}
    normalized = [normalize(t) for t in texts]
    printed = [printed_number(t) for t in texts]
    jumps = []
    prior = None
    for i, n in enumerate(printed):
        if n is None:
            continue
        if prior is not None and (n <= prior[1] or n - prior[1] > i - prior[0]):
            jumps.append({"pdf_page_before": prior[0] + 1, "printed_before": prior[1],
                          "pdf_page_after": i + 1, "printed_after": n})
        prior = (i, n)
    duplicates = []
    for i, left in enumerate(normalized):
        if len(left) < 100:
            continue
        for j in range(i + 1, min(i + 4, len(texts))):
            right = normalized[j]
            if len(right) < 100 or min(len(left), len(right)) / max(len(left), len(right)) < .75:
                continue
            ratio = difflib.SequenceMatcher(None, left, right, autojunk=False).ratio()
            if ratio >= duplicate_ratio:
                duplicates.append({"pdf_pages": [i + 1, j + 1], "similarity": round(ratio, 3)})
    low = [{"pdf_page": i + 1, "text_chars": len(s)} for i, s in enumerate(normalized)
           if len(s) < min_chars]
    return {"page_count": len(texts), "printed_page_jumps": jumps,
            "near_duplicate_pages": duplicates, "low_text_pages": low,
            "errors": []}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--json-out", type=Path)
    ap.add_argument("--min-chars", type=int, default=80)
    ap.add_argument("--duplicate-ratio", type=float, default=.90)
    args = ap.parse_args(argv)
    try:
        import pymupdf
        with pymupdf.open(args.pdf) as doc:
            texts = [page.get_text() for page in doc]
    except (ImportError, OSError, ValueError) as exc:
        print(f"无法读取 PDF：{exc}", file=sys.stderr)
        return 3
    report = inspect_pages(texts, min_chars=args.min_chars, duplicate_ratio=args.duplicate_ratio)
    report["source"] = str(args.pdf)
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json_out:
        args.json_out.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 2 if report["errors"] or report["printed_page_jumps"] or report["near_duplicate_pages"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

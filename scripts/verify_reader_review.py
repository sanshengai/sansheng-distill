"""Validate source-bound reader review records; never manufacture a review signature."""
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from verify_book_review_scope import validate_review_scope


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def validate_reader_review(distill_path, source_path, receipt_path):
    errors = []
    if not source_path:
        return ["[reader] 必须提供 --source，不能脱离来源签收"]
    try:
        raw = Path(distill_path).read_bytes()
        source = Path(source_path).read_bytes()
        data = json.loads(raw)
        receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
        if not isinstance(receipt, dict) or not isinstance(data, dict):
            raise ValueError("正文与收据必须为对象")
    except (OSError, ValueError, TypeError) as exc:
        return [f"[reader] 审阅记录不可读取: {exc}"]
    if data.get("quality_profile") != "reader":
        errors.append("[reader] 正文未显式选择 reader 档")
    if not source.strip():
        errors.append("[reader] 来源不得为空")
    if receipt.get("schema") not in {"reader-review-v1", "reader-review-v2"}:
        errors.append("[reader] 审阅记录 schema 必须为 reader-review-v2（v1仅兼容旧收据）")
    if receipt.get("schema") == "reader-review-v2":
        errors.extend(validate_review_scope(receipt.get("review_scope")))
    for key, expected in (("distill_sha256", sha256(raw)), ("source_sha256", sha256(source))):
        if receipt.get(key) != expected:
            errors.append(f"[reader] {key} 与当前输入不符")
    for key in ("authorization", "reviewer", "reviewed_at", "review_evidence"):
        if not isinstance(receipt.get(key), str) or not receipt[key].strip():
            errors.append(f"[reader] 缺 {key}")
    try:
        reviewed_at = datetime.fromisoformat(receipt.get("reviewed_at", "").replace("Z", "+00:00"))
        if reviewed_at.tzinfo is None:
            raise ValueError("时间必须带时区")
    except (ValueError, TypeError, AttributeError):
        errors.append("[reader] reviewed_at 必须为带时区的 ISO 时间")
    # Counts must be actual integers: False is not a signed zero.
    if type(receipt.get("unresolved_material_errors")) is not int or receipt["unresolved_material_errors"] != 0:
        errors.append("[reader] 未解决实质错误必须明确为整数 0")
    chapters = data.get("chapters")
    rows = receipt.get("chapters")
    if not isinstance(chapters, list) or not chapters or not isinstance(rows, list) or not rows:
        return errors + ["[reader] 正文与章节审阅集合均不得为空"]
    ids = [str(ch.get("no")) for ch in chapters if isinstance(ch, dict)]
    row_ids = [str(row.get("no")) for row in rows if isinstance(row, dict)]
    if len(ids) != len(chapters) or len(set(ids)) != len(ids) or "None" in ids:
        errors.append("[reader] 正文章节身份缺失或重复")
    if len(row_ids) != len(rows) or len(set(row_ids)) != len(row_ids) or set(ids) != set(row_ids):
        errors.append("[reader] 章节审阅集合缺项、多项或重复")
    by_no = {str(row.get("no")): row for row in rows if isinstance(row, dict)}
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        no = str(chapter.get("no"))
        body = chapter.get("narrative")
        if not isinstance(body, str) or not re.search(r"[^\W_]", body, re.UNICODE):
            errors.append(f"[reader] 第{no}章正文为空或无有效文字")
            continue
        row = by_no.get(no, {})
        if row.get("narrative_sha256") != sha256(body.encode("utf-8")):
            errors.append(f"[reader] 第{no}章正文哈希不符")
        if row.get("fidelity") != "reviewed" or not isinstance(row.get("evidence"), str) or not row["evidence"].strip():
            errors.append(f"[reader] 第{no}章未完成来源忠实审阅或缺证据定位")
        coverage = row.get("coverage")
        if not isinstance(coverage, dict):
            errors.append(f"[reader] 第{no}章缺主论证/案例/反例/限制审阅")
            continue
        for facet in ("argument", "cases", "counterexamples", "limits"):
            check = coverage.get(facet)
            if not isinstance(check, dict):
                errors.append(f"[reader] 第{no}章缺 {facet} 审阅")
                continue
            allowed = {"reviewed"} if facet == "argument" else {"reviewed", "not_applicable"}
            if check.get("status") not in allowed or not isinstance(check.get("note"), str) or not check["note"].strip():
                errors.append(f"[reader] 第{no}章 {facet} 未审或缺裁决依据")
    return errors

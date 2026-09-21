#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jev_support_check.py —— 原文支撑度第二意见（Jev Choice direct / partial / contradicted），只出报告，不改产物。

references/source-audit.md §3 的 `records[]` 每条是「≤150 字原文片段 source_excerpt + 最终陈述 assertion + support」，
support 现在由跑管线的主 Agent 自审自定。本脚本把每条（或任意「片段 + 陈述」对）交给 Jev 独立判一次，
输出第二意见报告：逐条 Jev 判定、置信度、与现有 support 的一致率、分歧清单。source-audit.json 本身一字不动。

site_id=distill.source.support（档位/key/台账在 _ops/jev/registry.yaml）。台账 meta：baseline=现有 support、jev=Jev 判定。
接入层缺失 / 未启用 / 无 key → 打印原因退出（退出码 0，不写文件）；单条失败只记 error，不抛。

用法：
  python3 jev_support_check.py --audit 读书蒸馏/<slug>/source-audit.json --out /tmp/support-check.json [--max 300] [--facet claim]
  python3 jev_support_check.py --pairs pairs.jsonl --out …      # 每行 {id, source_excerpt, assertion[, support]}
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

BJ = timezone(timedelta(hours=8))
SITE_ID = "distill.source.support"
SUPPORT_LEVELS = ("direct", "partial", "contradicted")
CRITERIA = {
    "direct": "原文片段直接、完整地说了这条陈述的意思：主体、结论、数字（若有）都能在片段里对上，没有添加片段没说的东西。",
    "partial": "原文片段支撑陈述的一部分或方向一致，但陈述比片段多了推断、概括、限定或数字，或措辞与片段不完全对得上；片段没有反对它。",
    "contradicted": "原文片段与陈述在主体、结论、方向或关键数字上相反或冲突。",
}
INSTRUCTIONS = ("`source_excerpt` 是书中逐字原文片段，`assertion` 是最终产物里对它的陈述。只依据片段本身判断片段对陈述的支撑程度，"
                "不引入片段之外的常识；陈述比片段多出的内容一律不算被支撑。")
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "_ops" / "jev"))
try:
    from client import JevClient, RegistryError  # noqa: E402
except ImportError:  # 接入层被删 → 本脚本无事可做
    JevClient = None  # type: ignore[assignment]
    RegistryError = RuntimeError  # type: ignore[assignment,misc]


def ask_record(jev, rec: dict) -> dict:
    baseline = rec.get("support") if rec.get("support") in SUPPORT_LEVELS else "unknown"
    meta = {"id": rec.get("id"), "facet": rec.get("facet"), "baseline": baseline}
    r = jev.ask(state={"source_excerpt": str(rec.get("source_excerpt") or "")[:600],
                       "assertion": str(rec.get("assertion") or "")[:600]},
                questions={"support": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": CRITERIA}},
                meta=meta, log=False)
    if not r.ok:
        return {"id": rec.get("id"), "baseline": baseline, "error": r.error}
    ans = r.answers.get("support") or {}
    choice = r.choice("support")
    if choice not in SUPPORT_LEVELS:
        jev.log(r, {**meta, "jev": "invalid"})
        return {"id": rec.get("id"), "baseline": baseline, "error": f"invalid_choice:{choice}"}
    probs = {k: round(float(v), 3) for k, v in (ans.get("probabilities") or {}).items() if k in SUPPORT_LEVELS}
    jev.log(r, {**meta, "jev": choice})
    return {"id": rec.get("id"), "facet": rec.get("facet"), "target": rec.get("target"), "baseline": baseline,
            "jev": choice, "confidence": round(float(ans.get("confidence") or 0.0), 3), "probabilities": probs,
            "source_excerpt": str(rec.get("source_excerpt") or "")[:150], "assertion": str(rec.get("assertion") or "")[:200]}


def select_records(records: list, *, max_n: int, facet: str | None, include_audit_flags: bool = False, seed: int = 7) -> list:
    """按 facet 过滤后，先把非 direct 的全取（少数类别更值得复核），再随机补 direct 到 max_n。
    target.kind=audit_flag 的记录默认跳过：它的 assertion 是「需外证复核」这类审计备注，不是对原文内容的陈述，
    问支撑度没有意义（《思考，快与慢》回放里 39 条 audit_flag 一致率 12/39，全是这个原因）。"""
    rows = [r for r in records if (not facet or r.get("facet") == facet)
            and (include_audit_flags or (r.get("target") or {}).get("kind") != "audit_flag")]
    if len(rows) <= max_n:
        return rows
    minority = [r for r in rows if r.get("support") != "direct"]
    majority = [r for r in rows if r.get("support") == "direct"]
    random.Random(seed).shuffle(majority)
    picked = minority[:max_n] + majority[:max(0, max_n - len(minority))]
    order = {id(r): i for i, r in enumerate(rows)}
    return sorted(picked, key=lambda r: order[id(r)])


def run(records: list, jev, *, concurrency: int = 8, deadline: float = 600.0, asker=ask_record) -> dict:
    t0 = time.time()
    results: list = []
    with cf.ThreadPoolExecutor(concurrency) as ex:
        futs = {ex.submit(asker, jev, rec): rec for rec in records}
        try:
            for fut in cf.as_completed(futs, timeout=deadline):
                results.append(fut.result())
        except cf.TimeoutError:
            pass
        for fut, rec in futs.items():
            if not fut.done():
                fut.cancel()
                results.append({"id": rec.get("id"), "baseline": rec.get("support"), "error": "deadline"})
    ok = [r for r in results if "error" not in r]
    cmp_rows = [r for r in ok if r["baseline"] in SUPPORT_LEVELS]
    by = {lvl: sum(1 for r in ok if r["jev"] == lvl) for lvl in SUPPORT_LEVELS}
    confusion = {b: {j: sum(1 for r in cmp_rows if r["baseline"] == b and r["jev"] == j) for j in SUPPORT_LEVELS} for b in SUPPORT_LEVELS}
    disagree = [r for r in cmp_rows if r["jev"] != r["baseline"]]
    disagree.sort(key=lambda r: (SUPPORT_LEVELS.index(r["jev"]) - SUPPORT_LEVELS.index(r["baseline"]), -r["confidence"]), reverse=True)
    return {
        "schema_version": "jev-support-check-v1", "site": SITE_ID, "mode": getattr(jev, "mode", "unknown"),
        "generated_at": datetime.now(BJ).isoformat(timespec="seconds"),
        "total": len(records), "asked": len(ok), "errors": len(results) - len(ok),
        "jev_counts": by, "baseline_pairs": len(cmp_rows),
        "agree_with_baseline": sum(1 for r in cmp_rows if r["jev"] == r["baseline"]),
        "confusion_baseline_x_jev": confusion,
        "elapsed_s": round(time.time() - t0, 1),
        "disagreements": disagree,
        "results": sorted(results, key=lambda r: (("error" in r), str(r.get("id")))),
    }


def load_records(audit: str | None, pairs: str | None) -> list:
    if audit:
        doc = json.loads(Path(audit).read_text(encoding="utf-8"))
        return list(doc.get("records") or [])
    return [json.loads(l) for l in Path(pairs).read_text(encoding="utf-8").splitlines() if l.strip()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--audit", help="source-audit.json（读 records[]）")
    g.add_argument("--pairs", help="jsonl，每行 {id, source_excerpt, assertion[, support]}")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max", type=int, default=300)
    ap.add_argument("--facet", help="只核此 facet（claim/mechanism/case/experiment/number/boundary/verbatim）")
    ap.add_argument("--include-audit-flags", action="store_true", help="连 target.kind=audit_flag 的审计备注记录也核（默认跳过）")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--deadline", type=float, default=600.0)
    a = ap.parse_args(argv)
    if JevClient is None:
        print("[jev_support_check] 接入层 _ops/jev 缺失，本脚本只做第二意见，无事可做，退出"); return 0
    try:
        jev = JevClient(SITE_ID, timeout=20.0)
    except RegistryError as e:
        print(f"[jev_support_check] 接入层登记错误，退出：{e}"); return 0
    if not jev.enabled:
        print(f"[jev_support_check] 接入层 mode={jev.mode} 或无 key，退出（不写文件）"); return 0
    records = select_records(load_records(a.audit, a.pairs), max_n=a.max, facet=a.facet, include_audit_flags=a.include_audit_flags)
    doc = run(records, jev, concurrency=a.concurrency, deadline=a.deadline)
    doc["inputs"] = {"audit": a.audit, "pairs": a.pairs, "facet": a.facet}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[jev_support_check] mode={doc['mode']} 核 {doc['total']} 答到 {doc['asked']} 错 {doc['errors']} "
          f"Jev 分布 {doc['jev_counts']} | 与现有 support 可比 {doc['baseline_pairs']} 一致 {doc['agree_with_baseline']} "
          f"用时 {doc['elapsed_s']}s → {a.out}")
    for r in doc["disagreements"][:8]:
        print(f"  {r['baseline']}→{r['jev']} conf={r['confidence']:.2f} [{r['id']}] {r['assertion'][:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

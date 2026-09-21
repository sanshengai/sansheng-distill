#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jev_merge_claims.py —— 观点归并第二意见（Jev Noul「两条是否同一主张」），只出建议表，不改任何产物。

把 references/creator-craft.md §4 写死的三条归并判据（同话题但主张不同 → 不合并 / 一条是另一条的例子 → 不合并 /
拿不准 → 不合并）做成独立批量步骤：

  1. 字面预合并：同主题内字符二元组 Dice ≥ --premerge（默认 0.12，Hormozi 标定值）直接并成字面族，不问模型；
  2. 灰区候选对：Dice ∈ [--min-dice, --premerge) 的对按 Dice 降序取前 --max-pairs 对，逐对问 Jev Noul；
  3. 输出建议归并表 JSON（字面族 + 每对 noul/判定/baseline + Jev 建议合并的并查集族），供人工比对。

baseline（台账对照）：给了 --families（已归并结果，如 Gemini Batch 产物）→ 两条同族 = same / 不同族 = different；
没给 → 字面层判断（灰区一律 different）。
site_id=distill.claims.merge（档位/key/台账在 _ops/jev/registry.yaml）。shadow = 只产出建议文件；
接入层缺失 / 未启用 / 无 key → 打印原因退出（退出码 0，不写文件）；单对失败只记 error，不抛。

用法：
  python3 jev_merge_claims.py --claims 03_工作数据/claims.jsonl --out /tmp/merge-suggest.json
  python3 jev_merge_claims.py --claims claims.jsonl --families families.jsonl --max-pairs 300 --sample balanced --out …
claims.jsonl 每行至少 {claim_id, text_zh}，可带 theme_id（有则只在同主题内配对）；families.jsonl 每行 {family_id, claim_ids}。
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import random
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

BJ = timezone(timedelta(hours=8))
SITE_ID = "distill.claims.merge"
NOUL_SAME_MIN = 0.70          # Noul ≥ 此值判「同一主张」；「拿不准就不合并」→ 阈值偏高，待复盘标定
PREMERGE_DICE = 0.12          # creator-craft.md §4：0.12 合 22%、0.10 开始错并
MIN_DICE = 0.04               # 灰区下沿；再低的对字面上几乎无关，不值得问
INSTRUCTIONS = (
    "`a` 与 `b` 是同一位创作者的两条观点陈述，判断它们是否是**同一个主张**（可以并成一族、只保留一条代表句而不丢信息）。"
    "判据写死：同一话题但主张不同 → 否；一条只是另一条的例子/案例/数字佐证 → 否；一条比另一条多出实质性的限定或新结论 → 否；"
    "拿不准 → 否。只有两条换个说法在讲同一件事、同一结论时才判是。"
)
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "_ops" / "jev"))
try:
    from client import JevClient, RegistryError  # noqa: E402
except ImportError:  # 接入层被删 → 本脚本无事可做
    JevClient = None  # type: ignore[assignment]
    RegistryError = RuntimeError  # type: ignore[assignment,misc]


# ---------- 字面层 ----------
def bigrams(text: str) -> set:
    t = "".join(ch for ch in (text or "") if not ch.isspace())
    return {t[i:i + 2] for i in range(len(t) - 1)} if len(t) > 1 else set()


def dice(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return 2 * len(a & b) / (len(a) + len(b))


def is_same(noul: float) -> bool:
    """Noul 阈值单一真源；测试用反例守边界。"""
    return noul >= NOUL_SAME_MIN


class UnionFind:
    def __init__(self):
        self.p: dict = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)

    def groups(self) -> list:
        g = defaultdict(list)
        for x in list(self.p):
            g[self.find(x)].append(x)
        return sorted((sorted(v) for v in g.values() if len(v) > 1), key=lambda v: v[0])


def lexical_pass(claims: list, *, premerge: float, min_dice: float) -> tuple:
    """同主题内两两 Dice：≥premerge 入字面族；[min_dice, premerge) 入灰区候选。返回 (字面族列表, 候选对列表[(dice,a,b)])。"""
    by_theme = defaultdict(list)
    for c in claims:
        by_theme[c.get("theme_id") or "_"].append(c)
    bg = {c["claim_id"]: bigrams(c.get("text_zh") or c.get("text") or "") for c in claims}
    uf, gray = UnionFind(), []
    for group in by_theme.values():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i]["claim_id"], group[j]["claim_id"]
                d = dice(bg[a], bg[b])
                if d >= premerge:
                    uf.union(a, b)
                elif d >= min_dice:
                    gray.append((round(d, 4), a, b))
    gray.sort(key=lambda t: (-t[0], t[1], t[2]))
    return uf.groups(), gray


def family_index(families: list) -> dict:
    idx = {}
    for f in families:
        for cid in f.get("claim_ids") or []:
            idx[cid] = f["family_id"]
    return idx


def baseline_of(a: str, b: str, fam_idx: dict | None) -> str:
    if fam_idx is None:
        return "different"  # 灰区在字面层没并
    fa, fb = fam_idx.get(a), fam_idx.get(b)
    if fa is None or fb is None:
        return "unknown"
    return "same" if fa == fb else "different"


def select_pairs(gray: list, *, max_pairs: int, sample: str, fam_idx: dict | None, seed: int = 7) -> list:
    """top = 按 Dice 降序取前 N；balanced（需要 families）= 同族 / 异族各取一半（同族不够就全取），便于回放算两边。"""
    if sample == "balanced" and fam_idx is not None:
        same = [t for t in gray if baseline_of(t[1], t[2], fam_idx) == "same"]
        diff = [t for t in gray if baseline_of(t[1], t[2], fam_idx) == "different"]
        rng = random.Random(seed)
        rng.shuffle(diff)
        half = max_pairs // 2
        picked = same[:half] + diff[:max_pairs - min(len(same), half)]
        return sorted(picked, key=lambda t: -t[0])[:max_pairs]
    return gray[:max_pairs]


# ---------- Jev 层 ----------
def ask_pair(jev, texts: dict, d: float, a: str, b: str, fam_idx: dict | None) -> dict:
    baseline = baseline_of(a, b, fam_idx)
    meta = {"a": a, "b": b, "dice": d, "baseline": baseline}
    r = jev.ask(state={"a": texts[a][:600], "b": texts[b][:600]},
                questions={"same_claim": {"type": "noul", "instructions": INSTRUCTIONS}}, meta=meta, log=False)
    if not r.ok:
        return {"a": a, "b": b, "dice": d, "baseline": baseline, "error": r.error}
    noul = r.noul("same_claim", 0.0)
    jev_dec = "same" if is_same(noul) else "different"
    jev.log(r, {**meta, "jev": jev_dec})
    return {"a": a, "b": b, "dice": d, "noul": round(noul, 3), "jev": jev_dec, "baseline": baseline,
            "text_a": texts[a][:120], "text_b": texts[b][:120]}


def run(claims: list, jev, *, families: list | None = None, premerge: float = PREMERGE_DICE, min_dice: float = MIN_DICE,
        max_pairs: int = 300, sample: str = "top", concurrency: int = 8, deadline: float = 600.0, asker=ask_pair) -> dict:
    t0 = time.time()
    texts = {c["claim_id"]: (c.get("text_zh") or c.get("text") or "") for c in claims}
    fam_idx = family_index(families) if families is not None else None
    lex_groups, gray = lexical_pass(claims, premerge=premerge, min_dice=min_dice)
    pairs = select_pairs(gray, max_pairs=max_pairs, sample=sample, fam_idx=fam_idx)
    results: list = []
    with cf.ThreadPoolExecutor(concurrency) as ex:
        futs = {ex.submit(asker, jev, texts, d, a, b, fam_idx): (d, a, b) for d, a, b in pairs}
        try:
            for fut in cf.as_completed(futs, timeout=deadline):
                results.append(fut.result())
        except cf.TimeoutError:
            pass
        for fut, (d, a, b) in futs.items():
            if not fut.done():
                fut.cancel()
                results.append({"a": a, "b": b, "dice": d, "baseline": baseline_of(a, b, fam_idx), "error": "deadline"})
    ok = [r for r in results if "error" not in r]
    uf = UnionFind()
    for g in lex_groups:
        for x in g[1:]:
            uf.union(g[0], x)
    for r in ok:
        if r["jev"] == "same":
            uf.union(r["a"], r["b"])
    cmp_rows = [r for r in ok if r["baseline"] in ("same", "different")]
    results.sort(key=lambda r: (("error" in r), -r.get("noul", 0.0)))
    return {
        "schema_version": "jev-merge-suggest-v1", "site": SITE_ID, "mode": getattr(jev, "mode", "unknown"),
        "generated_at": datetime.now(BJ).isoformat(timespec="seconds"),
        "thresholds": {"premerge_dice": premerge, "min_dice": min_dice, "noul_same_min": NOUL_SAME_MIN},
        "claims": len(claims), "lexical_groups": len(lex_groups), "gray_pairs": len(gray), "asked": len(ok),
        "errors": len(results) - len(ok), "jev_same": sum(1 for r in ok if r["jev"] == "same"),
        "baseline_pairs": len(cmp_rows), "agree_with_baseline": sum(1 for r in cmp_rows if r["jev"] == r["baseline"]),
        "elapsed_s": round(time.time() - t0, 1),
        "lexical_families": lex_groups,
        "pairs": results,
        "suggested_families": uf.groups(),
    }


def _jlines(path: Path) -> list:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--claims", required=True)
    ap.add_argument("--families", help="已归并结果 families.jsonl（回放对照用，作 baseline）")
    ap.add_argument("--out", required=True)
    ap.add_argument("--theme", help="只处理此 theme_id")
    ap.add_argument("--premerge", type=float, default=PREMERGE_DICE)
    ap.add_argument("--min-dice", type=float, default=MIN_DICE)
    ap.add_argument("--max-pairs", type=int, default=300)
    ap.add_argument("--sample", choices=["top", "balanced"], default="top")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--deadline", type=float, default=600.0)
    a = ap.parse_args(argv)
    if JevClient is None:
        print("[jev_merge_claims] 接入层 _ops/jev 缺失，本脚本只做第二意见，无事可做，退出"); return 0
    try:
        jev = JevClient(SITE_ID, timeout=20.0)
    except RegistryError as e:
        print(f"[jev_merge_claims] 接入层登记错误，退出：{e}"); return 0
    if not jev.enabled:
        print(f"[jev_merge_claims] 接入层 mode={jev.mode} 或无 key，退出（不写文件）"); return 0
    claims = _jlines(Path(a.claims))
    if a.theme:
        claims = [c for c in claims if c.get("theme_id") == a.theme]
    families = _jlines(Path(a.families)) if a.families else None
    doc = run(claims, jev, families=families, premerge=a.premerge, min_dice=a.min_dice, max_pairs=a.max_pairs,
              sample=a.sample, concurrency=a.concurrency, deadline=a.deadline)
    doc["inputs"] = {"claims": str(a.claims), "families": a.families, "theme": a.theme}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[jev_merge_claims] mode={doc['mode']} claims {doc['claims']} 字面族 {doc['lexical_groups']} 灰区对 {doc['gray_pairs']} "
          f"问 {doc['asked']} 错 {doc['errors']} Jev 判同 {doc['jev_same']}"
          + (f" | 与 baseline 可比 {doc['baseline_pairs']} 一致 {doc['agree_with_baseline']}" if doc["baseline_pairs"] else "")
          + f" 用时 {doc['elapsed_s']}s → {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""批量交付闸(v0.5,2026-07-27):一批书蒸完、上站**之前**跑,给出「这批能不能上线」的总裁决。

立法背景 -- 2026-07-26 用 Antigravity(Gemini 3.6 Flash)蒸格拉德威尔「6 本」的实测事故:
  · 6 个 slug 里 2 本(眨眼之间 / 逆转)只跑到 Step0 就停了,只有 book.txt + diagnose.json
  · 但网站作品集页照着 6 本的名单挂了入口 → 线上 2 个 404
  · 另 4 本产物残缺(占位符残留 / 占位封面 / 缺 8 个顶层键),Step7 一次都没跑
单本 verify_page.py 管不了这类事故 -- 它只回答「这一本合不合格」,
回答不了「**这一批该有的都在吗**」。本脚本补的就是这层:
  ① 预期名单 vs 实际产物逐一核对(少蒸一本当场报,不靠人肉数)
  ② 逐本调 verify_page.py 收退出码(禁跳 Step7)
  ③ 中间态残留 / enrich 缺失等交付卫生告警

用法:
  python verify_batch.py --data-root "$DATA" --slugs yinbaodian,zhanyan-zhijian,yilei,nizhuan
  python verify_batch.py --data-root "$DATA" --slugs-from booklist.txt --fast
  python verify_batch.py --data-root "$DATA" --slugs-from psychology.txt --require-domain psychology

退出码:0 = 全部可上线 / 1 = 有书未过闸 / 2 = 参数或环境错
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

VERIFY = Path(__file__).with_name("verify_page.py")
# 通用交付必需产物；book.txt 通常属输入侧，但 psychology 严格批次会额外要求并传给 --source。
REQUIRED_ARTIFACTS = ("distill.json", "{slug}.html")
# 交付卫生:存在即告警(不阻断)。只列 SKILL.md 批量模式**明确要求合并后清理**的中间态 --
#   `.bak`(update_index 每次写前自动备份)与 `_verify.png`(Step7 正常产物)都是设计行为,不告警,免得淹没真信号。
STALE_GLOBS = ("_pass2_g*.json",)


def _read_slugs(a) -> list:
    if a.slugs:
        return [s.strip() for s in a.slugs.split(",") if s.strip()]
    if a.slugs_from:
        p = Path(a.slugs_from)
        if not p.exists():
            print(f"[环境] 名单文件不存在: {p}", file=sys.stderr)
            sys.exit(2)
        return [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.strip().startswith("#")]
    print("[参数] 必须给 --slugs 或 --slugs-from:交付闸的前提是**先声明这批该有哪些书**", file=sys.stderr)
    sys.exit(2)


def check_one(root: Path, slug: str, fast: bool, required_domain: str | None = None) -> dict:
    """返回 {slug, ok, blockers[], warns[]}。ok=False 即这本不许上线。"""
    d = root / slug
    r = {"slug": slug, "ok": False, "blockers": [], "warns": []}
    if not d.is_dir():
        r["blockers"].append("书目录不存在(这本**根本没蒸**,别把它挂上站)")
        return r
    # ① 产物齐备
    missing = [f.format(slug=slug) for f in REQUIRED_ARTIFACTS
               if not (d / f.format(slug=slug)).exists()]
    if missing:
        stage = "只跑到 Step0" if not (d / "distill.json").exists() else "停在 Step6 之前"
        r["blockers"].append(f"缺产物 {missing}({stage},管线没跑完)")
        return r
    source_path = d / "book.txt"
    if required_domain == "psychology" and not source_path.is_file():
        r["blockers"].append("心理学严格批次缺 book.txt，无法执行原文 grounding(--source)")
        return r
    # ② distill.json 可解析
    try:
        data = json.loads((d / "distill.json").read_text(encoding="utf-8"))
    except Exception as e:
        r["blockers"].append(f"distill.json 解析失败: {e}")
        return r
    n_ch = len(data.get("chapters") or [])
    # ③ Step7 出厂验证(禁跳)
    cmd = [sys.executable, str(VERIFY), str(d / f"{slug}.html"), "--distill", str(d / "distill.json")]
    if required_domain:
        cmd.extend(["--require-domain", required_domain])
    if required_domain == "psychology":
        cmd.extend(["--source", str(source_path)])
    if fast:
        cmd.append("--skip-interact")
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except Exception as e:
        r["blockers"].append(f"verify_page 调起失败: {e}")
        return r
    if p.returncode != 0:
        lines = [ln for ln in (p.stdout or "").splitlines() if ln.strip()]
        head = "; ".join(lines[:3]) + ("…" if len(lines) > 3 else "")
        r["blockers"].append(f"verify_page exit {p.returncode}({len(lines)} 条违规): {head}")
    # ④ 交付卫生(告警,不阻断)
    if not (d / "enrich.json").exists():
        r["warns"].append("无 enrich.json(Step3 联网增补整步没跑;确属抓不到应产 null 键的文件)")
    stale = [f.name for g in STALE_GLOBS for f in d.glob(g)]
    if stale:
        r["warns"].append(f"中间态残留 {stale[:5]}(合并后应清理,SKILL.md 批量模式)")
    r["ok"] = not r["blockers"]
    r["n_ch"] = n_ch
    return r


def main():
    ap = argparse.ArgumentParser(description="蒸馏批量交付闸:预期名单 vs 实际产物 + 逐本 Step7")
    ap.add_argument("--data-root", required=True, help="$DATA 数据根目录")
    ap.add_argument("--slugs", help="预期交付的 slug,逗号分隔")
    ap.add_argument("--slugs-from", dest="slugs_from", help="从文件读 slug 名单(一行一个,# 注释)")
    ap.add_argument("--fast", action="store_true",
                    help="逐本 verify 跳过 Playwright 冒烟(只跑静态 lint + 契约门禁);铺量前预检用,终审别带")
    ap.add_argument("--require-domain", choices=("psychology",),
                    help="把项目级严格域逐本传播给 verify_page；psychology 还强制 book.txt + --source")
    a = ap.parse_args()
    root = Path(a.data_root)
    if not root.is_dir():
        print(f"[环境] data-root 不存在: {root}", file=sys.stderr)
        return 2
    slugs = _read_slugs(a)
    print(f"预期交付 {len(slugs)} 本{'(fast:跳过冒烟)' if a.fast else ''}\n" + "-" * 72)

    results = [check_one(root, s, a.fast, a.require_domain) for s in slugs]
    for r in results:
        mark = "OK  " if r["ok"] else "FAIL"
        ch = f"{r.get('n_ch', 0)} 章" if r["ok"] or r.get("n_ch") else "--"
        print(f"[{mark}] {r['slug']:28} {ch}")
        for b in r["blockers"]:
            print(f"         ✗ {b}")
        for w in r["warns"]:
            print(f"         ! {w}")
    passed = [r for r in results if r["ok"]]
    failed = [r for r in results if not r["ok"]]
    print("-" * 72)
    print(f"可上线 {len(passed)}/{len(slugs)}" + (f" · 未过闸 {[r['slug'] for r in failed]}" if failed else ""))
    if failed:
        print("\n这批**不许整批上站**:未过闸的书要么补完管线、要么从上站名单里摘掉"
              "(名单留着而产物没有 = 线上 404)。")
        return 1
    warns = sum(len(r["warns"]) for r in results)
    print("全部过闸,可上站。" + (f"({warns} 条卫生告警,建议先清)" if warns else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

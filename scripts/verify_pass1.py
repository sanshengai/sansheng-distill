#!/usr/bin/env python3
"""Pass1 骨架门禁自检(随 skill 发布,带 utf-8 护栏)。

在 Step2·Pass1 产出 `distill.json` 骨架后、Pass2 详实转述之前运行,拦掉带病骨架进 Pass2。
用法:  python verify_pass1.py <distill.json> ; echo "退出码=$?"    (exit 0 全过 / 1 有违规)

为什么有这个脚本(2026-07-12 五作者批量复盘 A-7):
  Pass1 门禁原「内化无脚本」,agent 临跑现写打印 ✅/❌ 的助手脚本,在 Windows GBK 控制台
  触发 UnicodeEncodeError exit 1 = **假失败**(复盘中差点误杀 kk-2049)。**禁再临跑现写,统一用本脚本。**

实现:复用 `verify_page.lint_distill` 的已验证门禁逻辑(单一来源,不重复造轮子),只滤掉
  **Pass2 才产的字段**(narrative / excerpts / action_chain.detail / chapters.hook)——
  这些在 Pass1 阶段本就未产,缺失不算违规;Step7 的 `verify_page.py` 会在终稿再全量校验。
  故本脚本 = 「Pass1 可校验的骨架门禁」的早期闸,与 Step7 终检不重叠、不放宽。
"""
import argparse
import json
import sys
from pathlib import Path

# utf-8 护栏(根治 GBK 控制台 emoji/中文 UnicodeEncodeError 假失败;同 verify_page.py 顶部)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_page import lint_distill  # noqa: E402  复用已验证门禁(单一来源)

# Pass2 才产的字段:Pass1 阶段缺失属正常,不算违规(Step7 verify_page.py 会全量校验)。
# 这些标记词只出现在对应的 Pass2 字段违规文案里,不会误滤 Pass1 骨架违规(见 verify_page.lint_distill)。
PASS2_ONLY_MARKERS = ("narrative", "excerpts", "detail", "hook")


def pass1_violations(data: dict) -> list:
    """Pass1 阶段的骨架门禁违规 = 全量门禁去掉 Pass2 才产字段的违规。"""
    return [v for v in lint_distill(data) if not any(m in v for m in PASS2_ONLY_MARKERS)]


def main() -> int:
    ap = argparse.ArgumentParser(description="Pass1 骨架门禁自检(带 utf-8 护栏)")
    ap.add_argument("distill", help="distill.json 路径")
    args = ap.parse_args()
    try:
        data = json.loads(Path(args.distill).read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ 读取 distill.json 失败: {e}")
        return 2
    vs = pass1_violations(data)
    if vs:
        print(f"❌ Pass1 骨架门禁 {len(vs)} 处违规(须回补/重蒸后再进 Pass2):")
        for v in vs:
            print("  -", v)
        return 1
    print("✅ Pass1 骨架门禁全过,可进 Pass2 详实转述")
    return 0


if __name__ == "__main__":
    sys.exit(main())

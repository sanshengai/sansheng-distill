#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""深读稿中文标点归一化：中文语境里的半角标点 → 全角。

🔴 为什么需要这个：同一批 agent 写出来的稿子，标点习惯会分裂成两派 ——
实测 71 篇里 33 篇**全篇半角**（全角 0 处）、其余全篇全角，共 3,037 处。
半角逗号夹在中文字之间没有正确的字间距，页面上会挤成一团，
但它不影响任何数据校验，契约测试和防幻觉闸门都不会有症状。

🔴 唯一不能动的是英文原话 —— 那是逐字引用，里面的半角标点是原文的一部分。
所以所有替换规则都要求**至少一侧紧邻中文字符**，纯英文句子天然不匹配。

用法：
    python normalize_punct.py            # 全量修复
    python normalize_punct.py --check    # 只报告不修改（闸门用，有问题 exit 1）
"""
import os
import re
import sys
import glob

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFTS = os.path.join(BASE, "03_工作数据", "深读初稿")

CJK = r"一-鿿　-〿＀-￯"

# (正则, 替换) —— 每条都要求至少一侧是中文，英文引文行不会被命中
RULES = [
    # 前面是中文的半角逗号：中文后面不可能出现数字千分位，无条件转
    (re.compile(r"(?<=[" + CJK + r"])\s*,\s*"), "，"),
    # 后面是中文的半角逗号 —— 不必排除「前面是数字」：千分位的逗号后面
    # 必然还是数字（1,000），永远不会紧跟中文，所以这里不会误伤。
    # 早先加了 (?<!\d) 反而漏改「00:03:43,对应第 90 天」这类。
    (re.compile(r"\s*,\s*(?=[" + CJK + r"])"), "，"),
    (re.compile(r"(?<=[" + CJK + r"])\s*;\s*"), "；"),
    (re.compile(r"\s*;\s*(?=[" + CJK + r"])"), "；"),
    # 冒号：前面是中文即转（URL 的 :// 前面是英文，时间 12:30 前后是数字，都不匹配）
    (re.compile(r"(?<=[" + CJK + r"])\s*:\s*"), "："),
    (re.compile(r"(?<=[" + CJK + r"])\s*!\s*"), "！"),
    (re.compile(r"(?<=[" + CJK + r"])\s*\?\s*"), "？"),
    # 中文后面的半角句号，且后面不是数字或字母（排除小数、英文缩写、文件名）
    (re.compile(r"(?<=[" + CJK + r"])\.(?![\dA-Za-z])"), "。"),
]

# 检测用：中文字符之间夹半角标点
DETECT = re.compile(r"[" + CJK + r"][,;:!?][" + CJK + r"]")


def protect(text):
    """把不许改的片段挖出来占位：代码块、行内代码、Markdown 表格分隔行。

    英文原话行不必单独保护 —— 规则都要求紧邻中文，纯英文行不会被命中；
    而引文下方的中文译文行本来就该一起归一化。
    """
    holes = []

    def stash(m):
        holes.append(m.group(0))
        return "\x00%d\x00" % (len(holes) - 1)

    text = re.sub(r"```.*?```", stash, text, flags=re.S)
    text = re.sub(r"`[^`\n]+`", stash, text)
    text = re.sub(r"^\|[\s:-]+\|$", stash, text, flags=re.M)
    # 🔴 URL 用 \S+ 会一路吞到空格为止 —— 「.../test,他在那讲过。」整句都会被
    # 当成 URL 挖走，后面的中文标点就永远修不到了。遇到中文字符必须停。
    text = re.sub(r"https?://[^\s" + CJK + r"，。；：！？（）]+", stash, text)
    return text, holes


def restore(text, holes):
    for i, chunk in enumerate(holes):
        text = text.replace("\x00%d\x00" % i, chunk)
    return text


def fix(text):
    text, holes = protect(text)
    for pattern, repl in RULES:
        text = pattern.sub(repl, text)
    return restore(text, holes)


def main():
    check_only = "--check" in sys.argv
    files = sorted(glob.glob(os.path.join(DRAFTS, "*.md")))
    if not files:
        print("没有初稿可处理")
        return 0

    hit = 0
    total = 0
    for path in files:
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        n = len(DETECT.findall(src))
        if not n:
            continue
        hit += 1
        total += n
        name = os.path.basename(path)
        if check_only:
            print("  [半角] %-18s %d 处" % (name, n))
            continue
        out = fix(src)
        left = len(DETECT.findall(out))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(out)
        print("  %-18s %3d 处 → 剩 %d" % (name, n, left))

    if check_only:
        if hit:
            print("\n%d/%d 篇有中文半角标点，共 %d 处。跑 normalize_punct.py 修复。"
                  % (hit, len(files), total))
            return 1
        print("中文标点检查通过（%d 篇）" % len(files))
        return 0

    print("\n处理 %d/%d 篇，原有 %d 处半角标点" % (hit, len(files), total))
    return 0


if __name__ == "__main__":
    sys.exit(main())

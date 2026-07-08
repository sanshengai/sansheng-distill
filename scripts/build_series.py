#!/usr/bin/env python3
"""视频系列转写稿 -> book.txt + series.json + diagnose.json。

一个视频 = 一章,把已转写好的 srt/纯 txt 按 manifest 组装成蒸馏语料,下游四源蒸馏方法论复用书籍逻辑。
exit: 0 正常(含部分缺转写) / 2 输入问题(manifest 缺字段 / 非法 JSON / book.txt 已存在且无 --force) / 3 全部视频都缺转写(需人工)。

用法: python build_series.py --manifest <series-input.json> --outdir <书目录> [--force]
"""
import argparse
import json
import re
import sys
from pathlib import Path

# Windows 管道默认 cp936,打中文 JSON 前必须强制 UTF-8,否则 subprocess 侧解码会崩(本仓库跨脚本契约)
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# garbled_ratio 复用同目录 convert_book.py 的现成实现,不重写(保险起见把脚本目录塞进 sys.path)
sys.path.insert(0, str(Path(__file__).parent))
from convert_book import garbled_ratio  # noqa: E402

SRT_TIME = re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->")
# 时间码标记(去标记算 chars 用):[MM:SS] 或 [H:MM:SS]
TS_MARK = re.compile(r"\[\d+:\d{2}(?::\d{2})?\]")
# 章头标记 【视频N】标题(整行)
HEAD_MARK = re.compile(r"【视频\d+】.*")

REQUIRED_TOP = ["slug", "series_title", "author", "platform", "videos"]
REQUIRED_VIDEO = ["no", "title", "url", "transcript"]


def parse_srt(text):
    """srt 全文 -> [(start_sec, line_text)];纯 txt(无时间轴)-> [(None, 每段)]。"""
    if not SRT_TIME.search(text):
        return [(None, p.strip()) for p in re.split(r"\n\s*\n", text) if p.strip()]
    out = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l for l in block.splitlines() if l.strip()]
        ti = next((i for i, l in enumerate(lines) if SRT_TIME.match(l)), None)
        if ti is None or ti + 1 >= len(lines):
            continue
        m = SRT_TIME.match(lines[ti])
        sec = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])
        out.append((sec, " ".join(lines[ti + 1:])))
    return out


def fmt_ts(sec):
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"[{h}:{m:02d}:{s:02d}]" if h else f"[{m:02d}:{s:02d}]"


def assemble_video(no, title, cues, gap=45):
    """一个视频 -> 章头 + 每≥gap 秒注一次时间码的段落文本。

    开篇首个时间码统一注 [00:00](视频起点,对齐产物格式约定),其后按绝对时间;
    相邻时间码标记的实际间隔 ≥gap 秒才出新标记。纯 txt(sec 全为 None)只出章头、不注时间码。
    """
    parts, last_mark, buf, first_done = [f"【视频{no}】{title}"], None, [], False
    for sec, line in cues:
        if sec is None:
            # 纯 txt 段(无时间轴):flush 当前 buf,该段作为独立一行,保留空行分段边界
            if buf:
                parts.append(" ".join(buf))
                buf = []
            parts.append(line)
        elif last_mark is None or sec - last_mark >= gap:
            if buf:
                parts.append(" ".join(buf))
                buf = []
            disp = 0 if not first_done else sec  # 开篇标记恒 [00:00]
            buf.append(fmt_ts(disp) + " " + line)
            last_mark = sec
            first_done = True
        else:
            buf.append(line)
    if buf:
        parts.append(" ".join(buf))
    return "\n".join(parts) + "\n"


def count_chars(block: str) -> int:
    """该视频组装文本去掉时间码标记与章头后的字符数。"""
    t = TS_MARK.sub("", block)
    t = HEAD_MARK.sub("", t)
    return len(t.strip())


def validate_manifest(m) -> str | None:
    """返回缺失字段说明(供 stderr),合法返回 None。"""
    if not isinstance(m, dict):
        return "manifest 顶层必须是 JSON 对象"
    miss = [k for k in REQUIRED_TOP if k not in m]
    if miss:
        return f"manifest 缺顶层字段: {', '.join(miss)}"
    if not isinstance(m["videos"], list) or not m["videos"]:
        return "manifest videos 必须是非空数组"
    for i, v in enumerate(m["videos"]):
        if not isinstance(v, dict):
            return f"videos[{i}] 必须是对象"
        vm = [k for k in REQUIRED_VIDEO if k not in v]
        if vm:
            return f"videos[{i}] 缺字段: {', '.join(vm)}"
    return None


def recommend(garbled: float, chars_total: int, missing: list) -> str:
    """需人工确认 优先级高于 分组蒸馏。"""
    if garbled > 0.02 or missing:
        return "需人工确认"
    if chars_total > 150000:
        return "分组蒸馏"
    return "直接蒸馏"


def main():
    ap = argparse.ArgumentParser(description="视频系列转写稿 → book.txt + series.json + diagnose.json")
    ap.add_argument("--manifest", required=True, help="series-input.json 路径")
    ap.add_argument("--outdir", required=True, help="输出书目录(transcript 相对路径以此为基准)")
    ap.add_argument("--force", action="store_true", help="book.txt 已存在时强制覆盖")
    a = ap.parse_args()

    manifest_path, out = Path(a.manifest), Path(a.outdir)
    if not manifest_path.is_file():
        print(f"manifest 不存在: {manifest_path}", file=sys.stderr)
        return 2
    try:
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"manifest 不是合法 JSON: {e}", file=sys.stderr)
        return 2
    err = validate_manifest(m)
    if err:
        print(err, file=sys.stderr)
        return 2

    out.mkdir(parents=True, exist_ok=True)
    txt_path = out / "book.txt"
    if txt_path.exists() and not a.force:
        print(f"{txt_path} 已存在,防覆盖拒跑;确认重建请加 --force", file=sys.stderr)
        return 2

    blocks, series_videos, missing = [], [], []
    for v in m["videos"]:
        no, title = v["no"], v["title"]
        sv = dict(v)
        sv["transcript_kind"] = v.get("transcript_kind", "subs")  # manifest 有则透传,无则填 subs
        tpath = out / v["transcript"]  # transcript 相对 outdir
        if not tpath.is_file():
            missing.append(no)
            sv["chars"] = 0
            series_videos.append(sv)
            continue
        text = tpath.read_text(encoding="utf-8", errors="replace")
        block = assemble_video(no, title, parse_srt(text))
        blocks.append(block)
        sv["chars"] = count_chars(block)
        series_videos.append(sv)

    videos_total = len(m["videos"])
    chars_per_video = [sv["chars"] for sv in series_videos]
    chars_total = sum(chars_per_video)
    book = "\n".join(blocks)  # 视频之间空一行分隔(每块自带尾部换行)
    g = round(garbled_ratio(book), 4) if book else 0.0
    rec = recommend(g, chars_total, missing)

    diag = {
        "mode": "video_series",
        "videos_total": videos_total,
        "videos_missing_transcript": missing,
        "chars_total": chars_total,
        "chars_per_video": chars_per_video,
        "garbled_ratio": g,
        "recommendation": rec,
    }

    # 全部视频都缺转写(一个都读不到)→ 无可用语料,只落诊断供人工排查,exit 3
    if len(missing) == videos_total:
        (out / "diagnose.json").write_text(json.dumps(diag, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"全部 {videos_total} 个视频转写均缺失,无法组装语料;详见 diagnose.json", file=sys.stderr)
        print(json.dumps(diag, ensure_ascii=False, indent=1))
        return 3

    series = dict(m)
    series["videos"] = series_videos
    (out / "series.json").write_text(json.dumps(series, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "diagnose.json").write_text(json.dumps(diag, ensure_ascii=False, indent=1), encoding="utf-8")
    txt_path.write_text(book, encoding="utf-8")
    print(json.dumps(diag, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

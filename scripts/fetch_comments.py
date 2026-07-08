#!/usr/bin/env python3
"""视频系列评论抓取 -> comments.json(供观众评论蒸馏,对位书籍书评模块)。

读 series.json,对每个视频抓评论(YouTube 走 yt-dlp / B站走 web API),合并去重截断后
按视频分组落 comments.json。**解析层(parse_*)与网络层(fetch_*)严格分离**:解析是纯
函数、可单测;网络层靠 monkeypatch 打桩。

exit: 0 至少抓到 1 条 / 2 全失败(全 0 条)或平台不支持(douyin) / 其他输入问题也 2。

用法: python fetch_comments.py --series <series.json> --out <comments.json> [--per-video 15] [--total 40]
"""
import argparse
import datetime
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

# Windows 管道默认 cp936,打中文 JSON 前强制 UTF-8。pytest 直接 import 本模块时
# sys.stdout 可能是不带 reconfigure 的捕获对象,故 guard 防 import 崩(网络层契约不变)。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
BV_RE = re.compile(r"BV[0-9A-Za-z]+")


def _clean(s) -> str:
    """代理安全(实测真坑):评论文本可能含孤立代理字符(lone surrogate),
    直接 json.dump / 写盘会 UnicodeEncodeError。逐字段清洗为可编码文本。"""
    if s is None:
        return ""
    return str(s).encode("utf-8", "replace").decode("utf-8")


# ============================ 解析层(纯函数,可单测,不打网络) ============================
def parse_youtube(info: dict) -> list[dict]:
    """yt-dlp -J 的完整 info dict(含 comments 键)-> 顶层评论列表(likes 降序)。

    yt-dlp 把回复拍平成同列表条目;只保留 parent=="root" 的顶层评论,
    reply_count 自算 = 列表中 parent==该评论.id 的条数。
    """
    comments = (info or {}).get("comments") or []
    reply_counts: dict = {}
    for c in comments:
        p = c.get("parent")
        if p and p != "root":
            reply_counts[p] = reply_counts.get(p, 0) + 1
    out = []
    for c in comments:
        if c.get("parent") != "root":
            continue
        out.append({
            "text": _clean(c.get("text")),
            "likes": int(c.get("like_count") or 0),
            "author": _clean(c.get("author")),
            "reply_count": reply_counts.get(c.get("id"), 0),
        })
    out.sort(key=lambda x: x["likes"], reverse=True)
    return out


def parse_bili(resp: dict) -> list[dict]:
    """B站 reply/main 响应({code, data:{replies:[...]}})-> 评论列表(likes 降序)。
    code!=0 或无 replies -> []。"""
    if not isinstance(resp, dict) or resp.get("code") != 0:
        return []
    replies = ((resp.get("data") or {}).get("replies")) or []
    out = []
    for r in replies:
        content = r.get("content") or {}
        member = r.get("member") or {}
        out.append({
            "text": _clean(content.get("message")),
            "likes": int(r.get("like") or 0),
            "author": _clean(member.get("uname")),
            "reply_count": int(r.get("rcount") or 0),
        })
    out.sort(key=lambda x: x["likes"], reverse=True)
    return out


# ============================ 合并 / 去重 / 截断(纯函数) ============================
def merge_dedup(per_video_lists: list, per_video: int, total: int) -> list:
    """每视频取 likes 前 per_video 条 -> 全系列合并去重(text 前 40 字符相同视为重复,
    保留 likes 高者)-> 全局 likes 降序取前 total 条为保留集 -> 按视频回填(分组结构保留)。

    返回与 per_video_lists 平行的 list[list[dict]],每子列表是该视频命中保留集的评论(likes 降序)。
    """
    # ① 每视频截断 top per_video
    truncated = [sorted(lst, key=lambda c: c["likes"], reverse=True)[:per_video]
                 for lst in per_video_lists]
    # ② 全局去重:text[:40] 为键,保留 likes 高者(记录实际对象引用)
    best: dict = {}  # key -> (likes, comment_obj)
    for lst in truncated:
        for c in lst:
            key = c["text"][:40]
            if key not in best or c["likes"] > best[key][0]:
                best[key] = (c["likes"], c)
    # ③ 全局 likes 降序取前 total 为保留集
    uniques = sorted(best.values(), key=lambda t: t[0], reverse=True)[:total]
    kept_ids = {id(c) for _likes, c in uniques}
    # ④ 按视频回填:只保留命中 kept_ids 的对象,组内维持 likes 降序
    return [[c for c in lst if id(c) in kept_ids] for lst in truncated]


def decide_exit(total_written: int, platform: str) -> int:
    """至少 1 条 -> 0;全 0 条 或 douyin(不支持)-> 2。"""
    if platform == "douyin":
        return 2
    return 0 if total_written > 0 else 2


# ============================ 网络层(与解析分离,靠 monkeypatch 打桩) ============================
def fetch_youtube(url: str, cap: int) -> dict:
    """跑 yt-dlp 子进程 -J 抓评论,返回解析后的 info dict。"""
    args = ["-J", "--write-comments", "--skip-download",
            "--extractor-args", f"youtube:max_comments={cap},all,0,0", url]
    try:
        proc = subprocess.run(["yt-dlp", *args], capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError:
        proc = subprocess.run([sys.executable, "-m", "yt_dlp", *args],
                              capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0 or not (proc.stdout or "").strip():
        raise RuntimeError(f"yt-dlp 失败(rc={proc.returncode}): {(proc.stderr or '')[:300]}")
    return json.loads(proc.stdout)


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def fetch_bili(url: str) -> dict:
    """从 url 正则取 BVxxx -> view 拿 aid -> reply/main(mode=3 热门序)拿响应 dict。"""
    m = BV_RE.search(url)
    if not m:
        raise ValueError(f"URL 中未找到 BV 号: {url}")
    bv = m.group(0)
    view = _http_get_json(f"https://api.bilibili.com/x/web-interface/view?bvid={bv}")
    aid = (view.get("data") or {}).get("aid")
    if not aid:
        raise RuntimeError(f"取 aid 失败(code={view.get('code')})")
    return _http_get_json(
        f"https://api.bilibili.com/x/v2/reply/main?type=1&oid={aid}&mode=3")


def collect_comments(videos: list, platform: str, cap: int) -> list:
    """逐视频 fetch+parse;单视频抛异常 -> 该视频记 [] 并继续(不整体崩)。
    返回与 videos 平行的 list[list[dict]]。"""
    out = []
    for v in videos:
        url = v.get("url", "")
        try:
            if platform in ("youtube", "yt"):
                out.append(parse_youtube(fetch_youtube(url, cap)))
            elif platform in ("bilibili", "bili"):
                out.append(parse_bili(fetch_bili(url)))
            else:
                out.append([])
        except Exception as e:  # noqa: BLE001 -- 单视频失败不得拖垮整批
            print(f"视频 {v.get('no')} 抓取失败({url}): {e}", file=sys.stderr)
            out.append([])
    return out


def build_output(videos: list, regrouped: list) -> tuple:
    """按视频分组组装 comments.json 结构;返回 (dict, total_written)。"""
    out_videos = [{"no": v.get("no"), "url": v.get("url"), "comments": comments}
                  for v, comments in zip(videos, regrouped)]
    total = sum(len(c) for c in regrouped)
    doc = {
        "fetched_at": datetime.date.today().isoformat(),
        "total": total,
        "videos": out_videos,
    }
    return doc, total


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="视频系列评论抓取 → comments.json")
    ap.add_argument("--series", required=True, help="series.json 路径(Task 2 产物)")
    ap.add_argument("--out", required=True, help="comments.json 输出路径")
    ap.add_argument("--per-video", type=int, default=15, help="每视频保留评论上限")
    ap.add_argument("--total", type=int, default=40, help="全系列去重后保留总条数上限")
    a = ap.parse_args(argv)

    series_path = Path(a.series)
    if not series_path.is_file():
        print(f"series 不存在: {series_path}", file=sys.stderr)
        return 2
    try:
        series = json.loads(series_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"series 不是合法 JSON: {e}", file=sys.stderr)
        return 2

    platform = (series.get("platform") or "").lower()
    if platform == "douyin":
        print("抖音评论抓取 v1 暂不支持;下游 enrich reviews 降级 null", file=sys.stderr)
        return 2

    videos = series.get("videos") or []
    per_video = a.per_video
    cap = per_video * 2  # 给去重留量(抓 2 倍),别抓太多拖慢
    per_video_lists = collect_comments(videos, platform, cap)
    regrouped = merge_dedup(per_video_lists, per_video, a.total)
    doc, total = build_output(videos, regrouped)

    if total <= 0:
        print("全部视频均未抓到评论(全失败);不写 comments.json", file=sys.stderr)
        return decide_exit(total, platform)

    Path(a.out).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"写入 {a.out}: {total} 条评论,{len(videos)} 个视频")
    return decide_exit(total, platform)


if __name__ == "__main__":
    sys.exit(main())

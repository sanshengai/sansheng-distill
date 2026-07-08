"""fetch_comments.py 测试 -- 只喂 fixture,禁止打活体网络。

解析层(parse_*)/合并层(merge_dedup)/判定层(decide_exit)全是纯函数直测;
网络层(fetch_*)靠 monkeypatch 打桩验证失败隔离;douyin 退出码走 subprocess。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "fetch_comments.py"
FIX = Path(__file__).parent / "fixtures"


def _load():
    spec = importlib.util.spec_from_file_location("fetch_comments", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


fc = _load()


def load_fix(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


# --- parse_bili ---
def test_parse_bili_fixture():
    out = fc.parse_bili(load_fix("bili_comments.json"))
    assert len(out) == 5
    for c in out:
        assert set(c) >= {"text", "likes", "author", "reply_count"}
        assert c["text"] and c["author"]  # 非空
        assert isinstance(c["likes"], int) and isinstance(c["reply_count"], int)
    likes = [c["likes"] for c in out]
    assert likes == sorted(likes, reverse=True)  # 降序


def test_parse_bili_code_nonzero_or_empty():
    assert fc.parse_bili({"code": -404, "data": {"replies": []}}) == []
    assert fc.parse_bili({"code": 0, "data": {}}) == []
    assert fc.parse_bili({}) == []


# --- parse_youtube ---
def test_parse_youtube_fixture():
    comments = load_fix("yt_comments.json")
    out = fc.parse_youtube({"comments": comments})
    n_root = sum(1 for c in comments if c.get("parent") == "root")
    assert len(out) == n_root
    for c in out:
        assert set(c) >= {"text", "likes", "author", "reply_count"}
    likes = [c["likes"] for c in out]
    assert likes == sorted(likes, reverse=True)


def test_parse_youtube_reply_count_and_flatten():
    # 2 条顶层 + 1 条 parent==A 的回复;A 的 reply_count 应为 1,回复本身不作顶层输出
    info = {"comments": [
        {"id": "A", "parent": "root", "text": "顶层甲", "like_count": 10, "author": "@a"},
        {"id": "B", "parent": "root", "text": "顶层乙", "like_count": 5, "author": "@b"},
        {"id": "R1", "parent": "A", "text": "这是对甲的回复", "like_count": 3, "author": "@r"},
    ]}
    out = fc.parse_youtube(info)
    assert len(out) == 2
    top_a = next(c for c in out if c["text"] == "顶层甲")
    assert top_a["reply_count"] == 1
    top_b = next(c for c in out if c["text"] == "顶层乙")
    assert top_b["reply_count"] == 0
    assert all(c["text"] != "这是对甲的回复" for c in out)


# --- 代理安全 ---
def test_surrogate_safe_youtube():
    info = {"comments": [
        {"id": "X", "parent": "root", "text": "坏字\udc98尾", "like_count": 1, "author": "@x\udc98"},
    ]}
    out = fc.parse_youtube(info)
    s = json.dumps(out, ensure_ascii=False)  # 不得抛 UnicodeEncodeError
    assert isinstance(s, str)


def test_surrogate_safe_bili():
    resp = {"code": 0, "data": {"replies": [
        {"rpid": 1, "content": {"message": "坏\udc98串"}, "like": 1, "rcount": 0,
         "member": {"uname": "名\udc98"}},
    ]}}
    out = fc.parse_bili(resp)
    json.dumps(out, ensure_ascii=False)  # 不抛异常即通过


# --- merge_dedup ---
def test_merge_dedup_cross_video_keeps_higher_likes():
    dup = "这是一条足够长的评论用来测试前四十个字符相同即判重的去重逻辑abcdef"
    v1 = [{"text": dup, "likes": 100, "author": "a", "reply_count": 0},
          {"text": "v1独有内容", "likes": 50, "author": "b", "reply_count": 0}]
    v2 = [{"text": dup, "likes": 30, "author": "c", "reply_count": 0},
          {"text": "v2独有内容", "likes": 40, "author": "d", "reply_count": 0}]
    regrouped = fc.merge_dedup([v1, v2], 15, 40)
    flat = [c for lst in regrouped for c in lst]
    dups = [c for c in flat if c["text"] == dup]
    assert len(dups) == 1 and dups[0]["likes"] == 100  # 只保留 likes 高者
    assert any(c["text"] == dup for c in regrouped[0])   # 高者留在 v1 组
    assert all(c["text"] != dup for c in regrouped[1])   # v2 里那条被去掉


def test_merge_dedup_per_video_truncation():
    v = [{"text": f"c{i}", "likes": i, "author": "a", "reply_count": 0} for i in range(6)]
    regrouped = fc.merge_dedup([v], 2, 40)
    assert len(regrouped[0]) == 2
    assert [c["likes"] for c in regrouped[0]] == [5, 4]  # 每视频取 likes 前 2


def test_merge_dedup_total_truncation_preserves_grouping():
    v1 = [{"text": f"a{i}", "likes": 100 - i, "author": "a", "reply_count": 0} for i in range(5)]
    v2 = [{"text": f"b{i}", "likes": 50 - i, "author": "b", "reply_count": 0} for i in range(5)]
    regrouped = fc.merge_dedup([v1, v2], 15, 3)
    assert sum(len(lst) for lst in regrouped) == 3          # 总量截断到 3
    assert len(regrouped[0]) == 3 and len(regrouped[1]) == 0  # top3 都来自 v1,分组结构保留


# --- decide_exit ---
def test_decide_exit():
    assert fc.decide_exit(0, "youtube") == 2   # 全 0 条
    assert fc.decide_exit(5, "youtube") == 0
    assert fc.decide_exit(3, "douyin") == 2     # douyin 恒 2
    assert fc.decide_exit(0, "bilibili") == 2
    assert fc.decide_exit(1, "bilibili") == 0


# --- 网络失败隔离(monkeypatch,不打真网) ---
def test_collect_comments_isolates_failure(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("网络炸了")
    monkeypatch.setattr(fc, "fetch_youtube", boom)
    videos = [{"no": 1, "url": "https://www.youtube.com/watch?v=a"},
              {"no": 2, "url": "https://www.youtube.com/watch?v=b"}]
    out = fc.collect_comments(videos, "youtube", 30)
    assert out == [[], []]  # 单视频失败 → 0 条,不整体崩


# --- douyin 走 subprocess,exit 2 ---
def test_douyin_exit2(tmp_path):
    series = {"slug": "s", "series_title": "t", "author": "u", "platform": "douyin",
              "videos": [{"no": 1, "title": "x", "url": "https://v.douyin.com/xxx"}]}
    p = tmp_path / "series.json"
    p.write_text(json.dumps(series, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "comments.json"
    r = subprocess.run([sys.executable, str(SCRIPT), "--series", str(p), "--out", str(out)],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 2
    assert not out.exists()

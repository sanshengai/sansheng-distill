import json, subprocess, sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "build_series.py"

SRT = """1
00:00:01,000 --> 00:00:04,000
大家好 今天讲第一个观点

2
00:00:50,000 --> 00:00:53,000
第二段 间隔超过45秒 应该出新时间码

3
00:01:05,000 --> 00:01:08,000
第三段 距上一标记不足45秒 不出新标记
"""

def make_series(tmp_path, n=2, missing=0):
    raw = tmp_path / "raw"; raw.mkdir()
    videos = []
    for i in range(1, n + 1):
        t = f"raw/v{i}.srt"
        if i > n - missing:
            t = f"raw/nonexist{i}.srt"
        else:
            (raw / f"v{i}.srt").write_text(SRT, encoding="utf-8")
        videos.append({"no": i, "title": f"第{i}集", "url": f"https://www.youtube.com/watch?v=x{i}", "transcript": t})
    m = {"slug": "test-series", "series_title": "测试系列", "author": "测试UP", "platform": "youtube", "videos": videos}
    p = tmp_path / "series-input.json"
    p.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    return p

def run(manifest, outdir, *extra):
    return subprocess.run([sys.executable, str(SCRIPT), "--manifest", str(manifest), "--outdir", str(outdir), *extra],
                          capture_output=True, text=True, encoding="utf-8")

def test_assemble_chapters_and_timestamps(tmp_path):
    r = run(make_series(tmp_path), tmp_path)
    assert r.returncode == 0
    txt = (tmp_path / "book.txt").read_text(encoding="utf-8")
    assert "【视频1】第1集" in txt and "【视频2】第2集" in txt
    assert txt.index("【视频1】") < txt.index("【视频2】")
    assert "[00:00]" in txt and "[00:50]" in txt
    assert "[01:05]" not in txt  # 间隔<45s 不出新标记
    diag = json.loads((tmp_path / "diagnose.json").read_text(encoding="utf-8"))
    assert diag["mode"] == "video_series" and diag["videos_total"] == 2
    assert diag["recommendation"] == "直接蒸馏"
    series = json.loads((tmp_path / "series.json").read_text(encoding="utf-8"))
    assert series["videos"][0]["chars"] > 0

def test_all_missing_transcript_exit3(tmp_path):
    r = run(make_series(tmp_path, n=2, missing=2), tmp_path)
    assert r.returncode == 3

def test_partial_missing_records_diagnose(tmp_path):
    r = run(make_series(tmp_path, n=3, missing=1), tmp_path)
    assert r.returncode == 0
    diag = json.loads((tmp_path / "diagnose.json").read_text(encoding="utf-8"))
    assert diag["videos_missing_transcript"] == [3]
    assert diag["recommendation"] == "需人工确认"

def test_refuse_overwrite_without_force(tmp_path):
    m = make_series(tmp_path)
    assert run(m, tmp_path).returncode == 0
    assert run(m, tmp_path).returncode == 2
    assert run(m, tmp_path, "--force").returncode == 0

def make_txt_series(tmp_path, txt):
    """构造一个纯 txt(无时间轴)转写的单视频 manifest。"""
    raw = tmp_path / "raw"; raw.mkdir()
    (raw / "v1.txt").write_text(txt, encoding="utf-8")
    videos = [{"no": 1, "title": "第1集", "url": "https://www.youtube.com/watch?v=x1", "transcript": "raw/v1.txt"}]
    m = {"slug": "test-series", "series_title": "测试系列", "author": "测试UP", "platform": "youtube", "videos": videos}
    p = tmp_path / "series-input.json"
    p.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    return p

def test_plain_txt_paragraphs_each_own_line(tmp_path):
    # 纯 txt(无时间轴)3 段用空行分隔,组装后每段应各占一行,不能塌成一行
    p1, p2, p3 = "第一段内容。", "第二段内容。", "第三段内容。"
    txt_src = f"{p1}\n\n{p2}\n\n{p3}\n"
    r = run(make_txt_series(tmp_path, txt_src), tmp_path)
    assert r.returncode == 0
    txt = (tmp_path / "book.txt").read_text(encoding="utf-8")
    assert "【视频1】第1集" in txt
    # 三段文本各自都在
    assert p1 in txt and p2 in txt and p3 in txt
    # 被并成一行的形态(段间加空格)绝不出现
    assert f"{p1} {p2}" not in txt
    assert f"{p2} {p3}" not in txt
    # 该视频块内换行数 >= 3(章头 + 3 段,每段一行)
    assert txt.count("\n") >= 3

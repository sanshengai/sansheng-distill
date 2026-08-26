"""套装/合集 epub 按 TOC 切分册(v0.5,2026-07-27)。

立法背景:2026-07-26 蒸格拉德威尔 6 本时,全部切自同一个「经典系列(套装共5册)」epub。
旧 `extract_epub` **完全不读 TOC** -- 把所有 ITEM_DOCUMENT 一股脑拼起来,
`diagnose` 又只用正文启发式正则猜章节,结果 `toc_detected: false / chapters_detected: 1`:
**蒸馏时手里没有原书章节划分,章数只能靠模型自由发挥**,产出的 6 本一律被压成 6 章。

本文件锁住:① 顶层分册识别 ② 按 spine 区间切(不漏未列入 TOC 的正文续页)
③ diagnose 两路取大(TOC 章数 vs 正文正则)。
"""
import sys
import json
import subprocess
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from convert_book import epub_volumes, extract_epub, diagnose, _anchor_hrefs

ebooklib = pytest.importorskip("ebooklib")
pytest.importorskip("bs4")
from ebooklib import epub  # noqa: E402

SCRIPT = Path(__file__).parent.parent / "convert_book.py"


def run(*args):
    """跑 CLI(subprocess),用于验 exit code 与 stderr -- 库级函数测不到 main() 的守卫。"""
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, encoding="utf-8")


def _mk_omnibus(tmp_path: Path) -> Path:
    """合成一个 2 分册套装 epub。甲书 2 章 + 1 篇**未列入 TOC 的正文续页**;乙书 2 章。"""
    book = epub.EpubBook()
    book.set_identifier("omnibus-fixture")
    book.set_title("甲乙合集(套装共2册)")
    book.set_language("zh")

    def ch(fn, title, body):
        c = epub.EpubHtml(title=title, file_name=fn, lang="zh")
        c.content = f"<html><body><h1>{title}</h1><p>{body}</p></body></html>"
        book.add_item(c)
        return c

    a1 = ch("a1.xhtml", "第一章", "甲书第一章正文" * 20)
    a2 = ch("a2.xhtml", "第二章", "甲书第二章正文" * 20)
    a_tail = ch("a_tail.xhtml", "甲书续页", "甲书未列入目录的正文续页" * 20)
    b1 = ch("b1.xhtml", "第一章", "乙书第一章正文" * 20)
    b2 = ch("b2.xhtml", "第二章", "乙书第二章正文" * 20)

    # TOC 顶层两分册;a_tail **故意不列入 TOC**,用来验证按 spine 区间切而非只取 TOC 列出的篇目
    book.toc = ((epub.Section("甲书"), (a1, a2)), (epub.Section("乙书"), (b1, b2)))
    book.spine = [a1, a2, a_tail, b1, b2]
    book.add_item(epub.EpubNcx())
    p = tmp_path / "omnibus.epub"
    epub.write_epub(str(p), book)
    return p


def test_volumes_listed(tmp_path):
    p = _mk_omnibus(tmp_path)
    b = epub.read_epub(str(p), options={"ignore_ncx": True})
    names = [v[0] for v in epub_volumes(b)]
    assert "甲书" in names and "乙书" in names


def test_volume_extract_isolates_content(tmp_path):
    """切甲书不许混进乙书正文 -- 混书是最坏的静默失败。"""
    p = _mk_omnibus(tmp_path)
    text, _titles = extract_epub(p, volume="甲书")
    assert "甲书第一章正文" in text
    assert "乙书第一章正文" not in text
    assert "乙书第二章正文" not in text


def test_volume_extract_includes_untoc_tail(tmp_path):
    """未列入 TOC 的正文续页必须收进来 -- 只取 TOC 列出的篇目会静默丢正文。"""
    p = _mk_omnibus(tmp_path)
    text, _ = extract_epub(p, volume="甲书")
    assert "甲书未列入目录的正文续页" in text


def test_second_volume_runs_to_end(tmp_path):
    p = _mk_omnibus(tmp_path)
    text, _ = extract_epub(p, volume="乙书")
    assert "乙书第一章正文" in text and "乙书第二章正文" in text
    assert "甲书第一章正文" not in text


def test_unknown_volume_raises(tmp_path):
    p = _mk_omnibus(tmp_path)
    with pytest.raises(KeyError):
        extract_epub(p, volume="丙书")


def test_fuzzy_volume_name_match(tmp_path):
    """分册名带书名号/副标题时容忍包含匹配。"""
    p = _mk_omnibus(tmp_path)
    text, _ = extract_epub(p, volume="甲书:某副标题")
    assert "甲书第一章正文" in text


def test_no_volume_returns_whole_book(tmp_path):
    """不传 volume 时行为不变 = 整本抽取(向后兼容单本 epub)。"""
    p = _mk_omnibus(tmp_path)
    text, titles = extract_epub(p)
    assert "甲书第一章正文" in text and "乙书第二章正文" in text
    assert titles, "整书抽取也应带回 TOC 标题供 diagnose 数章数"


# ---------------------------------------------------------------- diagnose 两路取大
def test_diagnose_prefers_toc_when_body_regex_blind():
    """正文没有规整章节头(意译标题的外版书 / 切出来的分册)时,用 TOC 声明的章数兜底。"""
    body = "这是一段没有任何规整章节头的正文。" * 50
    d = diagnose(body, "epub", 0, toc_titles=["第一章 甲", "第二章 乙", "第三章 丙", "第四章 丁"])
    assert d["chapters_detected"] == 4
    assert d["toc_detected"] is True
    assert d["chapters_source"] == "epub_toc"


def test_diagnose_keeps_body_regex_when_higher():
    body = "\n".join(f"第{i}章 标题" for i in range(1, 11)) + "\n正文" * 50
    d = diagnose(body, "epub", 0, toc_titles=["第一章 甲"])
    assert d["chapters_detected"] == 10
    assert d["chapters_source"] == "body_regex"


def test_diagnose_without_toc_unchanged():
    """不传 toc_titles 时与改造前行为一致(向后兼容 pdf/txt 路径)。"""
    body = "\n".join(f"第{i}章 标题" for i in range(1, 6)) + "\n正文" * 50
    assert diagnose(body, "txt", 0)["chapters_detected"] == 5


# ================================================================ BUG-1 自身 href 锚点
# 立法背景:2026-08-25 曾国藩 12 册套装。NCX 里每个「曾国藩全集 N」顶层 Section **自身**
# 带 href,而它指向的是**别册**的正文文件(如第 11 册家书,自身 href 指到奏稿卷十四)。
# `_toc_walk` 把节点自身 href 也收进 hrefs[0],`min(starts)` 于是锚到别的书上 --
# 要第 11 册《家书》拿回奏稿卷十四,exit 0 零警告,是最坏的静默混书。
# 上面的 `_mk_omnibus` 造不出这个 bug(它的 Section 没有自身 href),9 个测试全绿也挡不住。


def _mk_self_href_omnibus(tmp_path: Path) -> Path:
    """3 分册套装,每个 Section **自身 href 指向别册的文件**(复刻曾国藩 12 册 NCX 结构)。"""
    book = epub.EpubBook()
    book.set_identifier("self-href-omnibus")
    book.set_title("甲乙丙合集(套装共3册)")
    book.set_language("zh")

    def ch(fn, title, body):
        c = epub.EpubHtml(title=title, file_name=fn, lang="zh")
        c.content = f"<html><body><h1>{title}</h1><p>{body}</p></body></html>"
        book.add_item(c)
        return c

    a1 = ch("a1.xhtml", "甲第一章", "甲书第一章正文" * 20)
    a2 = ch("a2.xhtml", "甲第二章", "甲书第二章正文" * 20)
    a_tail = ch("a_tail.xhtml", "甲书续页", "甲书未列入目录的正文续页" * 20)
    b1 = ch("b1.xhtml", "乙第一章", "乙书第一章正文" * 20)
    b2 = ch("b2.xhtml", "乙第二章", "乙书第二章正文" * 20)
    c1 = ch("c1.xhtml", "丙第一章", "丙书第一章正文" * 20)
    c2 = ch("c2.xhtml", "丙第二章", "丙书第二章正文" * 20)

    # 每个 Section 自身 href 都是**错锚点**(指向别册),只有子项 href 才对
    book.toc = (
        (epub.Section("甲书", "b1.xhtml"), (a1, a2)),
        (epub.Section("乙书", "a1.xhtml"), (b1, b2)),
        (epub.Section("丙书", "a2.xhtml"), (c1, c2)),
    )
    book.spine = [a1, a2, a_tail, b1, b2, c1, c2]
    book.add_item(epub.EpubNcx())
    p = tmp_path / "self_href.epub"
    epub.write_epub(str(p), book)
    return p


def test_volume_section_self_href_must_not_set_start(tmp_path):
    """分册起点必须由**子项** href 决定;节点自身 href 指向别册时不许把起点拉过去。

    修前:乙书的 starts 含自身 href a1(下标 0) → min=0 → 切出来的是甲书正文。
    """
    p = _mk_self_href_omnibus(tmp_path)
    text, _ = extract_epub(p, volume="乙书")
    assert "乙书第一章正文" in text and "乙书第二章正文" in text
    assert "甲书第一章正文" not in text, "自身 href 把起点锚到了别册 -- 静默混书"
    assert "丙书第一章正文" not in text


def test_volume_section_self_href_must_not_set_end(tmp_path):
    """终点同理:later 里也要丢掉后续分册的自身 href,否则终点被提前,正文被腰斩。

    修前:甲书 later 取到丙书自身 href a2(下标 1) → end=1 → 只剩 a1 一篇。
    """
    p = _mk_self_href_omnibus(tmp_path)
    text, _ = extract_epub(p, volume="甲书")
    assert "甲书第一章正文" in text
    assert "甲书第二章正文" in text, "终点被后续分册的自身 href 提前,正文被腰斩"
    assert "甲书未列入目录的正文续页" in text
    assert "乙书第一章正文" not in text


def test_last_volume_self_href_still_runs_to_end(tmp_path):
    p = _mk_self_href_omnibus(tmp_path)
    text, _ = extract_epub(p, volume="丙书")
    assert "丙书第一章正文" in text and "丙书第二章正文" in text
    assert "甲书第二章正文" not in text


def test_single_href_volume_unaffected(tmp_path):
    """回归护栏:每节点只有 1 个 href 的套装(曾文正公 16 册 / 家书上中下)行为必须完全不变。"""
    p = _mk_omnibus(tmp_path)
    text, _ = extract_epub(p, volume="甲书")
    assert "甲书第一章正文" in text and "甲书第二章正文" in text
    assert "乙书第一章正文" not in text


# ================================================================ BUG-2 同名分册 / 空切片
def _mk_dup_name_omnibus(tmp_path: Path, pad_bytes: int = 0) -> Path:
    """复刻唐浩明套装:顶层 6 节点,其中三个都叫「目录」;书名节点下只挂封面页。"""
    import os
    book = epub.EpubBook()
    book.set_identifier("dup-name-omnibus")
    book.set_title("唐浩明钦定版(套装全3册)")
    book.set_language("zh")

    def ch(fn, title, body):
        c = epub.EpubHtml(title=title, file_name=fn, lang="zh")
        c.content = f"<html><body><h1>{title}</h1><p>{body}</p></body></html>"
        book.add_item(c)
        return c

    t1 = ch("t1.xhtml", "《甲1:血祭》", "封面与版权页")
    a1 = ch("a1.xhtml", "甲一", "甲书第一章正文" * 20)
    a2 = ch("a2.xhtml", "甲二", "甲书第二章正文" * 20)
    t2 = ch("t2.xhtml", "《乙2:野焚》", "封面与版权页")
    b1 = ch("b1.xhtml", "乙一", "乙书第一章正文" * 20)
    b2 = ch("b2.xhtml", "乙二", "乙书第二章正文" * 20)
    t3 = ch("t3.xhtml", "《丙3:黑雨》", "封面与版权页")
    c1 = ch("c1.xhtml", "丙一", "丙书第一章正文" * 20)

    book.toc = (
        (epub.Section("《甲1:血祭》"), (t1,)),
        (epub.Section("目录"), (a1, a2)),
        (epub.Section("《乙2:野焚》"), (t2,)),
        (epub.Section("目录"), (b1, b2)),
        (epub.Section("《丙3:黑雨》"), (t3,)),
        (epub.Section("目录"), (c1,)),
    )
    book.spine = [t1, a1, a2, t2, b1, b2, t3, c1]
    book.add_item(epub.EpubNcx())
    if pad_bytes:
        pad = epub.EpubItem(uid="pad", file_name="pad.bin",
                            media_type="application/octet-stream",
                            content=os.urandom(pad_bytes))
        book.add_item(pad)
    p = tmp_path / "dupname.epub"
    epub.write_epub(str(p), book)
    return p


def test_duplicate_volume_name_is_rejected(tmp_path):
    """三个同名「目录」时按名寻址必须报错并列出候选下标,不许静默取第一个。"""
    p = _mk_dup_name_omnibus(tmp_path)
    r = run(str(p), "--outdir", str(tmp_path / "out"), "--volume", "目录")
    assert r.returncode == 2, r.stdout
    assert "1" in r.stderr and "3" in r.stderr and "5" in r.stderr, r.stderr


def test_volume_index_addresses_duplicate_names(tmp_path):
    """--volume-index 按 --list-volumes 的数组下标寻址,同名分册也能拿到第 2、3 册。"""
    p = _mk_dup_name_omnibus(tmp_path)
    out = tmp_path / "out3"
    r = run(str(p), "--outdir", str(out), "--volume-index", "3")
    assert r.returncode == 0, r.stderr
    txt = (out / "book.txt").read_text(encoding="utf-8")
    assert "乙书第一章正文" in txt and "乙书第二章正文" in txt
    assert "甲书第一章正文" not in txt


def test_volume_index_out_of_range(tmp_path):
    p = _mk_dup_name_omnibus(tmp_path)
    r = run(str(p), "--outdir", str(tmp_path / "outx"), "--volume-index", "99")
    assert r.returncode == 2
    # 断言走的是越界分支而不是 argparse 的「无此参数」-- 否则参数没实现时本用例会假绿
    assert "越界" in r.stderr and "0..5" in r.stderr, r.stderr


def test_volume_and_volume_index_are_exclusive(tmp_path):
    p = _mk_dup_name_omnibus(tmp_path)
    r = run(str(p), "--outdir", str(tmp_path / "outy"), "--volume", "目录", "--volume-index", "1")
    assert r.returncode == 2
    assert "二选一" in r.stderr, r.stderr


def test_empty_slice_downgraded_to_manual(tmp_path):
    """容器 >1MB 却只切出几百字(封面+版权页)= 切错了,必须降级「需人工确认」+ exit 3。"""
    p = _mk_dup_name_omnibus(tmp_path, pad_bytes=1_400_000)
    assert p.stat().st_size > 1_000_000
    out = tmp_path / "outc"
    r = run(str(p), "--outdir", str(out), "--volume", "《乙2:野焚》")
    assert r.returncode == 3, r.stdout
    d = json.loads((out / "diagnose.json").read_text(encoding="utf-8"))
    assert d["chars"] < 5000
    assert d["recommendation"] == "需人工确认"
    assert any("空切片" in n or "过短" in n for n in d["notes"]), d["notes"]


# ================================================================ BUG-4 生僻字造字图
def test_inline_glyph_images_become_visible_markers(tmp_path):
    """正文内联 <img>(古籍生僻字造字图)不许被 get_text 静默吞掉。"""
    book = epub.EpubBook()
    book.set_identifier("glyph-fixture")
    book.set_title("造字图测试")
    book.set_language("zh")
    c = epub.EpubHtml(title="卷之一", file_name="g1.xhtml", lang="zh")
    c.content = ('<html><body><p>臣国藩跪奏:为<img alt="9-142" src="images/f9_142.png"/>'
                 '事,谨陈<img src="images/f9_143.png"/>如左。</p></body></html>')
    book.add_item(c)
    book.toc = (c,)
    book.spine = [c]
    book.add_item(epub.EpubNcx())
    p = tmp_path / "glyph.epub"
    epub.write_epub(str(p), book)

    out = tmp_path / "outg"
    r = run(str(p), "--outdir", str(out))
    assert r.returncode == 0, r.stderr
    txt = (out / "book.txt").read_text(encoding="utf-8")
    assert "〔图字:9-142〕" in txt, "有 alt 时用 alt"
    assert "〔图字:f9_143〕" in txt, "无 alt 时回退 src basename"
    d = json.loads((out / "diagnose.json").read_text(encoding="utf-8"))
    assert d["inline_glyph_images"] == 2, d


# ---------------------------------------------------------------- _anchor_hrefs 单元护栏
# 🔴 立法背景:上面的 `_single_href_volume_unaffected` **挡不住**「无脑丢 hrefs[0]」这种修法 --
# ebooklib 把 href='' 的 Section 写进 NCX 时会把**首个子项的 href 填给它自己**,于是
# all_hrefs = [a1, a1, a2],丢掉第一个仍然得到 a1,两种实现看不出差别(已实测:变异后 20 全绿)。
# 但换成 EPUB3 nav 里 `<li><span>标题</span><ol>…` 这类**真的没有自身链接**的分节标题,
# all_hrefs = [a1, a2],无脑丢第一个就会**静默吞掉整册的第一章**。
# 所以必须直接对 `_anchor_hrefs` 下断言:丢的是「节点自身 href」,不是「列表第一项」。


class _N:
    """最小 TOC 节点 stub(只需 title / href 两个属性)。"""

    def __init__(self, title, href=None):
        self.title = title
        self.href = href


def test_anchor_hrefs_keeps_first_child_when_section_has_no_self_href():
    """分节标题没有自身链接时,首个子项必须保住 -- 丢了就等于吞掉整册第一章。"""
    node = (_N("甲书"), (_N("甲一", "a1.xhtml"), _N("甲二", "a2.xhtml")))
    assert _anchor_hrefs(node) == ["a1.xhtml", "a2.xhtml"]


def test_anchor_hrefs_drops_only_the_section_self_href():
    node = (_N("乙书", "别册.xhtml"), (_N("乙一", "b1.xhtml"), _N("乙二", "b2.xhtml")))
    assert _anchor_hrefs(node) == ["b1.xhtml", "b2.xhtml"]


def test_anchor_hrefs_falls_back_to_self_when_no_children():
    """Link 节点 / 光杆 Section:没有子项时才用自身 href(曾文正公 16 册就是这种)。"""
    assert _anchor_hrefs(_N("单篇", "x.xhtml")) == ["x.xhtml"]
    assert _anchor_hrefs((_N("空节", "y.xhtml"), ())) == ["y.xhtml"]


def test_anchor_hrefs_strips_fragment():
    node = (_N("丙书", "别册.xhtml#top"), (_N("丙一", "c1.xhtml#p3"),))
    assert _anchor_hrefs(node) == ["c1.xhtml"]

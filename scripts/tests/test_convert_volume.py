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
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from convert_book import epub_volumes, extract_epub, diagnose

ebooklib = pytest.importorskip("ebooklib")
pytest.importorskip("bs4")
from ebooklib import epub  # noqa: E402


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

#!/usr/bin/env python3
"""单本书 → book.txt + diagnose.json。exit: 0 正常 / 2 不支持或缺依赖或拒覆盖 / 3 需人工介入(扫描版/乱码率>2%)。

用法: python convert_book.py <input.epub|pdf|txt|azw3|mobi> --outdir <书目录> [--force]
epub/pdf 抽取与 z-library 文件名清洗逻辑改自 文稿成品/58-投资大师理念蒸馏/scripts/convert_books.py。
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

# Windows 管道默认 cp936,打中文 JSON 前必须强制 UTF-8,否则 subprocess 侧解码会崩
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# 章节头召回正则(启发式,只求「有规整标题」的书能召回;纯意译短标题的外版书仍会偏低,接受)。
# 各分支:① 第N章/回/讲/部/篇 与裸 N章(「第N部分」由「部」前缀覆盖);② Chapter N;
# ③ 行首「N. 标题」/「N、标题」(负向前瞻排除 3.14 小数,水平空白防跨行吞标题);
# ④ 罗马数字章「IV. 标题」(要求句点,避免行首 "I am ..." 整句误判)。
CH_PAT = re.compile(
    r"^[ \t]*("
    r"第?\s*[一二三四五六七八九十百0-9]+\s*[章回讲部篇]"
    r"|Chapter\s+\d+"
    r"|\d{1,2}[.、](?!\d)[ \t]*\S"
    r"|[IVXLCDM]{1,9}\.[ \t]*\S"
    r")",
    re.M,
)


def clean_filename(name: str) -> str:
    """去掉 z-library / epubw 等下载站后缀,得到干净书名(复用 58 号项目逻辑)。"""
    name = re.sub(r"\(z-library\.sk.*?\)", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\(1lib\.sk.*?\)", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\(z-lib\.sk.*?\)", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\(epubw\.com.*?\)", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\(\d+\)", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def extract_epub(p: Path) -> str:
    from ebooklib import epub, ITEM_DOCUMENT
    from bs4 import BeautifulSoup
    # ignore_ncx=True: 显式声明,避免 ebooklib 的 FutureWarning/UserWarning 噪音
    book = epub.read_epub(str(p), options={"ignore_ncx": True})
    parts = []
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        parts.append(soup.get_text("\n", strip=True))
    return "\n\n".join(x for x in parts if x)


def extract_pdf(p: Path):
    import fitz
    doc = fitz.open(str(p))
    pages = [pg.get_text() for pg in doc]
    doc.close()
    return "\n".join(pages), len(pages)


# gb18030 误吞检测阈值:常用字占比(实测校准:真简体/中英混排 0.85~1.0;
# big5 误解码 0.27~0.38;shift-jis 误解码 0.0 -- 取 0.6,两侧余量都足)
COMMON_RATIO_MIN = 0.6
_CN_PUNCT = set("，。、；：？！“”‘’（）《》【】—…·")


def common_char_ratio(text: str, sample: int = 20000) -> float:
    """ASCII 可打印 + 常见中文标点 + GB2312 一级常用字(约3755字) 占非空白字符比,采样前 sample 字。"""
    total = good = 0
    for ch in text[:sample]:
        if ch.isspace():
            continue
        total += 1
        if 0x20 <= ord(ch) < 0x7F or ch in _CN_PUNCT:
            good += 1
            continue
        try:
            b = ch.encode("gb2312")
            if len(b) == 2 and 0xB0 <= b[0] <= 0xD7:  # GB2312 一级字区(高频汉字)
                good += 1
        except UnicodeEncodeError:
            pass
    return good / total if total else 0.0


def read_txt(p: Path):
    """txt 直通:先 utf-8 严格,再 gb18030(中文书常见),最后 utf-8 replace 兜底。

    返回 (text, notes, force_manual)。gb18030 码位极宽,Big5/Shift-JIS 字节流大概率能被它
    "严格解码成功"产出不含 � 的假字(鍙戝竷式)-- 所以 gb18030 成功路径必写 note,并做常用字
    占比合理性检查,占比过低时 force_manual=True(调用方降级「需人工确认」/exit 3)。
    """
    raw = p.read_bytes()
    try:
        return raw.decode("utf-8"), [], False
    except UnicodeDecodeError:
        pass
    try:
        text = raw.decode("gb18030")
    except UnicodeDecodeError:
        return (raw.decode("utf-8", errors="replace"),
                ["txt 编码非 utf-8/gb18030,已 replace 兜底,乱码率见 garbled_ratio"], False)
    notes = ["txt 按 gb18030 解码(原文件非 UTF-8),请留意假字风险"]
    ratio = common_char_ratio(text)
    if ratio < COMMON_RATIO_MIN:
        notes.append(f"gb18030 解码后常用字占比仅 {ratio:.0%}(<{COMMON_RATIO_MIN:.0%}),"
                     "疑似 Big5/Shift-JIS 等编码被 gb18030 误吞成假字,需人工确认")
        return text, notes, True
    return text, notes, False


def garbled_ratio(text: str) -> float:
    if not text:
        return 1.0
    bad = sum(1 for ch in text if ch == "�" or (unicodedata.category(ch) == "Cc" and ch not in "\n\r\t"))
    return bad / len(text)


def diagnose(text: str, fmt: str, pages: int) -> dict:
    chapters = CH_PAT.findall(text)
    g = round(garbled_ratio(text), 4)
    # 扫描版判定:PDF 且平均每页可提取字符 < 50 → 基本是纯图,需 OCR
    is_scanned = fmt == "pdf" and pages > 0 and len(text.strip()) / max(pages, 1) < 50
    if is_scanned:
        rec = "需OCR"
    elif g > 0.02:
        rec = "需人工确认"
    elif len(text) > 800_000:
        rec = "分组蒸馏"
    else:
        rec = "直接蒸馏"
    return {"format": fmt, "extractable": not is_scanned, "is_scanned": is_scanned,
            "pages_est": pages, "chars": len(text), "garbled_ratio": g,
            "toc_detected": len(chapters) >= 3, "chapters_detected": len(chapters),
            "recommendation": rec, "notes": []}


def main():
    ap = argparse.ArgumentParser(description="单本电子书 → book.txt + diagnose.json")
    ap.add_argument("input", help="电子书路径(epub/pdf/txt/azw3/mobi)")
    ap.add_argument("--outdir", required=True, help="输出书目录")
    ap.add_argument("--force", action="store_true", help="book.txt 已存在时强制覆盖")
    a = ap.parse_args()
    src, out = Path(a.input), Path(a.outdir)
    if not src.is_file():
        print(f"输入文件不存在: {src}", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    txt_path = out / "book.txt"
    if txt_path.exists() and not a.force:
        print(f"{txt_path} 已存在,防覆盖拒跑;确认重转请加 --force", file=sys.stderr)
        return 2
    title = clean_filename(src.stem)
    orig_src = src  # diagnose 的 input 永远记录原始文件,不记中间产物 _converted.epub
    notes = []
    force_manual = False
    fmt = src.suffix.lower().lstrip(".")
    if fmt in ("azw3", "mobi"):
        if not shutil.which("ebook-convert"):
            print(f"{fmt} 需 calibre 的 ebook-convert,请先安装: winget install calibre.calibre", file=sys.stderr)
            return 2
        tmp_epub = out / "_converted.epub"
        # encoding 显式 utf-8:Windows text=True 默认 cp936,calibre 输出含非 GBK 字节会裸崩
        cv = subprocess.run(["ebook-convert", str(src), str(tmp_epub)],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
        if cv.returncode != 0 or not tmp_epub.is_file():
            print(f"ebook-convert 转换 {fmt} 失败(exit {cv.returncode}):\n{(cv.stderr or cv.stdout or '').strip()[-800:]}", file=sys.stderr)
            return 2
        notes.append(f"{fmt} 已经 ebook-convert 先转 epub 再抽取(中间产物 {tmp_epub.name})")
        src, fmt = tmp_epub, "epub"
    pages = 0
    if fmt == "epub":
        text = extract_epub(src)
    elif fmt == "pdf":
        text, pages = extract_pdf(src)
    elif fmt == "txt":
        text, txt_notes, force_manual = read_txt(src)
        notes.extend(txt_notes)
    else:
        print(f"不支持的格式: {fmt}(支持 epub/pdf/txt/azw3/mobi)", file=sys.stderr)
        return 2
    d = diagnose(text, fmt, pages)
    d["notes"].extend(notes)
    if force_manual and d["recommendation"] != "需OCR":
        d["recommendation"] = "需人工确认"  # gb18030 误吞疑似假字,降级人工介入
    d = dict(d, input=str(orig_src), title=title)
    (out / "diagnose.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    txt_path.write_text(text, encoding="utf-8")
    print(json.dumps(d, ensure_ascii=False, indent=1))
    return 3 if d["recommendation"] in ("需OCR", "需人工确认") else 0


if __name__ == "__main__":
    sys.exit(main())

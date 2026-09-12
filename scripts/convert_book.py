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
# 行首允许一个装饰符 [｜|〔【] -- 全角竖线 U+FF5C 是中文传记常见的章标题包裹符(「｜第一章｜ …」)。
# 各分支:① 第N章/回/讲/部/篇/卷/辑 与裸 N章(「第N部分」由「部」前缀覆盖);② Chapter N;
# ③ 行首「N. 标题」/「N、标题」/「N．标题」(全角句点 U+FF0E 是中文书常见小节序号;
#    负向前瞻排除 3.14 小数,水平空白防跨行吞标题);
# ④ 罗马数字章「IV. 标题」(要求句点,避免行首 "I am ..." 整句误判);
# ⑤ 中文古籍「体裁名 + 卷N」/「卷之N」(「奏稿 卷一」「卷之十四」)-- 曾国藩这类刻本全集的唯一版式。
CH_PAT = re.compile(
    r"^[ \t]*[｜|〔【]?("
    r"第?\s*[一二三四五六七八九十百0-9]+\s*[章回讲部篇卷辑]"
    r"|Chapter\s+\d+"
    r"|\d{1,2}[.、．](?!\d)[ \t]*\S"
    r"|[IVXLCDM]{1,9}\.[ \t]*\S"
    r"|\S{0,8}[ \t]?卷[之一二三四五六七八九十]"
    r")",
    re.M,
)


# 空切片守卫阈值:容器文件大于 EMPTY_SLICE_CONTAINER_BYTES 而分册正文不足 EMPTY_SLICE_CHARS 字,
# 判为「锚点切错/只拿到封面页」,降级需人工确认(exit 3),不许静默当成一本书交出去。
EMPTY_SLICE_CHARS = 5000
EMPTY_SLICE_CONTAINER_BYTES = 1_000_000


def clean_filename(name: str) -> str:
    """去掉 z-library / epubw 等下载站后缀,得到干净书名(复用 58 号项目逻辑)。"""
    name = re.sub(r"\(z-library\.sk.*?\)", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\(1lib\.sk.*?\)", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\(z-lib\.sk.*?\)", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\(epubw\.com.*?\)", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\(\d+\)", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _toc_walk(node, hrefs: list, titles: list, depth: int = 0):
    """递归遍历 ebooklib 的 TOC 树,收集 href(去 fragment)与标题。
    节点形态有三种:Link / Section / (Section, [children]) 元组。"""
    if isinstance(node, (tuple, list)):
        for x in node:
            _toc_walk(x, hrefs, titles, depth)
        return
    t = getattr(node, "title", None)
    if t:
        titles.append(str(t))
    h = getattr(node, "href", None)
    if h:
        hrefs.append(str(h).split("#")[0])


def _href_of(node) -> str | None:
    h = getattr(node, "href", None)
    return str(h).split("#")[0] if h else None


def _anchor_hrefs(node) -> list:
    """顶层 TOC 节点的**正文锚点** href -- 有子项时只认子项,丢掉 Section 自身那个。

    🔴 2026-08-25 曾国藩 12 册套装实证:NCX 里每个「曾国藩全集 N」顶层 Section **自身也带
    href**,而它指向的是**别册**的正文文件(第 11 册《家书》的自身 href 指到奏稿卷十四)。
    自身 href 混进 hrefs 后 `min(...)` 就锚到别的书上 -- 要家书拿回奏稿,exit 0 零警告。
    子项 href 才是这一册真正的正文起点,所以有子项时自身 href 一律不参与算区间;
    没有子项(Link 节点 / 光杆 Section)才回退用它自己。
    """
    if isinstance(node, (tuple, list)) and len(node) == 2 and isinstance(node[1], (tuple, list)):
        head, children = node
        child_hrefs = []
        _toc_walk(children, child_hrefs, [])
        if child_hrefs:
            return child_hrefs
        h = _href_of(head)
        return [h] if h else []
    hrefs = []
    _toc_walk(node, hrefs, [])
    return hrefs


def epub_volumes(book) -> list:
    """套装/合集 epub 的顶层分册:[(分册名, [正文锚点 href…], [TOC 标题…])]。
    单本书的 TOC 顶层就是各章,此时「分册」概念不成立 -- 由调用方按数量与命中情况判断。"""
    vols = []
    for node in book.toc:
        _h, titles = [], []
        _toc_walk(node, _h, titles)
        name = titles[0] if titles else "?"
        vols.append((name, _anchor_hrefs(node), titles))
    return vols


def _spine_docs(book) -> list:
    """按 spine(阅读顺序)取正文文档;spine 缺失时回退 get_items_of_type 的原始顺序。"""
    from ebooklib import ITEM_DOCUMENT
    out = []
    for idref, *_ in (book.spine or []):
        it = book.get_item_with_id(idref)
        if it is not None and it.get_type() == ITEM_DOCUMENT:
            out.append(it)
    return out or list(book.get_items_of_type(ITEM_DOCUMENT))


def _base(name: str) -> str:
    """href/item name 归一到 basename -- 两者常带不同的相对路径前缀(OEBPS/ 、../ 等)。"""
    return str(name).replace("\\", "/").rsplit("/", 1)[-1]


class VolumeError(KeyError):
    """分册寻址失败(不存在 / 同名歧义 / 下标越界)。继承 KeyError 保持向后兼容。"""


GLYPH_MARK = "〔图字:"


def _mark_inline_images(soup) -> None:
    """把正文内联 <img> 换成可见标记,而不是让 get_text() 静默吞掉。

    🔴 中文古籍电子书用**造字图**表示生僻字(曾文正公 16 册正文内联 img 2975 处、
    家书 2137 处)。`soup.get_text()` 直接丢掉 <img>,字就凭空消失,而 garbled_ratio
    检测不到(12 册实测 U+FFFD 比率 0.0002,远低于 0.02 阈值)-- 静默缺字。
    """
    for img in soup.find_all("img"):
        alt = (img.get("alt") or "").strip()
        if not alt:
            src = img.get("src") or img.get("xlink:href") or ""
            alt = _base(src).rsplit(".", 1)[0] or "?"
        img.replace_with(f"{GLYPH_MARK}{alt[:40]}〕")


def extract_epub(p: Path, volume: str | None = None,
                 volume_index: int | None = None, info: dict | None = None) -> tuple:
    """→ (正文文本, TOC 标题列表)。

    volume / volume_index 非空时只抽该分册(套装合集按 TOC 顶层切分):以该分册在 spine 里的
    **区间**为准,而非只取 TOC 列出的那几篇 -- 未列入 TOC 的正文续页也要收进来,否则静默丢正文。
    volume_index 是 --list-volumes 输出的数组下标(0-based),用于同名分册寻址。
    info 非 None 时回填 {"volume_name": …, "volume_index": …} -- 避免调用方为拿分册名重读一遍 epub。
    """
    from ebooklib import epub
    from bs4 import BeautifulSoup
    # ignore_ncx=True: 显式声明,避免 ebooklib 的 FutureWarning/UserWarning 噪音
    book = epub.read_epub(str(p), options={"ignore_ncx": True})
    docs = _spine_docs(book)
    toc_titles = []
    if volume or volume_index is not None:
        vols = epub_volumes(book)
        names = [v[0] for v in vols]
        if volume_index is not None:
            if not (0 <= volume_index < len(vols)):
                raise VolumeError(f"--volume-index {volume_index} 越界;该 epub 顶层共 {len(vols)} 个分册"
                                  f"(合法下标 0..{len(vols) - 1});可选: {names}")
            hit = volume_index
        else:
            exact = [i for i, n in enumerate(names) if n == volume]
            # 🔴 同名分册不许静默取第一个:唐浩明套装顶层三个节点都叫「目录」,
            #    首个精确匹配胜出 = 第 2、3 册在 CLI 下**根本无法寻址**,且切出来的是第 1 册。
            if len(exact) > 1:
                raise VolumeError(f"分册名 {volume!r} 在顶层目录中出现 {len(exact)} 次(下标 {exact}),"
                                  f"无法确定要哪一册;请改用 --volume-index <下标>。全部分册: {names}")
            hit = exact[0] if exact else None
            if hit is None:  # 退一步做包含匹配,容忍分册名带书名号/副标题
                fuzzy = [i for i, n in enumerate(names) if volume in n or n in volume]
                if len(fuzzy) > 1:
                    raise VolumeError(f"分册名 {volume!r} 模糊匹配到 {len(fuzzy)} 个节点(下标 {fuzzy}),"
                                      f"无法确定要哪一册;请改用 --volume-index <下标>。全部分册: {names}")
                hit = fuzzy[0] if fuzzy else None
            if hit is None:
                raise VolumeError(f"分册 {volume!r} 不在该 epub 的顶层目录中;可选: {names}")
        if info is not None:
            info["volume_name"], info["volume_index"] = names[hit], hit
        toc_titles = vols[hit][2]
        pos = {_base(d.get_name()): i for i, d in enumerate(docs)}
        starts = [pos[_base(h)] for h in vols[hit][1] if _base(h) in pos]
        if not starts:
            raise VolumeError(f"分册 {names[hit]!r} 的目录项无法对应到正文文档(epub 结构异常)")
        start = min(starts)
        # 终点 = 下一个**有正文落点**的分册起点;没有则到全书末尾。
        # 这里用的同样是 _anchor_hrefs 过滤后的锚点 -- 后续分册的自身 href 若指向靠前的
        # 别册文件,会把终点提前,正文被腰斩(甲书只剩第一篇)。
        later = []
        for _nm, hs, _t in vols[hit + 1:]:
            ps = [pos[_base(h)] for h in hs if _base(h) in pos]
            if ps:
                later.append(min(ps))
        end = min(p_ for p_ in later if p_ > start) if any(p_ > start for p_ in later) else len(docs)
        docs = docs[start:end]
    else:
        _h, toc_titles = [], []
        _toc_walk(book.toc, _h, toc_titles)
    parts = []
    for item in docs:
        soup = BeautifulSoup(item.get_content(), "html.parser")
        _mark_inline_images(soup)
        parts.append(soup.get_text("\n", strip=True))
    return "\n\n".join(x for x in parts if x), toc_titles


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


def diagnose(text: str, fmt: str, pages: int, toc_titles: list | None = None) -> dict:
    # 章数两路取大:正文启发式正则 vs epub TOC 里出版方声明的章标题。
    #   TOC 更可靠(意译短标题的外版书、分册切出来的正文,正文正则常召回为 0-1),
    #   但 TOC 也可能只列到「部」这一层,故不单用 TOC、取两者较大值。
    n_body = len(CH_PAT.findall(text))
    n_toc = len([t for t in (toc_titles or []) if CH_PAT.search(t)])
    chapters = [None] * max(n_body, n_toc)
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
            "chapters_source": "epub_toc" if n_toc > n_body else "body_regex",
            # 正文内联造字图数量:>0 说明这本书用图片表示生僻字,引文里会看到〔图字:…〕标记
            "inline_glyph_images": text.count(GLYPH_MARK),
            "recommendation": rec, "notes": []}


def main():
    ap = argparse.ArgumentParser(description="单本电子书 → book.txt + diagnose.json")
    ap.add_argument("input", help="电子书路径(epub/pdf/txt/azw3/mobi)")
    ap.add_argument("--outdir", help="输出书目录(仅 --list-volumes 时可省)")
    ap.add_argument("--force", action="store_true", help="book.txt 已存在时强制覆盖")
    ap.add_argument("--volume", help="套装/合集 epub:只抽这一个分册(按 TOC 顶层分册名);先用 --list-volumes 查名字。同名分册会报错,改用 --volume-index")
    ap.add_argument("--volume-index", type=int,
                    help="套装/合集 epub:按 --list-volumes 输出的数组下标(0-based)抽分册;同名分册(如三个「目录」)只能这样寻址")
    ap.add_argument("--list-volumes", action="store_true",
                    help="列出 epub 顶层分册名与各自章数后退出(不写任何文件);判断是不是套装合集用这个")
    a = ap.parse_args()
    if a.volume and a.volume_index is not None:
        print("--volume 与 --volume-index 只能二选一", file=sys.stderr)
        return 2
    src, out = Path(a.input), Path(a.outdir) if a.outdir else Path(".")
    if not src.is_file():
        print(f"输入文件不存在: {src}", file=sys.stderr)
        return 2
    if a.list_volumes:
        if src.suffix.lower() != ".epub":
            print("--list-volumes 只支持 epub", file=sys.stderr)
            return 2
        from ebooklib import epub as _epub
        vols = epub_volumes(_epub.read_epub(str(src), options={"ignore_ncx": True}))
        # index 显式打出来:同名分册(唐浩明套装三个「目录」)只能靠 --volume-index 寻址
        print(json.dumps([{"index": i, "volume": n, "toc_entries": len(t),
                           "chapters_detected": len([x for x in t if CH_PAT.search(x)])}
                          for i, (n, _h, t) in enumerate(vols)], ensure_ascii=False, indent=1))
        return 0
    if not a.outdir:
        print("缺 --outdir(只有 --list-volumes 可省)", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    txt_path = out / "book.txt"
    if txt_path.exists() and not a.force:
        print(f"{txt_path} 已存在,防覆盖拒跑;确认重转请加 --force", file=sys.stderr)
        return 2
    # 切分册时书名取分册名,不取套装文件名(否则 6 本 diagnose 的 title 全叫「…套装共5册」)
    title = a.volume if a.volume else clean_filename(src.stem)
    orig_src = src  # diagnose 的 input 永远记录原始文件,不记中间产物 _converted.epub
    notes = []
    force_manual = False
    fmt = src.suffix.lower().lstrip(".")
    if fmt in ("azw3", "mobi"):
        if not shutil.which("ebook-convert"):
            print(f"{fmt} 需 calibre 的 ebook-convert,请先安装: brew install --cask calibre（Windows: winget install calibre.calibre）", file=sys.stderr)
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
    toc_titles = []
    if fmt == "epub":
        vinfo: dict = {}
        try:
            text, toc_titles = extract_epub(src, a.volume, a.volume_index, vinfo)
        except KeyError as e:
            print(e.args[0] if e.args else str(e), file=sys.stderr)
            return 2
        if vinfo:
            title = vinfo["volume_name"]  # 分册名以 TOC 实际节点为准(--volume-index 时 a.volume 为空)
            notes.append(f"从套装/合集 epub 按 TOC 切出分册「{title}」(顶层下标 {vinfo['volume_index']})")
    elif a.volume or a.volume_index is not None:
        print("--volume / --volume-index 只支持 epub 输入", file=sys.stderr)
        return 2
    elif fmt == "pdf":
        text, pages = extract_pdf(src)
    elif fmt == "txt":
        text, txt_notes, force_manual = read_txt(src)
        notes.extend(txt_notes)
    else:
        print(f"不支持的格式: {fmt}(支持 epub/pdf/txt/azw3/mobi)", file=sys.stderr)
        return 2
    d = diagnose(text, fmt, pages, toc_titles)
    d["notes"].extend(notes)
    # 🔴 空切片守卫:容器上兆而分册只切出几百字 = 锚点切错了(唐浩明套装按书名切,
    #    拿到的是 589 字的封面+版权页,却照样 recommendation:直接蒸馏 + exit 0)。
    if (a.volume or a.volume_index is not None) and len(text) < EMPTY_SLICE_CHARS \
            and orig_src.stat().st_size > EMPTY_SLICE_CONTAINER_BYTES:
        d["notes"].append(
            f"疑似空切片:容器文件 {orig_src.stat().st_size / 1e6:.1f}MB 却只切出 {len(text)} 字"
            f"(<{EMPTY_SLICE_CHARS}),多半只拿到封面/版权页或锚点切错;"
            "请用 --list-volumes 核对下标后改用 --volume-index")
        force_manual = True
    if force_manual and d["recommendation"] != "需OCR":
        d["recommendation"] = "需人工确认"  # gb18030 误吞疑似假字,降级人工介入
    d = dict(d, input=str(orig_src), title=title)
    (out / "diagnose.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    txt_path.write_text(text, encoding="utf-8")
    print(json.dumps(d, ensure_ascii=False, indent=1))
    return 3 if d["recommendation"] in ("需OCR", "需人工确认") else 0


if __name__ == "__main__":
    sys.exit(main())

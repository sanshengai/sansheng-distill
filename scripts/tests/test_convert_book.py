# convert_book.py 的 6 用例测试 -- fixture 全部程序化构造,不依赖真书
import json, subprocess, sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "convert_book.py"

def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, encoding="utf-8")

def make_epub(path: Path, n_chapters=3):
    from ebooklib import epub
    bk = epub.EpubBook(); bk.set_title("测试小书"); bk.set_language("zh")
    items = []
    for i in range(1, n_chapters + 1):
        c = epub.EpubHtml(title=f"第{i}章 标题{i}", file_name=f"ch{i}.xhtml", lang="zh")
        c.content = f"<h1>第{i}章 标题{i}</h1>" + f"<p>这是第{i}章的正文内容。</p>" * 40
        bk.add_item(c); items.append(c)
    bk.toc = items; bk.spine = ["nav"] + items
    bk.add_item(epub.EpubNcx()); bk.add_item(epub.EpubNav())
    epub.write_epub(str(path), bk)

def make_pdf(path: Path, with_text=True):
    import fitz
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        if with_text:
            page.insert_text((72, 72), f"Chapter {i+1}\n" + "text line. " * 60)
    doc.save(str(path)); doc.close()

def test_epub_converts(tmp_path):
    src = tmp_path / "b.epub"; make_epub(src)
    r = run(str(src), "--outdir", str(tmp_path / "out"))
    assert r.returncode == 0
    txt = (tmp_path / "out" / "book.txt").read_text(encoding="utf-8")
    assert "第2章" in txt and "正文内容" in txt
    d = json.loads((tmp_path / "out" / "diagnose.json").read_text(encoding="utf-8"))
    assert d["format"] == "epub" and d["chapters_detected"] >= 3
    assert d["recommendation"] == "直接蒸馏"

def test_pdf_converts(tmp_path):
    src = tmp_path / "b.pdf"; make_pdf(src)
    r = run(str(src), "--outdir", str(tmp_path / "out"))
    assert r.returncode == 0
    d = json.loads((tmp_path / "out" / "diagnose.json").read_text(encoding="utf-8"))
    assert d["format"] == "pdf" and d["extractable"] is True

def test_scanned_pdf_flagged(tmp_path):
    src = tmp_path / "scan.pdf"; make_pdf(src, with_text=False)
    r = run(str(src), "--outdir", str(tmp_path / "out"))
    assert r.returncode == 3
    d = json.loads((tmp_path / "out" / "diagnose.json").read_text(encoding="utf-8"))
    assert d["is_scanned"] is True and d["recommendation"] == "需OCR"

def test_txt_passthrough(tmp_path):
    src = tmp_path / "b.txt"
    src.write_text("第一章 开头\n" + "内容。" * 500, encoding="utf-8")
    r = run(str(src), "--outdir", str(tmp_path / "out"))
    assert r.returncode == 0
    assert (tmp_path / "out" / "book.txt").exists()

def test_unsupported_format(tmp_path):
    src = tmp_path / "b.docx"; src.write_bytes(b"xx")
    r = run(str(src), "--outdir", str(tmp_path / "out"))
    assert r.returncode == 2 and "docx" in r.stderr

def test_refuses_overwrite_without_force(tmp_path):
    src = tmp_path / "b.txt"; src.write_text("内容" * 100, encoding="utf-8")
    out = tmp_path / "out"
    assert run(str(src), "--outdir", str(out)).returncode == 0
    assert run(str(src), "--outdir", str(out)).returncode == 2  # book.txt 已存在,拒跑
    assert run(str(src), "--outdir", str(out), "--force").returncode == 0

def test_big5_txt_misdecode_flagged(tmp_path):
    # Big5 繁体字节流会被 gb18030 严格解码"成功"产出假字(不含�,乱码率≈0)
    # 必须被常用字占比合理性检查拦下:notes 非空 + 需人工确认 + exit 3
    src = tmp_path / "big5.txt"
    src.write_bytes(("這是繁體中文測試內容,講述投資的第一章節。" * 200).encode("big5"))
    r = run(str(src), "--outdir", str(tmp_path / "out"))
    assert r.returncode == 3
    d = json.loads((tmp_path / "out" / "diagnose.json").read_text(encoding="utf-8"))
    assert d["recommendation"] == "需人工确认"
    assert len(d["notes"]) > 0 and any("gb18030" in n for n in d["notes"])

def test_gbk_txt_ok_with_note(tmp_path):
    # 真 GBK 简体书:合理性检查不得误伤(exit 0),但 notes 必须透出走了 gb18030
    src = tmp_path / "gbk.txt"
    src.write_bytes(("第一章 投资的基本原则。这是正常的简体中文内容。" * 200).encode("gbk"))
    r = run(str(src), "--outdir", str(tmp_path / "out"))
    assert r.returncode == 0
    d = json.loads((tmp_path / "out" / "diagnose.json").read_text(encoding="utf-8"))
    assert d["recommendation"] == "直接蒸馏"
    assert any("gb18030" in n for n in d["notes"])

def test_numbered_dot_chapters_detected(tmp_path):
    # 规整「N. 标题」版式(章标题独占一行):增强正则须召回全部 12 章,toc_detected=true。
    # 老正则(仅 第N章/Chapter N)对此漏判,本用例先红后绿。
    lines = []
    for i in range(1, 13):
        lines.append(f"{i}. 第{i}个主题的标题")            # 章头独占一行
        lines.append("这一章阐述其中的道理与依据。" * 50)   # 正文(不含章头模式)
    src = tmp_path / "numbered.txt"
    src.write_text("\n".join(lines), encoding="utf-8")
    r = run(str(src), "--outdir", str(tmp_path / "out"))
    assert r.returncode == 0, r.stderr
    d = json.loads((tmp_path / "out" / "diagnose.json").read_text(encoding="utf-8"))
    assert d["chapters_detected"] == 12          # 12 个「N. 标题」全召回
    assert d["toc_detected"] is True             # >=3 章 → 判有目录
    assert d["recommendation"] == "直接蒸馏"

def test_freeform_titles_low_but_no_error(tmp_path):
    # 纯意译短标题(不含 第N章 / N. / 罗马数字):增强正则仍召回不足 -- 这是外版书固有局限。
    # 断言:① 不报错(exit 0);② chapters_detected 偏低;③ recommendation 仍「直接蒸馏」-- 局限不阻断蒸馏。
    titles = ["最重要的事是二阶思维", "理解风险", "识别风险", "控制风险",
              "关注周期", "钟摆意识", "抵御负面影响", "警惕心理偏差"]
    parts = []
    for t in titles:
        parts.append(t)
        parts.append("这是这一节的正文,阐述其中的观点与例证。" * 60)
    src = tmp_path / "freeform.txt"
    src.write_text("\n".join(parts), encoding="utf-8")
    r = run(str(src), "--outdir", str(tmp_path / "out"))
    assert r.returncode == 0, r.stderr                 # 不报错
    d = json.loads((tmp_path / "out" / "diagnose.json").read_text(encoding="utf-8"))
    assert d["chapters_detected"] < len(titles)        # 召回不足(固有局限)
    assert d["recommendation"] == "直接蒸馏"            # 局限不阻断蒸馏

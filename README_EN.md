# sansheng-distill · Book Distillation Engine

> Turn a book (or a video series) into a single-file, clickable, ever-deepening **interactive web page**.

[中文](./README.md) | **English**

<p align="center">
  <img src="assets/demo.gif" alt="Demo: distilling Yuval Noah Harari's four books with this skill" width="100%">
  <br>
  <sub><em>▲ Distilling Yuval Noah Harari's four books into one "collected works" page: thought evolution, concept drift, recurring themes, cross-book links (12s silent loop)</em></sub>
</p>

## What it is

Feed it a book (`.epub` / `.pdf` / `.txt` / `.azw3` / `.mobi`), or a set of videos, and it runs a multi-step pipeline that produces **one self-contained HTML page you can just double-click open** -- no network, no server, one file is everything.

It is not a "summary." A summary shortens a book and you toss it after reading; a distillation turns the book into **a knowledge map**: a one-line formula, a clickable mind-map, chapter-by-chapter deep reads you can expand, a set of read-and-review self-check questions, plus web-enriched author profiles, for/against reviews, cross-book views, and automatic links to the other books you've distilled. **AI book distillation is a map to use, not a substitute for reading the original** -- that line stays pinned at the bottom of every page.

## See the output before you install

It isn't a GUI app, so there are no "operation screenshots" -- but its **output** is visual. Below is real output (the Harari four-book collection, plus the single-book page for *Sapiens*):

<table>
<tr>
<td width="50%"><img src="assets/01-at-a-glance.png" width="100%"><br><sub><b>At a glance + napkin formula</b> -- real cover, one-line formula, core claims, mind-map, key quotes: the whole skeleton in one screen.</sub></td>
<td width="50%"><img src="assets/02-mindmap.png" width="100%"><br><sub><b>Clickable mind-map</b> -- nodes expand; click one to jump to its chapter.</sub></td>
</tr>
<tr>
<td><img src="assets/03-chapter-deep-read.png" width="100%"><br><sub><b>Chapter deep read</b> -- each chapter expands on its own, a faithful retelling.</sub></td>
<td><img src="assets/04-core-idea.png" width="100%"><br><sub><b>The core hit</b> -- the book's single most counter-intuitive claim, as one visualization.</sub></td>
</tr>
<tr>
<td><img src="assets/05-action-checklist.png" width="100%"><br><sub><b>Action list</b> -- decision rules, mental models, an action road-map.</sub></td>
<td><img src="assets/06-critique.png" width="100%"><br><sub><b>Critique & blind spots</b> -- author blind spots, era limits, with sourced reviews.</sub></td>
</tr>
</table>

## What it actually does -- a five-stage reading funnel on one page

A distilled book is one page that unfolds layer by layer, from a 3-second glance down to a deep dig:

| Stage | What you see |
|---|---|
| **① At a glance** | Real cover + a one-line "napkin formula" + core claims + clickable mind-map + key quotes -- grab the whole skeleton in 3 seconds |
| **② Chapter deep read** | 800-1500 chars of faithful retelling per chapter, each expandable, not label-style bullets |
| **③ The core hit** | The book's single most counter-intuitive claim, made into one visualization |
| **④ Act & self-check** | Causal chains, mental models, decision rules, plus read-and-review self-check questions (read-only, no scoring) |
| **⑤ How much to believe / going further** | Critique, internal tensions, for/against reviews, similar books, cross-book echoes, author profile -- all with clickable sources |

On top of that, three interactive layers: a **clickable mind-map** (hand-drawn SVG, no third-party lib) · **7 one-click color themes** · **cross-book knowledge links** (the more books you distill, the denser the web).

When you distill a whole set (like Harari's four), it also synthesizes an **author collection page**: a thought-evolution timeline, how concepts drift across books, the themes that run through all of them, and a "where to start reading" route -- that's the page in the demo above.

## It can also distill *a person*, not just a work (v0.5.0)

Everything above turns **one work** into one page. Since v0.5.0 there is a second path: turn **everything one creator has published across media** -- hundreds of videos + a newsletter + books + podcasts -- into a map of their thinking.

The unit of analysis is different. The first asks "what does this book say"; the second asks "what is this person's system of ideas, and how did it change." So it doesn't distill each work separately and staple the results together: it collects everything, builds an evidence base entry by entry, clusters across media into **idea families** (a point he made in a video and again in a newsletter counts once), then distills the systems, action models, thought trajectory and internal tensions -- with a cross-check pass against third-party commentary in both English and Chinese.

First case study, Dan Koe: 162 videos + 212 letters + 25 book chapters, synthesized into 399 sources, 1,836 pieces of evidence, 299 idea families.

## When to use

Say *"distill this book"*, *"拆这本书"*, *"distill this video series"*, *"distill this creator"*, or just drop an ebook file and ask for a distillation page -- Claude picks up this skill and runs the whole pipeline.

**Not** for: writing an article, editing a video, or just wanting subtitles or a plain summary.

## Install

As a Claude Code plugin (recommended):

```bash
claude plugin marketplace add sanshengai/sansheng-distill
claude plugin install sansheng-distill
```

Or manually: clone and symlink into `~/.claude/skills/`:

```bash
git clone https://github.com/sanshengai/sansheng-distill.git
ln -s "$PWD/sansheng-distill" ~/.claude/skills/sansheng-distill
```

Then restart Claude Code.

## Updating

How you update depends on how you installed:

- **Via the plugin marketplace**: `claude plugin marketplace update`, then `claude plugin update sansheng-distill`
- **Via clone + symlink**: `git pull` in the repo -- the symlink picks it up immediately, no reinstall

To hear about new versions: watch the repo's [Releases](../../releases), or click **Watch -> Custom -> Releases** and GitHub will notify you. See the [CHANGELOG](CHANGELOG.md) for what changed in each version.

## Quick start

```bash
pip install ebooklib beautifulsoup4 pymupdf pillow playwright
playwright install chromium
# .azw3 / .mobi input also needs calibre's `ebook-convert`
cp .env.example .env        # then set DISTILL_DATA_DIR (and the video keys if you use the video path)
```

Then, in Claude Code, just ask it to distill a book. The pipeline (Step0-Step7) is in [`SKILL.md`](./SKILL.md); each step's details live under [`references/`](./references/).

## Configuration

- `DISTILL_DATA_DIR` -- where your book data and outputs live (see [`.env.example`](./.env.example)).
- Video path (optional): `GOOGLE_API_KEY`, `AI_DOUYIN_API_KEY`, `yt-dlp`.
- Theme: the page ships 7 color themes; switch anytime from the bottom-right switcher.

## Article

A companion write-up -- on how this skill came to be, which book-distillation traditions it blends, and what we added of our own -- is coming soon; link to follow.

## About the author · 关于作者

<p align="center">
  <a href="https://sanshengai.top"><strong>🌐 sanshengai.top</strong></a> ·
  <a href="https://namecard.xiaoyuzhoufm.com/nnl8x"><strong>🎧 Xiaoyuzhou (podcast)</strong></a> ·
  <a href="https://weibo.com/u/7546221967"><strong>Weibo</strong></a> ·
  <a href="https://www.xiaohongshu.com/user/profile/5c716b6d000000001000f5c4"><strong>Xiaohongshu</strong></a> ·
  <a href="mailto:sandypoli@gmail.com"><strong>✉️ Email</strong></a>
</p>

I'm **叁笙 (sansheng)** -- I use AI to make content and to build tools. This skill is what I ground out in real workflows while making「[叁笙早安 AI](https://sanshengai.top)」(*Sansheng Good Morning AI*), my personal site, then cleaned up and open-sourced. If it's useful, come look around the [site](https://sanshengai.top), or **scan to follow the WeChat account「叁笙早安AI」** (WeChat accounts have no click-through link, so scanning is quickest):

<p align="center">
  <img src="assets/qrcode-gongzhonghao.png" alt="WeChat official account 叁笙早安AI" width="200">
  <br><sub>Scan in WeChat to follow · 叁笙早安AI</sub>
</p>

## Credits & Dependencies

### Credits (what we drew on)

This distillation approach didn't come from nowhere; we studied and blended lessons from a number of fine community "book-distillation / reading / frontend" projects. Thanks to:

- **[crayon-ai/book-to-webpage](https://github.com/crayon-ai/book-to-webpage)** (MIT) -- the main reference for page design (layout, palettes, theme switcher); what we drew on most.
- **Li Jigang (李继刚)**'s book-distillation skill -- the "napkin formula / back-of-the-napkin" idea comes from him (that one idea only, not the whole method).
- Anthropic's **frontend-design** and Jim Liu's **baoyu-design** -- influences on frontend taste and design direction.

> The mind-map (hand-drawn SVG), chapter expansion, theme switching and other interactions are our own implementations; this repo **bundles no third-party library code**. The above are idea-level credits.

### Runtime dependencies (install separately; not bundled)

| Dependency | Purpose | When needed |
|---|---|---|
| `ebooklib` · `beautifulsoup4` · `pymupdf` · `pillow` · `playwright` (+ `playwright install chromium`) | Book parsing + page verification | Always |
| `calibre` (`ebook-convert`) | Convert `.azw3` / `.mobi` | Only for those input formats |
| `yt-dlp` | Fetch subtitles / comments | Video-series path only |
| A subtitle / ASR tool | Transcribe subtitle-less video | Only for non-YouTube, subtitle-less video series |
| Sibling skill [`sansheng-gemini-video`](https://github.com/sanshengai/sansheng-gemini-video) | Understand video frames / audio | Only for video series needing visual understanding (not for books) |

**License note.** This repo ships under MIT and bundles no third-party code. The runtime dependencies above are installed by you and keep their own licenses.

## License

[MIT](LICENSE) © 2026 叁笙 (sansheng)

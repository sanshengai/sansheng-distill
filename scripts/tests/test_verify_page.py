import sys
import re
import json
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from verify_page import (lint_html, lint_distill, lint_enrich_consistency, lint_mindmap,
                         lint_author_html, is_author_page)  # 纯函数:-> list[str] 违规

SKILL_ROOT = Path(__file__).resolve().parents[2]  # tests -> scripts -> 仓根
SKELETON = SKILL_ROOT / "templates" / "page-skeleton.html"
AUTHOR_SKELETON = SKILL_ROOT / "templates" / "author-page-skeleton.html"

# ---------------------------------------------------------------- HTML fixtures (v3:5 板块签名 class)
TOKENS = ':root{--ink:#171411;--red:#c0392b;--gold:#b8860b}body[data-theme="dark"]{--ink:#ddd}'
# v3 五 tab:(panel id, A 套名词式主名)
TABS = [("panel-glance", "全书速览"), ("panel-full", "逐章精读"), ("panel-judge", "批判与评价"),
        ("panel-action", "行动清单"), ("panel-extend", "延伸阅读")]
COVER = '<img class="cb-cover" alt="封面" src="data:image/svg+xml,%3Csvg/%3E">'
NAPKIN_ONE_LINER = "投资成功靠的是纪律而非聪明,少犯错胜过多正确"
FORMULA_READ = "为什么是减法:买价越低于价值,安全垫越厚;二者相等就毫无缓冲,这份余地是减出来的。"
GOOD_TITLE = "先估价值再看价格才不会追涨杀跌"
GOOD_CH = ('<section class="bd-chapter" id="ch-1" data-source="第1章">'
           f'<h3>{GOOD_TITLE}</h3><p>坡道开场,论证主体,叙事整段完整讲。</p>'
           '<p class="src-note">本章出处:第1章</p></section>')
# 脑图数据契约(§5,自绘 SVG 版):一级分支挂 hyperLink 二级(#ch-1 对齐 GOOD_CH)+ 二级带 tags[0] 判断句 + tags[1] 章码 chip。
# SVG 版只画父子引线、不画关联,故不含 arrows/summaries(残留也被生成器忽略,见 test_mindmap_arrows_summaries_ignored)。
MINDMAP_JSON = ('{"layout":"chapter-span","nodeData":{"id":"root","topic":"书","root":true,"children":['
                '{"id":"p1","topic":"分支一","children":['
                '{"id":"l1","topic":"叶一关键词","tags":["这是一句可反驳的判断句副文本","第1章"],"hyperLink":"#ch-1","expanded":false,"children":['
                '{"id":"l1-m","topic":"🧠 机制模型","_src":"第1章·mental_model"}]},'
                '{"id":"l2","topic":"叶二关键词","tags":["另一句可反驳的判断句副文本","第1章"],"hyperLink":"#ch-1"}]}]}}')
# v3 子视图 2 张(作者页 + 观点对照);作者页含 au-infobox + 恰一条 au-work-this
SUB_ENTRIES = ('<a class="cb-author" href="#sub-author">作者</a>'
               '<a class="views-entry" href="#sub-views">观点</a>')
AUTHOR_BODY = ('<button class="sub-back" data-sub-back>返回</button>'
               '<aside class="au-infobox">基础信息</aside>'
               '<ol class="au-works-list"><li class="au-work au-work-this">本书</li>'
               '<li class="au-work">另一本</li></ol>')
SUBPAGES = (f'<section class="subpage" id="sub-author" hidden>{AUTHOR_BODY}</section>'
            '<section class="subpage" id="sub-views" hidden><button class="sub-back" data-sub-back>返回</button></section>')


def _ci_cards():
    return (
        '<article class="ci ci-primary" data-source="第3章">'
        '<p class="ci-idea">核心主张一</p><p class="ci-analogy">类比一句</p>'
        '<div class="ci-detail"><p class="ci-explain">解释</p><p class="ci-evidence">证据</p>'
        '<span class="ci-evlevel" data-level="confirmed">原文确认</span></div></article>'
        '<article class="ci" data-source="第4章"><p class="ci-idea">主张二</p>'
        '<p class="ci-analogy">类比</p><div class="ci-detail"><p class="ci-explain">e</p>'
        '<p class="ci-evidence">v</p><span class="ci-evlevel" data-level="review">需复核</span></div></article>')


def page(*, tabs_html=None, cover=COVER, chapters=GOOD_CH, subpages=SUBPAGES, sub_entries=SUB_ENTRIES,
         cover_intro="这本书讲什么,信息型两句。", hero_h1="市场是钟摆,总在贪婪与恐惧间来回",
         ci_cards=None, quote_wall=True, toc_expand=True, extra_blocks="", drop_class=None,
         forbidden_class="", css="", lang='lang="zh"', ds_fill=10, no_srcnote=False, size_pad=0,
         banner_author_link=True, mindmap_json=None):
    if tabs_html is None:
        tabs_html = "".join(
            f'<button class="tab" data-panel="{p}">{l}<span class="tab-sub">副</span></button>' for p, l in TABS)
    if ci_cards is None:
        ci_cards = _ci_cards()
    # 各必需签名 class 块(可用 drop_class 删某块以测缺失)
    blocks = {
        "cb-banner": f'<header class="cb-banner">{cover}<p class="cb-intro">{cover_intro}</p>'
                     + ('<a class="cb-author" href="#sub-author">作者</a>' if banner_author_link
                        else '<span class="cb-author">作者</span>') + '</header>',
        "hero": f'<section class="hero"><h1>{hero_h1}</h1></section>',
        "bd-napkin": f'<div class="note bd-napkin" data-source="全书"><p class="formula">A = B</p>'
                     f'<p>{NAPKIN_ONE_LINER}</p></div>',
        "bd-mindmap-wrap": ('<div class="bd-mindmap-wrap">'
                            '<script type="application/json" id="bd-mindmap-data">'
                            + (mindmap_json if mindmap_json is not None else MINDMAP_JSON) +
                            '</script><div id="bd-mindmap"></div></div>'),
        "bd-coreideas": f'<div class="bd-coreideas"><div class="ci-list">{ci_cards}</div></div>',
        "soul-block": '<div class="soul-block" data-source="第2章">soul</div>',
        "concept-chips": '<div class="concept-chips"></div>',
        "chapter-toc": ('<div class="chapter-toc"><span class="toc-progress">已读 0/1</span>'
                        + ('<button class="toc-expand" data-toc-toggle>全部展开</button>' if toc_expand else '')
                        + '<button class="toc-row" data-ch="1">章一</button></div>'),
        "bd-chapter": f'<div class="bd-chapters">{chapters}</div>',
        "quote-wall": ('<div class="quote-wall"><figure class="qw-card" data-source="第5章">金句</figure></div>'
                       if quote_wall else ''),
        "verdict-bar": '<div class="verdict-bar" data-source="全书">裁决</div>',
        "arg-restate": '<div class="arg-restate" data-source="全书">立论</div>',
        "tensions": '<div class="tensions"><article class="tn-row" data-source="第1章">A⟷B</article></div>',
        "crit-quad": '<div class="crit-quad"><div class="cq-object" data-source="第2章">最强反对</div></div>',
        "reviews": '<div class="reviews"></div>',
        "rules": '<div class="rules"><article class="rule-card" data-source="第2章">规则</article></div>',
        "models": '<div class="models"><article class="model-drawer" data-source="第4章">模型</article></div>',
        "questions": '<div class="questions"><article class="question" data-source="第4章">自检</article></div>',
    }
    if drop_class:
        blocks.pop(drop_class, None)
    glance = (blocks.get("bd-napkin", "") + blocks.get("bd-mindmap-wrap", "")
              + blocks.get("bd-coreideas", "") + blocks.get("soul-block", "")
              + '<a class="next-cta" data-panel="panel-full">下一步 →</a>')
    full = (blocks.get("concept-chips", "") + blocks.get("chapter-toc", "") + blocks.get("bd-chapter", "")
            + blocks.get("quote-wall", "") + '<a class="next-cta" data-panel="panel-judge">下一步 →</a>')
    judge = (blocks.get("verdict-bar", "") + blocks.get("arg-restate", "") + blocks.get("tensions", "")
             + blocks.get("crit-quad", "") + blocks.get("reviews", "")
             + '<a class="next-cta" data-panel="panel-action">下一步 →</a>')
    action = (blocks.get("rules", "") + blocks.get("models", "") + blocks.get("questions", "")
              + '<div class="chain" data-chain><div class="chain-step">'
              '<div class="chain-detail" data-source="第1章">扩写</div></div></div>'
              '<a class="next-cta" data-panel="panel-extend">下一步 →</a>')
    footer = blocks.get("footer", '<footer class="footer">脚注</footer>')
    header = (blocks.get("cb-banner", "") + blocks.get("hero", ""))
    extra = "".join('<span data-source="第1章"></span>' for _ in range(ds_fill))
    srcnote = "" if no_srcnote else '<p class="src-note">出处常显</p>'
    pad = "x" * size_pad
    return (f'<html {lang}><head><style>{TOKENS}{css}</style></head><body>'
            f'{header}'
            f'<nav class="tabs" id="bd-tabs">{tabs_html}</nav>'
            f'<section class="panel on" id="panel-glance">{glance}{srcnote}{forbidden_class}{extra}</section>'
            f'<section class="panel" id="panel-full">{full}</section>'
            f'<section class="panel" id="panel-judge">{judge}{sub_entries}</section>'
            f'<section class="panel" id="panel-action">{action}</section>'
            f'<section class="panel" id="panel-extend"><p class="extend-pointer">末行</p></section>'
            f'{subpages}{footer}{pad}<script>var x="#333";</script></body></html>')


# ================================================================ HTML lint (静态)
def test_clean_page_passes():
    assert lint_html(page()) == []


def test_size_budget_3mb_flagged():
    v = lint_html(page(size_pad=3 * 1024 * 1024 + 10))
    assert any("3MB" in x for x in v)


def test_size_under_3mb_ok():
    assert lint_html(page(size_pad=1_400_000)) == []


def test_hex_outside_tokens_flagged():
    v = lint_html(page(css=".note{color:#ff0000}"))
    assert any("硬编码" in x for x in v)


def test_color_mix_not_flagged_as_hex():
    # 四区背景 color-mix(in srgb,var(--gold) 10%,transparent) 全用 token,不是字面 hex 违规 -> 放行
    v = lint_html(page(css=".cq{background:color-mix(in srgb,var(--gold) 10%,transparent)}"))
    assert v == []


def test_js_hash_string_not_flagged():
    # <script> 里的 "#333" 字符串是 JS 兜底、非 CSS,不应被 hex 扫描误伤(默认 fixture 已含)
    assert lint_html(page()) == []


def test_vendor_style_hex_exempted():
    # 专用 <style data-vendor="mind-elixir"> 内联 mind-elixir.css 的字面 hex -> 整块剥离豁免,不报违规
    v = lint_html(page(css='</style><style data-vendor="mind-elixir">.map-container{color:#276f86;background:#4f90f2;border:1px solid #757575}'))
    assert v == []


def test_non_vendor_style_hex_still_flagged():
    # 普通 <style>(非 data-vendor)里的 hex 仍照常拦截,豁免不误放
    v = lint_html(page(css='</style><style>.map-container{color:#276f86}'))
    assert any("硬编码" in x for x in v)


def test_missing_required_class_flagged():
    v = lint_html(page(drop_class="verdict-bar"))
    assert any("verdict-bar" in x for x in v)


def test_missing_soul_block_flagged():
    v = lint_html(page(drop_class="soul-block"))
    assert any("soul-block" in x for x in v)


def test_missing_quote_wall_flagged():
    v = lint_html(page(quote_wall=False))
    assert any("quote-wall" in x for x in v)


def test_missing_crit_quad_flagged():
    v = lint_html(page(drop_class="crit-quad"))
    assert any("crit-quad" in x for x in v)


def test_missing_chain_data_flagged():
    # 删掉 data-chain 的行动路线图(手工构造无 chain 的 action 段)
    html = page().replace('<div class="chain" data-chain>', '<div class="nochain">')
    v = lint_html(html)
    assert any("chain" in x and "data-chain" in x for x in v)


# ---------------------------------------------------------------- T7 金句唯一归宿
def test_quote_inline_forbidden():
    v = lint_html(page(forbidden_class='<blockquote class="quote-inline">行内金句</blockquote>'))
    assert any("quote-inline" in x for x in v)


def test_featured_quotes_forbidden():
    v = lint_html(page(forbidden_class='<div class="featured-quotes">首屏金句条</div>'))
    assert any("featured-quotes" in x for x in v)


# ---------------------------------------------------------------- 脑图自绘 SVG JSON 数据契约(§5)
# SVG 版契约:只审 nodeData 树(一级分支挂锚 / 锚点真实 / 二级 tags[0] 判断句 / 全图字数);
# arrows/summaries 不再是契约(生成器只画父子引线、不画关联),残留一律忽略。
# SVG 结构(真出 <svg>/节点数/无关联箭头/viewer 在/点二级跳章)由 smoke() 渲染期断,不进静态 lint。
def test_mindmap_clean_passes():
    assert lint_mindmap(GOOD_CH_WRAP()) == []


def test_mindmap_missing_data_flagged():
    v = lint_mindmap('<div class="bd-mindmap-wrap"><div id="bd-mindmap"></div></div>')
    assert any("bd-mindmap-data" in x for x in v)


def test_mindmap_bad_json_flagged():
    v = lint_mindmap('<script id="bd-mindmap-data">{not json,,}</script>')
    assert any("JSON 解析失败" in x for x in v)


def test_mindmap_branch_without_hyperlink_leaf_flagged():
    mj = ('{"nodeData":{"id":"root","topic":"书","root":true,"children":['
          '{"id":"p1","topic":"分支","children":[{"id":"l1","topic":"叶无锚"}]}]}}')
    v = lint_html(page(mindmap_json=mj))
    assert any("无 hyperLink 叶子" in x for x in v)


def test_mindmap_dead_anchor_flagged():
    # hyperLink 指向 #ch-9,但页面只有 #ch-1 -> 死链
    mj = ('{"nodeData":{"id":"root","topic":"书","root":true,"children":['
          '{"id":"p1","topic":"分支","children":['
          '{"id":"l1","topic":"叶","tags":["这是一句足够长的判断句副文本","第9章"],"hyperLink":"#ch-9"}]}]}}')
    v = lint_html(page(mindmap_json=mj))
    assert any("死链" in x and "ch-9" in x for x in v)


def test_mindmap_l2_missing_tag_flagged():
    # 二级缺 tags[0] 判断句 -> 拦(Q3-1)
    mj = ('{"nodeData":{"id":"root","topic":"书","root":true,"children":['
          '{"id":"p1","topic":"分支","children":['
          '{"id":"l1","topic":"叶一无tag","hyperLink":"#ch-1"}]}]}}')
    v = lint_html(page(mindmap_json=mj))
    assert any("tags[0]" in x for x in v)


def test_mindmap_l2_short_tag_flagged():
    # 二级 tags[0] 有效长 <8 字 -> 拦(Q3-1)
    mj = ('{"nodeData":{"id":"root","topic":"书","root":true,"children":['
          '{"id":"p1","topic":"分支","children":['
          '{"id":"l1","topic":"叶一","tags":["太短","第1章"],"hyperLink":"#ch-1"}]}]}}')
    v = lint_html(page(mindmap_json=mj))
    assert any("有效长" in x and "<8" in x for x in v)


def test_mindmap_total_topic_over_900_flagged():
    # 全图 topic 总字数 >900 -> 拦(Q3-5)
    kids = ",".join(
        '{"id":"l%d","topic":"%s","tags":["这是一句足够长的判断句副文本","第1章"],"hyperLink":"#ch-1"}'
        % (i, "字" * 40) for i in range(30))
    mj = ('{"nodeData":{"id":"root","topic":"书","root":true,"children":['
          '{"id":"p1","topic":"分支","children":[' + kids + ']}]}}')
    v = lint_html(page(mindmap_json=mj))
    assert any("总字数" in x and ">900" in x for x in v)


def test_mindmap_enriched_tree_passes():
    # 双层充实树(自绘 SVG 版):二级带 tags[0] 判断句 + tags[1] 章码 + expanded:false;真四级(三级下挂 📖 四级)-> 全通过(不误杀)
    mj = ('{"layout":"chapter-span","nodeData":{"id":"root","topic":"书","root":true,"children":['
          '{"id":"p1","topic":"① 一级","children":['
          '{"id":"v1","topic":"二级关键词甲","tags":["这是甲的一句可反驳判断句副文本","第1章"],"hyperLink":"#ch-1","expanded":false,"children":['
          '{"id":"v1-m","topic":"🧠 机制模型","_src":"第1章·mental_model","children":['
          '{"id":"v1-c","topic":"📖 招牌案例","_src":"第1章·narrative"}]},'
          '{"id":"v1-x","topic":"📚《某书》·印证","_src":"enrich·similar_page"}]},'
          '{"id":"v2","topic":"二级关键词乙","tags":["这是乙的一句可反驳判断句副文本","第1章"],"hyperLink":"#ch-1","expanded":false,"children":['
          '{"id":"v2-r","topic":"⚖️ 遇到X时→做Y","_src":"第1章·decision_rule"}]}]}]}}')
    assert lint_mindmap(f'<div>{GOOD_CH}<script id="bd-mindmap-data">{mj}</script></div>') == []


def test_mindmap_arrows_summaries_ignored():
    # SVG 版不画关联:即便数据里残留 arrows/summaries(含空 label / 悬挂引用 / 全幅收纳),生成器一律忽略 -> 不产生任何违规
    mj = ('{"layout":"chapter-span","nodeData":{"id":"root","topic":"书","root":true,"children":['
          '{"id":"p1","topic":"分支","children":['
          '{"id":"l1","topic":"叶一","tags":["这是一句足够长的判断句副文本","第1章"],"hyperLink":"#ch-1"},'
          '{"id":"l2","topic":"叶二","tags":["这是另一句足够长的判断句副文本","第1章"],"hyperLink":"#ch-1"}]}]},'
          '"arrows":[{"id":"a1","from":"l1","to":"ghost","label":""},'
          '{"id":"a2","from":"l2","to":"p1","label":"x"},{"id":"a3","from":"l1","to":"l2","label":"y"}],'
          '"summaries":[{"id":"s1","parent":"nope","start":0,"end":1,"label":""}]}')
    assert lint_html(page(mindmap_json=mj)) == []


def GOOD_CH_WRAP():
    return (f'<div id="page">{GOOD_CH}'
            '<script type="application/json" id="bd-mindmap-data">' + MINDMAP_JSON + '</script></div>')


# ---------------------------------------------------------------- T8 核心观点卡展开态三件
def test_ci_expand_triplet_required():
    bare = ('<article class="ci" data-source="第3章"><p class="ci-idea">主张</p>'
            '<p class="ci-analogy">类比</p></article>')
    v = lint_html(page(ci_cards=bare))
    assert any("ci-explain" in x for x in v)
    assert any("ci-evidence" in x for x in v)
    assert any("ci-evlevel" in x for x in v)


# ---------------------------------------------------------------- T6 目录态逃生门
def test_toc_expand_escape_hatch_required():
    v = lint_html(page(toc_expand=False))
    assert any("toc-expand" in x for x in v)


def test_bd_chapter_default_open_flagged():
    # 目录态应默认收起;初始带 open 类 -> 打回(T6)
    ch = f'<section class="bd-chapter open" id="ch-1" data-source="第1章"><h3>{GOOD_TITLE}</h3><p>x</p></section>'
    v = lint_html(page(chapters=ch))
    assert any("open" in x and "T6" in x for x in v)


# ---------------------------------------------------------------- 五 tab A 套文案 + 黑话拦截
def test_five_tabs_labels_and_ids():
    tabs = "".join(f'<button class="tab" data-panel="{p}">{l}</button>'
                   for p, l in TABS if p != "panel-extend")
    v = lint_html(page(tabs_html=tabs))
    assert any("panel-extend" in x for x in v)


def test_v2_tab_blackword_flagged():
    tabs = ('<button class="tab" data-panel="panel-glance">一眼全书</button>'
            + "".join(f'<button class="tab" data-panel="{p}">{l}</button>'
                      for p, l in TABS if p != "panel-glance"))
    v = lint_html(page(tabs_html=tabs))
    assert any("一眼全书" in x for x in v)


# ---------------------------------------------------------------- 章标题黑名单(G8)
def test_chapter_title_pure_number_flagged():
    ch = '<section class="bd-chapter" id="ch-1" data-source="第1章"><h3>第3章</h3><p>x</p></section>'
    v = lint_html(page(chapters=ch))
    assert any("G8" in x for x in v)


def test_chapter_title_too_short_flagged():
    ch = '<section class="bd-chapter" id="ch-1" data-source="第1章"><h3>太短标题</h3><p>x</p></section>'
    v = lint_html(page(chapters=ch))
    assert any("G8" in x for x in v)


def test_chapter_title_container_word_flagged():
    ch = '<section class="bd-chapter" id="ch-1" data-source="第1章"><h3>金句墙</h3><p>x</p></section>'
    v = lint_html(page(chapters=ch))
    assert any("G8" in x for x in v)


# ---------------------------------------------------------------- 封面 / 出处 / 外链
def test_missing_book_cover_img_flagged():
    v = lint_html(page(cover=""))
    assert any("cb-cover" in x for x in v)


def test_cover_must_be_data_uri():
    v = lint_html(page(cover='<div class="cb-cover">占位</div>'))
    assert any("cb-cover" in x for x in v)


def test_srctoggle_button_forbidden():
    html = page().replace('<footer', '<button id="srcToggle">显示出处</button><footer')
    v = lint_html(html)
    assert any("srcToggle" in x for x in v)


def test_srcnote_required():
    ch = f'<section class="bd-chapter" id="ch-1" data-source="第1章"><h3>{GOOD_TITLE}</h3><p>正文无出处</p></section>'
    v = lint_html(page(no_srcnote=True, chapters=ch))
    assert any("src-note" in x for x in v)


def test_external_script_flagged():
    v = lint_html('<html lang="zh"><body><script src="https://cdn.x.com/a.js"></script></body></html>')
    assert any("外链" in x for x in v)


def test_lint_flags_iframe():
    v = lint_html('<html lang="zh"><body><iframe src="https://x"></iframe></body></html>')
    assert any("内嵌播放器" in x for x in v)


def test_lint_flags_video():
    v = lint_html('<html lang="zh"><body><video controls></video></body></html>')
    assert any("内嵌播放器" in x for x in v)


def test_low_source_coverage_flagged():
    v = lint_html(page(ds_fill=0, chapters='<section class="bd-chapter" id="ch-1">'
                                           f'<h3>{GOOD_TITLE}</h3><p>x</p></section>'))
    assert any("data-source" in x for x in v)


def test_missing_lang_flagged():
    v = lint_html(page(lang=""))
    assert any("lang" in x for x in v)


# ---------------------------------------------------------------- 子视图一致性 / 作者页
def test_subpage_full_degrade_ok():
    # 两块 enrich 全 null -> 删全部子视图 + 全部入口(含 banner 作者链) -> 一致,不报错(§1.5)
    assert lint_html(page(subpages="", sub_entries="", banner_author_link=False)) == []


def test_subpage_partial_degrade_ok():
    # 仅 views_page 为 null -> 删 #sub-views + 其入口,保留作者页 -> 一致
    subs = f'<section class="subpage" id="sub-author" hidden>{AUTHOR_BODY}</section>'
    ents = '<a class="cb-author" href="#sub-author">作者</a>'
    assert lint_html(page(subpages=subs, sub_entries=ents)) == []


def test_dead_entry_to_missing_subpage_flagged():
    # 入口指向已删的 #sub-views(子视图不存在)-> 死链
    subs = f'<section class="subpage" id="sub-author" hidden>{AUTHOR_BODY}</section>'
    v = lint_html(page(subpages=subs))
    assert any("sub-views" in x and "不存在的子视图" in x for x in v)


def test_subpage_present_without_entry_flagged():
    v = lint_html(page(sub_entries=""))
    assert any("无入口" in x for x in v)


def test_subpage_present_without_backbtn_flagged():
    subs = ('<section class="subpage" id="sub-author" hidden><aside class="au-infobox">i</aside>'
            '<ol><li class="au-work au-work-this">本书</li></ol></section>'
            '<section class="subpage" id="sub-views" hidden><button class="sub-back" data-sub-back>返回</button></section>')
    v = lint_html(page(subpages=subs))
    assert any("返回按钮" in x and "sub-author" in x for x in v)


def test_author_missing_infobox_flagged():
    subs = ('<section class="subpage" id="sub-author" hidden><button class="sub-back" data-sub-back>返回</button>'
            '<ol><li class="au-work au-work-this">本书</li></ol></section>'
            '<section class="subpage" id="sub-views" hidden><button class="sub-back" data-sub-back>返回</button></section>')
    v = lint_html(page(subpages=subs))
    assert any("au-infobox" in x for x in v)


def test_author_this_book_must_be_exactly_one():
    # 两条 au-work-this -> works 不是恰一条 is_this_book
    subs = (f'<section class="subpage" id="sub-author" hidden><button class="sub-back" data-sub-back>返回</button>'
            '<aside class="au-infobox">i</aside>'
            '<ol><li class="au-work au-work-this">本书</li><li class="au-work au-work-this">又一本</li></ol></section>'
            '<section class="subpage" id="sub-views" hidden><button class="sub-back" data-sub-back>返回</button></section>')
    v = lint_html(page(subpages=subs))
    assert any("au-work-this" in x for x in v)


# ---------------------------------------------------------------- enrich 降级一致性
def test_enrich_author_null_but_subpage_present_flagged():
    enrich = {"author_page": None, "views_page": {"topics": []}, "reviews": None}
    v = lint_enrich_consistency(page(), enrich)
    assert any("author_page" in x and "sub-author" in x for x in v)


def test_enrich_views_present_but_subpage_absent_flagged():
    # views_page 非 null 但页面无 #sub-views
    subs = f'<section class="subpage" id="sub-author" hidden>{AUTHOR_BODY}</section>'
    ents = '<a class="cb-author" href="#sub-author">作者</a>'
    html = page(subpages=subs, sub_entries=ents)
    enrich = {"author_page": {"name": "x"}, "views_page": {"topics": []}, "reviews": {}}
    v = lint_enrich_consistency(html, enrich)
    assert any("views_page" in x and "sub-views" in x for x in v)


def test_enrich_reviews_null_but_block_present_flagged():
    enrich = {"author_page": {"name": "x"}, "views_page": {"topics": []}, "reviews": None}
    v = lint_enrich_consistency(page(), enrich)
    assert any("reviews" in x for x in v)


def test_enrich_consistency_clean():
    enrich = {"author_page": {"name": "x"}, "views_page": {"topics": []}, "reviews": {"items": []}}
    assert lint_enrich_consistency(page(), enrich) == []


# ---------------------------------------------------------------- 渲染侧查重(§2.2 / G16)
def test_html_cover_intro_reuses_napkin_flagged():
    v = lint_html(page(cover_intro="导语:" + NAPKIN_ONE_LINER + "所以很重要。"),
                  distill=distill(napkin={"formula": "A=B", "one_liner": NAPKIN_ONE_LINER}))
    assert any("cb-intro" in x and "查重" in x for x in v)


def test_html_hero_reuses_napkin_flagged():
    v = lint_html(page(hero_h1=NAPKIN_ONE_LINER),
                  distill=distill(napkin={"formula": "A=B", "one_liner": NAPKIN_ONE_LINER}))
    assert any("hero" in x and "查重" in x for x in v)


# ================================================================ distill lint (契约门禁)
def dch(no=1, title="先估价值再看价格才不会追涨杀跌", narr=900, excerpts=None):
    return {"no": no, "title": title, "narrative": "字" * narr,
            "excerpts": excerpts if excerpts is not None else [{"text": "原文短段", "anchor": "第1章·约第14页"}],
            "anchor": "第1章"}


def distill(**over):
    d = {
        "chapters": [dch()],
        "napkin": {"formula": "价值 − 价格 = 安全边际", "formula_read": FORMULA_READ, "one_liner": NAPKIN_ONE_LINER},
        "core_question": "为什么聪明人也常常在市场里亏钱?",
        "arguments": {"chain": "归纳型:先……再……",
                      "chain_steps": ["市场常错价", "价格不等于价值", "算清安全边际", "反人性下手"],
                      "hidden_assumptions": [], "counter_examples": []},
        "cover_intro": "作者从三十年备忘录里归纳出投资心法。全书拎出价值、风险、周期几根支柱。最后落到少犯错胜过多正确。",
        "credibility_verdict": "最硬的是风险即永久损失一条,有大量周期实例支撑。要打折的是逆向操作对普通人的可行性。",
        "core_ideas": [{"idea": "a", "anchor": "第3章", "primary": True, "layman_analogy": "类比一句", "evidence_level": "原文确认", "chain_step": 1}],
        "decision_rules": [{"when": "x", "do": "y", "because": "z", "anchor": "第2章", "chain_step": 2}],
        "quotes": [{"text": "q", "anchor": "第5章", "featured": True}],
        "mental_models": [{"model": "m", "evidence": ["证据在 第4章"], "boundary": "b", "chain_step": None}],
        "self_check": [{"q": f"你第{i}问会怎么做?", "followup": "再想一层?", "anchor": "第4章"} for i in range(4)],
        "soul_module": {"title": "钟摆极少停在中点", "subtitle": "两端来回冲", "type": "compare",
                        "intro": "点出反直觉", "states": [{"label": "A"}, {"label": "B"}]},
        "action_chain": [{"label": f"第{i}环行动", "explain": "3-6 句解释",
                          "detail": "这一环具体怎么下手:先交代读者最常卡在哪一步,再给出书里对应的那个案例或数据来印证做法,最后说清正确姿势到底是什么样,整段写满六十字以上,绝不是一句话草草带过。"}
                         for i in range(4)],
    }
    d.update(over)
    return d


def test_distill_clean_passes():
    assert lint_distill(distill()) == []


def test_distill_via_lint_html_integrates():
    v = lint_html(page(), distill=distill(chapters=[dch(narr=100)]))
    assert any("G9" in x for x in v)


def test_narrative_floor_book_800():
    v = lint_distill(distill(chapters=[dch(narr=799)]))
    assert any("G9" in x for x in v)
    assert lint_distill(distill(chapters=[dch(narr=800)])) == []


def test_narrative_floor_video_400():
    vbad = lint_distill(distill(source_type="video_series", chapters=[dch(narr=100, excerpts=[])]))
    assert any("G9" in x for x in vbad)
    assert lint_distill(distill(source_type="video_series", chapters=[dch(narr=450, excerpts=[])])) == []


def test_excerpt_over_150_copyright_flagged():
    v = lint_distill(distill(chapters=[dch(excerpts=[{"text": "字" * 151, "anchor": "第1章"}])]))
    assert any("G14" in x for x in v)


def test_book_excerpt_missing_flagged():
    v = lint_distill(distill(chapters=[dch(excerpts=[])]))
    assert any("G14" in x for x in v)


def test_video_excerpt_optional_ok():
    d = distill(source_type="video_series", chapters=[dch(narr=450, excerpts=[])])
    assert lint_distill(d) == []


def test_anchor_missing_self_check_flagged():
    v = lint_distill(distill(self_check=[{"q": "你?", "followup": "?", "anchor": ""}]))
    assert any("anchor" in x for x in v)


def test_anchor_missing_excerpt_flagged():
    v = lint_distill(distill(chapters=[dch(excerpts=[{"text": "原文", "anchor": ""}])]))
    assert any("anchor" in x for x in v)


def test_anchor_missing_core_idea_flagged():
    v = lint_distill(distill(core_ideas=[{"idea": "a", "anchor": "", "primary": True, "layman_analogy": "比"}]))
    assert any("anchor" in x for x in v)


def test_anchor_missing_mental_model_evidence_flagged():
    v = lint_distill(distill(mental_models=[{"model": "m", "evidence": ["无锚点证据"], "boundary": "b"}]))
    assert any("anchor" in x for x in v)


def test_video_anchor_accepted():
    d = distill(source_type="video_series",
                chapters=[dch(narr=450, excerpts=[], title="手动写 vs Codex 代写的分水岭")],
                core_ideas=[{"idea": "a", "anchor": "视频2·12:30", "primary": True, "layman_analogy": "比方", "evidence_level": "原文确认"}],
                decision_rules=[{"when": "x", "do": "y", "because": "z", "anchor": "视频1"}],
                quotes=[{"text": "q", "anchor": "视频3·05:10", "featured": True}],
                mental_models=[{"model": "m", "evidence": ["证据 视频4"], "boundary": "b"}],
                self_check=[{"q": "你?", "followup": "?", "anchor": "视频3"} for _ in range(4)])
    assert lint_distill(d) == []


def test_featured_over_3_flagged():
    v = lint_distill(distill(quotes=[{"text": f"q{i}", "anchor": "第1章", "featured": True} for i in range(4)]))
    assert any("G15" in x for x in v)


def test_primary_zero_flagged():
    v = lint_distill(distill(core_ideas=[{"idea": "a", "anchor": "第1章", "primary": False, "layman_analogy": "比"}]))
    assert any("G15" in x for x in v)


def test_primary_three_flagged():
    v = lint_distill(distill(core_ideas=[{"idea": f"a{i}", "anchor": "第1章", "primary": True, "layman_analogy": "比"}
                                         for i in range(3)]))
    assert any("G15" in x for x in v)


# ---------------------------------------------------------------- G10-G13
def test_g10_empty_layman_analogy_flagged():
    v = lint_distill(distill(core_ideas=[{"idea": "a", "anchor": "第1章", "primary": True, "layman_analogy": ""}]))
    assert any("G10" in x for x in v)


def test_g10_missing_layman_analogy_flagged():
    v = lint_distill(distill(core_ideas=[{"idea": "a", "anchor": "第1章", "primary": True}]))
    assert any("G10" in x for x in v)


def test_g11_missing_soul_module_flagged():
    v = lint_distill(distill(soul_module=None))
    assert any("G11" in x for x in v)


def test_g11_states_below_2_flagged():
    v = lint_distill(distill(soul_module={"title": "t", "subtitle": "s", "type": "compare",
                                          "intro": "i", "states": [{"label": "A"}]}))
    assert any("G11" in x for x in v)


def test_g11_empty_subtitle_flagged():
    v = lint_distill(distill(soul_module={"title": "t", "subtitle": "", "type": "compare",
                                          "intro": "i", "states": [{"label": "A"}, {"label": "B"}]}))
    assert any("G11" in x for x in v)


def test_g11_bad_type_flagged():
    v = lint_distill(distill(soul_module={"title": "t", "subtitle": "s", "type": "matrix",
                                          "intro": "i", "states": [{"label": "A"}, {"label": "B"}]}))
    assert any("G11" in x for x in v)


def test_g11_curve_missing_series_flagged():
    v = lint_distill(distill(soul_module={"title": "t", "subtitle": "s", "type": "curve",
                                          "intro": "i", "states": [{"label": "A"}, {"label": "B"}],
                                          "curve": {"series": []}}))
    assert any("G11" in x for x in v)


def test_g11_curve_with_series_ok():
    d = distill(soul_module={"title": "t", "subtitle": "s", "type": "curve", "intro": "i",
                             "states": [{"label": "A"}, {"label": "B"}],
                             "curve": {"series": [{"label": "L", "points": [[0, 0], [1, 1]], "token": "--red"}]}})
    assert lint_distill(d) == []


def test_g12_self_check_too_few_flagged():
    v = lint_distill(distill(self_check=[{"q": "你?", "followup": "?", "anchor": "第1章"} for _ in range(3)]))
    assert any("G12" in x for x in v)


def test_g12_self_check_too_many_flagged():
    v = lint_distill(distill(self_check=[{"q": "你?", "followup": "?", "anchor": "第1章"} for _ in range(9)]))
    assert any("G12" in x for x in v)


def test_g12_self_check_no_you_flagged():
    v = lint_distill(distill(self_check=[{"q": "会怎么做?", "followup": "?", "anchor": "第1章"} for _ in range(4)]))
    assert any("G12" in x for x in v)


def test_g13_action_chain_too_few_flagged():
    v = lint_distill(distill(action_chain=[{"label": "环", "explain": "e", "detail": "字" * 60} for _ in range(3)]))
    assert any("G13" in x for x in v)


def test_g13_action_chain_too_many_flagged():
    v = lint_distill(distill(action_chain=[{"label": "环", "explain": "e", "detail": "字" * 60} for _ in range(6)]))
    assert any("G13" in x for x in v)


def test_g13_action_chain_label_too_long_flagged():
    long_label = "这是一个明显超过十二字上限的超长环名标签"  # 有效长 20 > 12
    v = lint_distill(distill(action_chain=[{"label": long_label, "explain": "e", "detail": "字" * 60}] +
                                          [{"label": "环", "explain": "e", "detail": "字" * 60} for _ in range(3)]))
    assert any("G13" in x for x in v)


# ---------------------------------------------------------------- G16 cover_intro
def test_g16_missing_cover_intro_flagged():
    v = lint_distill(distill(cover_intro=""))
    assert any("cover_intro" in x and "G16" in x for x in v)


def test_g16_cover_intro_one_sentence_flagged():
    v = lint_distill(distill(cover_intro="只有一句话没有第二句"))
    assert any("句数" in x and "G16" in x for x in v)


def test_g16_cover_intro_four_sentences_flagged():
    v = lint_distill(distill(cover_intro="句一。句二。句三。句四。"))
    assert any("句数" in x and "G16" in x for x in v)


def test_g16_cover_intro_three_sentences_ok():
    assert lint_distill(distill(cover_intro="第一句素材来源。第二句框架支柱。第三句反直觉结论。")) == []


def test_g16_cover_intro_reuses_napkin_flagged():
    v = lint_distill(distill(cover_intro="开头一句。" + NAPKIN_ONE_LINER + "。"))
    assert any("查重" in x and "G16" in x for x in v)


# ---------------------------------------------------------------- G17 action_chain[].detail
def test_g17_detail_too_short_flagged():
    acs = [{"label": "环", "explain": "e", "detail": "太短了不够六十字"}] + \
          [{"label": "环", "explain": "e", "detail": "字" * 60} for _ in range(3)]
    v = lint_distill(distill(action_chain=acs))
    assert any("G17" in x for x in v)


def test_g17_detail_missing_flagged():
    acs = [{"label": "环", "explain": "e"}] + \
          [{"label": "环", "explain": "e", "detail": "字" * 60} for _ in range(3)]
    v = lint_distill(distill(action_chain=acs))
    assert any("G17" in x for x in v)


def test_g17_detail_60_ok():
    acs = [{"label": "环", "explain": "e", "detail": "字" * 60} for _ in range(4)]
    assert lint_distill(distill(action_chain=acs)) == []


# ---------------------------------------------------------------- G18 credibility_verdict
def test_g18_missing_verdict_book_flagged():
    v = lint_distill(distill(credibility_verdict=""))
    assert any("credibility_verdict" in x and "G18" in x for x in v)


def test_g18_verdict_optional_for_video():
    d = distill(source_type="video_series", credibility_verdict="",
                chapters=[dch(narr=450, excerpts=[])])
    assert lint_distill(d) == []


# ---------------------------------------------------------------- chain_step 合法性
def test_chain_step_out_of_range_flagged():
    v = lint_distill(distill(decision_rules=[{"when": "x", "do": "y", "because": "z",
                                              "anchor": "第2章", "chain_step": 7}]))
    assert any("chain_step" in x for x in v)


def test_chain_step_zero_flagged():
    v = lint_distill(distill(mental_models=[{"model": "m", "evidence": ["证据 第4章"],
                                             "boundary": "b", "chain_step": 0}]))
    assert any("chain_step" in x for x in v)


def test_chain_step_bool_flagged():
    # True 在 Python 是 int 子类,须显式排除(否则 chain_step=True 会被当作 1 蒙混过关)
    v = lint_distill(distill(decision_rules=[{"when": "x", "do": "y", "because": "z",
                                              "anchor": "第2章", "chain_step": True}]))
    assert any("chain_step" in x for x in v)


def test_chain_step_exceeds_ring_count_flagged():
    # action_chain 只有 4 环,chain_step=5 属越界
    v = lint_distill(distill(decision_rules=[{"when": "x", "do": "y", "because": "z",
                                              "anchor": "第2章", "chain_step": 5}]))
    assert any("越界" in x for x in v)


def test_chain_step_null_ok():
    d = distill(decision_rules=[{"when": "x", "do": "y", "because": "z", "anchor": "第2章", "chain_step": None}],
                mental_models=[{"model": "m", "evidence": ["证据 第4章"], "boundary": "b"}])
    assert lint_distill(d) == []


# ---------------------------------------------------------------- v4 G19 core_question
def test_g19_missing_core_question_flagged():
    v = lint_distill(distill(core_question=""))
    assert any("core_question" in x and "G19" in x for x in v)


def test_g19_core_question_too_long_flagged():
    v = lint_distill(distill(core_question="为什么" + "很" * 40 + "长的问题句子超过了四十个字的上限?"))
    assert any("core_question" in x and "40" in x for x in v)


def test_g19_core_question_not_question_flagged():
    v = lint_distill(distill(core_question="这其实是一句陈述句没有问号"))
    assert any("core_question" in x and "疑问句" in x for x in v)


def test_g19_core_question_reuses_one_liner_flagged():
    v = lint_distill(distill(core_question="真的吗," + NAPKIN_ONE_LINER + "?"))
    assert any("core_question" in x and "one_liner" in x for x in v)


def test_g19_core_question_reuses_cover_intro_flagged():
    d = distill(cover_intro="作者从三十年备忘录里归纳出投资心法。全书拎出价值、风险几根支柱。落到少犯错。",
                core_question="作者从三十年备忘录里归纳出的是什么?")
    v = lint_distill(d)
    assert any("core_question" in x and "cover_intro" in x for x in v)


def test_g19_core_question_clean_ok():
    assert lint_distill(distill(core_question="为什么大多数人越努力投资反而亏得越多?")) == []


def test_g19_html_eyebrow_reuses_napkin_flagged():
    html = page().replace('<section class="hero"><h1>',
                           f'<section class="hero"><p class="eyebrow">追问:{NAPKIN_ONE_LINER}?</p><h1>')
    v = lint_html(html, distill=distill(napkin={"formula": "A=B", "one_liner": NAPKIN_ONE_LINER}))
    assert any("eyebrow" in x and "查重" in x for x in v)


# ---------------------------------------------------------------- v4 pillar
def test_pillar_out_of_range_flagged():
    v = lint_distill(distill(core_ideas=[{"idea": "a", "anchor": "第1章", "primary": True,
                                          "layman_analogy": "比", "pillar": 6}]))
    assert any("pillar" in x for x in v)


def test_pillar_zero_flagged():
    v = lint_distill(distill(core_ideas=[{"idea": "a", "anchor": "第1章", "primary": True,
                                          "layman_analogy": "比", "pillar": 0}]))
    assert any("pillar" in x for x in v)


def test_pillar_bool_flagged():
    v = lint_distill(distill(core_ideas=[{"idea": "a", "anchor": "第1章", "primary": True,
                                          "layman_analogy": "比", "pillar": True}]))
    assert any("pillar" in x for x in v)


def test_pillar_null_and_valid_ok():
    assert lint_distill(distill(core_ideas=[
        {"idea": "a", "anchor": "第1章", "primary": True, "layman_analogy": "比", "evidence_level": "原文确认", "pillar": 2},
        {"idea": "b", "anchor": "第2章", "primary": False, "layman_analogy": "比", "evidence_level": "原文确认", "pillar": None}])) == []


# ---------------------------------------------------------------- v6.1 stakes / certainty (G22) + G7 evidence_level 机检
def _hi(**over):
    """stakes=high fixture:decision_rules + core_ideas 每条带 certainty(否则触发 G22)。"""
    dr = [{"when": "x", "do": "y", "because": "z", "anchor": "第2章", "certainty": "book_explicit", "chain_step": 2}]
    ci = [{"idea": "a", "anchor": "第3章", "primary": True, "layman_analogy": "比", "evidence_level": "原文确认", "certainty": "book_explicit"}]
    base = dict(stakes="high", decision_rules=dr, core_ideas=ci)
    base.update(over)
    return distill(**base)


def test_g22_high_with_certainty_ok():
    assert lint_distill(_hi()) == []


def test_g22_high_missing_certainty_flagged():
    d = _hi(); d["decision_rules"][0].pop("certainty")
    assert any("G22" in x and "decision_rule" in x for x in lint_distill(d))


def test_g22_high_bad_certainty_value_flagged():
    d = _hi(); d["core_ideas"][0]["certainty"] = "bogus"
    assert any("G22" in x for x in lint_distill(d))


def test_g22_normal_certainty_optional():
    # stakes=normal(默认):缺 certainty 不触发 G22(可选产)
    assert not any("G22" in x for x in lint_distill(distill()))


def test_g7_missing_evidence_level_flagged():
    v = lint_distill(distill(core_ideas=[{"idea": "a", "anchor": "第1章", "primary": True, "layman_analogy": "比"}]))
    assert any("G7" in x for x in v)


# ---------------------------------------------------------------- v4 G20 chain_steps
def test_g20_missing_chain_steps_flagged():
    v = lint_distill(distill(arguments={"chain": "x", "hidden_assumptions": [], "counter_examples": []}))
    assert any("chain_steps" in x and "G20" in x for x in v)


def test_g20_too_few_steps_flagged():
    v = lint_distill(distill(arguments={"chain": "x", "chain_steps": ["一", "二", "三"],
                                        "hidden_assumptions": [], "counter_examples": []}))
    assert any("chain_steps" in x and "G20" in x for x in v)


def test_g20_too_many_steps_flagged():
    v = lint_distill(distill(arguments={"chain": "x", "chain_steps": [f"步{i}" for i in range(9)],
                                        "hidden_assumptions": [], "counter_examples": []}))
    assert any("chain_steps" in x and "G20" in x for x in v)


def test_g20_step_too_long_flagged():
    v = lint_distill(distill(arguments={"chain": "x",
                                        "chain_steps": ["这一步的有效长度故意超过十四个字的上限用来触发门禁", "二", "三", "四"],
                                        "hidden_assumptions": [], "counter_examples": []}))
    assert any("chain_steps" in x and "G20" in x for x in v)


def test_g20_chain_steps_ok():
    assert lint_distill(distill(arguments={"chain": "x", "chain_steps": ["市场常错价", "价格不等于价值", "算清安全边际", "反人性下手"],
                                           "hidden_assumptions": [], "counter_examples": []})) == []


# ---------------------------------------------------------------- v4 G21 hook
def test_g21_hook_too_long_flagged():
    v = lint_distill(distill(chapters=[dch()] and [{**dch(), "hook": "钩" * 21}]))
    assert any("hook" in x and "G21" in x for x in v)


def test_g21_hook_within_20_ok():
    assert lint_distill(distill(chapters=[{**dch(), "hook": "被剪掉的牛仔裤,和总谈崩的谈判"}])) == []


def test_g21_hook_missing_ok():
    # hook 缺失不拦(存在性属自查)
    assert lint_distill(distill(chapters=[dch()])) == []


# ---------------------------------------------------------------- v4 B-2 餐巾纸 formula_read(G4 扩展 a)
def test_formula_read_missing_flagged():
    v = lint_distill(distill(napkin={"formula": "A = B × C", "one_liner": NAPKIN_ONE_LINER}))
    assert any("formula_read" in x and "G4" in x for x in v)


def test_formula_read_empty_flagged():
    v = lint_distill(distill(napkin={"formula": "A = B × C", "formula_read": "", "one_liner": NAPKIN_ONE_LINER}))
    assert any("formula_read" in x and "G4" in x for x in v)


def test_formula_read_no_operator_semantic_flagged():
    # 只复述、不解释运算符,既无运算符也无「乘/加/归零/缺一/比例」语义词 -> 打回
    v = lint_distill(distill(napkin={"formula": "A = B × C", "formula_read": "这本书讲的是一个很重要的道理。",
                                     "one_liner": NAPKIN_ONE_LINER}))
    assert any("formula_read" in x and "运算符" in x for x in v)


def test_formula_read_too_long_flagged():
    long_fr = "为什么用乘不用加" + "字" * 80
    v = lint_distill(distill(napkin={"formula": "A = B × C", "formula_read": long_fr, "one_liner": NAPKIN_ONE_LINER}))
    assert any("formula_read" in x and "80" in x for x in v)


def test_formula_read_with_operator_char_ok():
    # 含运算符 × 即算点明(不必有语义词)
    v = lint_distill(distill(napkin={"formula": "A = B × C", "formula_read": "三项 × 相连,任一为零整体归零。",
                                     "one_liner": NAPKIN_ONE_LINER}))
    assert v == []


def test_formula_read_semantic_word_ok():
    v = lint_distill(distill(napkin={"formula": "A = B × C", "formula_read": "为什么用乘不用加:缺一根就全盘归零。",
                                     "one_liner": NAPKIN_ONE_LINER}))
    assert v == []


# ---------------------------------------------------------------- v4 B-2 餐巾纸 sketch(G4 扩展 b,可降级)
def _sketch(**over):
    s = {"type": "cascade", "caption": "从起因到结果的因果骨架",
         "nodes": [{"id": f"n{i}", "label": l} for i, l in enumerate(["起因甲", "起因乙", "起因丙"])]
                  + [{"id": "m1", "label": "中间产物", "mid": True}, {"id": "e", "label": "汇流点"},
                     {"id": "z", "label": "最终结果"}],
         "edges": [{"from": "n0", "to": "m1", "label": ""}, {"from": "m1", "to": "e", "label": "汇入"},
                   {"from": "e", "to": "z", "label": "长成"}]}
    s.update(over)
    return s


def _napkin_with_sketch(sk):
    return {"formula": "健全 = 甲 × 乙 × 丙", "formula_read": FORMULA_READ, "one_liner": NAPKIN_ONE_LINER, "sketch": sk}


def test_sketch_absent_ok():
    # sketch 可降级:缺失合法(默认 fixture 无 sketch)
    assert lint_distill(distill()) == []


def test_sketch_valid_ok():
    assert lint_distill(distill(napkin=_napkin_with_sketch(_sketch()))) == []


def test_sketch_bad_type_flagged():
    v = lint_distill(distill(napkin=_napkin_with_sketch(_sketch(type="matrix"))))
    assert any("sketch.type" in x for x in v)


def test_sketch_missing_caption_flagged():
    v = lint_distill(distill(napkin=_napkin_with_sketch(_sketch(caption=""))))
    assert any("sketch.caption" in x for x in v)


def test_sketch_too_few_nodes_flagged():
    sk = _sketch(nodes=[{"id": f"n{i}", "label": f"节点{i}"} for i in range(5)])
    v = lint_distill(distill(napkin=_napkin_with_sketch(sk)))
    assert any("sketch.nodes" in x and "[6,12]" in x for x in v)


def test_sketch_too_many_nodes_flagged():
    sk = _sketch(nodes=[{"id": f"n{i}", "label": f"节点{i}"} for i in range(13)])
    v = lint_distill(distill(napkin=_napkin_with_sketch(sk)))
    assert any("sketch.nodes" in x and "[6,12]" in x for x in v)


def test_sketch_node_missing_label_flagged():
    sk = _sketch()
    sk["nodes"][0] = {"id": "n0"}  # 缺 label
    v = lint_distill(distill(napkin=_napkin_with_sketch(sk)))
    assert any("sketch.node" in x for x in v)


def test_sketch_no_edges_flagged():
    v = lint_distill(distill(napkin=_napkin_with_sketch(_sketch(edges=[]))))
    assert any("sketch.edges" in x for x in v)


def test_sketch_edge_missing_endpoint_flagged():
    sk = _sketch(edges=[{"from": "n0", "label": "x"}])  # 缺 to
    v = lint_distill(distill(napkin=_napkin_with_sketch(sk)))
    assert any("sketch.edge" in x for x in v)


def test_sketch_redraws_formula_flagged():
    # node.label 集合 == 公式右侧项集合(甲/乙/丙) -> 重画公式凑数,打回
    sk = _sketch(nodes=[{"id": "a", "label": "甲"}, {"id": "b", "label": "乙"}, {"id": "c", "label": "丙"},
                        {"id": "a2", "label": "甲"}, {"id": "b2", "label": "乙"}, {"id": "c2", "label": "丙"}])
    v = lint_distill(distill(napkin=_napkin_with_sketch(sk)))
    assert any("完全相同" in x for x in v)


def test_sketch_superset_of_formula_ok():
    # 含公式三项 + 额外中间产物/终点,不是「完全相同」-> 放行
    sk = _sketch(nodes=[{"id": "a", "label": "甲"}, {"id": "b", "label": "乙"}, {"id": "c", "label": "丙"},
                        {"id": "m", "label": "中间产物", "mid": True}, {"id": "e", "label": "汇流"},
                        {"id": "z", "label": "终点"}])
    assert lint_distill(distill(napkin=_napkin_with_sketch(sk))) == []


# ---------------------------------------------------------------- Q7-12 破折号统一
def test_fullwidth_dash_in_prose_flagged():
    # 转述正文(章节 <p>)出现全角 —— -> 打回
    html = page().replace("<footer", "<p>转述正文里出现了破折号——这是不允许的</p><footer")
    v = lint_html(html)
    assert any("破折号" in x for x in v)


def test_fullwidth_dash_single_em_flagged():
    html = page().replace("<footer", "<p>某处用了单个 — 破折号</p><footer")
    v = lint_html(html)
    assert any("破折号" in x for x in v)


def test_fullwidth_dash_in_excerpt_blockquote_exempt():
    # 原文照录 excerpt(blockquote)里的破折号照录不改 -> 豁免
    html = page().replace("<footer", '<blockquote class="excerpt">原文照录——保留原样</blockquote><footer')
    assert lint_html(html) == []


def test_fullwidth_dash_in_qwcard_exempt():
    # 金句墙 qw-card(含 blockquote 原文 + figcaption 点评)整块豁免
    html = page().replace(
        "<footer",
        '<figure class="qw-card"><blockquote>金句原文——照录</blockquote>'
        '<figcaption>编辑点评——也在 qw 豁免区</figcaption></figure><footer')
    assert lint_html(html) == []


def test_clean_page_no_fullwidth_dash():
    # 默认 fixture 无全角破折号 -> 不触发
    assert not any("破折号" in x for x in lint_html(page()))


# ---------------------------------------------------------------- Q7-9 chain cs-badge 死徽标
def test_cs_badge_zero_flagged():
    html = page().replace('<div class="chain-step">',
                          '<div class="chain-step"><span class="cs-badge">0 条相关做法</span>', 1)
    v = lint_html(html)
    assert any("死徽标" in x for x in v)


def test_cs_badge_positive_ok():
    html = page().replace('<div class="chain-step">',
                          '<div class="chain-step"><span class="cs-badge">2 条相关做法</span>', 1)
    assert not any("死徽标" in x for x in lint_html(html))


# ================================================================ 真实骨架回归
def test_skeleton_static_lint_clean():
    if not SKELETON.exists():
        pytest.skip(f"骨架不存在: {SKELETON}")
    v = lint_html(SKELETON.read_text(encoding="utf-8"))
    assert v == [], f"骨架静态 lint 应全过,实际违规: {v}"


# ================================================================ 作者演变页门禁(独立路径)
A_TOKENS = ':root{--ink:#171411;--blue:#245f73;--gold:#B8892F}body[data-theme="brand-dark"]{--ink:#CBD4E0}'
AUTHOR_VIEWS = ("tl-scroll", "rb-scroll", "ap-turns", "dag-wrap")


def author_html(*, views=AUTHOR_VIEWS, lang='lang="zh"', css="", extra=""):
    vh = "".join(f'<div class="{c}"></div>' for c in views)
    return (f'<html {lang}><head><style>{A_TOKENS}{css}</style></head>'
            f'<body><main class="author-page">{vh}{extra}</main></body></html>')


def ajson(**over):
    d = {
        "author": "测试思想家", "slug": "__fixture__",
        "core_sentence": "把注意力长成有意义的一生。",
        "books": [
            {"slug": "a-book", "title": "甲", "pub_year": 2015, "role_in_evolution": "起点"},
            {"slug": "b-book", "title": "乙", "pub_year": 2019, "role_in_evolution": "转折"},
        ],
        "turns": [
            {"id": "t1", "concept": "意志力",
             "from": {"stance": "靠意志", "distill_slug": "a-book", "year": 2015},
             "to": {"stance": "靠系统", "distill_slug": "b-book", "year": 2019},
             "verdict": "confirmed",
             "external": [{"type": "self", "who": "本人", "say": "我早年高估了意志力。", "source": "https://e.com/i"}]},
            {"id": "t2", "concept": "专注", "from": {"stance": "x"}, "to": {"stance": "y"}, "verdict": None, "external": []},
        ],
        "reading_path": [{"slug": "b-book", "why": "先读《乙》"}],
        "concept_graph": {"nodes": [
            {"id": "c1", "concept": "心流", "appearances": [{"slug": "a-book", "year": 2015, "stance": "s"}]}]},
        "evolution_summary": "连续的追问 -- 从甲到乙。",
    }
    d.update(over)
    return d


def test_author_clean_passes():
    assert lint_author_html(author_html(), ajson()) == []


def test_author_detect():
    assert is_author_page(author_html())                         # .author-page 标记
    assert is_author_page('<script id="author-data">{}</script>')  # 内联数据槽
    assert is_author_page("<x>", author_json_flag=True)          # 传 --author-json
    assert not is_author_page(page())                            # 蒸馏页不误判


def test_author_missing_view_flagged():
    v = lint_author_html(author_html(views=("tl-scroll", "rb-scroll", "ap-turns")), ajson())
    assert any("dag-wrap" in x for x in v)


def test_author_external_img_flagged():
    v = lint_author_html(author_html(extra='<img src="https://x/y.png">'), ajson())
    assert any("外链" in x for x in v)


def test_author_hex_outside_token_flagged():
    v = lint_author_html(author_html(css=".ap-core{color:#ff0000}"), ajson())
    assert any("硬编码" in x for x in v)


def test_author_missing_lang_flagged():
    v = lint_author_html(author_html(lang=""), ajson())
    assert any("lang" in x for x in v)


def test_author_bad_book_slug_flagged():
    v = lint_author_html(author_html(), ajson(books=[{"slug": "../evil", "title": "x", "pub_year": 2015}]))
    assert any("slug" in x and "非法" in x for x in v)


def test_author_missing_book_slug_flagged():
    v = lint_author_html(author_html(), ajson(books=[{"title": "无 slug 的书", "pub_year": 2015}]))
    assert any("slug" in x for x in v)


def test_author_fullwidth_dash_flagged():
    v = lint_author_html(author_html(), ajson(evolution_summary="从甲到乙——这是断裂"))
    assert any("破折号" in x for x in v)


def test_author_external_quote_dash_exempt():
    # external.say 外证照录里的破折号豁免(不打回)
    turns = [{"id": "t1", "concept": "x", "from": {"stance": "a"}, "to": {"stance": "b"}, "verdict": "confirmed",
              "external": [{"type": "media", "who": "记者", "say": "他说——我变了", "source": "https://e.com"}]}]
    assert not any("破折号" in x for x in lint_author_html(author_html(), ajson(turns=turns)))


def test_author_bad_verdict_flagged():
    turns = [{"id": "t1", "concept": "x", "from": {"stance": "a"}, "to": {"stance": "b"},
              "verdict": "maybe", "external": []}]
    v = lint_author_html(author_html(), ajson(turns=turns))
    assert any("verdict" in x for x in v)


def test_author_confirmed_without_external_flagged():
    turns = [{"id": "t1", "concept": "x", "from": {"stance": "a"}, "to": {"stance": "b"},
              "verdict": "confirmed", "external": []}]
    v = lint_author_html(author_html(), ajson(turns=turns))
    assert any("external" in x for x in v)


def test_author_null_verdict_not_rendered_ok():
    # verdict=null 的转向不渲染;即使 from/to 不全也不该被结构门禁打回
    turns = [{"id": "t1", "concept": "x", "from": {}, "to": {}, "verdict": None, "external": []}]
    assert lint_author_html(author_html(), ajson(turns=turns)) == []


def test_author_skeleton_static_gate_clean():
    if not AUTHOR_SKELETON.exists():
        pytest.skip(f"作者骨架不存在: {AUTHOR_SKELETON}")
    html = AUTHOR_SKELETON.read_text(encoding="utf-8")
    # 先剥 HTML 注释,防骨架注释里的 `<script id="author-data">` 示例被误命中
    no_comments = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    m = re.search(r'<script[^>]*\bid="author-data"[^>]*>(.*?)</script>', no_comments, re.S)
    author = json.loads(m.group(1)) if m else None
    assert author is not None, "作者骨架应含可解析的内联 #author-data"
    v = lint_author_html(html, author)
    assert v == [], f"作者骨架静态门禁应全过,实际违规: {v}"

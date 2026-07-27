"""T0 未填槽 / 真封面 / schema 完整性门禁(v0.5,2026-07-27)。

立法背景:2026-07-26 用 Antigravity(Gemini 3.6 Flash)蒸格拉德威尔 6 本,产物实测 --
  · 4 本 HTML 各残留 36 处 {{…}} + 39 处 dummy,封面全是占位 SVG
  · distill.json 缺 8 个顶层键(concepts/critique/quotes/tensions/render_profile/cross_domain/slug/title)
  · 其中 1 本 verify_page.py **exit 0「全部通过」**
根因:旧门禁 174 项全是「遍历已有字段校验取值」,默认「一定会填槽、一定会产全 schema」。
     弱模型直接把模板原样交付 / 少产半个 schema 时,循环空转 = 零违规。
本文件锁住这三道补盲门禁,防回归。
"""
import sys
import json
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from verify_page import lint_html, lint_distill, lint_no_placeholder, lint_distill_schema

from test_verify_page import page, distill, dch, COVER_SVG_PLACEHOLDER, SKELETON


# ================================================================ T0-P 未填槽(占位符 / dummy 残留)
def test_placeholder_braces_flagged():
    v = lint_no_placeholder('<p>{{cover_intro}} 正文</p>')
    assert any("占位" in x and "cover_intro" in x for x in v)


def test_dummy_text_flagged():
    v = lint_no_placeholder("<p>书系定位(dummy)</p>")
    assert any("dummy" in x for x in v)


def test_dummy_inside_html_comment_exempt():
    """注释里的 dummy 豁免 -- 骨架顶部那条用法说明注释本身就含「删 dummy/占位」字样,
    正常交付页普遍保留(全库 51 本里 47 本有,不渲染无危害)。不豁免会 100% 误报。"""
    assert lint_no_placeholder("<!-- 用法:逐槽填真实内容 -> 删 dummy/占位 -->") == []


def test_dummy_outside_comment_still_flagged():
    """可见文案里的 dummy 照拦 -- 未填槽产物的 36 处残留全在这里。"""
    assert lint_no_placeholder('<!-- 删 dummy/占位 --><p>书系定位(dummy)</p>') != []


def test_placeholder_braces_inside_comment_still_flagged():
    """{{槽}} 不豁免注释:全库已交付页实测命中恒为 0,严格查零误报。"""
    assert lint_no_placeholder("<!-- {{book_type}} -->") != []


def test_clean_page_has_no_placeholder_violation():
    assert lint_no_placeholder("<p>正常成品正文,无任何占位。</p>") == []


def test_css_and_js_braces_not_false_positive():
    # 单层 { } (CSS/JS)与 ${} 模板串不得误判;只认双大括号
    clean = '<style>.a{color:red}</style><script>const s=`${x}`;if(a){b()}</script>'
    assert lint_no_placeholder(clean) == []


def test_placeholder_gate_wired_into_lint_html():
    v = lint_html(page(cover_intro="{{cover_intro}}"))
    assert any("占位" in x for x in v)


def test_skeleton_template_flagged_without_exemption():
    """骨架模板不传 allow_placeholder 时**必须**被拦 -- 否则等于放行「模板原样交付」。"""
    if not SKELETON.exists():
        pytest.skip(f"骨架不存在: {SKELETON}")
    v = lint_html(SKELETON.read_text(encoding="utf-8"))
    assert any("占位" in x for x in v)


def test_allow_placeholder_exempts_template_only():
    if not SKELETON.exists():
        pytest.skip(f"骨架不存在: {SKELETON}")
    v = lint_html(SKELETON.read_text(encoding="utf-8"), allow_placeholder=True)
    assert not any("占位" in x for x in v)


# ================================================================ T0-C 真封面(占位 SVG 不算数)
def test_placeholder_svg_cover_flagged():
    v = lint_html(page(cover=COVER_SVG_PLACEHOLDER))
    assert any("占位 SVG" in x for x in v)


def test_real_jpeg_cover_passes():
    assert not any("封面" in x for x in lint_html(page()))


def test_cover_fallback_declared_exempts():
    """联网确实拿不到真封面 → 须在 distill 顶层显式声明 cover_fallback,不许静默降级。"""
    d = distill(cover_fallback=True)
    v = lint_html(page(cover=COVER_SVG_PLACEHOLDER), distill=d)
    assert not any("占位 SVG" in x for x in v)


def test_cover_fallback_must_be_true_not_truthy_string():
    d = distill(cover_fallback="yes")
    v = lint_html(page(cover=COVER_SVG_PLACEHOLDER), distill=d)
    assert any("占位 SVG" in x for x in v)


# ================================================================ T0-S schema 完整性
def test_schema_clean_fixture_passes():
    assert lint_distill_schema(distill()) == []


@pytest.mark.parametrize("key", ["slug", "title", "author", "book_type",
                                 "render_profile", "core_question", "cover_intro"])
def test_missing_core_key_flagged(key):
    d = distill()
    del d[key]
    v = lint_distill_schema(d)
    assert any("[schema]" in x and key in x for x in v)


@pytest.mark.parametrize("key", ["quotes", "critique", "tensions", "concepts",
                                 "soul_module", "decision_rules", "mental_models"])
def test_missing_conditional_key_flagged(key):
    d = distill()
    del d[key]
    v = lint_distill_schema(d)
    assert any("[schema]" in x and key in x for x in v)


def test_empty_container_counts_as_missing():
    """弱模型常产 "quotes": [] 充数 -- 空容器等同缺失。"""
    assert any("quotes" in x for x in lint_distill_schema(distill(quotes=[])))
    assert any("critique" in x for x in lint_distill_schema(distill(critique={})))
    assert any("cover_intro" in x for x in lint_distill_schema(distill(cover_intro="")))


def test_alias_key_gets_named_hint():
    """Antigravity 实测把 title 写成 book_title -- 报错须直接点名,省一轮猜。"""
    d = distill()
    d["book_title"] = d.pop("title")
    v = lint_distill_schema(d)
    assert any("title" in x and "book_title" in x for x in v)


def test_omit_blocks_exempt_conditional_keys():
    """语录型 omit soul-block/rules/models/questions/verdict-bar → 这些键缺失不算违规。"""
    d = distill(render_profile={"archetype": "语录"})
    for k in ("soul_module", "decision_rules", "mental_models", "self_check", "credibility_verdict"):
        d.pop(k, None)
    v = lint_distill_schema(d)
    for k in ("soul_module", "decision_rules", "mental_models", "self_check", "credibility_verdict"):
        assert not any(k in x for x in v), f"{k} 应被 语录型 omit_blocks 豁免,实际: {v}"


def test_booklist_archetype_also_exempts_napkin():
    d = distill(render_profile={"archetype": "书单"})
    d.pop("napkin", None)
    assert not any("napkin" in x for x in lint_distill_schema(d))


def test_video_series_exempts_concepts_and_verdict():
    d = distill(source_type="video_series")
    d.pop("concepts", None)
    d.pop("credibility_verdict", None)
    v = lint_distill_schema(d)
    assert not any("concepts" in x or "credibility_verdict" in x for x in v)


def test_schema_gate_wired_into_lint_distill():
    d = distill()
    del d["concepts"]
    assert any("[schema]" in x and "concepts" in x for x in lint_distill(d))


def test_non_dict_distill_flagged():
    assert lint_distill_schema([]) != []


# ================================================================ 回归:复刻 Antigravity 实测产物形态
def test_antigravity_shaped_output_is_rejected():
    """复刻 2026-07-26 实测形态:填了大部分槽但缺 8 个顶层键 + 占位 SVG 封面 + 残留占位符。
    改造前这样的产物 verify 报 0 违规;改造后三道门必须全部命中。"""
    d = distill()
    d["book_title"] = d.pop("title")
    for k in ("concepts", "critique", "quotes", "tensions", "render_profile", "slug"):
        d.pop(k, None)
    v = lint_html(page(cover=COVER_SVG_PLACEHOLDER, cover_intro="{{cover_intro}} 书系定位(dummy)"),
                  distill=d)
    assert any("占位" in x for x in v), "未填槽门禁应命中"
    assert any("占位 SVG" in x for x in v), "真封面门禁应命中"
    assert any("[schema]" in x for x in v), "schema 完整性门禁应命中"

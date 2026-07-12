"""render_profile 书型自适应门禁变体化测试(2026-07-12 B-1/B-2)。
核心断言:① 非 legacy profile 关掉的 Tier-1 门禁不报;② Tier-0 底线永远报;
③ profile 完整性校验拦「自造书型 / 篡改 active_gates 绕门禁」;④ lint_html 按 omit_blocks/tabs 省略。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from verify_page import lint_distill, lint_html, RENDER_PROFILES, _resolve_active_gates
from test_verify_page import distill, dch, page

# 语录 profile:必须与注册表一致(archetype/narrative_mode/active_gates)
QUOTE_PROFILE = {"archetype": "语录", "narrative_mode": "list", "active_gates": ["G16"]}


def _quote_distill(**over):
    """语录书:list 档、无 narrative/soul/action_chain(这些 Tier-1 门禁被 profile 关掉)。"""
    base = dict(render_profile=QUOTE_PROFILE, chapters=[dch(narr=0, excerpts=[])],
                soul_module=None, action_chain=[])
    base.update(over)
    return distill(**base)


def test_quote_profile_relaxes_tier1_gates():
    v = lint_distill(_quote_distill())
    # 语录关掉的门禁不报:G9 字数 / G11 soul / G13 行动链 / G4 公式 / G19 核心问题 / G18 裁决
    for g in ("(G9", "(G11", "(G13", "(G4", "(G19", "(G18"):
        assert not any(g in x for x in v), f"{g} 不应在语录 profile 下报: {[x for x in v if g in x]}"


def test_tier0_still_enforced_under_profile():
    # Tier-0 底线(§5.1 anchor)即使在语录 profile 下也必报
    d = _quote_distill(core_ideas=[{"idea": "a", "anchor": "", "primary": True, "layman_analogy": "比"}])
    v = lint_distill(d)
    assert any("anchor" in x for x in v)


def test_legacy_still_full_gated():
    # 无 render_profile(legacy)= 全 Tier-1:缺 soul/action 照报(向后兼容不放宽)
    v = lint_distill(distill(soul_module=None, action_chain=[]))
    assert any("(G11" in x for x in v)
    assert any("(G13" in x for x in v)


def test_profile_integrity_unknown_archetype():
    d = distill(render_profile={"archetype": "菜谱", "narrative_mode": "list", "active_gates": []})
    assert any("不在注册表" in x for x in lint_distill(d))


def test_profile_integrity_tampered_active_gates():
    # 声明 archetype=语录 却篡改 active_gates(想偷开/关门禁)→ 判不一致
    d = distill(render_profile={"archetype": "语录", "narrative_mode": "list", "active_gates": ["G16", "G9"]})
    assert any("active_gates 与注册表不一致" in x for x in lint_distill(d))


def test_profile_integrity_narrative_mode_mismatch():
    d = distill(render_profile={"archetype": "语录", "narrative_mode": "full-800", "active_gates": ["G16"]})
    assert any("narrative_mode 应为" in x for x in lint_distill(d))


def test_registry_legacy_four_are_full():
    # 四型 legacy 的 active_gates = 全 Tier-1(= 无 profile 行为,向后兼容)
    from verify_page import TIER1_GATES
    for arch in ("论说", "叙事", "人物", "工具"):
        assert set(RENDER_PROFILES[arch]["active_gates"]) == set(TIER1_GATES)


def test_lint_html_quote_profile_omits_soul_block():
    d = _quote_distill()
    # 语录页省略 soul-block:传 profile 后不报「缺必需区块 .soul-block」
    v = lint_html(page(drop_class="soul-block"), distill=d)
    assert not any("soul-block" in x for x in v), [x for x in v if "soul-block" in x]
    # 反证:legacy(无 profile)drop soul-block 应报缺失
    v2 = lint_html(page(drop_class="soul-block"), distill=distill())
    assert any("soul-block" in x for x in v2)

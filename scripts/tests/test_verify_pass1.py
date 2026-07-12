"""verify_pass1.py 测试:Pass1 骨架门禁 = 全量门禁滤掉 Pass2 才产字段(narrative/excerpts/detail/hook)。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from verify_pass1 import pass1_violations, PASS2_ONLY_MARKERS
from verify_page import lint_distill
from test_verify_page import distill, dch  # 复用 verify_page 测试的 distill/章节 fixture


def _pass1_stage():
    """模拟 Pass1 阶段的 distill:章节尚无 narrative/excerpts。"""
    return distill(chapters=[dch(narr=0, excerpts=[])])


def test_pass1_clean_skeleton_passes():
    # Pass1 骨架完整(仅缺 Pass2 才产的 narrative/excerpts)→ 应全过
    assert pass1_violations(_pass1_stage()) == []


def test_pass1_filters_pass2_only_violations():
    d = _pass1_stage()
    raw = lint_distill(d)
    assert any("narrative" in x for x in raw)          # 全量门禁会报 narrative 缺
    assert any("excerpts" in x for x in raw)           # 和 excerpts 缺
    v1 = pass1_violations(d)
    assert not any(any(m in x for m in PASS2_ONLY_MARKERS) for x in v1)  # Pass1 全滤掉


def test_pass1_surfaces_real_skeleton_issue():
    # 真骨架问题(缺 soul_module,Pass1 就该产)不被误滤
    d = distill(chapters=[dch(narr=0, excerpts=[])], soul_module=None)
    assert any("soul_module" in x for x in pass1_violations(d))


def test_pass1_surfaces_bad_title_and_anchor():
    # 章标题非论点式(G8,Pass1 产)+ core_idea 缺 anchor(§5.1)应 surface
    d = distill(chapters=[dch(no=1, title="第1章", narr=0, excerpts=[])],
                core_ideas=[{"idea": "a", "anchor": "", "primary": True, "layman_analogy": "比"}])
    v = pass1_violations(d)
    assert any("G8" in x for x in v)
    assert any("anchor" in x for x in v)

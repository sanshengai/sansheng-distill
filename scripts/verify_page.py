#!/usr/bin/env python3
"""蒸馏页出厂验证 v3:静态 lint(HTML)+ 契约门禁(distill.json,可选 --distill)+ Playwright 渲染冒烟。
exit 0 全过 / 1 有违规。

v3(2026-07-04,5 板块浏览型 · 读者逻辑链;替换 v2 五段漏斗):
  - 必需模块从 v2 `data-module="Mxx"` 编号体系改为 **签名 class**(html-spec §1.2/§2.0 T1 契约单一来源)。
  - 五 tab 文案改 A 套名词式主名(全书速览/逐章精读/批判与评价/行动清单/延伸阅读)+ panel id(glance/full/judge/action/extend)。
  - **契约反转(T6)**:②章节由 v2「默认全展开」改「目录态默认收起 + 手风琴多开」;删掉 v2 的 details 禁令与全展开断言,
                     改成正向断言 -- 目录态默认收起(`.bd-chapter` 初始不可见)+「全部展开」逃生钮 `.toc-expand[data-toc-toggle]` 存在 + 点 `.toc-row` 能展开(smoke)。
  - **金句唯一归宿(T7)**:金句只落 `.quote-wall`;`.quote-inline`/`.featured-quotes`(FQ)v2 遗留结构存在即报警。
  - **核心观点卡展开态(T8)**:必渲 `.ci-explain` + `.ci-evidence` + `.ci-evlevel`。
  - **查重 lint(§2.2 / G16)**:传 --distill 时,渲染的 `.cb-intro` / `.hero h1` 文案含 `napkin.one_liner` 中 ≥12 字连续片段 → FAIL。
  - **Zero-Hex**:token 块外零 hex;`color-mix(...)`(四区用 var(--*) 合成)不是字面 hex 违规,显式放行。
  - **作者一致性**:`#sub-author` 存在 ⟹ 含 `.au-infobox` 且 `.au-work-this`(works 恰一条 is_this_book)恰 1;
                   传 enrich 时交叉校验 author_page/views_page/reviews 为 null ⟺ 对应块/子视图删除(§1.5 降级一致性)。
  传 --distill 追加契约门禁 G8-G21:narrative 详实度(G9)、§5.1 六类 anchor、excerpts 版权红线(G14)、primary/featured(G15)、
          layman_analogy(G10)、soul_module(G11,含 curve.series)、self_check(G12)、action_chain(G13)、
          cover_intro(G16 存在+2-3 句+不复用 napkin)、action_chain[].detail(G17 每环去空白≥60 字)、
          credibility_verdict(G18 书籍必产)、chain_step / pillar 合法性(∈[1,5] 或 null,不越界)。
  v4(2026-07-05,深度分析批次 B):core_question(G19 书/视频必产、≤40 字疑问句、不复用 cover_intro/one_liner)、
          arguments.chain_steps(G20 4-8 步、每步 ≤14 字)、chapters[].hook(G21 若产则 ≤20 字);
          渲染侧:hero .eyebrow 渲 core_question,不得复用 one_liner/cover_intro(§2.2 查重)。
  v4 批次 B-2(2026-07-05,餐巾纸四件套):napkin.formula_read(G4 扩展 a,书/视频必产、≤80 字、含运算符/语义词)、
          napkin.sketch(G4 扩展 b,可降级;若产则 type/caption/nodes[6,12]/edges 齐全、node.label 集合 ≠ 公式右侧项)。
"""
import argparse
import json
import re
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SIZE_LIMIT = 3 * 1024 * 1024  # 3MB

# v3 必需签名 class(html-spec §1.5「必含区块」;可降级块 concept-chips/reviews/views-entry/⑤/子视图不列)
# 顺序:头部两层 / ① / ②(concept-chips 可降级不列) / ③ / ④(chain 用 data-chain 另检) / footer
# 注:.reading-guide 导读条 v3.1 移除(与 nav.tabs 重复列 5 板块),导航唯一入口 = sticky nav.tabs
REQUIRED_CLASSES = [
    "cb-banner", "cb-intro", "hero",                              # 头部两层(刊头 + hero)
    "bd-napkin", "bd-mindmap-wrap", "bd-coreideas", "soul-block",  # ① 全书速览
    "chapter-toc", "bd-chapter", "quote-wall",                    # ② 逐章精读(目录态)
    "verdict-bar", "arg-restate", "tensions", "crit-quad",        # ③ 批判与评价
    "rules", "models", "questions",                              # ④ 行动清单(chain 见 data-chain)
    "next-cta", "footer",
]
# v2 遗留结构(存在即违规):章内行内金句 / 首屏独立金句条(T7 金句唯一归宿=②金句墙)
FORBIDDEN_CLASSES = ["quote-inline", "featured-quotes"]
# v3 五 tab:(panel id, A 套名词式主名)。顺序 = 骨架 glance/full/judge/action/extend
TABS = [("panel-glance", "全书速览"), ("panel-full", "逐章精读"), ("panel-judge", "批判与评价"),
        ("panel-action", "行动清单"), ("panel-extend", "延伸阅读")]
# v2 漏斗黑话主名:禁出现在 tab 按钮文案(html-spec §1.1 硬契约)
FORBIDDEN_TAB_LABELS = ["一眼全书", "书魂", "该信几分", "全书详实"]

SUBPAGE_SECTION_RE = re.compile(
    r'<section[^>]*\bclass="[^"]*\bsubpage\b[^"]*"[^>]*\bid="(sub-[\w-]+)"[^>]*>(.*?)</section>', re.S)
SUBPAGE_ENTRY_RE = re.compile(r'href="#(sub-[\w-]+)"')

HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
TOKEN_BLOCK_RE = re.compile(r"(:root|body\[data-theme=[^\]]+\])\s*\{[^}]*\}", re.S)
# vendor 专用样式块 <style data-vendor>(通用机制:任何内联 vendor CSS 的字面 hex 属 vendor 合规):零-hex 门禁前先整块剥离。
# 注:自绘 SVG 脑图已无 vendor,当前骨架不触发此豁免;保留机制以备未来内联第三方 CSS
VENDOR_STYLE_RE = re.compile(r'<style[^>]*\bdata-vendor\b[^>]*>.*?</style>', re.S)
# 脑图自绘 SVG 内联 JSON 数据契约(§5)
MINDMAP_DATA_RE = re.compile(r'<script[^>]*\bid="bd-mindmap-data"[^>]*>(.*?)</script>', re.S)
CH_ANCHOR_RE = re.compile(r'#ch-(\d+)')
CH_ID_RE = re.compile(r'id="ch-(\d+)"')
MIN_SVG_TEXT = 6  # smoke:脑图 SVG 内 <text> 至少这么多(root + 一级 + 二级/叶子 = 生成器真出图)
# G8 章标题黑名单:纯章号 / 集号
TITLE_NUM_RE = re.compile(r"^(第?\d+[章节讲集]?|视频\d+)$")
CONTAINER_WORDS = {"章节脉络", "全书脉络", "内容概要", "核心内容", "主要观点",
                   "金句墙", "金句", "总结", "概述", "前言", "结语"}
# §5.1/§V.3 合法 anchor:第N章 / 约全书XX%处 / 视频N
ANCHOR_RE = re.compile(r"第\d+章|约全书\d+%处|视频\d+")
EXCERPT_MAX = 150  # 版权红线:单段引用去空白 ≤150 字
DUP_RUN = 12       # 查重:cover_intro/hero 与 napkin.one_liner 的 ≥12 字连续重叠片段
# Q7-12 破折号统一:可见转述正文禁全角破折号 —(U+2014)/―(U+2015);原文照录豁免区(blockquote/qw-card)剔除
FULLWIDTH_DASH_RE = re.compile(r"[—―]")
# Q7-9:chain_step 关联做法数为 0 → .cs-badge 整个不渲染;拦「0 条…做法」死徽标
CS_BADGE_RE = re.compile(r'<span[^>]*\bclass="[^"]*\bcs-badge\b[^"]*"[^>]*>(.*?)</span>', re.S)
ZERO_BADGE_RE = re.compile(r"0\s*条")
# 餐巾纸四件套(v4,批次 B-2):formula_read 读法(G4 扩展 a)+ sketch 因果骨架(G4 扩展 b)
FORMULA_READ_MAX = 80  # formula_read 有效长上限
FR_OPERATORS = set("=≈∝+−-×*÷/><≥≤→%")  # 公式运算符(formula_read 须含其一或语义词)
FR_SEMANTIC = ("乘", "加", "减", "除", "归零", "缺一", "比例", "乘积", "相乘", "相加", "相减")
SKETCH_TYPES = ("cascade", "fork", "loop")
# 公式右侧项拆分:先按首个 = 取右侧,再按运算符 / 括号切词(判「sketch 是否重画公式」)
FORMULA_OP_SPLIT = re.compile(r"[=≈∝+−\-×*÷/><≥≤→%()（）]")

# ---- 作者演变页(author-page-skeleton)独立门禁(references/author-craft.md §0 铁律)----
# 作者页与蒸馏页结构不同:检测到作者页则走 lint_author_html,不套蒸馏页 REQUIRED_CLASSES。
AUTHOR_DATA_RE = re.compile(r'<script[^>]*\bid="author-data"[^>]*>(.*?)</script>', re.S)
# 4 视图容器签名 class(时间线 / 母题 ribbon / 转向 / 概念图);静态骨架恒在(JS 只 unhide section)
AUTHOR_VIEW_CLASSES = [("tl-scroll", "时间线"), ("rb-scroll", "母题 ribbon"),
                       ("ap-turns", "转向"), ("dag-wrap", "概念图")]
AUTHOR_VERDICTS = {"confirmed", "apparent", "refuted"}
EVOLUTION_VERDICT_STANCES = {"continuous", "segmented", "mixed"}
# 破折号扫描豁免的子树键(external=外证 blockquote 照录;_provenance/来源 URL 非转述文字)
AUTHOR_DASH_EXEMPT_KEYS = {"external", "_provenance", "sources", "source", "timeline_anchors"}
# 深链 slug 坏字符(会破坏 ../{slug}/{slug}.html 内链;不强求目标文件存在,只验格式)
SLUG_BAD_RE = re.compile(r'[\s/\\<>"\']')

# ---- render_profile 书型自适应注册表(2026-07-12 B-1/B-2;method §1.4 契约镜像)----
# 门禁分两层,防「灵活」变成绕过反注水检查的洞:
#   Tier-0 底线(**不列入 active_gates,永远校验**):§5.1 六类 anchor / excerpts≤150 版权(G14 长度)/
#     primary·featured(G15)/ chain_step 合法 / 真封面 / 零外链 / Zero-Hex / data-source≥20 / 破折号 / lang=zh / 体积
#     —— 与书型无关,任何 profile 不可关。
#   Tier-1 形态(**随 archetype 的 active_gates 生效**):对不同体裁一刀切会误伤,故变体化。
TIER1_GATES = {"G4", "G8", "G9", "G10", "G11", "G12", "G13", "G16", "G17", "G18", "G19", "G20"}
_ALL_T1 = frozenset(TIER1_GATES)
# 四型 legacy = 全 Tier-1(= 无 render_profile 时的现行行为,向后兼容,旧书不必重蒸);四新型按体裁裁剪。
# active_gates 是注册表**权威**值:verify 以本表为准,data.render_profile.active_gates 与之不符即判篡改(防逐书手写绕检查)。
RENDER_PROFILES = {
    "论说": {"narrative_mode": "full-800", "active_gates": _ALL_T1, "omit_blocks": ()},
    "叙事": {"narrative_mode": "full-800", "active_gates": _ALL_T1, "omit_blocks": ()},
    "人物": {"narrative_mode": "full-800", "active_gates": _ALL_T1, "omit_blocks": ()},
    "工具": {"narrative_mode": "full-800", "active_gates": _ALL_T1, "omit_blocks": ()},
    # 语录/箴言:原文 excerpt 为主 + 逐条点评,砍讲书稿字数下限/公式/soul/行动链/论证链(治抽象密集书注水)
    "语录": {"narrative_mode": "list", "active_gates": frozenset({"G16"}),
             "primitives": ("语录墙",), "tabs": ("glance", "full", "extend"),
             "omit_blocks": ("soul-block", "arg-restate", "rules", "models", "questions", "verdict-bar")},
    # 书单/合集:每本一卡,无单一「本书」可蒸(单一 napkin/soul/core_question 是范畴错误)
    "书单": {"narrative_mode": "list", "active_gates": frozenset(),
             "primitives": ("书单卡",), "tabs": ("glance", "full", "extend"),
             "omit_blocks": ("soul-block", "arg-restate", "rules", "models", "questions", "verdict-bar", "bd-napkin")},
    # 课程培训:知识点树(递进结构非论点)+ 练习/项目卡
    "课程": {"narrative_mode": "dense-card", "active_gates": frozenset({"G9", "G13"}),
             "primitives": ("知识点树", "练习卡"), "tabs": ("glance", "full", "action", "extend"),
             "omit_blocks": ("soul-block", "arg-restate")},
    # 考试:考点卡 + 例题解析 + 记忆卡(复活 quiz)
    "考试": {"narrative_mode": "dense-card", "active_gates": frozenset({"G9"}),
             "primitives": ("考点卡", "例题解析", "记忆卡"), "tabs": ("glance", "full", "extend"),
             "omit_blocks": ("soul-block", "arg-restate", "rules", "models", "questions", "verdict-bar")},
}
LEGACY_ARCHETYPES = frozenset({"论说", "叙事", "人物", "工具"})
# dense-card 档 narrative 字数下限(考点/知识点卡本应短密,不套 800)
DENSE_CARD_FLOOR = 300


def _resolve_active_gates(prof):
    """按 render_profile.archetype 取注册表**权威** active_gates。
    无 profile / 未知 archetype → 返回 None = legacy(全 Tier-1 校验,向后兼容 + 安全兜底)。"""
    if not isinstance(prof, dict):
        return None
    reg = RENDER_PROFILES.get(prof.get("archetype"))
    return set(reg["active_gates"]) if reg else None


def _lint_profile_integrity(prof) -> list:
    """render_profile 完整性校验(防逐书手写门禁绕反注水检查):
    archetype 必须命中注册表;data 里声明的 active_gates / narrative_mode 必须与注册表**一致**(不许篡改)。"""
    if not prof:
        return []
    if not isinstance(prof, dict):
        return ["[profile] render_profile 非对象"]
    v = []
    arch = prof.get("archetype")
    reg = RENDER_PROFILES.get(arch)
    if reg is None:
        return [f"[profile] render_profile.archetype {arch!r} 不在注册表 {sorted(RENDER_PROFILES)}(禁自造书型;新型须先入注册表)"]
    if "active_gates" in prof and set(prof.get("active_gates") or []) != set(reg["active_gates"]):
        v.append(f"[profile] archetype={arch} 的 active_gates 与注册表不一致(禁逐书篡改绕门禁;应为 {sorted(reg['active_gates'])})")
    if "narrative_mode" in prof and prof.get("narrative_mode") != reg["narrative_mode"]:
        v.append(f"[profile] archetype={arch} 的 narrative_mode 应为 {reg['narrative_mode']!r}")
    return v


def _effective_len(t: str) -> int:
    """去标点空白后的有效长度(CJK/字母/数字计入;Python3 \\w 默认含 CJK,不吃中文)。"""
    return len(re.sub(r"[^\w]", "", t, flags=re.UNICODE))


def _has_class(html: str, cls: str) -> bool:
    """整词匹配 class="… cls …"(避免 bd-chapter 误命中 bd-chapters 之类前缀)。"""
    return re.search(r'class="[^"]*\b' + re.escape(cls) + r'\b[^"]*"', html) is not None


def _count_class(html: str, cls: str) -> int:
    return len(re.findall(r'class="[^"]*\b' + re.escape(cls) + r'\b[^"]*"', html))


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "")


def _visible_transcribed(html: str) -> str:
    """可见转述正文 = 剥 script/style/注释 + 原文照录豁免区(blockquote:excerpt 原文 + 金句 quote / .qw-card figure),再去标签取文本节点。
    Q7-12:转述文本破折号一律 --;excerpt/quote 原文照录不改,故整块剔除不参与破折号扫描。"""
    s = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", html, flags=re.S)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<blockquote\b[^>]*>.*?</blockquote>", "", s, flags=re.S)
    s = re.sub(r'<figure\b[^>]*\bclass="[^"]*\bqw-card\b[^"]*"[^>]*>.*?</figure>', "", s, flags=re.S)
    return _strip_tags(s)


def _strip_color_mix(css: str) -> str:
    """删掉 color-mix(...) 表达式(含 var(--*) 内层括号,按括号配平),使其内部内容不参与 hex 扫描。
    四区背景 color-mix(in srgb,var(--gold) 10%,transparent) 全用 token,本无字面 hex;此步是显式放行 + 未来防误伤。"""
    out, i, n = [], 0, len(css)
    while i < n:
        j = css.find("color-mix(", i)
        if j < 0:
            out.append(css[i:])
            break
        out.append(css[i:j])
        depth, k = 0, j + len("color-mix")  # 从 '(' 起配平
        while k < n:
            c = css[k]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    k += 1
                    break
            k += 1
        i = k
    return "".join(out)


def _shares_long_run(text: str, ref: str, n: int = DUP_RUN) -> bool:
    """text 是否含 ref 中长度 ≥n 的连续片段(去空白后)。ref/text 任一去空白 <n 则不可能共享 → False。"""
    t = re.sub(r"\s", "", text or "")
    r = re.sub(r"\s", "", ref or "")
    if len(r) < n or len(t) < n:
        return False
    for i in range(len(r) - n + 1):
        if r[i:i + n] in t:
            return True
    return False


def _sentence_count(s: str) -> int:
    """按句末标点 。！？ 切分的句数;末尾无标点的尾串计 1 句(过滤空段即得)。"""
    return len([p for p in re.split(r"[。！？]", (s or "").strip()) if p.strip()])


def _formula_rhs_terms(formula: str) -> set:
    """公式右侧项集合:按首个 = 取右侧,再按运算符/括号切词、去空白。无 = 返回空集。
    用于「sketch.nodes 是否与公式右侧项完全相同」的重画判定。"""
    s = str(formula or "")
    if "=" not in s:
        return set()
    rhs = s.split("=", 1)[1]
    parts = (re.sub(r"\s", "", p) for p in FORMULA_OP_SPLIT.split(rhs))
    return {p for p in parts if p}


def is_bad_title(title: str) -> bool:
    """G8 章标题黑名单:① 纯章号/集号 ② 整标题落通用容器词表 ③ 有效长 <8。判断句语义靠蒸馏自查。
    注(M1):容器词表判定放在「有效长 <8」之前,使 G8③(html-spec T5③)可达 —— 否则现有词表皆 <8 字,
    会被 ② 先行拦下成死分支;词表命中给专属语义、且未来若加长容器词仍能拦。"""
    t = (title or "").strip()
    core = re.sub(r"\s", "", t)
    if TITLE_NUM_RE.match(core):
        return True
    if core in CONTAINER_WORDS or t in CONTAINER_WORDS:
        return True
    if _effective_len(t) < 8:
        return True
    return False


def anchor_ok(s) -> bool:
    return bool(s) and bool(ANCHOR_RE.search(str(s)))


def lint_html(html: str, distill: dict | None = None, enrich: dict | None = None) -> list:
    v = []
    # render_profile(2026-07-12 B-1/B-2):非 legacy 书型可按 omit_blocks/tabs 省略部分区块与 tab;
    #   无 profile / 未知 archetype → 全量必检(向后兼容,现有 legacy 页与 196 测试不受影响)。
    #   profile 完整性校验由 lint_distill 统一做(此处不重复,避免重复报 [profile])。
    prof = distill.get("render_profile") if isinstance(distill, dict) else None
    _reg = RENDER_PROFILES.get((prof or {}).get("archetype")) if prof else None
    omit_blocks = set(_reg["omit_blocks"]) if _reg else set()
    allowed_tabs = set(_reg.get("tabs", ())) if _reg else None   # None = 全 5 tab 必检
    active_h = _resolve_active_gates(prof)

    def gon_h(g):  # Tier-1 形态门禁在 HTML 侧是否生效
        return active_h is None or g in active_h
    # 体积上限 3MB
    if len(html.encode("utf-8")) > SIZE_LIMIT:
        v.append("[lint] 体积超 3MB 预算")
    # 必需签名 class 齐(render_profile.omit_blocks 声明省略的块不检)+ 禁存在 v2 遗留金句结构(T7)
    for cls in REQUIRED_CLASSES:
        if cls in omit_blocks:
            continue
        if not _has_class(html, cls):
            v.append(f"[lint] 缺必需区块 .{cls}")
    if "data-chain" not in html and "rules" not in omit_blocks:  # 行动 tab 省略(rules 在 omit)时不检行动路线图
        v.append("[lint] 缺行动路线图 .chain[data-chain](④)")
    for cls in FORBIDDEN_CLASSES:
        if _has_class(html, cls):
            v.append(f"[lint] 存在 v2 遗留金句结构 .{cls}(金句唯一归宿=②金句墙 .quote-wall,T7)")
    # 目录态逃生门(T6):「全部展开」钮 .toc-expand[data-toc-toggle] 必存在
    if not re.search(r'class="[^"]*\btoc-expand\b[^"]*"[^>]*\bdata-toc-toggle\b', html) \
       and not re.search(r'\bdata-toc-toggle\b[^>]*class="[^"]*\btoc-expand\b', html):
        v.append("[lint] 缺目录态「全部展开」逃生门 .toc-expand[data-toc-toggle](T6)")
    # 核心观点卡展开态三件(T8)
    for cls in ("ci-explain", "ci-evidence", "ci-evlevel"):
        if not _has_class(html, cls):
            v.append(f"[lint] 核心观点卡展开态缺 .{cls}(T8 必渲三件:explain/evidence/evlevel)")
    # 五 tab:panel id + 按钮 + A 套文案(render_profile.tabs 声明的才检;新型可只留部分 tab)。
    #   tab 按钮/文案限定 nav.tabs 内查 —— data-panel 也用于 reading-guide/next-cta,全文查会漏报 tab 缺失。
    nav_m = re.search(r'<nav[^>]*\bid="bd-tabs"[^>]*>(.*?)</nav>', html, re.S)
    nav_html = nav_m.group(1) if nav_m else ""
    for pid, label in TABS:
        if allowed_tabs is not None and pid.replace("panel-", "") not in allowed_tabs:
            continue  # 本 profile 未声明该 tab,不检
        if f'data-panel="{pid}"' not in nav_html:
            v.append(f"[lint] 缺 tab 按钮 data-panel={pid}")
        if f'id="{pid}"' not in html:
            v.append(f"[lint] 缺 panel 容器 id={pid}")
        if label not in nav_html:
            v.append(f"[lint] 缺 tab 文案「{label}」")
    # v2 漏斗黑话主名禁出现在 tab 按钮文案
    tab_texts = re.findall(r'<button[^>]*\bclass="[^"]*\btab\b[^"]*"[^>]*>(.*?)</button>', html, re.S)
    tab_join = " ".join(_strip_tags(t) for t in tab_texts)
    for bad in FORBIDDEN_TAB_LABELS:
        if bad in tab_join:
            v.append(f"[lint] tab 文案含 v2 黑话主名「{bad}」(应用 A 套名词式主名)")
    # ② 手风琴章节存在 + 默认收起(无 .open 初始态,T6 正向断言的静态部分;可见性由 smoke 断)
    chap_bodies = re.findall(r'<section[^>]*\bclass="([^"]*\bbd-chapter\b[^"]*)"[^>]*>(.*?)</section>', html, re.S)
    if not chap_bodies:
        v.append("[lint] panel-full 无 section.bd-chapter 章节")
    for cls_attr, body in chap_bodies:
        if re.search(r"\bopen\b", cls_attr):
            v.append("[lint] .bd-chapter 初始带 open 类(目录态应默认收起,T6)")
        m = re.search(r"<h3[^>]*>(.*?)</h3>", body, re.S)
        if m:
            title = _strip_tags(m.group(1)).strip()
            if gon_h("G8") and is_bad_title(title):  # 论点式标题门禁(语录/考试等 profile 可关,见 render_profile)
                v.append(f"[lint] 章标题非论点式(G8): {title!r}")
    # 书籍封面 img.cb-cover[src^="data:image"]
    if not (re.search(r'<img[^>]*\bclass="[^"]*\bcb-cover\b[^"]*"[^>]*\bsrc="data:image', html)
            or re.search(r'<img[^>]*\bsrc="data:image[^"]*"[^>]*\bclass="[^"]*\bcb-cover\b', html)):
        v.append('[lint] 缺书籍封面 img.cb-cover[src^="data:image"](禁外链/占位 div)')
    # 子视图一致性(可降级 §1.5):每个存在的 .subpage 须有入口链 + 返回按钮;禁死链入口
    present_subs = {sid: body for sid, body in SUBPAGE_SECTION_RE.findall(html)}
    entry_targets = set(SUBPAGE_ENTRY_RE.findall(html))
    for sid, body in present_subs.items():
        if sid not in entry_targets:
            v.append(f"[lint] 子视图 #{sid} 存在却无入口(缺 href=\"#{sid}\" 入口链)")
        if "data-sub-back" not in body:
            v.append(f"[lint] 子视图 #{sid} 缺返回按钮 [data-sub-back]")
    for tgt in entry_targets:
        if tgt not in present_subs:
            v.append(f"[lint] 入口 href=\"#{tgt}\" 指向不存在的子视图(删子视图须连同入口一并删,§1.5)")
    # 作者页内部一致性:#sub-author 存在 ⟹ 含 .au-infobox + .au-work-this 恰 1(works 恰一条 is_this_book)
    if 'id="sub-author"' in html:
        if not _has_class(html, "au-infobox"):
            v.append("[lint] #sub-author 存在但缺 .au-infobox 归一栏")
        n_this = _count_class(html, "au-work-this")
        if n_this != 1:
            v.append(f"[lint] 作者页 .au-work-this 数 {n_this} ≠ 1(works 须恰一条 is_this_book=true)")
    # 返回胶囊 .sub-back(有子视图时必存在)
    if present_subs and not _has_class(html, "sub-back"):
        v.append("[lint] 有子视图但缺返回胶囊 .sub-back")
    # 「显示出处」开关 #srcToggle 已废 + .src-note 常显存在
    if 'id="srcToggle"' in html:
        v.append('[lint] 「显示出处」开关 #srcToggle 应删除(出处改 .src-note 随文常显)')
    if 'class="src-note"' not in html and "src-note" not in re.sub(r"<!--.*?-->", "", html, flags=re.S):
        v.append("[lint] 缺常显出处 .src-note")
    # 零外链(script/link/img)
    if re.search(r'<script[^>]+src=["\']https?://', html) or re.search(r'<link[^>]+href=["\']https?://', html) \
       or re.search(r'<img[^>]+src=["\']https?://', html):
        v.append("[lint] 存在外链资源(script/link/img),违反零 CDN")
    # 禁内嵌播放器
    if re.search(r"<(iframe|video|embed)\b", html, re.I):
        v.append("[lint] 存在内嵌播放器标签(iframe/video/embed),违反跳转不内嵌铁律")
    # 脑图自绘 SVG JSON 数据契约(§5:一级分支挂锚 / 锚点真实 / 二级 tags[0] 判断句 / 全图字数)
    v += lint_mindmap(html)
    # token 块外零 hex:先整块剥离 vendor 专用 <style data-vendor>(通用豁免;当前无 vendor,脑图 --mm-* 走 :root token),
    #   再剥 token 块 + color-mix 内层 var(--*)
    html_scan = VENDOR_STYLE_RE.sub("", html)
    css = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html_scan, re.S))
    css_no_tokens = TOKEN_BLOCK_RE.sub("", css)
    css_no_tokens = _strip_color_mix(css_no_tokens)
    hexes = HEX_RE.findall(css_no_tokens)
    if hexes:
        v.append(f"[lint] token 块外硬编码色 {len(hexes)} 处: {sorted(set(hexes))[:5]}…")
    # lang
    if 'lang="zh"' not in html:
        v.append("[lint] html 缺 lang=\"zh\"")
    # data-source 出处覆盖 ≥20
    if html.count("data-source") < 20:
        v.append(f"[lint] data-source 出处覆盖 {html.count('data-source')} 处,低于 20 下限")
    # Q7-12 破折号统一:转述正文禁全角 —/―(原文照录 blockquote/qw-card 豁免)
    n_dash = len(FULLWIDTH_DASH_RE.findall(_visible_transcribed(html)))
    if n_dash:
        v.append(f"[lint] 转述正文含全角破折号 —/― {n_dash} 处(应统一 --;原文引用 blockquote/qw-card 照录豁免,Q7-12)")
    # Q7-9:.cs-badge 死徽标「0 条…做法」(关联做法数为 0 应整个不渲染)
    for badge in CS_BADGE_RE.findall(html):
        if ZERO_BADGE_RE.search(_strip_tags(badge)):
            v.append("[lint] .cs-badge 出现「0 条…做法」死徽标(chain_step 关联做法数为 0 应不渲染 .cs-badge,Q7-9)")
            break
    # 查重 lint(§2.2 / G16 渲染侧):cover_intro/hero 文案含 napkin.one_liner ≥12 字连续片段
    if distill is not None:
        one_liner = (((distill.get("napkin") or {}).get("one_liner")) or "")
        m_intro = re.search(r'class="[^"]*\bcb-intro\b[^"]*"[^>]*>(.*?)</p>', html, re.S)
        intro_txt = _strip_tags(m_intro.group(1)) if m_intro else ""
        m_hero = re.search(r'class="[^"]*\bhero\b[^"]*"[^>]*>(.*?)</section>', html, re.S)
        hero_h1 = ""
        if m_hero:
            mh = re.search(r"<h1[^>]*>(.*?)</h1>", m_hero.group(1), re.S)
            hero_h1 = _strip_tags(mh.group(1)) if mh else ""
        if _shares_long_run(intro_txt, one_liner):
            v.append(f"[lint] 封面简介 .cb-intro 复用 napkin.one_liner ≥{DUP_RUN} 字连续片段(§2.2 查重)")
        if _shares_long_run(hero_h1, one_liner):
            v.append(f"[lint] hero 标语复用 napkin.one_liner ≥{DUP_RUN} 字连续片段(§2.2 查重)")
        # v4 G19 渲染侧:hero eyebrow(core_question)不得复用 one_liner / cover_intro
        m_eb = re.search(r'class="[^"]*\beyebrow\b[^"]*"[^>]*>(.*?)</p>', html, re.S)
        eyebrow_txt = _strip_tags(m_eb.group(1)) if m_eb else ""
        cover_txt = str(distill.get("cover_intro") or "")
        if _shares_long_run(eyebrow_txt, one_liner):
            v.append(f"[lint] hero eyebrow(core_question)复用 napkin.one_liner ≥{DUP_RUN} 字连续片段(§2.2 查重)")
        if _shares_long_run(eyebrow_txt, cover_txt):
            v.append(f"[lint] hero eyebrow(core_question)复用 cover_intro ≥{DUP_RUN} 字连续片段(§2.2 查重)")
    # enrich 降级一致性(数据 null ⟺ 对应块/子视图删除,§1.5)
    if enrich is not None:
        v += lint_enrich_consistency(html, enrich)
    # 契约门禁(可选)
    if distill is not None:
        v += lint_distill(distill)
    return v


def _leaf_hyperlinks(node: dict) -> list:
    """收集节点子树里所有 hyperLink(含自身)。充实树里 hyperLink 落在二级核心观点节点(非最深叶子),
    本函数按子树收集、对深度不敏感,故二级挂锚同样被采集,门禁③无需改。"""
    out = []
    hl = node.get("hyperLink")
    if hl:
        out.append(hl)
    for c in node.get("children") or []:
        out += _leaf_hyperlinks(c)
    return out


def _sum_topic_chars(node: dict) -> int:
    """全图 topic 总字数(有效长:CJK/字母/数字,不计 emoji/标点/空格/序号;Q3-5 ≤900 的度量)。"""
    return _effective_len(str(node.get("topic") or "")) + \
        sum(_sum_topic_chars(c) for c in node.get("children") or [])


def lint_mindmap(html: str) -> list:
    """脑图数据契约门禁(§5,自绘 SVG 深色版):生成器读 `nodeData` 出图,**只画父子直角引线、不画任何关联箭头/收纳虚线**,
    故 arrows/summaries 不再是契约的一部分 —— 若数据里残留,生成器一律忽略(不检查、不要求、不由字段驱动)。
    本函数只审 `nodeData` 树的静态数据契约(与渲染引擎无关,故仍能在页面片段上机检):
    ① 一级分支(root.children)每个至少一个 hyperLink 叶子(连续章区段/概念桶的宽松式:分支须挂真实章锚点);
    ② 每个 hyperLink #ch-N 在页面有对应 id=ch-N(锚点真实存在,不死链,对齐全页循环动线);
    ③ 二级核心观点须 tags[0] 判断句副文本(有效长 ≥8 字);tags[1] 承载章码 chip(Q3-1);
    ④ 全图 topic 总字数 ≤900(乱的真度量是字数不是节点数,Q3-5)。

    透传字段适配:忽略 `_src`/`expanded`/`layout`/`arrows`/`summaries` 等生成器原样挂载或忽略的键
      (json.loads 天然容纳未知键);不设节点数上限(充实树几十节点属正常)。
    **SVG 结构断言**(脑图区真出 `<svg>`、文字节点数达标、无关联箭头元素、viewer 脚本已跑、点二级真跳章)
      属渲染期产物,由 Playwright 冒烟 smoke() 断,不进本静态 lint。"""
    v = []
    m = MINDMAP_DATA_RE.search(html)
    if not m:
        v.append('[脑图] 缺内联数据 <script id="bd-mindmap-data">(自绘 SVG 数据契约,§5)')
        return v
    try:
        data = json.loads(m.group(1))
    except Exception as e:
        v.append(f"[脑图] bd-mindmap-data JSON 解析失败: {e}")
        return v
    node = data.get("nodeData") or {}
    # ① 一级分支各挂 hyperLink 叶子
    branches = node.get("children") or []
    if not branches:
        v.append("[脑图] root 无一级分支 children(§5)")
    all_links = []
    for b in branches:
        links = _leaf_hyperlinks(b)
        all_links += links
        if not links:
            v.append(f"[脑图] 一级分支 {b.get('id', b.get('topic', '?'))!r} 无 hyperLink 叶子"
                     "(须挂真实章锚点,禁造书里没有的层级,§5)")
    # ② hyperLink #ch-N 锚点真实存在
    page_chs = set(CH_ID_RE.findall(html))
    for hl in all_links:
        cm = CH_ANCHOR_RE.search(str(hl))
        if cm and cm.group(1) not in page_chs:
            v.append(f"[脑图] hyperLink {hl!r} 指向不存在的章锚点 id=ch-{cm.group(1)}(死链,§5)")
    # ③ (Q3-1)二级核心观点须 tags[0] 判断句副文本(有效长 ≥8 字);tags[1] 承载章码 chip
    for b in branches:                       # 一级分支
        for lv2 in b.get("children") or []:  # 二级核心观点
            tags = lv2.get("tags")
            t0 = tags[0] if isinstance(tags, list) and tags else None
            nid = lv2.get("id", lv2.get("topic", "?"))
            if not (t0 and str(t0).strip()):
                v.append(f"[脑图] 二级节点 {nid!r} 缺 tags[0] 判断句副文本(双层化后判断句须落 tags[0],Q3-1)")
            elif _effective_len(str(t0)) < 8:
                v.append(f"[脑图] 二级节点 {nid!r} 的 tags[0] 有效长 {_effective_len(str(t0))} <8 字(判断句副文本,Q3-1)")
    # ④ (Q3-5)全图 topic 总字数 ≤900(乱的真度量是字数不是节点数)
    total_chars = _sum_topic_chars(node)
    if total_chars > 900:
        v.append(f"[脑图] 全图 topic 总字数 {total_chars} >900(须凝练,乱的真度量是字数,Q3-5)")
    return v


def lint_enrich_consistency(html: str, enrich: dict) -> list:
    """§1.5 降级一致性:author_page/views_page/reviews 为 null ⟺ 对应子视图/块删除。"""
    v = []
    checks = [
        ("author_page", 'id="sub-author"', "#sub-author 子视图"),
        ("views_page", 'id="sub-views"', "#sub-views 子视图"),
    ]
    for field, present_tok, name in checks:
        val = enrich.get(field)
        present = present_tok in html
        if val is None and present:
            v.append(f"[lint] {field} 为 null 但 {name} 仍在(应连同入口一并删,§1.5)")
        if val is not None and not present:
            v.append(f"[lint] {field} 非 null 但缺 {name}")
    # reviews:null → .reviews 块删
    rv = enrich.get("reviews")
    if rv is None and _has_class(html, "reviews"):
        v.append("[lint] reviews 为 null 但 .reviews 块仍在(应整块删,§1.5)")
    return v


def _check_chain_step(items: list, kind: str, n_rings: int) -> list:
    """chain_step 合法性:None 放行;否则须 int(非 bool)且 ∈[1,5];超出实际环数按越界打回。"""
    v = []
    for it in items or []:
        cs = it.get("chain_step", None)
        if cs is None:
            continue
        if isinstance(cs, bool) or not isinstance(cs, int) or cs < 1 or cs > 5:
            v.append(f"[distill] {kind}.chain_step {cs!r} ∉ [1,5] 或 null(越界)")
        elif n_rings and cs > n_rings:
            v.append(f"[distill] {kind}.chain_step {cs} 越界(action_chain 仅 {n_rings} 环)")
    return v


CERTAINTY_VALUES = ("book_explicit", "cross_book_synthesis", "general_knowledge")


def _check_certainty(items: list, kind: str) -> list:
    """G22(v6.1,仅 stakes=high 激活):decision_rules / core_ideas 每条可执行建议必带
    certainty ∈ {book_explicit, cross_book_synthesis, general_knowledge}。缺失或非枚举即打回。"""
    v = []
    for it in items or []:
        c = it.get("certainty", None)
        if c is None:
            v.append(f"[distill] {kind} 缺 certainty(G22,stakes=high 必产)")
        elif c not in CERTAINTY_VALUES:
            v.append(f"[distill] {kind}.certainty {c!r} ∉ {{book_explicit,cross_book_synthesis,general_knowledge}}(G22)")
    return v


def lint_distill(data: dict) -> list:
    """distill.json 契约门禁(§7 可机拦部分 G7-G22):evidence_level(G7)/ 章标题(G8)/ narrative(G9)/ §5.1 六类 anchor /
    excerpts(G14)/ primary·featured(G15)/ layman_analogy(G10)/ soul_module(G11)/ self_check(G12)/
    action_chain(G13)/ cover_intro(G16)/ detail(G17)/ credibility_verdict(G18)/ core_question(G19)/ chain_steps(G20)/
    hook(G21)/ chain_step 合法性 / certainty(G22,仅 stakes=high 激活)。"""
    v = []
    is_video = data.get("source_type") == "video_series"
    # render_profile(2026-07-12 B-1/B-2):无 profile → active=None = legacy 全 Tier-1(向后兼容,旧书不必重蒸)
    prof = data.get("render_profile")
    active = _resolve_active_gates(prof)

    def gon(g):  # Tier-1 形态门禁是否生效(Tier-0 底线不走此闸,恒校验)
        return active is None or g in active
    nmode = (prof or {}).get("narrative_mode") or "full-800"
    v += _lint_profile_integrity(prof)  # profile 完整性(防逐书篡改绕门禁)
    # G9 字数档:dense-card(考点/知识点卡)300 / 视频 400 / 详实逐章 800
    floor = DENSE_CARD_FLOOR if nmode == "dense-card" else (400 if is_video else 800)
    for ch in data.get("chapters", []) or []:
        no = ch.get("no", "?")
        # G9 narrative 详实度(list/none 档不产 narrative → 关;dense-card 降档)
        if gon("G9"):
            narr_len = len(re.sub(r"\s", "", ch.get("narrative", "") or ""))
            if narr_len < floor:
                v.append(f"[distill] 第{no}章 narrative {narr_len} 字 < {floor}(G9 详实度)")
        # G8 章标题黑名单
        if gon("G8") and is_bad_title(ch.get("title", "") or ""):
            v.append(f"[distill] 第{no}章标题非论点式(G8): {ch.get('title')!r}")
        # G14 excerpts:详实逐章档书籍每章 ≥1(视频/语录/清单档不强求),版权红线 ≤150 与 §5.1 anchor 恒为 Tier-0
        exs = ch.get("excerpts", []) or []
        if not is_video and nmode == "full-800" and len(exs) < 1:
            v.append(f"[distill] 书籍第{no}章 excerpts 缺(G14 每章 ≥1)")
        for ex in exs:
            if len(re.sub(r"\s", "", ex.get("text", "") or "")) > EXCERPT_MAX:
                v.append(f"[distill] 第{no}章 excerpts.text 去空白 >{EXCERPT_MAX} 字(G14 版权红线)")
            if not anchor_ok(ex.get("anchor", "")):
                v.append(f"[distill] 第{no}章 excerpts 缺 anchor(§5.1)")
    # §5.1 六类 anchor:core_ideas / decision_rules / quotes / mental_models.evidence / chapters.excerpts / self_check
    for ci in data.get("core_ideas", []) or []:
        if not anchor_ok(ci.get("anchor", "")):
            v.append("[distill] core_idea 缺 anchor(G2/§5.1)")
        if ci.get("evidence_level") not in ("原文确认", "结构推断", "需复核"):
            v.append(f"[distill] core_idea 缺 evidence_level 或非三值枚举(G7): {ci.get('evidence_level')!r}")
    for dr in data.get("decision_rules", []) or []:
        if not anchor_ok(dr.get("anchor", "")):
            v.append("[distill] decision_rule 缺 anchor(G3/§5.1)")
    for q in data.get("quotes", []) or []:
        if not anchor_ok(q.get("anchor", "")):
            v.append("[distill] quote 缺 anchor(G3/§5.1)")
    for mm in data.get("mental_models", []) or []:
        for ev in mm.get("evidence", []) or []:
            if not anchor_ok(ev):
                v.append("[distill] mental_model.evidence 未内嵌 anchor(G3/§5.1)")
    for sc in data.get("self_check", []) or []:
        if not anchor_ok(sc.get("anchor", "")):
            v.append("[distill] self_check 缺 anchor(§5.1)")
    # G15 primary ∈[1,2] / featured ≤3
    primary_n = sum(1 for ci in (data.get("core_ideas", []) or []) if ci.get("primary") is True)
    if not (1 <= primary_n <= 2):
        v.append(f"[distill] core_ideas primary 数 {primary_n} ∉ [1,2](G15)")
    featured_n = sum(1 for q in (data.get("quotes", []) or []) if q.get("featured") is True)
    if featured_n > 3:
        v.append(f"[distill] quotes featured 数 {featured_n} > 3(G15)")
    # G10 core_ideas[].layman_analogy 全非空
    for ci in data.get("core_ideas", []) or []:
        la = ci.get("layman_analogy")
        if not (la and str(la).strip()):
            v.append("[distill] core_idea 缺 layman_analogy 生活类比(G10)")
    # G11 soul_module 合规
    sm = data.get("soul_module")
    if not isinstance(sm, dict):
        v.append("[distill] 缺 soul_module 书魂模块(G11)")
    else:
        states_n = len(sm.get("states", []) or [])
        if states_n < 2:
            v.append(f"[distill] soul_module.states 数 {states_n} < 2(G11)")
        if not (sm.get("subtitle") and str(sm.get("subtitle")).strip()):
            v.append("[distill] soul_module.subtitle 空(G11)")
        if not (sm.get("title") and str(sm.get("title")).strip()):
            v.append("[distill] soul_module.title 空(G11)")
        stype = sm.get("type")
        if stype not in ("compare", "chain", "curve"):
            v.append(f"[distill] soul_module.type {stype!r} ∉ {{compare,chain,curve}}(G11)")
        if stype == "curve":
            curve = sm.get("curve")
            series = curve.get("series") if isinstance(curve, dict) else None
            if not series:
                v.append("[distill] soul_module type=curve 但 curve.series 缺/空(G11)")
    # G12 self_check 4-8 条 + 每条 q 含「你」
    scs = data.get("self_check", []) or []
    if not (4 <= len(scs) <= 8):
        v.append(f"[distill] self_check 数 {len(scs)} ∉ [4,8](G12)")
    for sc in scs:
        if "你" not in (sc.get("q", "") or ""):
            v.append(f"[distill] self_check.q 非第二人称(不含「你」)(G12): {(sc.get('q', '') or '')[:20]!r}")
    # G13 action_chain 4-5 环 + 每环 label 有效长 ≤12 字;G17 每环 detail 去空白 ≥60 字
    acs = data.get("action_chain", []) or []
    n_rings = len(acs)
    if not (4 <= n_rings <= 5):
        v.append(f"[distill] action_chain 环数 {n_rings} ∉ [4,5](G13)")
    for idx, ac in enumerate(acs, 1):
        lbl = ac.get("label", "") or ""
        if _effective_len(lbl) > 12:
            v.append(f"[distill] action_chain.label 有效长 >12 字(G13): {lbl!r}")
        detail_len = len(re.sub(r"\s", "", ac.get("detail", "") or ""))
        if detail_len < 60:
            v.append(f"[distill] action_chain 第{idx}环 detail {detail_len} 字 < 60(G17 详实度)")
    # G16 cover_intro 存在 + 2-3 句 + 不复用 napkin.one_liner(≥12 字连续片段)
    ci_txt = data.get("cover_intro")
    if not (ci_txt and str(ci_txt).strip()):
        v.append("[distill] 缺 cover_intro 封面简介(G16)")
    else:
        sc_n = _sentence_count(str(ci_txt))
        if not (2 <= sc_n <= 3):
            v.append(f"[distill] cover_intro 句数 {sc_n} ∉ [2,3](G16 按 。！？ 计句)")
        one_liner = ((data.get("napkin") or {}).get("one_liner")) or ""
        if _shares_long_run(str(ci_txt), one_liner):
            v.append(f"[distill] cover_intro 与 napkin.one_liner 存在 ≥{DUP_RUN} 字连续重叠(G16 查重)")
    # 餐巾纸四件套(v4,批次 B-2):formula_read(G4 扩展 a,书/视频必产)+ sketch(G4 扩展 b,可降级)
    napkin = data.get("napkin") or {}
    fr = napkin.get("formula_read")
    if not (fr and str(fr).strip()):
        v.append("[distill] 缺 napkin.formula_read 公式读法(G4 扩展)")
    else:
        frs = str(fr).strip()
        if _effective_len(frs) > FORMULA_READ_MAX:
            v.append(f"[distill] napkin.formula_read 有效长 {_effective_len(frs)} > {FORMULA_READ_MAX} 字(G4 扩展)")
        has_op = any(ch in frs for ch in FR_OPERATORS)
        has_sem = any(w in frs for w in FR_SEMANTIC)
        if not (has_op or has_sem):
            v.append("[distill] napkin.formula_read 未点明运算符语义"
                     "(须含运算符或「乘/加/减/除/归零/缺一/比例/乘积」等语义词)(G4 扩展)")
    sk = napkin.get("sketch")
    if isinstance(sk, dict):  # 可降级:缺失合法,仅在产出时校验结构
        if sk.get("type") not in SKETCH_TYPES:
            v.append(f"[distill] napkin.sketch.type {sk.get('type')!r} ∉ {{cascade,fork,loop}}(G4 扩展)")
        if not (sk.get("caption") and str(sk.get("caption")).strip()):
            v.append("[distill] napkin.sketch.caption 空(G4 扩展)")
        nodes = sk.get("nodes")
        edges = sk.get("edges")
        if not isinstance(nodes, list) or not (6 <= len(nodes) <= 12):
            n_nodes = len(nodes) if isinstance(nodes, list) else "缺"
            v.append(f"[distill] napkin.sketch.nodes 数 {n_nodes} ∉ [6,12](G4 扩展)")
        else:
            for nd in nodes:
                if not (isinstance(nd, dict) and nd.get("id") and str(nd.get("label", "")).strip()):
                    v.append("[distill] napkin.sketch.node 缺 id/label(G4 扩展)")
                    break
        if not isinstance(edges, list) or len(edges) < 1:
            v.append("[distill] napkin.sketch.edges 缺/空(G4 扩展)")
        else:
            for ed in edges:
                if not (isinstance(ed, dict) and ed.get("from") and ed.get("to")):
                    v.append("[distill] napkin.sketch.edge 缺 from/to(G4 扩展)")
                    break
        # 防重画公式凑数:node.label 集合与公式右侧项集合完全相同 → 打回
        if isinstance(nodes, list) and nodes:
            labels = {str(nd.get("label", "")).strip() for nd in nodes if isinstance(nd, dict)}
            labels.discard("")
            rhs = _formula_rhs_terms(napkin.get("formula", ""))
            if rhs and labels == rhs:
                v.append("[distill] napkin.sketch.nodes 的 label 集合与公式右侧项完全相同"
                         "(防重画公式凑数,须展开中间产物等因果层)(G4 扩展)")
    # G18 credibility_verdict 书籍必产(视频可省)
    cv = data.get("credibility_verdict")
    if not is_video and not (cv and str(cv).strip()):
        v.append("[distill] 书籍缺 credibility_verdict 裁决条(G18)")
    # G19 core_question(v4)存在 + ≤40 字疑问句 + 不复用 cover_intro/one_liner(书 / 视频必产)
    cq = data.get("core_question")
    if not (cq and str(cq).strip()):
        v.append("[distill] 缺 core_question 核心问题(G19)")
    else:
        cq_s = str(cq).strip()
        if _effective_len(cq_s) > 40:
            v.append(f"[distill] core_question 有效长 {_effective_len(cq_s)} > 40 字(G19)")
        if not re.search(r"[?？]\s*$", cq_s):
            v.append("[distill] core_question 非疑问句(须以 ? / ? 结尾)(G19)")
        one_liner = ((data.get("napkin") or {}).get("one_liner")) or ""
        cover = data.get("cover_intro") or ""
        if _shares_long_run(cq_s, one_liner):
            v.append(f"[distill] core_question 与 napkin.one_liner 存在 ≥{DUP_RUN} 字连续重叠(G19 查重)")
        if _shares_long_run(cq_s, str(cover)):
            v.append(f"[distill] core_question 与 cover_intro 存在 ≥{DUP_RUN} 字连续重叠(G19 查重)")
    # core_ideas[].pillar(v4)∈ [1,5] 或 null(一级分支 §4.6 定为 3-5,机检上限取 5;牵强留空,禁硬塞)
    for ci in data.get("core_ideas", []) or []:
        p = ci.get("pillar", None)
        if p is None:
            continue
        if isinstance(p, bool) or not isinstance(p, int) or p < 1 or p > 5:
            v.append(f"[distill] core_idea.pillar {p!r} ∉ [1,5] 或 null(v4)")
    # G20 arguments.chain_steps(v4)4-8 步、每步有效长 ≤14 字(书 / 视频必产)
    steps = (data.get("arguments") or {}).get("chain_steps")
    if not isinstance(steps, list) or not (4 <= len(steps) <= 8):
        n_steps = len(steps) if isinstance(steps, list) else "缺"
        v.append(f"[distill] arguments.chain_steps 数 {n_steps} ∉ [4,8](G20)")
    else:
        for st in steps:
            if _effective_len(str(st)) > 14:
                v.append(f"[distill] arguments.chain_steps 某步有效长 >14 字(G20): {str(st)[:16]!r}")
    # G21 chapters[].hook(v4)若产则 ≤20 字(存在性属自查,不拦缺失)
    for ch in data.get("chapters", []) or []:
        hk = ch.get("hook")
        if hk and _effective_len(str(hk)) > 20:
            v.append(f"[distill] 第{ch.get('no', '?')}章 hook 有效长 {_effective_len(str(hk))} > 20 字(G21)")
    # chain_step 合法性(∈[1,5] 或 null,不越界):decision_rules + mental_models
    v += _check_chain_step(data.get("decision_rules", []), "decision_rule", n_rings)
    v += _check_chain_step(data.get("mental_models", []), "mental_model", n_rings)
    # G22(v6.1):高后果书 stakes=high → decision_rules + core_ideas 每条必带 certainty。
    #   独立 stakes 闸:G22 不进 TIER1_GATES(下方变体化过滤据 g∉t1_nums 自动放行=恒保留),只由 stakes 触发;
    #   normal 书不检(certainty 可选)。事实抽检(数字真伪)靠硬门禁②人工,G22 只机拦「有没有标」。
    if data.get("stakes") == "high":
        v += _check_certainty(data.get("decision_rules", []), "decision_rule")
        v += _check_certainty(data.get("core_ideas", []), "core_idea")
    # Tier-1 形态门禁按 render_profile.active_gates 变体化(2026-07-12 B-2):非 legacy 时,滤掉「未激活门禁」的违规。
    #   Tier-0 底线门禁(anchor/G14 版权≤150/G15/chain_step/真封面…)无 (Gxx) 编号或不在 TIER1,恒保留、不受影响。
    #   G17(行动链 detail 详实度)归属 G13;profile 完整性 [profile] 无编号 → 恒保留。active=None(legacy)整段跳过 = 行为不变。
    if active is not None:
        t1_nums = {int(g[1:]) for g in TIER1_GATES}

        def _gnum(msg):
            m = re.search(r"\(G(\d+)", msg)
            return int(m.group(1)) if m else None
        filtered = []
        for msg in v:
            g = _gnum(msg)
            g = 13 if g == 17 else g          # G17 detail 归属 G13
            if g in t1_nums and f"G{g}" not in active:
                continue
            filtered.append(msg)
        v = filtered
    return v


# ================================================================ 作者演变页门禁(独立路径)
def is_author_page(html: str, author_json_flag: bool = False) -> bool:
    """作者演变页识别:传 --author-json / 含内联 #author-data / .author-page|.author-evo 标记 任一即是。"""
    return bool(author_json_flag) or ('id="author-data"' in html) \
        or _has_class(html, "author-page") or _has_class(html, "author-evo")


def _slug_ok(slug) -> bool:
    """深链 slug 格式合法:非空、无空白/斜杠/尖括号/引号、无 .. 目录穿越(不校验目标文件是否存在)。"""
    s = str(slug or "")
    return bool(s) and not SLUG_BAD_RE.search(s) and ".." not in s


def _collect_author_strings(obj, skip_keys, out=None) -> list:
    """递归收集 author.json 里的字符串值,跳过 skip_keys 指向的子树(external 外证等照录豁免)。"""
    if out is None:
        out = []
    if isinstance(obj, dict):
        for k, val in obj.items():
            if k in skip_keys:
                continue
            _collect_author_strings(val, skip_keys, out)
    elif isinstance(obj, list):
        for it in obj:
            _collect_author_strings(it, skip_keys, out)
    elif isinstance(obj, str):
        out.append(obj)
    return out


def _strip_html_comments(s: str) -> str:
    return re.sub(r"<!--.*?-->", "", s, flags=re.S)


def _load_author_json(html: str, author_json_path: str | None):
    """取 author.json:优先 --author-json 文件,否则取内联 #author-data
    (**先剥 HTML 注释**,防骨架注释里写的 `<script id="author-data">` 示例被误命中)。
    返回 (author dict|None, 解析错误列表)。"""
    if author_json_path:
        try:
            return json.loads(Path(author_json_path).read_text(encoding="utf-8")), []
        except Exception as e:
            return None, [f"[author] --author-json 解析失败: {e}"]
    m = AUTHOR_DATA_RE.search(_strip_html_comments(html))
    if not m:
        return None, []
    try:
        return json.loads(m.group(1)), []
    except Exception as e:
        return None, [f"[author] 内联 #author-data JSON 解析失败: {e}"]


def lint_author_html(html: str, author: dict | None) -> list:
    """作者演变页出厂门禁(独立于蒸馏页 REQUIRED_CLASSES;照 author-craft.md §0 铁律):
    4 视图容器齐(时间线/母题/转向/概念图)/ 零外链(仅外证·时间线出处 <a href> 可外链)/ Zero-Hex /
    lang=zh + ≤3MB / 破折号 --(external 外证 blockquote 豁免)/ 深链 slug 格式合法 / 转向 verdict 存在性一致。"""
    v = []
    # 体积 ≤3MB
    if len(html.encode("utf-8")) > SIZE_LIMIT:
        v.append("[author] 体积超 3MB 预算")
    # lang="zh"
    if 'lang="zh"' not in html:
        v.append('[author] html 缺 lang="zh"')
    # 4 视图容器齐(时间线 / 母题 / 转向 / 概念图)
    for cls, name in AUTHOR_VIEW_CLASSES:
        if not _has_class(html, cls):
            v.append(f"[author] 缺 {name}视图容器 .{cls}")
    # 零外链(script/link/img 禁 http(s);外证 external.source / timeline_anchors 出处 <a href> 放行)
    if re.search(r'<script[^>]+src=["\']https?://', html) or re.search(r'<link[^>]+href=["\']https?://', html) \
       or re.search(r'<img[^>]+src=["\']https?://', html):
        v.append("[author] 存在外链资源(script/link/img),违反零 CDN(仅外证/时间线出处 <a href> 可外链)")
    # Zero-Hex:剥 vendor <style> + token 块 + color-mix 内层后,token 块外禁字面 hex
    html_scan = VENDOR_STYLE_RE.sub("", html)
    css = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html_scan, re.S))
    css_no_tokens = _strip_color_mix(TOKEN_BLOCK_RE.sub("", css))
    hexes = HEX_RE.findall(css_no_tokens)
    if hexes:
        v.append(f"[author] token 块外硬编码色 {len(hexes)} 处: {sorted(set(hexes))[:5]}…")
    # 以下门禁需 author.json 数据
    if author is None:
        v.append("[author] 取不到 author.json(未传 --author-json 且无内联 #author-data),数据类门禁跳过")
        return v
    # 深链 slug 格式合法(代表作导航 + 时间线书圆 + 各引用皆走 ../{slug}/{slug}.html)
    for b in author.get("books", []) or []:
        s = b.get("slug")
        if not s:
            v.append("[author] books[] 有条目缺 slug(深链无法生成)")
        elif not _slug_ok(s):
            v.append(f"[author] 书 slug {s!r} 非法(会破坏深链 ../{{slug}}/{{slug}}.html)")
    ref_slugs = []
    for rp in author.get("reading_path", []) or []:
        ref_slugs.append(rp.get("slug"))
    for t in author.get("turns", []) or []:
        for side in ("from", "to"):
            ref_slugs.append((t.get(side) or {}).get("distill_slug"))
    for n in ((author.get("concept_graph") or {}).get("nodes") or []):
        for ap in n.get("appearances", []) or []:
            ref_slugs.append(ap.get("slug"))
    for s in ref_slugs:
        if s and not _slug_ok(s):
            v.append(f"[author] 引用 slug {s!r} 非法(会破坏深链)")
    # 转向 verdict 一致性(存在性/结构性:渲染的转向卡只来自 verdict≠null 的 turn,author-craft §4.3)
    for t in author.get("turns", []) or []:
        verdict = t.get("verdict")
        if not verdict:      # null / '' → 不渲染,跳过
            continue
        tid = t.get("id", "?")
        if verdict not in AUTHOR_VERDICTS:
            v.append(f"[author] 转向 {tid} verdict {verdict!r} ∉ {{confirmed,apparent,refuted}}")
            continue
        if verdict != "refuted":
            frm, to = t.get("from") or {}, t.get("to") or {}
            if not (frm.get("stance") and to.get("stance")):
                v.append(f"[author] 转向 {tid}(verdict={verdict})缺 from/to.stance(前后双列数据不完整)")
        if verdict == "confirmed" and not (t.get("external") or []):
            v.append(f"[author] 转向 {tid} verdict=confirmed 但无 external 外证(叙事动词须有外部原话锚定)")
    # evolution_verdict(可选字段,存在才校验;缺失不算门禁失败,③板块退化不渲染徽章行)
    ev = author.get("evolution_verdict")
    if ev is not None:
        stance = ev.get("stance") if isinstance(ev, dict) else None
        if stance not in EVOLUTION_VERDICT_STANCES:
            v.append(f"[author] evolution_verdict.stance {stance!r} ∉ {EVOLUTION_VERDICT_STANCES}")
        if not (isinstance(ev, dict) and ev.get("headline")):
            v.append("[author] evolution_verdict 缺 headline(结论徽章旁的一句话大字)")
    # 破折号:转述文字禁全角 —/―(external 外证照录豁免,同蒸馏页 blockquote 豁免逻辑)
    n_dash = sum(len(FULLWIDTH_DASH_RE.findall(s))
                 for s in _collect_author_strings(author, AUTHOR_DASH_EXEMPT_KEYS))
    if n_dash:
        v.append(f"[author] 转述文字含全角破折号 —/― {n_dash} 处(应统一 --;外证 external 照录豁免)")
    return v


def author_smoke(path: Path, screenshot: str | None, author: dict | None = None) -> list:
    """作者演变页渲染冒烟:4 视图 SVG/容器出图 + 无 JS 错误 + 概念节点可展开(章码深链 = 静态门禁 slug 格式已管)。
    注(转向段降级一致性,author-craft §4.3/§6):`.turn-card` 只在 author.turns 存在 verdict≠null 的可渲染转向时才应出现;
    深化型作者(turns=[] 或全 null,如稻盛)按契约整段隐藏、无转向卡 —— 故本断言按数据是否有可渲染转向来门控,
    避免把「fixture 恰有 confirmed 转向」误当成所有作者页的硬要求(旧版对 turns=0 作者会误报)。"""
    from playwright.sync_api import sync_playwright
    v, errors = [], []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=2)
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.goto(path.resolve().as_uri())
        pg.wait_for_timeout(900)
        if errors:
            v.append(f"[author渲染] console 错误: {errors[:3]}")
        if not pg.evaluate("() => window.__authorReady === true"):
            v.append("[author渲染] 渲染器未跑完(window.__authorReady 未置真)")
        if pg.locator("#tl-host svg").count() < 1:
            v.append("[author渲染] 时间线未出 SVG(#tl-host 内无 <svg>)")
        if pg.locator("#rb-host svg").count() < 1:
            v.append("[author渲染] 母题 ribbon 未出 SVG(#rb-host 内无 <svg>)")
        if pg.locator("#dag-host svg").count() < 1:
            v.append("[author渲染] 概念图 DAG 未出 SVG(#dag-host 内无 <svg>)")
        has_renderable_turn = any((t or {}).get("verdict") for t in ((author or {}).get("turns") or []))
        if has_renderable_turn and pg.locator(".turn-card").count() < 1:
            v.append("[author渲染] 关键转向未出转向卡(.turn-card;数据有 verdict≠null 的转向却未渲染)")
        node = pg.locator(".dag-node").first
        if node.count():
            node.click()
            pg.wait_for_timeout(200)
            if pg.locator("#dag-panel .dp-concept").count() < 1:
                v.append("[author渲染] 点概念节点后详情面板未展开(.dp-concept 缺)")
        else:
            v.append("[author渲染] 概念图无 .dag-node 节点")
        if screenshot:
            pg.screenshot(path=screenshot, full_page=True)
        b.close()
    return v


def smoke(path: Path, screenshot: str | None) -> list:
    from playwright.sync_api import sync_playwright
    v, errors = [], []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=2)
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.goto(path.resolve().as_uri())
        pg.wait_for_timeout(1200)
        if errors:
            v.append(f"[渲染] console 错误: {errors[:3]}")
        # 五 tab 切换
        tabs = pg.locator(".tab")
        n = tabs.count()
        if n < 5:
            v.append(f"[渲染] tab 数 {n} < 5")
        else:
            tabs.nth(1).click()
            pg.wait_for_timeout(200)
            if "on" not in (tabs.nth(1).get_attribute("class") or ""):
                v.append("[渲染] tab 点击未激活")
        # 脑图(自绘 SVG 深色版):切回全书速览,生成器渲染后应有 <svg> + 达标文字节点 + viewer 脚本 + 零关联箭头元素
        pg.locator('.tab[data-panel="panel-glance"]').click()
        pg.wait_for_timeout(700)
        n_svg = pg.locator("#bd-mindmap svg").count()
        if n_svg < 1:
            v.append("[渲染] 脑图 #bd-mindmap 内无 <svg>(自绘 SVG 生成器未出图)")
        n_text = pg.locator("#bd-mindmap svg text").count()
        if n_text < MIN_SVG_TEXT:
            v.append(f"[渲染] 脑图 SVG 文字节点 {n_text} < {MIN_SVG_TEXT}(生成器未出图或数据过少)")
        # SVG 版去掉所有关联:不应有 mind-elixir 关联箭头/label 残留(真能拦「又把 arrows 画回去」)
        n_arrow = pg.locator('#bd-mindmap .topiclinks, #bd-mindmap [data-type="arrow"]').count()
        if n_arrow > 0:
            v.append(f"[渲染] 脑图仍含关联箭头元素 {n_arrow} 处(SVG 版应只画父子引线,去掉所有关联)")
        # viewer 脚本已跑:生成器暴露 window.__mm 诊断(viewBox viewer 在)
        has_viewer = pg.evaluate("() => !!(window.__mm && typeof window.__mm.fit === 'function' && window.__mm.nodes > 0)")
        if not has_viewer:
            v.append("[渲染] 脑图 viewer 脚本未运行(window.__mm 缺失,viewBox viewer 未初始化)")
        # stage 用 viewBox 缩放(非 transform:scale):mm-stage 的 transform 应为 none
        stage_tf = pg.evaluate("() => { const s = document.querySelector('#bd-mindmap .mm-stage'); return s ? getComputedStyle(s).transform : 'MISSING'; }")
        if stage_tf not in ("none", "matrix(1, 0, 0, 1, 0, 0)"):
            v.append(f"[渲染] 脑图 mm-stage transform={stage_tf!r} 非 none(应走 viewBox 缩放,非 transform:scale)")
        # 章码传送门:点带 hyperLink 的二级节点 a.jump -> location.hash -> 切板块②(逐章精读)+ 展开该章
        jumped = pg.evaluate("""() => {
            const a = document.querySelector('#bd-mindmap svg a.jump[href^="#ch-"]');
            if (!a) return null;
            const href = a.getAttribute('href');
            a.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
            return href;
        }""")
        if jumped:
            pg.wait_for_timeout(400)
            if "on" not in (pg.locator("#panel-full").get_attribute("class") or ""):
                v.append(f"[渲染] 点脑图二级节点({jumped})未跳到 panel-full 逐章精读(章码传送门失效)")
            chm = re.search(r"ch-(\d+)", jumped)
            if chm:
                tgt = pg.locator(f"#ch-{chm.group(1)}")
                if tgt.count() and not tgt.is_visible():
                    v.append(f"[渲染] 点脑图二级节点后 #ch-{chm.group(1)} 未展开(传送门未展章)")
            # 复位手风琴 + hash:避免传送门测试打开的章污染后续 T6 目录态默认收起断言
            pg.evaluate("""() => {
                document.querySelectorAll('.bd-chapter.open').forEach(c => c.classList.remove('open'));
                if (location.hash) history.replaceState(null, '', location.pathname);
            }""")
        else:
            v.append("[渲染] 脑图无带 hyperLink 的二级节点 a.jump(章码传送门无锚)")
        pg.locator('.tab[data-panel="panel-glance"]').click()
        pg.wait_for_timeout(150)
        # 每 panel(①-④)底部 .next-cta 存在
        for pid in ("panel-glance", "panel-full", "panel-judge", "panel-action"):
            if pg.locator(f"#{pid} .next-cta").count() < 1:
                v.append(f"[渲染] {pid} 缺板尾 .next-cta")
        # 核心观点卡展开态:点卡后 .ci-detail 可见(explain/evidence/evlevel)
        pg.locator('.tab[data-panel="panel-glance"]').click()
        pg.wait_for_timeout(150)
        ci = pg.locator(".ci").first
        if ci.count():
            ci.click()
            pg.wait_for_timeout(200)
            det = ci.locator(".ci-detail").first
            if det.count() and not det.is_visible():
                v.append("[渲染] 核心观点卡展开后 .ci-detail 未显示(T8 三件)")
        # ② 目录态(T6 正向断言):panel-full 激活后 .bd-chapter 初始不可见 + 全部展开钮在 + 点 toc 行可展开
        pg.locator('.tab[data-panel="panel-full"]').click()
        pg.wait_for_timeout(250)
        vis0 = pg.eval_on_selector_all(".bd-chapter", "els => els.filter(e => e.offsetParent !== null).length")
        if vis0 != 0:
            v.append(f"[渲染] 目录态默认应收起,panel-full 激活后可见 .bd-chapter 数 {vis0} ≠ 0(T6)")
        exp = pg.locator(".toc-expand[data-toc-toggle]").first
        if not exp.count():
            v.append("[渲染] 缺目录态「全部展开」逃生钮 .toc-expand[data-toc-toggle](T6)")
        elif "全部展开" not in (exp.inner_text() or ""):
            v.append("[渲染] .toc-expand 初始文案非「全部展开」(T6)")
        toc_row = pg.locator(".toc-row").first
        if toc_row.count():
            ch_no = toc_row.get_attribute("data-ch")
            toc_row.click()
            pg.wait_for_timeout(300)
            target = pg.locator(f"#ch-{ch_no}")
            if target.count() and not target.is_visible():
                v.append(f"[渲染] 点目录行后 #ch-{ch_no} 未展开(手风琴失效,T6)")
        else:
            v.append("[渲染] 目录态无 .toc-row 章行")
        # ④ 五环 .chain-detail 直接可见(全可见零点击,IX1/IX2)
        pg.locator('.tab[data-panel="panel-action"]').click()
        pg.wait_for_timeout(250)
        cd = pg.locator(".chain-detail").first
        if not cd.count():
            v.append("[渲染] 缺五环扩写 .chain-detail(④)")
        elif not cd.is_visible():
            v.append("[渲染] .chain-detail 未直接可见(应全可见,不折叠)")
        # 字阶抽查:hero h1 computed font-size ≤48px
        h1 = pg.locator(".hero h1").first
        if h1.count():
            fs = pg.evaluate("el => parseFloat(getComputedStyle(el).fontSize)", h1.element_handle())
            if fs > 48.5:
                v.append(f"[渲染] hero h1 字号 {fs}px > 48px(字阶 T0 上限)")
        else:
            v.append("[渲染] 缺 hero h1 标语")
        # 返回胶囊 + 子视图 hash 路由(可降级:#sub-author 存在时测)
        if pg.locator("#sub-author").count():
            if not pg.locator(".sub-back").count():
                v.append("[渲染] 有子视图但缺返回胶囊 .sub-back")
            author_link = pg.locator('a[href="#sub-author"]').first
            if not author_link.count():
                v.append("[渲染] #sub-author 子视图存在但缺入口链接 a[href=\"#sub-author\"]")
            else:
                author_link.click()
                pg.wait_for_timeout(300)
                if not pg.locator("#sub-author").is_visible():
                    v.append("[渲染] 点作者名后 #sub-author 子视图未显示(hash 路由失效)")
                pg.go_back()
                pg.wait_for_timeout(300)
                if pg.locator("#sub-author").is_visible():
                    v.append("[渲染] 浏览器后退后 #sub-author 子视图未关闭")
        # .src-note 常显(computed display ≠ none)
        sn = pg.locator(".src-note").first
        if sn.count():
            if sn.evaluate("el => getComputedStyle(el).display") == "none":
                v.append("[渲染] .src-note 出处被隐藏(应随文常显,display≠none)")
        else:
            v.append("[渲染] 页面无 .src-note 常显出处")
        # 主题切换(竖列弹层):先点触发按钮开弹层、再点某主题项;挑与当前主题不同且有具名 token 块的第一颗
        if pg.locator("[data-theme-pick]").count():
            target = pg.evaluate("""() => {
                const cur = document.body.dataset.theme || '';
                const named = new Set();
                for (const sh of document.styleSheets) {
                    try {
                        for (const r of sh.cssRules) {
                            const m = r.selectorText && r.selectorText.match(/body\\[data-theme="?([^"\\]]+)"?\\]/);
                            if (m) named.add(m[1]);
                        }
                    } catch (e) {}
                }
                const b = [...document.querySelectorAll('[data-theme-pick]')]
                    .find(x => x.dataset.themePick !== cur && named.has(x.dataset.themePick));
                return b ? b.dataset.themePick : null;
            }""")
            if not target:
                v.append("[渲染] 找不到与当前主题不同且有 token 块的 swatch,主题切换不可验")
            else:
                trigger = pg.locator(".theme-picker .tp-trigger")
                if not trigger.count():
                    v.append("[渲染] 主题切换器缺 .tp-trigger 触发按钮")
                else:
                    trigger.click()
                    pg.wait_for_timeout(200)
                    item = pg.locator(f'[data-theme-pick="{target}"]').first
                    if not item.is_visible():
                        v.append("[渲染] 点触发按钮后主题弹层未展开(主题项不可见)")
                    before = pg.evaluate("getComputedStyle(document.body).backgroundColor")
                    item.click()
                    pg.wait_for_timeout(200)
                    after = pg.evaluate("getComputedStyle(document.body).backgroundColor")
                    if before == after:
                        v.append(f"[渲染] 切主题 {target} 后 body 背景未变化")
        if screenshot:
            pg.screenshot(path=screenshot, full_page=True)
        b.close()
    return v


def main():
    ap = argparse.ArgumentParser(description="蒸馏页出厂验证 v3:静态 lint + 契约门禁 + Playwright 渲染冒烟")
    ap.add_argument("page")
    ap.add_argument("--distill", help="distill.json 路径:传入则追加契约门禁(G8-G18)+ 渲染侧查重")
    ap.add_argument("--enrich", help="enrich.json 路径:传入则校验降级一致性;缺省自动探测同目录 enrich.json")
    ap.add_argument("--author-json", dest="author_json",
                    help="author.json 路径:传入即按作者演变页门禁校验;缺省时若页面含内联 #author-data 自动识别")
    ap.add_argument("--screenshot")
    ap.add_argument("--skip-interact", action="store_true")
    a = ap.parse_args()
    html = Path(a.page).read_text(encoding="utf-8")
    # 作者演变页(结构不同)走独立门禁,不套蒸馏页 REQUIRED_CLASSES
    if is_author_page(html, a.author_json):
        author, perr = _load_author_json(html, a.author_json)
        v = perr + lint_author_html(html, author)
        if not a.skip_interact:
            v += author_smoke(Path(a.page), a.screenshot, author)
        print("\n".join(v) if v else "全部通过")
        return 1 if v else 0
    # 蒸馏页(默认路径)
    distill = json.loads(Path(a.distill).read_text(encoding="utf-8")) if a.distill else None
    enrich = None
    if a.enrich:
        enrich = json.loads(Path(a.enrich).read_text(encoding="utf-8"))
    else:
        sib = Path(a.page).parent / "enrich.json"
        if sib.exists():
            enrich = json.loads(sib.read_text(encoding="utf-8"))
    v = lint_html(html, distill, enrich)
    if not a.skip_interact:
        v += smoke(Path(a.page), a.screenshot)
    print("\n".join(v) if v else "全部通过")
    return 1 if v else 0


if __name__ == "__main__":
    sys.exit(main())

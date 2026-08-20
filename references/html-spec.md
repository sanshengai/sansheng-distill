# 页面生成规范 v3.1 -- Step6 单文件 HTML 填槽手册(sansheng-distill)

> **执行手册,不是理论文**。管线跑到 Step6 时 agent 逐节照做:复制 `templates/page-skeleton.html`,把 `distill.json`(v3)/ `enrich.json`(v3)的字段逐槽位填进去,产出一张能过 `verify_page.py` 的单文件 HTML。
> 核心理念(承 method.md):知识档案是主对象,**HTML 是投影** -- 本步只做「把结构化知识摆进既有槽位」,**不设计新结构、不自创模块**。设计层(token / signature / 排版 craft)见 `design-craft.md`;token 值与 7 主题见 `brand-tokens.md`。
> **v3 页型 = 浏览型「5 板块 · 按读者逻辑链」**(2026-07-04 sandy 反馈重构,替换 v2 五段漏斗):读者动线「全局 → 细节 → 反思 → 循环 → 延伸」落成 5 个 tab 板块,每板块内部按「先结论后论证、先立后破」自上而下排。板块② 逐章精读改**目录态**(默认收起 + 手风琴多开);头部走**纸底 + 森林绿粗色带刊头**(banner v3.2,原案 A 墨底反白已废,§2.3.1);字号收进 **6 级字阶**;金句、概念各归**唯一集中归宿**;子视图从 3 张减到 **2 张**(作者页 + 观点对照页,同类书内联板块⑤)。
> 本规范里写的每一个 class / id **都是 T5 骨架(page-skeleton.html)的对齐契约**,与实施计划 Task 5 接口段逐字一致;T5 照此建骨架、T6(verify_page.py)照此建门禁。填槽时不得漂移。
> 全文破折号一律 `--`;门禁全部给可判定标准(数字 / 枚举 / 命令),不用「酌情」「适当」。

---

## 0. 路径与变量约定(全文只定义一次)

| 占位符 | 展开为 |
|---|---|
| `$SKILL` | 本 skill 目录(安装后为 `~/.claude/skills/sansheng-distill`) |
| `$DATA` | 书数据根目录,由环境变量 `DISTILL_DATA_DIR` 指定(默认 `./distill-data`) |
| `{书目录}` | 本书数据目录,**纯 `{slug}`**(如 `pei-haizi-zhongshen-chengzhang`);不含书名,避免中文目录名 |
| 骨架 | `$SKILL\templates\page-skeleton.html` |
| 本书产物页 | `$DATA\{书目录}\{slug}.html` |
| distill / enrich | `$DATA\{书目录}\distill.json` / `enrich.json` |

下文命令里的占位符直接替换成实值再执行。

---

## 1. 区块规格(5 板块浏览型 + 2 张子视图)

> 骨架 `<main data-book-slug="…">` 内按板块顺序排布,每区块用成对注释 `<!-- SLOT:XXX -->` / `<!-- /SLOT:XXX -->` 包起,块根元素带对应**签名 class**(下表「根元素」列)。**填槽 = 只改注释对内部的内容,不动注释、不动签名 class、不动 SLOT 结构。**
> 区块的身份由**签名 class** 认(T5/T6 契约单一来源),不再用 v2 的 `data-module="Mxx"` 编号。数据来源列的字段名与 `method.md`(distill.json schema §6)、`enrich.md`(enrich.json schema §1)逐字对应。
> **v3 相对 v2 的结构性变更(清除 v2 残留矛盾)**:① 五 tab 由「漏斗」改「读者逻辑链」5 板块,新增独立 `#panel-extend`(延伸阅读),原 `panel-judge` 拆出延伸;② 板块② 章节由「默认全展开」改「**目录态默认收起 + 手风琴**」(T6 反转,见 §2);③ **金句唯一集中归宿 = ② 金句墙 `.quote-wall`**,废除 v2 的首屏金句条 `FQ` 与章内行内金句 `.quote-inline`(章内只留 `excerpts`);④ **概念唯一归宿 = ② 概念筹码条 `.concept-chips`**;⑤ 核心观点卡新增**展开态**渲 `explain + evidence + evidence_level`;⑥ 头部去掉 `.lede` 与 `aside.thesis`,`arguments.chain` 移到板块③ 立论复述;⑦ 同类书子视图删除、内容内联板块⑤。v2 的「显示出处」`#srcToggle` 开关早已废(出处 `.src-note` 随文常显),v3 继续无此开关。

### 1.1 五 tab 分组(与骨架 `nav.tabs#bd-tabs` 一致)

5 个 tab,`button.tab[data-panel]` → `section.panel[id]`。tab 文案 = **A 套名词式主名** + **B 套口语副题**,渲染成「A -- B」(如「批判与评价 -- 别急着全信」),两套命名都不浪费。

| 顺序 | tab 文案(A -- B) | `data-panel` / panel id | 读者此刻的问题 | 收纳板块 |
|---|---|---|---|---|
| ① | **全书速览 -- 先看全貌** | `panel-glance` | 这本书到底说了什么 | 板块①(§1.2.1) |
| ② | **逐章精读 -- 一章一章读** | `panel-full` | 具体怎么论证的,故事和证据呢 | 板块②(§1.2.2) |
| ③ | **批判与评价 -- 别急着全信** | `panel-judge` | 该信几分,谁在反对 | 板块③(§1.2.3) |
| ④ | **行动清单 -- 读完这么用** | `panel-action` | 明天遇到事怎么做,做完怎么查自己 | 板块④(§1.2.4) |
| ⑤ | **延伸阅读 -- 接着读什么** | `panel-extend` | 下一本读什么 | 板块⑤(§1.2.5) |

- **tab 文案硬契约**(verify 机拦):A 套主名固定 `全书速览 / 逐章精读 / 批判与评价 / 行动清单 / 延伸阅读`;panel id 固定 `panel-glance / panel-full / panel-judge / panel-action / panel-extend`。禁用 v2 黑话主名(`一眼全书 / 书魂 / 该信几分 / 全书详实`)。B 套副题按上表,允许换字但必须 ≤6 字口语句、不写观点。
- **tabs 之外的固定件**:头部两层(`header.cb-banner` + `section.hero`,§1.2.0)居页首;`footer.footer` 与主题切换器 `.theme-picker`(右下角浮钮,`bottom:20px`,🎨 图标 + 弹层)居页尾;**2** 个子视图 `.subpage`(#sub-author / #sub-views)在 `</main>` 前、panel 之外(全屏覆盖,默认 `hidden`)。
- **默认导航形态(决策 D4=A;v3.1 去导读条)**:保留 5-tab(sticky)+ 每板块底部固定一枚「下一步 →」CTA(`.next-cta`)。**头部导读条 `.reading-guide` 已移除**(与 sticky `nav.tabs` 重复列同一批 5 板块,徒增一排),导航唯一入口 = 顶部 sticky `nav.tabs`;想被带着走的读者从头 CTA 一路点到底。**点 tab / CTA / 章行后,JS(`scrollPanelTop` / `scroll-margin-top:var(--tab-h)`)把目标顶部落到悬浮 tab 栏正下方**(§4)。

### 1.2 区块规格表(5 板块内部区块,照方案 §3-§8 逐块)

> 每板块内部**顺序固定**(读者逻辑链的核心兑现),填槽不得重排。除非注明「可降级」,均为**必含**。各板块 ①-④ 底部收一枚 `.next-cta`(下一步指向下一板块);板块⑤ 末尾改用单向「指路小字」(见 §1.2.5)。

#### 1.2.0 头部两层(tabs 外·页首,`.cb-banner` + `.hero`;v3.1 去导读条)

| 层 | 根元素(签名 class) | 数据来源(字段) | DOM 结构要点 | 降级 |
|---|---|---|---|---|
| **层1 刊头** | `<header class="cb-banner">` | distill:`title` / `author` / `book_type`;enrich:`author_page.name` | 纸底 + 森林绿粗色带(§2.3.1):`img.cb-cover`=真封面(书籍须 `data:image`,禁外链;视频用系列封面);`.cb-meta` 内 `.cb-kicker`=书系定位短语(book_type + 领域拟)/ `.cb-title`={书名}/ `.cb-author` = `.cb-author-lead`「作者 ·」+ `<a class="cb-author-link" href="#sub-author">{作者}</a>`(**醒目胶囊:金描边 + 金调底 + 下划线 + hover 位移,让「作者名即入口」可发现**)+ `.cb-author-hint`「查看作者档案 →」小字备注;左上返回件不在此(仅子视图有) | 必含 |
| **层2 封面简介** | `<p class="cb-intro">`(在 `.cb-meta` 内) | distill:`cover_intro` | 2-3 句 / 3-4 行封面简介,关键词用 `<strong>`(金下划线,靠 `--gold` 不靠字色);**只讲内容、禁比喻、禁复用 `napkin.one_liner`**(见 §2.2 文案分工) | `cover_intro` 缺 → 该行删(不降级整页,但书籍应产,见门禁) |
| **层3 hero** | `<section class="hero">` | distill:`core_question`(eyebrow)+ hero 标语构建期拟(h1) | `.eyebrow`=**核心问题**(渲 `core_question`,v4;与 h1 标语成问答配对)+ `<h1>`=巨型标语(**降级保留、字阶 T0 ≤48px**,§2.3.2);**删掉 v2 的 `.lede` 段与 `aside.thesis` 总论框**(F4 重复源)。**`.reading-guide` 导读条 v3.1 移除**(与 sticky `nav.tabs` 重复列同批 5 板块) | 必含 |

- **`.eyebrow` = `core_question`(v4,Q1-1)**:hero 副题小字槽位由 v3.1 的「作者 · 领域拟语」(与刊头作者信息冗余)改渲 distill 顶层 `core_question`(一句疑问句 ≤40 字),与下方 `<h1>` 标语构成**问答配对**(问「为什么父母明明很爱孩子,却把孩子越养越糟?」→ 答「养育是培育一片森林」)。零新增区块;餐巾纸不重复渲染核心问题(防同板块双曝光,问题归 hero、答案归餐巾纸)。禁复用 `cover_intro`/`napkin.one_liner`(§2.2 查重,G19)。
- **hero 标语来源**:全书中心比喻 / 立场一句,构建期从 `soul_module.title` 或全书最强钩子句提炼,**非独立 schema 字段**;只此一句、不带解释、字阶降到 T0(治 F4)。
- **导航唯一入口 = sticky `nav.tabs`**:v3.1 起头部不再有导读条(`.reading-guide` 已废),进门看到刊头 + hero,5 板块承诺由悬浮 tab 承担,不再重复列一排。
- **演变入口卡 `.author-entry`(SLOT:AUTHOR-ENTRY,`.cb-banner` 之后 · `.hero` 之前)**:该书作者若已蒸 **≥2 部**(存在 `authors/{author_slug}/author.json`),在刊头与 hero 之间渲一张入口卡 -- 文案「这是 {作者} 的第 {K}/{N} 部蒸馏 · {books[].role_in_evolution} → 查看思想演变全景」,`href=../authors/{author_slug}/author.html`(StepA 聚合产物,见 `author-craft.md §7`)。**降级(硬)**:该作者 <2 部已蒸 或无 author.json → 生成时把整个 SLOT(含注释对)整段删,单书页照常。

#### 1.2.1 板块① 全书速览(`#panel-glance`,内部顺序 1→6 固定)

| 序 | 区块 · 根元素 | 数据来源(字段) | DOM 结构要点 | 降级 |
|---|---|---|---|---|
| 1 | **餐巾纸(四件套)** `<div class="note bd-napkin" data-source>` | distill:`napkin.formula` + **`napkin.formula_read`**(v4)+ `napkin.one_liner` | 自上而下四段:`.formula`=公式(**必含 `=`/`≈`/`∝` 运算关系**,method §7.3)→ **`<p class="formula-read">`=公式读法**(v4,Q4-1:`.formula` 正下方,小一号,**前缀「怎么读:」**,渲 `napkin.formula_read` -- 点明为什么是这个运算符/归零边界)→ `<p>`=`napkin.one_liner`(独立成段)。整块带 `data-source`(全书收束章)。**`napkin.one_liner` 全页唯一出现处**(不再进头部,治 F5);核心问题不在此(归 hero eyebrow) | 必含(formula_read 缺→该行删,但书/视频应产,见 method G4 扩展) |
| 2 | **因果骨架草图** `<div class="napkin-sketch">`(内 `#bd-sketch` + `<script id="bd-sketch-data">`) | distill:`napkin.sketch`(`type`/`caption`/`nodes[]`/`edges[]`,v4,Q4-2) | 位置**固定在餐巾纸之后、脑图之前**(承四件套第四件)。`<script type="application/json" id="bd-sketch-data">` 内 sketch JSON + `<div id="bd-sketch">`(空,`initSketch()` 脚本层渲**内联 SVG 纵向因果流**)+ `.sk-caption`=`caption`。**全书因果骨架「一眼图」**:≤12 节点、静态、**零交互、一屏收完**(不缩放/不全屏);视觉走脑图统一「直角经典」语言(直角肘形引线、经典描边节点),但因嵌浅色纸底区用**浅色配色**(--paper 底 / --green 引线与描边 / --ink 文字 / 中间产物节点 --gold 描边),不套脑图深墨绿画布。SVG 生成器读 `#bd-sketch-data` 通用出图,禁写死某本书。规格见 §1.2.1a | **可降级**:`napkin.sketch` 缺 / 空 → 整块删(蒸不出干净骨架允许省略,method G4 扩展 b) |
| 3 | **全书脑图** `<div class="bd-mindmap-wrap">` | distill:`chapters[]` + `core_ideas` + `mental_models`/`concepts`/`decision_rules` + `enrich` | 位置**固定在因果骨架草图之下、核心观点之前**(F5)。`<script type="application/json" id="bd-mindmap-data">` 内**充实知识树 JSON**(三键 `nodeData`/`arrows`/`summaries`,规范见 §5;二级核心观点带 `hyperLink:'#ch-N'` + `expanded:false` 默认折叠,三级/📖/📚 点开才露)+ `<div id="bd-mindmap">`(空,脚本层渲染)+ `.mm-hint`=动作指令式说明「点任一分支,直达该章精读」;两个 id 勿改。点二级节点 → 切②、展开目标章、滚动、章头高亮 2 秒(章码传送门,§4.交互);关联箭头默认极淡、hover 节点才高亮(§5.2 克制) | 必含 |
| 4 | **核心观点卡** `<div class="bd-coreideas">` | distill:`core_ideas[]`(`idea` / `layman_analogy` / `primary` / `pillar` / **`explain` / `evidence` / `evidence_level`** / `anchor`) | `.section-title` + `.section-lead` + **按 `pillar` 分组**(v4,Q1-3)的 `.ci-group`:每组 `.ci-group-head`=脑图一级分支名(如「① 问题的根源 · 第1-2章」)+ 组内 `.ci-list`(2-4 个 `<article class="ci">`);`pillar===null` 的卡入末组 `.ci-group` 组头「贯穿全书」。**默认态**露 `.ci-idea`=`idea`(加粗)+ `.ci-analogy`=`layman_analogy`;`primary===true` 的 1-2 条加 `ci-primary`(跨列放大)。**展开态(点卡)必渲三件**(硬约束 3,T8):`.ci-explain`=`explain` + `.ci-evidence`=`evidence` + `.ci-evlevel`=`evidence_level` 徽标(可见前缀固定「原书依据/转述状态:」,三档色点:原文确认 / 结构推断 / 需复核,`data-level` 驱动 token 色)+ 章码传送门「出自第 N 章 →」(`<a href="#ch-N">`)。**不得写「证据强度」**--该徽标只表示转述忠实度,心理学科学有效性在③ `.psych-evidence`。每卡带 `data-source`=`anchor`。**书魂查重(v4,Q1-4)**:某条 core_idea 若与 `soul_module` 同源(同一反直觉主张),该条**不标 primary**、渲普通卡,卡尾加 `<a class="ci-portal" href="#soul-…">完整可视化见本板块结尾 ↓</a>` 页内锚点(锚点指向本板块① `.soul-block`) | 必含 |
| 5 | **两种养法对照(收尾)** `<div class="soul-block" data-source>`(原「书魂」) | distill:`soul_module`(`title` / `subtitle` / `intro` / `type` / `states` / `curve`) | 板块① 的**收官**(soul 并入①,不再独立 tab,决策 D9)。按 `type` **三选一**(填页删掉不用的两型模板):必渲 `.soul-title`=`title`(自解释论点句)+ `.soul-subtitle`=`subtitle`(非空,G11)+ `.soul-intro`=`intro`(点反直觉)。compare→`.soul-grid`(2-3 列 `<article class="soul-state">`,每态 h4 + p + ul;行级 hover 联动同行);chain→`.soul-chain`(`.soul-link` 内 `.sl-no` + h4 + p,`.soul-arrow` 分隔);curve→`.soul-curve` 内 `<svg class="soul-curve-svg">`(每 `series` 一根 `<polyline class="sc-line">`,stroke 走 token)+ `.soul-grid` states 并排。**标题用 soul_module 自带 title/subtitle,不出现「书魂」二字** | 必含 |
| 6 | **板尾 CTA** `<a class="next-cta" data-panel="panel-full">` | 静态 | 「下一步:进入逐章精读 →」,点击切 tab 到 `panel-full` | 必含 |

#### 1.2.1a 因果骨架草图 sketch SVG 规格(v4,Q4-2)+ 三图分工

**三图分工(立法,防重复建设)**:①`.napkin-sketch` sketch = **全书因果骨架「一眼图」**(≤12 节点、静态、一屏、零交互,讲「全书因果怎么串」);①`.bd-mindmap-wrap` 脑图 = **探索型全树**(45-75 节点、可缩放 / 全屏,讲「全书知识怎么铺」,§5);①`.soul-block` 书魂 = **单点反直觉主张**(讲「一个最反直觉的点」,§1.2.1 表 序 5)。三者岗位不重叠、内容不重画。

**sketch 数据契约(`#bd-sketch-data`)**:一段 JSON = `napkin.sketch = {type, caption, nodes[], edges[]}`(schema 见 method §3 餐巾纸压缩)。`type∈{cascade,fork,loop}`;`nodes[]` 6-12 个 `{id, label, note?, mid?}`(`mid:true` = 中间产物,--gold 描边);`edges[]` `{from, to, label}`。脚本层 `initSketch()` 读它 → 纵向分层布局(按边方向做最长路径分层,源节点在顶、逐层向下)→ 生成内联 `<svg>` 挂到 `#bd-sketch`。**nodeData 之外零硬编码,换书换数据即出图(通用生成器)**。

**渲染规格(直角经典 · 浅色 · 静态一屏)**:

- **节点**:圆角矩形 `.sk-node`(`fill:var(--paper)`、`stroke:var(--green)`)+ 居中文字 `.sk-label`(`fill:var(--ink)`);`mid:true` 节点加类 `.sk-mid`(`stroke:var(--gold)` 区分中间产物)。节点宽随 label 字数自适应,保证文字不溢出。
- **引线**:父→子 **直角肘形折线** `.sk-line`(`fill:none;stroke:var(--green);shape-rendering:crispEdges`)-- **禁贝塞尔曲线**;源节点底缘出竖段 → 横段 → 落到目标节点顶缘,汇流(多入一)时多条肘线收进同一顶点。可选小箭头 `.sk-arrow`(`fill:var(--green)`)标向下因果方向。
- **边标签**:`.sk-elabel`(`fill:var(--ink-soft)`,小字)渲非空 `edge.label`,置于肘线拐点旁。
- **零 hex**:所有颜色走 CSS 类 + `var(--*)`;SVG 生成器只设几何(坐标 / points)与 class + 文本,**不设内联 hex 颜色**(JS 内 hex 仅 fallback,`<script>` 不入门禁)。
- **静态**:`<svg viewBox width="100%">` 随容器缩放即可,**不做缩放 / 拖动 / 全屏 viewer**(与脑图区分:sketch 是一眼图,脑图才是可探索全树)。
- **降级**:`initSketch()` 若读不到数据或 `nodes` < 2 → 隐藏 `.napkin-sketch` 整块(填页时数据缺则连 SLOT 一并删)。
- **布局自查**:节点若重叠 / 拥挤,调层间距 / 节点间距到不重叠、一屏可读再交(冒烟目测)。

#### 1.2.2 板块② 逐章精读(`#panel-full`,目录态,内部顺序 1→4 固定)

| 序 | 区块 · 根元素 | 数据来源(字段) | DOM 结构要点 | 降级 |
|---|---|---|---|---|
| 1 | **概念筹码条(本书关键词)** `<div class="concept-chips">` | distill:`concepts[]`(`concept` / `one_liner` / `common_misread` / `stance`) | **概念唯一归宿**(J2 修补,决策 D10)。`.section-title`「本书关键词」+ 一行 N 枚 `<button class="cc-chip" data-concept-idx>`(chip 文字=`concept`);点 chip 弹小卡 `.cc-pop`(`one_liner` + `common_misread` 常见误读 + `stance`),同时目录里含该概念的章行高亮。**误读角标(v4,Q2-2)**:`common_misread` 非空的 chip 加类 `cc-has-mis`,CSS `::after` 在面上右上角出小角标「≠」(token 色,`title="这个词常被理解错"`),把「点进去有误读纠偏」的诱因摆到面上;弹卡内容不变。名实一致,不叫黑话 | **可降级**:`concepts` 空 → 整块删 |
| 2 | **章目录(目录态)** `<div class="chapter-toc">` | distill:`chapters[]`(`no` / `title` / `summary` / `hook`);字数派生 | 总览头 `.toc-head`:「全书 N 章 · 详实转述约 X 万字 · 通读约 M 分钟」+ `.toc-progress`=「已读 0/N」(纯视觉,内存态,无存储)+ `<button class="toc-expand" data-toc-toggle>全部展开</button>`(再点变「全部收起」,**逃生门,必存在**)。其下 `.toc-list` 每行 `<button class="toc-row" data-ch="N">`=章号圆标 + **论点式章名**(`title`,最强资产)+ `summary` 一句(灰)+ **`hook` 悬念钩子**(v4,Q5-5:`.toc-hook` 强调色短句,取该章招牌案例的具象意象,≤20 字;`hook` 缺则省)+ 约 N 分钟角标 + 展开箭头。**收起行 = 结论(标题)+ 概览(摘要)+ 钩子(hook)三层**,扫完 N 行 = 拼出全书骨架 | 必含 |
| 3 | **手风琴章节** `<div class="bd-chapters">` 内 N 个 `<section class="bd-chapter" id="ch-N">` | distill:`chapters[]`(`title` / `narrative` / `excerpts` / `anchor`) | **目录态默认收起、点击手风琴展开、允许多章同开**(T6,与目录行 `data-ch` 联动)。展开态每章顺序固定:`<h3>`=论点式标题 → `narrative` 多段 `<p>`(书 800-1500 字/章)→ 每 3-4 段插 `<blockquote class="excerpt" data-source>`(原文 ≤150 字,内含 `<span class="src-note">` 出处,打破字墙)→ 块尾 `.ch-actions` 三键「收起 \| 回目录 \| 继续读第 N+1 章 →」(连读钮=循环动线一环)。每 `<section>` 带 `data-source`=`anchor`;`id="ch-N"` 与脑图 / 传送门锚点一致。**章内不再有行内金句 `.quote-inline` 或独立金句块**(金句全归④金句墙) | 必含 |
| 4 | **全书金句墙** `<div class="quote-wall">` | distill:`quotes[]` **全量**(`text` / `note` / `featured`) | **金句唯一集中归宿**(决策 D3,T7)。`.section-title`「全书金句墙」+ 每条 `<figure class="qw-card" data-source>` 内 `<blockquote>`=`text`(原文照录不改写)+ `<figcaption>`=`note`(编辑点评)+「出自第 N 章 →」传送门(`<a href="#ch-N">`)。`featured===true` 的 ≤3 条可视觉加重(`qw-featured`),但**仍在墙内、不另设首屏金句条**。金句墙兼当目录态收起后的托底肉 | 必含(书) |
| 5 | **板尾 CTA** `<a class="next-cta" data-panel="panel-judge">` | 静态 | 「下一步:看看该信几分 →」→ `panel-judge` | 必含 |

#### 1.2.3 板块③ 批判与评价(`#panel-judge`,自上而下「先立后破、由内到外」,顺序 1→8 固定)

| 序 | 区块 · 根元素 | 数据来源(字段) | DOM 结构要点 | 降级 |
|---|---|---|---|---|
| 1 | **开场裁决条** `<div class="verdict-bar">` | distill:`credibility_verdict`;enrich:`reviews.rating`(豆瓣分) | 10 秒出结论。`.vb-score`=豆瓣评分大数字(取 `reviews.rating`,如「7.7」)+ `.vb-text`=`credibility_verdict`(2-3 句总裁决:哪些结论最硬 / 哪些要打折) | `credibility_verdict` 缺 → 裁决条只留分;分与文均无 → 整块删 |
| 2 | **立论复述** `<div class="arg-restate" data-source>` | distill:`arguments.chain` + `arguments.chain_steps[]` | 副题「反驳之前,先复述」+ **论证链胶囊(v4,Q4-7)**:散文段**之上**渲一条 `<ol class="arg-steps">` step 胶囊链(N 个 `<li class="arg-step">`=`chain_steps[i]`,横向 `arg-arrow` 箭头相连,窄屏纵排,5 秒可扫)+ 其下 `<p>`=`arguments.chain`(作者完整论证一段,散文保留作展开解释,引导块样式)。**arguments.chain 唯一归宿在此**(从 v2 头部 thesis 移来) | 必含 |
| 3 | **书里自带的矛盾** `<div class="tensions">` 内 `.grid` | distill:`tensions[]`(`a` / `b` / `note`,≥2 对) | `.zone-title`「内在张力」+ 每张力窄行 `<article class="tn-row" data-source>`=`{a} ⟷ {b}`(A⇄B 对撞,与① soul 宽两栏刻意区分),点行展开 `note` 仲裁 | 必含 |
| 4 | **批判四区** `<div class="crit-quad">` | distill:`critique`(`unproven_assumptions` / `blind_spots` / `era_limits` / `strongest_objection`)+ `arguments.hidden_assumptions` / `counter_examples` | **2×2 四色分区,全部可见不藏**,各带 `.zone-title` + 独立底色(走 token):① **没证明的前提**=`unproven_assumptions` + `arguments.hidden_assumptions` 合并渲染(同质);② **作者盲点**=`blind_spots`;③ **时代局限**=`era_limits`(v2 浪费字段,独立渲染);④ **最强反对**=`strongest_objection` 单卡压轴 + `counter_examples` 附于其下(非稻草人)。每区条目带 `data-source`,可回②章 | 必含 |
| 5 | **心理学科学证据** `<div class="psych-evidence">` | distill:`domain_profile` + `core_ideas/decision_rules[].claim_id`;enrich:`evidence_page.claims` | 仅 psychology 渲染。每项 `<article class="pe-claim" data-claim-id="…">` 固定三栏:`.pe-book`「原书怎么说」(取对应原书主张 + claim_type)、`.pe-research`「外部研究怎么说」(status + best_evidence + replication + sources)、`.pe-boundary`「适用边界与风险」(scope)。`.pe-boundary` 必须逐项完整呈现 population/context/所有非空 limits/risks；`.pe-research` 中**可见且有文字**的 http(s) 链接 URL 集合须与该 claim 的 `sources[].url` 精确一致(`not_testable` 可为空),不得少链、偷加或藏链。G24 还要求 DOM 的 data-claim-id 集合与 distill claim_id 完全一致 | **条件必含**:非心理学整块删;心理学书缺/空即失败,不可降级 |
| 6 | **别人怎么评** `<div class="reviews">` | enrich:`reviews`(`items[]`,`stance` 正 / 反) | `.zone-title` + **正反两列**引文墙:每条 `.review-item` 首个 `<span class="stance">`(反向加 `neg`)+ 末尾 `<a class="r-src" rel="noopener">`;**正反都要有**(全好评=信源可疑),保持原始比例、不做柱状汇总 | **可降级**:`reviews===null` → 整块删 |
| 7 | **观点对照子页入口** `<a class="views-entry sub-entry" href="#sub-views">` | enrich:`views_page`(`topics[].viewpoint`) | 大入口卡,卡面直接列 **4 议题 viewpoint 一句话**(目录即承诺,读者知道点进去有什么)+「进入观点对照 →」。子页排版沿用 v2(正反双栏带学术来源,§1.3) | **可降级**:`views_page===null` → 入口卡 + 子视图一并删 |
| 8 | **板尾 CTA** `<a class="next-cta" data-panel="panel-action">` | 静态 | 「下一步:读完这么用 →」→ `panel-action` | 必含 |

#### 1.2.4 板块④ 行动清单(`#panel-action`,「行动主线当骨架,规则/模型挂上去」,顺序 1→5 固定)

| 序 | 区块 · 根元素 | 数据来源(字段) | DOM 结构要点 | 降级 |
|---|---|---|---|---|
| 1 | **行动路线图** `<div class="chain" data-chain>` | distill:`action_chain[]`(`label` / `explain` / **`detail`**,4-5 环) | **竖向步骤条,全部可见零点击**(治 F7)。`.chain-steps` 内 N 个 `<div class="chain-step" data-idx>`=`.cs-no` 序号 + `label`(大字)+ `.chain-explain`=`explain`(直接显示)+ `<div class="chain-detail" data-source>`=`detail`(80-150 字扩写段,直接显示,治「薄」)+ 徽标 `.cs-badge`「N 条相关做法」。点某环 → 平滑滚到下方该环规则分组并高亮。**第⑤环→第①环画回环虚线**(`.chain-loop`,SVG/CSS 虚线,把 F9「循环」画在界面上) | 必含 |
| 2 | **情境决策卡** `<div class="rules">` | distill:`decision_rules[]`(`when` / `do` / `because` / `anchor` / `chain_step`) | 顶部双轴入口 `<div class="rule-chips">`:**按环分组**(`chain_step` 字段,null 入「通用」组)`环① 环② …` + **「遇事速查」情境 chips**(从 `when` 提炼「发火时 / 谈成绩 / 被顶嘴…」,筛选卡)。每条 `<article class="rule-card" data-source data-step>` 三行全可见:`.rc-when`「**当** {when}」(加粗)/ `.rc-do`「**做** {do}」/ `.rc-because`「**因为** {because}」(淡色)+ 章码传送门「第 N 章 →」。**交互只筛选 / 分组 / 回章,不折叠一句话** | 必含 |
| 3 | **心智模型工具架** `<div class="models">` | distill:`mental_models[]`(`model` / `how_to_apply` / `evidence` / `boundary` / `chain_step`) | **抽屉式**(点击回报 ≥3 行,合格):每卡 `<article class="model-drawer" data-source>` 卡面常显 `.md-name`=`model` + 一句本质 + 明示「展开 ▾」;点开抽屉渲三段 `.md-how`=`how_to_apply`(怎么用)/ `.md-evidence`=`evidence`(书里依据 + 锚点)/ `.md-boundary`=`boundary`(**什么时候失效**,v2 没渲的宝藏字段,让工具卡自带批判性)。一次开一张(手风琴) | 必含 |
| 4 | **读完自检** `<div class="questions">` | distill:`self_check[]`(`q` / `followup` / `anchor`,4-8 条) | 整组收尾不打散。板头一句「这六个问题,建议每隔一段时间回来问自己一遍」。每条 `<article class="question" data-source>`=大号编号 + `<h3>`=`q`(第二人称主问句,含「你」)+ `<p>`=`followup`(**直接显示、不藏**)+「回到第 N 章 →」回链(`<a href="#ch-N">`,循环落点)。**无勾选、无打分、无记录**(决策 D11) | 必含 |
| 5 | **板尾 CTA** `<a class="next-cta" data-panel="panel-extend">` | 静态 | 「下一步:接着读什么 →」→ `panel-extend` | 必含 |

#### 1.2.5 板块⑤ 延伸阅读(`#panel-extend`,全页末尾,顺序 1→7 固定;跨域命名小节排 crossbook 之前,带走条排末行指路之前)

| 序 | 区块 · 根元素 | 数据来源(字段) | DOM 结构要点 | 降级 |
|---|---|---|---|---|
| 1 | **同类书卡** `<div class="similar">` | enrich:`similar_page.items[]`(`title` / `author` / `relation` / `why` / `fit` / `order`) | 原同类书子视图**撤销、内容内联**(少跳一步)。卡片栅格,每卡 `<article class="sim-card" data-source>`=书名 + 作者 + `.sim-rel`(**relation 三色徽标**:印证 `rel-support` / 互补 `rel-extend` / 纠偏 `rel-rebut`)+ `why` + `fit` | **可降级**:`similar_page===null` 或 `items:[]` → 整块删 |
| 2 | **阅读路径** `<div class="reading-path">` | enrich:`similar_page.reading_path` + `items[].order` | 编号路线条 stepper(`.rp-step` 按 `order` 串成 ①→②→③),路径说明放条上方;点路径步高亮对应书卡(名实相符版「星图高亮」) | 随 `similar_page` 降级 |
| 3 | **作者书架** `<div class="author-shelf">` | enrich:`author_page.works[]`(`title` / `year` / `one_liner` / `is_this_book` / `distill_slug`) | 栏头「还想读{作者} →」`<a href="#sub-author">`(进作者子页)。横排小卡 `.shelf-card`=书名 + 年份 + `one_liner`;已蒸的书(`distill_slug` 非空)= 站内互链 | **可降级**:`author_page===null` → 整块删(连同入口) |
| 4 | **跨域命名(这套思想在别处叫什么)** `<div class="cross-domain">` | distill:`cross_domain[]`(`domain` / `name` / `note`,v4,Q4-3) | 独立小节,排在 `.crossbook` 跨书回声**之前**。`.zone-title`「这套思想在别处叫什么」+ `.section-lead` 一句 + `.xd-list` **一行一条** `<div class="xd-item">`=`.xd-domain`(领域名,徽标样式)+ `.xd-name`(该领域的对应命名,强调)+ `.xd-note`(一句对应说明)。跨学科命名 3-5 条,把新书挂到读者已有知识域(xray 灵魂层回收)。**宁缺毋滥**:置信不足的条目不产 | **可降级**:`cross_domain` 空 / 缺 → 整块删 |
| 5 | **跨书回声** `<div class="crossbook">` | enrich:`cross_book_external[]`(`concept` / `book` / `stance` / `source`)+ Step4 互链(`knowledge-index.json`) | `.zone-title` + 概念连线卡:已蒸书=站内互链 `<a href="{对方slug}.html#ch-N">`,外部书=外链 `<a rel="noopener">`;标 5-tag(`NEW_CONCEPT` / `SUPPORTS` / `REFINES` / `CONTRADICTS` / `NEW_SUB_ASPECT`),**CONTRADICTS 左右并列不抹平**。跨书索引门面 | **可降级**:数据全空 → 整块删 |
| 6 | **离开前带走(带走条)** `<div class="takeaway-strip">` | distill:`napkin.formula`(复现)+ `action_chain[].label` | **出口骨架复现**(v4,Q2-1;间隔再现):排在末行指路**之前**。`.tw-head`「离开前带走:」+ `.tw-formula`=`napkin.formula` 复现(**小号**,后附 `.tw-tag`「① 见过 · 回顾」标注这是回顾非新内容)+ `.tw-rings` = `action_chain` 的 4-5 个 `label` 横排胶囊 `<a class="tw-ring" data-panel="panel-action">{label}</a>`(点击经现成 `initNav` 跳④行动清单对应环)。**声明式复现,非新字段归宿**:formula 唯一归宿仍在①餐巾纸,此处是回顾豁免(见 §1.4 例外注),不算 F5 金句复发;verify 不加新拦 | **可降级**:`action_chain` 缺 → 整块删(但④必产,通常在) |
| 7 | **末行指路** `<p class="extend-pointer">` | 静态 | 单向小字「想看围绕本书观点的争论 → ③ 观点对照」。**观点对照入口不放⑤**(它答「该不该信」不答「读什么」,主入口在③;放⑤=复刻 v2 捏合错误)。⑤ 是末板块,**不设 `.next-cta`** | 必含 |

#### 1.2.6 固定件(tabs 外)

| 区块 | 位置 | 根元素 | 说明 |
|---|---|---|---|
| **footer** | 页尾 | `<footer class="footer">` | 保留骨架文案,`{书名}`/`{作者}` 替实值;底部声明「AI 蒸馏是地图…回原书/原视频细看」 |
| **theme-picker** | main 内·tabs 外 | `<div class="theme-picker">` 内 `.tp-trigger`(`.tp-ico`🎨 + 「主题」+ `.tp-caret`)+ `.tp-menu`(7 颗 `[data-theme-pick]`) | 浮于右下角 `bottom:20px`(v3.1 下移、加图标 + 金描边 hover);**非默认主题在前**:`brand-dark` 放菜单第一位、默认 `warm-paper` 靠后(verify 冒烟依赖,brand-tokens §6),勿重排 |

### 1.3 页内子视图规格(2 张:作者页 + 观点对照页)

> 2 个全屏覆盖子视图,骨架在 `</main>` 前、panel 之外,`<section class="subpage" id="…" hidden>`(`position:fixed;inset:0;z-index:200`,默认 `hidden`)。**hidden 属性别删**(删了子视图默认展开盖住全页)。**同类书子视图 `#sub-similar` v3 删除**(内容内联板块⑤,§1.2.5)。
> **返回件统一改墨色胶囊 + 归属语境**(§2.3.3):`.subpage-bar` 内 `<button class="sub-back" data-sub-back>返回</button>`(箭头由 `::before` 出,HTML 只写「返回」)+ `.subpage-title` + 右对齐 `<span class="subpage-from">《{书名}》· {档案类型}</span>`(新增归属语境类)。

| 子视图 | 根元素 | 数据来源 | DOM 结构要点 | 降级 |
|---|---|---|---|---|
| **作者页** | `<section class="subpage" id="sub-author" hidden>` | enrich:`author_page`(结构化) | 见 §1.3.1(infobox 归一栏 + 五栏,引 author-template §2.2 的 `au-*` class) | `author_page===null` → 子视图 + 全部入口(hero 作者名链 + ⑤作者书架栏头链)一并删 |
| **观点对照页** | `<section class="subpage" id="sub-views" hidden>` | enrich:`views_page`(`topics` / `sources`) | **沿用 v2**:`.subpage-body` 内 `.sp-lead` + N 个 `<article class="view-topic">`(`.vt-viewpoint`=书中观点句 + **`.vt-focus`=「争议焦点」小结句**[v3 新增,防读者在两列迷路] + `.vt-cols` > `.vt-col.vt-support`[赞同方,`supporters` → `.vt-entry`{who/say/`<a rel="noopener">`}]/ `.vt-col.vt-critic`[质疑方,`critics`;某方空用 `<p class="vt-empty">`])+ `.sp-srcs`。页名改「观点对照」 | `views_page===null` → 删;某 topic 缺一方 → 该方 `.vt-empty` |

#### 1.3.1 作者页内部规范(F2,引 author-template §2.2,类名前缀 `au-`)

`.subpage-body au-body` 内桌面两栏(`grid-template-columns: minmax(0,1fr) 296px`),**显式行定位消左空白(v3.1)**:`au-tagline` 占 `grid-row:1`(跨全宽),`au-main` 正文填 `grid-column:1;grid-row:2`、`au-infobox` 占 `grid-column:2;grid-row:2` 并 sticky —— 两栏真并排(避免 grid 稀疏自动排布把 `au-main` 挤到 infobox 下方、左列留大片空白)。移动端(≤720px)单栏、两者 `grid-row:auto` 回落、infobox 顶置横卡、取消 sticky:

- **导语** `<p class="au-tagline">`(跨全宽 `grid-row:1`)= `author_page.tagline`(≤50 字,一句钉住)。
- **身份卡(v4,Q1-6,可降级)** `<blockquote class="au-persona">`(紧接 au-tagline 之下,跨全宽 `grid-row` 顺延):第一人称引块样式渲 distill `persona_card`(传主口吻「我是谁、我怎么想」)。**仅 `book_type=人物` 且 `persona_card` 非空时出现**;其他书型 / 字段空 → 整块删(零信息架构成本)。治「人物书最贵的产出读者看不到」(§1.4 原判「无独立可见槽位」的产了没人用)。
- **infobox 归一栏** `<aside class="au-infobox">`(桌面右侧 `grid-column:2;grid-row:2;position:sticky;top:12px`):`.au-photo`(`photo` 的 `<img data:>` 真人清晰照,缺→ `.au-monogram` 姓氏字符头像;照片获取标准见 enrich.md §1)+ `.au-name`=`name` + `.au-roles`=`infobox.roles`(`·` 分隔)+ `<dl class="au-facts">` 逐行 `.au-fact`(`<dt>`标签 + `<dd>`值):出生 `birth` / 逝世 `death` / 祖籍 `ancestry` / 国籍 `nationality` / 学历 `education[]` / 以何知名 `known_for` / 代表作 `notable_works[]`(可点:本书加 `.au-thisbook-badge`「本书」/ 已蒸站内互链 / 否则跳 `#au-works`)/ 开放行 `extra[]`。**逐行删不留「未知」;事实行(姓名外)<3 时整体降级为速览横条**。
- **正文五栏** `<div class="au-main">`,每栏 `<section class="au-sec" id="…">` 标题 `.au-sec-title`=「直白名 -- 论点副题」:
  - **S1 人物经历** `#au-life`:`career[]` → `<ol class="au-timeline">` 竖向时间线,每 `<li class="au-tl" data-source>`=`.au-tl-period`(`period`)+ `.au-tl-body`(`label` 加粗 + `text`)。
  - **S2 成就与影响** `#au-impact`:`impact.stats[]` → `.au-stats` 内 `.au-stat`(`<b>`num + `<span>`label)横排 + `<p>`=`impact.text`。
  - **S3 争议与评价** `#au-debate`:`debate.pro[]` / `.con[]` → `.au-debate-cols` 双列(`.au-dcol-pro` 围墙内 / `.au-dcol-con` 围墙外),每 `.au-dentry`={who/say/`<a rel="noopener">`}。
  - **S4 他与这本书** `#au-thisbook`:`this_book.text` 散文 + `.au-lineage`=`this_book.lineage`(写作谱系箭头行)。
  - **S5 主要作品** `#au-works`:`works[]` 年表 `<ol class="au-works-list">`,每 `<li class="au-work">`=`.au-wyear`(`year`,缺→「年份不详」组)+ 书名 + `one_liner`;`is_this_book` 行加 `au-work-this` + 「本书」徽标;已蒸=站内互链。`media_type==="video"` 时栏名措辞改「主要作品与系列」。
  - **尾** `.sp-srcs`=`author_page.sources`(可点外链 `rel="noopener"`)。
- **各栏可整栏降级**:`impact` / `debate` / `this_book` / `works` 任一 null/空 → 整栏删(含标题)。`career` 空但 `bio_long` 存在 → S1 按 v2 散文兜底渲染(旧书迁移)。

**hash 路由(脚本层 `initHashRouter`,骨架已连,勿改)**:`#sub-*` → 对应 subpage `hidden=false`、其余隐藏、`scrollTop=0`;非 `#sub-` 的 hash → 关全部子视图。入口 = hero 作者名 `<a href="#sub-author">` + ⑤作者书架栏头链 + ③观点对照入口卡 `<a href="#sub-views">`。返回(`initSubBack`):`.sub-back[data-sub-back]` → `history.back()` 或 `location.hash=''`。

### 1.4 资产归宿对账清单(每项资产 → 唯一归宿,防遗漏防重复)

> **本表是 F5 病根(一种资产两处出现无身份区分)的根治**:distill / enrich 每个可见字段**只有一个集中归宿**,填槽逐项对照,**禁为字段新造结构**(承 method T1)。「唯一归宿」列若写「+ 传送门」表示该资产在别处只以**链接**形式出现(导航),不重复渲染内容。

| distill / enrich 字段 | 唯一归宿 | 落法 / 备注 |
|---|---|---|
| `title` / `author` / `book_type` | 头部①刊头 `.cb-banner` | kicker 由 book_type + 领域拟;作者名即 `#sub-author` 入口 |
| `cover_intro` | 头部②封面简介 `.cb-intro` | 2-3 句,**禁比喻 / 禁复用 napkin**(§2.2) |
| `core_question`(v4) | **头部③ hero `.eyebrow`(唯一)** | 一句疑问句 ≤40 字,与 h1 标语成问答配对;餐巾纸不重复(防同板块双曝光);禁复用 cover_intro/one_liner(§2.2) |
| hero 标语(派生,非字段) | 头部③ `<h1>` | 全书比喻一句,字阶 T0 ≤48px |
| `napkin.formula` | ①餐巾纸 `.formula`(唯一渲染归宿) | 必含运算关系。**例外(v4,Q2-1)**:⑤`.takeaway-strip .tw-formula` 是**声明式回顾复现**(标注「① 见过 · 回顾」),不算第二归宿、不算 F5 金句复发;verify 不拦 formula 复现 |
| `napkin.formula_read`(v4) | **①餐巾纸 `.formula-read`(`.formula` 正下方,前缀「怎么读:」)** | 公式读法一句,点明运算符语义;书/视频必产(G4 扩展) |
| `napkin.one_liner` | **①餐巾纸 `<p>`(全页唯一)** | 不再进头部(治 F5 重复) |
| `napkin.sketch`(v4) | **①因果骨架草图 `.napkin-sketch`(餐巾纸后、脑图前)** | 内联 SVG 纵向因果流,直角经典 / 浅色 / 静态一屏;三图分工见 §1.2.1a;可降级(缺则整块删) |
| `chapters[]`(no/title/summary/hook) | ②目录态 `.chapter-toc` **+ ①脑图节点(传送门)** | title 论点式(T5),脑图叶子 `hyperLink:'#ch-N'` 只做跳转;`hook`(v4)渲 `.toc-hook` 悬念钩子(第三层,≤20 字) |
| `chapters[].narrative` | ②手风琴 `.bd-chapter` 正文 | 多段 `<p>`,800-1500 字/章 |
| `chapters[].excerpts` | ②手风琴章内 `.excerpt` | 书每章 ≥1;**章内唯一原文块**(金句不入章内) |
| `core_ideas[]`(idea/layman_analogy/primary/pillar) | ①核心观点卡 `.bd-coreideas` **+ 传送门回②** | primary→`.ci-primary` 放大;`pillar`(v4)按脑图一级分支分组渲染(组头=分支名,null 入「贯穿全书」组);与 soul 同源的条降 primary + `.ci-portal` 传送门到 `.soul-block`(Q1-4) |
| `core_ideas[].explain/evidence/evidence_level` | **①核心观点卡展开态 `.ci-explain`/`.ci-evidence`/`.ci-evlevel`** | **必渲三件**(硬约束 3,T8);高后果书(stakes=high)可另加 `.rc-certainty` 同款色点标来源硬度(v6.1,可选) |
| `arguments.chain` | **③立论复述 `.arg-restate`** | 从 v2 头部 thesis 移来;头部不再有总论框 |
| `arguments.chain_steps`(v4) | **③立论复述 `.arg-steps` 胶囊链(散文段之上)** | 4-8 步阶梯,每步 ≤14 字;散文保留作展开(Q4-7) |
| `arguments.hidden_assumptions` | ③批判四区·没证明的前提 | 与 `unproven_assumptions` 合并渲染 |
| `arguments.counter_examples` | ③批判四区·最强反对(附其下) | |
| `decision_rules[]`(when/do/because/chain_step/**certainty**) | ④情境决策卡 `.rule-card` **+ 传送门回②** | 按 `chain_step` 分组(null→通用),遇事速查 chip 从 `when` 提炼;**`certainty`(v6.1,仅 stakes=high)渲 `.rc-certainty` 色点徽标** -- book_explicit/cross_book_synthesis/general_knowledge → 绿/金/灰 = 书中明确/跨书合成/编者通识(复用 `.ci-evlevel` 模式,Zero-Hex;normal 书整删不渲) |
| `mental_models[]`(model/how_to_apply/evidence/boundary/chain_step) | ④模型抽屉卡 `.model-drawer` | boundary 必渲(什么时候失效) |
| `tensions[]`(a/b/note) | ③内在张力 `.tn-row` | A⇄B 窄行 |
| `critique.blind_spots` | ③批判四区·作者盲点 | |
| `critique.era_limits` | ③批判四区·时代局限 | 独立渲染(v2 浪费的字段) |
| `critique.unproven_assumptions` | ③批判四区·没证明的前提 | |
| `critique.strongest_objection` | ③批判四区·最强反对(压轴大字) | |
| `credibility_verdict` | ③裁决条 `.verdict-bar` | 2-3 句总裁决(v3 必产) |
| `quotes[]`(text/note/featured) | **②全书金句墙 `.quote-wall`(全量唯一)+ 传送门回②章** | featured 仅视觉加重、不另设首屏条;**废除 v2 FQ + `.quote-inline`** |
| `concepts[]`(concept/one_liner/common_misread/stance) | **②概念筹码条 `.concept-chips`(唯一)** | chip 弹卡;`common_misread` 非空的 chip 加 `.cc-has-mis` → 面上「≠」角标(v4,Q2-2);另供 Step4 跨书索引(上游,不额外渲染) |
| `soul_module` | **①两种养法对照 `.soul-block`(收尾)** | 不再独立 tab,不出现「书魂」二字 |
| `action_chain[]`(label/explain/detail) | ④行动路线图 `.chain` + `.chain-detail` | detail 全可见治「薄」;第⑤→①回环虚线 |
| `self_check[]`(q/followup) | ④读完自检 `.questions` **+ 回链②** | followup 直显 |
| `narrative_arcs[]` | (叙事书)②narrative 血肉素材 | **无独立可见槽位**(供 Pass2 写 narrative 参考) |
| `persona_card`(v4) | **作者页 `.au-persona`(仅人物书,au-tagline 下)** | 第一人称引块渲传主自述;`book_type≠人物` 或空 → 删(Q1-6;原「无独立可见槽位」已给槽) |
| `voice_dna` | footer 生成说明一行带过 | **无独立可见槽位** |
| enrich `author_page` | **子视图 `#sub-author`** + hero 作者名入口 + ⑤作者书架 | 结构化 infobox + 五栏(§1.3.1) |
| enrich `author_page.tagline` | 作者页导语 + ⑤/入口短卡 desc | 单一来源,不另存 `author_card` |
| enrich `similar_page` | **⑤同类书卡 + 阅读路径(内联,无子视图)** | relation 三色徽标 |
| enrich `views_page` | **子视图 `#sub-views`** + ③观点对照入口卡 | 沿用 v2 + 争议焦点 |
| enrich `reviews` | ③书评正反两列(rating 另喂①裁决条豆瓣分) | 可降级 |
| `cross_domain`(v4) | **⑤跨域命名 `.cross-domain`(crossbook 之前独立小节)** | 3-5 条跨学科命名;宁缺毋滥,空则删(Q4-3) |
| enrich `cross_book_external` | ⑤跨书回声 `.crossbook` | 可降级 |

### 1.5 可降级区块与 tab 名(判定规则,沿用 v2 降级一致性)

- **必含区块(verify 硬拦存在)**:头部两层(`.cb-banner` / `.cb-intro` / `.hero`;`.reading-guide` v3.1 已移除,不再必含)+ 板块①(`.bd-napkin` / `.bd-mindmap-wrap` / `.bd-coreideas` / `.soul-block`)+ 板块②(`.concept-chips` 见下 / `.chapter-toc` / `.bd-chapter` / `.quote-wall`)+ 板块③(`.verdict-bar` / `.arg-restate` / `.tensions` / `.crit-quad`)+ 板块④(`.chain` / `.rules` / `.models` / `.questions`)+ 每板 `.next-cta`(①-④)+ footer。
- **可降级区块**(对应 enrich / distill 数据 `null`/空 → 整块删,含 SLOT 注释对,不留空壳):`.concept-chips`(concepts 空)/ ③`.reviews`(reviews null)/ ③观点对照入口 + `#sub-views`(views_page null)/ ⑤`.similar` / `.reading-path` / `.author-shelf` / `.crossbook`(对应源 null)/ `#sub-author` + 全部入口(author_page null)/ **`.bd-brandbar` 品牌浮标(未配 `brand` → 整块删,见 §1.6)**。
- **板块⑤ 整体降级**:若 similar_page / author_page / cross_book_external **全 null**,`#panel-extend` 整块隐藏、其 tab 从 `nav.tabs` 撤除、④`.next-cta` 改指 footer 或删。tab 降到 4 个不报错(verify 只校验存在的 tab 文案 / panel id 对齐)。
- **删除动作**:该区块 `<!-- SLOT:XXX -->` 到 `<!-- /SLOT:XXX -->` 连同注释对整段删;删子视图连同其入口(hero 作者名链外壳→纯文本、⑤书架栏头链、③观点入口卡)。
- **删可降级块后 data-source 可能跌破 20**:删完复跑 verify;不足 20 说明蒸得薄,回补①核心观点 / ②章节 / ③批判 / ④规则的 anchor,**别为凑数塞空 `data-source`**。
- 单区块内部条目偏少但整块不该删的(如 quotes 只 2 条),据实少给,不硬凑、不编造。

### 1.6 品牌浮标 `.bd-brandbar`(可降级,**默认删**)

产物是新标签页打开的单文件 HTML,天然脱离站点布局 —— 读者进来后没有任何出口。这枚左上角浮标就是出口。

**默认状态是没有它。** 不配 `brand` 就连同 `<!-- SLOT:BRANDBAR -->` 注释整块删,产出干净页面 —— 使用者不该继承交付方的 logo。

配了才渲染,契约如下:

| 槽 | 含义 | 硬约束 |
|---|---|---|
| `brand.home_url` | 母品牌首页 | 与 `series_url` **必须不同** |
| `brand.home_label` | logo 的 alt / aria-label | 无障碍必需 |
| `brand.logo_light` | 浅色主题 logo | **必须 `data:image` 内联**,与封面同规矩 |
| `brand.logo_dark` | 暗色主题 logo | 同上;没有反色版就删掉 `is-dark` 那张 img |
| `brand.series_label` | 系列名(如「读书蒸馏」) | |
| `brand.series_url` | 本系列列表页 | |

🔴 **两个去向不许合并成一个**。2026-08-13 线上出过这个事故:一个挂着母品牌 logo 的按钮,点下去还停在同一个工具里 —— logo 在所有人的认知里就是「回首页」,接到别处等于把人人都会做的动作接错了地方。`verify_page.py` 的 `lint_brandbar()` 会拦。

配色全部走 §brand-tokens 那 21 个 token(`--line` / `--bar-bg` / `--paper` / `--ink` / `--font-display` / `--green`),所以 6 套主题下自动协调,不必每主题写一遍;暗主题靠两张 logo 显隐切换,比 `content:url()` 兼容。

### 1.6 render_profile 变体化区块 / tab + 新结构原语(v6,2026-07-12 B-1/B-5/B-7)

§1.5 是 legacy 四型的必含区块。**书型自适应(见 `method.md §1.4`)按 `render_profile.archetype` 增删区块、tab 并挂新原语。** verify 按注册表 `RENDER_PROFILES` 的 `omit_blocks`/`tabs` 变体化校验;**无 render_profile = §1.5 全量必检(向后兼容,现有页不受影响)**。

| archetype | 省略区块(不必含) | 保留 tab | 主体新原语(签名 class) |
|---|---|---|---|
| 论说/叙事/人物/工具 | (无,同 §1.5) | 全 5 | (无) |
| 语录 | `.soul-block` `.arg-restate` `.rules` `.models` `.questions` `.verdict-bar` | 速览/精读/延伸 | **`.quote-board` 语录墙** |
| 书单 | 上 + `.bd-napkin` | 速览/精读/延伸 | **`.booklist-cards` 书单卡** |
| 课程 | `.soul-block` `.arg-restate` | 速览/精读/清单/延伸 | **`.kp-tree` 知识点树** + `.exercise-card` 练习卡 |
| 考试 | 上 + `.rules` `.models` `.questions` `.verdict-bar` | 速览/精读/延伸 | **`.exam-point` 考点卡** + `.worked-example` 例题解析 + `.recall-card` 记忆卡 |

**新原语规格(填 `#panel-full` 主体,替代/补充讲书稿逐章)**:
- **`.quote-board` 语录墙(语录型)**:格言按主题聚成卡组,**每卡 = 原文 excerpt(blockquote 照录 ≤150 字 + anchor)+ 一句点评**;点评转述(破折号 `--`)、原文照录(豁免)。主体前置,不套每章 800 字 narrative(治抽象密集书注水)。
- **`.booklist-cards` 书单卡(书单型)**:每本一卡 = 书名 + 作者 + 一句「为何读」+ 关键观点 1-2 条(带 anchor);已蒸的关联书挂站内互链 `../{slug}/{slug}.html`。
- **`.kp-tree` 知识点树(课程型)**:层级大纲,叶子=可独立掌握的最小知识点,带前置依赖标注;可复用脑图 concept-cluster 引擎渲染。配 `.exercise-card`(题干/提示/参考)。
- **`.exam-point` / `.worked-example` / `.recall-card`(考试型)**:考点卡(考点名 + 考频/难度 chip + 要点)、例题解析(题干/标准解法/常见陷阱)、记忆卡(正反面、间隔重复、可 Anki 导出)。**这是 `method.md §9` 停产 quiz 的按体裁重启**——仅考试型激活,不回全书型自测。
- **合法自创口(T1)**:新 primitive 的签名 class 须**先入本表 + verify `RENDER_PROFILES`**,再据以填页;禁逐书即兴造未登记的块。

> ⚠ **状态(诚实标注)**:契约层(profile 注册表 / omit_blocks / tabs / 门禁分层 / verify 拦篡改)已落地且测试覆盖;**但四新型的骨架 SLOT 与 CSS 尚未用真书 E2E 验收**(手上暂无语录/书单/课程/考试样书)。首次蒸对应书型时按 method「先抽样 1 本验收再铺量」跑通、补 `page-skeleton.html` 的 SLOT 与样式,再固化。**案例档案 `.case-archive`(B-5)= 论说/叙事型的可选子视图**(把埋在章正文的招牌案例升为可浏览卡,挂 ⑤ 或 ② 下),按 `render_profile.primitives` 声明触发,非默认必含。

---

## 2. 版式铁律(命中即返工)

### 2.0 结构与内容铁律

| # | 铁律 | 判定标准 |
|---|---|---|
| **T1** | **区块结构不可自创** | 不改五 tab 分组 / panel id、不改签名 class(`.cb-banner`/`.cb-intro`/`.hero`/`.bd-napkin`/`.bd-mindmap-wrap`/`.bd-coreideas`/`.ci`/`.ci-primary`/`.ci-evidence`/`.ci-evlevel`/`.soul-block`/`.concept-chips`/`.chapter-toc`/`.bd-chapter`/`.excerpt`/`.quote-wall`/`.verdict-bar`/`.arg-restate`/`.tensions`/`.crit-quad`/`.reviews`/`.views-entry`/`.chain`/`.chain-step`/`.chain-detail`/`.chain-loop`/`.rules`/`.rule-chips`/`.rule-card`/`.models`/`.model-drawer`/`.questions`/`.similar`/`.reading-path`/`.author-shelf`/`.crossbook`/`.next-cta`/`.au-infobox`/`.au-sec`/`.au-timeline`/`.subpage-from`/`.ci-group`/`.ci-portal`/`.arg-steps`/`.arg-step`/`.cross-domain`/`.xd-item`/`.au-persona`/`.toc-hook`/`.cc-has-mis`/`.formula-read`/`.napkin-sketch`/`.takeaway-strip`/`.tw-ring`（v4 新增签名 class） 等)、不动 SLOT 注释对。只在槽位内填内容。soul 三型 / infobox 逐行 / 各栏降级按数据定,不算改结构。要「不一样」只走 `design-craft.md` 的 token / signature 层 |
| **T2** | **Rule 70/30(详实层散文豁免)** | 页面可见正文里落在**结构化组件**的文本 ≥70%;纯散文引导句(`.section-lead`/`.eyebrow`/`.soul-intro`/`.mm-hint`/`.sp-lead`/`.au-tagline`)合计 ≤30%。**豁免**:`panel-full` 的 `.bd-chapter` narrative 多段 `<p>` 视同结构化、不占 30% 额度(method §3.5);豁免仅限此处 |
| **T3** | **出处覆盖 `data-source` ≥20(常显)** | 全页 `data-source` 出现 ≥20(verify 硬拦 `<20`)。每条 core_idea / chapter / excerpt / rule / mental_model / critique / tension / verdict / arg-restate 落 DOM 带其 anchor;出处由 `.src-note` **随文常显**(无「显示出处」开关)。JSON 可保留 `book.txt` 原始锚点供核验，但公开 HTML 必须转为读者可读的“章节·原文位置”，不得泄露内部文件名。 |
| **T4** | **Zero Hex** | 组件样式只用 `var(--*)`;hex 只许出现在 `:root{}` 与 `body[data-theme=…]{}` token 块内;内联 `style="…"` 里的 hex 同样禁(curve `sc-line`、evidence_level 色点等换色走 token / `data-*` + CSS) |
| **T5** | **论点式标题** | `chapters[].title` / `.bd-chapter>h3` / `.chapter-toc` 章行 / 脑图二级节点文字 禁零信息标题,命中任一返工:① 黑名单正则 `^(第?\d+[章节讲集]?\|视频\d+)$`(以 method §7.5 G8 为准);② 有效长度 <8 字;③ 落通用容器词表(`章节脉络/内容概要/核心内容/主要观点/金句墙/金句/总结/概述/前言/结语`)。判断句语义靠蒸馏自查,verify 机拦 ①②③ |
| **T6** | **②目录态(默认收起 + 手风琴,替换 v2「默认全展开」)** | `panel-full` 的 `.chapter-toc` 章行**默认收起**,`.bd-chapter` 点击手风琴展开(**允许多章同开**),**必配「全部展开」逃生门**(`.toc-expand[data-toc-toggle]` 存在)。verify 拦:目录态章行默认非展开态 + 全部展开钮存在。**注**:这是 v3 对 v2「章节非 details、默认全展开」的定向反转,勿再套用旧铁律 |
| **T7** | **金句唯一归宿 = ②金句墙** | 金句只落 `.quote-wall`(quotes 全量);**章内不得出现 `.quote-inline` 行内金句、首屏不得出现 `FQ`/`.featured-quotes` 独立金句条**。verify 拦这两个 v2 遗留结构存在即报警 |
| **T8** | **核心观点卡展开态必渲三件(硬约束 3)** | `.ci` 展开态必含 `.ci-explain`(explain)+ `.ci-evidence`(evidence)+ `.ci-evlevel`(evidence_level 徽标);缺任一即返工。徽标可见文案固定「原书依据/转述状态」,禁称「证据强度」,避免与心理学外证混淆 |
| **T9 / G24** | **心理学外证 100% 映射** | psychology 页面必须含**唯一、可见** `.psych-evidence`;每个 distill claim_id 恰有一个可见 `.pe-claim[data-claim-id]`,无多无少;每项含 3 个独立、可见、非空真节点 `.pe-book/.pe-research/.pe-boundary`,不得藏进 `template`、`hidden`、`aria-hidden` 或 `display:none/visibility:hidden`。`.pe-title` 回指原书主张,`.pe-status` 对齐结构化状态;`.pe-research` 必须呈现 best_evidence、status、replication,且非 `not_testable` 至少有一个回指 `evidence_page.sources` 的有效可见链接。普通书不得因此新增必选块 |

### 2.1 交互立法双条款 + 三问出厂检(治 F7/F10 的根,verify + 出厂自查)

| # | 条款 | 判定标准 |
|---|---|---|
| **IX1** | **点击回报率 ≥3 行** | 任何可点元素展开后必须换来 **≥3 行新信息**,否则内容直接可见、不做点击。反例(v2 病根):`.chain-step` 点开只显一句 `explain` -- v3 改 explain + detail 全可见。合规:核心观点卡展开态(explain+evidence+evlevel)、模型抽屉(how+evidence+boundary)、概念 chip 弹卡(one_liner+误读+stance) |
| **IX2** | **交互用于组织,不用于隐藏** | 筛选 / 分组 / 跳转 / 手风琴对照是**好交互**(rule-chips 筛选、chapter-toc 目录、脑图传送门);把短内容藏进点击是**坏交互**。规则卡三行、自检 followup、行动 detail 一律**直接可见**,不折叠 |
| **三问** | **每个可点元素出厂三问**(design-craft §7 同款) | 每个可点元素须能回答:*① 为什么想点(诱因可见)/ ② 点完得到什么(≥3 行回报)/ ③ 怎么回来(逃生门 / 返回胶囊 / tab 常驻)*。答不齐即改回直显或补逃生门 |

> **每个折叠必配逃生门**:②目录态配「全部展开」;子视图配显眼返回胶囊;手风琴配「收起 / 回目录」。

### 2.2 三处文案分工表(消灭重复的硬规则 + 查重 lint)

> v3.1 导读条 `.reading-guide` 移除后,头部文案位收敛为三处(原「导读条=这一页怎么读」职责由 sticky tab 的板块名 + 副题承担,不再单列一段文案)。

| 位置 | 职责(装什么) | 禁令 |
|---|---|---|
| hero eyebrow `core_question`(v4) | 这本书**答什么问题**(一句疑问句,与 h1 成问答配对) | **禁复用 `cover_intro` / `napkin.one_liner`**(不得含其 ≥12 字连续片段,G19);是真问题句、不是把答案改反问 |
| 封面简介 `cover_intro` | 这本书**讲什么**(信息型:素材从哪来 / 框架是什么 / 结论落在哪) | **禁比喻**(比喻是 hero 标语专属);**禁复用 `napkin.one_liner`**(不得含其 ≥12 字连续片段) |
| hero 标语 `<h1>` | 这本书的**立场**(一句,情绪型比喻) | 只此一句、不带解释;字阶 T0 ≤48px |
| 各板块 `.section-lead` | **该板块装什么、怎么用** | 不复述全书总论 |

- **机械保障(verify 查重 lint,对齐 method G16/G19)**:`cover_intro` / hero 标语文案含 `napkin.one_liner` 中 **≥12 字连续片段** 即 FAIL;`core_question` 含 `cover_intro` 或 `napkin.one_liner` 中 **≥12 字连续片段** 即 FAIL(G19)。四处文案(问题 / 讲什么 / 立场 / 板块说明)职责错开=从源头写不重(治 F4「两处总论抢活」)。

### 2.3 视觉规格(banner 纸底绿带 / 6 级字阶 / 返回胶囊,数值引 `v3-visual-header.md`,零 hex)

#### 2.3.0 交互态底色 = `--green`(v3.1,替代刺眼纯 `--ink` 黑块)

大块**交互态**统一走品牌绿 `--green` 底 + `--paper` 反白字(森林绿呼应「培育 / 成长」类主题,7 主题下均与 `--paper` 亮度反向、对比度过 AA 大字):`.tab.on`(选中 tab)/ `.next-cta`(板尾 CTA)/ `.sub-back`(返回胶囊)/ `.cc-chip.on`·`.rc-chip.on`(选中筹码)/ `.ch-act.ch-next`(继续读下一章)。**不再用纯 `--ink` 做大块交互底**(视觉过黑)。保留 `--ink` 的仅:`.cs-no`/`.rp-no` 小号数字圆标、`[data-source]::after` 悬浮出处气泡(小件 / 装饰 / 瞬态,非大块交互);`.cb-banner` 刊头 v3.2 已改**纸底 + 森林绿粗色带**(§2.3.1,不再用 `--ink` 墨底,避免在暖纸页上突兀)。全程 token 驱动、零 hex。若某主题 `--green` 太跳可退 `--ink-soft` 深棕,但当前 7 主题实测均协调。

#### 2.3.1 banner 纸底 + 森林绿粗色带刊头(v3.2,替换旧「案 A 墨底反白」)

**变更缘由**(sandy 2026-07-04):旧「墨底反白」整块纯黑(`--ink` 底)压在暖纸页上太突兀。改成**与页面一体的纸底 + 左侧森林绿粗色带 + 深字**:banner 背景走 `linear-gradient(135deg,var(--paper),var(--paper-deep))`(极淡纸质渐变,仅 var);左缘 `border-left:6px solid var(--green)`(森林绿呼应「培育成长」主题);文字全部翻**深色**(书名 `--ink`、作者/简介 `--ink-soft`);`--gold` 只做**装饰级**(kicker 金章描边 + tint 底、作者胶囊金边、`.cb-intro strong` 金下划线、底缘金渐变线),绕开 `--gold` 小字前景对比度短板(§1 注意列 -- 金只上边框/装饰底/大字,正文字色一律深墨)。书封由 `filter` 双投影(落纸阴影 + 1px 轻边)在纸底上立体化。**零 hex、零新 token**(dark 系主题 `--paper`/`--paper-deep` 自动翻深、`--ink` 翻亮 → banner 自动变「暗纸 + 亮字 + 绿带」,与站壳一体,属预期语义反转;交互态选中 / CTA / 返回胶囊仍走 `--green` §2.3.0,不受影响)。

```css
.cb-banner{display:grid;grid-template-columns:300px 1fr;margin:18px 0 8px;
  border:0;border-left:6px solid var(--green);border-radius:6px;                /* 森林绿粗色带 */
  background:linear-gradient(135deg,var(--paper),var(--paper-deep));            /* 极淡纸质渐变,仅 var */
  box-shadow:var(--shadow);position:relative;overflow:hidden}
.cb-banner::after{content:"";position:absolute;left:0;right:0;bottom:0;height:3px;
  background:linear-gradient(90deg,var(--gold),transparent 72%)}       /* 金色底缘,装饰级 */
.cb-banner img.cb-cover{width:100%;height:100%;max-height:420px;object-fit:contain;
  padding:32px 8px 32px 32px;
  filter:drop-shadow(0 14px 26px rgba(0,0,0,.20)) drop-shadow(0 1px 1px rgba(0,0,0,.26))} /* 落纸阴影 + 轻边定义 */
.cb-banner .cb-meta{padding:44px 48px 40px 24px}
.cb-banner .cb-kicker{display:inline-flex;align-items:center;gap:9px;margin:0 0 14px;
  padding:5px 13px 5px 11px;border:1.5px solid var(--gold);border-radius:999px;   /* 金章:描边 + tint 底 */
  background:var(--tint-accent);color:var(--ink-soft);
  font:700 .8125rem/1.3 var(--font-display);letter-spacing:.13em}
.cb-banner .cb-kicker::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--gold)} /* 金印点 */
.cb-banner .cb-title{margin:0 0 10px;color:var(--ink);                    /* 深字(纸底上 ~12:1) */
  font:900 2.25rem/1.22 var(--font-display);letter-spacing:.01em}      /* T1 书名 36px/900 */
.cb-banner .cb-author{margin:0 0 16px;display:flex;flex-wrap:wrap;align-items:center;
  gap:8px 10px;color:var(--ink-soft);font-size:.9375rem}                  /* v3.1 作者入口做醒目 */
.cb-banner .cb-author-lead{color:var(--muted)}                           /* 「作者 ·」前缀,弱化 */
.cb-banner .cb-author-link{display:inline-flex;align-items:center;padding:4px 14px;
  border:1.5px solid var(--gold);border-radius:999px;
  background:var(--tint-accent-strong);color:var(--ink);                  /* 金边金调底 + 深字,纸底上仍醒目 */
  font-weight:700;text-decoration:underline;text-underline-offset:3px;
  text-decoration-color:var(--gold);transition:transform .18s ease,background .18s ease}
.cb-banner .cb-author-link:hover{transform:translateX(3px);
  background:color-mix(in srgb,var(--gold) 30%,transparent)}
.cb-banner .cb-author-hint{color:var(--muted);
  font:700 .8125rem/1 var(--font-display);letter-spacing:.02em}          /* 「查看作者档案 →」备注 */
.cb-banner .cb-intro{margin:0;max-width:40em;color:var(--ink-soft);
  font-size:1.0625rem;line-height:1.9}                                 /* 承 2-3 句/3-4 行 */
.cb-banner .cb-intro strong{color:var(--ink);font-weight:700;border-bottom:2px solid var(--gold)} /* 深字 + 金下划线 */
@media(max-width:720px){.cb-banner{grid-template-columns:1fr}
  .cb-banner img.cb-cover{max-height:280px;padding:24px}
  .cb-banner .cb-meta{padding:26px 24px 30px}.cb-banner .cb-title{font-size:1.75rem}}
```

- `rgba(…)` 仅出现在书封 `drop-shadow` 双投影(允许项,非组件前景色);其余全 `var(--*)` / `color-mix(var)` / `transparent`,零 hex。
- **文字全深色**:书名 `--ink`、作者行 / 简介 `--ink-soft`、lead / hint `--muted`;`--gold` 只落 kicker 金章描边、作者胶囊金边、`.cb-intro strong` 金下划线、底缘金渐变线(边框 / 装饰底 / 下划线,非小字前景),任意主题不掉对比度。
- **作者入口胶囊**在纸底上靠「金边 + `--tint-accent-strong` 金调底 + 金下划线 + hover 位移」保持醒目;kicker 与作者胶囊靠「金印点 vs 下划线名 + hint」区分,不混淆。

#### 2.3.2 6 级字阶系统(治 F4 字号失控,级比≈1.22)

全页正标题**收进 6 级阶梯**,任何组件标题只许取梯内值,新组件不得发明新字号。

| 级 | 名 | 值 | 字重/行高 | 落到选择器 |
|---|---|---|---|---|
| T0 | hero 巨标语(降级保留) | `clamp(2.25rem,4vw,3rem)`=36-48px | 900 / 1.15 | `.hero h1`(**上限砍到 48px,禁再 72**) |
| T1 | 书名(banner) | 2.25rem=36px | 900 / 1.22 | `.cb-title` |
| T2 | 板块题 | 1.625rem=26px | 900 / 1.25 | `.section-title` / `.zone-title` |
| T3 | 章节题 / 子页题 | 1.375rem=22px | 800 / 1.35 | `.bd-chapter>h3` / `.subpage-title` / `.au-sec-title` |
| T4 | 卡片题 | 1.125rem=18px | 800 / 1.4 | `.ci-idea` / `.md-name` / `.sim-card h3` / `.question h3` / `.toc-row` 标题 / `.au-name` |
| T5 | 标签 / 眉题 | .8125rem=13px | 700 / 1.3 + `letter-spacing≥.08em` | `.cb-kicker` / `.eyebrow` / `.rc-when` 标签 / `.sp-field-label` |

- 配套正文阶(防串级):lede/导语 19px;正文/卡片正文 17px/1.85;出处小字 13px;tab 文字 16px/800。移动端整体降半级(T0→2rem、T1→1.75rem、T2→1.375rem、T3→1.25rem,T4/T5 不动)。
- verify 抽查:`.hero h1` computed font-size ≤48px(48*dpr 容差);标题选择器不得出现梯外字号。

#### 2.3.3 返回按钮墨色胶囊 + 归属语境(F10)

```css
.sub-back{display:inline-flex;align-items:center;gap:8px;padding:10px 20px 10px 16px;
  border:0;border-radius:999px;background:var(--green);color:var(--paper);      /* v3.1 交互底 --green,§2.3.0 */
  font:700 .875rem/1 var(--font-display);cursor:pointer;box-shadow:var(--shadow)}
.sub-back::before{content:"\2190";font-size:1rem;line-height:1;transition:transform .18s ease}
.sub-back:hover::before{transform:translateX(-3px)}                    /* 动效只给箭头,底色不变 */
.sub-back:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
.sub-back:active{transform:scale(.97)}
.subpage-bar{border-bottom:2px solid var(--ink)}                       /* 归属线提级(原 1px --line) */
.subpage-bar .subpage-title{font:800 1.375rem/1.2 var(--font-display)}  /* T3 22px */
.subpage-bar .subpage-from{margin-left:auto;color:var(--muted);
  font:700 .8125rem/1.3 var(--font-display);letter-spacing:.06em}       /* 归属语境,右对齐 */
@media(max-width:720px){.sub-back{min-height:44px}.subpage-bar .subpage-from{display:none}}
```

- HTML:`<button class="sub-back" data-sub-back>返回</button>`(箭头交给 `::before`,HTML 只写「返回」)+ `<span class="subpage-from">《{书名}》· 延伸档案</span>`。`[data-sub-back]` 行为契约与 JS 不动。

---

## 3. 生成流程(逐步照做,直到 verify exit 0)

1. **复制骨架**:`cp $SKILL\templates\page-skeleton.html $DATA\{书目录}\{slug}.html`(或读骨架另存到产物路径)。
2. **全局替换头信息**:`SLUG_PLACEHOLDER` → `{slug}`(`<main data-book-slug>` 拼进度 key);`{书名}` → 真实书名;`{作者}` → 真实作者(`<title>` / `.cb-title` / `.cb-author` / footer / `.subpage-title` / `.subpage-from` 都有)。
3. **填头部两层**:`.cb-cover`(书籍须 `data:image` 封面)/ `.cb-kicker`(book_type + 领域)/ `.cb-title` / `.cb-author`(`.cb-author-link` 内嵌 `#sub-author` 链 + `.cb-author-hint` 备注)/ `.cb-intro`=`cover_intro`(过 §2.2 查重)/ `.hero h1`=hero 标语。**导读条 `.reading-guide` v3.1 已删,无需填。**
4. **逐板填充(①→⑤,板内顺序固定)**:按 §1.2 各板块表把 distill / enrich 字段填进签名 class 槽位;anchor 一律进 `data-source`;金句 / excerpt / 书评原文照录不改写;章标题过 T5 自查。**核心观点卡展开态必填 explain+evidence+evidence_level(T8)**;**金句全落 `.quote-wall`,章内不填行内金句(T7)**;**②章行默认收起(T6)**。
5. **soul 三选一**:`.soul-block` 按 `soul_module.type` 保留一型模板,删掉另两型;curve 型每 `series` 一根 `<polyline class="sc-line">`,`points` 映射 `viewBox`。
6. **填两张子视图**:`#sub-author` 按 §1.3.1 填 infobox(逐行降级)+ 五栏(整栏降级);`#sub-views` 沿用 v2 + 每 topic 加 `.vt-focus` 争议焦点。**同类书子视图不存在**(内联⑤)。
7. **删未用 dummy + 降级**:骨架「(示例)」「(dummy)」内容填真时删干净;可降级区块 / 子视图数据 null 的,整块(含 SLOT 注释 + 入口)删除(§1.5);⑤ 全空时隐藏 `#panel-extend` + 撤 tab。
8. **跑出厂验证**(每次改完都跑,失败按提示改后重跑,直到 exit 0):
   ```
   python $SKILL\scripts\verify_page.py $DATA\{书目录}\{slug}.html --distill $DATA\{书目录}\distill.json --source $DATA\{书目录}\book.txt --screenshot $DATA\{书目录}\_verify.png
   # 已知心理学项目另加 --require-domain psychology；会自动查同目录 source-audit.json
   ```
   verify v3 覆盖(Task 6 建门禁):体积 ≤3MB / 必需区块齐(§1.5)/ 五 tab A 套文案 + panel id 对(含 `panel-extend`)/ **②目录态默认收起 + 全部展开钮存在(T6)** / 核心观点卡展开态三件齐(T8)/ **金句墙唯一、无 `.quote-inline`/`FQ`(T7)** / **cover_intro/hero 查重(§2.2,对齐 G16)** / 裁决条 + 底部 CTA 存在 / 字阶抽查(hero≤48px)/ 返回胶囊 + `.subpage-from` 存在 / 子视图一致性(`#sub-author` present IFF author_page 非 null、works 恰一条 is_this_book;`#sub-views` present IFF views_page 非 null)/ 「显示出处」按钮不存在 + `.src-note` 常显 / 无外链 script·link·img / lang="zh" / `data-source`≥20 / token 块外零 hex / 主题切换后 body 背景变化。传 `--distill` 另拦 method §5.1 六类 anchor / excerpts 版权红线(G14)/ primary·featured 越界(G15)/ layman_analogy 非空(G10)/ soul_module 合规(G11)/ self_check(G12)/ action_chain + detail(G13/G17)/ cover_intro(G16)/ credibility_verdict(G18)/ chain_step∈[1,5]或空；心理学严格域再核 source-audit 原文证据链和证据卡完整 scope/精确来源 URL 集合。
9. **违规修复优先级**:内容类(缺区块 / data-source 不足 / dummy 未删 / narrative 太薄 / 标题非论点式 / 展开态缺三件)→ 回补内容;样式类(hex 外泄 / 外链)→ 改回 `var(--*)` / 内联为 `data:`;**绝不放宽 verify 或删检查项来「过关」**。exit 0 才算 Step6 完成。

---

## 4. 章码传送门与目录态交互(脚本层契约,骨架已连,勿改)

> 全页「循环」动线靠章码传送门兑现:脑图节点 / ①核心观点卡「出自第 N 章」/ ②金句墙「出自第 N 章」/ ④规则卡「第 N 章」/ ④自检「回到第 N 章」,全部指向 `#ch-N`。

- **传送门链一律 `<a href="#ch-N">`**;JS 在 hashchange 时:若 hash 匹配 `#ch-N` → 激活 `panel-full`(切 tab)→ 展开该 `.bd-chapter`(手风琴)→ 滚到章首 → 章头高亮 2 秒(`.flash` 类),目录其余行保持收起、避免迷失。`#ch-N` 必须真实存在(对齐 `.bd-chapter id="ch-N"` 与 `.chapter-toc` 的 `data-ch="N"`),否则跳空。
- **目录态(v4 批次C 定稿 Q5-8)**:`.toc-row[data-ch=N]` **整行可点**(整个 `<button>` 热区,非仅箭头)→ 就地展开 `.bd-chapter#ch-N`(不跳页),再点收起;**保持多开手风琴**(可同时展多章,与「全部展开」并存,不互斥收起);`.toc-expand[data-toc-toggle]` 一键全展 / 全收。行 `:hover` 有 `--tint-accent` 底色反馈;点开后 `scrollIntoView({block:'start'})` **平滑滚到章首、落 sticky tab 栏正下方**(由 `.panel [id]{scroll-margin-top:calc(var(--tab-h)+12px)}` 顶开,一行搞定)。
- **已读语义(v4 批次C Q5-3/Q5-3B,治「点开即计」假)**:`.toc-progress` 计数 = **读到章尾才 +1** —— `IntersectionObserver` 观测每章 `.ch-actions`(章尾),入视口才 `markRead`;**「全部展开」只展开、不计已读**;已读集合落 **`localStorage` key `bd:{slug}:read`**,回访恢复(`loadRead`)。**读态 / 开态视觉分离**:`.toc-row.open`=金标 `.toc-no` + 金描边高亮(正在读),`.toc-row.read`=绿标 `.toc-no` + ✓ 角标(读过了)。
- **章尾预告卡(v4 批次C Q5-2)**:`initChapterPreview()` 把章尾裸钮 `.ch-next[data-ch-next]` 升级为**下一章预告卡**(JS 读 `.toc-row[data-ch=N+1] .toc-title` 论点标题 + `.toc-meta` 读时,渲 `.cn-kick/.cn-title/.cn-meta`,保留 `data-ch-next` 连读契约);**末章无 ch-next → 注入 `.ch-final` 终局卡**(「全书读完 ✓ · 这书该信几分? → 批判与评价」,`data-panel="panel-judge"` 经 `initNav` 委托切板)。`initChapters` 须在 `initNav` **之前**跑(先注入终局卡再统一绑 `data-panel`)。
- **阅读中上下文条(v4 批次C Q5-4)**:`.ch-ctxbar`(panel-full 顶,`position:sticky;top:var(--tab-h)`,默认 `display:none`)—— 章正文占视口时经 `IntersectionObserver`(与 Q5-3 共用观测 `.bd-chapter`)显示「第 N 章 · 已读 n/N · 回目录」,离开正文自动隐;与移动端 sticky tab 栏(Q7-6)同吸顶层,两者总高约 96px,勿叠爆遮内容。
- **切板定位(v3.1)**:tab / `.next-cta` / 末行指路回链 的 `data-panel` → `activateTab` 切 panel 后 `scrollPanelTop(panelId)` 把该 panel 顶部滚到悬浮 tab 栏正下方(减去实测 `tabBarH()`,不写死);章行 `.toc-row` / 章码传送门 → 展开 `.bd-chapter` 后 `scrollIntoView`,落点由 `.panel [id]{scroll-margin-top:calc(var(--tab-h)+12px)}` 顶开 tab 栏高度(`--tab-h` 由 `syncTabH()` 实测 tab 栏 offsetHeight 写入,resize 时刷新)。**导读条已废,原 `.reading-guide` chip 切 tab 逻辑随之删除。**
- **CTA / chip**:`.rule-chips` chip → 筛选 `.rule-card`(按 `data-step` 分组 + 情境筛选);`.concept-chips` chip → 弹 `.cc-pop` + 高亮含该概念的 `.toc-row`;`.model-drawer` → 手风琴开合(一次一张)。
- 脑图为**自绘 SVG 深色版(无 vendor 依赖)**:交互 `<script>` 内 `initMindmap()`(读 `#bd-mindmap-data` 的 `nodeData` → tidy-tree 布局 + SVG 挂线 + viewBox viewer)+ `initHashRouter` + `__bdInitExtra` **勿删勿改勿重排**;初始化挂 `astro:page-load` + `DOMContentLoaded` 双时机(extract 兼容,§6)。

---

## 5. 脑图 JSON 数据契约(`#bd-mindmap-data`,自绘 SVG 深色版,位置固定①内)

> 脑图落位 **固定在板块① 餐巾纸正下方、核心观点之前**(F5)。引擎 **v4.1 起从 mind-elixir 换自绘 SVG**(sandy 定稿):树骨架 + 关联/收纳这套 vendor 组件被替换成一段**通用 SVG 生成器 + viewBox viewer**(无任何 vendor,净省 ~69KB)。写进 `<script type="application/json" id="bd-mindmap-data">` 的仍是一段 JSON,数据主体是 `nodeData` 双层知识树(顶层 `layout` 字段可缺省;**`arrows`/`summaries` 已废——SVG 版不画任何跨枝关联/收纳虚线,残留字段生成器一律忽略**)。脚本层 `initMindmap()` 读 `nodeData` → tidy-tree 确定性布局 → 生成 SVG 挂线节点(root 卡片 / 一级金奶油纯文字 / 二级双层[关键词 + 判断句 + 章码 chip] / 三四级 emoji 前缀纯文字)+ **父子直角肘形梳齿引线**,插进 `<div id="bd-mindmap"><div class="mm-stage">` 并挂 viewBox viewer。**nodeData 之外零硬编码,换书换数据即出图(通用生成器,禁把某本书内容写死进 skeleton)**。**nodeData 是「关键词路标 + 判断句副文本」双层知识树**(真 4 级:一级章区段 → 二级核心观点[双层] → 三级支撑[🧠/💡/⚖️] → 四级案例/外部[📖/📚],45-75 节点;拆法见 method §4.6),**全图 topic 总字数 ≤900**。

### 5.1 schema(单键 `nodeData` + 可缺省 `layout`)

- **顶层 `layout`**(字符串,可缺省):`"chapter-span"`(章区段模式,默认)或 `"concept-cluster"`(概念聚类模式)。语义仍在(驱动一级分支怎么拆,见 method §4.6);SVG 版布局是固定的横向 tidy-tree(root 在左、逐级右展),`layout` 为透传字段,verify 忽略。
- **`nodeData`**(双层知识树,单根):`{ id, topic, root?, children?[], tags?[], hyperLink?, expanded?, _src? }`
  - **根 = 书名**(`root:true`,唯一根节点)→ 渲染为稍亮墨绿圆角卡片 + 米白大字。
  - **一级分支 = 章区段(默认)或概念桶**(见 method §4.6),3-5 个;`topic` = 概念短语段名 **≤8 字**(可含 ①②③④ 序号与「第N-M章」后缀,如「① 问题的根源 · 第1-2章」)→ 渲染为金奶油粗体纯文字挂线。
  - **二级 = 核心观点·双层节点**(每一级 2-4 个,全图 8-12 个):`topic` = **概念关键词/短语 ≤10 字**(扫读层,禁「第N章」式零信息 / 通用容器词,取消 ≥8 字下限)→ 渲染为米白关键词;`tags[0]` = **可反驳判断句 ≥8 字且 ≤18 字**(细读层)→ 渲染为关键词下方浅青小字;`tags[1]` = 「第N章」→ 渲染为极简描边章码 chip;挂 `hyperLink:'#ch-N'` 承载章码传送门,`#ch-N` 与 `.bd-chapter id="ch-N"` 对齐,**整个二级块可点跳章**;**一章可拆多个二级**。`expanded` 字段透传保留但 **SVG 版默认全展开**(不折叠,靠 viewBox 缩放看全图,见 §5.2)。
  - **三级 = 支撑**(每个二级 ≤4 个,只收三类,排序固定 🧠→💡→⚖️):🧠 机制/心智模型、💡 核心概念、⚖️ 决策规则(当X→做Y)。**动宾/名词短语 ≤14 字,禁冒号双段式**;emoji 前缀承载类型。
  - **四级 = 📖 案例 / 📚 外部书**(真四级,挂到它直接证明的那条支撑之下,无所属支撑的案例可直挂二级末位):📖 = 专名短语 ≤12 字(挂 narrative/excerpts 招牌真事,细节不进图);📚 = 书名 + ≤6 字关系词(挂二级最末位,每二级 ≤1,只用 enrich 真实书目)。每叶子带 `_src`(章锚点或书名)--**溯源用,生成器原样忽略;verify 亦忽略未知字段**。
  - 同一概念不同说法(归属感 / 被接纳、概念条 vs 规则条)**归并为一个节点**,不在多枝重复。
- **~~`arrows` / `summaries`~~(已废)**:SVG 版**不画任何跨枝关联箭头、不画收纳组虚线**(sandy 诉求:去掉所有关联虚线)。生成器读到也忽略;写作时**不再产出这两键**(留着只增体积、无渲染效果)。

### 5.2 硬约束

- **全展开 + viewBox 缩放(清爽靠矢量缩放,不靠折叠)**:SVG 版一次画全 4 级,清爽由 viewBox viewer 承担——默认 `fit()` 铺满容器居中,滚轮/双指连续指数缩放(光标锚点)、拖动平移、双击复位;**矢量放大任意倍率不糊**(每次浏览器重新光栅化 viewBox,非 `transform:scale` 位图放大)。`expanded:false` 在 SVG 版是透传无效字段(保留兼容旧数据,不驱动折叠)。
- **二级双层节点样式(反 slop)**:二级渲染为「米白关键词(`--mm-ink`,15px 粗)+ 下方浅青判断句(`--mm-judge`,11.5px)+ 极简描边章码 chip(`--mm-chip-*`)」三层挂在同一条引线末端,纯文字不套外框;判断句是细读层、章码 chip 是传送门可见性入口。
- **传送门 = 二级整块可点**:二级节点带 `<a class="jump" href="#ch-N">` 包裹(含一层透明 hit-rect 放大点触靶);点击(非拖动)→ `location.hash = '#ch-N'` → 复用 `initHashRouter`(切 `panel-full` + 展开该章 + 滚动 + 高亮)。章码 chip 显式标出「点我去第 N 章」。
- **只画父子引线,不画关联**:引线是父→子的直角肘形梳齿(父出一段 stub → 竖脊 → 每子一齿),`--mm-line` 淡青灰细线 + `shape-rendering:crispEdges`;**全图无任何跨枝关联箭头、无收纳组框/虚线**。
- **一级分支覆盖章区段**:各分支下 `#ch-N`(落二级)的并集 = 全书章号(method §4.6 自检)。verify 门禁①:每个一级分支至少有一个 hyperLink 节点。
- **锚点必须真实存在**:每个 `hyperLink:'#ch-N'` 的 `#ch-N` 必须有对应 `id="ch-N"`(手风琴章节),否则点了跳空;verify 门禁②拦死链。
- **深色画布 + 上下留白过渡**:嵌入页面态,`#bd-mindmap` 是深墨绿圆角画布(点阵磨砂纹 + 极缓径向渐变 + 软投影),嵌在纸底浅色页里不生硬贴边;点「⤢ 全屏」→ `.bd-mindmap-wrap.mm-fullscreen`(`position:fixed;inset:0`)进纯深色聚焦态,ESC/再点退出,进出后重新 `fit()`。
- **配色走一套 dark token(零 hex)**:脑图恒深色、**不随页面主题**(`__bdMindmapRetheme` 为 no-op)。深色配色定义为 `:root` 里一套 `--mm-*` token(`--mm-bg/-ink/-sec/-judge/-line/-root-fill/-chip-*/-accent …`),组件 CSS 只用 `var(--mm-*)`;SVG 生成器经 `getComputedStyle` 读**同一套** `--mm-*`(单一来源),JS 里的 hex 仅作 fallback 兜底。CSS 零 hex(HEX_RE 只扫 `<style>`,`<script>` 内 hex 不入门禁)。
- **verify 门禁(自绘 SVG 版)**:静态 `lint_mindmap` 审 nodeData 树 —— ① 一级分支挂 hyperLink 叶子;② `#ch-N` 不死链;③ 二级缺 `tags[0]` 或 `tags[0]` 有效长 <8 字拦截;④ 全图 topic 总字数 >900 拦截(arrows/summaries 相关门禁随字段作废一并删除)。**SVG 结构断言**(脑图区真出 `<svg>`、文字节点数达标、**无关联箭头元素**、`window.__mm` viewer 已跑、`mm-stage` 走 viewBox 非 transform、点二级真跳章)由 Playwright 冒烟 `smoke()` 断。per-node 分级字数(≤10/≤14/≤12)靠蒸馏自查 + 冒烟,不进硬门禁。

范例(结构示意,《陪孩子终身成长》·双层知识树;`arrows`/`summaries` 已废,不再出现):
```json
{
  "layout": "chapter-span",
  "nodeData": { "id": "root", "topic": "陪孩子终身成长", "root": true, "children": [
    { "id": "p1", "topic": "① 问题的根源 · 第1-2章", "children": [
      { "id": "v1", "topic": "关系母版", "tags": ["亲子关系是孩子与世界所有关系的母版", "第1章"],
        "hyperLink": "#ch-1", "children": [
        { "id": "v1-m", "topic": "🧠 复印件-原件模型", "_src": "第1章·mental_model", "children": [
          { "id": "v1-m-c1", "topic": "📖 剪牛仔裤的女会员", "_src": "第1章·narrative" } ] },
        { "id": "v1-c", "topic": "📖 3000万词汇差距实验", "_src": "第1章·narrative" },
        { "id": "v1-x", "topic": "📚《教养的迷思》·反驳", "_src": "enrich·similar_page·反驳" } ] } ] } ] }
}
```
> 二级 `topic` 是概念关键词、判断句落 `tags[0]`、章码落 `tags[1]`;整个二级块 `<a href="#ch-1">` 可点跳章。全图无 arrows/summaries。

### 5.3 移动端脑图可用性(≤880px)

- **靠 viewBox 缩放看全图**:窄屏不折叠,`fit()` 先铺满居中,双指 pinch 连续缩放(触点中点为锚)、单指拖动平移、双击复位;`touch-action:none` + `user-select:none` 保证拖动顺滑不选中。
- **一次性触摸提示**:画布内 `.mm-hint` 首次自动淡出(触屏文案「双指缩放 · 单指拖动 · 双击复位」),`pointerdown` 即隐。
- **全屏查看**:工具栏「⤢ 全屏」→ `.bd-mindmap-wrap.mm-fullscreen`(纯深色铺满),ESC / 再点退出,进出后重新 `fit()`。
- **点触靶放大**:二级 `<a class="jump">` 内含透明 hit-rect(节点块 +4px)扩大触摸目标。

---

## 6. 单文件与体积预算(≤3MB)+ extract 兼容

- **交互脚本勿动,无 vendor**:`</main>` 之后是**纯自写**交互 `<script>`(含 `initTabs`/`initThemes`/`initChain`/`initSubBack`/`initHashRouter`/`initMindmap`[自绘 SVG 脑图生成器 + viewBox viewer]/目录态与传送门逻辑);这些块勿删勿改勿重排。脑图**不再有任何 vendor 依赖**(mind-elixir/markmap/d3 全部移除)。
- **体积账**:verify 上限 **≤3MB**。自绘 SVG 脑图为纯 JS(几 KB,较 mind-elixir 单件再省 ~69KB,较旧 markmap 三件套省 ~650KB);详实正文预估 1.5-2.5MB。留给正文净预算约 ≤2.8MB(含 base64 封面)。
- **超预算合法裁法**:① 删净 dummy / 未用槽位;② 先压 excerpts,再压封面图(WebP data URI / 降尺寸),再收紧啰嗦 lede / section-lead;③ 仍超再报 sandy。**禁**删 vendor / 删必需区块 / 删 `data-source` / 压 narrative 跌破 G9。
- **零外链**:所有 `<script src>` / `<link href>` / `<img src>` 不得指向 `http(s)://`;图片一律 `data:` 内联;引用出处 `<a href>` 是唯一允许外链。
- **extract 兼容三条(勿破坏)**:① 页面 JS 全包在一个 IIFE 内,init 幂等(`main[data-bd-ready]` 守卫);② 初始化挂 `astro:page-load` + `DOMContentLoaded` 双时机;③ CSS 可被 `@scope(.bk-wrap)` 包裹,token 块保持 `:root{}` / `body[data-theme=…]{}` 标准形态,子视图 `.subpage{position:fixed}` 上站后仍全屏覆盖。

---

## 7. 注意事项(已知坑)

- **verify 的 `HEX_RE` 会误伤「hex 形状」的 CSS 标识符**:`url(#fade)`、`#abc123` 形状的 id / fragment 可能被当硬编码色。命名一律避开纯 hex 形状(`#bd-mindmap` / `#ch-N` / `#sub-author` / `#au-life` 等安全,别改成 `#a1b2c3`)。
- **脑图深色配色走 `--mm-*` token,零 hex**:自绘 SVG 脑图恒深色,配色在 `:root` 定义一套 `--mm-*` dark token(主题无关),组件 CSS 只用 `var(--mm-*)`;SVG 生成器经 `getComputedStyle` 读同一套 token(单一来源),JS 内 hex 仅 fallback(`<script>` 不入零-hex 门禁)。**注**:`data-vendor` 零-hex 豁免机制仍在 verify 里(通用,未来任何 vendor CSS 可用),当前无 vendor 触发它。
- **内联 `style="…"` 里的 hex 属规范违规**(即便 lint 扫不到):evidence_level 色点、soul curve `sc-line` 换色一律走 `data-*` 属性 + CSS `var(--*)`,禁内联 hex。
- **token 块写法**:块内只放声明,不嵌套 `{}`,注释里不出现右花括号 `}`;主题组件微调(带后代选择器)不算 token 块,内部禁 hex。
- **主题 picker = 触发按钮 + 竖列弹层,非默认主题在前**:`brand-dark` 第一位、`warm-paper` 靠后;verify 先点 `.tp-trigger` 开弹层再点某主题项断言背景变化。
- **子视图 `.subpage` 的 `hidden` 属性别删**:hash 路由靠它开合;2 个子视图默认全 hidden。
- **删可降级块后 data-source 可能跌破 20**:删完复跑,不足回补 anchor,别塞空 `data-source`。

---

## V. 视频系列填槽差异(source_type = video_series)

蒸视频系列时,**五 tab / panel id / 板块顺序 / 签名 class / SLOT / 降级 / 体积 / extract 全部不变**(与书籍同骨架);下表未列的区块 = 与书籍填法完全一致。**核心铁律:跳转一律 `<a href target="_blank" rel="noopener">` 新开原平台,禁 `<iframe>`/`<video>`/`<embed>`(verify 拦)。**

| 区块 | 视频页差异 |
|---|---|
| **头部刊头** | `.cb-cover`=系列封面(首集缩略图 `data:` URI,16:9 放 3:4 框用 `object-fit:cover`);`.cb-author`={UP主/频道名};`.cb-kicker`=平台 + 题材(「YouTube · AI 编程系列」);`.cb-intro`=`cover_intro`(视频必产)。hero 作者名链 → **频道页** |
| **①脑图 / ②手风琴** | 二级节点 / 章=主题段;`.bd-chapter>h3`=论点式主题段标题(G8 检,黑名单含 `视频\d+`);narrative ≥400 字/段;`.excerpt`=讲者原话段(繁体照录,视频可 0);章内跳转链 `<a href="{解析URL}" target="_blank" rel="noopener">▶ 看原视频</a>`(anchor→URL 按 §V.1) |
| **②金句墙** | `figcaption` 出处=`视频N · MM:SS`(繁体照录);金句可整条包跳转 `<a target="_blank" rel="noopener">` |
| **③书评** | → 观众评论(`reviews` 视频变体):`.review-item` 的 `.stance` + `.r-src href="{视频URL}"`;有 `likes` 前缀 `👍{likes}`;正反据实(全好评如实全正) |
| **③裁决条** | `credibility_verdict` 视频可省 → 省则裁决条只留分或整块删(§1.2.3 降级) |
| **⑤ / 子视图** | `#sub-author`=**频道页**(`media_type:"video"`:S5 栏名「主要作品与系列」、`works`=同频道其他代表系列、`known_for`=频道名、`photo`=频道头像、`birth` 常缺→行删);⑤同类书=同类频道/系列;`#sub-views`=观点对比(评论区实质观点 + 外部看法) |
| **footer** | 声明「AI 蒸馏是地图…**回原视频**细看」;书名 / 作者位=系列标题 / UP主 |

### V.1 anchor → 跳转 URL 解析规则(填章内 / 金句跳转链时用)

distill 视频 anchor 两式,渲染 `<a href>` 时按下表解析(`videos[]` 里按 `no` 查该集 `url` 与 `platform`):

| anchor 形态 | 解析为 href |
|---|---|
| `视频N`(无时间码) | 该集**裸 url** |
| `视频N·MM:SS`(或 `视频N·H:MM:SS`) | 该集 url + 时间参数,定位到 `MM:SS` 换算的**总秒数** |

时间参数按 `platform`:`youtube`→`&t={秒}s`(无 `?` 则 `?t={秒}s`);`bilibili`→`?t={秒}`(有 `?` 则 `&t={秒}`);`douyin`→裸 url。链接**文案**用 anchor 原文(如 `视频3 · 12:30`);一律 `target="_blank" rel="noopener"`。

### V.2 data-source 语义不变

视频页 `data-source` 属性值仍是 **anchor 原文文本**(`视频3` / `视频3·12:30`),**不是** URL -- 溯源定位文字,由 `.src-note` 常显,与书籍一致;URL 只出现在 `<a href>` 跳转链。verify 的 `data-source ≥20` 照检。

### V.3 D 视频试点固化:双语 / 热度条 / 概念中英 / 去书味(骨架 CSS 已内置)

Dan Koe 出片(外语视频)三特性,填 `distill` 对应键即渲染(schema 见 `method.md §6.2` 尾注),缺键整块降级:

| 特性 | 渲染 | 填法 |
|---|---|---|
| **双语引用** | 英文原话 `<blockquote>` 原样照录 + 其下 `<p class="qw-zh">` 中文译 | `quotes[].text_zh` / `chapters[].excerpts[].text_zh`(外语视频补;中文视频省 → 不出 `.qw-zh`)。**红线:英文原话只进 `text`、不改写;中文只进 `text_zh`** |
| **热度条(替豆瓣评分)** | ③书评/裁决区顶 `.vb-heat`:「频道 {channel} · {followers} 粉 · 系列 {total_views} 播放 · 截至 {as_of}」 | `series_stats`;抓不到 → null → `.vb-heat` 整块删,不留占位 |
| **概念中英** | 概念筹码/卡的中文名后接 `<span class="cc-en">{concept_en}</span>` | `concepts[].concept_en`(外语视频**逐条**补;书籍侧默认全中文,只国际信号词点缀) |

**去残留书味(视频硬项,verify 不机检、生成时自查)**:① tab② 副标题「一章一章读」→「**一段一段看**」(tab 主名仍是硬契约 T5,不动);② 章尾预告卡 / `action_chain` 里「读 / 翻页 / 回原书」→「看 / 回原视频」;③ `.cb-kicker` 平台+题材(「YouTube · AI 编程系列」)。**判据:通读一遍页面,凡把视频当"书"称呼的书面动词都改**。

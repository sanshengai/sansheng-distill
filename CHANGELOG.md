# Changelog

本项目的变更记录。版本号遵循 [semver](https://semver.org/lang/zh-CN/)。

## [未发布]

补三道**未填槽门禁**、一道**批量交付闸**,并新增轻量模型执行卡 -- 让 Gemini Flash 级模型 / 弱 agent 客户端也能按本 skill 的标准产出合格蒸馏页。

### 追加：原文事实门禁（2026-07-28）

一次格拉德威尔重蒸复核发现，旧页面即使通过结构检查，仍可能出现原文不存在的摘录、章节锚点错位，以及把同一段正文复制到多个章节凑字数。根因是 `verify_page.py` 只校验页面与 JSON 契约，没有把产物反查回用户提供的原文。

**新增**

- `verify_page.py --source <book.txt>`：与 `--distill` 联用时，逐条核验摘录去空白后的逐字命中、章节锚点是否指向该书真实章节，并拦截跨章节重复的 ≥120 字正文。
- 补齐同章注水与结构盲区：拦截 `narrative` 内重复的 ≥40 字句、读者可见的编辑流程语；顶层 `quotes` 也必须逐字命中原文；`尾声` 成为合法锚点。文章选编每篇须带并命中 `source_title`，从结构上阻止篇名—正文错配；文章选编新增 `render_profile.archetype="文章选编"`，采用 ≥300 字的独立篇目阈值，避免用论说书的 800 字硬门槛诱发凑字。
- Step7 的标准命令与交付条件已改为必须带 `--source`；没有原文就不能把页面标为完成。
- 三个回归用例覆盖：伪造摘录、虚构章节锚点、跨章重复正文。

**验证**：全量 `python -m pytest` 为 **288 passed**。

缘起是 2026-07-26 一次用 Antigravity(Gemini 3.6 Flash)蒸 6 本书的实测事故:5 分钟跑完、全部上站,事后核查发现 2 本只跑到 Step0 就停了(线上 404)、4 本 HTML 各残留 68 处 `{{槽}}` + 36 处 dummy、封面全是占位 SVG、distill.json 缺 8 个顶层键 —— **其中 1 本 `verify_page.py` 报 exit 0「全部通过」**。

根因不是模型写不出好内容(同批《异类》narrative 写到 824-1119 字,达标),而是**旧门禁 174 项全部是「遍历已有字段校验取值」**,默认「一定会填槽、一定会产全 schema」。模型把模板原样交付或少产半个 schema 时,循环空转 = 零违规放行。这三道补盲门与模型强弱无关,对所有模型同等生效。

**新增**
- **T0-P 未填槽门禁**(`lint_no_placeholder`,恒校验):成品页残留 `{{槽}}` 或 dummy 示例文案即 exit 1。`{{槽}}` 全文查;dummy **先剥 HTML 注释再查** —— 骨架顶部那条用法说明注释本身含「删 dummy/占位」字样、正常交付页普遍保留(全库 51 本里 47 本有,不渲染无危害),不剥会 100% 误报。校验 `templates/` 下的骨架模板时传 `lint_html(..., allow_placeholder=True)` 豁免。
- **T0-S schema 完整性门禁**(`lint_distill_schema`,恒校验):`method.md §6` 的 21 个顶层必需键缺失即 exit 1。空容器(`"quotes": []`)等同缺失;条件必需键按 `render_profile.omit_blocks` 豁免(语录/书单/课程/考试型);视频系列豁免 `concepts`/`credibility_verdict`。自造近义键名会被点名纠错(实测出现过把 `title` 写成 `book_title`)。**门禁在 `verify_pass1.py` 同样生效 —— 问题在 Pass1 就被拦下,不会一路带到 HTML。**
- **T0-C 真封面门禁**:占位 SVG(`data:image/svg+xml`)不再算合格封面。旧检查只查 `src^="data:image"`,占位 SVG 天然满足、形同虚设(全库正常蒸馏封面均为 jpeg/png/webp)。确实联网拿不到,须在 distill.json 顶层显式写 `"cover_fallback": true`,不许静默降级。
- **`scripts/verify_batch.py` 批量交付闸**(硬门禁④):上站前把**预期名单显式**交给它核对 —— 逐本核产物齐备 / `verify_page.py` 退出码 / 交付卫生(enrich 缺失、`_pass2_g*.json` 中间态残留),exit 0 才许上站。单本 verify 只回答「这一本合不合格」,回答不了「这一批该有的都在吗」;靠人肉数「应该都蒸完了吧」正是漏掉 2 本仍上站的病因。
- **`references/flash-mode.md` 轻量模型执行卡**:不降低任何质量标准,只把「靠自觉」的环节换成「可自检的判据」,逐步给完成判据与自检命令,并钉死六个最易滑落点(跳 Step7 / 槽没填完 / schema 少产 / 章数归并 / narrative 写到 300 字就收 / 少蒸的书仍进名单)。SKILL.md 顶部加指引。
- **Step0 目录识别门**(硬门禁①补充):`toc_detected: false` / `chapters_detected: 1` 也要停下问用户 —— 目录没识别出来 = 模型手里没有原书章节划分,章数只能自由发挥。
- **`convert_book.py` 支持套装/合集 epub 切分册**(`--list-volumes` / `--volume`):这正是上述「章数一律 6 章」的根因 —— 6 本全切自同一个「套装共5册」epub,而旧 `extract_epub` **完全不读 TOC**(把所有 ITEM_DOCUMENT 一股脑拼起来)、`diagnose` 又只用正文启发式正则猜章节。现改为:按 TOC 顶层定分册、按 **spine 区间**取正文(未列入目录的正文续页也收进来 —— 只取 TOC 列出的篇目会静默丢正文)、`title` 自动取分册名;`diagnose` 章数改**两路取大**(正文正则 vs TOC 声明)并新增 `chapters_source` 字段标明来源。真实套装 epub 实测:5 个分册全部正确识别与切分,标志词高频命中(盖蒂 29 / 薄片分析 33 / 肯纳 72)、跨书串扰零命中(一万小时 0 / 披头士 0)。

**测试**
- 新增 47 个单测(`scripts/tests/test_flash_gates.py` 37 + `test_convert_volume.py` 10):三道门禁的正反用例、omit_blocks / 视频豁免、别名纠错、注释豁免边界,以及一条复刻实测事故形态的回归断言。
- 全库回归:51 本已交付蒸馏页扫描,新门禁**零误报** —— 精确命中且仅命中 4 本问题产物。
- 测试基线 238 → **285 passed**。

**兼容性**
- `[schema]` 项对 2026-07-27 之前蒸的旧书会报 `render_profile`/`cover_intro` 等缺失,**属预期,旧书不必重蒸**(与既有 legacy 向后兼容策略一致)。T0-P / T0-C 两道对旧书零影响(实测 47 本全过)。

### 追加：富交互壳保真门禁（2026-07-28）

格拉德威尔重蒸复核发现，临时渲染器虽然能把 JSON 填进 HTML，也能通过旧版静态检查，却把正式骨架的主题切换、自绘脑图 viewer 与 hash 路由整段丢掉，形成“内容表面正确、阅读体验被降级”的隐蔽回归。

- verify_page.py 在传入 --distill 的单书页上新增富交互壳断言：必须保留 .theme-picker、initMindmap()、initHashRouter() 与脑图缩放控制；极简重写器直接 exit 1。
- Step6/Step7 明确：必须复制并逐槽填 page-skeleton.html，不能另造简壳来替代正式页面。
- 回归测试新增“数据页拒绝极简壳”；全量测试基线由 288 → 294 passed。

## [0.4.1] -- 2026-07-22

### 改进

- **触发边界更准确**：压缩自动触发描述，明确一本书全文、单集视频与视频系列均可进入深度蒸馏；只要字幕摘要、普通文章写作和「一页」专项不误触发。

## [0.4.0] -- 2026-07-15

新增 **StepB 主题聚合** -- 把同一主题下 ≥3 本已蒸作品横向重组成一张「分类地图 + 分歧矩阵 + 维度对照表 + 书目导航」的主题聚合页。这是继 StepA 作者演变(时间轴)之后的空间轴对称能力:StepA 看「一个作者怎么变」,StepB 看「一群书在同一议题上站哪边」。缘起是婴幼儿睡眠 13 本蒸馏 → 合成专题文的复盘 -- 手工把 13 本归成 7 派、挖出 3 条真分歧的活,值得沉淀成可复用的一步。

**新增**
- **StepB 管线 + `build_topic.py` 聚合器**:只读各书 distill.json + knowledge-index.json 做确定性集合运算(禁 LLM/联网),合并人工 `topic.manual.json`(流派归类/分歧分组/维度定义/怎么选)聚合成 topic.json。成员靠 `members:[slug]` 显式圈定;有效成员 <3 → exit 3 触发门槛;manual 缺失且 out 已存在 → 防覆盖栏 exit 2。
- **主题聚合页 4 视图**:分类地图(流派分区卡)/ 分歧矩阵(多列立场对照)/ 维度对照表(各书可执行数字并排、每格标 certainty 来源硬度)/ 书目导航。纯 HTML+CSS 表格卡片,不套 StepA 的坐标系 SVG,复用蒸馏页同源 token 与 Zero-Hex 铁律。
- **分歧诚实三档 `index_relation`**:`CONTRADICTS`(knowledge-index 已登记真对立,红旗)/ `curated`(编者从各书立场归纳、index 未登记,金标,须给依据)/ `parallel`(松散并列,聚合器剔除不渲)。把「index 往往只登记了少数 CONTRADICTS,但一个主题常有多条真分歧」这个现实如实呈现,而非硬造对立;编者归纳出 index 未登记的分歧应回补进 knowledge-index(顺带修 Step4 跨书分歧判定偏保守)。
- **每书页「主题入口卡」`SLOT:TOPIC-ENTRY`**:成员书蒸馏页顶部链到主题全景,<3 本或无 topic.json 生成时整卡删(可与作者演变入口卡并存)。
- **verify 独立门禁**:`is_topic_page` / `lint_topic_html` / `topic_smoke`(4 视图齐 / 零外链 / Zero-Hex / lang=zh / 破折号 / 深链格式 / 成员 ≥3 / index_relation + certainty 枚举 / 分歧可回指 / 渲染冒烟),照作者页那套对称加,走 main 短路分支绕开蒸馏页 REQUIRED_CLASSES。
- **契约 `references/topic-craft.md`**:topic.json schema / 4 视图数据契约 / 事实 vs 归纳分层铁律 / 成员圈定 / enrich 外部争议 / 入口卡,作为 build_topic + skeleton + verify 三者的单一权威。SKILL.md 管线表补 StepB 段(对称 StepA)。

**测试**
- 新增 26 个单测(15 topic 门禁 + 11 build_topic 聚合),覆盖 index_relation 三档判定、certainty 拉取/校验、门槛/防覆盖、破折号 quote 豁免、骨架静态门禁。clean-env pytest 全绿(238 passed)。

## [0.3.0] -- 2026-07-15

给「读者会照着做」的高后果书（育儿 / 医疗 / 理财…）加一层**数字可信度标注**，并把蒸馏产物的清理与验证边界写清楚。缘起是一次婴幼儿睡眠 13 本蒸馏 → 合成专题文的复盘：蒸馏本身很忠实，但下游引用时分不清哪些数字是「书里白纸黑字」、哪些是「编者补的通识」。

**新增**
- **后果轴 `stakes`（`high` / `normal`）**：与书型 / render_profile 正交的第三根轴，标记「读者照做、数字错会误导」的高后果书（育儿 / 医疗 / 用药 / 投资仓位 / 法律…）。缺省 `normal`，旧蒸馏无需回填。
- **可执行数字确定性 `certainty`**：`decision_rules[]` 与 `core_ideas[]` 元素级新字段，三值 `book_explicit`（书里白纸黑字）/ `cross_book_synthesis`（跨书合成）/ `general_knowledge`（编者通识），让下游一眼分清数字来源硬度；与 `evidence_level`（转述忠实度）正交共存。
- **门禁 G22**：`stakes=high` 时 `decision_rules` / `core_ideas` 每条必带合法 `certainty`（独立 stakes 闸，不随 render_profile；`normal` 书不检）。渲染侧复用 `.ci-evlevel` 色点，为决策卡加 `.rc-certainty` 来源硬度徽标。
- **G7 `evidence_level` 机检补齐**：`core_ideas` 必带 `evidence_level` 从「蒸馏自查」升为「verify 机检」。

**改进**
- **Pass2 中间态自动清理**：合并完整性门禁通过后删 `_pass2_g*.json`（已 gitignore、已回填 distill），治历史残留污染目录。
- **verify 边界澄清**：文档写清 `verify_page.py exit 0 ≠ 事实正确` -- 只保结构 / 契约 / 版权长度；内容真伪靠蒸馏自查 + 高后果书人工回原书抽检数字。

**修复**
- SKILL.md 硬门禁②的门禁编号从陈旧的 G1-G15 校正到 G1-G22。

## [0.2.0] -- 2026-07-12

这一版让蒸馏**按书型走不同形态**，并把批量蒸馏的成本压在编排上、而非砍内容深度。

**新增**
- **书型自适应 render_profile**：8 种书型原型（论说 / 叙事 / 人物 / 工具 / 语录 / 书单 / 课程 / 考试），按书型自动选输出形态与门禁档位 -- 语录书走语录墙、书单书走书单卡、课程 / 考试书走知识点树 + 考点卡，不再对所有书死搬同一套五段式。**向后兼容**：未标注书型的旧蒸馏页按原全门禁校验，无需重蒸。
- **4 类新原型页面原语**：语录墙 `.quote-board`、书单卡 `.booklist-cards`、知识点树 `.kp-tree`、考点卡 / 例题解析 / 记忆卡（`.exam-point` / `.worked-example` / `.recall-card`）。
- **门禁 Tier-0 / Tier-1 分层**：底线门禁（锚点 / 零外链 / 出处常显…）永不放宽；形态门禁（字数档 / 书魂 / 行动链…）随书型注册表变。verify 加书型完整性校验，防「自造书型 / 篡改 active_gates 偷绕门禁」。
- **批量编排效率规约**：跨会话并发闸（全局在飞 Pass2 subagent ≤ 6-8）、1 本书 = 1 会话防反复 compact、批前 token 预算、失败先核盘再定点 gap-fill（防假重跑）、Pass2 产物统一 `_pass2_gN.json` 命名、同作者 enrich 只搜一次。
- **Pass1 独立门禁** `verify_pass1.py`：骨架阶段即校验，UTF-8 控制台守卫修 GBK 假失败。
- **作者演变辅助脚本** `merge_enrich.py` / `merge_pass2.py`（数据根目录走 `DISTILL_DATA_DIR`）。

**修复**
- 兄弟 skill `sansheng-gemini-video` 链接改为完整 GitHub URL（独立扁平仓不再用 monorepo 相对路径）。
- 测试骨架路径按扁平仓结构修正（`parents[2] / templates`），clean-env pytest 全绿（208 passed）。

## [0.1.0] -- 2026-07-08

把一本书蒸成一张**能点、能跳、越读越厚**的交互网页 -- 脑图可点跳、章节可展开、7 主题切换、读完回看的自检问句，单文件 `file://` 直接打开。

**这一版包含：**
- 八步蒸馏管线：入书诊断 → 书型判定 → 四源融合蒸馏 → 联网增补 → 跨书索引 → 设计两遍工作法 → 单文件 HTML → 出厂验证
- 两类输入：书籍电子全文（epub / pdf / txt / azw3 / mobi），以及视频系列（每集当章节）
- 跨书概念索引：越蒸越厚的个人知识网络，新书自动与旧书互链
- 产出为零外链单文件 HTML，可离线 `file://` 打开

装法与网页演示见 README。这是叁笙自己每天在用、清洗脱敏后开源的 Claude Code 技能。

[0.4.0]: https://github.com/sandypoli-boop/sansheng-distill/releases/tag/v0.4.0
[0.3.0]: https://github.com/sandypoli-boop/sansheng-distill/releases/tag/v0.3.0
[0.1.0]: https://github.com/sandypoli-boop/sansheng-distill/releases/tag/v0.1.0

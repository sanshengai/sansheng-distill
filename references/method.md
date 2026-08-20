# 四源融合蒸馏方法论 -- Step1 书型判定 + Step2 蒸馏手册(sansheng-distill)

> **执行手册,不是理论文**。管线跑到 Step1/Step2 时 agent 逐节照做,产出唯一主对象 `distill.json`。
> 基底 = 58 号项目「四源融合版」(投资 15 本 + 育儿 33 本两轮验证):李继刚 xray 三轮压缩为主干,嫁接 book-to-webpage 的出处标注/决策规则、nuwa 的心智模型/内在张力、仓颉的批判段;新增书型判定前置、证据等级、质量门禁。
> **核心理念**:知识档案(distill.json)是主对象,HTML 是投影 -- 蒸的是结构化知识,不是直接写页面。
> 全文破折号一律 `--`;门禁/门槛全部给可判定标准(数字/枚举),不用「酌情」「适当」。

---

## 0. 前置:消费入书诊断(diagnose.json)

诊断细则(页数/可提取性/扫描判定/乱码率/目录识别)由 Step0 `convert_book.py` 产出 `diagnose.json`,**本手册不重做诊断,只消费 4 个字段**:

| 字段 | 类型 | 本手册用途 |
|---|---|---|
| `recommendation` | `直接蒸馏\|分组蒸馏\|需OCR\|需人工确认` | 决定进 §1 还是走 §8 或退回 |
| `pages_est` | int | §5 页码估算的分母之一(缺失时 anchor 省略页码) |
| `chars` | int | §5 页码估算的分母(字符总数) |
| `garbled_ratio` | float | §5 判 `evidence_level` 是否降到「需复核」 |

`recommendation` 分流(硬规则,不许自作主张):

| recommendation | 处置 |
|---|---|
| `直接蒸馏` | 进 §1 全书一次性蒸馏 |
| `分组蒸馏` | 进 §1 定书型后,Step2 走 §8 分组流程(禁一次性硬吞) |
| `需OCR` / `需人工确认` | **本手册不启动**,退回 Step0 报告扫描版/需人工;不硬读、不编内容 |

> **`toc_detected` / `chapters_detected` 是启发式信号,不消费、不作门槛**:convert_book.py 靠章头正则统计,对「第N章/N. 标题/Chapter N/罗马数字章」等规整版式召回好;但**意译短标题的外版书**(如《投资最重要的事》《聪明的投资者》,章名是「最重要的事是二阶思维」这类短语、不带任何章号)会偏低甚至 `chapters_detected=1 / toc_detected=false`。**这不阻断蒸馏**:章节以 §1 全书通读提炼为准(§6 `chapters[]` 手工锚定),diagnose 的两字段仅供参考,别据它判「这本书没有章节」而降级。

---

## 1. Step1:书型判定(定权重与硬门槛)

### 1.1 四型判定特征

读 `diagnose.json` 目录 + 全书抽样(首章 + 中段 + 末章各扫一遍),按**主导特征**归一型:

| 书型 | 判定特征(主导即判) | 典型 |
|---|---|---|
| **论说** | 以命题 + 论证为主轴,章节围绕观点展开,大量「因为/所以/证据」;核心是一套 idea 体系 | 《思考,快与慢》《投资最重要的事》 |
| **叙事** | 以故事/案例/时间线推进,人物 + 情节 + 转折,靠故事传达道理 | 商业纪实、传记式案例、纪实文学 |
| **人物** | 全书是某一思想家的观点/语录/思维方式,蒸的是「他怎么想」 | 《穷查理宝典》《巴菲特致股东的信》 |
| **工具** | 以方法/步骤/操作/清单为主,大量「怎么做」 | 《手把手教你读财报》 |

### 1.2 混合型裁决(边界模糊时按序判,命中即停)

1. 删掉书里的人名/主角,还认得出是「某一个人的思维方式」吗?→ 认得出判 **人物**
2. 主要在教「怎么一步步做」(步骤/清单/规则占主体)?→ 是判 **工具**
3. 主要靠故事/案例的戏剧性承载道理?→ 是判 **叙事**
4. 以上都不是 → **论说**(默认兜底)

> 传记但重在提炼思维 → 人物(不判叙事);案例集但重在论证观点 → 论说(不判叙事)。书型写入 `distill.json.book_type`。

### 1.3 四型权重与硬门槛(打回线)

书型只调**加重字段 + 硬门槛**,不改四源融合的骨架(每型都要跑满三轮 + 四嫁接件):

| 书型 | 加重字段 | 硬门槛(未达 = §7 打回) | 放宽 |
|---|---|---|---|
| **论说** | `core_ideas` + `arguments` | `core_ideas`≥6;`arguments` 三件齐(chain + hidden_assumptions + counter_examples) | `decision_rules`/`mental_models`/`narrative_arcs` 按书自然产出,不设高门槛 |
| **叙事** | `narrative_arcs` | `narrative_arcs`≥3,且每条以 **3-5 句短叙事**保留戏剧弧光(禁压成标签,判定见 §7) | `decision_rules` 可少 |
| **人物** | `mental_models` + `tensions` | `mental_models`≥5 且**每条过 nuwa 三重验证**(§4.2);`tensions`≥2(防扁平圣人) | `chapters` summary 可略 |
| **工具** | `decision_rules` | `decision_rules`≥8,每条 `when/do/because/anchor` 齐全且 `do` 可执行 | `tensions`/`narrative_arcs` 可少 |

> 通用底线(所有书型):`tensions`≥2、批判段四件套齐(§4.4)、每条 `core_ideas`/`decision_rules`/`quotes` 带 anchor -- 见 §7。

### 1.4 render_profile:书型 → 输出形态(v6,2026-07-12 B-1)

§1.1-1.3 判出 `book_type` 后,**Step1 再产一个 `render_profile` 写入 `distill.json` 顶层**,把书型从「只调门槛」升到「**驱动输出形态**」(tab 组合 / 区块取舍 / 字数策略 / 生效门禁)。这是 v6 治「所有书硬套五段漏斗」的总闸。

> **为什么**:2026-07-12 五作者约 20 本复盘实测——book_type 判了却不改骨架(§1.3),34 本里 24 本塌成「论说」、KK《宝贵人生建议》箴言体被塞 22 章×878 字讲书稿(注水,违反自己的 G1)。而「按轴变体化门禁」的机制视频路径(§V)早有(G9 按 `source_type` 取 800/400),把它键到「书型轴」即可,是机械泛化非新架构。

**8 型注册表**(`verify_page.py` 的 `RENDER_PROFILES` 是**权威镜像**,改此表必同步改脚本,否则 verify 拦篡改):

| archetype | narrative_mode | 省略区块 omit_blocks | 生效 Tier-1 门禁 active_gates | 新原语 primitives | tabs |
|---|---|---|---|---|---|
| **论说/叙事/人物/工具**(legacy) | full-800 | (无) | 全 Tier-1 | (无) | 全 5 |
| **语录**(箴言/格言/清单) | list | soul-block/arg-restate/rules/models/questions/verdict-bar | G16 | 语录墙 | glance/full/extend |
| **书单**(荐书/书目导览) | list | 上 + bd-napkin | (无) | 书单卡 | glance/full/extend |
| **课程**(教材/培训) | dense-card | soul-block/arg-restate | G9,G13 | 知识点树/练习卡 | glance/full/action/extend |
| **考试**(备考/考点) | dense-card | 上 | G9 | 考点卡/例题解析/记忆卡 | glance/full/extend |

schema(distill.json 顶层,Step1 产;下游 Step6 选模板变体 / Step2 按 narrative_mode 定字数 / Step7 只验 active_gates):

```jsonc
"render_profile": {
  "archetype": "论说|叙事|人物|工具|语录|书单|课程|考试",
  "narrative_mode": "full-800|dense-card|list",   // 字数策略,驱动 G9 档(full=800/dense=300/list=不产narrative)
  "active_gates": ["G16", ...],                    // 必须逐字等于上表(verify 拦篡改绕门禁)
  "primitives": ["语录墙", ...]                     // 可选,声明本页用的新结构原语(见 html-spec)
}
```

**判型补充(扩 §1.2,四型之外先判这四新型,命中即停,都不像再回 §1.2 判 legacy)**:
1. 全书是**箴言/格言/清单**(每条独立、无贯穿论证,如稻盛《活法》语录、KK《宝贵人生建议》)→ **语录**。
2. 全书是**荐书/书目导览**(每节介绍别的一本书,如吴晓波《影响商业的 50 本书》)→ **书单**。
3. 全书是**教材/培训课**(知识点递进 + 可练习,价值单元是「知识点+练习」非「论点+案例」)→ **课程**。
4. 全书是**备考/考点**(考点密 + 例题 + 易错点)→ **考试**。

**与门禁共存(§7 详)**:门禁分 **Tier-0 底线**(不编造/§5.1 anchor/版权≤150/真封面/零外链/Zero-Hex/data-source/破折号/G1 反空洞…,**任何 profile 不可关**)与 **Tier-1 形态**(随 `active_gates`)。**active_gates 是上表权威值,禁逐书手写篡改**;verify 拦「archetype 不在表 / active_gates 或 narrative_mode 与表不符」(防用自定义 profile 偷关反注水检查)。

**向后兼容**:无 `render_profile` 的旧 distill.json = legacy 全门禁,**旧书不必重蒸**;四型 legacy 的 profile 等价于「不写 render_profile」。

### 1.5 stakes:后果轴(高后果实操书标签,v6.1,2026-07-15)

**与 book_type / render_profile 正交的第三根轴**:书型 / archetype 决定「内容怎么组织、页面什么形态」,`stakes` 只回答「**读者照着做,数字错了后果多大**」。二者独立并存 -- 一本育儿书既是「工具 / 论说」型、又是高后果。Step1 判型时一并定 `stakes`(顶层枚举 `high|normal`,缺省 `normal`):

| 值 | 判定 | 例 |
|---|---|---|
| `high` | 书里给**读者会直接照做的可执行指令**(月龄窗口 / 剂量 / 时长 / 频次 / 温度 / 仓位…),且**数字错会造成现实伤害或误导** -- 育儿、医疗、用药、投资仓位、法律、饮食营养、健身处方等 | 婴幼儿睡眠训练、喂养剂量、投资操作手册 |
| `normal` | 观点 / 思想 / 史论 / 方法论为主,数字错顶多减损说服力、不直接伤人 | 《思考,快与慢》《人类简史》《影响商业的 50 本书》 |

**为什么做正交标签而非第五书型**(四证):① book_type / archetype 是「组织形态」轴、stakes 是「后果」轴,一本书可同属两轴(育儿书 = 工具型 + 高后果),塞进 book_type 枚举会互斥;② 既有正交维度(`source_type` / `pub_year` / `render_profile`)的落法都是「新加顶层键」,不扩 book_type;③ §V.5 明确先例「视频不新增第五型、用 `source_type` 正交」,后果轴照此;④ verify 的 archetype 注册表驱动 tab / 区块取舍,stakes 只该**追加门禁**、不该开关区块。

**驱动什么**:`stakes=high` 激活门禁 **G22**(可执行数字必带 `certainty`,§4.5.16 / §7)+ 硬门禁②的**事实抽检**(SKILL 铁律「不编造」:回原书抽检 ≥5 条数字 + 金句)。`normal` 书不强制 certainty(可选产)。**旧 distill 无 `stakes` = normal**(向后兼容,旧书不必回填,除非要做高后果主题聚合 / StepB)。

### 1.6 domain_profile:心理学科学证据轴(v6.2)

`domain_profile` 在通用旧库中是可选顶层对象,只在需要把「作者/原书主张」与「外部科学证据」分开的领域启用。本版先注册 `domain:"psychology"`;旧书与非心理学书不写,行为完全不变。**已知心理学批次出厂必须用 `verify_page.py --require-domain psychology`，批量闸则用 `verify_batch.py --require-domain psychology`**,把项目严格门传播到每一本；这样即使某本书漏写整个对象也会被 G23 拒绝。默认模式不猜领域,因而不破坏旧库:

```jsonc
"domain_profile": {
  "domain": "psychology",
  "subfields": ["judgment-and-decision-making"],
  "work_kind": "popular_science",
  "clinical_relevance": "none"
}
```

- `work_kind` ∈ `popular_science|academic_monograph|methods_manifesto|applied_guide|textbook|casebook`;`clinical_relevance` ∈ `none|indirect|direct`;`subfields` 至少 1 个非空领域标识。
- 该轴不新增 `book_type`、不改变 `render_profile`,只条件激活 **G23**(Pass1 claim 契约)与 Step3/Step7 **G24**(外部科学证据契约)。
- `evidence_level` 仍只问「转述是否忠于原书」,`certainty` 仍只问「这条内容来自原书/跨书合成/编者通识」;二者都**不能**回答某项心理学结论是否经得住复制、元分析或边界检验。科学有效性只写 `enrich.evidence_page`。

---

## 2. Step2:两遍蒸馏总览(v2)

**2026-07-03 起 Step2 分两遍**(页面从「压缩标签页」改「凝练地图 + 详实正文」;病因:旧管线只产压缩物、schema 无详实转述长文字段,16/17 个具体案例在 JSON 有、HTML 为 0):

- **第一遍 Pass 1 = 四源压缩(凝练地图)**:§3 三轮认知压缩 + §4 四嫁接件 + §4.5 延展字段 + §5 anchor/证据等级。产 `distill.json` 骨架层**除 `chapters[].narrative`/`chapters[].excerpts`/`action_chain[].detail` 外的全部字段**,含 v3 顶层 `cover_intro`(封面简介三句法)/`credibility_verdict`(裁决条),以及 `decision_rules[].chain_step`/`mental_models[].chain_step`(规则模型挂环归站)。
- **第二遍 Pass 2 = 详实转述(详实正文)**:§3.5。吃 Pass 1 骨架 + 逐章原文切片,产 `chapters[].narrative`(讲书稿式 800-1500 字/章)+ `chapters[].excerpts`(原文精选短段)+ `action_chain[].detail`(每环 80-150 字扩写,随 narrative 一起写)。给愿读 30 分钟的人,页面不再怕长。

产物 = 单一 `distill.json`(schema 见 §6),由四源零件拼成,**每个零件标注来源**(内化非运行时依赖):

| 零件 | 来源 | 落点(distill.json 字段) | 章节 |
|---|---|---|---|
| 三轮认知压缩(骨架/血肉/灵魂)+ 餐巾纸 | 李继刚 xray(主干,`_SKILL_template.md`) | `napkin` / `chapters`(no/title/summary/anchor) / `core_ideas` / `arguments` | §3 |
| Decision Rules「当 X→做 Y→因为 Z」+ 出处标注 | book-to-webpage | `decision_rules` / 全字段 `anchor` | §4.1 §5 |
| 心智模型(证据 + 边界 + 怎么用)/ 决策启发式 / 内在张力 | nuwa 女娲 | `mental_models`(含 `how_to_apply`) / `decision_rules`(启发式归一化,§4.1 note) / `tensions` | §4.1 §4.2 §4.3 |
| 批判段(盲点/时代局限/未证假设/最强反对) | 仓颉 cangjie | `critique` | §4.4 |
| 证据等级 / 质量门禁 | deep-reading-coach / reading-pipeline | `evidence_level` / 全表 | §5 §7 |
| **v2 浏览型延展字段**(生活类比 / 主次 / 金句点评 / 概念误读 / 书魂 / 因果链 / 第二人称自检 / 人物身份卡) | 本 skill v2(四源掉落宝石回收) | `core_ideas.layman_analogy`+`.primary` / `quotes.note`+`.featured` / `mental_models.how_to_apply` / `concepts.common_misread` / `soul_module` / `action_chain` / `self_check` / `persona_card`+`voice_dna` | §4.5 |
| **v2 详实转述层**(讲书稿正文 + 原文摘录) | 本 skill v2(讲书稿范式立法) | `chapters[].narrative` / `chapters[].excerpts` | §3.5 |
| **v3 浏览型新增字段**(封面简介 / 裁决条 / 行动扩写 / 规则模型挂环) | 本 skill v3(sandy 反馈重构) | `cover_intro` / `credibility_verdict` / `action_chain[].detail` / `decision_rules[].chain_step` / `mental_models[].chain_step` | §4.5(cover_intro/verdict/chain_step 属 Pass 1;detail 属 Pass 2 §3.5) |

执行顺序(两遍):
1. **Pass 1**:§3(三轮)→ §4(四嫁接件)→ §4.5(延展字段,含 v3 cover_intro / credibility_verdict / chain_step 归站)→ §5(逐条补 anchor + evidence_level)。
2. **Pass 2**:§3.5(逐章详实转述 + `action_chain[].detail` 扩写,长书 subagent fan-out)。
3. §7 自查门禁(G1-G18,不过则回补)。超长书在 Pass 1 上套 §8 分组外壳。

**`quiz` 字段停产(2026-07-03)**:页面改浏览型、删自测复习 M12;§9 已弃用,新蒸不产 `quiz`,§7 门禁无 quiz 项(见 §9)。

---

## 3. 三轮认知压缩执行细则(xray 主干)

逐轮做满,不许跳。**餐巾纸只保「一个公式 + 一句话」**,不做 xray 原版的 ASCII 图(本 skill schema 无该字段)。

### R1 骨架扫描 -- 「这本书在说什么」

| 要提取 | 判定标准 | 落点 |
|---|---|---|
| 核心问题 | 作者试图回答的那个问题,**一句疑问句 ≤40 字**(以 `?`/`?` 结尾) | **顶层字段 `core_question`**(v4,书/视频必产;规格见 §4.5.12;hero eyebrow 渲染,与 h1 标语成问答配对) |
| 一句话答案 | 作者的回答,一句话 | `napkin.one_liner`(卸掉「核心问题」载荷,只承载答案) |
| 章节骨架 | 每章 `summary` **一句 30-80 字**(目录态灰字一行,扫 N 行拼出全书骨架) | `chapters[].{no,title,summary,anchor}` |
| 论证结构 | 演绎/归纳/案例/对比 四选一 | 写进 `arguments.chain` 首句(如「归纳型:……」),并派生 `arguments.chain_steps[]`(§4.5.14) |

### R2 血肉解剖 -- 「凭什么这么说」

| 要提取 | 判定标准 | 落点 |
|---|---|---|
| 核心论证链 | 前提 → 前提 → 结论,可复述 | `arguments.chain`(散文)+ **`arguments.chain_steps[]`**(v4,4-8 步阶梯,每步 ≤14 字,§4.5.14) |
| 关键证据 | 最有说服力的 **3 个**证据/案例 | 挂进对应 `core_ideas[].evidence`(强证据可另入 `quotes`) |
| 隐形假设 | 作者没说但必须成立的前提 | `arguments.hidden_assumptions[]` |
| 反例与边界 | 何种情况下结论失效 | `arguments.counter_examples[]` |

### R3 灵魂提取 -- 「还能怎么用」

| 要提取 | 判定标准 | 落点 |
|---|---|---|
| 作者盲点 | 作者没看到什么 | `critique.blind_spots[]`(与 §4.4 合流) |
| 可迁移模式 | 这思想在别的领域叫什么(**跨学科命名**,如「在管理学叫 Y 理论」) | **顶层字段 `cross_domain[]`**(v4,§4.5.13;落板块⑤,宁缺毋滥 -- 置信不足的条目不产;注:此为「跨学科命名」,与 §4.2 nuwa「跨域复现=书内 ≥2 场景」是两回事) |
| 知识连接 | 与既有知识体系的交叉概念 | `concepts[]`(供跨书索引,§附) |
| 行动触发 | 读完该做什么不同的事 | 归一化成 `decision_rules[]`(当 X→做 Y) |

> **R3 的 v2 延伸(Pass 1)**:灵魂提取额外产三件浏览型字段 -- `soul_module`(全书最核心的那条反直觉主张,结构化成可视化母本)、`action_chain`(读完的行动主线 4-5 环)、`self_check`(第二人称自检问句)。规格见 §4.5。与 `decision_rules` 分工:`action_chain` 是一条有先后的行动主脉络,`decision_rules` 是散点战术规则。

### 餐巾纸压缩(v4 = 四件套:公式 + 公式读法 + 一句话 + 因果骨架草图)

xray 餐巾纸是「公式 + 读法段 + 一句话 + 草图」四件套;v1-v3 只保了公式 + 一句话两件,恰好把「运算符语义」与「全书因果骨架」这两个最高密度件砍掉了(诊断见 Q4 报告 §3)。v4 补回 `formula_read` 与 `sketch` 两件。四件全落 `napkin`,页面①在脑图之前一屏收完。

- `napkin.formula`:全书只能留一个公式时是什么 -- **必须是含 `=`/`≈`/`∝` 的关系式,左侧为被定义量**(判定见 §7.3 公式门禁)。范例:`投资成功 =(内在价值 − 买入价格)+ 情绪纪律`。
- `napkin.formula_read`(**v4 新增,Q4-1/Q1-2,书/视频必产**):公式的**读法一句**,**1-2 句 ≤80 字**,**必须点明运算符语义** -- 为什么是 ×/加/减/比例、归零或边界条件,而不是复述公式或再写一句 one_liner。范例(乘法归零):「为什么用乘不用加:三根支柱任一项被打到零,乘积就整体归零 -- 哪怕另两项满分也救不回;加法能以长补短,乘法里缺一根就全盘坍塌。」判定见 §7.3(G4 扩展):缺失、有效长 >80 字、或不含运算符/「乘·加·减·除·归零·缺一·比例·乘积」等语义词即打回。
- `napkin.one_liner`:全书只能留一句话时说什么(**只承载 R1 答案**;核心问题已独立成顶层 `core_question`,§4.5.12,不再凝进这里)。
- `napkin.sketch`(**v4 新增,Q4-2,可降级**):全书**因果骨架一眼图**的结构化母本,页面渲成内联 SVG 纵向因果流(§html-spec ①.sketch),落餐巾纸之后、脑图之前,静态一屏。`sketch = {type, caption, nodes[], edges[]}`:
  - `type`:枚举 `cascade|fork|loop`(级联汇流 / 分叉 / 回环)。
  - `caption`:一句图注,点出这张骨架讲什么(≤40 字)。
  - `nodes[]`(**6-12 个**,每个 `{id, label, note?, mid?}`):`label` = 节点短语(≤8 字);`mid:true` 标「**中间产物**」节点(页面 --gold 描边区分);**必须含 ≥1 层中间产物**(不是把公式右侧三项重画一遍就完 -- 骨架的价值在于展开「支柱 → 中间产物 → 汇流 → 副产品 → 终点」的因果层,含被埋没的洞察,如「自律 = 自尊的副产品」)。
  - `edges[]`(**≥1 条**,每个 `{from, to, label}`):`from`/`to` = 节点 id;`label` = 边上关系词(≤6 字,可空)。
  - **三图分工(与脑图 / 书魂不重叠,写进 html-spec)**:`sketch` 讲「全书因果怎么串」(≤12 节点、静态、一屏);脑图讲「全书知识怎么铺」(45-75 节点、可缩放全屏,§4.6);`soul_module` 讲「一个最反直觉的点」(单点对照,§4.5.5)。
  - **宁缺毋滥(可降级)**:蒸不出干净骨架(节点乱、无清晰因果层、只能重画公式)就**整块省略**,`sketch` 缺失不打回;**禁硬凑**。门禁见 §7.3(G4 扩展):若产,则 `type/caption/nodes/edges` 齐全、`nodes` 数 ∈ [6,12]、且 **node.label 集合不得与公式右侧项完全相同**(防把公式重画一遍凑数)。

---

## 3.5 第二遍 Pass 2:详实转述(讲书稿正文)

> ⏱ **执行时机**:Pass 2,在 §3 三轮 + §4 嫁接件 + §4.5 延展字段(Pass 1)全部完成、`distill.json` 骨架层落定后再跑。本节编号紧接 §3,是因二者同属「内容生产两遍」;§4 / §4.5 是横切的字段规格,Pass 2 直接消费其产物。
> **产什么**:逐章填 `chapters[].narrative`(讲书稿式详实转述)+ `chapters[].excerpts`(原文精选短段),并回填 `action_chain[].detail`(每环 80-150 字扩写,§3.5.6)。**只填这三处,不动 Pass 1 其他字段。**
> **为什么**:AI 书摘没人看的根因是砍掉了「演算过程 / 具体例子 / 作者原声」--「答案没有演算过程,而演算过程才是全部意义」。narrative 就是把演算过程补回来。

### 3.5.1 两级检索(每章必走,先结构后血肉)

| 级 | 动作 | 目的 |
|---|---|---|
| 一级·保结构 | 先读该章的 Pass 1 骨架(`chapters[].{title,summary}` + 落在本章的 `core_ideas`/`quotes`/`decision_rules`),锁定本章讲哪几个论点、按什么顺序 | 不跑题、不与别章重复 |
| 二级·保血肉 | 再回 `book.txt` 该章原文切片,`grep` / 通读定位**关键案例、具体数字、作者原话**,把骨架的每个论点补满细节 | narrative 有血有肉,excerpts 有据可摘 |

**铁律**:narrative 的每个论点必须能在 book.txt 该章找到出处;grep 不到支撑就降级(标 `evidence_level` 或不写该点),**禁凭印象编案例 / 编数字**。

### 3.5.2 讲书稿写作模板(每章 narrative)

按樊登式讲书稿范式推进,一章一段完整叙述(不是要点罗列):

1. **坡道开场(1 段)**:用一个悬念 / 反常识现象 / 具体场景把读者拽进来,别用「本章讲了……」式开场。
2. **论证主体**:本章每个重点 = **观点 + 至少一种「案例 / 故事 / 数据」充分论证**。其中:
   - **故事必须按叙事整段完整讲**(时间、人物、动作、转折、结果),**禁压成一句标签**(如把「清洁工 Ronald Read 攒下 800 万美元」压成「省下的钱会复利」即为失败)。
   - 数据带原书给的具体数字,不含糊成「很多 / 大幅」。
3. **收束(1 句)**:一句话把本章接回全书主线(与 `napkin.one_liner` 呼应),说清「这章在整本书的位置」。

**字数档**:书 **800-1500 字/章**(下限 800 硬门槛 G9);视频段 **≥400 字/段**。上不封顶但别注水,宁可少论点讲透。

**Pass 2 文风约束(硬规,写 narrative / summary / excerpts 注解时全守)**:

- **随机进入自足性(v4 批次C,Q5-6)**:目录态 + 脑图传送门鼓励读者「随机进入」任一章,故**每章 narrative 必须能单独读懂,不假设读者已线性读过前章**。① **人名 / 昵称 / 自创比喻每章首现,带一次性同位语**说明身份/含义(如「樊登的儿子嘟嘟」「作者称之为『培育森林』的养育观」),而非直接甩一个前文才介绍过的代号;同一章内再现可省。② **`chapters[].summary`(收起态摘要)不得引用未在本句内说明的人物 / 专名**(扫目录的读者没上下文)——摘要里出现的人名必须自带一句话交代是谁,否则改用泛称。③ 跨章再现的支柱概念、标志性故事,再现时至少带全称重述一次(不靠代词悬空)。**自查项见 §7**。
- **破折号统一(v4 批次C,Q7-12,机检)**:**转述文本(narrative / summary / 卡片文案 / 编辑点评等一切自己的话)破折号一律用 `--`(两个半角连字符),禁全角 `——` / `—`**;**只有 `excerpts` / `quotes` 的原文照录字段保留原样不改**(CLAUDE.md「原文照录除外」)。verify 机拦:页面可见转述正文出现全角 `——`/`—` 即打回(blockquote / qw-card 原文区豁免)。

### 3.5.3 excerpts:原文精选短段

- 每章挑**最有冲击力的 1-N 个原文短段**填 `chapters[].excerpts[] = {text, anchor}`,页面 blockquote 明示引用。书**每章 ≥1 条**(门禁 G14);视频可 0(讲者原话另走 `quotes`)。
- `text` = **原文照录**(不改写、不润色),单段 **≤150 字**;`anchor` 指向原文位置(格式同 §5)。
- 挑选标准:能当「作者原声」证据、转述不如原话有力的句子。**不是随手截段,是精选。**

### 3.5.4 版权线(引用红线,narrative + excerpts 都守)

| 红线 | 标准 |
|---|---|
| 单段引用长度 | 直接照录原文的单段 **≤150 字** |
| 全书总引用占比 | 所有 excerpts + narrative 内直接引文合计 **≤ 全书正文 10%** |
| 引用必明示 | excerpts 一律 blockquote + `anchor` 出处;narrative 里引原话须加引号并注出处 |
| 转述为主 | narrative 以**自己的话转述**为主(讲书稿),非成段搬运;**连续 30 字与原文雷同即红线**,须改写 |

### 3.5.5 长书执行方式(subagent fan-out)

> 2026-07-12 五作者约 20 本批量复盘定案:**fan-out 分块数不是成本大头**(逐章命名 ≠ 逐章派 agent,各 subagent 仍 4-6 章/组;砍分块省不到 token 且掉详实度)。杠杆在**并发调度 + 失败核盘 + 统一命名**——本节据此收紧。

章数多(如 20 章)时按章分组并行:

1. **分组**:按章切组,**每组 ≤5 章**;每组派 1 个 subagent(全 Opus),各拿「本组各章 Pass 1 骨架 + 本组原文切片」。**并发上限**:全局在飞的 Pass2 subagent **≤ 6-8**(批量多本时跨会话统算,见 SKILL `§批量模式` 并发闸),别一次性起满所有组、别多作者同时段并跑(会引爆 529 风暴)。
2. **组内串行**:subagent 组内逐章写 narrative + excerpts(串行,保上下文连贯),不跳章。
3. **产物落盘·统一命名(硬)**:每组写 **`$DATA\{书目录}\_pass2_g{N}.json`**(N=组序,连续)。**只用这一套命名**——禁 `_ch_N` / `_pass2_N` / `_pass2_batchX` 等即兴变体(并发多会话命名漂移会致合并对不齐、掉章;复盘曾四套并存)。
4. **主控合并 + 完整性门禁(硬)**:各组 `_pass2_g*.json` 回填 `distill.json` 对应 `chapters[].no`,主控做:
   - **合并完整性断言**:回填后核「`chapters[].no` 全齐(1..总章数无缺)+ 每章 narrative 达 G9 字数下限 + 书籍每章 G14 excerpts」。缺口**只对缺章定点 gap-fill**(补派一个只写缺章的 subagent),**禁整组重跑**。
   - **失败先核盘再重派**:某组 subagent 报「失败 / 无 result」时,**先看它的 `_pass2_g{N}.json` 是否已落盘**——已落盘且完整就直接用,别被「无 result」骗去整组重跑(复盘中吴晓波 23 个「无 result」的 agent 多已写盘、只是返回元数据被限流,整组重派 = 纯浪费)。
   - **标志性案例保全抽检**:该书招牌故事必须完整出现在对应章,不得被压成标签(复盘实测此闸有效:卡哈马卡 / 秦池 / 火鸡均整段完整,保留)。
   - **清理中间态(合并通过后收尾,硬)**:上述完整性断言**全绿后**(章号 1..N 全齐 + 每章 narrative 达 G9 + 书籍每章 G14 excerpts),删本书目录下 `_pass2_g*.json` -- 它们已回填进 `distill.json`、已被 gitignore、无保留价值,留着只会在下次入库/聚合时污染目录(2026-07-15 复盘实测 13 本睡眠书里 7 本残留)。**唯一例外**:仍需对照调试分块产物时暂留,收工前删。⚠ **无合并脚本在环**(现行 group 格式 = 按章号 keyed 的 dict `{"1":{…},"2":{…}}`,旧 `merge_pass2.py` 按「一文件一章 + 顶层 `no`」设计、已与之脱节失效),本步是主控手动 `rm _pass2_g*.json` 的**文字规约**,不是 CLI flag;删前必先确认完整性断言过、`distill.json` 已收全。

### 3.5.6 action_chain[].detail(v3,随 narrative 一起写)

Pass 1 已产 `action_chain` 的 `label` + `explain`(骨架);Pass 2 在写 narrative 的同时,给**每一环**补 `detail` -- **80-150 字整段扩写**,把这一环从「一句话」摊开成一段能照着做的说明(治 v2「点开只有一句话」的薄)。写法与门禁见 §4.5.6;素材从本环相关的 `narrative` / `decision_rules` / `core_ideas` 提炼,**不新造事实**。门禁 G17:每环 detail 去空白字符数 ≥ 60。detail 与 narrative 同批产,长书分组时随本组各章一并写。

**时间盒首步动作(v4,Q4-5,写法规范不加 schema 字段)**:每环 `detail` 的**末句**必须给出一个**带时间盒 / 场景盒的首步动作**,格式「**今晚 / 本周 / 下次遇到 X 时,先做 Y,产出 Z(可见产物)**」-- 让读者合上页面就知道今晚第一步干什么,而非只知道该怎么想(xray 行动触发范式:「今晚写下最近一周对孩子说的 5 句话」「把公约贴在冰箱上」)。**自查**:全 5 环里至少 **2 环** 的末句含时间盒词(今晚 / 本周 / 明天 / 下次…)+ 一个可见产物(一张清单 / 一句话 / 一条消息…);产物要具体可核,不写「多陪陪」这类没有产出物的空动作。不加机检门禁(纯文案规范,靠蒸馏自查)。

---

## 4. 四源嫁接件规格

### 4.1 决策规则 Decision Rules(book-to-webpage + nuwa 启发式归一)

`decision_rules[]` 每条 = `{when, do, because, anchor}`:

| 字段 | 要求 |
|---|---|
| `when` | 可观测的**触发情境**(如「市价大跌但基本面未变」),不是抽象概念 |
| `do` | 具体**可执行动作**(如「复核价值后持有或加仓」),不是「要注意」类空话 |
| `because` | 原书给的理由 |
| `anchor` | 指向 `because` 依据的原文位置(格式见 §5),**每条必带** |

> nuwa 的决策启发式「如果 X 则 Y」在此归一化:「如果 X」→ `when`,「则 Y」→ `do`,补上原书理由填 `because`。因此本 skill 不设独立「启发式」字段,全部收进 `decision_rules`。工具书 ≥8 条。

### 4.2 心智模型 Mental Models(nuwa)

`mental_models[]` 每条 = `{model, evidence[], boundary}`:

| 字段 | 要求 |
|---|---|
| `model` | 一句话讲清这个「怎么想」的模型(捕捉思维方式,非书摘) |
| `evidence` | **≥2 条**,每条内嵌 anchor 文本(格式见 §5) |
| `boundary` | 适用边界/失效域,**必填**(防蒸成万能的扁平圣人) |

**nuwa 三重验证(人物书每条 mental_model 必过,过不了则剔除;验证过程不入 JSON,仅作纳入门槛)**:

1. **跨域复现**:同一模型在书中 ≥2 个不同领域/场景复现
2. **生成力**:能用它推断作者对一个书中没提的新问题会怎么反应
3. **排他性**:删掉作者名字仍能认出是谁的思维,且与主流/对立观点可区分

### 4.3 内在张力 Tensions(nuwa)

`tensions[]` 每条 = `{a, b, note}`,**≥2 对**:

- `a` / `b`:作者自身**未调和**的两个立场(如「相信市场长期理性」vs「靠市场短期犯蠢赚钱」)
- `note`:为什么没调和 / 被什么勉强缝合
- 目的:防把作者蒸成没有矛盾的圣人 -- 张力是深度来源。

### 4.4 批判段 Critique(仓颉)

`critique` = 四件套,**全齐**:

| 键 | 含义 | 类型 |
|---|---|---|
| `blind_spots` | 作者没看到的 | 数组 |
| `era_limits` | 写作年代绑定、今天已变的结论/数据 | 数组 |
| `unproven_assumptions` | 当公理用却没证的前提 | 数组 |
| `strongest_objection` | 站在对立面能提的**最有力**反驳(不是稻草人) | 字符串 |

### 4.5 v2/v3 浏览型延展字段规格(四源掉落宝石回收 + v3 重构新增)

以下字段分两批:**v2**(4.5.1-4.5.8)从四源样张里回收的「掉落宝石」(旧管线 JSON 有、页面没落点或根本没产),全部在 **Pass 1** 随对应主字段一并产出;**v3**(4.5.9-4.5.11,2026-07-04 sandy 反馈重构新增)-- `cover_intro`(封面简介)/ `credibility_verdict`(裁决条)/ `chain_step`(规则模型挂环)属 Pass 1,`action_chain[].detail` 属 Pass 2(§3.5.6)。命名与 §6 schema 逐字一致,下游按此消费。

#### 4.5.1 core_ideas 增字段

| 字段 | 要求 | 门禁 |
|---|---|---|
| `layman_analogy` | **一句生活类比桥**,把抽象观点翻成日常经验(李继刚 gem:「邻居报低价你不会贱卖房子,持股一绿你却慌着割肉」)。**必填、非空。** | G10 |
| `primary` | 布尔;全书**最核心的 1-2 条** core_idea 标 `true`(页面视觉放大),其余 `false` / 省略。`true` 条数 ∈ [1,2]。**若某条主张与 `soul_module` 同源(同一反直觉主张),该条不得标 primary**(§4.5.5 查重)。 | G15 |
| `pillar`(v4) | **int = 脑图一级分支序号**(即论证段序号,§4.6 的 root.children 第几个,3-5 段之一);观点卡按 pillar 分组渲染(组头=一级分支名,组内 2-4 卡)。**牵强留 `null`**(入「贯穿全书」组),规则同 §4.5.11 chain_step「禁硬塞」-- 归错组比不归更误导。 | verify 机拦 `pillar ∈ [1,5] 或 null`(一级分支 §4.6 定为 3-5 个,机检上限取 5;是否 ≤ 实际分支数属填页自查) |

#### 4.5.2 quotes 增字段

| 字段 | 要求 |
|---|---|
| `note` | **金句编辑点评一句**(「全书最后一句,反鸡汤的终极注脚」),说清这句为何值得停。 |
| `featured` | 布尔;凝练层精选 **≤3 条** 标 `true`(首屏小金句条),其余落详实层行内。 |

#### 4.5.3 mental_models 增字段

| 字段 | 要求 |
|---|---|
| `how_to_apply` | **动作化一句**:怎么用这个模型去看一个书里没提的新问题(nuwa 五件套缺的那件)。空泛「要多思考」不算。 |

#### 4.5.4 concepts 增字段

| 字段 | 要求 |
|---|---|
| `common_misread` | **作者定义 vs 常识误解**(仓颉 gem:「安全边际 ≠ 设止损」)。二者无实质差异时**可省**(留空 / 缺字段),不硬凑。 |

#### 4.5.5 soul_module(书魂模块,全书 1 个)

全书最核心那条**反直觉主张**的结构化可视化母本。`soul_module = {title, subtitle, type, intro, states[], curve?}`:

| 字段 | 要求 |
|---|---|
| `title` | **自解释论点句**(读标题就懂主张,非「书魂」这种容器名)。非空。 |
| `subtitle` | 一句副题讲清「这是什么」。**非空**(门禁 G11)。 |
| `type` | 枚举 `compare\|chain\|curve`:并排对照 / 流程链 / 曲线。 |
| `intro` | 2-3 句导语,**点出反直觉**在哪。 |
| `states[]` | **2-3 个同构态**(门禁 G11 要求 ≥2),每态 `{label, body(整段解释), points[](输入/机理/输出式要点)}`;compare 型是并排对照的两三列,chain 型是链上的环,curve 型是曲线旁的注解态。 |
| `curve` | **仅 `type=curve` 时必填**:`{series:[{label, points:[[x,y]…], token}]}`,`token` 取品牌色变量(如 `--red`),页面随主题换肤。其他 type 省略。 |

**与 primary 观点卡查重(v4,Q1-4)**:`soul_module` 承载的那条反直觉主张,若与某条 `core_idea` **同源**(蒸馏自查:同一反直觉主张,如 soul「养育是培育森林非组装汽车」↔ core_idea「养育是复杂系统不能像组装汽车」),则**该条 core_idea 不得标 `primary`**(降为普通卡),并在卡尾加页内锚点「完整可视化见本板块结尾 ↓」指向 `.soul-block`。重要主张值得多遇,但同板块①内两块大组件同主张 = 车轱辘;降一档 + 传送门既保留再遇、又消除冗余。G15 备注同款判定。

#### 4.5.6 action_chain(行动主线,4-5 环)

读完的**一条行动主脉络**(区别于 `decision_rules` 的散点规则):`action_chain[] = {label, explain, detail}`,**4-5 环**(门禁 G13):

- `label`:环名 **≤12 字**。
- `explain`:**3-6 句整段解释**这一环做什么、为什么(Pass 1 产)。
- `detail`(**v3 新增,Pass 2 产**):**80-150 字整段扩写**,把这一环摊开成一段能照着做的说明 -- 具体怎么下手、常卡在哪、书里哪个案例 / 数据印证。**不是一句话**(治 v2「点开只有一句话」的薄),**也不是把 explain 换个说法重抄**;素材从本环相关的 `narrative` / `decision_rules` / `core_ideas` 提炼,不新造事实。门禁 G17:去空白字符数 ≥ 60。随 narrative 一起写(§3.5.6)。
- 环与环有先后 / 因果顺序,连起来是一条可走的路。

#### 4.5.7 self_check(第二人称自检,4-8 条)

纯浏览式自检问句(**无打分交互**):`self_check[] = {q, followup, anchor}`,**4-8 条**(门禁 G12):

- `q`:**第二人称主问句**(必含「你」),把某个 core_idea 翻成「你会怎么做 / 你是不是也……」。
- `followup`:追加追问一句,逼读者再想一层。
- `anchor`:指向所测 core_idea 的原文位置(格式同 §5),**必带**。

#### 4.5.8 persona_card / voice_dna(人物书选填)

**仅 `book_type=人物` 时产**,其他书型省略:

| 字段 | 要求 |
|---|---|
| `persona_card` | **第一人称身份卡一段**:以传主口吻自述「我是谁、我怎么想」。 |
| `voice_dna` | 传主的**句式 / 节奏 / 禁忌**(表达 DNA),供页面还原其口吻。 |

#### 4.5.9 cover_intro(v3 封面简介,顶层字段,Pass 1 产)

`cover_intro`(顶层 string,**2-3 句**):头部 banner 的封面简介,答读者进门第一问「这是本什么书,值得花 30 分钟吗」。**三句法**固化(素材从哪来 / 框架是什么 / 结论落在哪):

| 句 | 写什么 |
|---|---|
| 1 素材从哪来 | 作者的材料来源(咨询案例 / 研究 / 亲历),一句交代凭什么谈这题 |
| 2 框架是什么 | 全书拎出的那套框架 / 支柱 / 主线,点名不展开 |
| 3 结论落在哪 | 最终落到的那个(常反直觉的)结论 |

- **禁比喻**:比喻是 hero 标语的专属资产,cover_intro 只讲内容、不打比方 -- 从源头写不重(治 F4「cover_intro 与 hero 标语都在抢全书总论的活」)。
- **禁复用 napkin**:不得含 `napkin.one_liner` 中 **≥12 字连续片段**(门禁 G16 查重)。
- 信息型措辞,别写成立场句 / 情绪句(那是 hero 标语的活)。

#### 4.5.10 credibility_verdict(v3 裁决条,顶层字段,Pass 1 产)

`credibility_verdict`(顶层 string,**2-3 句**):板块③批判与评价开场的总裁决,让读者 10 秒对「该信几分」有数。

- 一句写**哪些结论最硬**(证据扎实、经得起推敲、可放心采用),一句写**哪些要打折**(时代局限 / 未证假设 / 样本偏差 / 可行性存疑等该扣分处);两句一硬一软最省力,也可 3 句。
- 从既有 `critique` / `tensions` / `arguments` 归纳,**不新造事实**(每句可回溯到已蒸批判内容)。
- **书籍必产**(门禁 G18);视频可省。

#### 4.5.11 chain_step 归站规则(v3,decision_rules + mental_models 挂环,Pass 1 产)

`decision_rules[].chain_step` 与 `mental_models[].chain_step`(**int 1-5,可空 / null**):把散点规则、心智模型挂到 `action_chain` 五环上,页面按环分组呈现(「行动主线当骨架,规则 / 模型挂上去」)。

- **取值** = 该规则 / 模型最贴合的那一环序号(1-5,对应 `action_chain` 的第几环)。
- **牵强则留空**:一条规则同时贴多环、或哪环都不特别贴,`chain_step` 置 `null`(页面归入「通用」组)。**禁硬塞**一个不贴的环号 -- 归错站比不归站更误导。
- 归站是「组织」不是「隐藏」:所有规则 / 模型无论归没归站都全量呈现,`chain_step` 只决定分在哪一组。
- `action_chain` 只有 4 环时合法取值即 1-4;`chain_step` 不得超出实际环数(超出按越界处理,应留空或改挂)。

#### 4.5.12 core_question(v4 核心问题前置,顶层字段,Pass 1 产)

`core_question`(顶层 string,**一句疑问句 ≤40 字**,以 `?` / `?` 结尾):全书回答的那个核心问题,放在 hero eyebrow(副题小字)槽位,与 `<h1>` 巨型标语构成**问答配对**(如问「为什么父母明明很爱孩子,却把孩子越养越糟?」上方标语答「养育是培育一片森林」)。

- **为什么前置**:问题先于答案激活图式,是新手建图式的第一挂钩点(得到 / Blinkist 都以问题开场);旧管线把它「凝进 one_liner」后就丢了独立落点。
- **书 / 视频必产**(门禁 G19)。**禁复用**:不得与 `cover_intro` / `napkin.one_liner` 存在 **≥12 字连续重叠片段**(门禁 G19 查重,防与全书总论 / 答案句重复)。
- 措辞是**真问题句**,不是把答案改成反问;一句、不带解释。

#### 4.5.13 cross_domain(v4 跨域映射回收,顶层字段,Pass 1 产)

`cross_domain[]`(顶层数组,**3-5 条**,每条 `{domain, name, note}`):这套核心思想在别的学科里叫什么 -- 把新书挂到读者已有知识域上的 Ausubel 式锚点(xray 灵魂层最值钱的一层,四源融合时被概念偷换丢掉,此处恢复)。

| 字段 | 要求 |
|---|---|
| `domain` | 学科 / 领域名(如「管理学」「系统科学」「心理学(自我决定论)」)。 |
| `name` | 该领域里的**对应命名**(如「Y 理论」「复杂适应系统 CAS」「内在动机三要素」)。 |
| `note` | 一句说清对应关系(≤60 字,点明为什么是同构)。 |

- **落点**:板块⑤延伸阅读,`.crossbook` 跨书回声**之前**的独立小节「这套思想在别处叫什么」,一行一条。
- **宁缺毋滥(事实从宽但不硬凑)**:标准是「**常识级学科对应**」而非需引证的论断;**置信不足的条目直接不产**,数组可短(3 条)甚至整体省略,**禁为凑数硬编不靠谱的跨学科对应**。不设机检门禁(选填)。

#### 4.5.14 arguments.chain_steps(v4 论证链阶梯化,Pass 1 产)

`arguments.chain_steps[]`(数组,**4-8 步**,每步 **≤14 字**):把 `arguments.chain` 那段散文论证抽成一条可 5 秒扫完的阶梯(前提 → 前提 → 结论),落板块③立论复述 `.arg-restate` 的散文段**之上**,渲成横向箭头相连的 step 胶囊链(窄屏纵排);散文保留作展开解释。

- 每步是论证链上的一环短语(如「养育是复杂系统」「内核是三根支柱」「要先改父母自己」),动宾 / 名词短语,**不写整句**。
- 素材从 `arguments.chain` 提炼(常已自带链尾,如「个案归纳 → 复杂系统类比 → 三支柱内核 → 先改自己」),**不新造**。
- 门禁 G20:`chain_steps` 数 ∈ **[4,8]**,每步有效长(去标点空白)**≤14 字**。

#### 4.5.15 chapters[].hook(v4 目录悬念钩子,Pass 2 随 narrative 产)

`chapters[].hook`(string,**≤20 字悬念句**):取该章**标志性案例的具象意象**,渲在目录收起行摘要之后、以强调色短句出现 -- 让收起行成为「结论(标题)+ 概览(摘要)+ 钩子」三层,给读者一个想点开的 scent。

- **必须具象人事物**(如「被剪掉的牛仔裤,和总谈崩的谈判」「沙丁鱼只用三条规则,就躲开了鲨鱼」);**禁抽象复述论点**(如「亲子关系很重要」)。
- 取该章 narrative 里最有画面感的招牌案例,**不新造**。
- 门禁 G21(机检):hook 若存在,有效长 **≤20 字**(超出打回);「是否具象、非论点复述」属蒸馏自查(§7 自查项)。存在性推荐(书每章宜产),不硬拦缺失。

#### 4.5.16 certainty(v6.1 可执行数字确定性,decision_rules + core_ideas 元素级,Pass 1 产)

区别于 `evidence_level`(问「转述**忠不忠于原文**」),`certainty` 问「这条可照做的建议,**知识来源硬不硬、该信几分**」--- 让下游(读者 / 主题聚合 StepB 的数字对照表 / 引用本书的文章)一眼分清哪些数字是书里白纸黑字、哪些是编者合成或通识。**加在 `decision_rules[]` 与 `core_ideas[]` 元素级**(可执行数字的两处主要载体):

| 值 | 含义 | 例 |
|---|---|---|
| `book_explicit` | **书里白纸黑字**的确切值,`anchor` 指向处能找到原句 | 「先等至少 90 秒再进房」(How Babies Sleep 原文) |
| `cross_book_synthesis` | **跨书合成 / 并集**,单本没有、由多本拼出 | 「婴儿睡眠周期 30-60 分钟」(三本各给一段并成区间) |
| `general_knowledge` | **编者补的通识**,书里没有、属教科书常识 | 「成人 REM 约占两成」(13 本睡眠书 distill 均无此数) |

- **何时必产**:`stakes=high`(§1.5)的书,`decision_rules[]` 每条 + `core_ideas[]` 每条**必带** `certainty`(门禁 G22 机拦)。`stakes=normal` 书**可选**(不产不拦)。
- **与 evidence_level 正交共存**:`core_ideas[]` 同时挂 `evidence_level`(忠实度)与 `certainty`(来源硬度),二者互不覆盖、都填。
- **诚实优先**:拿不准往低标(宁 `general_knowledge` 不冒充 `book_explicit`);`cross_book_synthesis` / `general_knowledge` 的数字**尤其要过硬门禁②事实抽检** -- 它们最易在下游被当成「书里说的」误引(这正是 2026-07-15 婴幼儿睡眠文章 fact-check 抓出「成人 REM 20%」「一晚醒 2-8 次」的根因:distill 没标来源硬度,写作时被当书中数据引用)。

#### 4.5.17 心理学 claim_id / claim_type(v6.2,Pass 1 产)

当 `domain_profile.domain=="psychology"` 时,`core_ideas[]` 与 `decision_rules[]` 每条都必须增加:

- `claim_id`:本书内唯一、稳定的 ASCII kebab 标识,如 `loss-aversion-generalizes`;后续修文案不改 ID。
- `claim_type` ∈ `framework|descriptive|associational|causal|predictive|intervention|methodological|normative`。按主张最强语义定型,不得把相关性包装成因果、把规范建议包装成实证结论。

这一步只是在原书层给可核查主张建立主键,**不是**给主张判真。Step3 的 `evidence_page.claims` 必须逐一覆盖这些 ID;框架型、方法论型和规范型主张也保留,确实不接受经验检验时可在外证层标 `not_testable` 并写明理由。`descriptive|associational|causal|predictive|intervention` 属实证型,不得用 `not_testable` 逃掉来源。

---

## 4.6 M03 脑图拆分(自绘 SVG 知识树:关键词路标 + 判断句副文本,先读骨架再读血肉)

> 脑图不是 distill.json 里的字段,而在填页时把 `chapters[]` + `arguments.chain` + `core_ideas` +
> `decision_rules`/`mental_models`/`concepts` + `enrich` 派生成 `#bd-mindmap-data` 的 JSON
> (单键 `nodeData` + 可缺省 `layout`;schema 见 html-spec §5)。立法核心:**图是目录不是正文--节点文案是路标,
> 血肉全部留在②逐章精读,靠传送门抵达**。「乱」的真度量是 topic 总字数,不是节点数;全图 topic 总字数 ≤900
> (现状约 1970,重组后约 700,-57% 而节点数几乎不变)。引擎 **v4.1 起 mind-elixir → 自绘 SVG 深色版**(sandy 定稿):
> 读 `nodeData` → tidy-tree 布局 → SVG 挂线节点 + 父子直角引线 + viewBox viewer,**去掉所有跨枝关联/收纳虚线**。
> 这里定「怎么拆」,html-spec 定「怎么写」。

**一级分支(root.children)= 按书型选组织法,3-5 个:**

1. **论说型/叙事型/人物型(默认)**:作者论证链的**连续章区段**(如 1-2/3/4-6/7-9),段名=概念短语
   **≤8 字**(不含 ①②③④ 序号前缀与「第N-M章」后缀),如「① 问题的根源 · 第1-2章」。
   自检:各分支覆盖的章区段连续、无交叉、并集=全书;分支数与 napkin 公式项数相等或在说明里点明映射。
2. **工具型/清单型/合集型(章序无论证含义时)**:改**概念聚类**--一级=3-5 个 MECE 概念桶,
   放弃「连续区段」自检,改为「全部 hyperLink 章号并集=全书」;传送门仍逐节点挂真实章号。
   两种组织法**二选一,禁混用,禁做页内双模式切换**(双倍数据双倍维护,读者一次只需要一张对的图)。Step1 书型判定直接驱动。
3. **布局(`layout` 字段仅记录组织法语义)**:章区段模式写 `layout:"chapter-span"`、概念聚类写 `layout:"concept-cluster"`。
   SVG 版布局固定为横向 tidy-tree(root 在左、①②③④ 自上而下 = 章序 = 论证序,逐级右展),`layout` 为透传字段、不驱动方向;
   缺省按章区段。区别只在「一级分支怎么拆」(见 1/2),不再有 mind-elixir 的 RIGHT/SIDE 方向切换。

**二级 = 核心观点,双层节点(每一级挂 2-4 个,全图 8-12 个):**

4. `topic` = **概念关键词/短语 ≤10 字**(扫读层,如「支柱一·无条件的爱」「叛逆=无助」);
   `tags[0]` = **可反驳判断句 ≥8 字且 ≤18 字**(细读层,T5 条件化改写,如「爱里没有交换、恐吓与威胁」);
   `tags[1]` = 「第N章」章码 chip;`hyperLink:'#ch-N'`(N=真实章号);`expanded:false`。
   G8 在脑图上的适用调整:判断句要求落在 **tags[0]**,topic 适用黑名单(禁「第N章」式零信息、禁通用容器词)
   但**不再要求 ≥8 字**。一章可拆多个二级;子命题不得与母命题平级(「≠溺爱」挂支柱一之下,不与三支柱并列)。

**三级 = 支撑,只收三类,每个二级 ≤4 个:**

5. 🧠 机制/心智模型、💡 核心概念、⚖️ 决策规则(当X→做Y)。**动宾/名词短语 ≤14 字,禁冒号双段式**
   (「X:Y」的 Y 要么删、要么下沉四级、要么本来就是案例)。同级排序固定 🧠→💡→⚖️。
   同一概念的不同说法(概念条 vs 规则条、归属感 vs 被接纳)**必须归并为一个节点**。

**四级 = 案例与外部书(真四级,挂到它直接证明的那条支撑之下):**

6. 📖 案例 = **专名短语 ≤12 字**(时间/数字/对话/转折等细节一律不进图);每条支撑下 ≤2;
   直接论证二级、无所属支撑的案例可直挂二级末位,每个二级直挂 ≤2。
   📚 外部书 = 书名 + ≤6 字关系词(印证/补充/反驳/推向极端),固定挂二级**最末位**,每个二级 ≤1,
   只用 enrich 里真实存在的书。每个叶子写 `_src`(章锚点或书名)供对账,引擎原样挂载。

**坚决不进脑图(六类,有各自板块,进图即噪声):**
实验数据与数字细节、金句原文、书评/批判观点、自检问句、行动清单条目、作者生平。

**可溯性铁律(不变)**:二级/三级=distill 真实内容;📖=narrative/excerpts 真事;📚=enrich 真实书目;
禁造书里/enrich 里没有的东西;重组是编辑动作,不新增书中不存在的层级。

**全展开 + viewBox 缩放(SVG 版)**:SVG 版一次画全 4 级,清爽由 viewBox viewer(连续缩放/拖动/复位/全屏)承担,
不靠折叠。`expanded` 字段透传保留(兼容旧数据)但不驱动折叠。默认 `fit()` 铺满居中,矢量放大任意倍率不糊。

**不画关联(SVG 版硬删)**:**去掉所有跨枝关联箭头(arrows)与收纳组(summaries)**--sandy 诉求:去掉所有关联虚线。
只画父子直角引线。写作时**不再产出 `arrows`/`summaries` 两键**(留着只增体积、无渲染效果;生成器读到也忽略)。
原「同一关系全页至多两处」的洞察改写进 napkin 公式或一级段名,不再画成图上箭头。

**规模指导**:45-75 节点、真 4 级;**topic 总字数 ≤900**(含 emoji 不含 tags)。
章少按比例缩;重点章拆 2-3 个二级,别一章一节点。

> verify 机拦(html-spec §5.2 同步)= 静态 `lint_mindmap` 审 nodeData 树四项:① 一级分支挂真实锚点(挂 hyperLink 叶子);
> ② `#ch-N` 不死链;③ 二级节点缺 `tags[0]` 或 `tags[0]` 有效长 <8 字拦截;④ 全图 topic 总字数 >900 拦截
> (arrows/summaries 相关门禁随字段作废一并删除)。**SVG 结构**(真出 `<svg>`/节点数达标/无关联箭头元素/viewer 已跑/点二级真跳章)
> 由 Playwright 冒烟断。分级 per-node 字数(≤10/≤14/≤12)与层级归位、案例挂位靠蒸馏自查 + 冒烟,不进硬门禁
> (避免误杀降级页/模板);`_src`/`expanded`/`layout`/残留 `arrows`/`summaries` 为透传字段机检忽略。

---

## 5. 锚点与证据等级

### 5.1 anchor 格式(每条 core_ideas / decision_rules / quotes / mental_models.evidence / chapters.excerpts / self_check 必带)

标准格式:**`第N章·约X-Y页`**。

页码估算(用 `diagnose.json` 的 `chars` 与 `pages_est`):

- 已知内容在 `book.txt` 的字符偏移 `c` → 页 ≈ `round(c / chars × pages_est)`
- 只知在第 N 章 → 用该章文本在全书的字符区间 `[c起, c止]`,页区间 = `round(c起/chars×pages_est)` 到 `round(c止/chars×pages_est)`,取内容大致所在的子区间
- 页码是**估算**,格式写「约」;禁止精确到假装读过纸书

降级(不得瞎编):

| 情形 | anchor 写法 |
|---|---|
| `pages_est` 缺失(纯 txt 无页概念) | 只写 `第N章`,省略页码 |
| 无章节结构(diagnose `toc_detected=false`) | 写 `约全书XX%处`(按字符偏移占比) |

### 5.2 evidence_level 三值(每条 core_idea 必标)

取值 `原文确认 | 结构推断 | 需复核`:

> `evidence_level` 是**原书转述忠实度**,不是科学证据等级。心理学书中即使一条主张标为「原文确认」,也只表示作者确实这样写过;它仍可能在外部研究中呈 `mixed`、`contested` 或 `not_supported`。

| 值 | 定义 | 判定标准 |
|---|---|---|
| `原文确认` | 有可复述的原文句子支撑 | `evidence` 能给出该书可在 `book.txt` 定位的原句/近似原句,且 agent 确实读到 |
| `结构推断` | 原文未直说,由结构/上下文推得 | txt 无直接对应句,结论由章节标题/论证链/前后文合理推断 |
| `需复核` | 存疑,需人工回原书核 | 满足任一:所在段 `garbled_ratio` 偏高(该段乱码明显)/ 被 §8 分组切断只见片段 / 页码无 `pages_est` 可依却给了页码需回填 |

---

## 6. distill.json schema(主对象,整块契约 · v2)

`evidence_level` 取值 `原文确认|结构推断|需复核`;`book_type` 取值 `论说|叙事|人物|工具`;`render_profile.archetype` 取值 `论说|叙事|人物|工具|语录|书单|课程|考试`(v6,见 §1.4);`soul_module.type` 取值 `compare|chain|curve`;`stakes` 取值 `high|normal`(v6.1,顶层,缺省 normal,见 §1.5);`certainty` 取值 `book_explicit|cross_book_synthesis|general_knowledge`(v6.1,decision_rules / core_ideas 元素级,stakes=high 必产,见 §4.5.16);心理学书另有可选顶层 `domain_profile` 与元素级 `claim_id/claim_type`(v6.2,见 §1.6/§4.5.17)。**本表是全 skill 契约单一来源,下游(enrich / page-skeleton / html-spec / verify)一律以此字段名为准。**

> **`pub_year`(顶层整数,v5,原著/系列首版年)**:多书作者「思想演变专题」的排序轴(见 `author-craft.md`)。书籍填原著首版年;视频系列填该系列最早一集年份。**一次性查证/手填,非重蒸**;单书蒸馏不消费它,只作跨书聚合的时间锚。缺失时演变页降级(时间线/分期不可用),故建议每部蒸完即回填。

### 6.1 书籍例(不写 `source_type` = 书籍)

```json
{
  "slug": "touzi-zui-zhongyao-de-shi", "title": "投资最重要的事", "author": "霍华德·马克斯",
  "book_type": "论说|叙事|人物|工具",
  "render_profile": {"archetype": "论说", "narrative_mode": "full-800", "active_gates": ["G4","G8","G9","G10","G11","G12","G13","G16","G17","G18","G19","G20"]},
  "stakes": "normal",
  "pub_year": 2011,
  "napkin": {
    "formula": "投资成功 =(内在价值 − 买入价格)+ 情绪纪律",
    "formula_read": "为什么是加法不是乘法:价差是本金、纪律是放大器,二者相加 -- 价差再大,情绪一崩纪律归零,收益也被吃掉一大半。",
    "one_liner": "…",
    "sketch": {
      "type": "cascade",
      "caption": "从错价机会到超额收益的因果骨架",
      "nodes": [
        { "id": "err", "label": "市场常错价" }, { "id": "gap", "label": "价差出现" },
        { "id": "margin", "label": "安全边际", "mid": true }, { "id": "hold", "label": "耐心持有", "mid": true },
        { "id": "cycle", "label": "熬过周期" }, { "id": "alpha", "label": "超额收益" }
      ],
      "edges": [
        { "from": "err", "to": "gap", "label": "" }, { "from": "gap", "to": "margin", "label": "算清" },
        { "from": "margin", "to": "hold", "label": "" }, { "from": "hold", "to": "cycle", "label": "" },
        { "from": "cycle", "to": "alpha", "label": "兑现" }
      ]
    }
  },
  "core_question": "为什么大多数聪明人还是没能在市场里赚到钱?",
  "cover_intro": "马克斯从三十余年的投资备忘录与亲历的多轮牛熊里,归纳出投资最要紧的不是比别人聪明、而是比别人少犯错。全书拎出第二层思维、价值、风险、周期、逆向、耐心等一组彼此咬合的要点,逐一拆解。最后落到一个反直觉的结论:超额收益不来自预测市场,而来自在别人贪婪时警惕、在别人恐惧时下手的纪律。",
  "chapters": [{
    "no": 1,
    "title": "第二层思维:与众不同且更正确,才有超额收益",
    "summary": "一句 30-80 字核心论点(Pass 1,目录态灰字一行)",
    "hook": "人人都看好的股票,凭什么还能赚超额?",
    "anchor": "第1章·约12-24页",
    "narrative": "详实转述 800-1500 字(Pass 2):坡道开场 → 观点+完整案例故事+数据 → 一句接全书主线",
    "excerpts": [{ "text": "原文照录短段 ≤150 字", "anchor": "第1章·约18页" }]
  }],
  "core_ideas": [{
    "idea": "…", "explain": "…", "evidence": "…",
    "anchor": "第3章·约45-52页", "evidence_level": "原文确认",
    "certainty": "book_explicit",
    "layman_analogy": "邻居报低价你不会贱卖房子,持股一绿你却慌着割肉",
    "primary": true, "pillar": 2
  }],
  // certainty:仅 stakes=high 必产(§4.5.16);normal 书可省。与 evidence_level 正交:前者=来源硬度,后者=转述忠实度
  "arguments": { "chain": "…", "chain_steps": ["市场常错价", "价格≠价值", "算清安全边际", "反人性下手"], "hidden_assumptions": ["…"], "counter_examples": ["…"] },
  "cross_domain": [
    { "domain": "工程学", "name": "安全系数", "note": "造桥按 5 倍载荷设计,不是预计超载,是你算不准 -- 同「安全边际」" },
    { "domain": "概率论", "name": "期望值下注", "note": "赔率被市场算错时才下手,而非挑最可能赢的" }
  ],
  "decision_rules": [{ "when": "…", "do": "…", "because": "…", "anchor": "…", "certainty": "book_explicit", "chain_step": 3 }],
  "mental_models": [{
    "model": "…", "evidence": ["…第N章…"], "boundary": "…",
    "how_to_apply": "遇到一个没见过的新资产,先问它的钟摆现在摆到哪一端",
    "chain_step": null
  }],
  "tensions": [{ "a": "…", "b": "…", "note": "…" }],
  "critique": { "blind_spots": ["…"], "era_limits": ["…"], "unproven_assumptions": ["…"], "strongest_objection": "…" },
  "credibility_verdict": "最硬的两条是『风险是永久性损失而非价格波动』与『价格会大幅偏离价值』-- 有大量周期实例支撑,可放心采用;要打折的是逆向操作的可行性,它默认你有足够的耐心与闲置资金扛住长期错价,普通投资者未必具备,书里也没给出可操作的择时判据。",
  "quotes": [{ "text": "原话照录", "anchor": "…", "note": "编辑点评一句", "featured": true }],
  "narrative_arcs": [{ "who": "…", "arc": "…", "lesson": "…", "anchor": "…" }],
  "concepts": [{
    "concept": "安全边际", "one_liner": "…", "stance": "…", "anchor": "…",
    "common_misread": "常被当成『设止损位』,作者指的是买价远低于价值的缓冲垫"
    // 可选 "concept_en":"margin of safety" -- 书籍侧默认全中文,仅少量国际通行信号词(译名易歧义者)按需补英文原词点缀,禁全量中英对照;视频系列才逐条中英(§V)
  }],
  "soul_module": {
    "title": "钟摆永远在两个极端间摆动,却极少停在中点",
    "subtitle": "市场情绪不是围绕理性小幅波动,而是在贪婪与恐惧两端来回冲",
    "type": "curve",
    "intro": "多数人以为市场大部分时间是理性的 -- 恰恰相反,它极少处在『公允』位置。",
    "states": [
      { "label": "贪婪端", "body": "整段解释…", "points": ["输入:连涨", "机理:追高", "输出:泡沫"] },
      { "label": "恐惧端", "body": "整段解释…", "points": ["输入:连跌", "机理:割肉", "输出:超卖"] }
    ],
    "curve": { "series": [{ "label": "市场情绪", "points": [[0,5],[3,9],[6,1],[10,8]], "token": "--red" }] }
  },
  "action_chain": [
    { "label": "认清你在第几层", "explain": "3-6 句整段解释…", "detail": "先看清自己现在是第一层思维还是第二层 -- 第一层看到好公司就想买,第二层还要追问价格里是否已计入了所有乐观预期。做法是每次动手前写下三句:市场共识是什么、我和共识差在哪、凭什么我更对;写不出第三句就说明你只是在跟风,而非赚认知差。书里拿赛马打比方:光挑跑得最快的马没用,要挑赔率被市场算错的那匹。" },
    { "label": "先估价值再看价格", "explain": "…", "detail": "80-150 字扩写段(Pass 2,随 narrative 一起写)…" },
    { "label": "等钟摆到极端", "explain": "…", "detail": "…" },
    { "label": "反人性下手", "explain": "…", "detail": "…" }
  ],
  "self_check": [
    { "q": "上次大跌时你是加仓还是割肉?", "followup": "当时你复核过内在价值没变吗,还是只看了红绿?", "anchor": "第4章" }
  ],
  "persona_card": "(仅人物书)以传主口吻的第一人称身份卡一段",
  "voice_dna": "(仅人物书)句式 / 节奏 / 禁忌"
}
```

### 6.1a 心理学书条件增量(v6.2)

当且仅当顶层 `domain_profile.domain=="psychology"` 时,在上面的通用对象上叠加以下字段。这里的 `claim_id` 是 Step3 外部证据页与 Step7 G24 的连接键:

```jsonc
{
  "domain_profile": {
    "domain": "psychology",
    "subfields": ["judgment-and-decision-making"],
    "work_kind": "popular_science",
    "clinical_relevance": "none"
  },
  "core_ideas": [{
    "claim_id": "loss-aversion-generalizes",
    "claim_type": "descriptive"
  }],
  "decision_rules": [{
    "claim_id": "use-reference-class",
    "claim_type": "predictive"
  }]
}
```

`claim_id` 在 `core_ideas + decision_rules` 合并集合中不得重复;`claim_type` 必须取 §4.5.17 八枚举。旧数据、非心理学书与视频不回填、不触发 G23/G24。

> 约束回顾:`primary:true` 的 core_ideas **1-2 条**(G15);`featured:true` 的 quotes **≤3 条**(§4.5.2);`soul_module.states` **2-3 个同构态**、`subtitle` 非空(G11);`soul_module.curve` **仅 `type=curve` 必填**;`action_chain` **4-5 环**(G13);`self_check` **4-8 条**(G12);书 `chapters[].excerpts` **每章 ≥1**(G14)。**v3 新增**:`cover_intro` **2-3 句、禁比喻、禁复用 napkin ≥12 字连续片段**(G16);`action_chain[].detail` **每环去空白 ≥60 字**(G17);`credibility_verdict` **书籍必产**(G18);`decision_rules[].chain_step` / `mental_models[].chain_step` ∈ **[1,5] 或 null**(牵强留空,禁硬塞)。**v4 新增**:`core_question` **书/视频必产、≤40 字疑问句、禁复用 cover_intro/one_liner ≥12 字连续片段**(G19);`core_ideas[].pillar` ∈ **[1,5] 或 null**(牵强留空);`arguments.chain_steps` **4-8 步、每步 ≤14 字**(G20);`chapters[].hook` **若产则 ≤20 字**(G21);`cross_domain[]` **3-5 条、宁缺毋滥不设机检**;`action_chain[].detail` 末句补**时间盒首步动作**(§4.5.6 自查,不加机检)。**餐巾纸四件套(§3 餐巾纸压缩)**:`napkin.formula_read` **书/视频必产、≤80 字、须含运算符或「乘·加·减·除·归零·缺一·比例·乘积」语义词**(G4 扩展);`napkin.sketch` **可降级(蒸不出干净骨架即省略);若产则 type∈{cascade,fork,loop}、caption 非空、nodes ∈ [6,12] 含 ≥1 中间产物(mid:true)、edges ≥1、label 集合 ≠ 公式右侧项**(G4 扩展,防重画公式凑数)。**v6.1(2026-07-15)**:`stakes` ∈ `{high,normal}`(顶层,缺省 normal,§1.5);**`stakes=high` 时** `decision_rules[]` + `core_ideas[]` 每条必带 `certainty` ∈ `{book_explicit,cross_book_synthesis,general_knowledge}`(§4.5.16,G22 机拦);`normal` 书 certainty 可选、不产不拦。

### 6.2 视频系列例(增量键,详见 §V)

视频系列在书籍 schema 基础上**多写 `source_type` / `videos`,`chapters[]` 多写 `video_no`**,其余字段同构:

```json
{
  "slug": "leimeng-codex", "title": "雷蒙 Codex 实战系列", "author": "雷蒙",
  "book_type": "工具",
  "source_type": "video_series",
  "videos": [{ "no": 1, "title": "…", "url": "https://…", "platform": "youtube" }],
  "series_stats": { "channel": "Dan Koe", "channel_url": "https://…", "channel_followers": 1390000, "total_views": 980662, "as_of": "2026-07-05" },
  "napkin": { "formula": "…", "formula_read": "读法一句 ≤80 字,点明运算符语义(视频同书籍必产)", "one_liner": "…", "sketch": { "type": "cascade|fork|loop", "caption": "…", "nodes": [], "edges": [] } },
  "core_question": "为什么你让 AI 写的代码总是跑不起来?(视频同书籍必产,≤40 字疑问句)",
  "cover_intro": "2-3 句封面简介(视频同书籍三句法·素材从哪来 / 框架是什么 / 结论落在哪;禁比喻、禁复用 napkin;视频必产)",
  "chapters": [{
    "no": 1, "video_no": 1,
    "title": "论点式主题段标题(非『视频1』式)",
    "summary": "清洗后要点摘要",
    "hook": "≤20 字悬念句,取该集招牌演示的具象意象(可选)",
    "anchor": "视频1·03:20",
    "narrative": "详实转述 ≥400 字(Pass 2):口语清洗后仍保留讲解推演过程与演示案例",
    "excerpts": [{ "text": "讲者原话段(繁体照录,可选)", "text_zh": "中文译(仅外语视频:原话非中文时补,渲双语)", "anchor": "视频1·05:10" }]
  }],
  "core_ideas": [{ "idea": "…", "explain": "…", "evidence": "…", "anchor": "视频2·12:30", "evidence_level": "原文确认", "layman_analogy": "…", "primary": true }],
  "soul_module": {
    "title": "…", "subtitle": "…", "type": "compare", "intro": "…",
    "states": [
      { "label": "手动写", "body": "…", "points": ["…"] },
      { "label": "Codex 代写", "body": "…", "points": ["…"] }
    ]
  },
  "action_chain": [{ "label": "…", "explain": "…", "detail": "80-150 字扩写段(Pass 2,视频同书籍必产)" }],
  "self_check": [{ "q": "你上次让 AI 写代码时……?", "followup": "…", "anchor": "视频3" }]
}
```
> 视频例省略的字段(arguments / decision_rules / mental_models / tensions / critique / quotes / concepts)结构与书籍**完全一致**,不再重列;`narrative_arcs` 仅叙事型产;`excerpts` 视频可 0;`persona_card` / `voice_dna` 仅 `book_type=人物`。**v3**:`cover_intro` / `action_chain[].detail` 视频**同书籍必产**;`credibility_verdict` 书籍必产、视频可省;省略字段里的 `decision_rules[].chain_step` / `mental_models[].chain_step` 视频照产、可空(归站规则同 §4.5.11)。**v4**:`core_question`(G19)/ `arguments.chain_steps`(G20)视频**同书籍必产**;`core_ideas[].pillar` / `cross_domain[]` / `chapters[].hook` 视频同书籍规则(pillar 牵强留空、cross_domain 宁缺毋滥、hook 若产 ≤20 字)。

> **v4-D 视频试点固化(Dan Koe 出片,Q6)**——三特性 + 防幻觉 + 去书味,渲染规格见 `html-spec.md §V`:
> 1. **双语引用(外语视频)`text_zh`**:讲者原话非中文时,`quotes[].text_zh` / `chapters[].excerpts[].text_zh` 补一句忠实中文译(英文原话 `<blockquote>` 原样照录 + 中文译走 `.qw-zh`)。中文视频省略此键。**红线:英文原话严禁改写/意译进 `text`,只在 `text_zh` 出中文**。
> 2. **热度条 `series_stats`(替书评豆瓣评分)**:`{channel, channel_url, channel_followers, total_views, as_of}`,取即时快照 + 标 `as_of`(数字随时间变);数据源见 §热度元数据(逐条 `yt-dlp` full extract,`--flat-playlist` 为 NA)。渲 `.vb-heat`(频道粉丝 + 系列总播放)。抓不到 → 该键 null,热度条整块降级。
> 3. **概念中英 `concept_en`(外语视频逐条)**:外语视频每个 `concepts[].concept_en` 补英文原词(书籍侧默认全中文、只国际信号词点缀——见 §concepts 注释;此为视频例外)。渲 `.cc-en`。
> 4. **防幻觉·专名/金句逐字核对转写(硬)**:精读 agent 极易把**博主名/嘉宾名张冠李戴**(实证:Alex Ramsey → 误植更有名的 Alex HormZi 3 处 + 给博主安了没引用的名人)。factcheck 步**必做**:所有人名/专名/金句逐字比对转写文本(去时间码/标点),命中即改回原样或降级 `evidence_level`;转写乱码还原(如 daniel smocked→Schmachtenberger)属正常修正。**禁**把"更有名的同名人"当默认。
> 5. **去残留书味(视频)**:tab② 副标题「一章一章读」→ 视频改「**一段一段看**」;章尾/行动件里「读/翻页/回原书」类书面动词 → 视频改「看/回原视频」;`.cb-kicker` 用平台+题材(「YouTube · AI 编程系列」)非书系定位。tab 主名仍是 verify 硬契约(禁去五 tab 结构)。

> **`quiz` 字段已停产(2026-07-03)**:页面改浏览型、删自测复习 M12,新蒸的 distill.json **不再生成 `quiz[]`**(见 §9)。存量 distill.json 里残留的 `quiz` 无害,填页时忽略即可,不用回改。

字段 → 来源速查:`napkin`(formula/one_liner + **v4 `formula_read` / `sketch`**=§3 餐巾纸压缩四件套)/ `chapters`(no/title/summary/anchor)/ `core_ideas` / `arguments`=§3 三轮 + §4.5;`decision_rules`(含 `chain_step`)=§4.1 + §4.5.11;`mental_models`(含 `how_to_apply` / `chain_step`)=§4.2 + §4.5;`tensions`=§4.3;`critique`=§4.4;`quotes`(含 `note` / `featured`)=R2 关键证据/金句 + §4.5;`narrative_arcs`=叙事书戏剧弧光(§1.3);`concepts`(含 `common_misread`)=R3 知识连接 + §4.5;`layman_analogy` / `primary` / `pillar` / `soul_module` / `action_chain` / `self_check` / `persona_card` / `voice_dna`=§4.5(Pass 1 延展);`cover_intro` / `credibility_verdict`=§4.5.9 / §4.5.10(v3 Pass 1 顶层);`core_question`=§4.5.12 / `cross_domain`=§4.5.13 / `arguments.chain_steps`=§4.5.14(v4 Pass 1);`chapters[].narrative` / `chapters[].excerpts`=§3.5(Pass 2 详实转述);`chapters[].hook`=§4.5.15(v4 Pass 2);`action_chain[].detail`=§4.5.6 + §3.5.6(v3 Pass 2)。

---

## 7. 质量门禁清单(打回条件,命中任一即打回重蒸)

> **门禁分两层(v6,2026-07-12 B-2,与 §1.4 render_profile 配套)**:
> - **Tier-0 底线**(与书型无关,**任何 profile 不可关**):G1 反空洞夸赞 / G2·G3·§5.1 六类 anchor / G14 excerpts 版权≤150 / G15 primary·featured / chain_step 合法 + HTML 侧真封面 / 零外链 / Zero-Hex / data-source≥20 / 破折号 / lang=zh / 体积≤3MB。
> - **Tier-1 形态**(随 `render_profile.active_gates` 生效):G4 公式 / G8 论点标题 / G9 字数 / G10 类比 / G11 soul / G12 self_check / G13·G17 行动链 / G16 cover_intro / G18 裁决 / G19 core_question / G20 论证链阶梯。**无 render_profile(legacy 四型)= 全 Tier-1 生效**(向后兼容);语录/书单/课程/考试按注册表关掉不适配项(见 §1.4 表)。
> - **verify 机制**:`verify_page.py` 按 `active_gates` 变体化 Tier-1 校验,并拦「archetype 不在注册表 / active_gates 或 narrative_mode 被篡改」——**禁逐书手写 active_gates 偷关反注水检查**。**Tier-0 与「新型须先入注册表」不可绕**(收口铁律不变:绝不放宽验证或删检查项来假过关)。

### 7.1 通用门禁

| # | 打回条件 | 判定标准 |
|---|---|---|
| G1 | 出现空洞夸赞词 | 全文命中黑名单任一词:**经典之作 / 内容全面 / 受益匪浅 / 值得一读 / 发人深省 / 引人入胜 / 鞭辟入里**(以黑名单为准;发现新的空洞夸赞词须先补入本黑名单再据以判定,不得临场自由裁量) |
| G2 | 任一 `core_idea` 无 `anchor` | `anchor` 字段空或缺失 |
| G3 | 任一 `decision_rule` / `quote` 无 `anchor`,或任一 `mental_models.evidence` 条目未内嵌 anchor 文本(§5.1) | 同上(evidence 判定:字符串内不含 `第N章`/`约全书XX%处` 任一格式) |
| G4 | 餐巾纸公式含糊,或 `formula_read` 缺失/未解释运算符语义,或 `sketch`(若产)结构不齐/重画公式 | 见 §7.3(主判 + 扩展 a `formula_read` + 扩展 b `sketch`) |
| G5 | `tensions` < 2 对 | 数组长度 <2 |
| G6 | 批判段四件套不齐 | `critique` 任一键为空 |
| G7 | 任一 `core_idea` 缺 `evidence_level` | 字段缺失或不在三值枚举内 |

### 7.2 书型专项门禁(对应 §1.3)

| 书型 | 打回条件 |
|---|---|
| 叙事 | `narrative_arcs` < 3 |
| 人物 | `mental_models` < 5,或任一 model 未过 nuwa 三重验证(§4.2) |
| 工具 | `decision_rules` < 8,或任一 rule 的 `do` 非可执行动作 |
| 论说 | `core_ideas` < 6,或 `arguments` 三件不齐 |

### 7.3 「公式含糊」判定(G4)+ 餐巾纸 formula_read / sketch 门禁(G4 扩展,v4)

> **G4 属 Tier-1(v6 B-2/B-3)**:语录/书单 profile 无公式可提,`active_gates` 不含 G4、本组整关(见 §1.4);别为箴言/清单书硬造公式(硬凑连乘 = 伪造,违反不编造铁律)。**「契合则产,牵强留空」**:某本书的核心确实是一个「概念定义」而非「多因连乘」时,允许 `formula` 写成 `X = 定义式`(右侧是该概念的构成/条件而非乘法项),`formula_read` 解释这个定义为何这样切——这比硬塞一个 `A×B×C` 更诚实。判不出干净公式又不属语录/书单型 → 说明可能判型判错,回 §1.4 复核 archetype。

**G4 主判(`napkin.formula`)**:**必须含 `=` / `≈` / `∝` 之一,且其左侧为被定义的整体量,右侧各运算符号(`+ − - × * ÷ / > < ≥ ≤ → %`)两侧是有意义的量**(定义式 profile 例外见上)。

- ✅ 合格:`投资成功 =(内在价值 − 买入价格)+ 情绪纪律`
- ❌ 打回:`安全边际、市场先生、能力圈`(纯名词并列,无运算关系)
- ❌ 打回:`认知 + 耐心 + 运气`(有 `+` 但只是词组堆叠,无左侧被定义量;须写成 `X = 认知 + 耐心 + 运气` 且各项有实指)

**G4 扩展 a:`napkin.formula_read`(v4,Q4-1/Q1-2,书/视频必产)**。机检命中任一即打回:

- ① 缺 `formula_read` 或空串;
- ② 有效长(去标点空白)> **80 字**;
- ③ **不含运算符**(`= ≈ ∝ + − - × * ÷ / > < ≥ ≤ → %` 任一)**且不含**「乘·加·减·除·归零·缺一·比例·乘积·相乘·相加·相减」任一语义词 -- 即没在解释「为什么用这个运算符」,只是复述公式或又写了一句 one_liner。
- **自查(不机检)**:是否真答了「为什么是 ×/加/减/比例、归零或边界条件」,而非把公式念一遍。范例见 §3。

**G4 扩展 b:`napkin.sketch`(v4,Q4-2,可降级 -- 缺失不打回)**。**若产则**机检命中任一即打回:

- ① `type` ∉ `{cascade, fork, loop}`;
- ② `caption` 空;
- ③ `nodes` 非数组或数 ∉ **[6,12]**;或任一 node 缺 `id`/`label`;
- ④ `edges` 非数组或为空;或任一 edge 缺 `from`/`to`;
- ⑤ **`nodes` 的 `label` 集合与公式右侧项集合完全相同**(把公式右侧几项原样重画一遍凑数 -- 骨架必须展开中间产物/汇流/副产品等公式没有的因果层)。
- **蒸不出干净骨架(节点乱、无清晰因果层、只能重画公式)= 整块省略,不硬凑**(缺失合法);「含 ≥1 层中间产物、是否埋没洞察」属自查。

### 7.4 「叙事压成标签」判定(叙事书专项)

`narrative_arcs[].arc` 必须是 **3-5 句连续叙事**,含具体情节(时间/人物动作/转折三者至少两项)。

- ✅ 合格:「1938 年 A&P 茶叶跌到 36 美元,市场估值低于其流动资本;格雷厄姆复核价值未损后持有,数年后涨到等值 705 美元 -- 价格脱离价值到荒谬,恰是机会。」
- ❌ 打回:「坚持价值投资很重要」(单句抽象总结 = 标签;抽象道理应放 `lesson`,不是 `arc`)

### 7.5 v2/v3 详实 / 浏览层门禁(G8-G18,命中任一即打回)

判定一律机械可判(正则 / 数字 / 枚举),不用「酌情」。narrative / excerpts 的字数按 `source_type` 取档(书 vs 视频)。**「蒸馏自查 + verify 双拦」的项**:蒸馏时先自查语义,verify 机拦可判定部分。

| # | 打回条件 | 判定标准 |
|---|---|---|
| G8 | `chapters[].title` 非论点式(零信息标题) | 命中任一即打回:① 匹配黑名单正则 `^(第?\d+[章节讲集]?\|视频\d+)$`(纯章号 / 集号);② 有效长度(去标点空白)< **8 字**;③ 整标题落通用容器词表(`章节脉络 / 全书脉络 / 内容概要 / 核心内容 / 主要观点 / 金句墙 / 金句 / 总结 / 概述 / 前言 / 结语`)。**判断句(可反驳陈述句)语义靠蒸馏自查;verify 机拦 ①②③。** |
| G9 | `chapters[].narrative` 详实度不足(Tier-1) | 去空白字符数按 `render_profile.narrative_mode` 取档:**full-800** 书<800·视频<400;**dense-card**(课程/考试)<**300**;**list**(语录/书单)不产 narrative → G9 不在 active_gates、本项关。任一章命中即打回该章。 |
| G10 | `core_ideas[].layman_analogy` 有空 | 任一条 `layman_analogy` 缺失或空串。 |
| G11 | `soul_module` 不合规 | 命中任一:缺 `soul_module`;`states` 长度 < 2;`subtitle` 空;`title` 空;`type` ∉ `{compare,chain,curve}`;`type=curve` 但 `curve.series` 缺 / 空。 |
| G12 | `self_check` 不合规 | 长度 < 4 或 > 8;或任一 `q` 不含「你」(非第二人称)。 |
| G13 | `action_chain` 不合规 | 长度 < 4 或 > 5;或任一 `label` 有效长度 > 12 字。 |
| G14 | 书 `chapters[].excerpts` 缺 / 引用超版权红线 | **书籍**任一章 `excerpts` 长度 < 1(**视频不检存在**,可 0);**书/视频**任一 `excerpts.text` 去空白字符数 **> 150**(版权红线,§3.5.4)即打回。 |
| G15 | `primary` / `featured` 数越界 | `core_ideas` 中 `primary===true` 条数 ∉ [1,2];**或** `quotes` 中 `featured===true` 条数 **> 3**。 |
| G16 | `cover_intro`(v3)缺 / 句数越界 / 复用总论 | 命中任一即打回:① 缺 `cover_intro` 或空串;② 句数 ∉ [2,3](按句末标点 `。！？` 切分,末尾无标点的尾串计 1 句);③ 与 `napkin.one_liner` 存在 **≥12 字连续重叠片段**(查重,防封面简介与全书总论重复)。 |
| G17 | `action_chain[].detail`(v3)详实度不足 | 任一环 `detail` 去空白字符数 **< 60**(缺字段 / 空串计 0),命中即打回该环。 |
| G18 | 书 `credibility_verdict`(v3)缺 | **书籍**缺 `credibility_verdict` 或空串即打回(**视频不检**,可省)。 |
| G19 | `core_question`(v4)缺 / 越界 / 复用总论 | 命中任一即打回:① 缺 `core_question` 或空串(书 / 视频必产);② 有效长(去标点空白)> **40 字**,或不以 `?` / `?` 结尾;③ 与 `cover_intro` **或** `napkin.one_liner` 存在 **≥12 字连续重叠片段**(查重)。 |
| G20 | `arguments.chain_steps`(v4)不合规 | 命中任一:缺 `chain_steps` 或数 ∉ **[4,8]**;或任一步有效长 > **14 字**。 |
| G21 | `chapters[].hook`(v4)超长 | 任一章 `hook` **存在且**有效长 > **20 字**即打回该章(缺失不拦,存在性属自查;「具象 / 非论点复述」靠蒸馏自查)。 |
| G22 | `stakes=high` 书 `certainty` 缺失 / 非法(v6.1) | **仅 `stakes=="high"`(§1.5)激活**:`decision_rules[]` 任一条 **或** `core_ideas[]` 任一条缺 `certainty` 或值 ∉ `{book_explicit,cross_book_synthesis,general_knowledge}` 即打回。`stakes=normal` 本项**不检**(certainty 可选)。 |
| G23 | 心理学书 claim 主键 / 类型缺失或非法(v6.2) | **仅 `domain_profile.domain=="psychology"` 激活**:domain_profile 缺必要字段/枚举非法;或 `core_ideas[]`、`decision_rules[]` 任一条缺 `claim_id` / `claim_type`;或 claim_id 非 ASCII kebab、在两数组合并集合中重复;或 claim_type 不在 §4.5.17 八枚举即打回。 |

> **v4 补充**:`core_ideas[].pillar` ∈ [1,5] 或 `null`(同 chain_step 机检,牵强留空);`cross_domain[]` **宁缺毋滥、不设机检门禁**(置信不足不产);`action_chain[].detail` 末句时间盒动作(§4.5.6)靠蒸馏自查、不加机检。

> **原 quiz 门槛已删除**:v2 无任何 `quiz` 相关门禁(§9 已弃用)。`tensions≥2`(G5)/ 批判段四件套(G6)/ **§5.1 六类字段 anchor 必带**(G2/G3 覆盖清单**以 §5.1 为准**,含 `chapters.excerpts` / `self_check`;Task 5 verify 须机拦全 6 类)/ evidence_level(G7)/ 无编造(G1 + §3.5.1 铁律)照旧不放宽。
> **v3 新增门禁 G16-G18**(2026-07-04,sandy 反馈重构):G16 查 `cover_intro` 存在 + 2-3 句 + 不复用 napkin;G17 查 `action_chain[].detail` 每环 ≥60 字;G18 查书籍 `credibility_verdict` 存在。三条均机械可判(Task 6 verify 机拦)。`chain_step` 合法性(∈ [1,5] 或 `null`)一并由 verify 机拦(不单列 G 号)。原 **G8-G15 判定不变**。
> **v4 新增门禁 G19-G21**(2026-07-05,深度分析批次 B):G19 查 `core_question` 存在 + ≤40 字疑问句 + 不复用 cover_intro/one_liner;G20 查 `arguments.chain_steps` 4-8 步、每步 ≤14 字;G21 查 `chapters[].hook` 若产则 ≤20 字。`pillar` 合法性(∈ [1,5] 或 `null`)一并由 verify 机拦(不单列 G 号)。三条均机械可判。原 **G8-G18 判定不变**。
> **v4 批次 B-2 门禁(2026-07-05,餐巾纸四件套)**:**G4 扩展 a** 查 `napkin.formula_read` 存在 + ≤80 字 + 含运算符/语义词(书/视频必产);**G4 扩展 b** 查 `napkin.sketch` 若产则 `type/caption/nodes/edges` 齐全、`nodes` ∈ [6,12]、node.label 集合 ≠ 公式右侧项(sketch 可降级,缺失不拦)。两扩展均并入 G4、机械可判(见 §7.3)。原 **G8-G21 判定不变**。
> **v6.1 门禁 G22(2026-07-15,高后果书确定性)**:`stakes=high`(§1.5)时,`decision_rules[]` + `core_ideas[]` 每条可执行建议必带 `certainty`(§4.5.16 三枚举)。**这是独立 stakes 闸,不随 `render_profile.active_gates`**(后果轴与形态轴正交)—— verify 按 `distill.stakes=="high"` 单独激活、不登记进 archetype 注册表(避免污染 profile 完整性校验 `_lint_profile_integrity`)。`stakes=normal` 书 certainty 可选、不检。事实抽检(SKILL 铁律「不编造」)与 G22 配套:G22 机拦「有没有标 certainty」,抽检管「标得对不对 + 数字真不真」。原 **G1-G21 判定不变**。
> **v6.2 条件门禁 G23(心理学 claim 契约)**:`domain_profile.domain=="psychology"` 时,domain_profile 结构 + 每条 core_idea/decision_rule 的唯一 `claim_id` 与八类 `claim_type` 必须合规。与 G22 一样,G23 不写入 archetype 的 `active_gates`;它由领域轴独立激活。对已知心理学项目调用 `--require-domain psychology`,可把「漏掉整个 domain_profile」也失败关闭;不传时旧书行为不变。G23 只保证「所有待核主张有稳定主键且没有偷换主张类型」,科学证据覆盖由 enrich + Step7 **G24** 单独判定。
> **v4 批次 C 门禁 / 自查(2026-07-05,逐章交互 + UI 精修)**:
>   - **破折号统一(Q7-12,机检)**:verify 机拦「页面可见转述正文出现全角 `——`/`—`」(原文照录 blockquote/qw-card 豁免);写 narrative/summary/卡片文案时破折号一律 `--`(§3.5.2 Pass 2 文风约束)。
>   - **cs-badge 死徽标(Q7-9,机检)**:`chain_step` 关联做法数为 0 → **不渲染 `.cs-badge`**;verify 拦页面出现「0 条…做法」的 `.cs-badge`。
>   - **随机进入自足性(Q5-6,自查)**:每章 narrative 可单独读懂——人名/昵称/自创比喻每章首现带一次性同位语;`chapters[].summary` 不引用未在本句内说明的人物(§3.5.2)。**蒸馏自查,不机检**(语义判定);抽读任 2-3 章 narrative + 全部 summary 核对代号是否悬空。

---

## 8. 超长处理(diagnose.recommendation = 分组蒸馏)

全书 txt 超长、一次吞不下时,按下列 SOP,**禁一次性硬吞、禁跳章抽读**:

1. **分组**:按章节把全书切 **3-5 组**,每组为连续章节、字数尽量均衡,单组 ≤ 约 80K 字(仍超则细分但组数不破 5,组内再分块懒读)。
2. **组内蒸馏**:每组独立跑 §3 三轮(R1-R3),产出组级 partial(core_ideas / rules / models / quotes / concepts / narrative_arcs)。
3. **合成**:汇总各组产物 → 去重合并 → **napkin 与 arguments.chain 就全书重写一次**(不许拼接各组的餐巾纸)→ 章节骨架按真实章号顺序排。
4. **冲突检查**(合成必跑一遍):

   | 检查项 | 处置 |
   |---|---|
   | 同一 `concept` 在不同组结论矛盾 | **保留分歧并在 `note`/`stance` 标注,不抹平** |
   | 同章号重复 / 章号缺漏 | 归并、补齐 |
   | anchor 页码越界(> `pages_est`) | 重算(§5) |
   | napkin 是否覆盖全书而非某一组 | 不覆盖则重写 |

5. **证据降级**:分组导致某点跨组割裂、只在一组见到片段 → 该条 `evidence_level` 至少标 `需复核`。

---

## 9. 自测题生成规则(quiz[])-- 浏览型已弃用(2026-07-03);v6 考试型有条件重启(2026-07-12 B-7)

> **本节已弃用,不再执行。** 页面于 2026-07-03 从「学习型(含自测)」改为「浏览型(纯呈现核心内容)」,删除自测复习板块(M12)整套,骨架已无 `panel-quiz` / `.quiz-card` / ts-fsrs 复习卡。因此:
> - **蒸馏时不再生成 `quiz[]`**(§6 schema 的 `quiz` 字段停产)。
> - `core_ideas` 原本兼作自测出题来源,现只落 M01/M02/M04 的呈现(见 html-spec §1.2.1),不再喂自测。
> - 存量 distill.json 里的 `quiz` 数据无害,保留不动、填页时忽略。
> - **§7 门禁无 quiz 项**:现门禁为 G1-G18(v2 的 G1-G15 + v3 的 G16-G18),均不含任何自测 / quiz 门槛。
> - 若未来恢复自测,再据本节规则重启,并在 vendor 里加回 ts-fsrs。
>
> 以下为历史规则,仅备查:从 `core_ideas + decision_rules + mental_models` 生成 8-12 题主动回忆问答,每题带 anchor、答案可溯、覆盖不同来源。

**v6 重启(2026-07-12 B-7,仅 `render_profile.archetype=考试`)**:考试型的价值单元是「练会/测会」而非「读懂一个思想」,故对该型**有条件重启自测**——但落**新原语** `.recall-card` 记忆卡 + `.worked-example` 例题解析(见 `html-spec.md §1.6`),**不回到旧 M12 / ts-fsrs 全书型自测板块**。出题仍按上方历史规则(主动回忆、带 anchor、答案可溯、覆盖不同来源);记忆卡可 Anki 导出。**其余七型仍不产 quiz**(浏览型定位不变)。首个考试型样书按「先抽样 1 本验收再铺量」补骨架 SLOT 与渲染后固化。

---

## 附:concepts[] 与跨书索引(接口说明)

R3「知识连接」提出的每个可复用概念写进 `concepts[] = {concept, one_liner, stance, anchor}`,供 Step4 跨书索引(`cross-book.md` / `update_index.py`)登记与互链 -- 本手册只负责产出干净的 `concepts`,合并协议(5-tag)不在此文档。

---

## V. 视频系列附则(source_type = video_series)

**只有蒸馏视频系列时读本节;蒸书时整节不适用。** 视频系列的两遍蒸馏方法(§2-§9,含 §3.5 详实转述 + §4.5 延展字段)与书籍**完全一致** -- 三轮压缩、四嫁接件、详实转述、浏览型延展字段、锚点、证据等级、质量门禁的思路照搬。本节只讲「因输入是视频转写稿而不同」的落点(§V.0 取材固定流程 + §V.1-V.6 原有六处 + §V.7 v2 详实/延展层),其余一律回到前文。

### V.0 取材:视频 -> 干净转写稿(固定流程,build_series 之前)

蒸馏吃的是**转写全文**(做三轮压缩/金句/锚点),不是画面语义 -- 故取材按「哪条最干净、最省」分流,不一刀切「YouTube 一律 Gemini」。两个上游 skill 分工(2026-07-05 实测确认,均可直接引用):

| skill | 干什么 | YouTube 免下载 | 何时用 |
|---|---|---|---|
| **video-to-subtitle-summary**(vendor,`~/.claude/skills/`) | 出字幕/转写文本(yt-dlp 抓字幕 / faster-whisper ASR / AI Douyin 下载非 YT) | ✅ 抓字幕 | **默认**:口播/知识型,转写就是价值 |
| **sansheng-gemini-video**(可选外部依赖) | Gemini 原生看画面+音频 -> 转写/结构化理解 | ✅ `fileData.fileUri` 在线看 | **无字幕 / 需画面语义**(演示/代码/图表/PPT) |

**取材 cascade(按平台分流,能不下载就不下载):**

▎**YouTube**(在线优先)
1. 抓字幕:`python ~/.claude/skills/video-to-subtitle-summary/scripts/download_youtube_subtitles.py <url> --output-dir raw/{NN}_{id} --languages <manuallang>,en-US,en,zh-Hans`。
2. **认准【人工】字幕作转写源**:人工字幕文件(如 `subtitle.en-US.vtt`)一句一 cue、**无 `<...><c>` 内联词级标签、无 `align:/position:` 参数、无连续重复行**;VTT 可**直喂 build_series**(`SRT_TIME` 正则 `[,.]` 两用,兼容 vtt 毫秒点)。
   - ⚠️ **坑(Q6-4)**:`Kind: captions` 头**人工/自动都有,不能作判据**;脚本默认落地的 `text.txt`/`subtitle.srt` 常取**自动字幕**,带 `<c>` 词级标签 + 滚动重复约 **3×**(字数虚高 2-3 倍)。**别用 text.txt 当转写源**;快速判真:字数 ≈ 时长×(英文 ~150 / 中文 ~250)wpm 才对,2-3× 于此即为自动字幕。
3. 只有【自动】字幕(无人工)-> 抓下来**必须去重**:去 `<...>` 标签 + 去 `align:/position:` + 折叠连续重复行,再喂 build_series。
4. 无字幕 OR 需画面语义 -> `python ~/.claude/skills/sansheng-gemini-video/scripts/analyze_video.py <url> --prompt "逐字转写带[MM:SS],逐字照录不总结" --fps 0.2 --start/--end`(低 fps + 裁片段控成本;实测 ~$0.01/2min,40min ≈ $0.2;转写质量实测 ≈ 人工字幕)。
5. 兜底 -> 下载音频 + faster-whisper(`ASR_BACKEND=faster-whisper`)。

▎**非 YouTube**(B站/抖音/小红书:**先下载再解析**)
- `video-to-subtitle-summary`:AI Douyin 代理拿直链下载 -> 有平台字幕抓字幕,否则 faster-whisper ASR。需画面语义 -> 下载后**本地文件 inline** 喂 sansheng-gemini-video(非 URL)。

▎**本地视频/音频文件**
- faster-whisper(纯语音)/ inline 喂 sansheng-gemini-video(需画面)。

**热度元数据(供 §3 热度条 / Q6-3)**:逐条 `yt-dlp --skip-download --print "%(view_count)s|%(like_count)s|%(comment_count)s|%(upload_date)s|%(channel_follower_count)s"`。⚠️ `--flat-playlist` 拉列表时这些字段为 `NA`,**必须逐条 full extract**;取即时快照值 + 标 `as_of` 日期(播放量随时间变)。

转写就位后写 `series-input.json`(`transcript` 指向选定的**干净**字幕文件),再跑 `build_series.py` -> `book.txt`(§V.1)。

### V.1 输入形态
- 语料 = `build_series.py` 组装的 `book.txt`:章头 `【视频N】{标题}` 独占一行,时间码标记 `[MM:SS]`(满 1 小时 `[H:MM:SS]`)按段落注入(纯 txt 转写无时间码)。
- distill.json 多写两个键(§6 schema 之外的视频专属,书籍不写):
  ```json
  "source_type": "video_series",
  "videos": [{ "no": 1, "title": "…", "url": "https://…", "platform": "youtube" }]
  ```
  `platform` ∈ `youtube|bilibili`;`chapters[].no` 与 `videos[].no` 一一对应。

### V.2 口语清洗(蒸馏时执行,不改原始转写)
转写稿含寒暄、口头禅、「求关注求三连」、广告口播、跑题闲聊 -- 这些**不计入** `core_ideas` 与 `chapters[].summary`,当噪声滤掉。**唯一例外是 `quotes`**:金句原话照录(可**截断**取核心句,但**禁润色**、禁把口语改写成书面语),沿用 R2 金句铁律。

### V.3 anchor 格式扩展
- 视频锚点两式:`视频{N}`(整集)或 `视频{N}·{MM:SS}`(精确到时间点,取自 book.txt 的时间码标记)。
- **G3 门禁判定正则同步扩展**:原 `第N章`/`约全书XX%处` 之外,`视频\d+` 亦视为合法 anchor(`mental_models.evidence` 内嵌 anchor 的判定一并加此式)。其余门禁(G1/G2/G4-G7)对视频稿**照检不放宽**。
- **v2/v3 门禁(G8-G18)对视频照检**,仅 G9 narrative 走视频档 400、G14 excerpts 视频不检、G18 credibility_verdict 视频不检(可省)、G8 黑名单含 `视频\d+`(详见 §V.7);G10-G13 / G15 / G16 / G17 同书籍不降。

### V.4 硬门槛降配(仅 video_series,按语料总字数)
视频系列体量常小于成书(单集 3 千-1 万字,一个系列约 3-10 万字),硬按书籍门槛会逼模型注水。按 `diagnose.json.chars_total` 分档:

| 语料总字数 | 论说/工具硬门槛调整(v2:narrative 走 G9 视频档 400;quiz 已删,不列) |
|---|---|
| ≥ 6 万 | 原表不变(§1.3:core_ideas≥6 / decision_rules≥8) |
| 3 万-6 万 | core_ideas≥5 / decision_rules≥6 |
| < 3 万 | core_ideas≥4 / decision_rules≥5 |

**`tensions≥2` 与批判段四件套(§7.1 G5/G6)永不降;叙事书弧光门槛(§1.3)若判为叙事型亦不降。** 降配只动「量」的门槛,不动「有没有」的门槛。**v2/v3 门禁同理**:narrative 字数档已在 G9 内按 `source_type` 取视频档 400(不再另降);G8 / G10-G17 属「有没有 / 论点式 / 详实度」类,视频照检不降(G18 credibility_verdict 视频不检)。原 quiz 门槛已删,降配表不再含 quiz 列。

### V.5 书型判定
视频系列照 §1 四型正常判(讲解/评测类多落**论说**或**工具**,访谈/自述类可落**人物**),**不新增第五型**。抽样方式:每个视频取开头段落 + 中段各一处(替代书籍的首/中/末章抽样)。判定顺序与裁决规则完全同 §1.2。

### V.6 章节 = 页面骨架(集数或主题段,目标 5-8 条)
`chapters[]` 是页面脉络骨架,撑起 M03 脑图一级节点与 M04 手风琴,**目标 5-8 条**(与成书章节数量级一致)。按视频数量与单集时长两种切法:

- **多视频系列(`videos_total ≥ 5` 且单集偏短)**:一集一条,`chapters[].no = videos[].no`,`title` = 视频标题,`anchor = 视频{N}`,`video_no = N`。
- **单视频 / 少而长(`videos_total < 5`,或某集 > 20 分钟)**:把长视频按**主题**切段,凑够 5-8 条,每段一条 chapter。`no` 从 1 起**连续编号**(跨视频不重置),`title` = 自拟的主题段小标题(概括这段讲什么),`anchor = 视频{V}·{MM:SS}`(该段起点时间码,取自 book.txt),`video_no = V`(该段所属视频号)。切段依据 book.txt 的时间码 + 话题转折,别按固定时长机械切。

两式都写 `chapters[] = {no, title, summary, anchor, video_no}`(`video_no` 为视频专属,书籍不写);`summary` = 该章/段清洗后要点摘要。**单视频不因「只有一个视频」退化成一章** -- 按主题切够 5-8 段。脑图/手风琴/互链的页内 id 一律 `#ch-{no}`(对齐 `chapters[].no`,不是 video no)。

**`chapters[].title` 亦须论点式(G8 照检)**:切段的主题小标题必须是可反驳的判断句,禁「视频1 / 第一段 / 主题一」式零信息容器名,黑名单含 `^视频\d+$`。

### V.7 v2/v3 详实层与浏览字段(视频同构必产)

书籍 v2/v3 的两遍蒸馏(§3.5 详实转述)与浏览型延展字段(§4.5),视频系列**同构照产**,仅字数档与素材形态不同:

- **narrative(Pass 2,§3.5)**:每个主题段 `chapters[].narrative` **≥400 字**(门禁 G9 视频档)。口语清洗后**仍保留讲解的推演过程与演示案例**(别清洗成干巴要点)。长系列同 §3.5.5 按段分组 fan-out。两级检索的「原文」= book.txt 该段转写切片。
- **excerpts(§3.5.3)**:视频取**讲者原话段**(繁体照录,同 §V.2 金句铁律:可截断、禁润色),`anchor` 用 `视频{N}·{MM:SS}`。**视频可 0 条**(G14 不检视频)。
- **soul_module / action_chain / self_check(§4.5.5-4.5.7)**:视频**同书籍必产**(G11 / G12 / G13 照检不降):书魂取该系列最核心的反直觉主张(compare 型常见,如「手动写 vs Codex 代写」),self_check 的 `q` 第二人称含「你」,action_chain 4-5 环。
- **layman_analogy / primary / quotes.note+featured / mental_models.how_to_apply / concepts.common_misread(§4.5.1-4.5.4)**:同书籍必产(G10 / G15 照检)。
- **persona_card / voice_dna(§4.5.8)**:仅 `book_type=人物`(访谈 / 自述型频道)时产。
- **v3 新增字段(§4.5.9-4.5.11 + §3.5.6)**:`cover_intro`(封面简介三句法,视频**必产**,禁比喻 / 禁复用 napkin,G16 照检)/ `action_chain[].detail`(每环 80-150 字扩写,视频**必产**,G17 照检)/ `decision_rules[].chain_step` + `mental_models[].chain_step`(归站 1-5 可空,同 §4.5.11)照产;`credibility_verdict` **书籍必产、视频可省**(G18 视频不检)。

# topic-craft.md — 多书「主题聚合专题」契约(v6 · StepB)

> 只有为**同一主题下 ≥3 本已蒸作品**做横向聚合时读本节。单书蒸馏、双书均不涉及。对称 `author-craft.md`(StepA 作者演变),但换一根轴。
> **单一权威**:topic.json / 4 视图 / topic.enrich 的字段名以本文件为准,下游(build_topic.py / topic-page-skeleton.html / verify_page.py)一律对齐。

## 0. 定位与铁律

- **StepA vs StepB 的轴不同**:StepA 聚合「同一**作者**的思想**演变**」(时间轴,谁先谁后怎么变);StepB 聚合「同一**主题**下各书的**立场光谱与分歧**」(空间轴,谁和谁在同一议题上站哪边)。**不照搬四视图,是对称迁移** -- 主题侧的自然视图 = 分类地图 / 分歧矩阵 / 维度对照表 / 书目导航。
- **绝不重蒸**:聚合只读各书 `distill.json` + `knowledge-index.json`,不碰 book.txt/raw,脚本内禁跑 LLM / 禁联网。
- **事实 vs 归纳分层(最高铁律)**:分类地图 / 维度对照表 = **书内派生的事实 + 编者归类**,照发;**分歧矩阵的「对立」判定 = 跨书归纳**,分三档诚实标注(见 §4.3 `index_relation`):
  - `CONTRADICTS` — knowledge-index 已入库的真实对立(Step4 人工判定过),渲成红旗「已登记分歧」。
  - `curated` — index 未登记 CONTRADICTS、但编者从各书 stance 对立措辞归纳出的分歧轴,渲成金标「编者归纳的分歧轴」,**须在 `note` 给依据**(哪本书哪句话对立)。不冒充 index 硬事实。
  - `parallel` — 仅「都讨论了主题 X」的松散并列,**不渲成交锋**,只在维度对照表并置「各书分别说了什么」。
- **分歧不抹平,也不硬造**:只有真实对立(CONTRADICTS 或 curated 且有可回指 stance)才进分歧矩阵;松散并列不夸成尖锐分歧(对称 StepA 的 turns verdict 分级 + 一致性反证精神)。
- **成员圈定 = 人工显式列 slugs**:主题边界是编辑判断(「这 13 本算一个睡眠专题」),由 `topic.manual.json` 的 `members:[slug]` 圈定,不改 distill schema、不重蒸、不自动按 tag 归堆。
- **触发门槛**:成员 <3 本 → 不生成(build_topic exit 3),每书页入口卡整段删。
- **可视化**:主题数据形态天然是**表格 / 多列对照卡**(分类分区、书×立场矩阵、维度×书对照),**不套 StepA 的坐标系 SVG**(时间线/ribbon/DAG)。纯 HTML+CSS 表格/卡片,零库零 CDN,更贴数据、更稳。维度对照表每格标来源硬度色点(复用蒸馏页 `.ci-evlevel` 那套 certainty 徽标);来源缺失/非法统一显示 `unverified`,绝不静默升级成「原书明确」。

## 1. 三输入分层(服务「绝不重蒸 + 安全增量重建」)

```
读书蒸馏/topics/{topic_slug}/
  topic.manual.json    # ✍️人工:topic 名/slug/副标/导语 · members(圈定 slugs) · schools(流派归类) · disputes(分歧分组) · dimensions(维度对照) · verdict(怎么选) · consensus/reading_guide。重建永不动。
  topic.enrich.json    # 网搜外证:external_debate(主题外部争议现状,§6)。可选,enrich 步产。
  topic.json           # 🤖 build_topic.py 合并三源 + knowledge-index 的产物(下游只读它)。可重建。
  topic.html           # 主题聚合页(Step 渲染产物)
  (各成员书 distill.json 仍在 读书蒸馏/{slug}/;knowledge-index.json 在 读书蒸馏/ 根;fixture 用 topics/__fixture__/)
```

**重建语义**:新蒸一本同主题书 → 把它 slug 加进 manual.members、补它的 school/dispute/dimension 归类 → 重跑 build_topic.py,🤖 字段(书元数据 + index 摊出的立场)全刷新、manual/enrich 零丢失。**防覆盖栏**:已有 topic.json 且 `topic.manual.json` 缺失 → 拒跑(需 `--force`)。

## 2. topic.json schema(🤖自动聚合 / ✍️人工 / 🔶index播种+人工归类)

```jsonc
{
  "topic": "婴幼儿睡眠",            // ✍️ (manual) 主题名
  "slug": "yingyouer-shuimian",     // ✍️ (manual) topic_slug(ASCII kebab,全站唯一,别撞书 slug)
  "subtitle": "7 大流派 · 13 本经典 · 3 条真分歧",   // ✍️ 可选 副标
  "intro": "…",                     // ✍️ 专题导语(为什么值得做 / 这批书覆盖了什么;渲成定位卡 lead)
  "verdict": {                      // ✍️ 可选:怎么选的收口结论(对称 StepA evolution_verdict)
    "headline": "…(≤40字,一句话总结论,徽章大字)",
    "guidance": [ { "axis": "按月龄|按能接受的哭声程度|…", "when": "0-3 月",
                    "recommend": "…", "books": ["slug"] } ]   // 分流建议,每条可挂推荐书(深链)
  },
  "books": [ { "slug":"…","title":"…","book_type":"…","pub_year":0,"stakes":"high|normal",  // 🤖 直取各 distill
               "school_ids":["s1"],        // 🔶 可归入一个或多个流派(manual.book_meta;旧 school_id 自动兼容)
               "one_liner":"…",           // ✍️ 该书在本主题的一句话定位(manual.book_meta;缺则退化取 distill.napkin/core_question)
               "role_in_topic":"…" } ],   // ✍️ 该书角色(深挖代表作/带过;喂入口卡 + 书目导航)
  "schools": [ { "id":"s1","name":"新生儿安抚派","claim":"该流派的核心主张(可反驳判断句)",   // ✍️ 流派归纳(对称 StepA periods)
                  "kind":"theoretical|methodological|applied|mixed",
                  "evidence_status":"supported|mixed|contested|not_supported|not_testable|unverified",
                  "members":["slug"],"anchor_book":"slug",   // anchor_book=该流派深挖代表作
                  "color_idx":0 } ],
  "disputes": [ { "id":"d1","question":"自我安抚能不能训练出来?(可反驳的真问题)","axis":"训练派 vs 反训练派",  // 🔶
                   "question_type":"conceptual|descriptive|causal|predictive|intervention|methodological|normative",
                  "concept":"自我安抚/自主入睡",        // 关联的 knowledge-index concept 名(可 null)
                  "index_relation":"CONTRADICTS|curated|parallel",  // 🤖 由 index 登记状态判定(§4.3)
                  "positions":[ { "label":"可训练/后天习得",
                                  "books":[ { "slug":"…","stance":"可回指原文的立场句","quote":"原文≤150字","anchor":"第X章" } ] },
                                { "label":"不可训练/发育里程碑","books":[ {…} ] } ],
                   "note":"编者依据(curated 分歧必填:指出哪本哪句对立)",
                   "adjudication": {
                     "status":"supported|mixed|contested|not_supported|not_testable|unverified",
                     "book_view":"原书之间到底怎么分歧",
                     "research_view":"外部研究当前如何裁决",
                     "boundary_conditions":"在哪些人群/情境下结论可能变化"
                   },
                   "sources":["https://…"] } ],   // ✍️ 外证可选;有则只收合法 http(s)
  "dimensions": [ { "id":"dim1","name":"自主入睡起始月龄","note":"…",   // ✍️🔶 维度对照表(topic 独有,吃 certainty)
                    "cells":[ { "slug":"…","value":"3-4 月","certainty":"book_explicit|cross_book_synthesis|general_knowledge|unverified","anchor":"第X章" } ] } ],
  "consensus": { "agreements":[ {"text":"跨书共识(可反驳判断句)","books":["slug"]} ],   // ✍️ 可选(对称 StepA critique)
                 "caveats":[ {"text":"这批书的集体局限/该信几分"} ] },
  "reading_guide": [ { "slug":"…","why":"读它能懂什么 / 什么人先读它" } ],   // ✍️ 可选(对称 StepA reading_path)
  "external_debate": null,          // ← enrich:主题外部争议现状(§6);整块 null → 该板块不渲染
  "_provenance": { "generated_from":["slug"],"topic_slug":"…","member_count":0,"school_count":0,
                   "dispute_count":0,"aggregator_version":"1","warnings":[] }   // 🤖(时间戳由主控事后补,脚本不取 Date)
}
```

## 3. build_topic.py 契约

**用法**:`python build_topic.py --topic "<主题名>" --data-root "<读书蒸馏>" --manual "<topic.manual.json>" [--index <knowledge-index.json>] [--enrich <topic.enrich.json>] --out "<topic.json>" [--force]`
成员圈定**只认 `manual.members`**(显式 slug 列表);`--data-root` 用于定位各 `{slug}/distill.json` 与默认 `<data-root>/knowledge-index.json`。

**流程**:① 读 manual.members → 逐个加载 `<data-root>/{slug}/distill.json`(缺失记 warning 并剔除)② 门槛:有效成员 <3 → exit 3(不生成)③ 防覆盖栏:out 已存在且 manual 缺失且无 --force → exit 2 ④ 派生 🤖 字段(§4 规则)⑤ 并入 manual(✍️/🔶)+ index(disputes 立场摊平 / index_relation 判定)+ enrich(external_debate)⑥ 写 topic.json + 打印各段条数 + `_warnings`。

**🤖 确定性派生(纯 Python,集合运算,禁 LLM/联网)**:
- **books**:从各 distill 直取 `title/book_type/pub_year/stakes`;合并 manual.book_meta 的 `school_ids[]/one_liner/role_in_topic`(缺 one_liner 回退 distill 的 `napkin.one_liner`/`core_question`)。旧 `school_id` 自动归一成单元素 `school_ids`,输出只写新字段。
- **disputes 立场摊平**:对每条 manual dispute,positions[].books[] 里每个 slug **从 knowledge-index 该 `concept` 的 entries 自动拉 `stance/quote/anchor/relation`**;index 无该 concept-slug 时用 manual 内联提供的 stance/quote/anchor(fallback,记 warning)。
- **index_relation 判定**(§4.3):看该 dispute.concept 在 index 的 entries -- 任一 entry `relation==CONTRADICTS` → `CONTRADICTS`;否则若 manual 标了 `curated:true`(或 positions ≥2 且各有 books)→ `curated`;都不满足 → `parallel`。
- **certainty 校验**:dimensions.cells[] 缺/非法 `certainty` 时一律写 `unverified` 并记 warning;非 `unverified` 还必须以 anchor 精确回指对应 distill 的 `decision_rules[]`/`core_ideas[]`,回指失败同样降级。**禁止默认或推断 `book_explicit`**--「没有来源」不能推成「书中明确」。
- **统计**:member_count/school_count/dispute_count、schools 补 anchor_book 的 title、color_idx 缺则按序补。
**✍️ 认知部分(不在脚本内跑 LLM,由 manual 提供)**:topic/slug/subtitle/intro/verdict、schools 的 name+claim+members、disputes 的 question+axis+concept+positions 分组、dimensions 的 name+cells(slug+value)、consensus、reading_guide、book_meta。脚本对这些**只做「读 manual 填入 + 校验(slug∈成员 / certainty 合法 / members⊆成员)/ 无则留空 + 记 warning」**,不臆造。

**校验硬门**:builder 在派生前直接拒绝重复 `schools[].id`、school 内重复/非成员 slug、脱离本 school 的 `anchor_book`，以及 `book_meta.school_ids` 重复或引用不存在 school(退出 2,不落 topic.json),避免生成孤儿引用;其余 members 中 distill 缺失、其他视图 slug 不在成员集、concept/stance/anchor 问题进入明确 warning/降级。verify 再完整校验 school 双向回指与唯一性、`kind/evidence_status/question_type/adjudication/certainty` 枚举和必需字段;所有外证 URL 必须经 URL parser 得到 `http(s)` + 非空 host,但不做联网可达性探测。

## 4. 派生规则 + 4 视图数据契约

### 4.1 schools[](分类地图 · 流派分区卡)
```jsonc
{ "id":"s1","name":"新生儿安抚派","claim":"…","kind":"applied","evidence_status":"mixed","members":["slug"],"anchor_book":"slug","color_idx":0 }
```
- **来源**:纯 manual(knowledge-index 无「流派」结构,聚合器**不自己发明流派**)。build_topic 只校验 members⊆成员、补 color_idx、把 anchor_book 解析成 title。
- **呈现**:每流派一张卡(对称 StepA 分期卡):流派名(color_idx 上色左边条)+ kind + claim(可反驳主张)+ evidence_status 科学证据状态 + 代表作深链(anchor_book)+ 成员书 chip(深链)。一本书可同时出现在多个流派;手机端单列。

### 4.2 dimensions[](维度对照表 · topic 最硬增量)
```jsonc
{ "id":"dim1","name":"自主入睡起始月龄","note":"…",
  "cells":[ { "slug":"…","value":"3-4 月","certainty":"book_explicit|cross_book_synthesis|general_knowledge|unverified","anchor":"第X章" } ] }
```
- **来源**:name/cells.value 纯 manual(distill 的 decision_rules 是自由文本、无维度结构,**无法自动归维**);certainty 优先 manual,缺则 build_topic 从 distill 按 anchor 拉、拉不到/非法即 `unverified`。
- **呈现**:一维一表格块(行=维度值、列=书,或一维一张横向对照条);每格 `value` + **来源硬度色点**(复用 `.ci-evlevel` 模型:book_explicit→绿/cross_book_synthesis→金/general_knowledge→muted/unverified→红并写「未核」)。空 cell(某书该维无数据)留白不编。这是「A 相对普通书单最硬的增量」-- 让读者一眼看清「这个数字是书里白纸黑字,还是编者跨书合成」。

### 4.3 disputes[](分歧矩阵 · 多列立场对照)
```jsonc
{ "id":"d1","question":"…","question_type":"causal","axis":"…","concept":"…","index_relation":"CONTRADICTS|curated|parallel",
  "positions":[ { "label":"…","books":[ {"slug","stance","quote","anchor"} ] } ], "note":"…",
  "adjudication":{"status":"mixed","book_view":"…","research_view":"…","boundary_conditions":"…"},
  "sources":["https://…"] }
```
- **候选来源**:manual 圈定 concept + positions 分组(哪些 slug 站哪边);build_topic 从 knowledge-index 摊各 slug 立场 + 判 index_relation(§3)。
- **index_relation 三档(诚实标注,对称 StepA verdict)**:
  - `CONTRADICTS` — index 已登记真实对立 → 红旗「已登记分歧」。
  - `curated` — 编者从各书立场对立归纳(index 未登记)→ 金标「编者归纳的分歧轴」,`note` 必给依据。**回补 index 后重跑会升级为 CONTRADICTS**。
  - `parallel` — 松散并列 → **不进分歧矩阵**(降级到维度对照表并置)。builder 会剔除;为兼容旧 topic.json,verify 可接受其作为追溯数据,但模板与渲染冒烟均保证绝不生成 `.dsp-card`。
- **呈现**:每分歧一张卡:question(判断句)+ question_type + index_relation 旗标 + axis + `positions` 多列对照(每列 label + 各书 stance/quote/anchor 深链)。其后固定三栏:① **原书怎么说**=`adjudication.book_view`;② **外部研究怎么说**=`research_view` + sources;③ **适用边界与风险**=`boundary_conditions`。**作者之间有分歧不等于科学证据 CONTRADICTS**:前者由 positions/index_relation 表达,后者只由 adjudication.status + 外证表达。

### 4.4 books[](书目导航)
- 🤖 直取 distill 元数据 + manual role_in_topic/one_liner。呈现对称 StepA renderBooks:每书一行(year? + title + book_type chip + role_in_topic + 深链 `../{slug}/{slug}.html`)。主题书可无 pub_year 排序键则按 manual.members 顺序。

## 5. topic.html 板块骨架(倒金字塔 · 成果前置)

页顶眉题(`{topic} · 主题聚合`,**无大字 hero**) → **定位卡直接开场**(左:topic 名 H1 + subtitle + intro lead;右:统计字段 N 本/M 流派/K 分歧 + 成员书 chip)→ **① 怎么选(verdict,收口前置)** → **② 分类地图(schools ⭐,一屏看清流派光谱)** → **③ 分歧矩阵(disputes,真交锋)** → **④ 维度对照表(dimensions,吃 certainty 的硬增量)** → **⑤ 书目导航(深链)** → 该信几分(consensus,可选) → 怎么读(reading_guide,可选) → 外部争议(external_debate,enrich,可选) → footer(AI 是地图别当目的地)。**先「分类/怎么选」给扫读者,后「分歧/对照」给深读者**。

每板块 `<section hidden>` + host div,render 内 `if(空) return; show('sec-x')`(对称 StepA);`[hidden]{display:none!important}`。定位卡 `#tp-card` 无 hidden(总渲染,页面开场)。空数据整块隐藏,不留占位。

## 6. topic.enrich.json 契约(主题外部争议层,enrich 步产,可选)

```jsonc
"external_debate": {   // 整块 null → 该板块 + 入口一并不渲染
  "topic":"…","scope":["slug≥3"],"tagline":"≤50字,可null",
  "current_consensus":"当前学界/权威机构主流立场(带 source)",
  "open_questions":[ {"q":"…","camps":[{"who":"…","say":"含立场原话≤80字","source":"url"}]} ],
  "sources":["url"] }
```
- **降级**:<3 部→不生成;整块搜空→ `external_debate` null(该板块整块隐藏,但分类地图/分歧矩阵/维度对照表作书内事实照发)。工具链按 `enrich.md §3.4` 路由表选一个引擎(中文观点→AnySearch;要原话段落→doubao_search;英文→Tavily;内置 WebSearch 仅末位回退),一次失败即换、禁重试轰炸,外证须可点击 URL。

## 7. 每书页「主题入口卡」(page-skeleton)

每成员书蒸馏页顶部加一张卡:`本书属于 {topic} 主题聚合(共 {N} 本 · {school_name}派)→ 查看主题全景`,链到 `../topics/{topic_slug}/topic.html`。**降级**:该主题 <3 部已蒸 或 无 `topics/{topic_slug}/topic.json` → 整卡不渲染(单书页不受影响)。SLOT 名 `SLOT:TOPIC-ENTRY`,class `.topic-entry`,子元素前缀 `te-*`(对称 AUTHOR-ENTRY 的 `ae-*` / J-VIEWS-ENTRY 的 `ve-*`)。

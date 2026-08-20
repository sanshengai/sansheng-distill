# topic-craft.md — 多书「主题聚合专题」契约(v7 · StepB)

> 只有为**同一主题下 ≥3 本已蒸作品**做横向聚合时读本节。单书蒸馏、双书均不涉及。对称 `author-craft.md`(StepA 作者演变),但换一根轴。
> **单一权威**:topic.json / 4 个核心视图 + 独立平行对照 / topic.enrich 的字段名以本文件为准,下游(build_topic.py / topic-page-skeleton.html / verify_page.py)一律对齐。

## 0. 定位与铁律

- **StepA vs StepB 的轴不同**:StepA 聚合「同一**作者**的思想**演变**」(时间轴,谁先谁后怎么变);StepB 聚合「同一**主题**下各书的**立场光谱与分歧**」(空间轴,谁和谁在同一议题上站哪边)。**不照搬四视图,是对称迁移** -- 主题侧的 4 个核心视图 = 分类地图 / 分歧矩阵 / 维度对照表 / 书目导航;只有编辑显式声明时,另加不计入分歧数的平行对照。
- **绝不重蒸**:聚合只读各书 `distill.json` + `knowledge-index.json`,不碰 book.txt/raw,脚本内禁跑 LLM / 禁联网。
- **事实 vs 归纳分层(最高铁律)**:分类地图 / 维度对照表 = **书内派生的事实 + 编者归类**,照发;**分歧矩阵的「对立」判定 = 跨书归纳**,只收两档真争议(见 §4.3 `index_relation`):
  - `CONTRADICTS` — knowledge-index 已入库的真实对立(Step4 人工判定过),渲成红旗「已登记分歧」。
  - `curated` — index 未登记 CONTRADICTS、但编者从各书 stance 对立措辞归纳出的分歧轴,渲成金标「编者归纳的分歧轴」,**须在 `note` 给依据**(哪本书哪句话对立)。不冒充 index 硬事实。
- **平行不是争议**:`parallel` 只表示各书在同一问题上提供互补镜头,只能由编辑在 `parallel_comparisons[]` 显式声明并渲成独立 `.cmp-card`;它不进入 `disputes[]`、不生成 `.dsp-card`、不计入分歧数。算法判出的松散 `parallel` 直接剔除,绝不自动升级为比较结论。
- **分歧不抹平,也不硬造**:只有真实对立(CONTRADICTS 或 curated 且有可回指 stance)才进分歧矩阵;平行对照必须至少有两列非空、可回指的书内立场(对称 StepA 的 turns verdict 分级 + 一致性反证精神)。
- **成员圈定 = 人工显式列 slugs**:主题边界是编辑判断(「这 13 本算一个睡眠专题」),由 `topic.manual.json` 的 `members:[slug]` 圈定,不改 distill schema、不重蒸、不自动按 tag 归堆。它是精确成员契约而非候选池:任一 slug 非法、文件缺失/损坏或路径 slug 与 `distill.slug` 不一致均 exit 2,不允许缩成残缺集合继续生成。
- **书页路由 fail-closed**:`manual.book_meta.{slug}.web_url` 只允许同站根相对路径(单 `/` 开头,禁 `//`、反斜杠、空白/控制字符及明文或多重 URL 编码后的 `.`/`..` 穿越);非法值剔除并 warning,模板/verify 再防守。字段缺失时保留旧路由 `../{slug}/{slug}.html`,旧主题零行为变化。
- **触发门槛**:成员 <3 本 → 不生成(build_topic exit 3),每书页入口卡整段删。
- **可视化**:主题数据形态天然是**表格 / 多列对照卡**(分类分区、书×立场矩阵、维度×书对照),**不套 StepA 的坐标系 SVG**(时间线/ribbon/DAG)。纯 HTML+CSS 表格/卡片,零库零 CDN,更贴数据、更稳。维度对照表每格标来源硬度色点(复用蒸馏页 `.ci-evlevel` 那套 certainty 徽标);来源缺失/非法统一显示 `unverified`,绝不静默升级成「原书明确」。

## 1. 三输入分层(服务「绝不重蒸 + 安全增量重建」)

```
读书蒸馏/topics/{topic_slug}/
  topic.manual.json    # ✍️人工:topic 名/slug/副标/导语 · members(精确 slugs) · book_meta(归类/安全深链) · schools(流派归类) · disputes(真争议) · parallel_comparisons(显式平行对照) · dimensions(维度对照) · verdict(怎么选) · consensus/reading_guide。重建永不动。
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
                "role_in_topic":"…",       // ✍️ 该书角色(深挖代表作/带过;喂入口卡 + 书目导航)
                "web_url":"/library/work-a.html" } ], // ✍️ 可选;只允许安全同站根相对路径,缺则旧路由
  "schools": [ { "id":"s1","name":"新生儿安抚派","claim":"该流派的核心主张(可反驳判断句)",   // ✍️ 流派归纳(对称 StepA periods)
                  "kind":"theoretical|methodological|applied|mixed",
                  "evidence_status":"supported|mixed|contested|not_supported|not_testable|unverified",
                  "members":["slug"],"anchor_book":"slug",   // anchor_book=该流派深挖代表作
                  "color_idx":0 } ],
  "disputes": [ { "id":"d1","question":"自我安抚能不能训练出来?(可反驳的真问题)","axis":"训练派 vs 反训练派",  // 🔶
                   "question_type":"conceptual|descriptive|causal|predictive|intervention|methodological|normative",
                  "concept":"自我安抚/自主入睡",        // 关联的 knowledge-index concept 名(可 null)
                   "index_relation":"CONTRADICTS|curated",  // 🤖 仅真争议;parallel 独立放下方(§4.3/§4.4)
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
  "parallel_comparisons": [ {             // ✍️ 可选;独立互补镜头,不属于 disputes、不计入分歧数
    "id":"p1","question":"这些方法分别在解决问题的哪一层?","question_type":"conceptual",
    "axis":"机制层 vs 操作层","concept":"主题概念","index_relation":"parallel",
    "positions":[ { "label":"机制解释","books":[ { "slug":"…","stance":"可回指原文的立场句","quote":"原文≤150字","anchor":"第X章" } ] },
                  { "label":"操作方案","books":[ { "slug":"…","stance":"可回指原文的立场句","quote":"原文≤150字","anchor":"第Y章" } ] } ],
    "note":"为什么值得并置,但不构成对立",
    "adjudication":null,
    "sources":[]
  } ],
  "dimensions": [ { "id":"dim1","name":"自主入睡起始月龄","note":"…",   // ✍️🔶 维度对照表(topic 独有,吃 certainty)
                    "cells":[ { "slug":"…","value":"3-4 月","certainty":"book_explicit|cross_book_synthesis|general_knowledge|unverified","anchor":"第X章" } ] } ],
  "consensus": { "agreements":[ {"text":"跨书共识(可反驳判断句)","books":["slug"]} ],   // ✍️ 可选(对称 StepA critique)
                 "caveats":[ {"text":"这批书的集体局限/该信几分"} ] },
  "reading_guide": [ { "slug":"…","why":"读它能懂什么 / 什么人先读它" } ],   // ✍️ 可选(对称 StepA reading_path)
  "external_debate": null,          // ← enrich:主题外部争议现状(§6);整块 null → 该板块不渲染
  "_provenance": { "generated_from":["slug"],"topic_slug":"…","member_count":0,"school_count":0,
                    "dispute_count":0,"parallel_comparison_count":0,"aggregator_version":"1","warnings":[] }   // 🤖 parallel 字段仅显式声明时输出;时间戳由主控事后补
}
```

## 3. build_topic.py 契约

**用法**:`python build_topic.py --topic "<主题名>" --data-root "<读书蒸馏>" --manual "<topic.manual.json>" [--index <knowledge-index.json>] [--enrich <topic.enrich.json>] --out "<topic.json>" [--force]`
成员圈定**只认 `manual.members`**(显式 slug 列表);`--data-root` 用于定位各 `{slug}/distill.json` 与默认 `<data-root>/knowledge-index.json`。显式成员必须全部可读且自报 slug 一致,否则 exit 2,不得把「载入失败」误当「不属于本主题」。

**流程**:① 读 `manual.members` → 精确加载 `<data-root>/{slug}/distill.json`(非法 slug、缺文件、JSON 损坏、`distill.slug != 路径 slug` 任一命中即 exit 2,不落残缺集合)② 门槛:成员 <3 → exit 3(不生成)③ 防覆盖栏:out 已存在且 manual 缺失且无 --force → exit 2 ④ 派生 🤖 字段(§4 规则)⑤ 并入 manual(✍️/🔶)+ index(disputes 真争议立场摊平 / 显式 parallel_comparisons 独立解析)+ enrich(external_debate)⑥ 写 topic.json + 打印各段条数 + `_warnings`。

**🤖 确定性派生(纯 Python,集合运算,禁 LLM/联网)**:
- **books**:从各 distill 直取 `title/book_type/pub_year/stakes`;合并 manual.book_meta 的 `school_ids[]/one_liner/role_in_topic/web_url`(缺 one_liner 回退 distill 的 `napkin.one_liner`/`core_question`)。旧 `school_id` 自动归一成单元素 `school_ids`,输出只写新字段。`web_url` 仅在通过安全根相对路径归一化后写入;非法值剔除并 warning,缺字段仍走旧深链。
- **disputes 立场摊平**:对每条 manual dispute,输入用 `positions[].members[]` 列 slug(也可用含 slug/stance/quote/anchor 的内联对象);builder 输出为 `positions[].books[]`,并优先从 knowledge-index 该 `concept` 的 entries 自动拉 `stance/quote/anchor/relation`;index 无该 concept-slug 时用 manual 内联值 fallback,记 warning。
- **真争议判定**(§4.3):看该 dispute.concept 在 index 的 entries -- 任一 entry `relation==CONTRADICTS` → `CONTRADICTS`;否则若 manual 标了 `curated:true`(或 positions ≥2 且各有 books)→ `curated`;都不满足只说明「尚无对立证据」,builder 判为松散 `parallel` 后从 disputes 剔除,**不会自动搬进平行对照**。
- **平行对照解析**(§4.4):只读 manual 的 `parallel_comparisons[]`;兼容旧 manual 写法 `disputes[].parallel:true`,但二者都输出到独立 `parallel_comparisons[]`。复用 index/manual 立场解析,每项至少两列须各有一条非空 stance,否则 warning + fail-closed 跳过。
- **certainty 校验**:dimensions.cells[] 缺/非法 `certainty` 时一律写 `unverified` 并记 warning;非 `unverified` 还必须以 anchor 精确回指对应 distill 的 `decision_rules[]`/`core_ideas[]`,回指失败同样降级。**禁止默认或推断 `book_explicit`**--「没有来源」不能推成「书中明确」。
- **统计**:member_count/school_count/dispute_count;仅显式声明平行对照时再输出 `parallel_comparison_count`;schools 补 anchor_book 的 title、color_idx 缺则按序补。
**✍️ 认知部分(不在脚本内跑 LLM,由 manual 提供)**:topic/slug/subtitle/intro/verdict、schools 的 name+claim+members、disputes 的 question+axis+concept+positions 分组、parallel_comparisons 的 question+axis+concept+positions 分组、dimensions 的 name+cells(slug+value)、consensus、reading_guide、book_meta。脚本对这些**只做「读 manual 填入 + 校验(slug∈成员 / certainty 合法 / members⊆成员)/ 无则留空 + 记 warning」**,不臆造。

**校验硬门**:builder 在派生前直接拒绝 `manual.members` 中任一非法项、对应 distill 缺失/损坏/自报 slug 不一致，以及重复 `schools[].id`、school 内重复/非成员 slug、脱离本 school 的 `anchor_book`、`book_meta.school_ids` 重复或引用不存在 school(退出 2,不落 topic.json),避免静默缩成员或生成孤儿引用;其他视图 slug、concept/stance/anchor 问题进入明确 warning/降级。verify 再完整校验 school 双向回指与唯一性、`kind/evidence_status/question_type/adjudication/certainty` 枚举和必需字段、`books[].web_url` 安全根相对路径,以及 §4.3/§4.4 的争议和平行独立 schema。所有外证 URL 必须经 URL parser 得到 `http(s)` + 非空 host,但不做联网可达性探测;渲染冒烟还须校验非 parallel 可渲染分歧的 `.dsp-card` 精确数量与 `parallel_comparisons[]` 的 `.cmp-card` 精确数量,并禁止两种卡跨容器混放。

## 4. 派生规则 + 4 个核心视图及独立平行对照数据契约

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
{ "id":"d1","question":"…","question_type":"causal","axis":"…","concept":"…","index_relation":"CONTRADICTS|curated",
  "positions":[ { "label":"…","books":[ {"slug","stance","quote","anchor"} ] } ], "note":"…",
  "adjudication":{"status":"mixed","book_view":"…","research_view":"…","boundary_conditions":"…"},
  "sources":["https://…"] }
```
- **候选来源**:manual 圈定 concept + positions 分组(哪些 slug 站哪边);build_topic 从 knowledge-index 摊各 slug 立场 + 判真争议 relation(§3)。
- **index_relation 两档(诚实标注,对称 StepA verdict)**:
  - `CONTRADICTS` — index 已登记真实对立 → 红旗「已登记分歧」。
  - `curated` — 编者从各书立场对立归纳(index 未登记)→ 金标「编者归纳的分歧轴」,`note` 必给依据。**回补 index 后重跑会升级为 CONTRADICTS**。
- **兼容只读旧数据**:历史 `topic.json` 若仍在 `disputes[].index_relation="parallel"`,verify 只把它当追溯数据放行;模板与渲染冒烟保证绝不生成 `.dsp-card`。新构建不得写这种形态;需要正式呈现时迁到 §4.4。
- **呈现**:每分歧一张卡:question(判断句)+ question_type + index_relation 旗标 + axis + `positions` 多列对照(每列 label + 各书 stance/quote/anchor 深链)。其后固定三栏:① **原书怎么说**=`adjudication.book_view`;② **外部研究怎么说**=`research_view` + sources;③ **适用边界与风险**=`boundary_conditions`。**作者之间有分歧不等于科学证据 CONTRADICTS**:前者由 positions/index_relation 表达,后者只由 adjudication.status + 外证表达。

### 4.4 parallel_comparisons[](平行对照 · 互补镜头,非争议)
```jsonc
{ "id":"p1","question":"…","question_type":"conceptual","axis":"…","concept":"…","index_relation":"parallel",
  "positions":[ { "label":"机制解释","books":[ {"slug":"…","stance":"…","quote":"…","anchor":"…"} ] },
                { "label":"操作方案","books":[ {"slug":"…","stance":"…","quote":"…","anchor":"…"} ] } ],
  "note":"为什么值得并置,但不构成对立",
  "adjudication":null,
  "sources":[] }
```
- **来源与迁移**:只能由 manual `parallel_comparisons[]` 显式声明(输入 position 同 dispute,用 `members[]` 列 slug/内联立场);旧 manual `disputes[].parallel:true` 作为迁移入口也会写入本数组。普通 dispute 仅因算法判为松散 parallel 时会被剔除,不会自动进入本数组。
- **独立 schema 硬门**:`id` 必须非空、数组内唯一且不得撞 `disputes[].id`;`index_relation` 必须精确为 `parallel`;`question` 必填,`question_type` 只能用规定枚举或 null;每个 position 必须有非空 label 与 books 数组,书 slug 必须是合法主题成员、stance 必须非空,整项至少两列各有一条有效 stance。`adjudication` 只能为 null 或含 `status/book_view/research_view/boundary_conditions` 的完整对象;status 若为 `supported|mixed|contested|not_supported`,至少须有 1 条合法 http(s) source。
- **呈现与数量门**:每项只渲成 `#parallels-host` 内一张 `.cmp-card[data-index-relation="parallel"]`,标题明确「平行对照 · 互补镜头」,不使用分歧旗标、不计入 dispute_count。渲染冒烟要求 `.cmp-card` 数量与 JSON 数组长度精确相等;`#disputes-host` 禁 `.cmp-card`,`#parallels-host` 禁 `.dsp-card`。

### 4.5 books[](书目导航)
- 🤖 直取 distill 元数据 + manual `book_meta` 的 role_in_topic/one_liner/web_url。呈现对称 StepA renderBooks:每书一行(year? + title + book_type chip + role_in_topic + 深链)。合法 `web_url` 优先;缺字段退回 `../{slug}/{slug}.html`,因此旧书零行为变化。主题书可无 pub_year 排序键则按 manual.members 顺序。

## 5. topic.html 板块骨架(倒金字塔 · 成果前置)

页顶眉题(`{topic} · 主题聚合`,**无大字 hero**) → **定位卡直接开场**(左:topic 名 H1 + subtitle + intro lead;右:统计字段 N 本/M 流派/K 真分歧 + 成员书 chip)→ **① 怎么选(verdict,收口前置)** → **② 分类地图(schools ⭐,一屏看清流派光谱)** → **③ 分歧矩阵(disputes,真交锋)** → **③b 平行对照(parallel_comparisons,互补镜头,可选且不计入分歧)** → **④ 维度对照表(dimensions,吃 certainty 的硬增量)** → **⑤ 书目导航(深链)** → 该信几分(consensus,可选) → 怎么读(reading_guide,可选) → 外部争议(external_debate,enrich,可选) → footer(AI 是地图别当目的地)。**先「分类/怎么选」给扫读者,后「真分歧/平行/维度」给深读者;三类对照必须用独立容器与卡型**。

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

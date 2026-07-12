# author-craft.md — 多书作者「思想演变专题」契约(v5)

> 只有为**同一作者 ≥2 部已蒸作品**做演变聚合时读本节。单书蒸馏不涉及。设计源:`docs/2026-07-05-v5-作者演变专题-设计方案.md`。
> **单一权威**:author.json / 4 视图 / author.enrich 的字段名以本文件为准,下游(build_author.py / author-page-skeleton / verify)一律对齐。

## 0. 定位与铁律

- **绝不重蒸**:聚合只读各书 `distill.json`,不碰 book.txt/raw。
- **事实 vs 叙事分层(最高铁律)**:时间线 / 母题 / 概念演化图 = **书内派生的事实**,照发;**思想转向(turns)= 跨书推断的叙事,高幻觉区**,单条无 `author.enrich.json` 外证不强渲染(见 §5 verdict)。
- **触发门槛**:作者 <2 部已蒸 → 不生成,连网搜不启。
- **可视化**:坐标**生成时预算写死** → 静态 `<svg>` + <2KB vanilla JS(hover / 点击展开 / `location.hash` 深链)。零库零 CDN;不实现 force-directed / Sankey solver / Reingold-Tilford。

## 1. 三输入分层(服务「绝不重蒸 + 安全增量重建」)

```
读书蒸馏/authors/{author_slug}/
  author.manual.json    # ✍️人工:bio / 时期名与主题 / 每书 role / 转向 note / derive 边 / 内核句 / 演变总结 / 入门路径。重建永不动。
  author.enrich.json    # 网搜外证:thought_evolution(转向证伪层,§6)。enrich 步产。
  author.json           # 🤖 build_author.py 合并三源的产物(下游只读它)。可重建。
  author.html           # 演变页(Step 渲染产物)
  (books 的 distill.json 仍在各自 读书蒸馏/{slug}/,按 author 字段分组;fixture 用 authors/__fixture__/books/)
```

**重建语义**:新蒸一本 → 重跑 build_author.py,🤖 字段全刷新、manual/enrich 零丢失。**防覆盖栏**:已有 author.json 且 `author.manual.json` 缺失 → 拒跑(需 `--force`)。

## 2. author.json schema(🤖自动聚合 / ✍️人工 / 🔶自动播种+人工确认)

```jsonc
{
  "author": "…",            // 🤖 各 distill.json.author 分组键(需归一化同名异写)
  "slug": "…",              // ✍️ (manual)
  "aliases": [],            // ✍️
  "bio": { "birth_year": 0, "one_liner": "…",
           "portrait": "data:image/jpeg;base64,…",   // ✍️ 可选,缺则名片卡退化纯文字(布局不变)
           "background": [ { "label": "治学之路", "text": "…" }, { "label": "世界影响", "text": "…" }, { "label": "生活与底色", "text": "…" } ],
           "facts": [ { "label": "职业", "value": "…" }, { "label": "毕业院校", "value": "…" }, { "label": "研究领域", "value": "…" } ] },
           // ✍️ 任何 distill 都没有,纯人工。one_liner 渲成小传 lead(.c-lead)。
           // portrait:88x88 展示,base64 内联(单文件页零外链铁律);优先复用该作者某本书蒸馏页 SUB01 作者子视图里已有的 au-photo(同一张脸,免重新找图);
           //   与作者名横排渲成 .c-id 人物档案卡范式(.c-portrait + .c-idtext),渲染逻辑见 author-page-skeleton.html renderCard()。
           // background v5.2 起为 [{label,text}] 数组:每段带主题标签(治学之路/世界影响/生活与底色…)渲成结构化小传(label→.c-seg-k 绿色小标题,text→.c-seg-t),把「文字墙」拆成可扫读段落;
           //   旧式含 \n 的字符串仍兼容(退化成无标签 <p class=c-bg>,老 author.json 不改也能渲染)。知名作者务必详实(案例/师承/成长),数字以官网核实。
           // facts v5.2 起可选 [{label,value}] 数组:维基/百度信息框式身份字段(职业/毕业院校/研究领域/国籍等),渲染在右栏「生卒」下方、代表作之前,纯文本(多值「 · 」分隔,不成 chip),
           //   给结构化左栏配平右栏、补齐信息框标准条目。缺则右栏退化回「生卒/代表作/核心关切/代表概念」四字段。事实以官网核实,禁编造;别与 background 正文机械重复到冗余,选能一眼扫读的身份锚点。
  "core_sentence": "…",     // ✍️ I1:30 字思想内核概括句(我们的编辑论点,非作者原话)。v5.1 起渲染在 ③ 演变总结板块开头(绿左边线大字),不再当页顶大字 hero
  "books": [ { "slug":"…","title":"…","book_type":"…",  // 🤖 直取各 distill
              "pub_year": 0,          // 🤖 取 distill.pub_year(缺则该书不进时间线,记 _warnings)
              "period_id": "p1",      // 🔶 落入哪个时期
              "role_in_evolution": "…" } ],  // ✍️ 该书在思想线的位置(喂入口卡 + timeline tooltip)
  "periods": [ /* §4.1 */ ],          // 🔶 year_range/books/boundary_signal 🤖;name/theme ✍️(manual.period_names/period_themes)
  "motifs": [ /* §4.2 */ ],           // 🔶 聚类🤖播种;label/statement 人工润色
  "turns": [ /* §4.3 */ ],            // 🔶 候选🤖;note ✍️(manual.turns_note);verdict/external ← enrich
  "concept_graph": { /* §4.4 */ },    // 🤖 nodes/appearances/persist+drift 边;derive 边 🔶(manual.derive_edges)
  "persistent_tensions": [ {"a":"…","b":"…","note":"…","books":["slug"]} ],  // 🤖 tensions 跨书复现(≥2 书,(a,b)语义匹配)
  "recurring_critique": { "blind_spots":[{"text":"…","books":["slug"]}],     // 🤖 critique 跨书复现(语义去重)
                          "era_limits":[{"text":"…","year":0,"slug":"…"}] }, // 🤖 I5:era_limits 挂 pub_year
  "influences": { "upstream":[{"name":"…","via":"…"}], "downstream":[] },     // 🔶 upstream 播种自 cross_domain[].name(频次≥2);人工补师承/downstream
  "signature_lines": [ {"text":"…","slug":"…","year":0} ],   // 🤖 I6:各书 quotes[].featured 汇总去重,按年排
  "genre_arc": [ {"year":0,"book_type":"…","slug":"…"} ],     // 🤖 book_type 按年序列
  "reading_path": [ {"slug":"…","why":"…"} ],                 // ✍️ I7(manual.reading_path)
  "evolution_summary": "…",           // ✍️ I4:全生涯思想弧论点句 + 「连续 vs 断裂」显式回答(manual)
  "evolution_verdict": { "stance":"continuous|segmented|mixed", "headline":"…(≤30字,一句话结论,页面顶部徽章大字)" },  // ✍️(manual.evolution_verdict) 可选:缺失则③板块不渲染徽章行,只退化显示旧版纯文字摘要,不影响其他渲染
  "consistency_note": null,           // ← enrich:反证轨命中「作者自认一贯」时如实呈现(带 source)
  "_provenance": { "generated_from":["slug"], "pub_years":[0], "aggregator_version":"1", "warnings":[] }  // 🤖(时间戳由主控事后补,脚本不取 Date)
}
```

## 3. build_author.py 契约

**用法**:`python build_author.py --author "<名>" [--data-root <读书蒸馏>] --manual <author.manual.json> --enrich <author.enrich.json> --out <author.json> [--force]`
备选(fixture / 显式):`--inputs "<glob 指向若干 distill.json>"` 取代 --author 扫描。

**流程**:① 收集该作者 distill.json(--author 扫 data-root/*/distill.json 按 author 分组;或 --inputs)② 门槛:<2 部 → exit 3(不生成)③ 防覆盖栏:out 已存在且 manual 缺失且无 --force → exit 2 ④ 派生 🤖 字段(§4 规则)⑤ 并入 manual(✍️/🔶)+ enrich(turns.verdict/external、consistency_note)⑥ 写 author.json + 打印各段条数 + `_warnings`。

**🤖 确定性派生(纯 Python,集合运算)**:concept_graph 节点/persist+drift 边、persistent_tensions、recurring_critique、era_limits×pub_year、signature_lines、genre_arc、influences.upstream 播种、periods 候选边界(§4.1 Jaccard)、turns 候选骨架(相邻年 stance 冲突 §4.3)。
**🔶 认知部分(不在脚本内跑 LLM,由 manual 提供或主控填)**:motif 语义聚类的标签、turn 的 note、derive 边、period 命名、core_sentence、evolution_summary、evolution_verdict、reading_path、bio.background(定位卡结构化小传,`[{label,text}]` 数组,非纯一句话简介)。脚本对这些**只做「读 manual 填入 / 无则留候选占位 + 记 warning」**,不臆造。

## 4. 派生规则 + 4 视图数据契约

### 4.1 periods[](时间线·泳道 Lifeline)
```jsonc
{ "id":"p1","name":"早期·…","theme":"…","year_range":[2015,2016],"books":["slug"],"boundary_signal":"question换题|genre变|概念换手>0.6|年份断档","color_idx":0 }
```
- **边界候选(🤖)**:按 pub_year 排书;相邻两书算概念换手率 Jaccard `1 − |C_k∩C_{k+1}|/|C_k∪C_{k+1}|`,>0.6 或 core_question 换主题或 book_type 变或年份断档>N → 候选边界。**命名/主题人工**(manual.period_names/period_themes)。
- **呈现**:横轴=年份(`X=y=>pad+(y-min)/(max-min)*W`);period 底层 `<rect opacity=.08>`+标签;每书 `<circle>`+`<text>`;转向年叠红 ◆;`overflow-x:auto` 缩放;点书圆深链跳该书蒸馏页(`../{slug}/{slug}.html`)。

### 4.2 motifs[](母题·Story Ribbons)
```jsonc
{ "id":"m1","label":"…","statement":"…","status":"persistent|refined","span":[2015,2023],"color_idx":0,
  "appears_in":[{"slug":"…","year":2015,"prominence":0.8,"primary":true}] }
```
- **派生**:全书 core_ideas[].idea(+primary)+ mental_models[].model 跨书**语义聚类**(🔶,禁字符串匹配);簇跨 ≥2 书成 motif;单书落 singleton 不进。prominence 由该书该母题的 primary/条数估(🤖 可给 0.5/0.8 档)。
- **呈现**:每 motif 一条**填充多边形** ribbon(对每采样年算上沿 `y-w/2`、下沿 `y+w/2`,`d`=上沿正向 + 下沿逆向 + `Z`,`w`=prominence×maxW);一母题一色;消退 `w→0` 收尖;Catmull-Rom→Bézier 平滑。lane 生成写死。

### 4.3 turns[](思想转向·前后双列 + 时间线红标)
```jsonc
{ "id":"t1","year":2019,"concept":"意志力","motif_id":null,
  "from":{"book":"…","year":2015,"stance":"可回指原文立场A","distill_slug":"…"},
  "to":  {"book":"…","year":2019,"stance":"可回指原文立场B","distill_slug":"…"},
  "trigger_field":"concepts.stance|tensions|napkin.formula",   // 🤖 哪个 diff 命中
  "note":"为什么转(✍️ manual.turns_note)",
  "verdict":"confirmed|apparent|refuted|null",                 // ← enrich
  "external":[{"type":"self|scholar|media","who":"…","say":"含叙事动词原话≤80字","source":"url"}] }  // ← enrich
```
- **候选(🤖)**:相邻年两书对**同一共享概念** stance 语义对立 / 早书某 tension 被晚书正面处理 / 某 primary 母题被反 / formula 增删项。**只排可回指差异,禁脚本写「他转向了」**。
- **verdict 合闸(← enrich §6)**:confirmed(书内差异 + 外部原话指同一转变,出全文+来源)/ apparent(仅弱佐证 → 措辞降级「侧重移到」,禁断裂动词)/ refuted(作者自认一贯 → 转「看似不同实则一致」澄清条)/ **null(无外证 → 该条不渲染)**。
- **呈现**:时间线 turn.year 处红 ◆;下方前/后两列对照卡;**verdict 控样式**:confirmed 实线红+外证引文徽章 / apparent 琥珀软措辞 / refuted 灰底澄清 / null 不渲染。

### 4.4 concept_graph(概念演化·DAG)
```jsonc
{ "nodes":[{ "id":"c1","concept":"…","concept_en":"…","first_year":2015,"last_year":2023,
             "lane":0,"status":"persist|new|dropped|drift",
             "appearances":[{"slug":"…","year":2015,"one_liner":"…","stance":"…"}] }],
  "edges":[{ "from":"c1","to":"c1","type":"persist|drift|derive","label":"…","book_pair":["slug","slug"] }] }
```
- **派生(🤖 走现成跨书 5-tag 索引 `update_index.py`/`cross-book.md`,别另造)**:node=去重概念(同名合并);持续=同名现 ≥2 书;新增=首现于第 K 书;消失=晚书起无(dropped 终端);**漂移 drift 边**=同名但 one_liner/stance 跨书变(自动,label 标漂移);**派生 derive 边**=早书概念催生晚书新概念(🔶 manual.derive_edges,schema 无此编码)。lane 按主题族生成时写死。
- **呈现**:x=first_year、y=lane;边三次贝塞尔 `<path>`,按类型上色(persist 灰实 / drift 红 / derive 蓝虚 `stroke-dasharray`);dropped 描边淡+×;点节点展开 appearances 面板;hover 非相邻 `.dim{opacity:.15}`;**手机端 CSS Grid 兜底**(列=书、行=概念世系)。

## 5. author.html 板块骨架(内容形态调研·倒金字塔·成果前置)

页顶小眉题(`{作者} · 思想演变`,**不放大字 hero**) → **定位名片卡直接开场**(左栏:作者名 H1 + 别名 + one_liner 速览 + **bio.background 详实背景段(多段)**;右栏结构化字段:生卒/**代表作品清单(书名+年份,深链)**/**核心关切(全部母题 chip,hover 显 statement)**/**代表概念(top3 chip,hover 显出现次数+状态)**) → **③ 演变总结(连续 vs 断裂;core_sentence 论点在此)** → **演变总览地图 ⭐(时间线,一屏)** → 分期详解(每期五栏统一模板:阶段名·年份·一句主张·代表作·相较上期变了什么) → 关键转向(前后双列,verdict 控样式) → 母题 ribbon(不变的红线) → 概念演化图 → 影响谱系 → 代表作导航(每书一句「读它能懂什么」+ 深链) → 该信几分(recurring_critique 去神话化) → 入门路径(reading_path)。**先「变」(分期/转向)后「不变」(母题/谱系),两者互为张力**。

**① 页面不放页顶大字 hero(v5.1 起)**:早期把 `core_sentence` 当页顶大字,但它是**我们蒸馏出的"思想内核概括",不是作者原话** -- 放最顶当 hero 会读成"像引文却不是引文"(provenance 歧义)、且抽象概括做开篇落地偏弱。改为:页面用**定位名片卡直接开场**,作者名(`.c-name`)升为页面唯一 H1;`core_sentence` 下沉到 ③ 演变总结板块当**思想内核论点**(在"连续/断裂"的编辑分析语境里,它作为我们的论点 provenance 清晰、不再像伪引文)。若日后想放真金句当 hero,应取 `signature_lines` 里的**逐字原话 + 出处**(而非 core_sentence 概括),这是另一条可选设计,不默认。

**② 定位名片卡要有信息密度 + 结构化排版,不能是一坨文字墙**(知名作者尤其要详实):
- **左栏「结构化小传」(v5.2)**:`bio.one_liner` 渲成小传 **lead**(`.c-lead`,略大、ink 色,作全卡的一句话定位)+ `bio.background` **主题标签分段**。background 用 **`[{label,text}]` 数组**:每段一个主题标签(如 **治学之路 / 世界影响 / 生活与底色**),渲染器把 label 出成绿色小标题(`.c-seg-k`)、text 出成正文(`.c-seg-t`),**和右栏 `label:内容` 字段同一套节奏**,把密集正文拆成"一眼知道这段讲什么"的可扫读结构(而非从头读到尾的文字墙)。每段仍要补**具体案例、事例、成长经历**(顿悟时刻、师承、代表作出版脉络、个人生活)。**别为分段而注水**:文字已够充实时只做结构化(打标签+拆段),不新增废话。旧式含 `\n` 的字符串仍兼容(退化成无标签 `<p class="c-bg">`);缺 background 才退化只显 one_liner。**具体数字/事实以官网(如作者官网 about 页)为第一信源核实**,别凭印象编销量/年份。
- **右栏结构化字段**:**生卒** → **`bio.facts` 身份字段(v5.2,可选:职业/毕业院校/研究领域/国籍等,维基·百度信息框标准条目,纯文本)** → **代表作**(必须列出书名+年份、每条深链可点,禁"N 部已蒸馏"这种空话)→ **核心关切**(渲染全部母题,通常 2-4 个)→ **代表概念**(按 concept_graph 出现次数取 top3,而非只取最高 1 个);母题/概念 chip 都用 `title` 挂 hover 详情。**右栏 `align-content:center`**:字段在卡片高度内垂直居中,与左栏对齐更均衡。**当左栏结构化小传较高、右栏偏空留白时,用 `bio.facts` 补 1-3 条身份字段配平**(别硬凑重复项或注水,选能一眼扫读、与正文不冗余的身份锚点)。

**③ evolution_summary 板块(连续 vs 断裂)不能只是一段裸文字**:必须给读者一眼可抓的视觉锚点,固定顺序:「连续,还是断裂?」眉题 → **`core_sentence` 思想内核论点**(绿色左边线大字,我们对作者全弧的一句话概括,即从页顶下沉来的那句)→ **`evolution_verdict` 结论徽章行**(彩色 pill:continuous 绿/segmented 红/mixed 金 + headline,可选字段,缺失则跳过这行不影响其他渲染)→ **分期速览 strip**(复用 periods 数据渲染成一排彩色小 chip + `→` 连接符,给「一眼看清几个阶段」的可视锚点,zero 额外数据成本)→ 完整 evolution_summary 论证段(不删减,原文照发)→ **consistency_note 用 `.text` 取值渲染**(它是 `{text,source}` 对象,**禁止 `'前缀' + consistency_note` 字符串拼接**,会拼出 `[object Object]`;source 存在则挂「查看来源 ↗」外链,复用 turn-ext 的引文卡样式)。

## 6. author.enrich.json 契约(思想转向证伪层,enrich 步产)

```jsonc
"thought_evolution": {   // 整块 null → 转向段 + 时间线红标不渲染
  "author":"…","scope":["slug≥2"],"tagline":"≤50字,可null",
  "timeline_anchors":[{"year":"…","event":"…","source":"url"}],   // 空→时间线不叠事件锚
  "shifts":[ /* 结构同 §4.3 turns 的 external+verdict 部分,按 concept 对齐 */ ],
  "consistency_note": null,   // 反证轨命中「作者自认一贯」→ 如实呈现(带 source)
  "sources":["url"] }
```
- **四轨检索(排序即优先级,前档拿到即停)**:① 作者自述轨(最高,`"{作者}" 访谈|自序|后记 "以前认为"|"不再"|"修正"`,**须作者名锚定**)② 学界/媒体/传记轨 ③ 生平事件锚轨 ④ **一致性反证轨(强制跑,防确认偏误:`"{作者}" 一以贯之|否认转变`)**。
- **三硬约束**:① 叙事动词(转向/放弃/回归)须在某 external.say 找到同义原话+source,否则删 ② 主题差 ≠ 思想变(只在同一概念两书立场真冲突才算)③ 一致性反证强制搜。
- **降级**:<2 部→不生成;shift 四轨全空→该条 null 隐藏(不留占位);整块搜空→ `thought_evolution` null(转向段整块隐藏,但时间线/母题/概念图作书内事实照发)。工具链 AnySearch→Tavily→WebSearch,一次失败即降级、禁重试轰炸,外证须可点击 URL。

## 7. 每书页「演变入口卡」(page-skeleton)

每书蒸馏页顶部加一张卡:`这是 {作者} 的第 {K}/{N} 部蒸馏 · {role_in_evolution} → 查看思想演变全景`,链到 `../authors/{author_slug}/author.html`。**降级**:该作者 <2 部已蒸 或 无 author.json → 整卡不渲染(单书页不受影响)。

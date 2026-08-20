# 联网增补手册 v2.1 -- Step3 enrich.json:五个基础块 + 心理学科学证据层(sansheng-distill)

> **执行手册,不是理论文**。管线跑到 Step3 时 agent 逐节照做,产出 `enrich.json`(五个基础顶层键,任一基础键可降级为 `null`;心理学书条件增加第六键 `evidence_page`)。
> 核心立场:蒸馏主体(distill.json)已完成且**不依赖网络**;本层是锦上添花的外部信息,拿不到就隐藏,**绝不编造**。
> **v2 变化**:三块内容做成「延展二级页」(satellite_form=B,页内全屏子视图,仍单文件填充)-- `author_page`(作者页)/ `similar_page`(同类书页)/ `views_page`(观点对比页);外加两个内联模块 `reviews`(书评)/ `cross_book_external`(跨书外部立场)沿用。主页只放短卡/入口卡,点开子视图看全文。
> 全文破折号一律 `--`;规则全部给可判定标准(数字/枚举/命令),不用「酌情」「适当」。

---

## 0. 路径与变量约定(全文只定义一次)

| 占位符 | 展开为 |
|---|---|
| `$SKILL` | 本 skill 目录(安装后为 `~/.claude/skills/sansheng-distill`) |
| `$DATA` | 书数据根目录,由环境变量 `DISTILL_DATA_DIR` 指定(默认 `./distill-data`) |
| `{书目录}` | 本书数据目录,**纯 `{slug}`**(如 `jinqian-xinlixue`);不含书名,避免中文目录名 |
| 本书产物 | `$DATA\{书目录}\enrich.json` |
| 跨书索引 | `$DATA\knowledge-index.json` |

下文命令里的 `$SKILL` / `$DATA` / `{书目录}` 直接替换成上表实值再执行。

---

## 1. 五个基础键 + 心理学条件键与 enrich.json schema(整块契约)

普通书/视频的 `enrich.json` 恰好五个基础顶层键。**任一基础键取值 `null` 表示该块整块降级隐藏**(页面对应子视图/内联模块不渲染)。当 `distill.domain_profile.domain=="psychology"` 时必须再写第六键 `evidence_page`,该键不可降级为 `null`;字段命名逐字以本表为准(下游 page-skeleton / verify 消费,不得改名)。

```jsonc
{
  "author_page": {
    "name": "樊登",                                    // 必填
    "tagline": "从央视主持人到 6500 万书友的\"讲书人\" -- 这本书是他把十几本亲子书熔成三根支柱的收束之作。", // ≤50字,页顶导语
    "photo": null,                                     // base64 data URI(优先真人清晰正面照,裁方≤50KB;见 §1「作者照片获取标准」)或 null→字符头像
    "media_type": "book",                              // book|video|paper… 驱动 S5 标题措辞(见 §V.2)
    "infobox": {
      "birth":       { "date": "1976年3月24日", "place": "陕西西安" },
      "death":       null,
      "ancestry":    "山西运城",
      "nationality": null,                             // 不写→不显示
      "education":   ["西安交通大学 材料系 工学学士", "西安交通大学 管理学院 管理学硕士", "北京师范大学 电影学(传播学) 博士"],
      "roles":       ["讲书人", "帆书(原樊登读书)创始人", "前中央电视台主持人"],
      "known_for":   "樊登读书会/帆书 -- 每周精讲一本书的知识付费平台",
      "notable_works": ["陪孩子终身成长", "读懂孩子的心", "可复制的领导力"],
      "extra":       [ { "label": "活跃年代", "value": "1999 年至今" } ]
    },
    "career": [                                        // S1 时间线,3-5 段,每段 2-4 句
      { "period": "1976-1999", "label": "西安少年到辩论冠军", "text": "西安交大读完材料系本科与管理学硕士,又拿下北师大传播学博士;1999 年作为主力拿下国际大专辩论赛冠军,一副好口才从此成了吃饭的家伙。", "source": "https://baike.baidu.com/item/..." },
      { "period": "1999-2013", "label": "央视主持人与大学教师", "text": "进入中央电视台,主持《实话实说》《12演播室》《三星智力快车》等节目,也在北京交通大学教过书。", "source": "https://zh.wikipedia.org/wiki/..." },
      { "period": "2013-2018", "label": "\"樊登读书会\"起步", "text": "针对\"没时间读书、不知道读什么、读了记不住\",在西安发起樊登读书会,每周精讲一本书、每人每年 365 元起步。", "source": "https://www.dushu365.com/intro/read" },
      { "period": "2018-至今", "label": "更名帆书,\"去樊登化\"", "text": "2018 年更名\"樊登读书\",2023 年改叫\"帆书\";十年滚成覆盖 6500 万书友的知识付费平台。", "source": "https://wallstreetcn.com/articles/3630220" }
    ],
    "impact": {                                        // S2;null→整栏删
      "stats": [ { "num": "6500万", "label": "书友" }, { "num": "8000万", "label": "号称覆盖读者" }, { "num": "365元/年", "label": "会员模式" } ],
      "text": "这门\"讲书\"生意十年滚成知识付费帝国,也把\"每周一本书\"变成一代中产家庭的日常仪式。"
    },
    "debate": {                                        // S3;null→整栏删
      "pro": [ { "who": "围墙内·书友", "say": "把他捧成\"知识偶像\",讲书让不读书的人重新亲近了书。", "source": "https://..." } ],
      "con": [ { "who": "围墙外·批评者", "say": "\"前有咪蒙、今有樊登\";50 分钟讲完一本书不过是知识快餐、碎片化的二手知识。", "source": "https://..." } ]
    },
    "this_book": {                                     // S4;null→整栏删
      "text": "本书本质是一位\"职业读书人\"的二次创作 -- 樊登自陈讲过十几二十本亲子书后,发现所有育儿难题的分野只有一个:你把孩子当机械体还是当生命体。他把阿德勒、德韦克、高普尼克\"园丁与木匠\"式的复杂系统观熔成三根支柱;作为女儿\"嘟嘟\"的父亲,他把冰激凌与芹菜、辅导作业的怒火这类亲历细节写进书里。",
      "lineage": "2019《读懂孩子的心》解具体难题 → 2020 本书挖底层逻辑"
    },
    "works": [                                         // S5 年表;year 升序;渲染层排序
      { "title": "可复制的领导力", "year": "2017", "one_liner": "…", "is_this_book": false, "distill_slug": null },
      { "title": "读懂孩子的心",   "year": "2019", "one_liner": "…", "is_this_book": false, "distill_slug": null }, // 已蒸馏时填 slug→站内互链
      { "title": "陪孩子终身成长", "year": "2020", "one_liner": "…", "is_this_book": true,  "distill_slug": null },
      { "title": "樊登讲论语",     "year": "",     "one_liner": "…", "is_this_book": false, "distill_slug": null }  // 无年份→年表尾"年份不详"组
    ],
    "bio_long": "…(legacy,可选)…",                    // 向后兼容:仅当结构化字段缺失时按 v2 多段散文渲染
    "sources": [ "https://baike.baidu.com/item/...", "…" ]
  },
  "similar_page": {
    "items": [{ "title": "…", "author": "…", "relation": "印证|补充|反驳", "why": "为什么推荐 2-4 句", "fit": "适合谁读", "order": "先读/后读建议" }],
    "reading_path": "一段阅读路线(把本书 + 这几本串成从入门到进阶/从印证到反驳的顺序)",
    "sources": ["…"]
  },
  "views_page": {
    "topics": [{
      "viewpoint": "书中观点一句(取自 distill.json 的真实主张)",
      "supporters": [{ "who": "人名/媒体/机构", "say": "其表态原话或摘要,照录不改立场", "source": "url" }],
      "critics":    [{ "who": "…", "say": "…", "source": "url" }]
    }],
    "sources": ["…"]
  },
  "reviews": { "rating": "8.9 / 豆瓣", "items": [{ "text": "书评摘要 ≤80 字", "stance": "正|反", "source": "url" }] },
  "cross_book_external": [{ "concept": "…", "book": "…", "stance": "…", "source": "url" }],
  "evidence_page": {
    "as_of": "2026-08-20",
    "claims": {
      "loss-aversion-generalizes": {
        "status": "mixed",
        "best_evidence": "当前最佳证据的简明裁决,不复述原书。",
        "confidence": "moderate",
        "replication": { "status": "mixed", "note": "复制结果与主要异质性。" },
        "scope": {
          "population": "研究覆盖的人群",
          "context": "研究成立的任务/场景",
          "limits": ["不能外推到的边界"],
          "risks": ["照做或误用的风险"]
        },
        "sources": [{ "title": "论文或官方项目题名", "url": "https://…", "type": "meta_analysis", "year": 2024 }]
      }
    }
  }
}
```

| 键 | 页面呈现 | 定义 | 降级写法 |
|---|---|---|---|
| `author_page` | **子视图 `#sub-author`**(全屏,infobox 归一栏 + 五栏)+ **主页短作者卡** | 结构化人物档案:infobox 基础信息 + 人物经历/成就影响/争议评价/他与这本书/主要作品五栏;主页 hero 只放短卡,点开看全档 | 整块置 `null`(短卡 + 入口卡一并隐藏) |
| `similar_page` | **子视图 `#sub-similar`**(全屏) | 同类书推荐(带关系/适合谁/先后读)+ 一条阅读路线 | 整块置 `null` 或 `items: []` |
| `views_page` | **子视图 `#sub-views`**(全屏) | 书中核心观点的国内外赞同方/质疑方对照,每条带来源 | 整块置 `null`;某 topic 缺一方 → 该方 `[]` |
| `reviews` | **内联 ⑤**(该信几分·书评) | 评分 + 代表性书评(正反都收),每条带来源 | 整块置 `null`;有评分无书评 → `items: []` 保留 `rating` |
| `cross_book_external` | **内联 ⑤**(跨书表·外部书立场) | 同一概念在**未蒸过的**其他书里的立场 | 整块置 `null` 或 `[]`(见 §6) |
| `evidence_page` | **内联 ③**(心理学科学证据卡) | 按 claim_id 显示「原书怎么说 / 外部研究怎么说 / 适用边界与风险」 | 非心理学书省略;心理学书必填且不可为 `null`(G24) |

**主页短作者卡 = `author_page.tagline`**(≤50 字页顶导语,渲染层直接取用,比截断 bio_long 更短更钉人),点开 `#sub-author` 看完整结构化档案。因此 enrich.json **不再有独立 `author_card` 字段**--短卡是 `author_page` 的派生视图,单一来源,避免两处数据漂移。旧版 `similar_books` 已由 `similar_page` 取代(升级为带 author/why/fit/order/reading_path 的子视图),不再单列。

### 1.1 evidence_page 心理学科学证据层(v2.1,G24)

这一层回答「这条心理学主张在书外站不站得住」,与 `evidence_level`(原书转述忠实度)和 `certainty`(内容来源)正交。执行顺序固定:

1. 从 `distill.core_ideas[] + decision_rules[]` 收集全部唯一 `claim_id`;`evidence_page.claims` 的键集合必须**无多无少完全相等**。框架、方法论、规范建议也不能跳过。
2. 每项 `status` ∈ `supported|mixed|contested|not_supported|not_testable`;`confidence` ∈ `high|moderate|low|very_low|not_applicable`;`replication.status` ∈ `replicated|mixed|failed|not_attempted|not_applicable`。
3. `best_evidence` 写外部证据裁决,不是作者观点复述;`scope` 必含 `population/context/limits[]/risks[]`。`clinical_relevance` 为 `direct|indirect` 时 `risks[]` 至少 1 条。
4. 非 `not_testable` 主张至少 1 个可点击来源;`not_testable` 可 `sources:[]`,但必须 `confidence:not_applicable` + `replication.status:not_applicable`,并在 `best_evidence` 明说为何不可检验/不可证伪。`descriptive|associational|causal|predictive|intervention` 属实证型,**不得**标 `not_testable`;只有 `framework|methodological|normative` 可在理由充分时使用。
5. 来源优先级:元分析/系统综述 → 注册报告/大样本复制 → 原始研究 → 官方勘误或共识声明。`sources[].type` **必须**取 `meta_analysis|systematic_review|registered_report|replication|primary_study|official_correction|consensus_statement`;每项必带非空 `title`、可解析且有 host 的 `http(s) url`、合法 `type`、合理四位 `year`。普通 verifier 不联网探测可达性,避免构建依赖网络。

**检索纪律**:这是英文技术/学术任务,按全局路由只用 Tavily;技术问题只采一手材料(论文原页/DOI、期刊、OSF/Center for Open Science、学术组织或官方勘误),作者官网、出版社、媒体书评不能充当科学有效性证据。先找综述/元分析定全局,再为争议点补复制与原始研究;不同研究冲突时标 `mixed|contested`,不得以票数或作者名气替代证据权重。`as_of` 写核查截止日(ISO 日期)。

**author_page 逐字段降级规则(逐行/逐栏删,绝不渲染「未知/暂无」占位)**:

- 任一可选字段 `null`/空 → 对应 infobox 行或正文栏整删,高度自适应;绝不留空值占位。`infobox` 各行(birth/death/ancestry/nationality/education/roles/known_for/notable_works/extra)缺哪行删哪行;`nationality` 中文作者可默认省略,写入才显示;`death` 在世时 `null`(不显示「至今」废话行)。
- **infobox 最低成立线**:姓名之外的事实行 **< 3 行**时,infobox 不值得独占一栏 → 整体降级为正文顶部一条「作者速览横条」(`name` + `roles` + `known_for` 拼一行),正文转单栏全宽。
- `impact` / `debate` / `this_book` 任一 `null` → 对应正文栏整栏删(含标题),页面少一栏依然成立;`debate` 对争议极小的作者是常缺项,删了页面照样成立(不硬造反方,见 §5 铁律三)。
- `career` 全量分段 3-5 段;`works` 必须**恰有一条** `is_this_book:true`,缺 `year` 的条目进年表尾「年份不详」组、不硬编年份,本书年表行永不外链,已蒸馏的书填 `distill_slug` 走站内互链。
- **`photo` 作者照片获取标准(所有作者统一,优先真人照)**:公开出书 / 有公众身份的作者,**优先联网找一张清晰正面照**(信源序:维基/百度百科头图 → 出版社作者页 / 官网 → 公开活动·媒体专访图;`media_type:"video"` 用频道头像)→ 下载 → PIL 裁成正方形(取人脸居中区)→ 压缩到 **≤50KB**(webp/jpg,长边 ≤240px 够 120px 显示的 2x)→ 转 **base64 `data:` URI** 存 `author_page.photo`,渲进 `.au-photo` 的 `<img>`。**查不到可靠清晰图源才置 `null`**(别硬塞模糊 / 侵权 / 张冠李戴的图)。
- `photo` 为 `null` → infobox 头像**降级为字符头像**(`.au-monogram` 圆角色块 + 姓氏首字,取 `--gold`),不留空图框。
- `author_page === null` → 子页 `#sub-author` + 全部入口(hero 作者名链 + 延伸入口卡)一并删(沿用 v2)。

**`bio_long` 仅作 legacy 兜底**:v3 结构化字段(`infobox`/`career`/`impact`/`debate`/`this_book`/`works`)齐全时**不渲染** `bio_long`;仅当这些结构化字段整体缺失(旧书未重蒸)时,才按 v2 多段散文把 `bio_long` 渲染进作者页正文;单独 `career` 空但 `bio_long` 存在时,S1(人物经历)按 v2 散文段落渲染(迁移兜底)。**新蒸的书不再产 `bio_long`,旧书数据靠它兜底、不必重跑。**

> 已蒸过的书之间的跨书观点(互链)**不在本文件**,由 Step4 `cross-book.md` 直接从 `knowledge-index.json` 渲染跨书互链;`cross_book_external` 只收「索引里没有、只能联网找到」的外部书立场。二者在 ⑤ 跨书模块并列呈现,分工见 §6。

---

## 2. 各块产出量与内容规格(可判定)

| 块 / 字段 | 数量硬规 | 内容规格 |
|---|---|---|
| `author_page.name` / `tagline` | name 必填;tagline **≤50 字** | tagline = 页顶一句导语,把人钉住(「他是谁 + 凭什么写这本书」);同时作主页短作者卡文案 |
| `author_page.infobox` | 事实行(姓名外)**≥3 行**才成栏,<3 行降级为速览横条 | 逐行事实:`birth`/`death`/`ancestry`/`nationality`/`education[]`/`roles[]`(≤3)/`known_for`/`notable_works[]`(≤4)/`extra[]`;每行拿不到即删,绝不填「未知」 |
| `author_page.career` | **3-5 段**,每段 2-4 句 | S1 时间线;每段 `{period, label, text, source}`;text 讲这一阶段他做了什么/怎么走过来,每段尽量带 source |
| `author_page.impact` | 0 或 1 块(可 `null`) | S2;`stats[]` 2-4 个大数字 `{num, label}` + `text` 一段短散文;拿不到量化数字则整块 `null`→整栏删 |
| `author_page.debate` | 0 或 1 块(可 `null`) | S3;`pro[]`/`con[]` 各 `{who, say, source}`,据实(§5 铁律三);争议极小的作者常缺→整块 `null`、整栏删,不硬造反方 |
| `author_page.this_book` | 0 或 1 块(可 `null`) | S4;`text` 1-2 段讲这本书在他谱系里的位置、他凭什么写;`lineage` 一条写作谱系箭头行 |
| `author_page.works` | **全量带 year**;**恰一条** `is_this_book:true` | S5 年表;每条 `{title, year, one_liner, is_this_book, distill_slug}`;year 拿不到留空进「年份不详」组、不硬编;已蒸馏填 `distill_slug`→站内互链;`one_liner` 一句话不臆造;本书行永不外链 |
| `author_page.sources` | **≥1 个 URL** | 见 §5 铁律一;career/debate 每条尽量自带 source,`sources` 兜底汇总 |
| `similar_page.items` | **3-6 本** | 每本 `{title, author, relation, why, fit, order}`;`relation` 三选一:`印证`(同立场加固)/`补充`(不同角度扩展)/`反驳`(对立观点);`why` 2-4 句说清「与本书什么关系 + 为什么值得读」;`fit` = 适合谁读(读者画像);`order` = 先读/后读建议(据难度/前置知识) |
| `similar_page.reading_path` | **一段** | 把本书 + 这几本串成一条阅读路线(从入门到进阶、或从印证到反驳),不是逐本复述 |
| `similar_page.sources` | **≥1** | 命中本地索引的可无外部 URL,但至少标注来源(索引本身或书评页) |
| `views_page.topics` | **2-5 个** | 每个 `viewpoint` 必须取自 `distill.json` 的真实主张(`core_ideas`(优先 `primary`)/`tensions`/`critique` 涉及的观点),**禁自行发明「书中观点」** |
| `views_page.topics[].supporters` / `.critics` | 每 topic **目标各 1-3 条,据实** | 每条 `{who, say, source}`;`who` 尽量具名(学者/媒体/机构),拿不到具名可用平台标注(如「豆瓣用户 @X」「Goodreads 读者」);`say` = 表态原话或摘要(≤80 字,照录不改立场);`source` = 可点击 URL |
| `views_page.sources` | 汇总所有 topic 用到的源 | 见 §5 铁律一 |
| `reviews.items` | **3-5 条** | 正反都要(见 §5 铁律三);每条 `{text, stance:"正"\|"反", source:url}`;text 为原书评摘要(≤80 字),不改写立场 |
| `cross_book_external` | 无下限(有几个算几个) | 每条 `{concept, book, stance, source:url}`;`concept` 用本书 `distill.json.concepts[]` 的概念名;仅收 §6 判定为「索引没有」的概念 |
| `evidence_page.claims` | 心理学书 **100% 覆盖 claim_id** | 键集合与 distill 的 core_ideas + decision_rules claim_id 完全一致;非 not_testable 每项 sources≥1;结构与枚举见 §1.1 |

- `reviews.rating` 格式:`{分值} / {来源}`,如 `8.9 / 豆瓣`、`4.2 / Goodreads`;多源只填最先命中的一个,不加权平均(避免制造假精度)。
- 所有 `sources` / 每条 `source`:必须是**可点击的 http(s) URL**(见 §5 铁律一)。

---

## 3. 信源优先级表 + 基础块与条件证据搜索 pass 设计

**v2 预算加大**:三个二级页各起一轮**专门**搜索(不再是 v1 单模块一击即止);长搜可按块派 subagent 并行(全 Opus,禁 cheap model)。每块按下方降级链从左到右尝试,**前一档拿到可用信息即停**;某档抓取失败(含反爬,见 §4)即降级下一档;全部档位都拿不到 → 该块整块置 `null`。

| 块 | 信源优先级(降级链) |
|---|---|
| 作者页(author_page) | 维基百科(中/英)/官网/个人主页 → 出版社作者页 / 豆瓣作者页 / Goodreads author → 深度访谈·媒体专访·演讲 → 搜索引擎摘要 |
| 同类书页(similar_page) | 本地 `knowledge-index.json` 优先 → 豆瓣「喜欢这本书的人也喜欢」/ Goodreads "Readers also enjoyed" → 书单文章·书评人推荐·领域经典书目 → 搜索摘要 |
| 观点对比页(views_page) | **国内轨 + 国外轨两轨分搜**(见 §3.3,不是单链降级) |
| 书评(reviews) | 豆瓣(反爬时降级)→ 微信读书 → Goodreads → 搜索引擎摘要 |
| 跨书外部(cross_book_external) | 先查本地索引(Step4 query)→ 已蒸书走互链不进本文件;索引缺的再联网找(见 §6) |
| 心理学科学证据(evidence_page) | 元分析/系统综述 → 注册报告/大样本复制 → 原始研究 → 官方勘误/共识;只收一手学术或官方页面 |

### 3.1 author_page 搜索 pass(v3 结构化,按字段分头检索)

> **批量同作者:作者研究只做一次(2026-07-12 复盘 A-3)。** 一次拆同一作者多本书时,`author_page` 的联网搜索**一位作者只跑一次**,产物写 `$DATA\authors\{author_slug}\author.enrich.json`(与 StepA 作者演变页共用同一份);各书 `enrich.json` 的 `author_page` **引用/拷贝这份共享结果**(仅 `this_book`/`works.is_this_book` 按本书微调),**禁每本各搜一遍**(复盘中 6 本凯文各搜一遍「凯文·凯利」= ~19 轮冗余联网)。仅当该作者只蒸 1 本时才就地随本书搜。
>
> 每一步的目标都是**填结构化字段**,不再合成一坨散文。全程延续 §5 铁律:**查不到就删,绝不编造**--任一事实项拿不到即让渲染层整行/整栏删,不写「未知/暂无」占位、不凭记忆补。

1. **infobox 事实项**:维基百科(中/英)/官网/出版社作者页 → 生年生地(`birth`)、逝世(`death`,在世则 `null`)、籍贯(`ancestry`)、国籍(`nationality`)、学历(`education[]`)、身份定位(`roles[]`,≤3)、以何知名(`known_for`)、代表作(`notable_works[]`,≤4)。逐项据实填,查不到的项直接不填。
2. **career 分期**:维基/百科/媒体专访/演讲实录 → 把生平切成 **3-5 个阶段**,每段 `{period, label, text, source}`,text 2-4 句讲这一阶段他做了什么、怎么走到下一步;每段尽量挂来源 URL。
3. **impact 成就与影响**:出版社/平台官方数据/权威媒体报道 → 2-4 个可量化大数字(销量/订阅/覆盖人数/获奖)进 `stats[]`,配一段短散文 `text`;拿不到量化数字则 `impact` 整块 `null`。
4. **debate 正反声音**:书评人/媒体评论/学界商榷/读者社区 → 正面(`pro[]`)与质疑(`con[]`)两侧各找 **1-3 条** `{who, say, source}`,照录不改立场;真一边倒就如实只给到的一边(§5 铁律三),争议极小的作者整块 `null`,不硬造反方。
5. **this_book 他与这本书**:作者访谈/自序/创作谈 → 1-2 段讲这本书在他谱系里的位置、他凭什么写(`text`),外加一条写作谱系箭头行(`lineage`)。
6. **works 作品年表**:出版社作者页 / 豆瓣作者页 / Goodreads author → 尽量全,每条 `{title, year, one_liner, is_this_book, distill_slug}`;`year` 拿不到留空(进「年份不详」组,不硬编);本书条目 `is_this_book:true`(**恰一条**);已蒸馏的书填 `distill_slug` 走站内互链;`one_liner` 据书评摘要一句话说清,不臆造。
7. **tagline**:综合以上凝练 **≤50 字**一句页顶导语(「他是谁 + 凭什么写这本书」),同时作主页短作者卡文案。

### 3.2 similar_page 搜索 pass

1. **本地索引优先**:先查 `knowledge-index.json`,已蒸的同类书直接入 `items`,`relation` 据实。
2. **联网候选**:豆瓣「喜欢这本书的人也喜欢」/ Goodreads "Readers also enjoyed" → 候选同类书。
3. **补充与理由**:书单文章 / 书评人推荐 / 该领域公认经典 → 补候选 + 提炼 `why`(2-4 句,讲与本书的关系而非复述该书内容)。
4. **给每本定标签**:`relation`(印证/补充/反驳)、`fit`(适合谁读)、`order`(先读/后读,据难度/前置知识)。
5. **织 `reading_path`**:把本书 + 这几本串成一条阅读路线(入门→进阶,或印证→反驳)。

### 3.3 views_page 搜索 pass(**重点,双轨分搜**)

**先定 topics**:从 `distill.json` 里挑 **2-5 个最核心/最具争议**的观点(优先 `core_ideas` 里 `primary:true` 的、`tensions` 涉及的、`critique` 针对的主张),逐条写成 `topics[].viewpoint`(书中观点一句)。**viewpoint 必须是书里真有的主张,不许自造。**

**对每个 viewpoint,两轨都搜**,分别找赞同方(`supporters`)与质疑方(`critics`):

- **国内轨**(AnySearch 中文广搜为主):
  - 豆瓣长评 / 短评(搜「书名 + 观点关键词」)
  - 知乎问答(搜「书名/观点关键词 + 评价/质疑/怎么看」)
  - 微信公众号书评 / 评论文章
  - (可选)知网 / 学术中文,取有署名的学者观点
- **国外轨**(Tavily 英文深搜 / 定向域为主):
  - Goodreads reviews(高赞正反评)
  - 主流媒体书评(NYT / The Guardian / The Atlantic / The Economist / Financial Times / New Yorker 等)
  - 学术(Google Scholar / JSTOR / 书评期刊)
  - 行业博客 / 专家专栏

**每条 supporter/critic** = `{who, say, source}`:`who` 尽量具名(学者/媒体/高赞用户),拿不到具名用平台标注;`say` 照录该方表态(≤80 字,不改立场,不润色);`source` 为可点击 URL。

**组织成「书中观点 → 赞同方 / 质疑方」**:每个 topic 力求国内外都有、赞同质疑都有;但**据实**(§5 铁律三)-- 真一边倒就如实一边倒,不硬造反方来凑平衡。

### 3.3a evidence_page 搜索 pass(仅 psychology)

1. 按 claim_id 逐条把原书主张压成英文检索式,先找最近且范围匹配的 meta-analysis/systematic review。
2. 对 `mixed|contested` 候选补 registered report、multi-lab/large-sample replication 与官方 correction;记录研究对象、任务与情境,不只记结论方向。
3. 同一文献可支撑多个 claim,但每个 claim 都须独立写 `best_evidence/scope`;不得把一条宽泛综述复制粘贴到所有主张。
4. 将「没有复制研究」与「复制失败」分开:`not_attempted` 不等于 `failed`;把「效应量很小/高度异质」与「完全不存在」分开,不把统计不显著自动写成 `not_supported`。
5. 最后做 ID 集合对账;缺一条即 G24 失败,不能用 `views_page` 的书评/观点材料顶替科学证据页。

### 3.4 搜索工具链降级(全局规范,取「搜索引擎摘要」这一档时用)

**按任务类型选一个引擎,不是固定顺序链**(同题并行撒网只烧上下文):

| 本 skill 的典型场景 | 引擎 |
|---|---|
| 作者生平/访谈/中文书评/人物公司 | `AnySearch`(`mcp__anysearch__search` / `batch_search`),**条数压 3–5** |
| 要可引用的**原文段落**(书评正反、观点原话) | `doubao_search`(`mcp__doubao_search__web_search`),直接返正文,`Count` 压 3–5 |
| 英文深搜 / 定向域 / 时间窗 / 技术类 | `Tavily`(`tavily_search` / `tavily_research`) |

内置 `WebSearch` 是**末位回退**,不是链条一环:用前须先按上表选定引擎并实际尝试,回退时说明试了哪个、失败在哪一层。取具体页面正文用 `WebFetch`;某一引擎报限流/质量差即换下一个,不在同一引擎上反复重试。完整路由与硬约束见 `AGENTS.global.md`「工具使用」节。

---

## 4. 豆瓣反爬应对(硬约束,对所有块生效)

豆瓣评分/书评是 reviews 首选源,也常出现在 views_page 国内轨。规则:

1. 直接抓取豆瓣页面(WebFetch / 搜索工具的 extract)返回 **403 / 429 / 验证码页 / 登录墙 / 空正文** → **立即判定该档失败,降级下一档**(reviews:微信读书 → Goodreads → 搜索摘要;views_page 国内轨:知乎 / 公众号 / 搜索摘要)。
2. **禁止**为绕过豆瓣反爬做任何重试轰炸:不换 UA 硬刷、不加 sleep 循环重抓、不多次换代理试探。一次失败即降级,零重试。
3. 若只在搜索引擎摘要里看到「豆瓣 X.X 分」但抓不到豆瓣正文书评 → `reviews.rating` 可填 `X.X / 豆瓣` 并把该摘要 URL 作为 source,但书评/观点正文必须来自能真正抓到正文的下一档,**不得把搜索摘要里的只言片语伪造成一条完整豆瓣书评/观点**。

> 同一「一次失败即降级、禁重试轰炸」原则适用于所有信源(微信读书 / Goodreads / 知乎 / Scholar 同样可能拦),不止豆瓣。

---

## 5. 三条铁律(硬约束,违反即本层作废重来)

**铁律一 · 每条外部信息必带来源 URL。**
`author_page.sources`(≥1 条)、`similar_page.sources`(≥1 条,承载全部同类书条目来源 -- `similar_page.items` **无** per-item source)、每条 `views_page.topics[].supporters/critics[].source`、每条 `reviews.items[].source`、`cross_book_external[].source`、每条可检验 `evidence_page.claims.*.sources[]` 都必须是可点击的 http(s) URL。拿不到 URL 的信息 = 拿不到该信息,按铁律二处理,**绝不凭记忆/训练知识填充无源内容**。

**铁律二 · 拿不到就降级留空/置 null,页面隐藏,不编造。**
某个**基础块**所有信源档位都失败 → 该顶层键置 `null`,页面对应子视图/内联模块不渲染。单字段拿不到 → 该字段留空(`year:""`、某 topic 的 `critics:[]`),不臆造填充。宁可缺内容,不可编造作者生平、假著作、假书评、假赞同/质疑方。「据实降级」永远优于「编个像样的」。心理学 `evidence_page` 不允许整块降级:证据不足就如实写 `low|very_low`、`not_attempted` 或 `not_testable`,仍须覆盖全部 claim_id。

**铁律三 · 评价/观点类必须尽量正反都收;一边倒要如实呈现,不硬造反方。**
- `reviews.items` 尽量同时含 `stance:"正"` 与 `stance:"反"`(至少各一条)。若某书在所有档位都**只搜到清一色好评**、找不到任何批评:这是信源可疑信号(营销页/水军/样本偏);处置 = 正面书评照收,但在 `reviews.rating` 后追加标注 ` (未见负面书评,信源存疑)`,`items` 里**不得为凑「反」而伪造差评**。
- `views_page` 每个 `topic` 力求 `supporters` 与 `critics` 都有;但若某观点确实只找到一边(如学界普遍赞同、无公开质疑),就**如实**只给到的那一边,另一边留 `[]`,不硬造。真实的「一边倒」本身就是对读者有用的信号。
- `similar_page.items` 的 `relation` 不许全是 `印证`;若真只找到印证类,如实呈现,不硬造反驳。

---

## 6. cross_book_external 与 cross-book.md 的衔接(避免与互链重复)

`cross_book_external` 只收「索引里没有、只能联网找到」的外部书立场;已蒸书之间的跨书观点由 Step4 生成互链。二者共用同一次 `query`,分工如下:

1. **共享读取(Step4 的 ① 步,只读)**:
   ```
   python $SKILL\scripts\update_index.py query --index $DATA\knowledge-index.json --names-only
   ```
   拿到当前跨书索引的概念名单。命令语义、退出码详见 `cross-book.md` §2。

2. **切分本书 concepts[]**:把 `distill.json.concepts[]` 逐个与名单**语义匹配**(同义合并规则见 `cross-book.md` §4):
   - **命中索引**(索引里已有同义概念,来自其他已蒸书)→ 交给 Step4 走跨书**互链**(`cross-book.md` §5),**不进** `cross_book_external`。
   - **未命中索引**(索引里没有)→ 交给本层,联网找该概念在其他外部书里的立场,写入 `cross_book_external[]`,每条带 `source` URL。

3. 因此 `cross_book_external[i].concept` 一定是「query 名单里查不到」的概念;若某概念既在索引又想补外部书,以互链为准,不重复塞进 `cross_book_external`。

4. 联网找不到任何外部书立场 → `cross_book_external` 置 `null` 或 `[]`;跨书观点部分仅由 Step4 互链填充(可能也为空,则整个跨书子块隐藏)。

> 执行顺序提示:Step3 填 `cross_book_external` 需要先跑一次 §6.1 的 `query`(只读,无副作用);真正写索引的 `register` 在 Step4 进行。二者共用同一份 query 结果即可,不必查两遍。

---

## 7. 收尾自查 checklist(写完 enrich.json 逐条核对)

- [ ] 五个基础顶层键都在;拿不到的据实置 `null`,没有为凑数编造的块。心理学书另有非 null 的第六键 `evidence_page`。
- [ ] `author_page` 为结构化:`name`/`tagline`(≤50字)必填;`infobox` 事实行据实(缺项已删非填「未知」)或事实行 <3 已降级速览横条;`career` 3-5 段;`impact`/`debate`/`this_book` 有则规范、无则整栏 `null`;`works` 全量带 year(缺 year 进「年份不详」组)且**恰一条** `is_this_book:true`;`sources` ≥1 个 URL。
- [ ] 主页短作者卡取 `author_page.tagline`(非截断 `bio_long`),未在 enrich.json 里另存 `author_card`(无重复数据);`bio_long` 仅旧书兜底、新蒸不产。
- [ ] `similar_page.items` 3-6 本,每本 `relation` ∈ {印证,补充,反驳} 且不全是 `印证`,`why`/`fit`/`order` 齐全;`reading_path` 非空;`sources` 齐。
- [ ] `views_page.topics` 2-5 个,每个 `viewpoint` 取自 distill 真实主张;`supporters`/`critics` 尽量各有、据实(一边倒如实留另一边为 `[]`);每条带 URL;国内外两轨都搜过。
- [ ] `reviews.items` 3-5 条,**尽量有正有反**;全好评已按铁律三标注 `(未见负面书评,信源存疑)`。
- [ ] 每条外部信息(作者/同类书/观点/书评/跨书)都带可点击 http(s) URL(铁律一)。
- [ ] `cross_book_external` 只含「query 名单里查不到」的概念(§6),未与 Step4 互链重复。
- [ ] 心理学 `evidence_page.claims` 与 distill 全部 claim_id 无多无少;状态/置信度/复制/范围结构合法;非 not_testable 每项至少 1 个一手 URL;页面三栏没有把「原书确认」冒充「科学支持」。
- [ ] 豆瓣抓取失败处已降级,无重试轰炸痕迹(§4)。
- [ ] 全文破折号 `--`,无全角 `——`;书评/观点原文照录未润色改立场。

---

## V. 视频系列变体(source_type = video_series)

蒸视频系列时,enrich.json **五个键名不变**,schema 结构(§1)一字不改,只是语义与数据源变化如下。

| 键 | 书籍语义 | 视频语义 | 数据源 |
|---|---|---|---|
| `author_page` | 作者页 | **频道页 / UP 主页**(`media_type:"video"`):`infobox.known_for`=频道名、`photo`=频道头像、`birth` 常查不到→行删;`career`=主理人背景 + 内容谱系分期;`works`=同频道**其他**代表系列/爆款视频(`{title, year, one_liner, is_this_book, distill_slug}`,year 可为该系列年);`sources`=频道主页 URL(≥1) | 联网搜频道页 |
| `similar_page` | 同类书 | **同类频道 / 系列**:`items` 为同领域其他优质频道/系列,`relation` 仍 ∈ 印证/补充/反驳(指与本系列的关系);`reading_path` → 「观看路线」建议 | 联网搜 |
| `views_page` | 国内外观点对比 | **评论区实质观点 + 外部看法**:`topics`=本系列几个核心主张;`supporters`/`critics` 来自 ① `comments.json` 里有实质论点的评论(照录)+ ② 联网找的外部对该主题的不同看法;`source`=评论所在**视频 URL** 或外部 URL | comments.json + 联网 |
| `reviews` | 书评正反 | **观众评论蒸馏**(快速正反采样):`rating` 置 `null`(视频无统一评分);`items` 从 `comments.json` 提炼,非联网搜 | **`comments.json`(Step0-V 产物)** |
| `cross_book_external` | 跨书外部立场 | **不变**:同一概念在未蒸过的其他作品(书**或**视频)里的立场,可指向书 | 联网搜 |

### V.1 reviews 与 views_page 的分工(视频)
- `reviews` = **快速正反采样**:从 comments.json 直接选 3-5 条代表性评论(高 `likes` 优先),`{text 原话照录, stance 正/反, source=视频URL}`,内联展示,给「观众整体怎么看」的快信号。
- `views_page` = **深度观点对比**:先定 2-5 个本系列核心主张(`topics[].viewpoint`),对每个主张:① 从 comments.json 里挑**有实质论点**的赞同/质疑评论(照录,source=该评论所在视频 URL);② 联网找外部(其他博主/媒体/文章)对该主题的不同看法(source=外部 URL)。组织成子视图。
- 两者都可用 comments.json,但 reviews 是浅采样、views_page 是按观点组织 + 外部补充。**comments.json 里的评论只从抓到的真实评论选,禁联网另搜评论、禁凭印象编评论**;comments.json 文本已做代理清洗,原样可用。

### V.2 频道页(author_page 视频专项)
频道页与书籍作者页**共用同一套结构化 schema**(§1 的 author_page),只把 `media_type` 设为 `"video"` 来切换措辞与数据源:

- `media_type: "video"` → 作品栏(S5)标题措辞由「主要作品」改为「**主要作品与系列**」;`works` 条目 = 同频道**代表系列 / 爆款视频**(不是本次蒸的这几集),`{title, year, one_liner, is_this_book, distill_slug}` 语义完全复用(year 可为该系列/视频发布年)。
- `infobox.known_for` = **频道名**(而非某本书);`infobox.photo` = 频道头像;`birth`/`ancestry`/`education` 等常查不到→逐行删(素人 UP 主正常);`roles` = 如「B 站 UP 主」「知识区博主」。
- `infobox.extra[]` 放平台特有事实:频道 / 平台 / 开播年份 / 订阅数。
- `career` = 主理人背景 + 频道内容谱系分期;`impact.stats[]` = 订阅数 / 总播放等;`this_book` 语义变为「他与这个系列」;`debate` = 外界对该频道的评价。
- 联网找频道简介 / 百科 / 代表作介绍填充;拿不到 → 整块 `null`。`bio_long` 仍作 legacy 兜底(旧数据未结构化时按 v2 散文渲染),新蒸系列不再产。

### V.3 收尾自查补充(视频系列额外过)
- [ ] `reviews` 的每条 `source` 都是**视频 URL**(非书评站),text 出自 comments.json(未联网另搜);倾向如实反映评论区(未为平衡编造反面),全好评已标注 `(评论区未见明显批评)`。
- [ ] `views_page` 的评论区部分出自 comments.json(照录),外部部分带外部 URL;两部分来源不混淆。
- [ ] `author_page` 是频道页语义,`works` 未把「本次蒸的这几集」当成其他代表作重复列。
- [ ] comments.json 缺失或为空(Step0-V 的 fetch 全失败 / 抖音降级)→ `reviews` 置 `null`;`views_page` 若外部也搜不到 → 整块 `null`。

# biography_corpus -- 证据型人物传记资料库

这条路径用于把一个历史人物的生平材料整理成**可追溯、可争议、可迁移、可发布**的数据资料库。它回答的不是「这个人表达过哪些思想」，而是「发生过什么、依据是什么、不同来源如何冲突、正式版本为何这样裁决」。

> 当前数据契约是实验性的 `0.9.0-candidate`。数据契约版本与本仓库 SemVer 属于两个独立版本域；候选期字段仍可能调整。若宿主直接复用源码 API，应固定到明确的仓库 tag（本次发布为 `v0.8.0`），不要跟随可变的 `main`。

## 0. 路由与边界

| 目标 | 应走路径 |
|---|---|
| 蒸馏一本书或一组视频 | Step0-Step7 主管线 |
| 归并一个创作者自己的跨媒介观点 | `creator_corpus` |
| 汇合多来源，建立人物生平、作品、关系、争议与引语的证据库 | `biography_corpus` |
| 设计页面、SEO、站点路由或执行部署 | 下游产品/网站能力 |

`biography_corpus` 负责公共资料模型、初始化、审计和发布前门禁。它不规定某个网站长什么样，也不把页面交互状态写回事实层。下游只能消费投影。

## 1. 单向证据链

```text
Source Unit -> Observation -> MergeDecision -> Canonical -> Editorial -> Projection
     |                                        ^
     +-> ExternalVerification ----------------+
```

- **Source Unit**：一本书的一版、一篇论文、一件馆藏记录或一个可复查网页，不是笼统的机构名。
- **Observation**：来源在某个明确 locator 上实际支持的最小主张。解释与事实必须分开记录。
- **MergeDecision**：正式 reviewer 对 Observation 的接纳和 Canonical 写入方式作出的签署裁决。
- **Canonical**：跨来源合并后的现役人物事实，分为 People、Events、Works、Relations、Controversies、Quotes 六类。
> 🔴 **抽取阶段的字段上限决定了下游能写多厚**（2026-08-24 立）。
> 提炼提示词 v6 曾规定 `quote_text` ≤ 80 字符并明令「超过就挑一句或直接放弃」、
> `detail_hint` ≤ 120 字符、每包最多 10 条候选。结果是素材在入库时就被切成碎片：
> 爱因斯坦线的旅行日记 21.5 万字，全书只抽出 **1 条**观察；主传写到 4.7 万字，
> 只用掉叙事主干源文的 **5.8%**，读起来像简报。
>
> 写主传的人手里从来没有长文本，**这不是笔力问题，是米不在锅里**。
> 改写作规范、喊「写深一点」都无效——形容词改不动这个。
>
> v7 已取消引文上限、把细节栏改为下限 80 / 上限 400 字符、候选条数按包长给下限。
> 为新人物设计提炼契约时，**先问一句「这个上限会不会让下游没东西可写」**。
>
> 配套：产品层的篇幅与深度判据见 `sansheng-yiye/references/deep-prose.md`
> （等密重写：≥400 字/幕 · ≥70% 源段覆盖 · 40–70% 等密比 · ≥1 直引/幕）。
>
> 一手材料另有一条路：当事人的日记、书信、文集**整段直引不改写**，
> 不必经过候选提炼。爱因斯坦线用程序按「本人文字区间 + 归属分层」直接建索引
> （`工具/extract_first_person.py`），拿到 2,263 条 / 21 万字可直引原文，
> 比模型抽取更准也更省。前提是先划清编者前言、伪托语录与他人评价的边界——
> 把编者的话当原话引用，读者完全无从察觉。

- **ExternalVerification**：对既有主张的外部复核。它必须反链来源和目标，但不能越过 Observation / MergeDecision 直接改写 Canonical。
- **Editorial**：章节、概览、布局和档案等叙事选择。它可以选择怎样讲，不能创造新的事实。
- **Projection**：给页面、API 或其他消费者的只读输出。

JSON Schema 只验证单个文档的形状；`scripts/biography_contract.py` 验证跨文件语义闭包。CLI、宿主编译器和测试必须调用这一份实现，不能分别复制一套近似规则。

## 2. 初始化一个独立人物 store

公共入口只有一个：`scripts/biography_store.py`。新人物从 v2 骨架开始，不复制另一个人物的目录。

```bash
python scripts/biography_store.py init \
  --store-root ./biography-data/sample-scholar \
  --slug sample-scholar \
  --subject-id per-sample-scholar \
  --catalog-name "Sample Scholar" \
  --language en
```

`--language` 默认 `zh-CN`。`catalog_name` 只是 draft/bootstrap 阶段的兼容提示；发布前必须与主人物 Canonical Person 的 primary name 一致，人物姓名的正式真源始终是 Canonical Person。

初始化器创建 manifest、六类 Canonical JSONL、治理账本和 Editorial 空骨架。它必须拒绝覆盖已有正式数据；确需迁移时先用 `audit` 盘点，不要重新初始化。

建议布局：

```text
sample-scholar/
  manifest.json
  source-registry.json
  observations.jsonl
  merge-decisions.jsonl
  external-verifications.jsonl
  source-coverage-decisions.jsonl
  work-classifications.jsonl
  work-identity-decisions.jsonl
  quote-attribution-audits.jsonl
  prose-risk-reviews.jsonl
  changesets.jsonl
  model-recommendations.jsonl
  media-assets.jsonl
  canonical/
    people.jsonl
    events.jsonl
    works.jsonl
    relations.jsonl
    controversies.jsonl
    quotes.jsonl
  editorial/
    chapter_order.json
    chapters.json
    overview.json
    layout.json
    dossier.json
    media.json
```

## 3. Manifest v2：身份与目录不可混为一谈

`manifest.json` 使用 `biography-store-manifest-v2`，并显式声明：

- `subject.slug`：目录和路由 namespace；目录名必须与它相等。
- `subject.subject_id`：稳定历史人物 ID；它不必由 slug 推导。
- `subject.id_namespace`：新对象 ID 的 namespace；必须与 slug 相等。
- `canonical` / `editorial`：全部文件映射，消费者不得靠固定文件名猜测。
- `governance`：正式 reviewer allowlist、Source Registry 和所需账本。
- `projection`：人物专属路由、资源路径、CSS scope 与显式共享资源。
- `publication`：draft / review / published 状态及发布所需元数据。

manifest 不复制人物姓名。主人物 Canonical Person 是姓名和 name forms 的唯一真源。旧 ID 若已被外部引用而不能重写，应通过显式 legacy alias 迁移，不要为追求整齐破坏稳定引用。

## 4. 先建来源，再写观察

每个 Source Unit 至少要能回答：

1. 这是哪一个具体版本、见证本、网页快照或馆藏对象？
2. 读者如何回到支持主张的准确位置？
3. 这个来源能证明什么，又不能证明什么？
4. 它与哪些 Observation、ExternalVerification 双向连接？

Locator 应使用来源本身的定位体系：卷、篇、叶、页、行、条目或 accession 各归各位，不能把它们互换。传统文献、手稿和多版本作品应保留 edition / witness；博物馆对象应保留 accession。历法日期也要保留原始书写，不能只留下换算后的 ISO 日期。

Observation 一条只承载一个可审计主张，并显式携带 `subject_id`、`id_namespace`、`source_id`、locator、certainty 与 statement kind。来源正面支持、来源内部解释、编者推断和未知状态不可揉成一句。

## 5. MergeDecision：两次判断，exact-once

每条 Observation 先经过 `observation_admission`：

- `accept`：允许进入正式事实合并流程。
- `hold`：材料值得保留，但当前不足以裁决。
- `reject`：不进入 Canonical；拒绝原因仍留在账本。

只有 `accept` 才能再有一条 `canonical_resolution`，其 verdict 为 `adopt / create / enrich / correct / merge`。由此形成 exact-once 约束：

- 每条现役 Observation 恰有一条 signed admission。
- accepted Observation 恰有一条 signed resolution；hold/reject 不得有 resolution。
- 每个 active/hold Canonical 都有可追到 Observation 的正式 resolution。
- redirect 只能由 signed merge 产生，并一步指向同类型的最终 active 或 hold 对象；只有 active 目标才能暴露为公开 alias。

`status=superseded` 只保留审计历史，不参与现役 exact-once。迁移旧资料时，无法重建历史创建动作可使用 `adopt + migration_basis`；不知道的历史审核时间写 `null`，不要补造精确时间。

## 6. 六类 Canonical 的历史资料语义

### 6.1 Person 与姓名形式

主人物必须有一个 primary name。字、号、别名、异体、罗马化形式分别进入稳定的 `name_forms`；每个 name form 自带语言、文字体系、证据、适用时期和确定性。姓名形式不是新的 Person，也不要求每个人都具备罗马化形式。

### 6.2 Event 与日期

事件日期可保留原历法、原文、展示标签、精度和起止范围。若提供换算日期，还要记录换算方法、依据 Observation 与换算 certainty。来源只到某年时不得伪造月日。

### 6.3 Work 的三个层级

区分 intellectual work、textual expression 与 material manifestation：作品概念、某个文本版本、某件实物载体不是同一个对象。手稿、刻本、译本或馆藏卷轴必须通过明确关系连接，不能因为标题相同就跨层级 merge。

### 6.4 Relation

active Relation 必须有可解析端点，其中至少一个是主人物。`counterpart_hint` 只能帮助人工处理 hold 数据，不能替代正式端点。

### 6.5 Controversy

争议由一个 question、两个或更多 positions 及各自的 source/evidence 构成；不要预设所有争议都只有两方。consensus 可为 none / partial / majority / resolved / unknown。证据支持多种说法时，应保留结构化分歧，不要把单一猜测写成 confirmed 事件。

### 6.6 Quote

引语必须区分作者、作品、实际说话者和文本形式。persona、narrator 与历史人物本人不是同一语义；原文、异文和翻译进入不同 text form，并分别绑定 witness / locator / evidence。翻译不能冒充原文，伪托语句不能把主人物标为事实 speaker。

### 6.7 Media ledger

媒体不是事实层的装饰字段。资源账本要分别记录 creator、object attribution、depicted subject、真实性判断、权利状态、来源和文件摘要。一个作品是谁创作的、画面描绘谁、馆藏对象归属谁、文件能否公开使用是四个问题，不能压成一个 `author`。没有可靠肖像时，可以选择手稿、器物或地点作 hero；publish-ready 必须阻断权利不明的正式资产。

## 7. 外部核验与模型治理

外部核验的正确路径是：

1. 找到可独立复查的来源与 locator。
2. 新增或补强 Source Unit 和 Observation。
3. 创建 `ExternalVerification`，连接 sources 与 Canonical targets。
4. 如事实结论需要变化，另走 admission / resolution，由正式 reviewer 签署。
5. Canonical、Source Unit 与 verification 建立双向反链。

GLM-5.3 或其他外部模型适合并行完成来源候选整理、缺口扫描、冲突比较与修订建议。它们的产物一律是 `recommendation_only`，必须保留模型、任务、输入范围和建议引用，且不能成为 formal review。正式签署者只能是 manifest allowlist 中的 `human` 或 `main_agent`；伪装成人名的模型 reviewer 同样会被门禁拦截。

## 8. Audit 与 Verify

### 8.1 单人物审计

```bash
python scripts/biography_store.py audit \
  --store-root ./biography-data/sample-scholar \
  --mode audit

python scripts/biography_store.py audit \
  --store-root ./biography-data/sample-scholar \
  --mode strict-data --json

python scripts/biography_store.py audit \
  --store-root ./biography-data/sample-scholar \
  --mode publish-ready
```

- `audit`：迁移盘点。只有 fatal 返回失败码；非 fatal 缺口仍完整报告，不能把结果描述为“已合规”。
- `strict-data`：要求 v2 manifest、治理账本、六类 Canonical、证据/解释/核验闭包、redirect、关系、历史资料语义与资源隔离全部成立。内容可以稀疏，但不能不诚实。
- `publish-ready`：完整执行 strict-data，再要求 publication 与 Editorial 达到发布状态。

### 8.2 编译/导出前验证

```bash
python scripts/biography_store.py verify \
  --store-root ./biography-data/sample-scholar \
  --phase compile

python scripts/biography_store.py verify \
  --store-root ./biography-data/sample-scholar \
  --phase export --json
```

`verify` 与 `audit` 调用同一 `audit_store()` 谓词。compile/export 不允许各自维护一份删减版检查：

- legacy store 可在迁移期间继续读取，但 fatal 仍阻断。
- v2 draft 空骨架可以初始化和迭代。
- v2 一旦进入有内容的 draft，compile 至少达到 strict-data。
- review/published 以及正式 export 必须达到 publish-ready。

退出码 0 只说明被声明的结构与闭包成立，不代表所有历史解释已经穷尽。高风险事实、争议和译文仍需人工语义复审。

## 9. 跨人物隔离与 corpus 审计

每个人物必须拥有独立：

- store 根、slug、ID namespace 与稳定 subject ID；
- Canonical / Editorial 文件映射和治理账本；
- route base、asset base、asset target 与包含 slug 的 CSS scope；
- Source↔Observation↔Decision↔Canonical↔Verification 闭包。

共享资源只有在 manifest 中声明 `owner=biography-series`、`read_only=true`、`@series/` 引用和 SHA-256 时才可跨人物复用。另一个人物的路径、人物 ID、CSS selector、资产目录或 reviewer 不得成为隐式默认值。

批量检查使用：

```bash
python scripts/biography_store.py audit-corpus \
  --corpus-root ./biography-data \
  --mode strict-data --json
```

`audit-corpus` 除逐人物运行同一审计外，还检查 slug、namespace、路由、资源目标和 Canonical ID 的跨 store 冲突。新增第二个人物前先跑一次，批量发布前再跑一次。

## 10. 源码级 Python API 与宿主适配器

稳定、面向使用者的正式入口是 `scripts/biography_store.py` CLI。本仓当前不发布 PyPI 包；下面这些函数属于源码级 API。需要嵌入自有编译器时，从 `scripts.biography_contract` 导入，并把依赖固定到明确的仓库 tag：

- `manifest_v2_skeleton(...)`：生成新人物 v2 manifest 骨架。
- `normalize_manifest(...)`：给迁移期消费者提供受控的 v1/v2 兼容视图。
- `audit_store(...)`：单人物统一语义审计。
- `audit_corpus(...)`：跨人物冲突与逐 store 审计。
- `assert_store_ready(...)`：compile/export 前 fail-closed 门禁。

宿主可以写薄适配器处理本地路径，但不得复制或改写谓词。Schema registry 的定义名、Python registry 与测试 fixture 必须一一对应；改规则后应同时增加正例、反例和 mutation test，确认门禁真的会红。候选期源码 API 不承诺跨 tag 自动兼容，升级时必须先运行宿主回归。

## 11. 完成定义

一个人物资料库只有同时满足下列条件，才可交给发布层：

- source、observation、decision、canonical、verification 的双向证据链闭合；
- 所有正式裁决由 allowlist reviewer 签署，模型只保留 recommendation；
- 日期、版本、姓名、争议、引语和媒体权利没有被压平成不真实的通用字段；
- 单人物 `publish-ready` 通过，整个 corpus 的 `audit-corpus --mode publish-ready` 也通过；
- projection 可由源数据确定性重建，且下游没有反写事实层。

任何一项未满足，都应继续处于 draft/review，而不是靠降低门禁或删除争议来“发布成功”。

# 跨书索引协议 -- Step4 knowledge-index.json 登记与互链(sansheng-distill)

> **执行手册,不是理论文**。管线跑到 Step4 时 agent 逐节照做:把本书 `distill.json.concepts[]` 按 **5-tag 增量合并协议**登记进全局跨书索引,并为页面 M11 模块生成已蒸书互链。
> 核心立场:索引**越蒸越富**,新书**增强而非重置**既有知识;`CONTRADICTS` 分歧**原样保留、绝不抹平**。
> 全文破折号一律 `--`;规则全部给可判定标准(数字/枚举/命令),不用「酌情」「适当」。

---

## 0. 路径与变量约定(全文只定义一次)

| 占位符 | 展开为 |
|---|---|
| `$SKILL` | 本 skill 目录(安装后为 `~/.claude/skills/sansheng-distill`) |
| `$DATA` | 书数据根目录,由环境变量 `DISTILL_DATA_DIR` 指定(默认 `./distill-data`) |
| `{书目录}` | 本书数据目录,**纯 `{slug}`**(如 `touzi-zui-zhongyao-de-shi`);不含书名,避免中文目录名 |
| 跨书索引 | `$DATA\knowledge-index.json`(数据与 skill 分离,skill 升级不动此文件) |
| 本书合并单 | `$DATA\{书目录}\index-merge.json`(本步产出,喂给 update_index.py) |
| 索引脚本 | `$SKILL\scripts\update_index.py`(Task 2 产物) |

下文命令里的 `$SKILL` / `$DATA` / `{书目录}` 直接替换成上表实值再执行。

上游接口:本步从 `method.md` §6 定义的 `distill.json.concepts[] = {concept, one_liner, stance, anchor}` 出发(method.md「附」节:concepts 供本步登记与互链)。

---

## 1. 两个 schema(整块契约)

**knowledge-index.json**(全局索引,`$DATA\knowledge-index.json`;不存在时 update_index.py 视为 `{"version":1,"concepts":[]}`):

```json
{
  "version": 1,
  "concepts": [
    { "concept": "安全边际", "one_liner": "…",
      "entries": [{ "book_slug": "…", "book_title": "…", "source_type": "book|video_series", "stance": "…", "anchor": "…", "quote": "…", "relation": "NEW_CONCEPT|SUPPORTS|REFINES|CONTRADICTS|NEW_SUB_ASPECT" }] }
  ]
}
```

**index-merge.json**(本步 agent 产出、update_index.py 消费;顶层是**数组**,每元素一个待合并概念):

```json
[
  { "concept": "安全边际", "relation": "SUPPORTS", "one_liner": "仅 NEW_CONCEPT 时必填",
    "entry": { "book_slug": "…", "book_title": "…", "source_type": "book|video_series", "stance": "…", "anchor": "…", "quote": "…" } }
]
```

字段约束(与 update_index.py 校验逐字一致):

| 字段 | 位置 | 要求 |
|---|---|---|
| `relation` | 顶层 | 必须 ∈ `{NEW_CONCEPT, SUPPORTS, REFINES, CONTRADICTS, NEW_SUB_ASPECT}`,否则 exit 1 |
| `concept` | 顶层 | 非空;非 NEW_CONCEPT 时必须**逐字**等于索引现有概念名(见 §4),否则 exit 1;NEW_CONCEPT 时不得与现有名重复,否则 exit 1 |
| `one_liner` | 顶层 | **仅 NEW_CONCEPT 必填**(用作新概念的一句话释义);其它 relation 忽略,合并时不改动既有 one_liner |
| `entry.book_slug` | entry | **必填**(本书 slug);同一 slug 已在索引 → exit 2,需 `--force`(见 §2 ④) |
| `entry.book_title` | entry | **必填**(本书书名 / 视频系列标题) |
| `entry.source_type` | entry | 可选,∈ `{book, video_series}`,**缺省 `book`**(向后兼容,老索引无此字段照读);标记本条来自书还是视频系列,供跨媒介展示。非法值 → exit 1 |
| `entry.anchor` | entry | **必填**(本作品内该概念位置;书=`第3章·约45-52页`,视频系列=`视频3` 或 `视频3·12:30`,格式见 method.md §5 / §V.3) |
| `entry.stance` | entry | 强烈建议(本书对该概念的立场,供 M11 分歧表展示) |
| `entry.quote` | entry | 强烈建议(一句原文,供 M11 分歧表引证) |

> update_index.py 合并时会把顶层 `relation` 注入 `entry`(存进索引的 entry 自带 relation);同书再登记时**覆盖该书旧条目而非累加**(见 §2 ④ 幂等说明)。

---

## 2. Step4 执行流程(精确命令,四步)

**① 拿现有概念名单(只读):**

```
python $SKILL\scripts\update_index.py query --index $DATA\knowledge-index.json --names-only
```

输出 = JSON 概念名数组(索引不存在时输出 `[]`)。此步与 `enrich.md` §6 共用同一次 query,不必查两遍。去 `--names-only` 则输出全索引(含 entries),需要看某概念既有立场做匹配时用全量。

**② 语义匹配 + 赋 5-tag,写 index-merge.json:**

把 `distill.json.concepts[]` **逐个**与 ① 的名单做语义匹配(同义合并规则见 §4),为每个概念决定 relation(判定标准见 §3),组装成数组写入:

```
$DATA\{书目录}\index-merge.json
```

- 命中索引现有概念(含同义词)→ relation ∈ {SUPPORTS, REFINES, CONTRADICTS, NEW_SUB_ASPECT},`concept` 填**索引现名**。
- 未命中 → relation = NEW_CONCEPT,`concept` 填本书概念名,`one_liner` 必填。
- 每个概念的 `entry.book_slug/book_title/anchor` 取本书值(anchor 沿用 `distill.json.concepts[].anchor`)。
- 未命中索引、又想补外部书立场的概念 → 不进本文件,转 `enrich.md` §6 的 `cross_book_external`(联网找,带 URL)。

**③ dry-run 校验(不写盘):**

```
python $SKILL\scripts\update_index.py register --index $DATA\knowledge-index.json --merge "$DATA\{书目录}\index-merge.json" --dry-run
```

exit 0 = 校验通过(打印「dry-run 通过: N 条待合并」);exit 1/2 见 §2.1,先修 index-merge.json 再重跑,**不通过不许进 ④**。

**④ 真跑合并(去掉 --dry-run):**

```
python $SKILL\scripts\update_index.py register --index $DATA\knowledge-index.json --merge "$DATA\{书目录}\index-merge.json"
```

成功打印「合并完成: N 条, 现有概念 M 个」;写前自动备份 `knowledge-index.json.bak`。
**仅当确为「重蒸同一本书」**(该 book_slug 已在索引、要用新蒸结果覆盖旧条目)才追加 `--force`:

```
python $SKILL\scripts\update_index.py register --index $DATA\knowledge-index.json --merge "$DATA\{书目录}\index-merge.json" --force
```

`--force` 幂等:同书同概念的旧 entry 被**覆盖**(按 book_slug 去重),不累加。

### 2.1 退出码处置表

| exit | 含义 | 处置 |
|---|---|---|
| `0` | dry-run 通过 / 合并完成 | ③ 通过进 ④;④ 通过则本步完成 |
| `1` | 校验失败(stderr 列**全部**错误) | 按 stderr 逐条改 `index-merge.json`(非法 relation / 缺 concept / entry 缺 book_slug\|book_title\|anchor / NEW_CONCEPT 撞名 / 非 NEW 却索引无此概念),回 ③ 重校验。**禁止用 `--force` 绕过 exit 1**(`--force` 只解 exit 2,对校验错无效) |
| `2` | 同书冲突(该 book_slug 已在索引) | 仅当**确为重蒸同书**才加 `--force` 覆盖(④);若 slug 是**撞车**(不同书误用同 slug)→ 改 `entry.book_slug` 换唯一 slug,回 ③ |

> 对齐 autopilot 铁律:exit 1 是内容错,必须修数据;`--force` 不是「跳过校验」的开关,别拿它绕过 exit 1。

---

## 3. 5-tag 判定标准(各配一个例句)

以「本书对某概念的立场 vs 索引里该概念既有立场」判定。基准场景:索引里已有概念「安全边际」= 买入价远低于内在价值,留出犯错余量。

| tag | 判定标准 | 例句 |
|---|---|---|
| **SUPPORTS** | 同立场,提供**新证据/新案例**加固,方向和边界都不变 | 索引已有《聪明的投资者》的「安全边际」;现蒸《投资最重要的事》,马克斯用「便宜是最可靠的风险控制」佐证同一立场并给新市场案例 → SUPPORTS |
| **REFINES** | 同方向,但**追加边界条件 / 限定适用域**,把粗结论收细 | 现蒸《安全边际》(卡拉曼)同意留足余量,但补「成长股难估内在价值时该概念失灵,须改用清算价值」-- 同向 + 加边界 → REFINES |
| **CONTRADICTS** | **立场相反**;**禁止抹平**,不揉成「都对/要平衡」,M11 分歧表左右并列原样呈现 | 某成长投资著作主张「为伟大公司支付溢价、放弃安全边际」,与格雷厄姆低价买入直接对立 → CONTRADICTS;两方立场分别照录,不合并成一句 |
| **NEW_SUB_ASPECT** | 同一概念的**新侧面**(既有条目未覆盖的维度) | 索引「安全边际」偏财务估值面;新书从「心理安全边际 = 预留情绪犯错空间」这一未收录侧面切入 → 同概念、新侧面 → NEW_SUB_ASPECT |
| **NEW_CONCEPT** | 索引里**没有**该概念(query 名单查不到) | query 名单里没有「能力圈」,本书首次提出 → NEW_CONCEPT(顶层 `one_liner` 必填) |

判定顺序建议(命中即停):索引没有 → NEW_CONCEPT;有且立场相反 → CONTRADICTS;有、同向但加边界 → REFINES;有、是没覆盖过的新维度 → NEW_SUB_ASPECT;有、同立场纯加固 → SUPPORTS。

> **CONTRADICTS 硬约束**:分歧是跨书阅读的价值来源,不是要消除的噪声。既不改写本书立场去迁就索引,也不改写索引旧条目去迁就本书;两条 entry 都留在同一 `concept` 下,M11 分歧表原样呈现(§5)。

---

## 4. 语义匹配 / 同义合并规则(concept 字段怎么填)

`distill.json.concepts[]` 里的概念名可能与索引现名字面不同但**语义同一**,须合并为一条,不得因用词不同重复建概念。

1. **判同义**:指同一知识点即算同义,含中英/译名/近义表述。示例:`安全边际` = `margin of safety`;`能力圈` = `circle of competence`;`市场先生` = `Mr. Market`。
2. **命中后 concept 填索引现名**:非 NEW_CONCEPT 时,`index-merge.json` 的 `concept` 必须**逐字**等于 ① 名单里的现有名(update_index.py 用 `concept in existing` 做存在性校验;字面对不上会判「索引没有该概念」→ exit 1)。即便本书原文叫 `margin of safety`,只要索引现名是 `安全边际`,就填 `安全边际`。
3. **NEW_CONCEPT 用本书名**:确认索引无同义概念后,`concept` 用本书 `distill.json.concepts[].concept`,并确保不与任何现有名重复(重复 → exit 1);`one_liner` 必填。
4. **一书多概念指向同一索引概念**:去重后对该索引概念只登记**一条** entry(取立场最鲜明、anchor 最准的一条),避免同书同概念多 entry。
5. 拿不准是否同义时,先 `query`(去 `--names-only`)看该候选概念的既有 entries 立场原文再定,别凭概念名硬猜。

---

## 5. 页面互链规则(M11 模块渲染)

Step4 合并后,为页面 M11-network 的「跨书观点」子块生成**已蒸书互链**:凡本书某概念在索引里也出现于**其他已蒸书**(entry.book_slug ≠ 本书 slug),就为每本这样的书渲染一条链接:

```html
<a href="{对方slug}.html#ch-{N}">《{对方书名}》怎么看</a>
```

- `{对方slug}` = 对方 entry 的 `book_slug`;`{对方书名}` = 对方 entry 的 `book_title`。
- `#ch-{N}` = 锚点:对方页章节 details 的 id 是 `ch-{chapters[].no}`(page-skeleton 章节 id 契约)。
  - **书**:anchor「第N章」的章号 N 即 `chapters[].no`,故 `#ch-N` 直接成立。
  - **视频系列**(对方 `source_type=video_series`):anchor 里的「视频N」是**视频序号**,而视频页章节 id 走 `chapters[].no`——多视频系列虽二者恰好一致,但**单/长视频按主题切段时 `chapters[].no ≠ 视频号`**(method §V.6),仅凭 entry.anchor 无法可靠定位具体章节(如概念 anchor `视频1·33:59` 可能落在 ch-6 而非 ch-1)。故**视频系列互链一律省略 fragment**,只写 `{对方slug}.html`(退回页顶)。跨媒介互链(书 ⟷ 视频)仍成立,只是视频侧落在页顶。
  - 若对方 anchor 无可提取序号(如 `约全书XX%处`),同样**省略 fragment**,只写 `{对方slug}.html`。
  - > 升级路:未来若 index entry 补存解析后的 `chapter_no`(而非只存 anchor 文本),视频侧可升级为章节级锚点。当前 entry 只存 anchor,故取页顶降级。
- **CONTRADICTS 的两方并排**:同一概念下若有 CONTRADICTS 关系的 entry,M11 用**分歧表**(`.network-table`)左右并列本书与对方的 `stance`/`quote`,原样呈现分歧,不给「谁对」结论(呼应 §3 CONTRADICTS 硬约束)。

**standalone 相对路径 与 上站的说明(重要):**

- href 一律写**相对路径** `{对方slug}.html#...`,**不写**绝对 file 路径、不写 http 域名 -- 这样 extract 抽取时原样保留 a 链。
- **standalone(file:// 直开)阶段**:各书在各自子目录 `$DATA\{书目录}\{slug}.html`,同级相对链接 `{对方slug}.html` 跨目录**不保证跳达**(可能 404)。这是**预期**的:互链是为**上站后**的站内布局设计的,standalone 阶段该链接主要供 extract 采集,**不作为可点验收项**。
- **跨书互链**:M11 的兄弟 slug 链接在单文件 HTML 里是相对路径;若托管到站点,由站点路由把兄弟 slug 解析成站内可达路径。

---

## 6. 索引没有的概念 → 转 enrich 联网(衔接 enrich.md)

§2 ② 里判为 **NEW_CONCEPT / 未命中索引**的概念,若还想在 M11 展示「这个概念其他(未蒸)书怎么看」:

- **不**在本步 register(它只登记本书自己的 entry)。
- 转 `enrich.md` §6 的 `cross_book_external`:联网找该概念在外部书里的立场,每条带 `source` URL,写进 `enrich.json`。
- 于是 M11 的「跨书观点」= Step4 互链(已蒸书,§5)+ enrich 外部条目(未蒸书,带 URL)两部分并列;两边共用 §2 ① 的同一次 query 结果切分,互不重复(命中索引走互链,未命中走外部联网)。

---

## 7. 收尾自查 checklist(逐条核对)

- [ ] `index-merge.json` 是数组;每元素 `relation` ∈ 五枚举、`concept` 非空、`entry` 含 book_slug/book_title/anchor。
- [ ] 非 NEW_CONCEPT 的 `concept` 逐字等于 query 名单现名(同义已归并,§4);NEW_CONCEPT 的 `one_liner` 已填、未撞名。
- [ ] `entry.book_slug` 为本书 slug 且非撞车;需覆盖旧条目才用 `--force`,未用 `--force` 绕 exit 1。
- [ ] ③ dry-run exit 0 后才跑 ④;④ 打印「合并完成」。
- [ ] CONTRADICTS 分歧原样保留,未抹平;M11 分歧表左右并列(§3/§5)。
- [ ] M11 互链写相对路径 `{对方slug}.html#ch-{N}`,无绝对/http 路径;standalone 不跳达属预期(§5)。
- [ ] 未命中索引且需外部视角的概念已转 `enrich.md` cross_book_external(§6),未与互链重复。
- [ ] 全文破折号 `--`,无全角 `——`。

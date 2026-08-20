---
name: sansheng-distill
description: Use when 用户要把一本书全文、单个视频（按 1 集）、YouTube/B站视频系列，或一个视频博主/人物的全部作品（跨媒介人物思想蒸馏）做成深度蒸馏资料；触发词：蒸馏这本书、拆书、蒸馏视频、视频系列蒸馏、蒸馏 UP 主、蒸馏这个博主、人物思想蒸馏。只要字幕摘要、单篇文章写作或「一页」世界史专项时不用此 Skill。
---

# sansheng-distill -- 书籍/视频蒸馏引擎(v3 浏览型)

输入一本书的电子全文(或一组视频),跑完 Step0-Step7 管线(Step2 分两遍),产出一个可 `file://` 直开的**单文件交互 HTML 蒸馏页**。

**v3 页型 = 浏览型「凝练地图 + 详实正文 + 批判证据 + 页内二级视图」**,按读者逻辑链组织:

| Tab | 装什么 |
|---|---|
| ① 全书速览 | 真封面 + 餐巾纸公式/因果草图 + 可点跳脑图 + 核心观点 + 最强反直觉主张 |
| ② 逐章精读 | 逐章 800-1500 字详实转述 + 概念筹码 + 金句墙;**目录态默认收起,可全部展开** |
| ③ 批判与评价 | 先复述作者论证,再放内在张力、批判四区、书评与观点对照;心理学书另列科学证据层 |
| ④ 行动清单 | 行动路线 + 决策规则 + 心智模型 + 第二人称自检(纯浏览,无打分) |
| ⑤ 延伸阅读 | 同类书、作者书架、跨域命名、跨书互链与阅读路径 |

交互:脑图可点跳章节、章节手风琴多开、两张页内全屏子视图(hash 路由开合)、多主题换肤。

**这是入口编排文件。** 先读本文对齐管线,再在每一步按下表**读对应 reference / 跑对应 script**;references 是各步的执行细则,不要凭记忆做。

## 先分流：蒸馏对象 → 路径

| 蒸馏对象 | 走路径 |
|---|---|
| 一本书全文 | 主管线 Step0-B（下表） |
| 单个视频（按 1 集）/ 一个视频系列 | 主管线 Step0-V（下表） |
| **一个博主/人物的全部作品（跨媒介思想蒸馏）** | **StepC · creator_corpus 路径（`references\creator-craft.md`）** |

判断口诀：分析单位是「作品」→ 主管线；分析单位是「人」→ StepC。用户说「蒸馏这个 UP 主 / 这个人 / 他的思想体系」即 StepC。StepA/StepB 是主管线的可选聚合步，与 StepC 不冲突。

> 🪶 **用轻量模型 / 弱 agent 跑本 skill(如 Gemini Flash 级、Antigravity 客户端)→ 先读 `references\flash-mode.md`。**
> 那份卡不降低任何质量标准,只把「靠自觉」的环节换成「可自检的判据」,并钉死六个最容易滑落的点。
> Opus / Sonnet 级模型照本文主管线走即可,不必读。

## 路径与变量约定(全文只定义一次)

| 占位符 | 展开为 |
|---|---|
| `$SKILL` | 本 skill 目录(安装后为 `~/.claude/skills/sansheng-distill`) |
| `$DATA` | 书数据根目录,由环境变量 `DISTILL_DATA_DIR` 指定(默认 `./distill-data`) |
| `{slug}` | 书的 ASCII kebab 短名(如 `jinqian-xinlixue`);全站唯一,别撞投资 `NN`/育儿 `pNN` |
| `{书目录}` | 本书数据目录,**纯 `{slug}`**(如 `jinqian-xinlixue`);不含书名,避免中文目录名、git/Windows 友好 |

命令里的占位符替成实值再执行。单书目录首次运行 Step0 时自动建。

## 数据目录约定(单书产物布局)

```
$DATA\
  knowledge-index.json          # 跨书概念索引(全库共享,Step4 维护,自动 .bak)
  {书目录}\
    book.txt                    # 全文(书=Step0-B;视频=Step0-V 组装的转写语料)  -- gitignore
    diagnose.json               # 入书诊断(书=Step0-B;视频=Step0-V 的 video_series 变体)
    raw\                        # 仅视频:各集原始转写 srt/txt(Step0-V)             -- gitignore
    series-input.json           # 仅视频:手写 manifest(Step0-V 输入)
    series.json                 # 仅视频:规范化 manifest(Step0-V 产物,下游只读它)
    comments.json               # 仅视频:观众评论(Step0-V,供 Step3 enrich.reviews)
    distill.json                # 蒸馏主对象 v2(Step2 两遍产:Pass1 骨架 + Pass2 narrative/excerpts)
    _pass2_g*.json              # Pass2 分块中间态(长书按章 fan-out 各组产物,合并回 distill) -- gitignore
    enrich.json                 # 联网增补 v2.1(五个基础键;心理学书加 evidence_page 科学证据层)
    claim-coverage.json         # 仅心理学:Pass1 待审计项到最终 claim 的裁决表
    source-audit.json           # 仅心理学:原文分段、逐项来源记录与四输入 hash
    index-merge.json            # 5-tag 合并清单(Step4 中间产物)
    {slug}.html                 # 单文件交互蒸馏页(Step6 产物,最终交付,≤3MB;真封面 base64 内联,无独立 cover 文件)
    _verify.png                 # Step7 验证全页截图                                  -- gitignore
```

> gitignore(建议在数据目录加 `.gitignore`):`book.txt` / `raw/` / `_verify.png` / `_pass2_*.json` / `*.bak` 不入库(版权原文 / 临时产物);其余(distill / enrich / HTML / index-merge / series / comments / diagnose;心理学另含 claim-coverage / source-audit)可入库。

---

## 管线表(Step0-Step7,Step2 分两遍)

每一步:**做什么 / 读哪个 reference / 跑哪条命令 / 产物 / 失败降级**。逐步照做,上一步产物是下一步输入。

| 步 | 做什么 | 读哪个 reference | 跑哪条命令 | 产物 | 失败降级 |
|---|---|---|---|---|---|
| **Step0-B** 入书诊断 + 转 txt(蒸**书**走此行) | 电子书 → 全文 txt + 诊断(格式/可提取/扫描版/乱码率/目录识别) | 脚本自足;分流规则见 `method.md §0` | `python $SKILL\scripts\convert_book.py "<书文件>" --outdir "$DATA\{书目录}"`(重转加 `--force`)。**套装/合集 epub**:先 `--list-volumes` 列分册,再逐本 `--volume "<分册名>"` 切(按 TOC 顶层 + spine 区间,不漏未列入目录的正文续页) | `book.txt` / `diagnose.json` | exit 2 = 缺依赖/格式不支持/拒覆盖 → 装 calibre(azw3·mobi)或补 pip 依赖或加 `--force`;**exit 3 = 需OCR / 需人工确认 → 停下问用户(见硬门禁①),不硬读、不编内容** |
| **Step0-V** 视频系列入库(蒸**视频**走此行) | 每个视频取材转写 → 手写 manifest → 组装语料 + 抓评论。章节=集数 | **`method.md §V.0`(取材 cascade,固定流程,先读)** + `§V`。分流:YouTube 优先抓字幕(**认准人工字幕**,`video-to-subtitle-summary`)/ 无字幕或需画面语义 → Gemini 原生在线(`claude-gemini-video`,免下载)/ 非 YouTube 先下载再解析 | ① 按 §V.0 取每视频**干净转写**(YouTube 人工字幕 `subtitle.{lang}.vtt` 可直喂 build_series;⚠️ 别用滚动重复 3× 的 `text.txt`/自动字幕),存 `$DATA\{书目录}\raw\{NN}_{id}\`;② 手写 `series-input.json`(`transcript` 指向选定的**干净**字幕文件);③ `python $SKILL\scripts\build_series.py --manifest "<series-input.json>" --outdir "$DATA\{书目录}"`;④ `python $SKILL\scripts\fetch_comments.py --series "$DATA\{书目录}\series.json" --out "$DATA\{书目录}\comments.json"`;⑤ 逐条 `yt-dlp --skip-download --print` 抓热度元数据(播放/赞/评论数/日期,供热度条;`--flat-playlist` 拿不到须逐条 full extract) | `book.txt` / `series.json` / `diagnose.json` / `comments.json` | build exit 3 = 全部视频缺转写/乱码 → 停下问用户(见硬门禁①);fetch exit 2 = 全失败或抖音不支持 → 评论整块降级(enrich.reviews 置 null),不阻塞蒸馏 |
| **Step1** 书型 + 领域判定 | 读诊断 + 全书抽样(首/中/末章),判书型、stakes;心理学书另写 `domain_profile` | `method.md §1` | 无(读 `diagnose.json` + `book.txt` 抽样) | `book_type/stakes/domain_profile?`(写入 distill.json) | 边界模糊按 §1.2 顺序裁决;`domain_profile` 不确定则不冒标,一旦标 psychology 就激活 G23/G24 |
| **Step2·Pass1** 压缩骨架(凝练地图) | 三轮认知压缩 + 四嫁接件 + v2/v4 延展字段 + 逐条补锚点与原书转述状态;心理学 core_ideas/decision_rules 逐条补唯一 claim_id + claim_type | `method.md §2-§5`(心理学另读 §1.6/§4.5.17) | 无(内化方法蒸馏,产出 JSON) | `distill.json` 骨架层(**除 `chapters[].narrative`/`.excerpts` 外全部字段**) | diagnose=分组蒸馏 → 走 `method.md §8`;产出后过 §7 门禁 G1-G23(条件门按 stakes/domain 激活) |
| **Step2·Pass2** 详实转述(详实正文) | 逐章两级检索(先读 Pass1 骨架保结构,再回 book.txt 该章原文 grep 案例/数字/原话保血肉)→ 讲书稿式 narrative(坡道开场 → 观点+完整案例故事+数据 → 一句接主线)+ 挑 excerpts。**长书按章 fan-out 并行**(每组≤5 章派 1 subagent 全 Opus,组内串行,主控合并) | `method.md §3.5`(两级检索 / 讲书稿模板 / 版权线 / fan-out) | 无(内化;长书分组各产 `_pass2_g*.json` 中间态,主控回填 distill.json) | 回填 `distill.json` 的 `chapters[].narrative`(书 800-1500 字/章·视频段 ≥400；**文章选编**设 `render_profile.archetype="文章选编"`，逐篇 ≥300 字)+ `chapters[].excerpts`(书每章 ≥1,原文 ≤150 字) | grep 不到支撑就降级不写该点,**禁凭印象编案例/编数字**；读者可见 narrative 禁写“蒸馏/审计/后续出版”等工作流元话语，禁用同章重复句凑字数；主控做 G9 / G14 机械核对 + **标志性案例保全抽检**(招牌故事必须整段完整出现,不得压成标签) |
| **Step3** 联网增补(页内子视图 + 内联) | 产五个基础块;心理学书再逐 claim 查元分析/复制研究/官方勘误,产 `evidence_page`,并在最终 distill/enrich 定稿后封存原文审计账本 | `enrich.md`(§1.1 科学证据契约 + §3 搜索 pass;视频看 §V);心理学另读 `source-audit.md` | 联网检索按 §3.4 路由只选一个引擎;心理学学术检索走 Tavily且只采一手论文/官方材料;按 source-audit schema 生成 claim coverage + audit | 普通书五键;心理学书第六键 `evidence_page` + `claim-coverage.json` + `source-audit.json` | 基础块可据实置 null;心理学 evidence_page/审计账本不可整块降级,证据不足须标低置信/not_testable 仍全量覆盖 |
| **Step4** 跨书索引登记 + 互链 | `distill.concepts` 逐个与现有索引语义匹配,赋 5-tag(SUPPORTS/REFINES/CONTRADICTS/NEW_SUB_ASPECT/NEW_CONCEPT),登记本书 entry + 渲染 ⑤ M11 已蒸书互链 | `cross-book.md`(§2 精确四步 + §3 tag 判定) | ① `python $SKILL\scripts\update_index.py query --index "$DATA\knowledge-index.json" --names-only` → ② 写 `index-merge.json` → ③ `... register --index "$DATA\knowledge-index.json" --merge "$DATA\{书目录}\index-merge.json" --dry-run`(exit 0)→ ④ 去 `--dry-run` 真跑 | `index-merge.json` / 更新 `knowledge-index.json`(+.bak) / M11 互链数据 | register exit 1 = 校验错 → 按 stderr 逐条修 `index-merge.json` 回 ③ 重校验(**禁用 `--force` 绕 exit 1**);exit 2 = 同书 slug 冲突 → 确为重蒸才加 `--force`,slug 撞车则换唯一 slug |
| **Step5** 设计两遍工作法 | 为这本书出 token plan + signature 决策,过对抗自审;品牌锁八成、书魂放两成 | `design-craft.md`(两遍工作法)+ `brand-tokens.md`(主题 token 契约) | 无(设计决策,内化到 Step6 填槽) | token/signature 定调(不落独立文件,直接指导 Step6) | signature 命中反 slop 黑名单(蓝紫渐变/emoji 图标/圆角+左边框卡滥用/凑数数据)→ 改;衬线模式必配 CJK 衬线兜底 |
| **Step6** 生成单文件 HTML | 复制骨架填五 tab + 两张页内子视图;删净 dummy;心理学书保留并填 `J-PSYCH-EVIDENCE`,普通书整段删 | `html-spec.md`(§1 区块规格 / §1.2.3 心理学证据 / §3 生成 / §5 体积) | 复制 `$SKILL\templates\page-skeleton.html` 到 `$DATA\{书目录}\{slug}.html` 后逐槽填充(vendor 已内联,勿动) | `$DATA\{书目录}\{slug}.html`(单文件,**≤3MB**) | 超体积先删 dummy 再压 excerpts/封面;禁删必需块、data-source 或心理学 G24 三栏 |
| **Step7** 出厂验证 v2 | 静态 lint + 原文事实门禁 + Playwright 冒烟 + G1-G24 条件契约。心理学严格域另核 `source-audit.json` 四 hash、章界、逐项原文命中与覆盖，并核 HTML 三栏一一对应 | `html-spec.md §3` + `method.md §7` + `enrich.md §1.1` + `source-audit.md` | 通用:`python $SKILL\scripts\verify_page.py "$DATA\{书目录}\{slug}.html" --distill "$DATA\{书目录}\distill.json" --source "$DATA\{书目录}\book.txt" --screenshot "$DATA\{书目录}\_verify.png"`;**已知心理学批次必须追加 `--require-domain psychology`**;`echo "退出码=$?"` | 退出码 + `_verify.png` | exit 0 才算完成;绝不放宽验证阈值或删检查项假过关 |

> ⚠ **视频路径 v2 尚未跑 E2E 验证**:骨架 / `method.md §V` / `html-spec.md §V` / `enrich.md §V` / `verify_page.py` 的视频分支已随 v2 更新到位,但尚未用视频样本完整重蒸验收(书样本《金钱心理学》已 E2E 通过)。蒸视频系列时按 §V 照做,遇到骨架/门禁与视频不吻合的坑先记录再修。
> 跑判成败的脚本别用 `\| tail` / `\| head` 取摘要(管道退出码取最后一段,`tail` 永远成功会吞失败);看完整结尾行或补 `; echo "退出码=$?"`。

> ⚠ Step6 只能在正式 page-skeleton.html 的基础上逐槽填入数据。严禁另起极简 HTML 壳，或删掉 theme-picker、initMindmap()、initHashRouter() 来“简化渲染”；这会丢失主题、脑图 viewer 和章节路由，Step7 会直接拒收。

## StepA · 作者演变聚合(可选,同一作者 ≥2 部已蒸时)

某作者在 `$DATA` 下已蒸 **≥2 部**作品时,可选做「思想演变专题」聚合页;单书蒸馏不涉及,**<2 部不生成**。

- **做什么**:只读各书 `distill.json`(**绝不重蒸**)聚合成 `author.json` → 渲染作者演变页 `author.html`(4 视图:时间线 / 母题 ribbon / 思想转向 / 概念演化图)。每书蒸馏页顶部「演变入口卡」(SLOT:AUTHOR-ENTRY)链到它。
- **读哪个 reference**:`author-craft.md`(§0 事实 vs 叙事铁律 / §2 author.json schema / §4 四视图数据契约 / §5 板块骨架 / §6 转向证伪层 / §7 入口卡)。
- **跑哪条命令**:`python $SKILL\scripts\build_author.py --author "<作者名>" --data-root "$DATA" --manual "$DATA\authors\{author_slug}\author.manual.json" --enrich "$DATA\authors\{author_slug}\author.enrich.json" --out "$DATA\authors\{author_slug}\author.json"`(已有 author.json 且 manual 缺失时防覆盖栏拒跑,确需重建加 `--force`;<2 部 exit 3 不生成);再复制 `templates\author-page-skeleton.html`、把 `#author-data` 槽替换为该 `author.json` 生成 `author.html`。
- **产物**:`$DATA\authors\{author_slug}\author.json` + `author.html`。
- **触发门槛 / 降级**:该作者 <2 部已蒸 → `build_author.py` exit 3 不生成、连网搜(enrich)不启、每书页入口卡整卡删。
- **出厂验证**:`python $SKILL\scripts\verify_page.py "$DATA\authors\{author_slug}\author.html"; echo "退出码=$?"`(自动识别作者页走独立门禁:4 视图齐 / 零外链 / Zero-Hex / lang=zh / 破折号 / 深链格式 / 转向 verdict 一致;exit 0 才算完成)。

## StepB · 主题聚合(可选,同主题 ≥3 本已蒸时)

同一主题下已蒸 **≥3 本**作品时,可选做「主题聚合专题」页 -- 把各书按流派归类、把分歧摆上台面、把可执行数字并排对照。单书/双书不涉及,**<3 本不生成**。StepA 聚合「同一**作者**的思想**演变**」(时间轴);StepB 聚合「同一**主题**下各书的**立场光谱与分歧**」(空间轴),对称迁移非照搬四视图。

- **做什么**:只读各书 `distill.json` + `knowledge-index.json`(**绝不重蒸**)聚合成 `topic.json` → 渲染主题聚合页 `topic.html`(4 视图:分类地图 / 分歧矩阵 / 维度对照表 / 书目导航)。每成员书蒸馏页顶部「主题入口卡」(SLOT:TOPIC-ENTRY)链到它。
- **读哪个 reference**:`topic-craft.md`(§0 事实 vs 归纳分层铁律 + 成员圈定 / §2 topic.json schema / §4 四视图数据契约 / §5 板块骨架 / §6 外部争议 enrich / §7 入口卡)。
- **跑哪条命令**:先手写 `$DATA\topics\{topic_slug}\topic.manual.json`(圈定 `members:[slug]` + schools 流派归类 + disputes 分歧分组 + dimensions 维度对照 + verdict 怎么选);再 `python $SKILL\scripts\build_topic.py --topic "<主题名>" --data-root "$DATA" --manual "$DATA\topics\{topic_slug}\topic.manual.json" --out "$DATA\topics\{topic_slug}\topic.json"`(已有 topic.json 且 manual 缺失时防覆盖栏拒跑,确需重建加 `--force`;<3 本 exit 3 不生成);再复制 `templates\topic-page-skeleton.html`、把 `#topic-data` 槽替换为该 `topic.json` 生成 `topic.html`。
- **产物**:`$DATA\topics\{topic_slug}\topic.json` + `topic.html`。
- **成员圈定 = manual 显式列 slugs**:主题边界是编辑判断,不改 distill schema、不自动按 tag 归堆(见 topic-craft §0)。
- **分歧诚实分档**:分歧矩阵的 `index_relation` 三档 -- `CONTRADICTS`(knowledge-index 已登记真对立,红旗)/ `curated`(编者从各书立场归纳、index 未登记,金标,`note` 须给依据)/ `parallel`(松散并列,聚合器剔除不渲)。**编者归纳出 index 未登记的分歧轴时,应回补进 knowledge-index**(顺带修 Step4 跨书分歧判定偏保守的欠充分)。
- **触发门槛 / 降级**:有效成员 <3 → `build_topic.py` exit 3 不生成、每书页入口卡整卡删;`external_debate` 整块搜空 → 该板块隐藏,分类/分歧/维度作书内事实照发。
- **出厂验证**:`python $SKILL\scripts\verify_page.py "$DATA\topics\{topic_slug}\topic.html"; echo "退出码=$?"`(自动识别主题页走独立门禁:4 视图齐 / 零外链 / Zero-Hex / lang=zh / 破折号 / 深链格式 / index_relation + certainty 枚举 / 分歧可回指;exit 0 才算完成)。

## StepC · 人物/博主蒸馏(creator_corpus 路径)

蒸馏对象是「**一个人**的跨媒介全部作品」(视频博主的全部视频 + 专栏/Newsletter + 书 + 播客)时走本路径,**不走 Step0-Step7 主管线** -- 主管线的分析单位是「一部作品」,本路径的分析单位是「人」,基本单元是跨媒介归并后的「观点族」。

- **做什么**:全量采集 → 来源卡建库 → 去重聚类(观点族/主题/关系/时间线) → 总体蒸馏(系统/模型/张力/谱系) → **外部交叉核验 + 通俗化两道闸(必做)** → 产出与网站 creator-distill 契约一致的 10 份数据 JSON + 作者简介。
- **读哪个 reference**:`creator-craft.md`(§0 路由 / §1 总原则「输入全量采集、分析完整建库、展示去重重构」/ §3 P0-P9 阶段管线与批次门 / §5 密度下限 / §6 外部交叉核验 / §7 通俗化两道闸 / §8 展示层信息架构 / §9 数据流规则)。
- **产物**:`{人物项目目录}` 五层数据(L0-L4) + 网站数据包(契约测试参照 `个人网站\web\tests\creatorDistill.data.test.ts`);页面渲染与部署归 `sandy-website`。
- **先例与模板**:Dan Koe 项目(`Cowork\其他\Dan Koe\`),首次执行已验证全流程;其来源卡规范、证据索引结构、导出器均可作模板复用。
- **与 StepA 的区别**:StepA 聚合「同一作者已蒸的 ≥2 本书」(只读 distill.json,绝不重蒸);StepC 从零蒸「一个人的全部语料」。人物出了书且书已单蒸,两者可共存。

---



## 硬门禁(三处,不过不许往下走)

1. **Step0 exit 3 → 停下问用户**:诊断判「需OCR」(扫描版纯图)或「需人工确认」(gb18030 疑似假字/乱码率>2%)时,**不启动蒸馏、不硬读、不编内容**,把 diagnose 结论报给用户定夺(补 OCR / 换文件 / 人工核编码)。**视频系列同理**:`build_series.py` exit 3(全部视频都缺转写,一个都没抓到)→ 停下问用户(补转写 / 换视频 / 核 manifest),不拿空语料硬蒸。
   > **`toc_detected: false` / `chapters_detected: 1` 也要停**(v0.5 补):目录结构没识别出来 = 蒸馏时手里**没有原书章节划分**,章数只能靠模型自由发挥(2026-07-26 实测:6 本全切自同一个「套装共5册」合订 epub,`toc_detected` 全 false,产出的章数一律被压成 6 章)。
   > **套装/合集 epub 走 `--volume` 切,别整本硬蒸、也别手工切**:`convert_book.py --list-volumes` 列出顶层分册与各自章数 → 逐本 `--volume "<分册名>"`。切分按 TOC 顶层定分册、按 **spine 区间**取正文(未列入目录的正文续页也收进来,只取 TOC 篇目会静默丢正文),`diagnose.title` 自动取分册名。`chapters_source` 字段标明章数来自 `epub_toc` 还是 `body_regex`。
2. **Step2 两遍质量门禁自查(G1-G23)**:Pass1 骨架 + Pass2 详实转述产出后,按 `method.md §7` 逐条自查。通用/书型/详实门 G1-G21 不变;`stakes=high` 条件激活 G22;`domain_profile.domain=psychology` 条件激活 G23,要求每条 core_idea/decision_rule 有唯一 claim_id + 合法 claim_type。命中即打回重蒸/回补,不带病进 Step3/Step6。
3. **Step7 verify v2 exit 0 才算完成**:`verify_page.py`(v2,传 `--distill` 追加契约门禁)退出码非 0 就不是成品。**已知心理学项目必须传 `--require-domain psychology`**,否则一本漏写 `domain_profile` 的书无法仅凭文件内容被通用验证器识别;默认不传则保持旧书兼容。心理学严格域另要求同书目录 `source-audit.json`,核四输入 hash、原文章界、逐项原文命中、全部 audit flags 账本覆盖、evidence 对最终 claims 的精确覆盖及 HTML 三栏映射(见 `source-audit.md`)。按输出修数据/样式后重跑,直到 exit 0。**绝不放宽验证阈值或删检查项来假过关**。
   > **T0 三道补盲门(v0.5,2026-07-27 加)**:`[占位]` 模板槽 / dummy 残留、`[schema]` 顶层必需键缺失、`[lint]` 封面是占位 SVG -- 三者**恒校验、任何 render_profile 不可关**。立法起因见 `flash-mode.md §0`(旧门禁 174 项全是「校验已有字段的取值」,默认「一定会填槽、一定产全 schema」;模型把模板原样交付或少产半个 schema 时,循环空转 = 零违规放行)。**`[schema]` 项对 2026-07-27 前蒸的旧书会报 render_profile/cover_intro 等缺失,属预期,旧书不必重蒸。**⚠ 默认/普通书 verify 仍主要查「结构 / 契约 / 版权长度 / 防注水」,不保证事实正确；心理学严格域会额外机检 source-audit 中声明的原文片段与行号、覆盖和输入 hash,但仍不能替代对「是否遗漏关键反例 / 是否误解语境」的人工语义复审。**exit 0 ≠ 内容绝对属实**(高后果书另做人工抽检,见铁律「不编造」)。

4. **批量交付闸 exit 0 才许上站**(v0.5,蒸多本时):单本 verify 只回答「这一本合不合格」,回答不了「**这一批该有的都在吗**」。上站前把**预期名单显式**交给批量闸核对:

   ```
   python $SKILL\scripts\verify_batch.py --data-root "$DATA" --slugs slug1,slug2,slug3; echo "退出码=$?"
   # 已知心理学批次必须把严格域传播到每一本
   python $SKILL\scripts\verify_batch.py --data-root "$DATA" --slugs slug1,slug2,slug3 --require-domain psychology; echo "退出码=$?"
   ```

   它逐本核 ①产物齐备(缺 distill/html = 这本根本没蒸完)②`verify_page.py` 退出码 ③交付卫生(enrich 缺失 / `_pass2_g*.json` 中间态残留)。心理学严格批次还强制 `book.txt` 与 `source-audit.json` 存在，自动传播 `--source` 并逐书复算审计 hash；默认批次行为不变。**退出码 0 才允许上站**;非 0 时二选一 -- 补完管线,或**把这本从上站名单里摘掉**。⚠ **名单留着而产物不存在 = 线上 404**(2026-07-26 实测:6 本里 2 本只跑到 Step0,仍被挂上作品集页)。

## 铁律(每步都守)

- **锚点**:蒸馏内容必须锚定原文,`method.md §5.1` **六类字段**(core_ideas / decision_rules / quotes / mental_models.evidence / chapters.excerpts / self_check)每条带 `anchor`,上站进 `data-source`;无锚点论断 = 门禁打回。
- **论点式标题(v2)**:`chapters[].title` / M04 `<h3>` 一律**可反驳的判断句**,禁「第N章 / 视频N」式纯章号、禁通用容器词(章节脉络/全书脉络/金句墙/总结/概述…),有效长度 ≥8 字(G8;verify 机拦黑名单+长度,判断句语义靠蒸馏自查)。**脑图二级节点(v4 批 A 双层化)例外**:`topic` 改概念关键词 ≤10 字做扫读层、**取消 ≥8 字下限**(仍守黑名单+禁容器词);可反驳判断句下沉到 `tags[0]`(≥8 字,verify 机拦缺失/过短),`tags[1]` 放「第N章」章码 chip(见 method §4.6 / html-spec §5)。
- **详实度下限(v2)**:每章 `narrative` 书 ≥800 字 / 视频段 ≥400 字(G9);宁可少论点讲透,不注水;**标志性案例 / 故事必须整段完整讲**(时间·人物·动作·转折·结果),禁压成一句标签。
- **真封面(书,v2)**:书籍 M01 封面必须**真封面 base64**(`data:image`),禁外链、禁纯色占位;联网拿不到才退占位 SVG。视频用系列封面(首集缩略图 `data:` URI)。
- **URL**:外部信息(作者/书评/同类书/观点对比/跨书外部/心理学科学证据)必须带可点击 http(s) 来源 URL;拿不到就按各块契约降级,不臆造。心理学可检验 claim 不得整块隐藏,证据不足要显式低置信或未复制。
- **不编造**:金句 `<blockquote>` / `excerpts` 原文照录不改写(直接照录单段 **≤150 字**,blockquote 明示引用,连续 30 字与原文雷同即版权红线须改写);拿不到的数据(评分/年份)据实留空,不制造假精度。`evidence_level` 只表示原书转述忠实度,**不得当作科学有效性**。**高后果书事实抽检(`stakes=high`)**:育儿 / 医疗 / 理财 / 法律等读者会照着做、数字错会误导的书(判定见 `method.md §1.5`),蒸完须**人工回原书抽检 ≥5 条可执行数字 / 月龄 / 剂量 / 时长 + 金句**,确认所标 `anchor` 指向处确有其文、数值未被记串。抽出错即回改或降 `evidence_level`;这类可执行数字还须逐条标 `certainty`(见 §4.5.16/G22)。心理学书另逐 claim 做外部科学证据核查(见 enrich §1.1/G24)。
- **破折号一律 `--`**:所有给读者看的文字里用两个英文连字符,禁全角 `——`。
- **底部「回原书」声明**:页面底部固定 AI 拆书当地图、别当目的地的收口声明(骨架已带,别删)。
- **上站 = 有静态入口 + 有 SEO 头,少一样等于没上站**(2026-08-14 实证,代价:一批蒸馏页零收录):
  - **静态入口**:新蒸的书必须能从某个目录/书单页用**静态 `<a href>`** 点到。判据是 HTML 里那条边 ——
    搜索引擎只认它,**JS 运行时才渲染出来的导航对爬虫完全不存在**。只把 HTML 丢进静态目录、
    只登记进索引 JSON、只提交 sitemap,**都不算**:实测这样的页面会被判「已发现 - 尚未编入索引」,
    一篇都不收。而它毫无症状 —— 页面能开、构建不报错、索引也登记了。
  - **SEO 头**:蒸馏产出的独立 HTML 往往只有 `<title>`。上站前补 `description` / `canonical` /
    `og:*`,用**幂等脚本批量注入**(读书目 JSON 取书名作者简介封面),别手改一百个文件。
  - **URL 一致**:目录页链 `/x/` 而 sitemap 提交 `/x/index.html`,同一篇会以两个 URL 进索引。
  - 数量一多就该建**从数据真源自动生成的目录页**:内容增删自动跟随,不需要谁回头维护清单。

## 批量模式(蒸多本)

> **成本大头在编排层,不在 Pass2 分块数**:逐章命名 ≠ 逐章派 agent,各 subagent 仍守「≤5 章/组」,砍分块数省不到 token 且掉详实度。真正吃 token/时长的四项:①并发撞 529 风暴 ②会话碎片化 re-grounding ③同作者重复联网 ④失败假重跑。以下按此立规,**优化编排、不砍生成深度**。

- **先抽样 1 本人工验收再铺量**:多本任务先完整跑通 1 本(Step0-7 + 浏览器过一遍),你/审校者确认质量与 signature 成立,**通过才铺其余**;通过后**错峰**铺,不齐发。
- **上站前必过批量交付闸**(见硬门禁④):`verify_batch.py --slugs <预期名单>` exit 0 才许上站；心理学批次追加 `--require-domain psychology`。**预期名单必须显式声明**,靠人肉数「应该都蒸完了吧」正是 2026-07-26 漏掉 2 本仍上站的病因。
- **跨会话并发闸**:**全局在飞的 Pass2 subagent ≤ 6-8 个**,不论开了几个会话 / 几个作者批次并行。**多作者批次禁同时段并跑 Pass2** —— 多作者通宵并发会直接引爆服务端 529 风暴(大量 agent 撞 529、大量 retry、墙钟拖到 8-9 小时)。批次之间**错峰发起**,别十分钟内齐发。
- **1 本书 = 1 会话(或每会话 ≤2-3 本)**:避免单会话塞多本反复 compact(实测单会话曾 compact 8 次)。会话续接**只重读小的 `distill.json` checkpoint,禁重读 `book.txt` 全文**(实测 book.txt 曾被重复引用 60-198 次/会话)。
- **批前估 token 预算**:铺量前粗估「N 本 × 每本约 X = 总量」,对照账户周/日用量上限;超则分日/分批跑,**预留撞用量上限的余量**(实测批量铺量曾把账户用量跑爆、被迫中途暂停)。全程用高能力模型、不做 token 节流仍成立,但要预判总量别中途断粮。
- **失败先核盘再重派(防假重跑)**:agent 报「失败」多为已写盘、只是返回元数据时被限流。重派任何失败 agent 前,**先查 `$DATA\{书目录}\` 下 `_pass2_g*.json` / 产物是否已落盘**:已落盘只对缺章做**定点 gap-fill,禁整组重跑**。fan-out 合并后断言「N 章 narrative 全齐且达标」,只补真缺口(见 `method.md §3.5.5` 合并完整性门禁)。
- **Pass2 产物统一命名 `_pass2_gN.json` + 合并后清理**:并发多会话易各自即兴命名(曾并存 `_ch_N`/`_pass2_N`/`_pass2_gN`/`_pass2_batchX` 四套),漂移致合并对不齐、掉章。**统一只用 `_pass2_gN.json`**;**合并完整性门禁通过后,主控删本书 `_pass2_g*.json` 中间态**(已 gitignore、已回填 distill,别留到入库/聚合污染目录 -- 2026-07-15 复盘 13 本睡眠书 7 本残留)。见 `method.md §3.5.5` 清理步。
- **同作者 enrich 只搜一次**:批量拆同一作者多本时,作者研究(author_page)**一位作者只联网搜一次**,写 `$DATA\authors\{author_slug}\author.enrich.json`,各书 enrich 的 author_page **引用它、不重搜**(否则同一作者多本各自重搜作者背景 = 大量冗余联网轮次);与 StepA 作者演变聚合页共用同一份作者研究(见 `enrich.md §3` + StepA)。
- **索引串行登记**:Step4 的 `update_index.py register` 会写同一个 `knowledge-index.json`,批量时**串行**登记(逐本 dry-run→真跑),避免并发写盘互相覆盖;每次写前自动 `.bak`。

## 环境依赖

- Python:`pip install ebooklib beautifulsoup4 pymupdf pillow pytest playwright` + `playwright install chromium`(Step7 需 chromium;`pillow` 用于真封面 / 缩略图的压缩与 base64 内联)。
- azw3 / mobi 输入需 calibre 的 `ebook-convert`(`winget install calibre.calibre`);epub/pdf/txt 不需要。
- **视频系列**(取材 cascade 见 `method.md §V.0`):`yt-dlp`(YouTube 抓字幕 + 抓评论;B站评论走公开 API 免依赖)。B站/抖音的转写需一个字幕/ASR 上游工具(如 `video-to-subtitle-summary`,读其 `AI_DOUYIN_API_KEY`);fetch_comments 的 B站评论无需 key。**无字幕 / 需画面语义**走一个 Gemini 视频分析工具,如独立公开 skill [`sansheng-gemini-video`](https://github.com/sanshengai/sansheng-gemini-video)(读 env `GOOGLE_API_KEY`),装上即可;不装不影响书籍蒸馏与有字幕视频。

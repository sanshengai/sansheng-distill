# 参考文件导航与经验维护

只在寻找下一阶段细则或沉淀经验时读取。本表是导航，不是开工阅读清单。先选 SKILL.md 的一路，再按标题定位必要段；schema、模板与脚本需要使用时直接调用，不当成默认上下文。

## 1. 路线 → 当前阶段

| 路线 | 当前阶段 → 读取 |
|---|---|
| book-reader | 开工/写作/审阅：reader-edition-books.md §1–§2；科学范围：§3；预算/交付：§4；页面校验：§5；历史参数仅同类生产优化时读 §7 |
| book-strict | 开工与来源：high-retention-books.md §0；知识分母：§1–§4；阅读装配：§5；变更审阅与签署：§6.1–§6.2；历史异常仅命中时读 §6.2a–§6.7；不要把严格路线的分母步骤追加到 reader |
| book-guide | pipeline-steps.md 当前行；method.md §1 书型、§2–§5 生产、§6 schema、§7 门禁；pipeline-rules.md 对应规则 |
| video-series | pipeline-steps.md Step0-V；method.md §V；转写合格后才进入作品生产；enrich.md §V / html-spec.md §V 仅增补/页面时读 |
| creator_corpus | creator-craft.md §0–§3 范围/采集/来源卡；§4–§5 综合；§6–§7 核验与可读性；逐条深读或消费者需要深读包才读 §5.5；网站数据/页面终点才读 §8–§11 |
| biography_corpus | biography-craft.md §0–§1 叙事/证据；新建 store 才读 §2–§3；观察与入库 §4–§6；核验 §7；出厂 §8–§9/§11；写宿主适配器才读 §10 |
| person-topic | person-topics.md，再按思想/史实读取对应路线的小节；不启动全量采集 |
| aggregate-author | aggregation-steps.md StepA；author-craft.md §1–§3 输入/构建、§4–§5 视图、§6 需要外部研究时读 |
| aggregate-topic | aggregation-steps.md StepB；topic-craft.md §1–§3 输入/构建、§4–§5 比较视图、§6 需要外部争议时读 |
| category-map | category-framework.md；不把当前书单当完整学科，不自动蒸新书 |
| subject-curriculum | subject-curriculum.md；先盘点公认分法、给对比由用户选骨架，再分站、学派与内容件，改写后必做独立事实复核 |

## 2. 条件资源

| 触发条件 | 资源与用途 |
|---|---|
| 落盘/缺依赖 | workspace-layout.md：变量、布局、按需依赖 |
| 心理学/科学支持声明 | enrich.md §1.1、source-audit.md：来源主张与科学裁决分层；reader 同时读其 §3/§5，不擅自删科学检查 |
| 普通外部增补 | enrich.md 当前字段/搜索段；可选块无可靠来源据实置 null |
| 正式旧书替换 | redistillation.md：整包版本、索引撤销/替换、科学终审 |
| 跨书索引 | cross-book.md §2–§3；先 dry-run，串行写共享索引 |
| 多书/多进程/成本 | book-batch-operations.md：真实车道、依赖回执、背压与计时 |
| 管理类仍有分母的旧生产线提效 | efficient-book-distillation.md；不能和 reader 重叠抽样/签署 |
| 制作书/视频 HTML | html-spec.md §1/§3 当前槽位与验收；design-craft.md、brand-tokens.md 按设计阶段读；模板直接复制，不全文加载进提示 |
| 轻量模型执行导读/视频 | flash-mode.md：仅已选流程的执行卡 |

## 3. 经验如何归位

先判断经验能改变哪项决定，再修唯一权威位置：

- 误识别对象、范围扩张、默认档位冲突 → SKILL.md 路由/默认。
- 某路线阶段返工或停不下来 → 对应 reference 的当前阶段，不追加到入口尾部。
- 输入形状、哈希、退出码、空输入问题 → 脚本及能失败的测试；reference 只说明适用契约。
- 单本书/单个人物的底本疑点、实例、临时并发和账户 → 项目资料与状态，不升级为所有任务规则。
- 可复用来源/作者研究 → 数据资产及版本记录；不把正文和生产回执复制进指令。

新经验先找已有段和调用者，优先合并/替换旧规则，删除同义重复；阶段参数留真实项目配置。更新质量档位时同时核入口、路线首段、实际验证器和 README，禁止旧默认在另一份参考里继续生效。

复核至少覆盖真实正例和容易混淆的反例：人物传记单书 vs 生平库、个人专题 vs 全量思想、已蒸聚合 vs 新采集、心理学 reader vs 管理书提效。闸门改动增加真实失败输入与变异证明；有独立复核收益时才委派只读试跑。不因“进一步完善”无限增加审阅轮次。

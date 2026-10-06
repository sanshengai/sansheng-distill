---
name: sansheng-distill
description: 蒸馏工艺：将书籍、单集或系列视频、创作者作品、人物生平或人物专题蒸馏成有来源的可读资料；也处理已蒸书库的作者、问题专题、类别聚合与学科化结构。只产出中间资料与本地书页，放进哪个产品板块、做成什么产品页面由调用它的产品能力决定。企业研究交给企业研究能力，本 Skill 承接其中的书籍/人物资料子任务。只要字幕摘要、普通单篇文章或页面工程时不触发。
---

# 蒸馏：识别对象，按需加载，复用已有成果

交付忠实、可回查的阅读资料与结构化数据。本 Skill 是工艺层：被产品能力调用时，产品归属、板块位置与产品页面标准以调用方为准，这里不替它决定。默认效率优先：一条生产路线、一套权威正文、有限审阅、定点修复；不为凑流程重蒸。书页、人物库、专题资料的格式由所选路线和实际消费者决定。

## 1. 先识别本轮任务

从用户意图与已有材料判断三个维度，简短记录即可，不另造通用 JSON：

- **对象**：单部作品 / 创作者思想 / 人物生平事实 / 企业 / 已蒸书库。
- **范围**：全书或全生涯 / 明确专题或时段 / 单集或系列 / 已有成果的局部更新。
- **终点**：资料或数据 / 本地页面 / 已授权的产品交付。讨论、体检、查错只做到本轮终点。

分析目的先于媒介和学科：一本人物传记作为独立书蒸馏仍是书籍；多本传记用来复原生平才是人物库；管理学/心理学是书籍的领域附加规则，不是重复的主流程。已有数据优先增量复用。只有关键意图无法从上下文推断且会显著扩大工作时才问；范围、样式等低风险缺项用现有约定。

| 意图 / 识别线索 | 主路线 | 首次只读 |
|---|---|---|
| “蒸馏这本书”，保留全书主要论证 | **book-reader**：普通新书默认完整读者版 | [reader-edition-books.md](references/reader-edition-books.md) §1–§2；后续按阶段读 |
| 明确逐项审计、严格深读、精确覆盖；现有严格书续跑 | **book-strict**：严格知识分母与签署 | 新任务读 [high-retention-books.md](references/high-retention-books.md) §0；续跑先读当前阶段与 §6 变更契约 |
| 明确只要导读、概览、低成本浏览页 | **book-guide**：导读主管线 | [pipeline-steps.md](references/pipeline-steps.md) 对应行 + [pipeline-rules.md](references/pipeline-rules.md) 适用门 |
| 单个视频、播放列表、课程合集，目标是这些作品的内容 | **video-series**：单集是单成员系列 | pipeline-steps.md 的 Step0-V；[method.md](references/method.md) §V.0 |
| 博主/思想家的作品体系、全部输出、思想演变 | **creator_corpus**：跨媒介观点族 | [creator-craft.md](references/creator-craft.md) §0–§3 |
| 生平、人生经历、关系、历史事件、引语证据库 | **biography_corpus**：生平叙事与证据 | [biography-craft.md](references/biography-craft.md) §0–§1 |
| 某人的“领导力/教育思想”等专题、某一时段或问题 | **person-topic**：限定范围，区分思想与史实 | [person-topics.md](references/person-topics.md)；不自动采集全人生/全部作品 |
| 已蒸同作者 ≥2 本的思想演变；同问题 比较（正式主题页须 ≥3 本；两书可交比较资料） | **aggregate-author / aggregate-topic**：只聚合已有资料 | [aggregation-steps.md](references/aggregation-steps.md) 对应 StepA 或 StepB |
| 心理学/管理学等类别全景、书目与空白 | **category-map**：类别导航 | [category-framework.md](references/category-framework.md) |
| 把某个领域的已蒸书库做成一门能学完的学科（总览、分站、学派、学习顺序、关键想法、争论） | **subject-curriculum**：学科化，先给几种分法对比由用户选骨架；只管结构与内容，页面标准归产品能力；单书、人物、创作者不走这里 | [subject-curriculum.md](references/subject-curriculum.md) 开头边界 + §1 |
| 企业档案、经营机制、财务、控制权或企业现状 | **企业研究**主导；子任务分别返回上述路线 | 当前环境有 `sandy-firms` 时转企业研究入口；没有时按其已有项目契约处理，不冒充本 Skill 能独立完成企业研究 |

“蒸馏这个人”先看目标是思想还是人生；目标未明且缺上下文时再澄清。“人物专题”优先于“人物全量”，“已蒸聚合”优先于“从零采集”。不因作者身份自动创建人物库。

人物全传默认以出版传记为依据，保留连续故事并融合补充材料的独有细节；不设默认硬性字数配额。稿件阅读检查遗漏、重复、无据增写和接续，普通出版事实不逐条外查；篇幅要求与补查边界按 biography-craft.md §0 执行。
网页人物传记交付同时按 biography-craft.md §0.5 准备头像、逐章开篇图、主题曲和统一排版；只交稿或资料不触发这些产品配套。

## 书籍复审范围门（派任务前必过）

**蒸馏不是替原书做学术审计。原书的事实、案例与作者判断默认接受为来源，不逐条外查真假；检查的是“有没有忠实、完整地讲清原书”。** 不因育儿、心理学、年代久远或模型声称“可能误读”自动扩成事实审判。原文没给研究设计、页码或提名机构，不构成蒸馏缺陷；不为每句作者主张追加免责声明。

只开放两类书外补查：①已有具体变化线索的过时内容，附原书位置、变化理由及当前资料，保留作者原意，另作简短更新；②用户明确授权的具体外查对象。书龄10年/20年本身不证明过时。不把普通书升级为研究项目。独立新写的学科总览/站故事、明确承诺科学支持的证据卡和当前医疗等操作指导，按各自契约核自己新增的主张，不能反向要求全书事实重证；已有消费者需证据卡时明确适配，不能伪签科学通过。

**执行入口**：每次派书籍写作/复审任务前，以及接收拟采用意见后，必须运行 `python3 scripts/verify_book_review_scope.py <范围.json>`；失败不派发、不进入修订队列。范围为 `schema: book-review-scope-v1`、`book_facts: accept_as_source`、`exceptions: []`、非空 `items`；每项含唯一id与kind。默认kind仅 `source_fidelity/material_omission/author_attribution/unsupported_addition`；`style` 必须 `blocking:false`。`dated_update/external_truth_check` 必须引用对应例外id，例外必含具体claim及source_location，前者另含change_reason/current_source，后者另含user_authorization。任务文字须明确上述禁区；校验器不理解自然语言，不以PASS代替主控判别。

**用户明确取消内容审核时**：停止全部书本内容审阅任务，包括名为来源忠实度的整轮复审；并行仅做生产。只修明确的缺章、坏文件、图片错位和页面功能问题。书页采用 `reader-production-v1` 制作记录，填写用户指令、来源/正文哈希与实际装配检查，`content_review_performed:false`，不得伪填 `fidelity:reviewed` 或语义覆盖签收。该记录表示生产交付，不表示内容或科学审核通过。已有审阅不重跑。本规则优先于路线参考里的默认审核步骤。

新书审阅收据用 `reader-review-v2`，内嵌通过校验的 `review_scope`，由实际书页验收调用同一范围门；`reader-review-v1` 仅兼容已存在旧收据，新任务不得生成v1逃过范围门。默认一次有效审阅、一次定点修正；误报、次要措辞与忠实原书但未经外查的记载，不能作为新一轮审核触发条件。

## 2. 渐进式披露与效率默认

1. **选一路**：读取上表命中的首读资料；严格深读、读者版、导读三者互斥。本次普通书效率默认已经成立，无需逐书重新申请；明确档位与现有在制书契约优先。
2. **选当前阶段**：先定位相关标题/字段，再读对应段；长文不整份灌入。各阶段条件导航见 [reference-map.md](references/reference-map.md)，只在查找资源时打开。
3. **复用与停止**：相同来源、正文和依赖版本的有效证据直接复用。一轮有效审核后只修实质错误并复核变化；发现系统性错误才扩大审查。预算未知不编数字，成本记录和批量调度仅在需要时读 [book-batch-operations.md](references/book-batch-operations.md)。
4. **附加规则按条件加载**：心理学科学支持另读 [enrich.md](references/enrich.md) §1.1 和 [source-audit.md](references/source-audit.md)，读者版再读其 §3/§5；替换正式旧书读 [redistillation.md](references/redistillation.md)；仍有知识分母的管理流水线要提效才读 [efficient-book-distillation.md](references/efficient-book-distillation.md)。
5. **到消费者才验收**：只有制作页面才加载 HTML/设计/品牌参考；只有批量页面交付才跑批量验收。只交资料不强制造 HTML、10 份网站 JSON 或推广文章。实现尚不支持目标格式时做明确适配并验证，不伪造旧契约回执。

模型能力不决定档位。轻量模型需要执行卡时读 [flash-mode.md](references/flash-mode.md)，仅用于导读/视频的相关步骤；模型、并发与子 Agent 由真实环境和任务收益决定，不固定某供应商，也不默认每阶段新开 Agent。

## 3. 共用底线与完成定义

- 来源缺页、乱码、章界不清或关键转写不可用，先修来源；不凭记忆编补。区分原书观点、编辑推断、外部事实与当前科学裁决。
- 保留主论证、关键案例、反例、条件和实质图表。效率取舍可省重复审阅与次要例子，不能省核心意思、真实归属、关键数字和必要图意。
- 引文回源，外部信息带真实出处；版本变化使受影响审据失效。未外查记未外查，估计不冒称逐项覆盖，机械通过不冒称语义或科学正确。
- 精确机器契约以实际 schema、校验器与消费者为准。规则分工：本文负责路由与默认；路线参考负责流程；脚本负责其实际检查范围。冲突先查输入与实现，不降阈值、不删除检查凑绿。
- 交付报告实际范围、采用路线、验证结果、关键缺口。页面交付需实际页面及必要截图验收；上线须既有授权和真实发布成功，数据完成不等于上线。

「一页课桌」产品规则由 `sandy-yiye` 承接，站点工程与发布由 `sandy-website` 承接；本 Skill 交付公共资料与证据。没有这些能力的环境沿当前项目契约，不自动新增产品或外发。

落盘时才读 [workspace-layout.md](references/workspace-layout.md) 获取变量、数据布局和按需依赖；命令使用实际目录与 `python3`，读取原命令退出码。

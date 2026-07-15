# Changelog

本项目的变更记录。版本号遵循 [semver](https://semver.org/lang/zh-CN/)。

## [未发布]

## [0.3.0] -- 2026-07-15

给「读者会照着做」的高后果书（育儿 / 医疗 / 理财…）加一层**数字可信度标注**，并把蒸馏产物的清理与验证边界写清楚。缘起是一次婴幼儿睡眠 13 本蒸馏 → 合成专题文的复盘：蒸馏本身很忠实，但下游引用时分不清哪些数字是「书里白纸黑字」、哪些是「编者补的通识」。

**新增**
- **后果轴 `stakes`（`high` / `normal`）**：与书型 / render_profile 正交的第三根轴，标记「读者照做、数字错会误导」的高后果书（育儿 / 医疗 / 用药 / 投资仓位 / 法律…）。缺省 `normal`，旧蒸馏无需回填。
- **可执行数字确定性 `certainty`**：`decision_rules[]` 与 `core_ideas[]` 元素级新字段，三值 `book_explicit`（书里白纸黑字）/ `cross_book_synthesis`（跨书合成）/ `general_knowledge`（编者通识），让下游一眼分清数字来源硬度；与 `evidence_level`（转述忠实度）正交共存。
- **门禁 G22**：`stakes=high` 时 `decision_rules` / `core_ideas` 每条必带合法 `certainty`（独立 stakes 闸，不随 render_profile；`normal` 书不检）。渲染侧复用 `.ci-evlevel` 色点，为决策卡加 `.rc-certainty` 来源硬度徽标。
- **G7 `evidence_level` 机检补齐**：`core_ideas` 必带 `evidence_level` 从「蒸馏自查」升为「verify 机检」。

**改进**
- **Pass2 中间态自动清理**：合并完整性门禁通过后删 `_pass2_g*.json`（已 gitignore、已回填 distill），治历史残留污染目录。
- **verify 边界澄清**：文档写清 `verify_page.py exit 0 ≠ 事实正确` -- 只保结构 / 契约 / 版权长度；内容真伪靠蒸馏自查 + 高后果书人工回原书抽检数字。

**修复**
- SKILL.md 硬门禁②的门禁编号从陈旧的 G1-G15 校正到 G1-G22。

## [0.2.0] -- 2026-07-12

这一版让蒸馏**按书型走不同形态**，并把批量蒸馏的成本压在编排上、而非砍内容深度。

**新增**
- **书型自适应 render_profile**：8 种书型原型（论说 / 叙事 / 人物 / 工具 / 语录 / 书单 / 课程 / 考试），按书型自动选输出形态与门禁档位 -- 语录书走语录墙、书单书走书单卡、课程 / 考试书走知识点树 + 考点卡，不再对所有书死搬同一套五段式。**向后兼容**：未标注书型的旧蒸馏页按原全门禁校验，无需重蒸。
- **4 类新原型页面原语**：语录墙 `.quote-board`、书单卡 `.booklist-cards`、知识点树 `.kp-tree`、考点卡 / 例题解析 / 记忆卡（`.exam-point` / `.worked-example` / `.recall-card`）。
- **门禁 Tier-0 / Tier-1 分层**：底线门禁（锚点 / 零外链 / 出处常显…）永不放宽；形态门禁（字数档 / 书魂 / 行动链…）随书型注册表变。verify 加书型完整性校验，防「自造书型 / 篡改 active_gates 偷绕门禁」。
- **批量编排效率规约**：跨会话并发闸（全局在飞 Pass2 subagent ≤ 6-8）、1 本书 = 1 会话防反复 compact、批前 token 预算、失败先核盘再定点 gap-fill（防假重跑）、Pass2 产物统一 `_pass2_gN.json` 命名、同作者 enrich 只搜一次。
- **Pass1 独立门禁** `verify_pass1.py`：骨架阶段即校验，UTF-8 控制台守卫修 GBK 假失败。
- **作者演变辅助脚本** `merge_enrich.py` / `merge_pass2.py`（数据根目录走 `DISTILL_DATA_DIR`）。

**修复**
- 兄弟 skill `sansheng-gemini-video` 链接改为完整 GitHub URL（独立扁平仓不再用 monorepo 相对路径）。
- 测试骨架路径按扁平仓结构修正（`parents[2] / templates`），clean-env pytest 全绿（208 passed）。

## [0.1.0] -- 2026-07-08

把一本书蒸成一张**能点、能跳、越读越厚**的交互网页 -- 脑图可点跳、章节可展开、7 主题切换、读完回看的自检问句，单文件 `file://` 直接打开。

**这一版包含：**
- 八步蒸馏管线：入书诊断 → 书型判定 → 四源融合蒸馏 → 联网增补 → 跨书索引 → 设计两遍工作法 → 单文件 HTML → 出厂验证
- 两类输入：书籍电子全文（epub / pdf / txt / azw3 / mobi），以及视频系列（每集当章节）
- 跨书概念索引：越蒸越厚的个人知识网络，新书自动与旧书互链
- 产出为零外链单文件 HTML，可离线 `file://` 打开

装法与网页演示见 README。这是叁笙自己每天在用、清洗脱敏后开源的 Claude Code 技能。

[0.3.0]: https://github.com/sandypoli-boop/sansheng-distill/releases/tag/v0.3.0
[0.1.0]: https://github.com/sandypoli-boop/sansheng-distill/releases/tag/v0.1.0

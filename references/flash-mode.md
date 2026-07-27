# flash-mode -- 轻量模型 / 弱 agent 执行卡

> **谁该读这份**:用 Gemini Flash 级轻量模型、或 agent 编排能力较弱的客户端(如 Antigravity)跑本 skill 时,**先读本卡再读 SKILL.md**。
> 用 Opus / Sonnet 级模型跑的,不必读本卡,照 SKILL.md 主管线走即可。
>
> **本卡不降低任何质量标准**,只做三件事:①把「靠自觉」的环节换成「可自检的判据」;②把长链条拆成带完成凭证的短步;③把最容易滑落的六个点单独拎出来钉死。

---

## 0. 为什么有这份卡(2026-07-26 实测事故)

一次用 Antigravity(Gemini 3.6 Flash)蒸 6 本书,5 分钟跑完、全部上站,事后核查:

| 实际发生 | 本该如何 |
|---|---|
| 6 本里 **2 本只跑到 Step0** 就停了,但仍被挂上作品集页 | 少蒸的书不许进上站名单(线上直接 404) |
| 4 本 HTML 各残留 **68 处 `{{槽}}` + 39 处 dummy** | Step6 要求「删干净 dummy」 |
| 封面全是**占位 SVG** | 铁律「真封面」要求真书影 base64 |
| distill.json 缺 **8 个顶层键** | method.md §6 schema 是硬契约 |
| 每章 narrative **213-465 字**(1 本达标) | G9 下限 800 字 |
| 章数一律压成 **6 章** | 章数跟原书目录走,禁归并 |
| **Step7 一次都没跑** | 硬门禁③:exit 0 才算完成 |

**注意最后一行 -- 这是总病根。** 上面每一条,Step7 跑一次都会当场报出来。
所以本卡的第一原则是:**宁可少蒸一本,也不许跳一次验证**。

---

## 1. 开工前提(不满足就别开始)

### 1.1 一本书 = 一个独立电子书文件

**禁用「套装合集」epub 切书。** 上述事故里 6 本全部切自同一个「经典系列(套装共5册)」epub,
`diagnose.json` 因此报 `toc_detected: false, chapters_detected: 1` --
**模型手里根本没有目录结构,只能自由发挥,这就是「章数一律 6 章」的直接来源。**

开工前先看 `diagnose.json`:

```
toc_detected: true   → 正常开工
toc_detected: false  → 停下。换单本电子书文件,或人工确认章节划分后再走 Step1
```

### 1.2 一本书 = 一个会话

多本塞一个会话会反复 compact 丢上下文。轻量模型尤其扛不住,**一本一会话**。

---

## 2. 逐步执行卡(每步都有完成判据)

> 每步做完先自问「判据满足了吗」,不满足**不许进下一步**。判据是可核对的事实,不是感觉。

### Step0 · 转 txt + 入书诊断

```bash
python $SKILL/scripts/convert_book.py "<书文件>" --outdir "$DATA/{slug}"
```

**判据**:`book.txt` 与 `diagnose.json` 都已落盘 且 `toc_detected: true` 且 exit 0。
exit 3(需 OCR / 需人工确认)→ **停下问用户**,不硬读、不编内容。

### Step1 · 书型判定 + render_profile

读 `diagnose.json` + 抽样首/中/末章,判 `book_type`,产 `render_profile`(见 method.md §1.4)、`stakes`(§1.5)。

**判据**:能说出这本书属 论说/叙事/人物/工具 中哪一型、依据是哪一段。

### Step2 Pass1 · 压缩骨架

按 method.md §3-§5 产 `distill.json` 骨架层(除 `narrative`/`excerpts`/`action_chain[].detail`)。

**判据 -- 用命令核,别靠印象**:

```bash
python $SKILL/scripts/verify_pass1.py "$DATA/{slug}/distill.json"; echo "退出码=$?"
```

退出码 0 才算 Pass1 完成。**这一步最容易少产字段**,门禁会逐个点名缺了哪个。必产的 21 个顶层键:

```
slug  title  author  book_type  render_profile  napkin  core_question
cover_intro  chapters  core_ideas  arguments  decision_rules  mental_models
tensions  critique  credibility_verdict  quotes  concepts  soul_module
action_chain  self_check
```

另有 `stakes`(高后果轴,缺省 normal)与 `pub_year`(作者演变页排序轴)**建议一并产**,门禁不拦。

⚠️ 键名以 method.md §6 为准。**别自造近义名**(实测出现过把 `title` 写成 `book_title`)。
⚠️ `"quotes": []` 这种空数组**等同没产**,门禁按缺失处理。

### Step2 Pass2 · 逐章详实转述

**章数 = 原书实际章数,禁归并。** 一本 15 章的书就产 15 章,不许压成 6 章"概括一下"。

逐章写 `narrative`:先读 Pass1 骨架保结构,再**回 `book.txt` grep 该章原文**取案例/数字/原话。

**判据**:每章 `narrative` ≥ 800 字(视频段 ≥400),且每章 ≥1 条 `excerpts`(原文照录 ≤150 字)。

```bash
# 自检:逐章字数一次看清
python -c "import json;d=json.load(open(r'$DATA/{slug}/distill.json',encoding='utf-8'));\
print([(c.get('no'),len(c.get('narrative','') or '')) for c in d['chapters']])"
```

⚠️ **grep 不到支撑就降级不写那一点,禁凭印象编案例、编数字。**
⚠️ 标志性案例必须整段完整讲(时间·人物·动作·转折·结果),不许压成一句标签。

### Step3 · 联网增补

三张子视图各起一轮搜索(作者页 / 同类书页 / 观点对比页)+ `reviews` + `cross_book_external`,全带来源 URL。

**判据**:`enrich.json` 已落盘,五个顶层键都在(整块抓不到的置 `null`,**但文件必须有**)。
参考量级:正常一本 19-34 KB;**产出不足 5 KB 基本等于没搜**,回去补。

### Step4 · 跨书索引登记

```bash
python $SKILL/scripts/update_index.py query --index "$DATA/knowledge-index.json" --names-only
# 写 index-merge.json 后:
python $SKILL/scripts/update_index.py register --index "$DATA/knowledge-index.json" \
  --merge "$DATA/{slug}/index-merge.json" --dry-run
```

**判据**:dry-run exit 0 后再去掉 `--dry-run` 真跑。
⚠️ `index-merge.json` 必须由 `distill.concepts` 支撑 -- **没产 concepts 就不许登记**,否则污染全库共享索引。
⚠️ **禁用 `--force` 绕 exit 1。**

### Step5-6 · 设计 + 生成 HTML

复制 `$SKILL/templates/page-skeleton.html` 到 `$DATA/{slug}/{slug}.html`,逐槽填充。

**判据 -- 这一步的头号事故点,填完立刻自检**:

```bash
# 必须两个都输出 0
grep -o '{{[^}]*}}' "$DATA/{slug}/{slug}.html" | wc -l
grep -oi 'dummy' "$DATA/{slug}/{slug}.html" | wc -l
```

**骨架里有 177 个 `{{槽}}` 和 129 处 dummy 示例文案 -- 全部都要处理掉**:
有数据的填真值,**整块降级的连区块一起删**(不是留着空槽)。

封面必须是**真封面 base64**(`data:image/jpeg` 或 `png`/`webp`)。
占位 SVG 不算数;确实联网拿不到,才在 `distill.json` 顶层显式写 `"cover_fallback": true`。

### Step7 · 出厂验证(不许跳)

```bash
python $SKILL/scripts/verify_page.py "$DATA/{slug}/{slug}.html" \
  --distill "$DATA/{slug}/distill.json" --screenshot "$DATA/{slug}/_verify.png"
echo "退出码=$?"
```

**判据:退出码 0。非 0 就不是成品。**

⚠️ 别用 `| head` / `| tail` 取摘要 -- 管道退出码取最后一段,`head` 永远成功,**会把失败吞掉**。
⚠️ **绝不放宽阈值、绝不删检查项来「过关」。** 报什么就修什么,修完重跑。

---

## 3. 整批收口(上站前最后一道)

单本 verify 只回答「这一本合不合格」,回答不了「**这一批该有的都在吗**」。
上站前**必须**跑批量闸,把预期名单显式交给它核对:

```bash
python $SKILL/scripts/verify_batch.py --data-root "$DATA" \
  --slugs slug1,slug2,slug3,slug4
echo "退出码=$?"
```

**退出码 0 才允许上站。** 非 0 时二选一:补完管线,或**从上站名单里摘掉这本**。
名单留着而产物不存在 = 线上 404。

---

## 4. 六个最容易滑落的点(钉死)

| # | 滑落点 | 钉法 |
|---|---|---|
| 1 | 跳 Step7 直接交付 | 每本收工前必跑 verify_page,看退出码不看感觉 |
| 2 | 槽没填完就交付 | Step6 收尾 grep 两个计数,都必须是 0 |
| 3 | schema 少产字段 / 自造键名 | Pass1 后跑 verify_pass1.py;键名对照 method.md §6 |
| 4 | 章数归并成 5-6 章 | 章数跟原书目录走;`toc_detected: false` 先停 |
| 5 | narrative 写到 300 字就收 | 逐章核字数,<800 回去补,不许"精简一下"过关 |
| 6 | 少蒸的书仍进上站名单 | 上站前跑 verify_batch,预期名单显式声明 |

---

## 5. 三条不可协商的铁律

1. **不编造**:金句 / excerpts 原文照录不改写;grep 不到支撑就不写那一点;拿不到的数据据实留空,不制造假精度。
2. **不放宽门禁**:验证脚本报错就修数据,**永远不改脚本、不删检查项、不加 `--force` 绕过**。
3. **不带病上站**:任何一步的判据没满足,停下报告用户,不往下走。**少交付一本,好过交付一本坏的。**

> 高后果书(育儿 / 医疗 / 理财 / 法律,`stakes=high`)读者会照着做、数字错会误导 --
> **这类书不建议用轻量模型蒸**;确要蒸,蒸完须人工回原书抽检 ≥5 条可执行数字,verify 不做此核。

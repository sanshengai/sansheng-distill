# 心理学原文审计账本（psychology-source-audit-v1）

> 适用：`domain_profile.domain="psychology"` 的书。目的不是再写一份摘要，而是把
> `book.txt → distill.json → claim coverage → enrich.json` 锁成可复算的原文证据链。
> 普通书不产、不触发；已知心理学项目必须用 `--require-domain psychology` 验收。

## 1. 文件与生成时点

同一本书目录最终至少有：

```text
book.txt
distill.json
claim-coverage.json
enrich.json
source-audit.json
{slug}.html
```

`source-audit.json` 最后生成：Pass1/Pass2 已合并成最终 `distill.json`、claim coverage
已裁决、`enrich.evidence_page` 已定稿后，才计算四份输入的原始文件字节 SHA-256。
之后任一输入改变，旧账本立即失效，必须重生成；不要保存 `status:"PASS"`、覆盖率或错误数等
会陈旧的自报结论。

四个 `inputs.*.path` 只能是**同书目录的单个相对文件名**，禁止绝对路径、`..`、子目录与
跨目录软链接。标准命名中的连字符文件在 JSON 键里写 `claim_map`：

```json
{
  "schema_version": "psychology-source-audit-v1",
  "book_slug": "thinking-fast-and-slow",
  "inputs": {
    "source": {
      "path": "book.txt",
      "sha256": "64位小写十六进制",
      "line_count": 2643
    },
    "distill": {"path": "distill.json", "sha256": "64位小写十六进制"},
    "claim_map": {"path": "claim-coverage.json", "sha256": "64位小写十六进制"},
    "enrich": {"path": "enrich.json", "sha256": "64位小写十六进制"}
  },
  "segments": [],
  "records": []
}
```

`line_count` 按 UTF-8 文本 `splitlines()` 计；hash 按文件原始字节计，不按 JSON 语义归一化。

## 2. segments：先锁定整本书的章界

`segments` 按原文顺序连续覆盖 `L000001` 至末行，不许空洞、重叠或越界。枚举：

- `kind`: `frontmatter|chapter|backmatter`
- `line_range`: 固定 `L000001-L000123`
- `heading_excerpt`: 必须在该 segment 的**起始行**逐字命中
- `kind="chapter"` 时：`chapter_no` 为正整数，`id` 固定为 `ch01/ch02/...`；并与
  `distill.chapters[].no` 一一对应
- 非 chapter segment 不写 `chapter_no`

```json
{"id":"ch01","kind":"chapter","chapter_no":1,
 "line_range":"L000141-L000224","heading_excerpt":"第1章 一张愤怒的脸和一道乘法题"}
```

前言、目录、附录不能丢掉；用 frontmatter/backmatter segment 吃掉它们，整本 source 仍须连续。

## 3. records：每条最终陈述回到章内原文

```json
{
  "id": "claim:behavioral-social-priming:01",
  "target": {"kind": "claim", "id": "behavioral-social-priming"},
  "facet": "claim",
  "source_segment": "ch04",
  "line_range": "L000329-L000340",
  "source_excerpt": "不超过150字的逐字原文",
  "assertion": "最终产物中可逐字定位的陈述片段",
  "support": "direct"
}
```

字段契约：

- `id`：全局唯一、非空。
- `target.kind`：`claim|chapter_narrative|quote|excerpt|audit_flag`。
- `target.id` 稳定命名：claim 用最终 `claim_id`；narrative 用 `ch01`；quote 用 `q01`；
  excerpt 用 `ch01:e01`；audit flag 用 `{source_group}:{source_claim_id}`。
- `facet`：`claim|mechanism|case|experiment|number|boundary|verbatim`。
- `support`：`direct|partial|contradicted`。覆盖门只把 direct/partial 算作支撑。
- `source_segment` 必须存在；`line_range` 必须完全落在该 segment 内。
- `source_excerpt` 非空、去空白后 ≤150 字，并在该 `line_range` 内逐字命中。
- `assertion` 非空，是模型对该来源支撑关系的短述；不要求逐字包含在最终 claim/narrative 文案中，
  真实性由 `source_excerpt` 的确定性原文命中承担。

覆盖下限：

1. 每个最终 `core_ideas + decision_rules` claim 至少 1 条 direct/partial 记录，且至少一条来自
   该 claim `anchor` 的章。
2. 每章 narrative 至少 2 条 direct/partial 记录，且至少 2 个不同 facet；数字、案例、实验与
   边界分别记，不得用两条同义 `claim` 充数。
3. 每条最终 quote、每章每条 excerpt 恰有 1 条 `facet="verbatim",support="direct"` 记录；
   `source_excerpt` 与最终 `text`、已有 `line_range` 必须逐字一致，来源章必须对齐 anchor。
4. claim coverage 的每个 audit flag 恰有 1 条 `audit_flag` 记录，record `line_range` 与
   claim-map immutable range 完全相同。

## 4. claim coverage 与 evidence 对账

`claim-coverage.json` 使用：

```json
{
  "schema_version": "psychology-claim-coverage-v1",
  "book_slug": "thinking-fast-and-slow",
  "entries": [{
    "source_group": "g1",
    "source_claim_id": "ego-depletion-need-review",
    "line_range": "L000274-L000291",
    "reason": "为什么须进入外证审计",
    "disposition": "mapped",
    "final_claim_id": "ego-depletion-resource"
  }]
}
```

- `mapped` 的 `final_claim_id` 必须存在；`excluded` 时必须为 `null`。
- `mapped.final_claim_id` 必须属于最终 claims；允许多个待审计项合并到同一 final claim，也允许
  最终规则来自 Pass1 audit flags 之外。claim-map 要精确覆盖的是全部原始 audit flags，而不是
  反向覆盖全部最终 claims。
- `{source_group}:{source_claim_id}` 唯一，且与 source-audit 的 audit_flag targets 精确一一对应。
- `enrich.evidence_page.claims` 的键必须与最终 `core_ideas + decision_rules` claim_id 无多无少。
- claim-map 回答「Pass1 待审计项去了哪里」；evidence_page 回答「最终主张的外部科学状态」；
  两者不能互相顶替。

## 5. 验证

单独查账本：

```powershell
python $SKILL\scripts\validate_psychology_source_audit.py "$DATA\{书目录}\source-audit.json"
```

成品硬闸（会自动再次查账本并把四个 hash 与本次输入绑定）：

```powershell
python $SKILL\scripts\verify_page.py "$DATA\{书目录}\{slug}.html" `
  --distill "$DATA\{书目录}\distill.json" `
  --source "$DATA\{书目录}\book.txt" `
  --require-domain psychology
```

批量闸缺 `book.txt` 或 `source-audit.json` 会在调起单书验证前失败；默认不带
`--require-domain psychology` 时不查本契约，65 本旧书行为保持不变。

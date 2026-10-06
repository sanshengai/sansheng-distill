# 书籍派发入口：范围检查与实际提示一起执行

当项目用外部模型批量生产普通书时，先读本页。单一任务清单同时保存操作类型与执行契约；不另维护一份会漂移的“审核计划”。书籍任务用 `scripts/run_book_wave.py` 包装项目既有执行器，不直接把未经范围检查的任务交给模型。项目已有驱动时将同一 `compile_manifest` 接在请求前，不再串联一个重复模型车道。

这层检查发生在凭证读取和请求之前；默认 production_only。它拒绝空清单、遗漏契约、重复ID、无授权内容审阅、无具体例外的外查和没有明确缺陷的修复，并把实际禁区加入每个最终模型提示。它不理解所有自然语言，不能识破把审稿伪装成写作的所有语义越界；主控须如实标操作，不把结构PASS说成无误审阅或原书真实。

## 单一清单

```json
{
  "run_id": "book-batch-01",
  "book_contract": {
    "schema": "book-wave-contract-v1",
    "book_facts": "accept_as_source",
    "review_mode": "production_only",
    "exceptions": []
  },
  "jobs": [{
    "job_id": "book-a-ch01",
    "book_id": "book-a",
    "operation": "write",
    "task": "本章来源与完整写作任务；使用当前消费者字段。"
  }]
}
```

普通生产操作为 source_prepare/write/derive/render/functional_check；targeted_repair 必须给 `issue`（已经发现的具体制作问题）。content_review 仅在 review_mode=requested_review 且 `review_authorization` 记录用户明确要求和范围时允许，学科标签与旧模板不构成授权。

external_check 必须引用 `exception_id`：例外有 id/kind/claim/source_location；kind=dated_update 另有 change_reason/current_source，kind=authorized_external_check 另有 user_authorization。书龄不能替代具体变化线索。必要更新可在 production_only 中定项执行，不反向授权全书审核。

## 先本地校验，再一次实际派发

```sh
python3 scripts/run_book_wave.py --manifest /absolute/path/jobs.json --dry-run
python3 scripts/run_book_wave.py --manifest /absolute/path/jobs.json \
  --project-runner /absolute/path/project/run_coding_plan_wave.py \
  --output-dir /absolute/path/new-results --gateway coding \
  --model <用户或项目指定模型> --max-workers <实际可用并发>
```

输出、推理与超时参数按既有项目执行器传递；套餐、模型和并发必须显式指定。项目执行器仍负责真实全球槽位、认证、响应终态和模型漂移，包装层不复制这些能力。它目前适配 run_coding_plan_wave.py 的参数/输出格式；别的驱动先做真实最小适配，不声称通用支持。

实际调用保存 `book-wave-execution.json`，含清单哈希、执行契约、每个实际提示哈希及执行器退出码。用模型回执 task_sha256 对照这份记录；不能只写“已运行范围门”。结构通过不证明内容质量，执行器成功也不等于页面或官网完成。

失败只重试对应 job：`--job-ids book-a-ch01`，使用新输出目录；成功组和来源未变的已有成果复用。清单不得静默截断长来源。无新输入或新失败不再跑同一波来“更放心”。

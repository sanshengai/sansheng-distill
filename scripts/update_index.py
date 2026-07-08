#!/usr/bin/env python3
"""跨书知识索引维护:query 查询 / register 按 5-tag 协议合并(带防覆盖栏)。"""
import argparse, json, shutil, sys
from pathlib import Path

# CLI 输出契约为 UTF-8;Windows 下管道 stdout/stderr 默认走 locale(cp936)会把中文输出编成 GBK,
# 导致调用方按 UTF-8 解码崩溃,故启动即固定编码。
for _s in (sys.stdout, sys.stderr):
    if _s is not None and hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8")

RELATIONS = {"NEW_CONCEPT", "SUPPORTS", "REFINES", "CONTRADICTS", "NEW_SUB_ASPECT"}
SOURCE_TYPES = {"book", "video_series"}

def load_index(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "concepts": []}
    return json.loads(path.read_text(encoding="utf-8"))

def validate(index: dict, items: list) -> list:
    errors, existing = [], {c["concept"] for c in index["concepts"]}
    for i, it in enumerate(items):
        rel, name, e = it.get("relation"), it.get("concept"), it.get("entry", {})
        if rel not in RELATIONS:
            errors.append(f"[{i}] {name}: 非法 relation '{rel}',须为 {sorted(RELATIONS)}")
        if not name:
            errors.append(f"[{i}] 缺 concept")
        for k in ("book_slug", "book_title", "anchor"):
            if not e.get(k):
                errors.append(f"[{i}] {name}: entry 缺 {k}")
        st = e.get("source_type")
        if st is not None and st not in SOURCE_TYPES:
            errors.append(f"[{i}] {name}: 非法 source_type '{st}',须为 {sorted(SOURCE_TYPES)} 或省略")
        if rel == "NEW_CONCEPT" and name in existing:
            errors.append(f"[{i}] {name}: 标 NEW_CONCEPT 但索引已有同名概念")
        if rel in RELATIONS - {"NEW_CONCEPT"} and name not in existing:
            errors.append(f"[{i}] {name}: 标 {rel} 但索引没有该概念")
    return errors

def same_book_conflicts(index: dict, items: list) -> list:
    in_index = {e["book_slug"] for c in index["concepts"] for e in c["entries"]}
    merging = {it["entry"]["book_slug"] for it in items if it.get("entry")}
    return sorted(in_index & merging)

def apply(index: dict, items: list) -> dict:
    by_name = {c["concept"]: c for c in index["concepts"]}
    for it in items:
        entry = dict(it["entry"], relation=it["relation"])
        if it["relation"] == "NEW_CONCEPT":
            c = {"concept": it["concept"], "one_liner": it.get("one_liner", ""), "entries": [entry]}
            index["concepts"].append(c); by_name[it["concept"]] = c
        else:
            c = by_name[it["concept"]]
            c["entries"] = [e for e in c["entries"] if e["book_slug"] != entry["book_slug"]] + [entry]
    return index

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("query"); q.add_argument("--index", required=True)
    q.add_argument("--names-only", action="store_true")
    r = sub.add_parser("register"); r.add_argument("--index", required=True)
    r.add_argument("--merge", required=True)
    r.add_argument("--dry-run", action="store_true"); r.add_argument("--force", action="store_true")
    a = ap.parse_args()
    path = Path(a.index); index = load_index(path)
    if a.cmd == "query":
        out = [c["concept"] for c in index["concepts"]] if a.names_only else index
        print(json.dumps(out, ensure_ascii=False, indent=1)); return 0
    items = json.loads(Path(a.merge).read_text(encoding="utf-8"))
    errors = validate(index, items)
    if errors:
        print("\n".join(errors), file=sys.stderr); return 1
    conflicts = same_book_conflicts(index, items)
    if conflicts and not a.force:
        print(f"同书再登记(将覆盖旧条目): {conflicts} -- 确认重蒸请加 --force", file=sys.stderr); return 2
    if a.dry_run:
        print(f"dry-run 通过: {len(items)} 条待合并"); return 0
    if path.exists():
        shutil.copy2(path, str(path) + ".bak")
    result = apply(index, items)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"合并完成: {len(items)} 条, 现有概念 {len(result['concepts'])} 个"); return 0

if __name__ == "__main__":
    sys.exit(main())

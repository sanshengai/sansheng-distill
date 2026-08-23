#!/usr/bin/env python3
"""Initialize and verify biography corpus stores through one public CLI."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from biography_contract import (
    assert_store_ready,
    audit_corpus,
    audit_store,
    format_human_report,
    manifest_v2_skeleton,
    normalize_manifest,
    validate_schema_instance,
)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_empty_jsonl(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def _manifest_subject_id(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    subject = value.get("subject")
    if isinstance(subject, dict):
        subject_id = subject.get("subject_id")
    else:
        subject_id = value.get("subject_id")
    return subject_id if isinstance(subject_id, str) and subject_id else None


def _check_identity_scope(root: Path, slug: str, subject_id: str) -> None:
    for sibling in root.parent.iterdir() if root.parent.exists() else []:
        if sibling == root or not sibling.is_dir() or sibling.name.startswith("."):
            continue
        manifest_path = sibling / "manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError(f"无法核验同语料库身份：{manifest_path}: {error}") from error
        normalize_manifest(existing, root_name=sibling.name)
        if _manifest_subject_id(existing) == subject_id:
            raise ValueError(f"subject_id {subject_id!r} 已由 {sibling.name!r} 使用")
    if root.exists() and (root / "manifest.json").is_file():
        try:
            existing = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError(f"无法核验待替换 store 的稳定身份：{error}") from error
        normalize_manifest(existing, root_name=slug)
        existing_id = _manifest_subject_id(existing)
        if existing_id is None:
            raise ValueError("待替换 store 缺稳定 subject_id，拒绝自动覆盖")
        if existing_id != subject_id:
            raise ValueError(
                f"拒绝改变已有传主的稳定 subject_id：{existing_id!r} -> {subject_id!r}"
            )


def _populate_store(root: Path, manifest: dict[str, Any], args: argparse.Namespace) -> None:
    root.mkdir(parents=True)
    _write_json(root / "manifest.json", manifest)
    _write_json(
        root / "source-registry.json",
        {
            "schema_version": "biography-source-audit-v1",
            "registry_id": f"registry-{args.slug}",
            "subject_id": args.subject_id,
            "id_namespace": args.slug,
            "source_units": [],
        },
    )
    for ref in manifest["canonical"].values():
        _write_empty_jsonl(root / ref)
    for descriptor in manifest["governance"]["ledgers"]:
        _write_empty_jsonl(root / descriptor["ref"])
    editorial = {
        "chapter_order": {
            "schema_version": "biography-chapter-order-v1",
            "subject_id": args.subject_id,
            "order": [],
        },
        "chapters": {
            "schema_version": "biography-editorial-chapters-v1",
            "subject_id": args.subject_id,
            "chapters": [],
        },
        "overview": {
            "schema_version": "biography-editorial-overview-v1",
            "subject_id": args.subject_id,
            "core_facts": [],
            "blocks": [],
        },
        "layout": {
            "schema_version": "biography-layout-v1",
            "subject_id": args.subject_id,
        },
        "dossier": {
            "schema_version": "biography-dossier-config-v1",
            "subject_id": args.subject_id,
            "sections": [],
        },
        "media": {
            "schema_version": "biography-media-ledger-v1",
            "subject_id": args.subject_id,
            "assets": [],
            "selections": {},
        },
    }
    for kind, value in editorial.items():
        _write_json(root / manifest["editorial"][kind], value)


def _init(args: argparse.Namespace) -> int:
    root = Path(args.store_root).resolve()
    if root.name != args.slug:
        raise ValueError(f"store-root 目录名必须等于 slug：{root.name!r} != {args.slug!r}")
    manifest = manifest_v2_skeleton(
        args.slug,
        args.subject_id,
        args.catalog_name,
        language=args.language,
    )
    schema_errors = validate_schema_instance("ManifestV2", manifest)
    if schema_errors:
        raise ValueError("初始化参数不符合公共契约：" + "；".join(schema_errors[:5]))
    if root.exists() and not root.is_dir():
        raise ValueError(f"目标已存在但不是目录：{root}")
    backup = root.parent / f".{root.name}-replace-backup"
    if backup.exists():
        raise ValueError(f"检测到未收口替换备份，拒绝继续：{backup}")
    if root.exists() and any(root.iterdir()) and not args.force:
        raise ValueError(f"目标目录非空，拒绝覆盖：{root}；确需重建请显式传 --force")
    if (
        args.force
        and root.exists()
        and any(root.iterdir())
        and not (root / "manifest.json").is_file()
    ):
        raise ValueError(
            "--force 只允许替换带可识别 manifest 的同一人物 store；"
            "普通非空目录拒绝覆盖"
        )
    _check_identity_scope(root, args.slug, args.subject_id)

    root.parent.mkdir(parents=True, exist_ok=True)
    staging_parent = Path(
        tempfile.mkdtemp(prefix=f".{args.slug}-init-", dir=root.parent)
    )
    candidate = staging_parent / args.slug
    moved_old = False
    try:
        _populate_store(candidate, manifest, args)
        assert_store_ready(candidate, phase="compile")
        if root.exists():
            root.replace(backup)
            moved_old = True
        candidate.replace(root)
    except Exception:
        if moved_old and root.exists() and backup.exists():
            shutil.rmtree(root)
        if moved_old and backup.exists() and not root.exists():
            backup.replace(root)
        raise
    finally:
        if staging_parent.exists():
            shutil.rmtree(staging_parent)
    if backup.exists():
        shutil.rmtree(backup)
    print(f"initialized biography store: {root}")
    return 0


def _print_report(report: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(format_human_report(report))


def _report_exit_code(report: Any, mode: str) -> int:
    if mode == "audit":
        return 0 if report.fatal_count == 0 else 1
    if mode == "publish-ready":
        return 0 if report.publish_ready else 1
    return 0 if report.strict_ready else 1


def _audit(args: argparse.Namespace) -> int:
    report = audit_store(args.store_root, mode=args.mode)
    _print_report(report, args.json)
    return _report_exit_code(report, args.mode)


def _verify(args: argparse.Namespace) -> int:
    try:
        report = assert_store_ready(args.store_root, phase=args.phase)
    except ValueError as error:
        print(str(error))
        return 1
    _print_report(report, args.json)
    return 0


def _audit_corpus(args: argparse.Namespace) -> int:
    report = audit_corpus(args.corpus_root, mode=args.mode)
    _print_report(report, args.json)
    return _report_exit_code(report, args.mode)


def _mode_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--mode",
        choices=("audit", "strict-data", "publish-ready"),
        default="audit",
    )
    parser.add_argument("--json", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser(
        "init", help="创建不伪造事实的 manifest v2 空骨架", allow_abbrev=False
    )
    init.add_argument("--store-root", required=True)
    init.add_argument("--slug", required=True)
    init.add_argument("--subject-id", required=True)
    init.add_argument("--catalog-name", required=True)
    init.add_argument("--language", default="zh-CN")
    init.add_argument("--force", action="store_true")
    init.set_defaults(handler=_init)

    audit = subparsers.add_parser(
        "audit", help="只读审计单个人物 store", allow_abbrev=False
    )
    audit.add_argument("--store-root", required=True)
    _mode_argument(audit)
    audit.set_defaults(handler=_audit)

    verify = subparsers.add_parser(
        "verify", help="执行 compile/export 共用 readiness 判据", allow_abbrev=False
    )
    verify.add_argument("--store-root", required=True)
    verify.add_argument("--phase", choices=("compile", "export"), required=True)
    verify.add_argument("--json", action="store_true")
    verify.set_defaults(handler=_verify)

    corpus = subparsers.add_parser(
        "audit-corpus", help="审计系列 registry 与跨人物隔离", allow_abbrev=False
    )
    corpus.add_argument("--corpus-root", required=True)
    _mode_argument(corpus)
    corpus.set_defaults(handler=_audit_corpus)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except ValueError as error:
        print(str(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

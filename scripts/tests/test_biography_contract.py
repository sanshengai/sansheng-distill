#!/usr/bin/env python3
"""Public mutation tests for biography-contract v0.9.0-candidate."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import biography_contract as contract_module  # noqa: E402
from biography_store import main as audit_main  # noqa: E402
from biography_contract import (  # noqa: E402
    ContractAuditReport,
    ContractIssue,
    SCHEMA_DEFINITION_REGISTRY,
    assert_store_ready,
    audit_corpus,
    audit_store,
    issue_codes,
    manifest_v2_skeleton,
    normalize_manifest,
    paragraph_text_sha256,
    governed_record_sha256,
    validate_schema_instance,
)


SUBJECT = "sample-scholar"
SUBJECT_ID = "per-sample-scholar"
OBS_PERSON = "obs-sample-scholar-000001"
MD_PERSON = "md-sample-scholar-000001"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_artifact(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = content.encode("utf-8")
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def register_source_usage(
    root: Path,
    *,
    observation_id: str | None = None,
    verification_id: str | None = None,
) -> None:
    path = root / "source-registry.json"
    registry = read_json(path)
    source = registry["source_units"][0]
    if observation_id is not None:
        source.setdefault("observation_refs", []).append(observation_id)
    if verification_id is not None:
        source.setdefault("verification_refs", []).append(verification_id)
    write_json(path, registry)


def append_observation(root: Path, row: dict) -> None:
    path = root / "observations.jsonl"
    rows = read_jsonl(path)
    rows.append(row)
    write_jsonl(path, rows)
    register_source_usage(root, observation_id=row["observation_id"])


def append_decisions(root: Path, *rows: dict) -> None:
    path = root / "merge-decisions.jsonl"
    decisions = read_jsonl(path)
    decisions.extend(rows)
    write_jsonl(path, decisions)


def observation(observation_id: str, statement: str = "来源记录了这项事实。") -> dict:
    return {
        "schema_version": "biography-observation-v2",
        "observation_id": observation_id,
        "subject_id": SUBJECT_ID,
        "id_namespace": SUBJECT,
        "source_id": "src-sample-scholar-sample-01",
        "anchor": {
            "locator_type": "chapter_position",
            "value": observation_id,
            "title": "样本",
            "witness_id": "wit-sample-scholar-sample-01",
        },
        "observation_type": "event",
        "statement_kind": "fact",
        "statement": statement,
        "verification_status": "unverified",
    }


def formal_review(*, reviewer_id: str = "main-agent") -> dict:
    return {
        "authority": "main_agent",
        "reviewer_id": reviewer_id,
        "reviewed_at": "2026-08-23T00:00:00Z",
        "recommendation_refs": [],
    }


def admission(
    decision_id: str,
    observation_ids: str | list[str],
    *,
    verdict: str = "accept",
    reviewer_id: str = "main-agent",
) -> dict:
    if isinstance(observation_ids, str):
        observation_ids = [observation_ids]
    return {
        "schema_version": "biography-merge-decision-v2",
        "decision_id": decision_id,
        "subject_id": SUBJECT_ID,
        "id_namespace": SUBJECT,
        "scope": "observation_admission",
        "observation_ids": observation_ids,
        "target_ids": [],
        "superseded_ids": [],
        "verdict": verdict,
        "reason": "小样 Observation 主审签署。",
        "conflicts": [],
        "review": formal_review(reviewer_id=reviewer_id),
        "changeset_id": "cs-sample-scholar-c2-001",
        "migration_basis": None,
        "status": "signed",
    }


def resolution(
    decision_id: str,
    observation_ids: str | list[str],
    target_ids: str | list[str],
    *,
    verdict: str = "create",
    superseded_ids: list[str] | None = None,
    reviewer_id: str = "main-agent",
) -> dict:
    if isinstance(observation_ids, str):
        observation_ids = [observation_ids]
    if isinstance(target_ids, str):
        target_ids = [target_ids]
    return {
        "schema_version": "biography-merge-decision-v2",
        "decision_id": decision_id,
        "subject_id": SUBJECT_ID,
        "id_namespace": SUBJECT,
        "scope": "canonical_resolution",
        "observation_ids": observation_ids,
        "target_ids": target_ids,
        "superseded_ids": superseded_ids or [],
        "verdict": verdict,
        "reason": "小样 Canonical 主审签署。",
        "conflicts": [],
        "review": formal_review(reviewer_id=reviewer_id),
        "changeset_id": "cs-sample-scholar-c2-001",
        "migration_basis": None,
        "status": "signed",
    }


def manifest_v2() -> dict:
    return manifest_v2_skeleton(SUBJECT, SUBJECT_ID, "示例学者")


def build_sparse_second_subject(root: Path) -> Path:
    write_json(root / "manifest.json", manifest_v2())
    write_json(
        root / "source-registry.json",
        {
            "schema_version": "biography-source-audit-v1",
            "registry_id": "registry-sample-scholar",
            "subject_id": SUBJECT_ID,
            "id_namespace": SUBJECT,
            "source_units": [
                {
                    "source_id": "src-sample-scholar-sample-01",
                    "source_type": "book",
                    "title": "公开合成样本",
                    "witnesses": [
                        {
                            "witness_id": "wit-sample-scholar-sample-01",
                            "label": "合成数字替身",
                            "witness_type": "digital_surrogate",
                        }
                    ],
                    "observation_refs": [OBS_PERSON],
                    "verification_refs": [],
                }
            ],
        },
    )
    write_jsonl(
        root / "canonical" / "people.jsonl",
        [
            {
                "person_id": SUBJECT_ID,
                "subject_id": SUBJECT_ID,
                "id_namespace": SUBJECT,
                "canonical_name": "示例学者",
                "name_forms": [
                    {
                        "name_form_id": "name-sample-scholar-primary",
                        "text": "示例学者",
                        "kind": "primary",
                        "language": "zh-CN",
                        "script": "Hans",
                        "evidence_refs": [OBS_PERSON],
                        "certainty": "confirmed",
                    },
                    {
                        "name_form_id": "name-sample-scholar-romanized",
                        "text": "Sample Scholar",
                        "kind": "romanized",
                        "language": "zh-Latn",
                        "script": "Latn",
                        "evidence_refs": [OBS_PERSON],
                        "certainty": "confirmed",
                        "derivation": {
                            "method": "Hanyu Pinyin",
                            "basis_evidence_refs": [OBS_PERSON],
                        },
                    },
                    {
                        "name_form_id": "name-sample-scholar-art",
                        "text": "示例别号",
                        "kind": "art_name",
                        "language": "zh-CN",
                        "script": "Hans",
                        "display_role": "secondary",
                        "evidence_refs": [OBS_PERSON],
                        "certainty": "confirmed",
                    },
                ],
                "role": "subject",
                "evidence_refs": [OBS_PERSON],
                "status": "active",
            }
        ],
    )
    for kind in ("events", "works", "relations", "controversies", "quotes"):
        write_jsonl(root / "canonical" / f"{kind}.jsonl", [])
    write_jsonl(root / "observations.jsonl", [observation(OBS_PERSON, "主人物是示例学者。")])
    write_jsonl(
        root / "merge-decisions.jsonl",
        [
            admission(f"{MD_PERSON}-admission", OBS_PERSON),
            resolution(f"{MD_PERSON}-resolution", OBS_PERSON, SUBJECT_ID),
        ],
    )
    write_jsonl(root / "external-verifications.jsonl", [])
    write_jsonl(
        root / "source-coverage-decisions.jsonl",
        [
            {
                "schema_version": "biography-source-coverage-decision-v1",
                "decision_id": "srcdec-sample-scholar-sample-01",
                "subject_id": SUBJECT_ID,
                "id_namespace": SUBJECT,
                "source_id": "src-sample-scholar-sample-01",
                "disposition": "covered",
                "review": formal_review(),
                "changeset_id": "cs-sample-scholar-c2-001",
                "status": "signed",
            }
        ],
    )
    changeset_artifact_ref = "artifacts/changesets/c2-001.json"
    changeset_hash = write_artifact(
        root / changeset_artifact_ref,
        '{"fixture":"changeset"}',
    )
    write_jsonl(
        root / "changesets.jsonl",
        [
            {
                "schema_version": "biography-changeset-v1",
                "changeset_id": "cs-sample-scholar-c2-001",
                "subject_id": SUBJECT_ID,
                "id_namespace": SUBJECT,
                "artifact_ref": changeset_artifact_ref,
                "applied_at": "2026-08-23T00:00:00Z",
                "applied_hash": changeset_hash,
                "status": "applied",
            }
        ],
    )
    for name in (
        "work-classifications",
        "work-identity-decisions",
        "quote-attribution-audits",
        "prose-risk-reviews",
        "model-recommendations",
        "media-assets",
    ):
        write_jsonl(root / f"{name}.jsonl", [])
    for name in ("chapter_order", "chapters", "overview", "layout", "dossier", "media"):
        write_json(root / "editorial" / f"{name}.json", {})
    return root


def add_event(
    root: Path,
    event_id: str,
    observation_id: str,
    decision_id: str,
    *,
    status: str = "active",
    merged_into: str | None = None,
    add_signed_decision: bool = True,
) -> None:
    event = {
        "event_id": event_id,
        "subject_id": SUBJECT_ID,
        "id_namespace": SUBJECT,
        "person_id": SUBJECT_ID,
        "actors": [SUBJECT_ID],
        "work_ids": [],
        "relation_ids": [],
        "controversy_ids": [],
        "status": status,
    }
    if status == "active":
        event.update(
            {
                "title": "合成样本事件",
                "date": {
                    "calendar_system": "gregorian",
                    "original_text": "1082",
                    "display_label": "1082年",
                    "start": "1082-01-01",
                    "end": "1082-12-31",
                    "precision": "year",
                },
            }
        )
    if status in {"active", "hold"}:
        event["evidence_refs"] = [observation_id]
    if merged_into is not None:
        event["merged_into"] = merged_into
    events_path = root / "canonical" / "events.jsonl"
    events = read_jsonl(events_path)
    events.append(event)
    write_jsonl(events_path, events)
    if status == "merged_redirect":
        return
    append_observation(root, observation(observation_id))
    if add_signed_decision:
        decisions_path = root / "merge-decisions.jsonl"
        decisions = read_jsonl(decisions_path)
        decisions.extend(
            [
                admission(f"{decision_id}-admission", observation_id),
                resolution(f"{decision_id}-resolution", observation_id, event_id),
            ]
        )
        write_jsonl(decisions_path, decisions)


def external_verification(
    verification_id: str,
    target_ids: str | list[str],
) -> dict:
    if isinstance(target_ids, str):
        target_ids = [target_ids]
    return {
        "schema_version": "biography-external-verification-v1",
        "verification_id": verification_id,
        "subject_id": SUBJECT_ID,
        "id_namespace": SUBJECT,
        "target_ids": target_ids,
        "source_ids": ["src-sample-scholar-sample-01"],
        "verdict": "confirmed",
        "review": formal_review(),
        "changeset_id": "cs-sample-scholar-c2-001",
        "status": "signed",
    }


def append_verification(root: Path, row: dict) -> None:
    path = root / "external-verifications.jsonl"
    rows = read_jsonl(path)
    rows.append(row)
    write_jsonl(path, rows)
    register_source_usage(root, verification_id=row["verification_id"])


def make_publish_ready(root: Path) -> None:
    manifest_path = root / "manifest.json"
    manifest = read_json(manifest_path)
    manifest["publication"].update(
        {
            "status": "review",
            "href": manifest["projection"]["route_base"],
            "catalog_summary": "以证据链呈现示例学者生平。",
        }
    )
    for descriptor in manifest["governance"]["ledgers"]:
        if descriptor["kind"] == "prose_risk_reviews":
            descriptor["required_for_publication"] = True
    write_json(manifest_path, manifest)
    write_json(
        root / "editorial" / "chapter_order.json",
        {
            "schema_version": "biography-chapter-order-v1",
            "subject_id": SUBJECT_ID,
            "order": [{"seq": 1, "chapter_id": "chapter-one"}],
        },
    )
    write_json(
        root / "editorial" / "chapters.json",
        {
            "schema_version": "biography-chapters-v1",
            "chapters": [
                {
                    "chapter_id": "chapter-one",
                    "title": "第一章",
                    "status": "review",
                    "event_refs": [],
                    "paragraphs": [
                        {
                            "paragraph_id": "paragraph-sample-scholar-one",
                            "text": "示例学者是本传记的主人物。",
                            "evidence_refs": [OBS_PERSON],
                        }
                    ],
                }
            ],
        },
    )
    for name in ("overview", "layout", "dossier"):
        write_json(
            root / "editorial" / f"{name}.json",
            {"schema_version": f"biography-{name}-v1", "subject_id": SUBJECT_ID},
        )
    paragraph = {
        "paragraph_id": "paragraph-sample-scholar-one",
        "text": "示例学者是本传记的主人物。",
        "evidence_refs": [OBS_PERSON],
    }
    write_jsonl(
        root / "prose-risk-reviews.jsonl",
        [
            {
                "schema_version": "biography-prose-risk-review-v1",
                "review_id": "prosereview-sample-scholar-one",
                "subject_id": SUBJECT_ID,
                "id_namespace": SUBJECT,
                "paragraph_id": "paragraph-sample-scholar-one",
                "text_sha256": paragraph_text_sha256(paragraph),
                "verdict": "approved",
                "evidence_refs": [OBS_PERSON],
                "review": formal_review(),
                "changeset_id": "cs-sample-scholar-c2-001",
                "status": "signed",
            }
        ],
    )


def append_ledger_row(root: Path, ledger_name: str, row: dict) -> None:
    path = root / f"{ledger_name}.jsonl"
    rows = read_jsonl(path)
    rows.append(row)
    write_jsonl(path, rows)


def add_active_work(root: Path, *, suffix: str = "sample") -> tuple[str, str]:
    work_id = f"wrk-sample-scholar-{suffix}"
    observation_id = f"obs-sample-scholar-work-{suffix}"
    append_observation(root, observation(observation_id, "来源记录了这部作品。"))
    works_path = root / "canonical" / "works.jsonl"
    works = read_jsonl(works_path)
    works.append(
        {
            "work_id": work_id,
            "subject_id": SUBJECT_ID,
            "id_namespace": SUBJECT,
            "title": "合成作品",
            "entity_level": "intellectual_work",
            "work_type": "literary_work",
            "evidence_refs": [observation_id],
            "status": "active",
        }
    )
    write_jsonl(works_path, works)
    append_decisions(
        root,
        admission(f"md-sample-scholar-work-{suffix}-admission", observation_id),
        resolution(
            f"md-sample-scholar-work-{suffix}-resolution",
            observation_id,
            work_id,
        ),
    )
    append_ledger_row(
        root,
        "work-classifications",
        {
            "schema_version": "biography-work-classification-v1",
            "classification_id": f"workclass-sample-scholar-{suffix}",
            "subject_id": SUBJECT_ID,
            "id_namespace": SUBJECT,
            "work_id": work_id,
            "entity_level": "intellectual_work",
            "review": formal_review(),
            "changeset_id": "cs-sample-scholar-c2-001",
            "status": "signed",
        },
    )
    append_ledger_row(
        root,
        "work-identity-decisions",
        {
            "schema_version": "biography-work-identity-decision-v1",
            "decision_id": f"workid-sample-scholar-{suffix}",
            "cluster_id": f"workcluster-sample-scholar-{suffix}",
            "subject_id": SUBJECT_ID,
            "id_namespace": SUBJECT,
            "work_ids": [work_id],
            "disposition": "keep_separate",
            "review": formal_review(),
            "changeset_id": "cs-sample-scholar-c2-001",
            "status": "signed",
        },
    )
    return work_id, observation_id


def add_active_quote(root: Path, *, suffix: str = "sample") -> tuple[str, str]:
    quote_id = f"quote-sample-scholar-{suffix}"
    observation_id = f"obs-sample-scholar-quote-{suffix}"
    append_observation(root, observation(observation_id, "来源记录了这句话。"))
    quotes_path = root / "canonical" / "quotes.jsonl"
    quotes = read_jsonl(quotes_path)
    quotes.append(
        {
            "quote_id": quote_id,
            "subject_id": SUBJECT_ID,
            "id_namespace": SUBJECT,
            "author_id": SUBJECT_ID,
            "speaker": {"type": "author", "person_id": SUBJECT_ID},
            "claimed_speaker_ids": [SUBJECT_ID],
            "attribution_status": "verified",
            "text_forms": [
                {
                    "text_form_id": f"qtext-sample-scholar-{suffix}-base",
                    "kind": "base",
                    "text": "合成引文。",
                    "language": "zh-CN",
                    "script": "Hans",
                    "locator": {
                        "locator_type": "chapter_position",
                        "value": f"quote-{suffix}",
                    },
                    "evidence_refs": [observation_id],
                }
            ],
            "evidence_refs": [observation_id],
            "status": "active",
        }
    )
    write_jsonl(quotes_path, quotes)
    append_decisions(
        root,
        admission(f"md-sample-scholar-quote-{suffix}-admission", observation_id),
        resolution(
            f"md-sample-scholar-quote-{suffix}-resolution",
            observation_id,
            quote_id,
        ),
    )
    append_ledger_row(
        root,
        "quote-attribution-audits",
        {
            "schema_version": "biography-quote-attribution-audit-v1",
            "audit_id": f"quoteaudit-sample-scholar-{suffix}",
            "subject_id": SUBJECT_ID,
            "id_namespace": SUBJECT,
            "quote_id": quote_id,
            "verdict": "verified",
            "evidence_refs": [observation_id],
            "review": formal_review(),
            "changeset_id": "cs-sample-scholar-c2-001",
            "status": "signed",
        },
    )
    return quote_id, observation_id


def add_media_asset(
    root: Path,
    *,
    authenticity_status: str = "verified",
) -> dict:
    file_ref = "media/sample-portrait.txt"
    file_hash = write_artifact(root / file_ref, "synthetic portrait bytes\n")
    row = {
        "schema_version": "biography-media-asset-v1",
        "asset_id": "media-sample-scholar-sample-portrait",
        "subject_id": SUBJECT_ID,
        "id_namespace": SUBJECT,
        "kind": "portrait",
        "source_id": "src-sample-scholar-sample-01",
        "file_ref": file_ref,
        "sha256": file_hash,
        "authenticity_status": authenticity_status,
        "object_attribution_status": "not_applicable",
        "depicted_person_ids": [SUBJECT_ID],
        "creator_ids": [],
        "rights_status": "public_domain",
        "license": "Public Domain Mark 1.0",
        "source_url": "https://example.test/sample-scholar-portrait",
        "review": formal_review(),
        "changeset_id": "cs-sample-scholar-c2-001",
        "status": "active",
    }
    row["metadata_sha256"] = governed_record_sha256(row)
    append_ledger_row(root, "media-assets", row)
    return row


def build_two_subject_corpus(root: Path) -> tuple[Path, Path]:
    su_shi_root = build_sparse_second_subject(root / "sample-scholar")
    other_scholar_root = build_sparse_second_subject(root / "other-scholar")
    for path in other_scholar_root.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            path.write_text(
                text.replace("sample-scholar", "other-scholar").replace("示例学者", "另一位学者"),
                encoding="utf-8",
            )
    subjects = []
    for store_ref, store_root in (
        ("sample-scholar", su_shi_root),
        ("other-scholar", other_scholar_root),
    ):
        manifest = read_json(store_root / "manifest.json")
        subjects.append(
            {
                "slug": manifest["subject"]["slug"],
                "store_ref": store_ref,
                "subject_id": manifest["subject"]["subject_id"],
                "id_namespace": manifest["subject"]["id_namespace"],
                "route_base": manifest["projection"]["route_base"],
            }
        )
    write_json(
        root / "corpus.json",
        {"schema_version": "biography-corpus-v1", "subjects": subjects},
    )
    return su_shi_root, other_scholar_root


def test_sparse_second_person_minimum_fixture_passes_strict_data(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)

    report = audit_store(root, mode="strict-data")

    assert report.strict_ready, report.to_dict()
    assert report.status == "STRICT_DATA_READY"


def test_stable_historical_subject_id_need_not_equal_per_slug(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    historical_id = "per-su-dongpo"
    manifest_path = root / "manifest.json"
    manifest = read_json(manifest_path)
    manifest["subject"]["subject_id"] = historical_id
    write_json(manifest_path, manifest)
    registry_path = root / "source-registry.json"
    registry = read_json(registry_path)
    registry["subject_id"] = historical_id
    write_json(registry_path, registry)
    people_path = root / "canonical" / "people.jsonl"
    people = read_jsonl(people_path)
    people[0]["person_id"] = historical_id
    people[0]["subject_id"] = historical_id
    write_jsonl(people_path, people)
    observations = read_jsonl(root / "observations.jsonl")
    observations[0]["subject_id"] = historical_id
    write_jsonl(root / "observations.jsonl", observations)
    decisions = read_jsonl(root / "merge-decisions.jsonl")
    for row in decisions:
        row["subject_id"] = historical_id
        row["target_ids"] = [historical_id] if row["scope"] == "canonical_resolution" else []
    write_jsonl(root / "merge-decisions.jsonl", decisions)
    for ledger_name in ("source-coverage-decisions", "changesets"):
        ledger_path = root / f"{ledger_name}.jsonl"
        rows = read_jsonl(ledger_path)
        for row in rows:
            row["subject_id"] = historical_id
        write_jsonl(ledger_path, rows)

    report = audit_store(root, mode="strict-data")

    assert report.strict_ready, report.to_dict()


def test_courtesy_name_is_a_name_form_not_a_second_person(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    people_path = root / "canonical" / "people.jsonl"
    people = read_jsonl(people_path)
    people[0]["name_forms"].append(
        {
            "name_form_id": "name-sample-scholar-courtesy-zizhan",
            "text": "示例字",
            "kind": "courtesy_name",
            "language": "zh-CN",
            "script": "Hans",
            "evidence_refs": [OBS_PERSON],
            "certainty": "confirmed",
        }
    )
    write_jsonl(people_path, people)

    report = audit_store(root, mode="strict-data")

    assert report.strict_ready, report.to_dict()
    assert len(read_jsonl(people_path)) == 1


def test_subject_person_does_not_require_romanized_or_secondary_name(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    people_path = root / "canonical" / "people.jsonl"
    people = read_jsonl(people_path)
    people[0]["name_forms"] = [
        form for form in people[0]["name_forms"] if form["kind"] != "romanized"
    ]
    for form in people[0]["name_forms"]:
        form.pop("display_role", None)
    write_jsonl(people_path, people)

    report = audit_store(root, mode="strict-data")

    assert report.strict_ready, report.to_dict()


def test_observation_requires_exactly_one_signed_admission(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    decisions_path = root / "merge-decisions.jsonl"
    decisions = read_jsonl(decisions_path)
    decisions = [row for row in decisions if row["scope"] != "observation_admission"]
    write_jsonl(decisions_path, decisions)

    missing = audit_store(root, mode="strict-data")
    assert "OBSERVATION_ADMISSION_MISSING" in issue_codes(missing)

    decisions.append(admission("md-sample-scholar-duplicate-admission-a", OBS_PERSON))
    decisions.append(admission("md-sample-scholar-duplicate-admission-b", OBS_PERSON))
    write_jsonl(decisions_path, decisions)
    duplicate = audit_store(root, mode="strict-data")
    assert "OBSERVATION_ADMISSION_DUPLICATE" in issue_codes(duplicate)


def test_accepted_observation_requires_exactly_one_resolution(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    decisions_path = root / "merge-decisions.jsonl"
    decisions = read_jsonl(decisions_path)
    resolutions = [row for row in decisions if row["scope"] == "canonical_resolution"]
    decisions = [row for row in decisions if row["scope"] != "canonical_resolution"]
    write_jsonl(decisions_path, decisions)

    missing = audit_store(root, mode="strict-data")
    assert "OBSERVATION_RESOLUTION_MISSING" in issue_codes(missing)

    decisions.extend(resolutions)
    decisions.append(resolution("md-sample-scholar-duplicate-resolution", OBS_PERSON, SUBJECT_ID))
    write_jsonl(decisions_path, decisions)
    duplicate = audit_store(root, mode="strict-data")
    assert "OBSERVATION_RESOLUTION_DUPLICATE" in issue_codes(duplicate)


def test_hold_or_reject_observation_must_not_have_resolution(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    decisions_path = root / "merge-decisions.jsonl"
    decisions = read_jsonl(decisions_path)
    admission_row = next(row for row in decisions if row["scope"] == "observation_admission")
    admission_row["verdict"] = "hold"
    write_jsonl(decisions_path, decisions)

    report = audit_store(root, mode="strict-data")

    assert "OBSERVATION_RESOLUTION_FORBIDDEN" in issue_codes(report)


def test_adopt_resolution_requires_and_accepts_migration_basis(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    decisions_path = root / "merge-decisions.jsonl"
    decisions = read_jsonl(decisions_path)
    resolution_row = next(row for row in decisions if row["scope"] == "canonical_resolution")
    resolution_row["verdict"] = "adopt"
    resolution_row["migration_basis"] = {
        "source_schema_version": "biography-merge-decision-v1",
        "legacy_decision_id": MD_PERSON,
        "original_reviewed_at": None,
        "migrated_at": "2026-08-23T00:00:00Z",
        "note": "保留旧 ID，不伪造旧审核时间。",
    }
    write_jsonl(decisions_path, decisions)

    accepted = audit_store(root, mode="strict-data")
    assert accepted.strict_ready, accepted.to_dict()

    resolution_row["migration_basis"] = None
    write_jsonl(decisions_path, decisions)
    missing = audit_store(root, mode="strict-data")
    assert "ADOPT_MIGRATION_BASIS_REQUIRED" in issue_codes(missing)


def test_migration_basis_requires_explicit_original_time_and_is_adopt_only(
    tmp_path: Path,
) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    decisions_path = root / "merge-decisions.jsonl"
    decisions = read_jsonl(decisions_path)
    resolution_row = next(row for row in decisions if row["scope"] == "canonical_resolution")
    resolution_row["verdict"] = "adopt"
    resolution_row["migration_basis"] = {
        "source_schema_version": "biography-merge-decision-v1",
        "legacy_decision_id": MD_PERSON,
        "migrated_at": "2026-08-23T00:00:00Z",
        "note": "原审核时间未知，不能用迁移时间冒充。",
    }
    write_jsonl(decisions_path, decisions)

    missing_time = audit_store(root, mode="strict-data")
    assert {
        "SCHEMA_MERGE_DECISION_INVALID",
        "MIGRATION_BASIS_ORIGINAL_TIME_REQUIRED",
    }.issubset(issue_codes(missing_time))

    resolution_row["verdict"] = "create"
    resolution_row["migration_basis"]["original_reviewed_at"] = None
    write_jsonl(decisions_path, decisions)
    wrong_verdict = audit_store(root, mode="strict-data")
    assert "MIGRATION_BASIS_FORBIDDEN" in issue_codes(wrong_verdict)


def test_redirect_requires_exactly_one_merge_resolution(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    target_id = "evt-sample-scholar-redirect-target"
    source_id = "evt-sample-scholar-old-target"
    add_event(
        root,
        target_id,
        "obs-sample-scholar-redirect-target",
        "md-sample-scholar-redirect-target",
    )
    events_path = root / "canonical" / "events.jsonl"
    events = read_jsonl(events_path)
    events.append(
        {
            "event_id": source_id,
            "subject_id": SUBJECT_ID,
            "id_namespace": SUBJECT,
            "status": "merged_redirect",
            "merged_into": target_id,
        }
    )
    write_jsonl(events_path, events)

    rogue = audit_store(root, mode="strict-data")
    assert "REDIRECT_MERGE_DECISION_MISSING" in issue_codes(rogue)

    merge_observation = "obs-sample-scholar-redirect-merge"
    append_observation(root, observation(merge_observation, "旧事件与现役事件同一。"))
    append_decisions(
        root,
        admission("md-sample-scholar-redirect-merge-admission", merge_observation),
        resolution(
            "md-sample-scholar-redirect-merge-resolution",
            merge_observation,
            target_id,
            verdict="merge",
            superseded_ids=[source_id],
        ),
    )
    valid = audit_store(root, mode="strict-data")
    assert valid.strict_ready, valid.to_dict()

    append_decisions(
        root,
        resolution(
            "md-sample-scholar-redirect-merge-resolution-duplicate",
            merge_observation,
            target_id,
            verdict="merge",
            superseded_ids=[source_id],
        ),
    )
    duplicate = audit_store(root, mode="strict-data")
    assert "REDIRECT_MERGE_DECISION_DUPLICATE" in issue_codes(duplicate)


def test_hold_object_interpretation_refs_require_resolution_coverage(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    event_id = "evt-sample-scholar-held-interpretation"
    evidence_id = "obs-sample-scholar-held-evidence"
    interpretation_id = "obs-sample-scholar-held-interpretation"
    add_event(root, event_id, evidence_id, "md-sample-scholar-held", status="hold")
    append_observation(root, observation(interpretation_id, "该材料是后世解释。"))
    append_decisions(
        root,
        admission("md-sample-scholar-held-interpretation-admission", interpretation_id),
        resolution(
            "md-sample-scholar-held-interpretation-resolution", interpretation_id, event_id
        ),
    )
    events_path = root / "canonical" / "events.jsonl"
    events = read_jsonl(events_path)
    target = next(row for row in events if row["event_id"] == event_id)
    target["interpretation_refs"] = [interpretation_id]
    write_jsonl(events_path, events)

    valid = audit_store(root, mode="strict-data")
    assert valid.strict_ready, valid.to_dict()

    decisions = read_jsonl(root / "merge-decisions.jsonl")
    decisions = [
        row
        for row in decisions
        if row["decision_id"] != "md-sample-scholar-held-interpretation-resolution"
    ]
    write_jsonl(root / "merge-decisions.jsonl", decisions)
    uncovered = audit_store(root, mode="strict-data")
    assert "INTERPRETATION_NOT_DECIDED" in issue_codes(uncovered)


def test_observation_source_and_source_registry_backlink_are_closed(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    observations_path = root / "observations.jsonl"
    observations = read_jsonl(observations_path)
    observations[0]["source_id"] = "src-sample-scholar-missing"
    write_jsonl(observations_path, observations)

    unknown = audit_store(root, mode="strict-data")
    assert "OBSERVATION_SOURCE_UNKNOWN" in issue_codes(unknown)

    observations[0]["source_id"] = "src-sample-scholar-sample-01"
    write_jsonl(observations_path, observations)
    registry_path = root / "source-registry.json"
    registry = read_json(registry_path)
    registry["source_units"][0]["observation_refs"] = []
    write_json(registry_path, registry)
    no_backlink = audit_store(root, mode="strict-data")
    assert "SOURCE_OBSERVATION_BACKLINK_MISSING" in issue_codes(no_backlink)


def test_formal_reviewer_must_be_declared_in_manifest_allowlist(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    decisions_path = root / "merge-decisions.jsonl"
    decisions = read_jsonl(decisions_path)
    decisions[0]["review"]["reviewer_id"] = "unregistered-human"
    write_jsonl(decisions_path, decisions)

    report = audit_store(root, mode="strict-data")

    assert "FORMAL_REVIEWER_UNREGISTERED" in issue_codes(report)


def test_external_verification_has_bidirectional_canonical_and_source_links(
    tmp_path: Path,
) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    verification_id = "ver-sample-scholar-person-0001"
    append_verification(root, external_verification(verification_id, SUBJECT_ID))
    people_path = root / "canonical" / "people.jsonl"
    people = read_jsonl(people_path)
    people[0]["verification_refs"] = [verification_id]
    write_jsonl(people_path, people)

    valid = audit_store(root, mode="strict-data")
    assert valid.strict_ready, valid.to_dict()

    registry_path = root / "source-registry.json"
    registry = read_json(registry_path)
    registry["source_units"][0]["verification_refs"] = []
    write_json(registry_path, registry)
    missing_source_backlink = audit_store(root, mode="strict-data")
    assert "SOURCE_VERIFICATION_BACKLINK_MISSING" in issue_codes(
        missing_source_backlink
    )
    registry["source_units"][0]["verification_refs"] = [verification_id]
    write_json(registry_path, registry)

    people[0].pop("verification_refs")
    write_jsonl(people_path, people)
    missing_backlink = audit_store(root, mode="strict-data")
    assert "VERIFICATION_BACKLINK_MISSING" in issue_codes(missing_backlink)

    people[0]["verification_refs"] = [verification_id]
    write_jsonl(people_path, people)
    verifications = read_jsonl(root / "external-verifications.jsonl")
    verifications[0]["target_ids"] = ["evt-sample-scholar-nonexistent"]
    write_jsonl(root / "external-verifications.jsonl", verifications)
    missing_target = audit_store(root, mode="strict-data")
    assert "VERIFICATION_TARGET_BACKLINK_MISSING" in issue_codes(missing_target)


def test_work_reader_explanation_participates_in_full_reference_graph(
    tmp_path: Path,
) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    event_id = "evt-sample-scholar-reader-context"
    add_event(
        root,
        event_id,
        "obs-sample-scholar-reader-event",
        "md-sample-scholar-reader-event",
    )
    work_id = "work-sample-scholar-reader-example"
    evidence_id = "obs-sample-scholar-reader-work"
    interpretation_id = "obs-sample-scholar-reader-interpretation"
    append_observation(root, observation(evidence_id, "来源记录了这件作品。"))
    append_observation(root, observation(interpretation_id, "研究者解释了作品意义。"))
    append_decisions(
        root,
        admission("md-sample-scholar-reader-work-admission", evidence_id),
        admission("md-sample-scholar-reader-interpretation-admission", interpretation_id),
        resolution(
            "md-sample-scholar-reader-work-resolution",
            [evidence_id, interpretation_id],
            work_id,
        ),
    )
    verification_id = "ver-sample-scholar-reader-work"
    append_verification(root, external_verification(verification_id, work_id))
    write_jsonl(
        root / "canonical" / "works.jsonl",
        [
            {
                "work_id": work_id,
                "subject_id": SUBJECT_ID,
                "id_namespace": SUBJECT,
                "title": "示例作品",
                "entity_level": "intellectual_work",
                "work_type": "prose",
                "collaborator_ids": [],
                "event_ids": [event_id],
                "evidence_refs": [evidence_id],
                "interpretation_refs": [interpretation_id],
                "verification_refs": [verification_id],
                "reader_explanation": {
                    "claim": "这是作品的核心主张。",
                    "importance": "它解释作品为何值得读。",
                    "misconception": "不能把后世解释冒充原始事实。",
                    "evidence_refs": [evidence_id],
                    "interpretation_refs": [interpretation_id],
                    "verification_refs": [verification_id],
                    "related_event_ids": [event_id],
                },
                "status": "active",
            }
        ],
    )

    valid = audit_store(root, mode="strict-data")
    assert valid.strict_ready, valid.to_dict()

    works = read_jsonl(root / "canonical" / "works.jsonl")
    works[0]["reader_explanation"]["related_event_ids"] = ["evt-sample-scholar-missing"]
    write_jsonl(root / "canonical" / "works.jsonl", works)
    broken = audit_store(root, mode="strict-data")
    assert "READER_RELATED_EVENT_MISSING" in issue_codes(broken)


def test_hold_relation_may_remain_sparse_while_active_relation_may_not(
    tmp_path: Path,
) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    observation_id = "obs-sample-scholar-held-relation"
    relation_id = "rel-sample-scholar-held-relation"
    append_observation(root, observation(observation_id, "关系端点尚不能确认。"))
    write_jsonl(
        root / "canonical" / "relations.jsonl",
        [
            {
                "relation_id": relation_id,
                "subject_id": SUBJECT_ID,
                "id_namespace": SUBJECT,
                "evidence_refs": [observation_id],
                "certainty": "unknown",
                "status": "hold",
            }
        ],
    )
    append_decisions(
        root,
        admission("md-sample-scholar-held-relation-admission", observation_id),
        resolution("md-sample-scholar-held-relation-resolution", observation_id, relation_id),
    )

    report = audit_store(root, mode="strict-data")

    assert report.strict_ready, report.to_dict()


def test_publish_ready_is_stricter_than_strict_data(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)

    strict_data = audit_store(root, mode="strict-data")
    publish_blocked = audit_store(root, mode="publish-ready")

    assert strict_data.strict_ready, strict_data.to_dict()
    assert not publish_blocked.publish_ready
    assert {
        "PUBLICATION_STATUS_NOT_READY",
        "EDITORIAL_CHAPTERS_EMPTY",
        "EDITORIAL_CHAPTER_ORDER_EMPTY",
    }.issubset(issue_codes(publish_blocked))

    make_publish_ready(root)
    publish_ready = audit_store(root, mode="publish-ready")
    assert publish_ready.publish_ready, publish_ready.to_dict()
    assert publish_ready.status == "PUBLISH_READY"


def test_strict_data_does_not_require_editorial_artifacts(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    for name in ("chapter_order", "chapters", "overview", "layout", "dossier"):
        (root / "editorial" / f"{name}.json").unlink()

    strict_data = audit_store(root, mode="strict-data")
    publish_ready = audit_store(root, mode="publish-ready")

    assert strict_data.strict_ready, strict_data.to_dict()
    assert not publish_ready.publish_ready
    assert "DECLARED_FILE_MISSING" in issue_codes(publish_ready)


def test_publish_ready_rejects_chapter_order_without_exact_closure(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    make_publish_ready(root)
    order_path = root / "editorial" / "chapter_order.json"
    order = read_json(order_path)
    order["order"].append({"seq": 2, "chapter_id": "chapter-missing"})
    write_json(order_path, order)

    report = audit_store(root, mode="publish-ready")

    assert "EDITORIAL_CHAPTER_ORDER_MISMATCH" in issue_codes(report)


def test_redirect_cycle_is_rejected(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    add_event(
        root,
        "evt-sample-scholar-cycle-a",
        "obs-sample-scholar-unused-a",
        "md-sample-scholar-unused-a",
        status="merged_redirect",
        merged_into="evt-sample-scholar-cycle-b",
    )
    add_event(
        root,
        "evt-sample-scholar-cycle-b",
        "obs-sample-scholar-unused-b",
        "md-sample-scholar-unused-b",
        status="merged_redirect",
        merged_into="evt-sample-scholar-cycle-a",
    )

    report = audit_store(root, mode="strict")

    assert "REDIRECT_CYCLE" in issue_codes(report)
    assert not report.strict_ready


def test_redirect_chain_is_rejected_even_when_it_ends_active(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    add_event(
        root,
        "evt-sample-scholar-chain-final",
        "obs-sample-scholar-chain-final",
        "md-sample-scholar-chain-final",
    )
    add_event(
        root,
        "evt-sample-scholar-chain-middle",
        "obs-sample-scholar-unused-middle",
        "md-sample-scholar-unused-middle",
        status="merged_redirect",
        merged_into="evt-sample-scholar-chain-final",
    )
    add_event(
        root,
        "evt-sample-scholar-chain-start",
        "obs-sample-scholar-unused-start",
        "md-sample-scholar-unused-start",
        status="merged_redirect",
        merged_into="evt-sample-scholar-chain-middle",
    )

    report = audit_store(root, mode="strict")

    assert "REDIRECT_CHAIN" in issue_codes(report)


def test_internal_redirect_to_hold_is_allowed_with_signed_merge(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    add_event(
        root,
        "evt-sample-scholar-held-target",
        "obs-sample-scholar-unused-held",
        "md-sample-scholar-unused-held",
        status="hold",
    )
    add_event(
        root,
        "evt-sample-scholar-held-redirect",
        "obs-sample-scholar-unused-redirect",
        "md-sample-scholar-unused-redirect",
        status="merged_redirect",
        merged_into="evt-sample-scholar-held-target",
    )
    merge_observation = "obs-sample-scholar-held-redirect-merge"
    append_observation(root, observation(merge_observation, "两个事件记录指向同一候选对象。"))
    append_decisions(
        root,
        admission("md-sample-scholar-held-redirect-admission", merge_observation),
        resolution(
            "md-sample-scholar-held-redirect-resolution",
            merge_observation,
            "evt-sample-scholar-held-target",
            verdict="merge",
            superseded_ids=["evt-sample-scholar-held-redirect"],
        ),
    )

    report = audit_store(root, mode="strict-data")

    assert "REDIRECT_TARGET_HOLD" not in issue_codes(report)
    assert report.strict_ready, report.to_dict()


def test_active_evidence_without_signed_decision_is_rejected(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    add_event(
        root,
        "evt-sample-scholar-uncovered",
        "obs-sample-scholar-uncovered",
        "md-sample-scholar-uncovered",
        add_signed_decision=False,
    )

    report = audit_store(root, mode="strict")

    assert "EVIDENCE_NOT_DECIDED" in issue_codes(report)
    issue = next(issue for issue in report.issues if issue.code == "EVIDENCE_NOT_DECIDED")
    assert issue.object_id == "evt-sample-scholar-uncovered"


def test_glm_cannot_be_formal_reviewer(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    decisions_path = root / "merge-decisions.jsonl"
    decisions = read_jsonl(decisions_path)
    decisions[0]["review"]["reviewer_id"] = "GLM-5.3"
    write_jsonl(decisions_path, decisions)

    report = audit_store(root, mode="strict")

    assert "FORMAL_REVIEWER_IS_MODEL" in issue_codes(report)
    assert not report.strict_ready


def test_duplicate_normalized_name_forms_are_rejected(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    people_path = root / "canonical" / "people.jsonl"
    people = read_jsonl(people_path)
    people[0]["name_forms"].append(
        {
            "text": "  示例学者  ",
            "kind": "alias",
            "language": "zh-CN",
            "script": "Hans",
        }
    )
    write_jsonl(people_path, people)

    report = audit_store(root, mode="strict")

    assert "NAME_FORM_DUPLICATE" in issue_codes(report)


def test_subject_owned_assets_and_css_must_be_namespaced(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    manifest_path = root / "manifest.json"
    manifest = read_json(manifest_path)
    manifest["projection"]["asset_base"] = "/yiye-biography/assets/"
    manifest["projection"]["asset_target"] = "assets"
    manifest["projection"]["css_scope"] = ".biography"
    write_json(manifest_path, manifest)

    report = audit_store(root, mode="strict")

    assert {
        "ASSET_NAMESPACE_REQUIRED",
        "ASSET_TARGET_NAMESPACE_REQUIRED",
        "CSS_SCOPE_NAMESPACE_REQUIRED",
    }.issubset(issue_codes(report))


def test_shared_resources_are_series_owned_read_only_and_content_addressed(
    tmp_path: Path,
) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    manifest_path = root / "manifest.json"
    manifest = read_json(manifest_path)
    manifest["projection"]["shared_resources"] = [
        {
            "resource_id": "series-biography-logo-v1",
            "kind": "asset",
            "ref": "other-scholar/logo.svg",
            "owner": "other-scholar",
            "read_only": False,
            "sha256": "not-a-digest",
        }
    ]
    write_json(manifest_path, manifest)

    report = audit_store(root, mode="strict-data")

    assert {
        "SCHEMA_MANIFEST_INVALID",
        "SHARED_RESOURCE_OWNERSHIP_INVALID",
        "SHARED_RESOURCE_REF_INVALID",
        "SHARED_RESOURCE_HASH_INVALID",
    }.issubset(issue_codes(report))


def test_valid_shared_resource_is_resolved_below_declared_root_and_hash_checked(
    tmp_path: Path,
) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    payload = b'<svg xmlns="http://www.w3.org/2000/svg"/>'
    shared_file = root / "shared" / "series-logo.svg"
    shared_file.parent.mkdir(parents=True)
    shared_file.write_bytes(payload)

    manifest_path = root / "manifest.json"
    manifest = read_json(manifest_path)
    manifest["projection"]["shared_resource_root"] = "shared"
    manifest["projection"]["shared_resources"] = [
        {
            "resource_id": "series-biography-logo-v1",
            "kind": "asset",
            "ref": "@series/series-logo.svg",
            "owner": "biography-series",
            "read_only": True,
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    ]
    write_json(manifest_path, manifest)

    report = audit_store(root, mode="strict-data")

    assert report.strict_ready, report.to_dict()


def test_required_governance_ledger_cannot_be_implicit(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    manifest_path = root / "manifest.json"
    manifest = read_json(manifest_path)
    manifest["governance"]["ledgers"] = [
        item
        for item in manifest["governance"]["ledgers"]
        if item["kind"] != "external_verifications"
    ]
    write_json(manifest_path, manifest)

    report = audit_store(root, mode="strict")

    assert "REQUIRED_LEDGER_UNDECLARED" in issue_codes(report)


def test_row_namespace_must_match_manifest(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    people_path = root / "canonical" / "people.jsonl"
    people = read_jsonl(people_path)
    people[0]["id_namespace"] = "other-scholar"
    write_jsonl(people_path, people)

    report = audit_store(root, mode="strict")

    assert "ROW_NAMESPACE_MISMATCH" in issue_codes(report)


def test_active_relation_requires_two_resolved_people(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    observation_id = "obs-sample-scholar-relation-0001"
    relation_id = "rel-sample-scholar-incomplete"
    append_observation(root, observation(observation_id, "只出现一个关系端点。"))
    relations = [
        {
            "relation_id": relation_id,
            "subject_id": SUBJECT_ID,
            "id_namespace": SUBJECT,
            "relation_type": "other",
            "participants": [
                {"person_id": SUBJECT_ID, "role": "known_endpoint"}
            ],
            "person_ids": [SUBJECT_ID],
            "evidence_refs": [observation_id],
            "certainty": "probable",
            "status": "active",
        }
    ]
    write_jsonl(root / "canonical" / "relations.jsonl", relations)
    decisions = read_jsonl(root / "merge-decisions.jsonl")
    decisions.extend(
        [
            admission("md-sample-scholar-relation-0001-admission", observation_id),
            resolution("md-sample-scholar-relation-0001-resolution", observation_id, relation_id),
        ]
    )
    write_jsonl(root / "merge-decisions.jsonl", decisions)

    report = audit_store(root, mode="strict")

    assert "RELATION_ENDPOINTS_INCOMPLETE" in issue_codes(report)


def test_active_relation_participant_roles_must_cover_the_same_endpoints(
    tmp_path: Path,
) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    counterpart_id = "per-sample-relative"
    person_observation_id = "obs-sample-scholar-person-sample-relative"
    relation_observation_id = "obs-sample-scholar-relation-sample-relative"
    append_observation(root, observation(person_observation_id, "来源记录示例亲属。"))
    people_path = root / "canonical" / "people.jsonl"
    people = read_jsonl(people_path)
    people.append(
        {
            "person_id": counterpart_id,
            "subject_id": SUBJECT_ID,
            "id_namespace": SUBJECT,
            "canonical_name": "示例亲属",
            "name_forms": [
                {
                    "name_form_id": "name-sample-relative-primary",
                    "text": "示例亲属",
                    "kind": "primary",
                    "language": "zh-CN",
                    "script": "Hans",
                    "evidence_refs": [person_observation_id],
                    "certainty": "confirmed",
                }
            ],
            "role": "family",
            "evidence_refs": [person_observation_id],
            "status": "active",
        }
    )
    write_jsonl(people_path, people)
    append_decisions(
        root,
        admission("md-sample-scholar-person-sample-relative-admission", person_observation_id),
        resolution("md-sample-scholar-person-sample-relative-resolution", person_observation_id, counterpart_id),
    )
    append_observation(root, observation(relation_observation_id, "来源记录兄弟关系。"))
    relation_id = "rel-sample-scholar-brothers"
    write_jsonl(
        root / "canonical" / "relations.jsonl",
        [
            {
                "relation_id": relation_id,
                "subject_id": SUBJECT_ID,
                "id_namespace": SUBJECT,
                "relation_type": "siblings",
                "participants": [
                    {"person_id": SUBJECT_ID, "role": "elder_brother"},
                    {"person_id": SUBJECT_ID, "role": "younger_brother"},
                ],
                "person_ids": [SUBJECT_ID, counterpart_id],
                "evidence_refs": [relation_observation_id],
                "certainty": "confirmed",
                "status": "active",
            }
        ],
    )
    append_decisions(
        root,
        admission("md-sample-scholar-relation-sample-relative-admission", relation_observation_id),
        resolution("md-sample-scholar-relation-sample-relative-resolution", relation_observation_id, relation_id),
    )

    report = audit_store(root, mode="strict-data")

    assert {
        "RELATION_PARTICIPANTS_DUPLICATE",
        "RELATION_PARTICIPANTS_MISMATCH",
    }.issubset(issue_codes(report))


def test_coarse_event_date_cannot_claim_a_single_exact_boundary(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    add_event(root, "evt-sample-scholar-coarse-date", "obs-sample-scholar-coarse-date", "md-sample-scholar-coarse-date")
    path = root / "canonical" / "events.jsonl"
    rows = read_jsonl(path)
    rows[0]["date"].pop("end")
    write_jsonl(path, rows)

    report = audit_store(root, mode="strict-data")

    assert "EVENT_DATE_PRECISION_DISHONEST" in issue_codes(report)


def test_ancient_calendar_conversion_declares_normalized_target(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    event_id = "evt-sample-scholar-ancient-date"
    observation_id = "obs-sample-scholar-ancient-date"
    add_event(root, event_id, observation_id, "md-sample-scholar-ancient-date")
    path = root / "canonical" / "events.jsonl"
    rows = read_jsonl(path)
    rows[0]["date"] = {
        "calendar_system": "chinese_lunisolar",
        "original_text": "元丰五年七月既望",
        "display_label": "元丰五年七月既望",
        "start": "1082-08-12",
        "end": "1082-08-12",
        "precision": "day",
        "conversion": {
            "method": "合成历法换算",
            "basis_evidence_refs": [observation_id],
            "certainty": "probable",
        },
    }
    write_jsonl(path, rows)

    report = audit_store(root, mode="strict-data")

    assert "DATE_CONVERSION_TARGET_INVALID" in issue_codes(report)


def test_legacy_manifest_is_reported_as_migration_not_pass(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    write_json(
        root / "manifest.json",
        {
            "schema_version": "biography-store-manifest-v1",
            "subject": SUBJECT,
            "subject_id": SUBJECT_ID,
            "id_namespace": SUBJECT,
            "display_name": "示例学者",
            "latin_name": "Sample Scholar",
            "source_registry": {"ref": "source-registry.json"},
            "projection": {
                "asset_base": "/yiye-biography/assets",
                "asset_target": "assets",
            },
        },
    )

    report = audit_store(root, mode="audit")

    assert report.status == "MIGRATION_REQUIRED"
    assert "MANIFEST_SCHEMA_LEGACY" in issue_codes(report)
    assert not report.strict_ready
    assert audit_main(["audit", "--store-root", str(root), "--mode", "audit"]) == 0
    assert audit_main(["audit", "--store-root", str(root), "--mode", "strict-data"]) == 1


def test_legacy_store_requires_allowlist_and_rejects_real_semantic_errors(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    write_json(
        root / "manifest.json",
        {
            "schema_version": "biography-store-manifest-v1",
            "subject": SUBJECT,
            "subject_id": SUBJECT_ID,
            "id_namespace": SUBJECT,
            "display_name": "示例学者",
            "latin_name": "Sample Scholar",
            "source_registry": {"ref": "source-registry.json"},
            "projection": {"asset_target": "sample-scholar/assets"},
        },
    )

    with pytest.raises(ValueError, match="MANIFEST_SCHEMA_LEGACY"):
        assert_store_ready(root, phase="compile")

    with pytest.raises(ValueError, match="FORMAL_REVIEWER_UNREGISTERED"):
        assert_store_ready(
            root,
            phase="compile",
            legacy_subject_ids={SUBJECT_ID},
        )


def test_legacy_allowlist_accepts_only_reviewed_migration_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / SUBJECT
    root.mkdir()
    write_json(
        root / "manifest.json",
        {
            "schema_version": "biography-store-manifest-v1",
            "subject": SUBJECT,
            "subject_id": SUBJECT_ID,
            "id_namespace": SUBJECT,
        },
    )
    report = ContractAuditReport(
        str(root),
        "audit",
        SUBJECT,
        "biography-store-manifest-v1",
        [
            ContractIssue(
                "MANIFEST_SCHEMA_LEGACY",
                "旧人物需迁移至 v2",
                "manifest.json",
                "migration",
            )
        ],
    )
    monkeypatch.setattr(contract_module, "audit_store", lambda *_args, **_kwargs: report)

    accepted = contract_module.assert_store_ready(
        root,
        phase="compile",
        legacy_subject_ids={SUBJECT_ID},
    )

    assert accepted is report


@pytest.mark.parametrize(
    ("severity", "code"),
    [
        ("error", "SOURCE_SUBJECT_MISMATCH"),
        ("migration", "NEW_UNREVIEWED_MIGRATION_RULE"),
    ],
)
def test_legacy_allowlist_rejects_non_migration_or_unreviewed_findings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    severity: str,
    code: str,
) -> None:
    root = tmp_path / SUBJECT
    root.mkdir()
    write_json(
        root / "manifest.json",
        {
            "schema_version": "biography-store-manifest-v1",
            "subject": SUBJECT,
            "subject_id": SUBJECT_ID,
            "id_namespace": SUBJECT,
        },
    )
    report = ContractAuditReport(
        str(root),
        "audit",
        SUBJECT,
        "biography-store-manifest-v1",
        [ContractIssue(code, "必须由产品迁移审查显式接纳", "manifest.json", severity)],
    )
    monkeypatch.setattr(contract_module, "audit_store", lambda *_args, **_kwargs: report)

    with pytest.raises(ValueError, match=code):
        contract_module.assert_store_ready(
            root,
            phase="compile",
            legacy_subject_ids={SUBJECT_ID},
        )


@pytest.mark.parametrize(
    "unsafe_ref",
    [
        "canonical/events.jsonl:payload",
        "canonical\\events.jsonl",
        "CON/events.jsonl",
        "canonical/../events.jsonl",
    ],
)
def test_local_refs_reject_cross_platform_unsafe_syntax(
    tmp_path: Path,
    unsafe_ref: str,
) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    manifest_path = root / "manifest.json"
    manifest = read_json(manifest_path)
    manifest["canonical"]["events"] = unsafe_ref
    write_json(manifest_path, manifest)

    report = audit_store(root, mode="strict-data")

    assert "LOCAL_REF_INVALID" in issue_codes(report)


def test_corpus_never_reads_a_canonical_ref_outside_its_subject_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corpus_root = tmp_path / "corpus"
    su_shi_root, _ = build_two_subject_corpus(corpus_root)
    outside = tmp_path / "outside.jsonl"
    outside.write_text('{"event_id":"evt-cross-store"}\n', encoding="utf-8")
    manifest_path = su_shi_root / "manifest.json"
    manifest = read_json(manifest_path)
    manifest["canonical"]["events"] = "../../outside.jsonl"
    write_json(manifest_path, manifest)
    original_read_text = Path.read_text

    def guarded_read_text(path: Path, *args, **kwargs):
        if path.resolve() == outside.resolve():
            raise AssertionError("corpus audit attempted to read outside the subject store")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    report = audit_corpus(corpus_root, mode="audit")

    assert "LOCAL_REF_INVALID" in issue_codes(report)


def test_unknown_manifest_version_fails_closed_in_every_entrypoint(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    manifest = read_json(root / "manifest.json")
    manifest["schema_version"] = "biography-store-manifest-v3"
    write_json(root / "manifest.json", manifest)

    report = audit_store(root, mode="audit")

    assert report.fatal_count == 1
    assert "MANIFEST_SCHEMA_VERSION_UNSUPPORTED" in issue_codes(report)
    with pytest.raises(ValueError, match="不支持的 manifest.schema_version"):
        normalize_manifest(manifest, root_name=SUBJECT)
    with pytest.raises(ValueError, match="MANIFEST_SCHEMA_VERSION_UNSUPPORTED"):
        assert_store_ready(root, phase="compile")


def test_schema_document_is_meta_valid_and_registry_has_python_parity() -> None:
    schema_path = TOOL_ROOT.parent / "references" / "biography-contract-v0.9.0.schema.json"

    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    assert schema["$ref"] == "#/$defs/ManifestV2"
    expected = {
        "biography-store-manifest-v2": "ManifestV2",
        "biography-source-audit-v1": "SourceRegistryV1",
        "biography-observation-v2": "ObservationV2",
        "biography-merge-decision-v2": "MergeDecisionV2",
        "biography-external-verification-v1": "ExternalVerificationV1",
        "canonical:people": "CanonicalPersonV2",
        "canonical:events": "CanonicalEventV2",
        "canonical:works": "CanonicalWorkV2",
        "canonical:relations": "CanonicalRelationV2",
        "canonical:controversies": "CanonicalControversyV2",
        "canonical:quotes": "CanonicalQuoteV2",
    }
    assert set(expected.items()).issubset(SCHEMA_DEFINITION_REGISTRY.items())
    assert set(SCHEMA_DEFINITION_REGISTRY.values()).issubset(schema["$defs"])
    assert validate_schema_instance("ManifestV2", manifest_v2()) == []


def test_runtime_actually_applies_schema_registry(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    manifest_path = root / "manifest.json"
    manifest = read_json(manifest_path)
    manifest["unexpected_contract_escape"] = True
    write_json(manifest_path, manifest)
    decisions_path = root / "merge-decisions.jsonl"
    decisions = read_jsonl(decisions_path)
    decisions[0].pop("scope")
    write_jsonl(decisions_path, decisions)

    report = audit_store(root, mode="strict-data")

    assert {
        "SCHEMA_MANIFEST_INVALID",
        "SCHEMA_MERGE_DECISION_INVALID",
    }.issubset(issue_codes(report))


def test_schema_invalid_reference_arrays_report_without_crashing(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    registry_path = root / "source-registry.json"
    registry = read_json(registry_path)
    registry["source_units"][0]["observation_refs"] = None
    write_json(registry_path, registry)

    malformed_source = audit_store(root, mode="strict-data")
    assert {
        "SCHEMA_SOURCE_REGISTRY_INVALID",
        "SOURCE_OBSERVATION_BACKLINK_MISSING",
    }.issubset(issue_codes(malformed_source))

    registry["source_units"][0]["observation_refs"] = [OBS_PERSON]
    write_json(registry_path, registry)
    verification_id = "ver-sample-scholar-malformed"
    append_verification(root, external_verification(verification_id, SUBJECT_ID))
    people_path = root / "canonical" / "people.jsonl"
    people = read_jsonl(people_path)
    people[0]["verification_refs"] = [verification_id]
    write_jsonl(people_path, people)
    verifications = read_jsonl(root / "external-verifications.jsonl")
    verifications[0]["target_ids"] = None
    write_jsonl(root / "external-verifications.jsonl", verifications)

    malformed_verification = audit_store(root, mode="strict-data")
    assert {
        "SCHEMA_EXTERNAL_VERIFICATION_INVALID",
        "VERIFICATION_TARGETS_INVALID",
        "VERIFICATION_NOT_SIGNED",
    }.issubset(issue_codes(malformed_verification))


def test_publish_ready_requires_source_coverage_for_every_source(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    make_publish_ready(root)
    write_jsonl(root / "source-coverage-decisions.jsonl", [])

    report = audit_store(root, mode="publish-ready")

    assert "SOURCE_COVERAGE_DECISION_EXACT_ONCE" in issue_codes(report)


def test_source_coverage_rejects_duplicate_signed_dispositions(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    coverage_path = root / "source-coverage-decisions.jsonl"
    rows = read_jsonl(coverage_path)
    duplicate = dict(rows[0])
    duplicate["decision_id"] = "srcdec-sample-scholar-sample-duplicate"
    rows.append(duplicate)
    write_jsonl(coverage_path, rows)

    report = audit_store(root, mode="strict-data")

    assert "SOURCE_COVERAGE_DECISION_DUPLICATE" in issue_codes(report)


def test_source_coverage_rejects_unknown_source_target(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    append_ledger_row(
        root,
        "source-coverage-decisions",
        {
            "schema_version": "biography-source-coverage-decision-v1",
            "decision_id": "srcdec-sample-scholar-unknown",
            "subject_id": SUBJECT_ID,
            "id_namespace": SUBJECT,
            "source_id": "src-sample-scholar-does-not-exist",
            "disposition": "excluded",
            "review": formal_review(),
            "changeset_id": "cs-sample-scholar-c2-001",
            "status": "signed",
        },
    )

    report = audit_store(root, mode="strict-data")

    assert "SOURCE_COVERAGE_TARGET_MISSING" in issue_codes(report)


def test_work_classification_must_match_canonical_entity_level(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    add_active_work(root)
    path = root / "work-classifications.jsonl"
    rows = read_jsonl(path)
    rows[0]["entity_level"] = "textual_expression"
    write_jsonl(path, rows)

    report = audit_store(root, mode="strict-data")

    assert "WORK_CLASSIFICATION_LEVEL_MISMATCH" in issue_codes(report)


def test_work_cannot_belong_to_multiple_active_identity_clusters(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    work_id, _ = add_active_work(root)
    append_ledger_row(
        root,
        "work-identity-decisions",
        {
            "schema_version": "biography-work-identity-decision-v1",
            "decision_id": "workid-sample-scholar-second-cluster",
            "cluster_id": "workcluster-sample-scholar-second-cluster",
            "subject_id": SUBJECT_ID,
            "id_namespace": SUBJECT,
            "work_ids": [work_id],
            "disposition": "keep_separate",
            "review": formal_review(),
            "changeset_id": "cs-sample-scholar-c2-001",
            "status": "signed",
        },
    )

    report = audit_store(root, mode="strict-data")

    assert "WORK_IDENTITY_MULTI_CLUSTER" in issue_codes(report)


def test_quote_attribution_verdict_must_match_canonical_quote(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    add_active_quote(root)
    path = root / "quote-attribution-audits.jsonl"
    rows = read_jsonl(path)
    rows[0]["verdict"] = "probable"
    write_jsonl(path, rows)

    report = audit_store(root, mode="strict-data")

    assert "QUOTE_ATTRIBUTION_VERDICT_MISMATCH" in issue_codes(report)


def test_quote_attribution_evidence_must_exist(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    add_active_quote(root)
    path = root / "quote-attribution-audits.jsonl"
    rows = read_jsonl(path)
    rows[0]["evidence_refs"] = ["obs-sample-scholar-quote-missing"]
    write_jsonl(path, rows)

    report = audit_store(root, mode="strict-data")

    assert "QUOTE_ATTRIBUTION_EVIDENCE_MISSING" in issue_codes(report)


def test_quote_attribution_evidence_must_resolve_to_same_quote(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    add_active_quote(root)
    path = root / "quote-attribution-audits.jsonl"
    rows = read_jsonl(path)
    rows[0]["evidence_refs"] = [OBS_PERSON]
    write_jsonl(path, rows)

    report = audit_store(root, mode="strict-data")

    assert "QUOTE_ATTRIBUTION_EVIDENCE_UNDECIDED" in issue_codes(report)


def test_misattributed_quote_records_claimed_subject_not_factual_speaker(
    tmp_path: Path,
) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    quote_id, _ = add_active_quote(root)
    path = root / "canonical" / "quotes.jsonl"
    rows = read_jsonl(path)
    rows[0]["speaker"] = {"type": "unknown", "label": "真实说话者未确认"}
    rows[0]["attribution_status"] = "misattributed"
    rows[0]["claimed_speaker_ids"] = []
    write_jsonl(path, rows)
    audits_path = root / "quote-attribution-audits.jsonl"
    audits = read_jsonl(audits_path)
    audits[0]["verdict"] = "misattributed"
    write_jsonl(audits_path, audits)

    report = audit_store(root, mode="strict-data")

    assert "MISATTRIBUTED_QUOTE_CLAIM_MISSING" in issue_codes(report)
    assert quote_id in {issue.object_id for issue in report.issues}


def test_translation_form_must_link_to_the_base_text_form(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    quote_id, observation_id = add_active_quote(root)
    path = root / "canonical" / "quotes.jsonl"
    rows = read_jsonl(path)
    rows[0]["text_forms"].append(
        {
            "text_form_id": "qtext-sample-scholar-sample-translation",
            "kind": "translation",
            "text": "Synthetic quotation.",
            "language": "en",
            "script": "Latn",
            "base_text_form_id": "qtext-sample-scholar-missing-base",
            "translation_direction": "zh-CN->en",
            "locator": {
                "locator_type": "chapter_position",
                "value": "translation-sample",
            },
            "evidence_refs": [observation_id],
        }
    )
    write_jsonl(path, rows)

    report = audit_store(root, mode="strict-data")

    assert "QUOTE_TRANSLATION_BASE_MISSING" in issue_codes(report)
    assert quote_id in {issue.object_id for issue in report.issues}


def test_publish_ready_requires_one_prose_review_per_paragraph(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    make_publish_ready(root)
    write_jsonl(root / "prose-risk-reviews.jsonl", [])

    report = audit_store(root, mode="publish-ready")

    assert "PROSE_REVIEW_EXACT_ONCE" in issue_codes(report)


def test_publish_ready_rejects_duplicate_prose_reviews(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    make_publish_ready(root)
    path = root / "prose-risk-reviews.jsonl"
    rows = read_jsonl(path)
    duplicate = dict(rows[0])
    duplicate["review_id"] = "prosereview-sample-scholar-duplicate"
    rows.append(duplicate)
    write_jsonl(path, rows)

    report = audit_store(root, mode="publish-ready")

    assert "PROSE_REVIEW_EXACT_ONCE" in issue_codes(report)


def test_prose_review_evidence_must_be_inside_paragraph_evidence(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    make_publish_ready(root)
    add_event(
        root,
        "evt-sample-scholar-prose-outside",
        "obs-sample-scholar-prose-outside",
        "md-sample-scholar-prose-outside",
    )
    path = root / "prose-risk-reviews.jsonl"
    rows = read_jsonl(path)
    rows[0]["evidence_refs"] = ["obs-sample-scholar-prose-outside"]
    write_jsonl(path, rows)

    report = audit_store(root, mode="publish-ready")

    assert "PROSE_REVIEW_EVIDENCE_OUTSIDE_PARAGRAPH" in issue_codes(report)


def test_prose_review_hash_detects_reader_text_mutation(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    make_publish_ready(root)
    path = root / "editorial" / "chapters.json"
    chapters = read_json(path)
    chapters["chapters"][0]["paragraphs"][0]["text"] += "后来被改动。"
    write_json(path, chapters)

    report = audit_store(root, mode="publish-ready")

    assert "PROSE_REVIEW_TEXT_HASH_MISMATCH" in issue_codes(report)


def test_prose_review_must_be_approved_for_publication(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    make_publish_ready(root)
    path = root / "prose-risk-reviews.jsonl"
    rows = read_jsonl(path)
    rows[0]["verdict"] = "revise"
    write_jsonl(path, rows)

    report = audit_store(root, mode="publish-ready")

    assert "PROSE_REVIEW_NOT_APPROVED" in issue_codes(report)


def test_governed_row_requires_applied_changeset_receipt(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    path = root / "source-coverage-decisions.jsonl"
    rows = read_jsonl(path)
    rows[0]["changeset_id"] = "cs-sample-scholar-missing"
    write_jsonl(path, rows)

    report = audit_store(root, mode="strict-data")

    assert "CHANGESET_RECEIPT_MISSING" in issue_codes(report)


def test_changeset_receipt_hash_is_recomputed_from_its_artifact(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    row = read_jsonl(root / "changesets.jsonl")[0]
    (root / row["artifact_ref"]).write_text("tampered changeset\n", encoding="utf-8")

    report = audit_store(root, mode="strict-data")

    assert "CHANGESET_HASH_MISMATCH" in issue_codes(report)


def test_media_review_is_bound_to_metadata_and_publishable_authenticity(
    tmp_path: Path,
) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    add_media_asset(root, authenticity_status="unverified")
    make_publish_ready(root)
    manifest_path = root / "manifest.json"
    manifest = read_json(manifest_path)
    for descriptor in manifest["governance"]["ledgers"]:
        if descriptor["kind"] == "media_assets":
            descriptor["required_for_publication"] = True
    write_json(manifest_path, manifest)

    publish_report = audit_store(root, mode="publish-ready")
    assert "MEDIA_AUTHENTICITY_NOT_READY" in issue_codes(publish_report)

    path = root / "media-assets.jsonl"
    rows = read_jsonl(path)
    rows[0]["license"] = "metadata changed after review"
    write_jsonl(path, rows)
    changed_report = audit_store(root, mode="strict-data")
    assert "MEDIA_METADATA_HASH_MISMATCH" in issue_codes(changed_report)


def test_formal_review_recommendation_requires_provenance_row(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    path = root / "source-coverage-decisions.jsonl"
    rows = read_jsonl(path)
    rows[0]["review"]["recommendation_refs"] = ["rec-sample-scholar-missing"]
    write_jsonl(path, rows)

    report = audit_store(root, mode="strict-data")

    assert "RECOMMENDATION_PROVENANCE_MISSING" in issue_codes(report)


def test_recommendation_only_provenance_with_hashes_is_accepted(tmp_path: Path) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    recommendation_id = "rec-sample-scholar-glm53-sample"
    input_ref = "artifacts/recommendations/glm53-sample-input.json"
    response_ref = "artifacts/recommendations/glm53-sample-response.md"
    input_hash = write_artifact(root / input_ref, '{"scope":"coverage"}\n')
    response_hash = write_artifact(root / response_ref, "建议保留当前覆盖裁决。\n")
    append_ledger_row(
        root,
        "model-recommendations",
        {
            "schema_version": "biography-model-recommendation-v1",
            "recommendation_id": recommendation_id,
            "subject_id": SUBJECT_ID,
            "id_namespace": SUBJECT,
            "model": "glm-5.3",
            "role": "recommendation_only",
            "task": "审查合成来源覆盖决策",
            "input_scope_ref": input_ref,
            "input_scope_sha256": input_hash,
            "response_ref": response_ref,
            "response_sha256": response_hash,
            "created_at": "2026-08-23T00:00:00Z",
        },
    )
    path = root / "source-coverage-decisions.jsonl"
    rows = read_jsonl(path)
    rows[0]["review"]["recommendation_refs"] = [recommendation_id]
    write_jsonl(path, rows)

    report = audit_store(root, mode="strict-data")

    assert report.strict_ready, report.to_dict()
    (root / response_ref).write_text("响应在签署后被改写。\n", encoding="utf-8")
    tampered = audit_store(root, mode="strict-data")
    assert "RECOMMENDATION_RESPONSE_HASH_MISMATCH" in issue_codes(tampered)


def test_corpus_keeps_two_subject_stores_isolated(tmp_path: Path) -> None:
    corpus_root = tmp_path / "biography-corpus"
    build_two_subject_corpus(corpus_root)

    report = audit_corpus(corpus_root, mode="strict-data")

    assert report.strict_ready, report.to_dict()
    assert "CORPUS_CANONICAL_ID_COLLISION" not in issue_codes(report)


def test_corpus_rejects_cross_subject_canonical_id_collision(tmp_path: Path) -> None:
    corpus_root = tmp_path / "biography-corpus"
    _, other_scholar_root = build_two_subject_corpus(corpus_root)
    people_path = other_scholar_root / "canonical" / "people.jsonl"
    people = read_jsonl(people_path)
    people[0]["person_id"] = SUBJECT_ID
    write_jsonl(people_path, people)

    report = audit_corpus(corpus_root, mode="strict-data")

    assert "CORPUS_CANONICAL_ID_COLLISION" in issue_codes(report)


def test_corpus_rejects_store_present_on_disk_but_missing_from_registry(
    tmp_path: Path,
) -> None:
    corpus_root = tmp_path / "biography-corpus"
    _, other_scholar_root = build_two_subject_corpus(corpus_root)
    registry = read_json(corpus_root / "corpus.json")
    registry["subjects"] = [
        row for row in registry["subjects"] if row["store_ref"] != other_scholar_root.name
    ]
    write_json(corpus_root / "corpus.json", registry)

    report = audit_corpus(corpus_root, mode="strict-data")

    assert "CORPUS_STORE_UNREGISTERED" in issue_codes(report)


def test_public_cli_initializes_complete_v2_draft_and_compile_accepts_it(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sample-scholar"

    exit_code = audit_main(
        [
            "init",
            "--store-root",
            str(root),
            "--slug",
            "sample-scholar",
            "--subject-id",
            "per-sample-scholar",
            "--catalog-name",
            "Sample Scholar",
            "--language",
            "en",
        ]
    )

    assert exit_code == 0
    manifest = read_json(root / "manifest.json")
    assert manifest["schema_version"] == "biography-store-manifest-v2"
    assert {
        item["ref"] for item in manifest["governance"]["ledgers"]
    }.issubset(set(manifest["required_files"]))
    assert all((root / ref).is_file() for ref in manifest["required_files"])
    assert audit_main(
        ["verify", "--store-root", str(root), "--phase", "compile"]
    ) == 0


def test_public_cli_refuses_to_overwrite_nonempty_store_without_force(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sample-scholar"
    args = [
        "init",
        "--store-root",
        str(root),
        "--slug",
        "sample-scholar",
        "--subject-id",
        "per-sample-scholar",
        "--catalog-name",
        "Sample Scholar",
    ]

    assert audit_main(args) == 0
    manifest_before = (root / "manifest.json").read_bytes()
    assert audit_main(args) == 2
    assert (root / "manifest.json").read_bytes() == manifest_before


def test_public_cli_force_still_rejects_an_unrecognized_nonempty_directory(
    tmp_path: Path,
) -> None:
    root = tmp_path / "ordinary-directory"
    root.mkdir()
    marker = root / "keep.txt"
    marker.write_text("must survive\n", encoding="utf-8")

    exit_code = audit_main(
        [
            "init",
            "--store-root",
            str(root),
            "--slug",
            "sample-scholar",
            "--subject-id",
            "per-sample-scholar",
            "--catalog-name",
            "Sample Scholar",
            "--force",
        ]
    )

    assert exit_code == 2
    assert marker.read_text(encoding="utf-8") == "must survive\n"
    assert not (root / "manifest.json").exists()


def test_public_cli_rejects_abbreviated_long_options(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        audit_main(
            [
                "audit",
                "--store-ro",
                str(tmp_path / "sample-scholar"),
            ]
        )


def test_public_cli_force_rejects_invalid_or_changed_stable_subject_id(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sample-scholar"
    args = [
        "init",
        "--store-root",
        str(root),
        "--slug",
        "sample-scholar",
        "--subject-id",
        "per-sample-scholar",
        "--catalog-name",
        "Sample Scholar",
    ]
    assert audit_main(args) == 0
    before = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }

    invalid = [*args]
    invalid[invalid.index("per-sample-scholar")] = "bad id"
    invalid.append("--force")
    assert audit_main(invalid) == 2

    changed = [*args]
    changed[changed.index("per-sample-scholar")] = "per-other-scholar"
    changed.append("--force")
    assert audit_main(changed) == 2
    after = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_v2_missing_canonical_declarations_cannot_masquerade_as_empty_draft(
    tmp_path: Path,
) -> None:
    root = build_sparse_second_subject(tmp_path / SUBJECT)
    manifest_path = root / "manifest.json"
    manifest = read_json(manifest_path)
    manifest["canonical"] = {}
    write_json(manifest_path, manifest)

    with pytest.raises(ValueError, match="CANONICAL|LOCAL_REF|SCHEMA_MANIFEST"):
        assert_store_ready(root, phase="compile")

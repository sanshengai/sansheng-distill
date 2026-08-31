#!/usr/bin/env python3
"""Biography contract v0.9.0-candidate semantic audit.

The JSON Schema owns single-document shape.  This module is the one semantic
predicate shared by the CLI and tests: cross-file closure, signed evidence,
redirect topology, formal reviewer authority, relation closure and resource
isolation.  It is deliberately read-only.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from copy import deepcopy
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


CONTRACT_VERSION = "0.9.0-candidate"
MANIFEST_V1 = "biography-store-manifest-v1"
MANIFEST_V2 = "biography-store-manifest-v2"
MERGE_DECISION_V2 = "biography-merge-decision-v2"
LEGACY_V1_MIGRATION_CODES = frozenset(
    {
        "ASSET_NAMESPACE_REQUIRED",
        "ASSET_TARGET_NAMESPACE_REQUIRED",
        "CANONICAL_ENVELOPE_V2_REQUIRED",
        "CANONICAL_PATHS_REQUIRED",
        "CSS_SCOPE_REQUIRED",
        "DECISION_OBSERVATIONS_INVALID",
        "EVIDENCE_NOT_DECIDED",
        "GOVERNANCE_DECLARATION_REQUIRED",
        "INTERPRETATION_NOT_DECIDED",
        "MANIFEST_SCHEMA_LEGACY",
        "MERGED_INTO_FORBIDDEN",
        "MERGE_DECISION_V2_REQUIRED",
        "NAME_FORMS_REQUIRED",
        "OBSERVATION_ENVELOPE_V2_REQUIRED",
        "RELATION_ENDPOINTS_INCOMPLETE",
    }
)
WINDOWS_RESERVED_BASENAMES = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{index}" for index in range(1, 10)}
    | {f"lpt{index}" for index in range(1, 10)}
)
SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "references"
    / "biography-contract-v0.9.0.schema.json"
)
SCHEMA_DEFINITION_REGISTRY = {
    "biography-corpus-v1": "BiographyCorpusV1",
    "biography-store-manifest-v2": "ManifestV2",
    "biography-source-audit-v1": "SourceRegistryV1",
    "biography-observation-v2": "ObservationV2",
    "biography-merge-decision-v2": "MergeDecisionV2",
    "biography-external-verification-v1": "ExternalVerificationV1",
    "biography-source-coverage-decision-v1": "SourceCoverageDecisionV1",
    "biography-work-classification-v1": "WorkClassificationV1",
    "biography-work-identity-decision-v1": "WorkIdentityDecisionV1",
    "biography-quote-attribution-audit-v1": "QuoteAttributionAuditV1",
    "biography-prose-risk-review-v1": "ProseRiskReviewV1",
    "biography-changeset-v1": "ChangeSetV1",
    "biography-model-recommendation-v1": "ModelRecommendationV1",
    "biography-media-asset-v1": "MediaAssetV1",
    "canonical:people": "CanonicalPersonV2",
    "canonical:events": "CanonicalEventV2",
    "canonical:works": "CanonicalWorkV2",
    "canonical:relations": "CanonicalRelationV2",
    "canonical:controversies": "CanonicalControversyV2",
    "canonical:quotes": "CanonicalQuoteV2",
}


def local_ref_error(ref: Any) -> str | None:
    """Return why a store-local reference is unsafe, or ``None`` when safe.

    Contract references deliberately use POSIX separators on every platform.
    Besides traversal and absolute paths, this rejects Windows ADS syntax and
    reserved device names so a corpus authored on another OS cannot become
    unsafe only when it reaches a Windows publisher.
    """

    if not isinstance(ref, str) or not ref.strip():
        return "empty reference"
    if any(ord(character) < 32 for character in ref):
        return "control character"
    if "\\" in ref:
        return "backslash separator"
    if ":" in ref:
        return "colon or Windows ADS syntax"
    if ref.startswith("/") or ref.startswith("//"):
        return "absolute path"
    parts = PurePosixPath(ref).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        return "empty, current, or parent path segment"
    for part in parts:
        normalized = part.rstrip(" .")
        if not normalized or normalized.casefold().split(".", 1)[0] in WINDOWS_RESERVED_BASENAMES:
            return "Windows reserved path segment"
    return None


def paragraph_text_sha256(paragraph: dict[str, Any]) -> str:
    """Hash the exact reader-visible paragraph text reviewed by a human."""

    text = paragraph.get("text")
    if not isinstance(text, str):
        text = ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def governed_record_sha256(record: dict[str, Any]) -> str:
    """Hash a governed row without its self-referential metadata hash."""

    payload = {
        key: value
        for key, value in record.items()
        if key not in {"metadata_sha256", "__contract_line__"}
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

CANONICAL_KINDS = (
    "people",
    "events",
    "works",
    "relations",
    "controversies",
    "quotes",
)
ID_FIELDS = {
    "people": "person_id",
    "events": "event_id",
    "works": "work_id",
    "relations": "relation_id",
    "controversies": "controversy_id",
    "quotes": "quote_id",
}
ID_PREFIXES = {
    "people": "per",
    "events": "evt",
    "works": "work",
    "relations": "rel",
    "controversies": "ctr",
    "quotes": "quote",
}
DEFAULT_CANONICAL_REFS = {
    kind: f"canonical/{filename}"
    for kind, filename in {
        "people": "people.jsonl",
        "events": "events.jsonl",
        "works": "works.jsonl",
        "relations": "relations.jsonl",
        "controversies": "controversies.jsonl",
        "quotes": "quotes.jsonl",
    }.items()
}
DEFAULT_EDITORIAL_REFS = {
    "chapter_order": "editorial/chapter_order.json",
    "chapters": "editorial/chapters.json",
    "overview": "editorial/overview.json",
    "layout": "editorial/layout.json",
    "dossier": "editorial/dossier.json",
}
LEGACY_LEDGER_REFS = {
    "observations": "observations.jsonl",
    "merge_decisions": "merge-decisions.jsonl",
    "external_verifications": "external-verifications.jsonl",
    "source_coverage_decisions": "source-coverage-decisions.jsonl",
    "work_classifications": "work-classifications.jsonl",
    "work_duplicate_decisions": "work-duplicate-decisions.jsonl",
    "work_identity_decisions": "work-identity-decisions.jsonl",
    "quote_attribution_audits": "quote-attribution-audits.jsonl",
    "prose_risk_reviews": "prose-risk-reviews.jsonl",
    "changesets": "changesets.jsonl",
    "model_recommendations": "model-recommendations.jsonl",
    "media_assets": "media-assets.jsonl",
}
REQUIRED_LEDGER_KINDS = {
    "observations",
    "merge_decisions",
    "external_verifications",
    "changesets",
}
LEGACY_REQUIRED_LEDGER_KINDS = {
    "observations",
    "merge_decisions",
    "external_verifications",
}
LEDGER_SCHEMA_VERSIONS = {
    "observations": "biography-observation-v2",
    "merge_decisions": "biography-merge-decision-v2",
    "external_verifications": "biography-external-verification-v1",
    "source_coverage_decisions": "biography-source-coverage-decision-v1",
    "work_classifications": "biography-work-classification-v1",
    "work_identity_decisions": "biography-work-identity-decision-v1",
    "quote_attribution_audits": "biography-quote-attribution-audit-v1",
    "prose_risk_reviews": "biography-prose-risk-review-v1",
    "changesets": "biography-changeset-v1",
    "model_recommendations": "biography-model-recommendation-v1",
    "media_assets": "biography-media-asset-v1",
}
KNOWN_LEDGER_KINDS = set(LEGACY_LEDGER_REFS)
ADMISSION_VERDICTS = {"accept", "hold", "reject"}
RESOLUTION_VERDICTS = {
    "adopt",
    "create",
    "enrich",
    "correct",
    "merge",
    "source_only",
}
LEGACY_ACCEPTED_VERDICTS = {"create", "enrich", "correct", "duplicate", "merge"}
CANONICAL_STATUSES = {"active", "hold", "merged_redirect"}
NAME_FORM_KINDS = {
    "primary",
    "native",
    "romanized",
    "alias",
    "birth_name",
    "courtesy_name",
    "art_name",
    "posthumous_name",
    "pseudonym",
}
MODEL_REVIEWER_RE = re.compile(
    r"(?:\bglm(?:[-_. ]?\d+(?:\.\d+)*)?\b|\bdeepseek\b|\bgpt(?:[-_. ]?\d+)?\b|"
    r"\bclaude\b|\bgemini\b|\bllm\b|\blanguage[-_ ]?model\b)",
    re.IGNORECASE,
)
SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
SCRIPT_RE = re.compile(r"[A-Z][a-z]{3}\Z")
SHA256_RE = re.compile(r"[a-f0-9]{64}\Z")


def manifest_v2_skeleton(
    slug: str,
    subject_id: str,
    catalog_name: str,
    *,
    language: str = "zh-CN",
    content_version: str = "0.0.0",
) -> dict[str, Any]:
    """Return the single public v2 bootstrap manifest.

    ``catalog_name`` is a draft bootstrap hint only.  Before publication the
    semantic audit requires it to equal the subject Person's primary name.
    """

    canonical = deepcopy(DEFAULT_CANONICAL_REFS)
    editorial = {
        **deepcopy(DEFAULT_EDITORIAL_REFS),
        "media": "editorial/media.json",
    }
    ledgers = [
        {
            "kind": kind,
            "ref": LEGACY_LEDGER_REFS[kind],
            "schema_version": LEDGER_SCHEMA_VERSIONS[kind],
            "required_for_publication": kind
            in {
                "observations",
                "merge_decisions",
                "external_verifications",
                "source_coverage_decisions",
                "changesets",
            },
        }
        for kind in (
            "observations",
            "merge_decisions",
            "external_verifications",
            "source_coverage_decisions",
            "work_classifications",
            "work_identity_decisions",
            "quote_attribution_audits",
            "prose_risk_reviews",
            "changesets",
            "model_recommendations",
            "media_assets",
        )
    ]
    required_files = [
        "source-registry.json",
        *[item["ref"] for item in ledgers],
        *canonical.values(),
        *editorial.values(),
    ]
    return {
        "schema_version": MANIFEST_V2,
        "biography_contract_version": CONTRACT_VERSION,
        "subject": {
            "slug": slug,
            "subject_id": subject_id,
            "id_namespace": slug,
            "language": language,
            "legacy_object_ids": [],
            "id_aliases": [],
        },
        "content_version": content_version,
        "canonical": canonical,
        "editorial": editorial,
        "governance": {
            "formal_reviewers": [
                {"reviewer_id": "main-agent", "authority": "main_agent"}
            ],
            "source_registry": {
                "ref": "source-registry.json",
                "schema_version": "biography-source-audit-v1",
            },
            "ledgers": ledgers,
        },
        "projection": {
            "projection_id": f"projection-{slug}-store",
            "canonical_library_id": f"canonical-{slug}-store",
            "route_base": f"/tools/biography/{slug}/",
            "asset_base": f"/yiye-biography/{slug}/assets/",
            "asset_target": f"{slug}/assets",
            "css_scope": f'[data-biography-subject="{slug}"]',
            "dossier_config_ref": "editorial/dossier.json",
            "shared_resources": [],
        },
        "publication": {
            "status": "draft",
            "href": None,
            "catalog_name": catalog_name,
            "catalog_summary": "",
        },
        "required_files": required_files,
    }


def normalize_manifest(manifest: dict[str, Any], root_name: str | None = None) -> dict[str, Any]:
    """Return a compatibility view consumed by legacy product adapters.

    The returned object is detached from the input.  Durable v2 data remains
    nested; flat keys are derived conveniences, never a second source of truth.
    """

    if not isinstance(manifest, dict):
        raise ValueError("manifest 必须是 JSON 对象")
    normalized = deepcopy(manifest)
    manifest_version = manifest.get("schema_version")
    if manifest_version == MANIFEST_V1:
        if root_name and manifest.get("subject") != root_name:
            raise ValueError("manifest.subject 与人物目录名不一致")
        return normalized
    if manifest_version != MANIFEST_V2:
        raise ValueError(f"不支持的 manifest.schema_version：{manifest_version!r}")
    subject = manifest.get("subject")
    if not isinstance(subject, dict):
        raise ValueError("manifest v2 缺 subject 对象")
    slug = subject.get("slug")
    if root_name and slug != root_name:
        raise ValueError("manifest.subject.slug 与人物目录名不一致")
    normalized["subject_v2"] = deepcopy(subject)
    normalized["subject"] = slug
    normalized["subject_id"] = subject.get("subject_id")
    normalized["id_namespace"] = subject.get("id_namespace")
    normalized["language"] = subject.get("language")
    normalized["subject_content_version"] = manifest.get("content_version")
    governance = manifest.get("governance") or {}
    source_descriptor = deepcopy(governance.get("source_registry") or {})
    source_descriptor.setdefault("subject_id", subject.get("subject_id"))
    normalized["source_registry"] = source_descriptor
    projection = deepcopy(manifest.get("projection") or {})
    editorial = manifest.get("editorial") or {}
    projection.setdefault("dossier_config_ref", editorial.get("dossier"))
    projection.setdefault("media_ledger_ref", editorial.get("media"))
    normalized["projection"] = projection
    normalized.setdefault("required_files", _declared_required_files(manifest))
    return normalized


def _declared_required_files(manifest: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    governance = manifest.get("governance") or {}
    registry = governance.get("source_registry") or {}
    if isinstance(registry.get("ref"), str):
        refs.append(registry["ref"])
    for group in ("canonical", "editorial"):
        values = manifest.get(group) or {}
        if isinstance(values, dict):
            refs.extend(value for value in values.values() if isinstance(value, str))
    for item in governance.get("ledgers", []) if isinstance(governance, dict) else []:
        if isinstance(item, dict) and isinstance(item.get("ref"), str):
            refs.append(item["ref"])
    return list(dict.fromkeys(refs))


@lru_cache(maxsize=1)
def _contract_schema() -> dict[str, Any]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def _schema_instance(value: Any) -> Any:
    """Remove read-only loader metadata before applying the public schema."""

    if isinstance(value, dict):
        return {
            key: _schema_instance(item)
            for key, item in value.items()
            if not key.startswith("__contract_")
        }
    if isinstance(value, list):
        return [_schema_instance(item) for item in value]
    return value


def validate_schema_instance(definition: str, instance: Any) -> list[str]:
    """Validate one registry definition and return stable, human-readable errors."""

    schema = _contract_schema()
    if definition not in schema.get("$defs", {}):
        raise KeyError(f"unknown biography schema definition: {definition}")
    wrapper = {
        "$schema": schema["$schema"],
        "$defs": schema["$defs"],
        "$ref": f"#/$defs/{definition}",
    }
    validator = Draft202012Validator(wrapper, format_checker=FormatChecker())
    errors: list[str] = []
    for error in sorted(
        validator.iter_errors(_schema_instance(instance)),
        key=lambda item: (
            tuple(str(part) for part in item.absolute_path),
            item.message,
        ),
    ):
        pointer = "/".join(str(part) for part in error.absolute_path)
        errors.append(f"{pointer or '$'}: {error.message}")
    return errors


@dataclass(frozen=True)
class ContractIssue:
    code: str
    message: str
    path: str
    severity: str = "error"  # migration | error | fatal
    object_id: str | None = None


@dataclass
class ContractAuditReport:
    store_root: str
    mode: str
    subject: str | None
    manifest_schema_version: str | None
    issues: list[ContractIssue] = field(default_factory=list)

    @property
    def strict_ready(self) -> bool:
        return not self.issues

    @property
    def publish_ready(self) -> bool:
        return self.mode == "publish-ready" and not self.issues

    @property
    def fatal_count(self) -> int:
        return sum(issue.severity == "fatal" for issue in self.issues)

    @property
    def status(self) -> str:
        if self.fatal_count:
            return "AUDIT_FAILED"
        if self.issues:
            if any(issue.severity == "migration" for issue in self.issues):
                return "MIGRATION_REQUIRED"
            return "PUBLISH_BLOCKED" if self.mode == "publish-ready" else "STRICT_DATA_FAILED"
        return "PUBLISH_READY" if self.mode == "publish-ready" else "STRICT_DATA_READY"

    def counts(self) -> dict[str, int]:
        values = Counter(issue.severity for issue in self.issues)
        return {name: values.get(name, 0) for name in ("migration", "error", "fatal")}

    def code_counts(self) -> dict[str, int]:
        return dict(sorted(Counter(issue.code for issue in self.issues).items()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": CONTRACT_VERSION,
            "store_root": self.store_root,
            "mode": self.mode,
            "subject": self.subject,
            "manifest_schema_version": self.manifest_schema_version,
            "status": self.status,
            "strict_ready": self.strict_ready,
            "publish_ready": self.publish_ready,
            "counts": self.counts(),
            "code_counts": self.code_counts(),
            "issues": [asdict(issue) for issue in self.issues],
        }


def _normalized_name(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _is_model_reviewer(value: Any) -> bool:
    return isinstance(value, str) and bool(MODEL_REVIEWER_RE.search(value))


def _is_iso_datetime(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


class _Auditor:
    def __init__(self, store_root: Path, mode: str) -> None:
        self.root = store_root.resolve()
        self.mode = mode
        self.issues: list[ContractIssue] = []
        self._issue_keys: set[tuple[str, str, str | None]] = set()
        self.manifest: dict[str, Any] = {}
        self.manifest_version: str | None = None
        self.is_v2 = False
        self.subject: str | None = None
        self.subject_id: str | None = None
        self.namespace: str | None = None
        self.canonical: dict[str, dict[str, dict[str, Any]]] = {
            kind: {} for kind in CANONICAL_KINDS
        }
        self.all_ids: dict[str, str] = {}
        self.observations: dict[str, dict[str, Any]] = {}
        self.decisions: list[dict[str, Any]] = []
        self.ledger_rows: dict[str, list[dict[str, Any]]] = {}
        self.coverage: dict[str, set[str]] = defaultdict(set)
        self.legacy_id_aliases: dict[str, str] = {}
        self.id_aliases: list[dict[str, Any]] = []
        self.formal_reviewers: dict[str, str] = {}
        self.source_units: dict[str, dict[str, Any]] = {}
        self.verifications: dict[str, dict[str, Any]] = {}
        self.signed_verification_ids: set[str] = set()
        self.signed_admissions: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.signed_resolutions: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.target_resolutions: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.superseded_resolutions: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def add(
        self,
        code: str,
        message: str,
        path: str,
        *,
        severity: str = "error",
        object_id: str | None = None,
    ) -> None:
        key = (code, path, object_id)
        if key in self._issue_keys:
            return
        self._issue_keys.add(key)
        self.issues.append(
            ContractIssue(
                code=code,
                message=message,
                path=path,
                severity=severity,
                object_id=object_id,
            )
        )

    def audit_schema(
        self,
        definition: str,
        value: Any,
        code: str,
        path: str,
        *,
        object_id: str | None = None,
    ) -> bool:
        try:
            errors = validate_schema_instance(definition, value)
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError) as error:
            self.add(
                "SCHEMA_REGISTRY_UNAVAILABLE",
                f"契约 schema registry 无法使用：{error}",
                str(SCHEMA_PATH),
                severity="fatal",
            )
            return False
        if errors:
            detail = "; ".join(errors[:3])
            if len(errors) > 3:
                detail += f"；另有 {len(errors) - 3} 项"
            self.add(code, detail, path, object_id=object_id)
            return False
        return True

    def rel(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return str(path)

    def resolve_ref(self, ref: Any, owner: str) -> Path | None:
        violation = local_ref_error(ref)
        if violation is not None:
            self.add(
                "LOCAL_REF_INVALID",
                f"人物内文件指针不安全（{violation}）：{ref!r}",
                owner,
            )
            return None
        assert isinstance(ref, str)
        raw = Path(ref)
        candidate = (self.root / raw).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError:
            self.add("LOCAL_REF_ESCAPE", f"人物内文件指针越过 store：{ref!r}", owner)
            return None
        return candidate

    def load_json(self, path: Path, *, required: bool = True) -> Any:
        if not path.exists():
            if required:
                self.add("REQUIRED_FILE_MISSING", "必需文件不存在", self.rel(path))
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            self.add(
                "JSON_UNREADABLE",
                f"JSON 无法读取：{error}",
                self.rel(path),
                severity="fatal",
            )
            return None

    def load_jsonl(self, path: Path, *, required: bool = True) -> list[dict[str, Any]]:
        if not path.exists():
            if required:
                self.add("REQUIRED_FILE_MISSING", "必需 JSONL 不存在", self.rel(path))
            return []
        rows: list[dict[str, Any]] = []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as error:
            self.add(
                "JSONL_UNREADABLE",
                f"JSONL 无法读取：{error}",
                self.rel(path),
                severity="fatal",
            )
            return []
        for line_no, raw in enumerate(lines, start=1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as error:
                self.add(
                    "JSONL_PARSE_ERROR",
                    f"第 {line_no} 行 JSON 无法解析：{error}",
                    self.rel(path),
                    severity="fatal",
                    object_id=str(line_no),
                )
                continue
            if not isinstance(row, dict):
                self.add(
                    "JSONL_ROW_NOT_OBJECT",
                    f"第 {line_no} 行不是对象",
                    self.rel(path),
                    severity="fatal",
                    object_id=str(line_no),
                )
                continue
            row["__contract_line__"] = line_no
            rows.append(row)
        return rows

    def run(self) -> ContractAuditReport:
        if not self.root.is_dir():
            self.add(
                "STORE_ROOT_MISSING",
                "人物 store 目录不存在",
                str(self.root),
                severity="fatal",
            )
            return self.report()

        manifest_path = self.root / "manifest.json"
        loaded = self.load_json(manifest_path)
        if not isinstance(loaded, dict):
            if loaded is not None:
                self.add(
                    "MANIFEST_NOT_OBJECT",
                    "manifest 必须是 JSON 对象",
                    "manifest.json",
                    severity="fatal",
                )
            return self.report()
        self.manifest = loaded
        self.manifest_version = loaded.get("schema_version")
        self.is_v2 = self.manifest_version == MANIFEST_V2

        if self.manifest_version not in {MANIFEST_V1, MANIFEST_V2}:
            self.add(
                "MANIFEST_SCHEMA_VERSION_UNSUPPORTED",
                f"不支持的 manifest.schema_version：{self.manifest_version!r}",
                "manifest.json",
                severity="fatal",
            )
            return self.report()

        if self.is_v2:
            self.audit_schema(
                SCHEMA_DEFINITION_REGISTRY[MANIFEST_V2],
                self.manifest,
                "SCHEMA_MANIFEST_INVALID",
                "manifest.json",
            )
            self.audit_manifest_v2()
        else:
            self.audit_manifest_legacy()

        canonical_refs = self.canonical_refs()
        editorial_refs = self.editorial_refs()
        ledger_refs = self.ledger_refs()
        self.audit_declared_files(canonical_refs, editorial_refs, ledger_refs)
        self.load_canonical(canonical_refs)
        self.load_ledgers(ledger_refs)
        self.audit_governance_ledgers()
        self.audit_source_registry()
        self.audit_source_coverage_decisions()
        self.audit_observations()
        self.audit_merge_decisions()
        self.audit_canonical_envelopes()
        self.audit_redirects()
        self.audit_public_aliases()
        self.audit_reference_closure()
        self.audit_temporal_semantics()
        self.audit_source_locators()
        self.audit_work_identity()
        self.audit_quote_semantics()
        self.audit_controversy_positions()
        self.audit_media_assets()
        self.audit_changesets_and_recommendations()
        self.audit_external_verifications()
        self.audit_source_backlinks()
        self.audit_evidence_closure()
        if self.mode == "publish-ready":
            self.audit_publish_ready(editorial_refs)
        return self.report()

    def report(self) -> ContractAuditReport:
        return ContractAuditReport(
            store_root=str(self.root),
            mode=self.mode,
            subject=self.subject,
            manifest_schema_version=self.manifest_version,
            issues=sorted(
                self.issues,
                key=lambda issue: (
                    {"fatal": 0, "error": 1, "migration": 2}.get(issue.severity, 9),
                    issue.code,
                    issue.path,
                    issue.object_id or "",
                ),
            ),
        )

    def audit_manifest_legacy(self) -> None:
        self.subject = self.manifest.get("subject")
        self.subject_id = self.manifest.get("subject_id")
        self.namespace = self.manifest.get("id_namespace")
        self.add(
            "MANIFEST_SCHEMA_LEGACY",
            f"现役 manifest 是 {self.manifest_version!r}，需迁移为 {MANIFEST_V2}",
            "manifest.json",
            severity="migration",
        )
        self.add(
            "NAME_FORMS_REQUIRED",
            "v1 的 display_name/latin_name 需迁移为带类型、语言和 script 的 name_forms",
            "manifest.json",
            severity="migration",
        )
        self.add(
            "GOVERNANCE_DECLARATION_REQUIRED",
            "治理账本需在 manifest v2 显式声明，不能靠约定文件名发现",
            "manifest.json",
            severity="migration",
        )
        self.add(
            "CANONICAL_PATHS_REQUIRED",
            "Canonical 与 Editorial 文件映射需进入 manifest v2",
            "manifest.json",
            severity="migration",
        )
        if not isinstance(self.subject, str) or not SLUG_RE.fullmatch(self.subject):
            self.add("SUBJECT_SLUG_INVALID", "legacy manifest subject slug 不合规", "manifest.json")
        elif self.root.name != self.subject:
            self.add(
                "SUBJECT_DIRECTORY_MISMATCH",
                f"目录 {self.root.name!r} 与 manifest subject {self.subject!r} 不一致",
                "manifest.json",
            )
        if self.namespace != self.subject:
            self.add(
                "SUBJECT_NAMESPACE_MISMATCH",
                "legacy manifest id_namespace 必须与 subject 一致",
                "manifest.json",
            )
        if not isinstance(self.subject_id, str) or not self.subject_id:
            self.add("SUBJECT_ID_INVALID", "legacy manifest 缺 subject_id", "manifest.json")
        projection = self.manifest.get("projection")
        if not isinstance(projection, dict):
            projection = {}
        asset_base = projection.get("asset_base")
        asset_target = projection.get("asset_target")
        if self.subject and (
            not isinstance(asset_base, str)
            or f"/{self.subject}/" not in f"{asset_base.rstrip('/')}/"
        ):
            self.add(
                "ASSET_NAMESPACE_REQUIRED",
                "人物自有 asset_base 未包含 subject namespace",
                "manifest.json#/projection/asset_base",
                severity="migration",
            )
        if self.subject and (
            not isinstance(asset_target, str)
            or not asset_target.replace("\\", "/").startswith(f"{self.subject}/")
        ):
            self.add(
                "ASSET_TARGET_NAMESPACE_REQUIRED",
                "人物自有 asset_target 未以 subject namespace 开头",
                "manifest.json#/projection/asset_target",
                severity="migration",
            )
        self.add(
            "CSS_SCOPE_REQUIRED",
            "manifest v2 必须声明含 subject namespace 的 css_scope",
            "manifest.json#/projection",
            severity="migration",
        )

    def audit_manifest_v2(self) -> None:
        if self.manifest.get("biography_contract_version") != CONTRACT_VERSION:
            self.add(
                "CONTRACT_VERSION_MISMATCH",
                f"biography_contract_version 必须是 {CONTRACT_VERSION}",
                "manifest.json",
            )
        if "latin_name" in self.manifest:
            self.add(
                "LATIN_NAME_RETIRED",
                "manifest v2 不允许 latin_name；使用主人物 Canonical Person.name_forms",
                "manifest.json",
            )
        subject = self.manifest.get("subject")
        if not isinstance(subject, dict):
            self.add("SUBJECT_V2_MISSING", "manifest v2 缺 subject 对象", "manifest.json")
            return
        self.subject = subject.get("slug")
        self.subject_id = subject.get("subject_id")
        self.namespace = subject.get("id_namespace")
        if not isinstance(self.subject, str) or not SLUG_RE.fullmatch(self.subject):
            self.add("SUBJECT_SLUG_INVALID", "subject.slug 不合规", "manifest.json#/subject")
        elif self.root.name != self.subject:
            self.add(
                "SUBJECT_DIRECTORY_MISMATCH",
                f"目录 {self.root.name!r} 与 subject.slug {self.subject!r} 不一致",
                "manifest.json#/subject",
            )
        if self.namespace != self.subject:
            self.add(
                "SUBJECT_NAMESPACE_MISMATCH",
                "subject.id_namespace 必须与 subject.slug 一致",
                "manifest.json#/subject",
            )
        if not isinstance(self.subject_id, str) or not self.subject_id:
            self.add("SUBJECT_ID_INVALID", "subject.subject_id 不能为空", "manifest.json#/subject")
        legacy_ids = subject.get("legacy_object_ids", [])
        if isinstance(legacy_ids, list):
            for index, alias in enumerate(legacy_ids):
                if not isinstance(alias, dict):
                    continue
                alias_id = alias.get("id")
                kind = alias.get("kind")
                path = f"manifest.json#/subject/legacy_object_ids/{index}"
                if isinstance(alias_id, str) and kind in CANONICAL_KINDS:
                    if alias_id in self.legacy_id_aliases:
                        self.add("LEGACY_ID_ALIAS_DUPLICATE", f"历史 ID 重复声明：{alias_id}", path)
                    else:
                        self.legacy_id_aliases[alias_id] = kind
        aliases = subject.get("id_aliases", [])
        if isinstance(aliases, list):
            seen_aliases: set[str] = set()
            for index, alias in enumerate(aliases):
                path = f"manifest.json#/subject/id_aliases/{index}"
                if not isinstance(alias, dict):
                    continue
                alias_id = alias.get("alias_id")
                if not isinstance(alias_id, str) or not alias_id:
                    continue
                if alias_id in seen_aliases:
                    self.add("ID_ALIAS_DUPLICATE", f"跳转别名重复声明：{alias_id}", path)
                seen_aliases.add(alias_id)
                self.id_aliases.append(alias)
        required_files = self.manifest.get("required_files")
        derived_files = set(_declared_required_files(self.manifest))
        if not isinstance(required_files, list):
            self.add("REQUIRED_FILES_INVALID", "manifest.required_files 必须是数组", "manifest.json")
        else:
            missing = derived_files - set(value for value in required_files if isinstance(value, str))
            extra = set(value for value in required_files if isinstance(value, str)) - derived_files
            if missing:
                self.add(
                    "REQUIRED_FILES_INCOMPLETE",
                    f"required_files 漏掉声明文件：{sorted(missing)}",
                    "manifest.json#/required_files",
                )
            if extra:
                self.add(
                    "REQUIRED_FILES_UNDECLARED",
                    f"required_files 含无归属文件：{sorted(extra)}",
                    "manifest.json#/required_files",
                )
        self.audit_governance_manifest()
        self.audit_projection_v2()

    def audit_name_forms(
        self,
        forms: Any,
        path: str,
        *,
        require_secondary: bool = False,
        object_id: str | None = None,
    ) -> None:
        if not isinstance(forms, list) or not forms:
            self.add("NAME_FORMS_REQUIRED", "name_forms 必须是非空数组", path, object_id=object_id)
            return
        primary_count = 0
        secondary_count = 0
        seen: dict[str, int] = {}
        seen_ids: set[str] = set()
        for index, form in enumerate(forms):
            item_path = f"{path}/{index}"
            if not isinstance(form, dict):
                self.add("NAME_FORM_INVALID", "name_forms 项必须是对象", item_path)
                continue
            text = form.get("text")
            kind = form.get("kind")
            language = form.get("language")
            script = form.get("script")
            if not isinstance(text, str) or not text.strip():
                self.add("NAME_FORM_TEXT_INVALID", "name form text 不能为空", item_path)
            else:
                normalized = _normalized_name(text)
                if normalized in seen:
                    self.add(
                        "NAME_FORM_DUPLICATE",
                        f"与 name_forms[{seen[normalized]}] 归一化后重复：{text!r}",
                        item_path,
                    )
                else:
                    seen[normalized] = index
            name_form_id = form.get("name_form_id")
            if not isinstance(name_form_id, str) or not name_form_id:
                self.add("NAME_FORM_ID_INVALID", "name_form_id 不能为空", item_path)
            elif name_form_id in seen_ids:
                self.add("NAME_FORM_ID_DUPLICATE", f"name_form_id 重复：{name_form_id}", item_path)
            else:
                seen_ids.add(name_form_id)
            if kind not in NAME_FORM_KINDS:
                self.add("NAME_FORM_KIND_INVALID", f"未知 name form kind：{kind!r}", item_path)
            if kind == "primary":
                primary_count += 1
            if form.get("display_role") == "secondary":
                secondary_count += 1
            if not isinstance(language, str) or not language.strip():
                self.add("NAME_FORM_LANGUAGE_INVALID", "name form language 不能为空", item_path)
            if not isinstance(script, str) or not SCRIPT_RE.fullmatch(script):
                self.add("NAME_FORM_SCRIPT_INVALID", "script 必须是 ISO 15924 四字母代码", item_path)
            evidence_refs = form.get("evidence_refs")
            if not isinstance(evidence_refs, list) or not evidence_refs:
                self.add("NAME_FORM_EVIDENCE_REQUIRED", "name form 必须有 evidence_refs", item_path)
            elif object_id:
                covered = self.coverage.get(object_id, set())
                for observation_id in evidence_refs:
                    if observation_id not in self.observations:
                        self.add("NAME_FORM_EVIDENCE_MISSING", f"name form 引用不存在：{observation_id}", item_path)
                    elif observation_id not in covered:
                        self.add("NAME_FORM_EVIDENCE_UNDECIDED", f"name form 证据未被同 Person resolution 覆盖：{observation_id}", item_path)
        if primary_count != 1:
            self.add(
                "NAME_FORM_PRIMARY_COUNT",
                f"name_forms 恰需一个 primary，实际 {primary_count}",
                path,
                object_id=object_id,
            )
        if require_secondary and secondary_count != 1:
            self.add(
                "NAME_FORM_SECONDARY_COUNT",
                f"主人物 name_forms 恰需一个 display_role=secondary，实际 {secondary_count}",
                path,
                object_id=object_id,
            )

    def audit_governance_manifest(self) -> None:
        governance = self.manifest.get("governance")
        if not isinstance(governance, dict):
            self.add("GOVERNANCE_DECLARATION_REQUIRED", "manifest v2 缺 governance", "manifest.json")
            return
        registry = governance.get("source_registry")
        if not isinstance(registry, dict):
            self.add("SOURCE_REGISTRY_DESCRIPTOR_MISSING", "governance 缺 source_registry", "manifest.json")
        elif registry.get("schema_version") != "biography-source-audit-v1":
            self.add(
                "SOURCE_REGISTRY_SCHEMA_MISMATCH",
                "source registry descriptor 必须声明 biography-source-audit-v1",
                "manifest.json#/governance/source_registry",
            )
        reviewers = governance.get("formal_reviewers")
        if not isinstance(reviewers, list) or not reviewers:
            self.add(
                "FORMAL_REVIEWER_ALLOWLIST_MISSING",
                "governance.formal_reviewers 必须声明至少一位正式主审",
                "manifest.json#/governance/formal_reviewers",
            )
        else:
            for index, item in enumerate(reviewers):
                path = f"manifest.json#/governance/formal_reviewers/{index}"
                if not isinstance(item, dict):
                    continue
                reviewer_id = item.get("reviewer_id")
                authority = item.get("authority")
                if isinstance(reviewer_id, str) and reviewer_id:
                    if reviewer_id in self.formal_reviewers:
                        self.add(
                            "FORMAL_REVIEWER_DUPLICATE",
                            f"正式主审重复声明：{reviewer_id}",
                            path,
                        )
                    elif _is_model_reviewer(reviewer_id):
                        self.add(
                            "FORMAL_REVIEWER_IS_MODEL",
                            "模型不能进入正式主审 allowlist",
                            path,
                            object_id=reviewer_id,
                        )
                    elif authority in {"human", "main_agent"}:
                        self.formal_reviewers[reviewer_id] = authority
        ledgers = governance.get("ledgers")
        if not isinstance(ledgers, list):
            self.add("LEDGER_DECLARATIONS_INVALID", "governance.ledgers 必须是数组", "manifest.json")
            return
        seen_kinds: set[str] = set()
        seen_refs: set[str] = set()
        for index, item in enumerate(ledgers):
            path = f"manifest.json#/governance/ledgers/{index}"
            if not isinstance(item, dict):
                self.add("LEDGER_DESCRIPTOR_INVALID", "ledger descriptor 必须是对象", path)
                continue
            kind = item.get("kind")
            ref = item.get("ref")
            if kind not in KNOWN_LEDGER_KINDS:
                self.add("LEDGER_KIND_UNKNOWN", f"未知治理账本 kind：{kind!r}", path)
            elif kind in seen_kinds:
                self.add("LEDGER_KIND_DUPLICATE", f"治理账本 kind 重复：{kind}", path)
            else:
                seen_kinds.add(kind)
            if isinstance(ref, str) and ref in seen_refs:
                self.add("LEDGER_REF_DUPLICATE", f"多个治理账本复用同一 ref：{ref}", path)
            elif isinstance(ref, str):
                seen_refs.add(ref)
            if not isinstance(item.get("schema_version"), str) or not item["schema_version"]:
                self.add("LEDGER_SCHEMA_VERSION_MISSING", "ledger 缺 schema_version", path)
            elif kind in LEDGER_SCHEMA_VERSIONS:
                expected = LEDGER_SCHEMA_VERSIONS[kind]
                if item["schema_version"] != expected:
                    self.add(
                        "LEDGER_SCHEMA_VERSION_MISMATCH",
                        f"{kind} schema_version 必须是 {expected}",
                        path,
                    )
            if not isinstance(item.get("required_for_publication"), bool):
                self.add("LEDGER_PUBLICATION_FLAG_INVALID", "required_for_publication 必须为布尔值", path)
        for missing in sorted(REQUIRED_LEDGER_KINDS - seen_kinds):
            self.add(
                "REQUIRED_LEDGER_UNDECLARED",
                f"必需治理账本未声明：{missing}",
                "manifest.json#/governance/ledgers",
                object_id=missing,
            )

    def audit_projection_v2(self) -> None:
        projection = self.manifest.get("projection")
        if not isinstance(projection, dict):
            self.add("PROJECTION_V2_MISSING", "manifest v2 缺 projection", "manifest.json")
            return
        if not self.subject:
            return
        route_base = projection.get("route_base")
        asset_base = projection.get("asset_base")
        asset_target = projection.get("asset_target")
        if not isinstance(route_base, str) or f"/{self.subject}/" not in route_base:
            self.add(
                "ROUTE_NAMESPACE_MISMATCH",
                "route_base 必须是含 subject slug 的站内目录；具体产品路径由宿主 Skill 约束",
                "manifest.json#/projection/route_base",
            )
        if not isinstance(asset_base, str) or f"/{self.subject}/" not in asset_base:
            self.add(
                "ASSET_NAMESPACE_REQUIRED",
                "asset_base 必须包含 subject namespace",
                "manifest.json#/projection/asset_base",
            )
        normalized_target = asset_target.replace("\\", "/") if isinstance(asset_target, str) else ""
        if not normalized_target.startswith(f"{self.subject}/"):
            self.add(
                "ASSET_TARGET_NAMESPACE_REQUIRED",
                "asset_target 必须以 subject namespace 开头",
                "manifest.json#/projection/asset_target",
            )
        css_scope = projection.get("css_scope")
        if not isinstance(css_scope, str) or self.subject not in css_scope:
            self.add(
                "CSS_SCOPE_NAMESPACE_REQUIRED",
                "css_scope 必须显式包含 subject slug",
                "manifest.json#/projection/css_scope",
            )
        if projection.get("projection_id") != f"projection-{self.subject}-store":
            self.add("PROJECTION_ID_MISMATCH", "projection_id 未绑定 subject", "manifest.json#/projection")
        if projection.get("canonical_library_id") != f"canonical-{self.subject}-store":
            self.add("CANONICAL_LIBRARY_ID_MISMATCH", "canonical_library_id 未绑定 subject", "manifest.json#/projection")
        resources = projection.get("shared_resources")
        if not isinstance(resources, list):
            self.add("SHARED_RESOURCES_INVALID", "shared_resources 必须是数组", "manifest.json#/projection")
            return
        seen_ids: set[str] = set()
        for index, item in enumerate(resources):
            path = f"manifest.json#/projection/shared_resources/{index}"
            if not isinstance(item, dict):
                self.add("SHARED_RESOURCE_INVALID", "共享资源项必须是对象", path)
                continue
            resource_id = item.get("resource_id")
            if not isinstance(resource_id, str) or not resource_id:
                self.add("SHARED_RESOURCE_ID_INVALID", "共享资源缺 resource_id", path)
            elif resource_id in seen_ids:
                self.add("SHARED_RESOURCE_ID_DUPLICATE", f"共享资源 ID 重复：{resource_id}", path)
            else:
                seen_ids.add(resource_id)
            if item.get("owner") != "biography-series" or item.get("read_only") is not True:
                self.add(
                    "SHARED_RESOURCE_OWNERSHIP_INVALID",
                    "共享资源必须归 biography-series 且 read_only=true",
                    path,
                )
            ref = item.get("ref")
            if not isinstance(ref, str) or not ref.startswith("@series/"):
                self.add("SHARED_RESOURCE_REF_INVALID", "共享资源 ref 必须以 @series/ 开头", path)
            digest = item.get("sha256")
            if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
                self.add("SHARED_RESOURCE_HASH_INVALID", "共享资源必须有 64 位 sha256", path)
            elif isinstance(ref, str) and ref.startswith("@series/"):
                shared_root_ref = projection.get("shared_resource_root")
                shared_root = self.resolve_ref(
                    shared_root_ref,
                    "manifest.json#/projection/shared_resource_root",
                )
                if shared_root is not None:
                    resource_path = (shared_root / ref.removeprefix("@series/")).resolve()
                    try:
                        resource_path.relative_to(shared_root.resolve())
                    except ValueError:
                        self.add("SHARED_RESOURCE_PATH_ESCAPE", "共享资源逃逸 shared_resource_root", path)
                    else:
                        if not resource_path.is_file():
                            self.add("SHARED_RESOURCE_FILE_MISSING", "共享资源文件不存在", path)
                        else:
                            actual = hashlib.sha256(resource_path.read_bytes()).hexdigest()
                            if actual != digest:
                                self.add(
                                    "SHARED_RESOURCE_HASH_MISMATCH",
                                    f"共享资源摘要不匹配：实际 {actual}",
                                    path,
                                )
        publication = self.manifest.get("publication")
        if isinstance(publication, dict):
            status = publication.get("status")
            href = publication.get("href")
            if href is not None and href != route_base:
                self.add(
                    "PUBLICATION_ROUTE_MISMATCH",
                    "非空 publication.href 必须与 projection.route_base 相同",
                    "manifest.json#/publication/href",
                )
            if status == "published" and href is None:
                self.add(
                    "PUBLISHED_ROUTE_MISSING",
                    "published 人物必须声明 publication.href",
                    "manifest.json#/publication/href",
                )

    def canonical_refs(self) -> dict[str, Any]:
        if self.is_v2:
            value = self.manifest.get("canonical")
            if not isinstance(value, dict):
                self.add("CANONICAL_PATHS_REQUIRED", "manifest v2 缺 canonical 文件映射", "manifest.json")
                return dict(DEFAULT_CANONICAL_REFS)
            return {kind: value.get(kind) for kind in CANONICAL_KINDS}
        return dict(DEFAULT_CANONICAL_REFS)

    def editorial_refs(self) -> dict[str, Any]:
        if self.is_v2:
            value = self.manifest.get("editorial")
            if not isinstance(value, dict):
                self.add("EDITORIAL_PATHS_REQUIRED", "manifest v2 缺 editorial 文件映射", "manifest.json")
                return dict(DEFAULT_EDITORIAL_REFS)
            return {kind: value.get(kind) for kind in DEFAULT_EDITORIAL_REFS}
        return dict(DEFAULT_EDITORIAL_REFS)

    def ledger_refs(self) -> dict[str, Any]:
        if not self.is_v2:
            refs: dict[str, Any] = {}
            for kind, ref in LEGACY_LEDGER_REFS.items():
                if kind in LEGACY_REQUIRED_LEDGER_KINDS or (self.root / ref).exists():
                    refs[kind] = ref
            return refs
        governance = self.manifest.get("governance")
        if not isinstance(governance, dict) or not isinstance(governance.get("ledgers"), list):
            return {kind: LEGACY_LEDGER_REFS[kind] for kind in REQUIRED_LEDGER_KINDS}
        refs = {}
        for item in governance["ledgers"]:
            if isinstance(item, dict) and isinstance(item.get("kind"), str):
                refs[item["kind"]] = item.get("ref")
        return refs

    def audit_declared_files(
        self,
        canonical_refs: dict[str, Any],
        editorial_refs: dict[str, Any],
        ledger_refs: dict[str, Any],
    ) -> None:
        for group, refs in (
            ("canonical", canonical_refs),
            ("editorial", editorial_refs),
            ("governance", ledger_refs),
        ):
            if group == "editorial" and self.mode != "publish-ready":
                continue
            for key, ref in refs.items():
                path = self.resolve_ref(ref, f"manifest.json#/{group}/{key}")
                if path is not None and not path.is_file():
                    self.add(
                        "DECLARED_FILE_MISSING",
                        f"manifest 声明的文件不存在：{ref!r}",
                        f"manifest.json#/{group}/{key}",
                        object_id=key,
                    )

    def load_canonical(self, refs: dict[str, Any]) -> None:
        for kind, ref in refs.items():
            path = self.resolve_ref(ref, f"manifest.json#/canonical/{kind}")
            if path is None:
                continue
            rows = self.load_jsonl(path)
            id_field = ID_FIELDS[kind]
            for row in rows:
                object_id = row.get(id_field)
                if not isinstance(object_id, str) or not object_id:
                    self.add(
                        "CANONICAL_ID_MISSING",
                        f"{kind} 行缺 {id_field}",
                        self.rel(path),
                        object_id=str(row.get("__contract_line__")),
                    )
                    continue
                if self.is_v2:
                    self.audit_schema(
                        SCHEMA_DEFINITION_REGISTRY[f"canonical:{kind}"],
                        row,
                        f"SCHEMA_CANONICAL_{kind.upper()}_INVALID",
                        self.rel(path),
                        object_id=object_id,
                    )
                if object_id in self.canonical[kind]:
                    self.add(
                        "CANONICAL_ID_DUPLICATE",
                        f"{kind} 内 ID 重复：{object_id}",
                        self.rel(path),
                        object_id=object_id,
                    )
                    continue
                if object_id in self.all_ids:
                    self.add(
                        "CANONICAL_ID_CROSS_KIND_DUPLICATE",
                        f"ID 同时用于 {self.all_ids[object_id]} 与 {kind}",
                        self.rel(path),
                        object_id=object_id,
                    )
                self.all_ids[object_id] = kind
                self.canonical[kind][object_id] = row

    def load_ledgers(self, refs: dict[str, Any]) -> None:
        for kind, ref in refs.items():
            path = self.resolve_ref(ref, f"manifest.json#/governance/{kind}")
            if path is None:
                continue
            required = kind in REQUIRED_LEDGER_KINDS
            rows = self.load_jsonl(path, required=required)
            self.ledger_rows[kind] = rows
        observations = self.ledger_rows.get("observations", [])
        for row in observations:
            observation_id = row.get("observation_id")
            if not isinstance(observation_id, str) or not observation_id:
                self.add(
                    "OBSERVATION_ID_MISSING",
                    "Observation 缺 observation_id",
                    LEGACY_LEDGER_REFS["observations"],
                    object_id=str(row.get("__contract_line__")),
                )
                continue
            if observation_id in self.observations:
                self.add(
                    "OBSERVATION_ID_DUPLICATE",
                    f"Observation ID 重复：{observation_id}",
                    LEGACY_LEDGER_REFS["observations"],
                    object_id=observation_id,
                )
            else:
                self.observations[observation_id] = row
        self.decisions = self.ledger_rows.get("merge_decisions", [])

    def audit_governance_ledgers(self) -> None:
        """Apply the registry to every declared v2 governance ledger."""

        if not self.is_v2:
            return
        seen_ids: dict[str, str] = {}
        for kind, rows in self.ledger_rows.items():
            schema_version = LEDGER_SCHEMA_VERSIONS.get(kind)
            definition = SCHEMA_DEFINITION_REGISTRY.get(schema_version or "")
            for index, row in enumerate(rows):
                path = f"{LEGACY_LEDGER_REFS.get(kind, kind + '.jsonl')}:{index + 1}"
                object_id = self.ledger_object_id(kind, row)
                if definition is not None:
                    self.audit_schema(
                        definition,
                        row,
                        "SCHEMA_GOVERNANCE_ROW_INVALID",
                        path,
                        object_id=object_id,
                    )
                if isinstance(object_id, str):
                    previous = seen_ids.get(object_id)
                    if previous is not None:
                        self.add(
                            "GOVERNANCE_ID_DUPLICATE",
                            f"治理对象 ID 已在 {previous} 使用",
                            path,
                            object_id=object_id,
                        )
                    else:
                        seen_ids[object_id] = kind
                if kind not in {"observations", "merge_decisions", "external_verifications"}:
                    self.audit_row_subject(row, path, object_id or kind)
                if kind not in {
                    "observations",
                    "merge_decisions",
                    "external_verifications",
                    "changesets",
                    "model_recommendations",
                }:
                    review = row.get("review")
                    if review is not None:
                        self.audit_formal_review(review, path, object_id or kind)

    def audit_source_registry(self) -> None:
        if self.is_v2:
            governance = self.manifest.get("governance")
            descriptor = governance.get("source_registry") if isinstance(governance, dict) else None
        else:
            descriptor = self.manifest.get("source_registry")
        ref = descriptor.get("ref") if isinstance(descriptor, dict) else None
        path = self.resolve_ref(ref, "manifest.json#/governance/source_registry")
        if path is None:
            return
        registry = self.load_json(path)
        if not isinstance(registry, dict):
            return
        if self.is_v2:
            self.audit_schema(
                SCHEMA_DEFINITION_REGISTRY["biography-source-audit-v1"],
                registry,
                "SCHEMA_SOURCE_REGISTRY_INVALID",
                self.rel(path),
            )
        if registry.get("subject_id") != self.subject_id:
            self.add(
                "SOURCE_REGISTRY_SUBJECT_MISMATCH",
                "source registry subject_id 与 manifest 不一致",
                self.rel(path),
            )
        if registry.get("id_namespace") != self.namespace:
            self.add(
                "SOURCE_REGISTRY_NAMESPACE_MISMATCH",
                "source registry id_namespace 与 manifest 不一致",
                self.rel(path),
            )
        source_units = registry.get("source_units")
        if not isinstance(source_units, list):
            return
        for index, source in enumerate(source_units):
            if not isinstance(source, dict):
                continue
            source_id = source.get("source_id")
            if not isinstance(source_id, str) or not source_id:
                continue
            if source_id in self.source_units:
                self.add(
                    "SOURCE_ID_DUPLICATE",
                    f"source registry 重复 source_id：{source_id}",
                    self.rel(path),
                    object_id=source_id,
                )
            else:
                self.source_units[source_id] = source

    def audit_observations(self) -> None:
        if not self.is_v2:
            self.add(
                "OBSERVATION_ENVELOPE_V2_REQUIRED",
                "legacy Observation 缺逐行 subject_id/id_namespace/schema_version 显式包络",
                LEGACY_LEDGER_REFS["observations"],
                severity="migration",
            )
            return
        for observation_id, row in self.observations.items():
            self.audit_schema(
                SCHEMA_DEFINITION_REGISTRY["biography-observation-v2"],
                row,
                "SCHEMA_OBSERVATION_INVALID",
                LEGACY_LEDGER_REFS["observations"],
                object_id=observation_id,
            )
            self.audit_row_subject(row, LEGACY_LEDGER_REFS["observations"], observation_id)
            if row.get("schema_version") != "biography-observation-v2":
                self.add(
                    "OBSERVATION_SCHEMA_MISMATCH",
                    "Observation schema_version 必须是 biography-observation-v2",
                    LEGACY_LEDGER_REFS["observations"],
                    object_id=observation_id,
                )
            if self.namespace and not observation_id.startswith(f"obs-{self.namespace}-"):
                self.add(
                    "OBSERVATION_NAMESPACE_MISMATCH",
                    "Observation ID 未包含 manifest namespace",
                    LEGACY_LEDGER_REFS["observations"],
                    object_id=observation_id,
                )
            if not isinstance(row.get("source_id"), str) or not row.get("source_id"):
                self.add(
                    "OBSERVATION_SOURCE_MISSING",
                    "Observation 缺 source_id",
                    LEGACY_LEDGER_REFS["observations"],
                    object_id=observation_id,
                )
            elif row["source_id"] not in self.source_units:
                self.add(
                    "OBSERVATION_SOURCE_UNKNOWN",
                    f"Observation source_id 不在 source registry：{row['source_id']}",
                    LEGACY_LEDGER_REFS["observations"],
                    object_id=observation_id,
                )
            if not isinstance(row.get("anchor"), dict):
                self.add(
                    "OBSERVATION_ANCHOR_MISSING",
                    "Observation 缺来源 anchor 对象",
                    LEGACY_LEDGER_REFS["observations"],
                    object_id=observation_id,
                )

    def audit_merge_decisions(self) -> None:
        if self.decisions and any(row.get("schema_version") != MERGE_DECISION_V2 for row in self.decisions):
            self.add(
                "MERGE_DECISION_V2_REQUIRED",
                "merge-decisions.jsonl 含 v1 行，需迁移为显式 subject/target/review/status 的 v2",
                LEGACY_LEDGER_REFS["merge_decisions"],
                severity="migration",
            )
        seen_ids: set[str] = set()
        for row in self.decisions:
            decision_id = row.get("decision_id")
            if not isinstance(decision_id, str) or not decision_id:
                self.add(
                    "DECISION_ID_MISSING",
                    "MergeDecision 缺 decision_id",
                    LEGACY_LEDGER_REFS["merge_decisions"],
                    object_id=str(row.get("__contract_line__")),
                )
                continue
            if decision_id in seen_ids:
                self.add(
                    "DECISION_ID_DUPLICATE",
                    f"MergeDecision ID 重复：{decision_id}",
                    LEGACY_LEDGER_REFS["merge_decisions"],
                    object_id=decision_id,
                )
            seen_ids.add(decision_id)
            if row.get("schema_version") == MERGE_DECISION_V2:
                self.audit_schema(
                    SCHEMA_DEFINITION_REGISTRY[MERGE_DECISION_V2],
                    row,
                    "SCHEMA_MERGE_DECISION_INVALID",
                    LEGACY_LEDGER_REFS["merge_decisions"],
                    object_id=decision_id,
                )
                self.audit_decision_v2(row, decision_id)
            else:
                self.audit_decision_legacy(row, decision_id)
        for kind, rows in self.ledger_rows.items():
            if kind == "merge_decisions":
                continue
            for row in rows:
                reviewer = row.get("reviewer")
                review = row.get("review")
                if _is_model_reviewer(reviewer) or (
                    isinstance(review, dict) and _is_model_reviewer(review.get("reviewer_id"))
                ):
                    object_id = self.ledger_object_id(kind, row)
                    self.add(
                        "FORMAL_REVIEWER_IS_MODEL",
                        "治理账本的正式 reviewer 不能是 GLM 或其他模型",
                        LEGACY_LEDGER_REFS.get(kind, f"{kind}.jsonl"),
                        object_id=object_id,
                    )
        if self.is_v2:
            self.audit_decision_exact_once()

    def ledger_object_id(self, kind: str, row: dict[str, Any]) -> str | None:
        id_fields = {
            "observations": "observation_id",
            "merge_decisions": "decision_id",
            "external_verifications": "verification_id",
            "source_coverage_decisions": "decision_id",
            "work_classifications": "classification_id",
            "work_duplicate_decisions": "decision_id",
            "work_identity_decisions": "cluster_id",
            "quote_attribution_audits": "audit_id",
            "prose_risk_reviews": "review_id",
            "changesets": "changeset_id",
            "model_recommendations": "recommendation_id",
            "media_assets": "asset_id",
        }
        field_name = id_fields.get(kind)
        if field_name is not None:
            value = row.get(field_name)
            return value if isinstance(value, str) else None

        # Legacy callers without a ledger kind retain the best-effort fallback.
        candidates = (
            "verification_id",
            "audit_id",
            "review_id",
            "decision_id",
            "classification_id",
            "changeset_id",
            "recommendation_id",
            "asset_id",
            "cluster_id",
        )
        for field_name in candidates:
            value = row.get(field_name)
            if isinstance(value, str):
                return value
        return None

    def audit_decision_legacy(self, row: dict[str, Any], decision_id: str) -> None:
        if _is_model_reviewer(row.get("reviewer")):
            self.add(
                "FORMAL_REVIEWER_IS_MODEL",
                "legacy MergeDecision 的正式 reviewer 不能是 GLM 或其他模型",
                LEGACY_LEDGER_REFS["merge_decisions"],
                object_id=decision_id,
            )
        observation_ids = row.get("observation_ids")
        if not isinstance(observation_ids, list) or not observation_ids:
            self.add(
                "DECISION_OBSERVATIONS_INVALID",
                "MergeDecision 必须引用至少一个 Observation",
                LEGACY_LEDGER_REFS["merge_decisions"],
                object_id=decision_id,
                severity="migration",
            )
            return
        for observation_id in observation_ids:
            if observation_id not in self.observations:
                self.add(
                    "DECISION_OBSERVATION_MISSING",
                    f"MergeDecision 引用不存在 Observation：{observation_id}",
                    LEGACY_LEDGER_REFS["merge_decisions"],
                    object_id=decision_id,
                )
        target_id = row.get("target_id")
        verdict = row.get("verdict")
        if verdict in LEGACY_ACCEPTED_VERDICTS and isinstance(target_id, str):
            self.coverage[target_id].update(
                value for value in observation_ids if isinstance(value, str)
            )

    def audit_decision_v2(self, row: dict[str, Any], decision_id: str) -> None:
        path = LEGACY_LEDGER_REFS["merge_decisions"]
        self.audit_row_subject(row, path, decision_id)
        if self.namespace and not decision_id.startswith(f"md-{self.namespace}-"):
            self.add(
                "DECISION_NAMESPACE_MISMATCH",
                "MergeDecision ID 未包含 manifest namespace",
                path,
                object_id=decision_id,
            )
        observation_ids = row.get("observation_ids")
        if not isinstance(observation_ids, list) or not observation_ids:
            self.add(
                "DECISION_OBSERVATIONS_INVALID",
                "MergeDecision v2 必须引用至少一个 Observation",
                path,
                object_id=decision_id,
            )
            observation_ids = []
        elif len(observation_ids) != len(set(value for value in observation_ids if isinstance(value, str))):
            self.add(
                "DECISION_OBSERVATIONS_DUPLICATE",
                "MergeDecision v2 的 observation_ids 不得重复",
                path,
                object_id=decision_id,
            )
        for observation_id in observation_ids:
            if observation_id not in self.observations:
                self.add(
                    "DECISION_OBSERVATION_MISSING",
                    f"MergeDecision 引用不存在 Observation：{observation_id}",
                    path,
                    object_id=decision_id,
                )
        scope = row.get("scope")
        verdict = row.get("verdict")
        target_ids = row.get("target_ids")
        superseded_ids = row.get("superseded_ids")
        if not isinstance(target_ids, list):
            target_ids = []
        if not isinstance(superseded_ids, list):
            superseded_ids = []

        semantic_ok = True
        if scope == "observation_admission":
            if verdict not in ADMISSION_VERDICTS:
                self.add(
                    "ADMISSION_VERDICT_INVALID",
                    f"observation_admission verdict 无效：{verdict!r}",
                    path,
                    object_id=decision_id,
                )
                semantic_ok = False
            if target_ids or superseded_ids:
                self.add(
                    "ADMISSION_TARGETS_FORBIDDEN",
                    "observation_admission 的 target_ids/superseded_ids 必须为空",
                    path,
                    object_id=decision_id,
                )
                semantic_ok = False
        elif scope == "canonical_resolution":
            if verdict not in RESOLUTION_VERDICTS:
                self.add(
                    "RESOLUTION_VERDICT_INVALID",
                    f"canonical_resolution verdict 无效：{verdict!r}",
                    path,
                    object_id=decision_id,
                )
                semantic_ok = False
            if verdict == "source_only" and target_ids:
                self.add(
                    "SOURCE_ONLY_TARGETS_FORBIDDEN",
                    "source_only resolution 的 target_ids 必须为空",
                    path,
                    object_id=decision_id,
                )
                semantic_ok = False
            elif verdict != "source_only" and not target_ids:
                self.add(
                    "RESOLUTION_TARGETS_REQUIRED",
                    "非 source_only 的 canonical_resolution 必须有非空 target_ids",
                    path,
                    object_id=decision_id,
                )
                semantic_ok = False
            for target_id in target_ids:
                kind = self.all_ids.get(target_id) if isinstance(target_id, str) else None
                target = self.canonical.get(kind, {}).get(target_id) if kind else None
                if target is None:
                    self.add(
                        "DECISION_TARGET_MISSING",
                        f"target_id 不存在：{target_id!r}",
                        path,
                        object_id=decision_id,
                    )
                    semantic_ok = False
                elif target.get("status") not in {"active", "hold"}:
                    self.add(
                        "DECISION_TARGET_NOT_RESOLVABLE",
                        f"target_id 必须指向 active/hold：{target_id}",
                        path,
                        object_id=decision_id,
                    )
                    semantic_ok = False
            if verdict == "merge":
                if len(target_ids) != 1 or not superseded_ids:
                    self.add(
                        "MERGE_RESOLUTION_SHAPE_INVALID",
                        "merge resolution 必须有且仅有一个 target_id，并有 superseded_ids",
                        path,
                        object_id=decision_id,
                    )
                    semantic_ok = False
                for source_id in superseded_ids:
                    source_kind = self.all_ids.get(source_id) if isinstance(source_id, str) else None
                    source = self.canonical.get(source_kind, {}).get(source_id) if source_kind else None
                    target_kind = self.all_ids.get(target_ids[0]) if len(target_ids) == 1 else None
                    if source is None or source.get("status") != "merged_redirect":
                        self.add(
                            "MERGE_SUPERSEDED_INVALID",
                            f"superseded_id 必须是 merged_redirect：{source_id!r}",
                            path,
                            object_id=decision_id,
                        )
                        semantic_ok = False
                    elif source_kind != target_kind or source.get("merged_into") != target_ids[0]:
                        self.add(
                            "MERGE_REDIRECT_CLOSURE_MISMATCH",
                            f"redirect {source_id} 必须同类型且 merged_into={target_ids[0]}",
                            path,
                            object_id=decision_id,
                        )
                        semantic_ok = False
            elif superseded_ids:
                self.add(
                    "SUPERSEDED_IDS_FORBIDDEN",
                    "非 merge resolution 不得声明 superseded_ids",
                    path,
                    object_id=decision_id,
                )
                semantic_ok = False
            if verdict == "adopt":
                migration_basis = row.get("migration_basis")
                if not isinstance(migration_basis, dict):
                    self.add(
                        "ADOPT_MIGRATION_BASIS_REQUIRED",
                        "adopt 必须用 migration_basis 保留旧裁决来源，不能补造历史",
                        path,
                        object_id=decision_id,
                    )
                    semantic_ok = False
                elif "original_reviewed_at" not in migration_basis:
                    self.add(
                        "MIGRATION_BASIS_ORIGINAL_TIME_REQUIRED",
                        "migration_basis 必须显式写 original_reviewed_at；未知时写 null",
                        path,
                        object_id=decision_id,
                    )
                    semantic_ok = False
        else:
            self.add(
                "DECISION_SCOPE_INVALID",
                f"未知 MergeDecision scope：{scope!r}",
                path,
                object_id=decision_id,
            )
            semantic_ok = False

        if verdict != "adopt" and row.get("migration_basis") is not None:
            self.add(
                "MIGRATION_BASIS_FORBIDDEN",
                "只有 adopt resolution 可以携带 migration_basis",
                path,
                object_id=decision_id,
            )
            semantic_ok = False

        formal_ok = self.audit_formal_review(row.get("review"), path, decision_id)
        status = row.get("status")
        if status not in {"signed", "superseded"}:
            self.add(
                "DECISION_STATUS_INVALID",
                "MergeDecision v2 status 必须是 signed 或 superseded",
                path,
                object_id=decision_id,
            )
            semantic_ok = False
        if status != "signed" or not formal_ok or not semantic_ok:
            return
        clean_observations = [value for value in observation_ids if isinstance(value, str)]
        if scope == "observation_admission":
            for observation_id in clean_observations:
                self.signed_admissions[observation_id].append(row)
        else:
            for observation_id in clean_observations:
                self.signed_resolutions[observation_id].append(row)
            for target_id in target_ids:
                if isinstance(target_id, str):
                    self.target_resolutions[target_id].append(row)
                    self.coverage[target_id].update(clean_observations)
            for source_id in superseded_ids:
                if isinstance(source_id, str):
                    self.superseded_resolutions[source_id].append(row)

    def audit_formal_review(self, review: Any, path: str, object_id: str) -> bool:
        if not isinstance(review, dict):
            self.add("FORMAL_REVIEW_MISSING", "正式记录缺 review", path, object_id=object_id)
            return False
        ok = True
        authority = review.get("authority")
        reviewer_id = review.get("reviewer_id")
        if authority not in {"human", "main_agent"}:
            self.add(
                "FORMAL_REVIEW_AUTHORITY_INVALID",
                "正式 review.authority 只能是 human 或 main_agent",
                path,
                object_id=object_id,
            )
            ok = False
        if _is_model_reviewer(reviewer_id):
            self.add(
                "FORMAL_REVIEWER_IS_MODEL",
                "GLM-5.3 及其他模型只能 recommendation_only，不能成为正式 reviewer",
                path,
                object_id=object_id,
            )
            ok = False
        elif not isinstance(reviewer_id, str) or not reviewer_id.strip():
            self.add("FORMAL_REVIEWER_MISSING", "正式 review 缺 reviewer_id", path, object_id=object_id)
            ok = False
        elif self.formal_reviewers.get(reviewer_id) != authority:
            self.add(
                "FORMAL_REVIEWER_UNREGISTERED",
                "reviewer_id/authority 未在 manifest governance allowlist 注册",
                path,
                object_id=object_id,
            )
            ok = False
        if not _is_iso_datetime(review.get("reviewed_at")):
            self.add(
                "FORMAL_REVIEW_TIME_INVALID",
                "reviewed_at 必须是 ISO-8601 datetime",
                path,
                object_id=object_id,
            )
            ok = False
        recommendations = review.get("recommendation_refs")
        if not isinstance(recommendations, list):
            self.add(
                "RECOMMENDATION_REFS_INVALID",
                "recommendation_refs 必须是数组",
                path,
                object_id=object_id,
            )
            ok = False
        return ok

    def audit_decision_exact_once(self) -> None:
        path = LEGACY_LEDGER_REFS["merge_decisions"]
        for observation_id in self.observations:
            admissions = self.signed_admissions.get(observation_id, [])
            if not admissions:
                self.add(
                    "OBSERVATION_ADMISSION_MISSING",
                    "每条 Observation 必须恰有一条 signed observation_admission",
                    path,
                    object_id=observation_id,
                )
                continue
            if len(admissions) != 1:
                self.add(
                    "OBSERVATION_ADMISSION_DUPLICATE",
                    f"Observation 有 {len(admissions)} 条 signed admission",
                    path,
                    object_id=observation_id,
                )
                continue
            resolutions = self.signed_resolutions.get(observation_id, [])
            if admissions[0].get("verdict") == "accept":
                if not resolutions:
                    self.add(
                        "OBSERVATION_RESOLUTION_MISSING",
                        "accept Observation 必须恰有一条 signed canonical_resolution",
                        path,
                        object_id=observation_id,
                    )
                elif len(resolutions) != 1:
                    self.add(
                        "OBSERVATION_RESOLUTION_DUPLICATE",
                        f"accept Observation 有 {len(resolutions)} 条 signed resolution",
                        path,
                        object_id=observation_id,
                    )
            elif resolutions:
                self.add(
                    "OBSERVATION_RESOLUTION_FORBIDDEN",
                    "hold/reject Observation 不得进入 canonical_resolution",
                    path,
                    object_id=observation_id,
                )

    def audit_row_subject(self, row: dict[str, Any], path: str, object_id: str) -> None:
        if row.get("subject_id") != self.subject_id:
            self.add(
                "ROW_SUBJECT_MISMATCH",
                "行级 subject_id 与 manifest 不一致",
                path,
                object_id=object_id,
            )
        if row.get("id_namespace") != self.namespace:
            self.add(
                "ROW_NAMESPACE_MISMATCH",
                "行级 id_namespace 与 manifest 不一致",
                path,
                object_id=object_id,
            )

    def audit_canonical_envelopes(self) -> None:
        if not self.is_v2:
            self.add(
                "CANONICAL_ENVELOPE_V2_REQUIRED",
                "legacy Canonical 行缺逐行 subject_id/id_namespace 显式包络",
                "canonical/*.jsonl",
                severity="migration",
            )
        for kind, objects in self.canonical.items():
            id_field = ID_FIELDS[kind]
            prefix = ID_PREFIXES[kind]
            for object_id, row in objects.items():
                status = row.get("status")
                if self.is_v2:
                    self.audit_row_subject(row, f"canonical/{kind}.jsonl", object_id)
                    allowed_id = (
                        (kind == "people" and object_id == self.subject_id)
                        or self.legacy_id_aliases.get(object_id) == kind
                    )
                    if self.namespace and not allowed_id and not object_id.startswith(
                        f"{prefix}-{self.namespace}-"
                    ):
                        self.add(
                            "CANONICAL_NAMESPACE_MISMATCH",
                            f"{id_field} 未包含 manifest namespace",
                            f"canonical/{kind}.jsonl",
                            object_id=object_id,
                        )
                    if status not in CANONICAL_STATUSES:
                        self.add(
                            "CANONICAL_STATUS_INVALID",
                            f"Canonical status 必须是 {sorted(CANONICAL_STATUSES)}",
                            f"canonical/{kind}.jsonl",
                            object_id=object_id,
                        )
                if status == "merged_redirect":
                    if not isinstance(row.get("merged_into"), str) or not row.get("merged_into"):
                        self.add(
                            "REDIRECT_TARGET_MISSING",
                            "merged_redirect 缺 merged_into",
                            f"canonical/{kind}.jsonl",
                            object_id=object_id,
                        )
                elif row.get("merged_into") is not None:
                    self.add(
                        "MERGED_INTO_FORBIDDEN",
                        "非 merged_redirect 对象不得有 merged_into",
                        f"canonical/{kind}.jsonl",
                        object_id=object_id,
                        severity="error" if self.is_v2 else "migration",
                    )
                if self.is_v2 and status in {"active", "hold"}:
                    if not self.target_resolutions.get(object_id):
                        self.add(
                            "CANONICAL_RESOLUTION_MISSING",
                            "active/hold Canonical 必须至少由一条 signed canonical_resolution 建立或更新",
                            f"canonical/{kind}.jsonl",
                            object_id=object_id,
                        )
        people = self.canonical["people"]
        subject_person = people.get(self.subject_id or "")
        if subject_person is None:
            self.add(
                "SUBJECT_PERSON_MISSING",
                "people 集合缺主人物对象",
                "canonical/people.jsonl",
                object_id=self.subject_id,
            )
        elif subject_person.get("status") != "active":
            self.add(
                "SUBJECT_PERSON_NOT_ACTIVE",
                "主人物 Person 必须是 active",
                "canonical/people.jsonl",
                object_id=self.subject_id,
            )
        if self.is_v2 and subject_person is not None:
            self.audit_name_forms(
                subject_person.get("name_forms"),
                "canonical/people.jsonl#/name_forms",
                require_secondary=False,
                object_id=self.subject_id,
            )
            forms = subject_person.get("name_forms")
            primary = next(
                (
                    item.get("text")
                    for item in forms
                    if isinstance(item, dict) and item.get("kind") == "primary"
                ),
                None,
            ) if isinstance(forms, list) else None
            if primary != subject_person.get("canonical_name"):
                self.add(
                    "CANONICAL_NAME_PRIMARY_MISMATCH",
                    "canonical_name 必须与唯一 primary name form 完全一致",
                    "canonical/people.jsonl#/name_forms",
                    object_id=self.subject_id,
                )
            publication = self.manifest.get("publication")
            catalog_name = publication.get("catalog_name") if isinstance(publication, dict) else None
            if catalog_name is not None and catalog_name != primary:
                self.add(
                    "CATALOG_NAME_PRIMARY_MISMATCH",
                    "draft 兼容 catalog_name 必须与主人物 primary name 一致",
                    "manifest.json#/publication/catalog_name",
                    object_id=self.subject_id,
                )
        for person_id, person in (people.items() if self.is_v2 else ()):
            if person_id == self.subject_id or person.get("name_forms") is None:
                continue
            self.audit_name_forms(
                person.get("name_forms"),
                "canonical/people.jsonl#/name_forms",
                object_id=person_id,
            )

    def audit_redirects(self) -> None:
        for kind, objects in self.canonical.items():
            for object_id, row in objects.items():
                if row.get("status") != "merged_redirect":
                    continue
                target_id = row.get("merged_into")
                if self.is_v2:
                    merge_resolutions = self.superseded_resolutions.get(object_id, [])
                    if not merge_resolutions:
                        self.add(
                            "REDIRECT_MERGE_DECISION_MISSING",
                            "merged_redirect 必须恰由一条 signed merge resolution 解释",
                            f"canonical/{kind}.jsonl",
                            object_id=object_id,
                        )
                    elif len(merge_resolutions) != 1:
                        self.add(
                            "REDIRECT_MERGE_DECISION_DUPLICATE",
                            f"merged_redirect 被 {len(merge_resolutions)} 条 signed merge resolution 重复接管",
                            f"canonical/{kind}.jsonl",
                            object_id=object_id,
                        )
                    else:
                        resolution = merge_resolutions[0]
                        if (
                            resolution.get("verdict") != "merge"
                            or resolution.get("target_ids") != [target_id]
                        ):
                            self.add(
                                "REDIRECT_MERGE_DECISION_MISMATCH",
                                "merge resolution 的 target_ids 必须与 merged_into 精确一致",
                                f"canonical/{kind}.jsonl",
                                object_id=object_id,
                            )
                if not isinstance(target_id, str) or not target_id:
                    continue
                if target_id not in objects:
                    other_kind = self.all_ids.get(target_id)
                    code = "REDIRECT_TARGET_KIND" if other_kind else "REDIRECT_TARGET_MISSING"
                    detail = (
                        f"redirect 目标属于其他类型 {other_kind}"
                        if other_kind
                        else "redirect 目标不存在"
                    )
                    self.add(code, detail, f"canonical/{kind}.jsonl", object_id=object_id)
                    continue
                target = objects[target_id]
                target_status = target.get("status")
                if target_status == "merged_redirect":
                    self.add(
                        "REDIRECT_CHAIN",
                        "redirect 必须一步直达 active 终点，不允许链",
                        f"canonical/{kind}.jsonl",
                        object_id=object_id,
                    )
                seen = {object_id}
                cursor = target_id
                while cursor in objects:
                    if cursor in seen:
                        self.add(
                            "REDIRECT_CYCLE",
                            "redirect 图存在环",
                            f"canonical/{kind}.jsonl",
                            object_id=object_id,
                        )
                        break
                    seen.add(cursor)
                    cursor_row = objects[cursor]
                    if cursor_row.get("status") != "merged_redirect":
                        break
                    next_id = cursor_row.get("merged_into")
                    if not isinstance(next_id, str):
                        break
                    cursor = next_id
                if target_status not in {"active", "hold", "merged_redirect"}:
                    self.add(
                        "REDIRECT_TARGET_NOT_ACTIVE",
                        f"redirect 目标状态无效：{target_status!r}",
                        f"canonical/{kind}.jsonl",
                        object_id=object_id,
                    )

    def audit_public_aliases(self) -> None:
        """Public aliases must resolve in one hop to an active same-kind object."""

        if not self.is_v2:
            return
        for index, alias in enumerate(self.id_aliases):
            path = f"manifest.json#/subject/id_aliases/{index}"
            alias_id = alias.get("alias_id")
            target_id = alias.get("target_id")
            kind = alias.get("kind")
            if isinstance(alias_id, str) and alias_id in self.all_ids:
                self.add("ID_ALIAS_COLLIDES_CANONICAL", "alias_id 不得占用 Canonical ID", path, object_id=alias_id)
            target = self.canonical.get(kind, {}).get(target_id) if kind in CANONICAL_KINDS else None
            if target is None:
                self.add("ID_ALIAS_TARGET_MISSING", f"alias target 不存在或类型不符：{target_id!r}", path, object_id=alias_id)
                continue
            if alias.get("public") is True and target.get("status") != "active":
                self.add("PUBLIC_ALIAS_TARGET_NOT_ACTIVE", "公开 alias 必须一步指向 active 对象", path, object_id=alias_id)

    def audit_reference_closure(self) -> None:
        reference_fields: dict[str, tuple[tuple[str, str, bool], ...]] = {
            "events": (
                ("person_id", "people", False),
                ("actors", "people", True),
                ("work_ids", "works", True),
                ("relation_ids", "relations", True),
                ("controversy_ids", "controversies", True),
            ),
            "works": (
                ("collaborator_ids", "people", True),
                ("event_ids", "events", True),
            ),
            "relations": (("person_ids", "people", True),),
            "quotes": (("speaker_id", "people", False),),
        }
        for kind, fields in reference_fields.items():
            for object_id, row in self.canonical[kind].items():
                if row.get("status") not in {"active", "hold"}:
                    continue
                for field_name, target_kind, is_list in fields:
                    raw = row.get(field_name)
                    if raw is None:
                        continue
                    values = raw if is_list else [raw]
                    if not isinstance(values, list):
                        self.add(
                            "REFERENCE_FIELD_INVALID",
                            f"{field_name} 类型不正确",
                            f"canonical/{kind}.jsonl",
                            object_id=object_id,
                        )
                        continue
                    for target_id in values:
                        if not isinstance(target_id, str):
                            self.add(
                                "REFERENCE_ID_INVALID",
                                f"{field_name} 含非字符串 ID",
                                f"canonical/{kind}.jsonl",
                                object_id=object_id,
                            )
                            continue
                        target = self.canonical[target_kind].get(target_id)
                        if target is None:
                            self.add(
                                "CANONICAL_REFERENCE_MISSING",
                                f"{field_name} 引用不存在 {target_kind}：{target_id}",
                                f"canonical/{kind}.jsonl",
                                object_id=object_id,
                            )
                        elif target.get("status") != "active":
                            self.add(
                                "CANONICAL_REFERENCE_NOT_ACTIVE",
                                f"{field_name} 指向 {target.get('status')} 对象：{target_id}",
                                f"canonical/{kind}.jsonl",
                                object_id=object_id,
                            )
        for work_id, row in self.canonical["works"].items():
            if row.get("status") not in {"active", "hold"}:
                continue
            explanation = row.get("reader_explanation")
            if explanation is None:
                continue
            if not isinstance(explanation, dict):
                self.add(
                    "READER_EXPLANATION_INVALID",
                    "reader_explanation 必须是对象",
                    "canonical/works.jsonl",
                    object_id=work_id,
                )
                continue
            related_event_ids = explanation.get("related_event_ids")
            if not isinstance(related_event_ids, list):
                self.add(
                    "READER_RELATED_EVENTS_INVALID",
                    "reader_explanation.related_event_ids 必须是数组",
                    "canonical/works.jsonl",
                    object_id=work_id,
                )
                continue
            for event_id in related_event_ids:
                event = self.canonical["events"].get(event_id) if isinstance(event_id, str) else None
                if event is None or event.get("status") != "active":
                    self.add(
                        "READER_RELATED_EVENT_MISSING",
                        f"reader_explanation 必须引用 active Event：{event_id!r}",
                        "canonical/works.jsonl",
                        object_id=work_id,
                    )
        for relation_id, row in self.canonical["relations"].items():
            if row.get("status") != "active":
                continue
            person_ids = row.get("person_ids")
            if not isinstance(person_ids, list) or len(person_ids) < 2:
                self.add(
                    "RELATION_ENDPOINTS_INCOMPLETE",
                    "active Relation 必须有至少两个 person_ids；counterpart_hint 不能代替端点",
                    "canonical/relations.jsonl",
                    object_id=relation_id,
                    severity="error" if self.is_v2 else "migration",
                )
                continue
            if len(person_ids) != len(set(value for value in person_ids if isinstance(value, str))):
                self.add(
                    "RELATION_ENDPOINTS_DUPLICATE",
                    "Relation person_ids 不得重复",
                    "canonical/relations.jsonl",
                    object_id=relation_id,
                )
            if self.subject_id not in person_ids:
                self.add(
                    "RELATION_SUBJECT_NOT_ENDPOINT",
                    "人物内 active Relation 至少一个端点必须是主人物",
                    "canonical/relations.jsonl",
                    object_id=relation_id,
                )
            if self.is_v2 and row.get("counterpart_hint") is not None:
                self.add(
                    "RELATION_COUNTERPART_HINT_FORBIDDEN",
                    "v2 active Relation 不允许用 counterpart_hint 代替 Person",
                    "canonical/relations.jsonl",
                    object_id=relation_id,
                )
            participants = row.get("participants")
            if not isinstance(participants, list):
                continue
            participant_ids = [
                participant.get("person_id")
                for participant in participants
                if isinstance(participant, dict)
                and isinstance(participant.get("person_id"), str)
            ]
            if len(participant_ids) != len(set(participant_ids)):
                self.add(
                    "RELATION_PARTICIPANTS_DUPLICATE",
                    "Relation participants 不得重复 person_id",
                    "canonical/relations.jsonl",
                    object_id=relation_id,
                )
            if set(participant_ids) != set(person_ids):
                self.add(
                    "RELATION_PARTICIPANTS_MISMATCH",
                    "participants.person_id 必须与 person_ids 形成同一端点集合",
                    "canonical/relations.jsonl",
                    object_id=relation_id,
                )
            for participant_id in participant_ids:
                person = self.canonical["people"].get(participant_id)
                if person is None or person.get("status") != "active":
                    self.add(
                        "RELATION_PARTICIPANT_NOT_ACTIVE",
                        f"participant 引用非 active Person：{participant_id}",
                        "canonical/relations.jsonl",
                        object_id=relation_id,
                    )

    def audit_temporal_semantics(self) -> None:
        if not self.is_v2:
            return
        for event_id, row in self.canonical["events"].items():
            if row.get("status") not in {"active", "hold"}:
                continue
            temporal = row.get("date")
            if not isinstance(temporal, dict):
                if row.get("status") == "active":
                    self.add("EVENT_DATE_REQUIRED", "active Event 必须有结构化 date", "canonical/events.jsonl", object_id=event_id)
                continue
            start = temporal.get("start")
            end = temporal.get("end")
            if isinstance(start, str) and isinstance(end, str) and start > end:
                self.add("EVENT_DATE_RANGE_REVERSED", "date.start 不得晚于 date.end", "canonical/events.jsonl", object_id=event_id)
            if temporal.get("precision") in {"exact_day", "day"} and not isinstance(start, str):
                self.add("EVENT_DATE_PRECISION_DISHONEST", "day 精度必须给出 start", "canonical/events.jsonl", object_id=event_id)
            if temporal.get("precision") in {"month", "season", "year"} and (
                isinstance(start, str) != isinstance(end, str)
            ):
                self.add(
                    "EVENT_DATE_PRECISION_DISHONEST",
                    "month/season/year 若写规范化边界，必须同时给出 start 与 end",
                    "canonical/events.jsonl",
                    object_id=event_id,
                )
            conversion = temporal.get("conversion")
            if isinstance(conversion, dict):
                if conversion.get("normalized_calendar_system") not in {
                    "gregorian",
                    "proleptic_gregorian",
                }:
                    self.add(
                        "DATE_CONVERSION_TARGET_INVALID",
                        "纪年换算必须声明 gregorian 或 proleptic_gregorian 目标历法",
                        "canonical/events.jsonl",
                        object_id=event_id,
                    )
                for observation_id in conversion.get("basis_evidence_refs", []):
                    if observation_id not in self.observations:
                        self.add("DATE_CONVERSION_EVIDENCE_MISSING", f"纪年换算依据不存在：{observation_id}", "canonical/events.jsonl", object_id=event_id)
                    elif observation_id not in self.coverage.get(event_id, set()):
                        self.add("DATE_CONVERSION_EVIDENCE_UNDECIDED", f"纪年换算依据未被 Event resolution 覆盖：{observation_id}", "canonical/events.jsonl", object_id=event_id)

    def audit_source_locators(self) -> None:
        if not self.is_v2:
            return
        editions: dict[str, set[str]] = {}
        witnesses: dict[str, set[str]] = {}
        for source_id, source in self.source_units.items():
            edition_rows = source.get("editions") if isinstance(source.get("editions"), list) else []
            raw_witnesses = source.get("witnesses") if isinstance(source.get("witnesses"), list) else []
            edition_ids = [item.get("edition_id") for item in edition_rows if isinstance(item, dict)]
            witness_rows = [item for item in raw_witnesses if isinstance(item, dict)]
            witness_ids = [item.get("witness_id") for item in witness_rows]
            editions[source_id] = {value for value in edition_ids if isinstance(value, str)}
            witnesses[source_id] = {value for value in witness_ids if isinstance(value, str)}
            if len(editions[source_id]) != len(edition_ids):
                self.add("SOURCE_EDITION_ID_DUPLICATE", "同一来源 edition_id 不得重复", "source-registry.json", object_id=source_id)
            if len(witnesses[source_id]) != len(witness_ids):
                self.add("SOURCE_WITNESS_ID_DUPLICATE", "同一来源 witness_id 不得重复", "source-registry.json", object_id=source_id)
            if source.get("source_type") in {
                "book",
                "archive",
                "manuscript",
                "museum_object",
            } and not witness_rows:
                self.add(
                    "SOURCE_WITNESS_REQUIRED",
                    "书籍、档案、手稿和馆藏对象必须声明至少一个可定位 witness",
                    "source-registry.json",
                    object_id=source_id,
                )
            for witness in witness_rows:
                edition_id = witness.get("edition_id")
                if edition_id is not None and edition_id not in editions[source_id]:
                    self.add("SOURCE_WITNESS_EDITION_MISSING", f"witness 引用不存在 edition：{edition_id}", "source-registry.json", object_id=witness.get("witness_id"))
        for observation_id, row in self.observations.items():
            source_id = row.get("source_id")
            anchor = row.get("anchor")
            if not isinstance(anchor, dict):
                continue
            edition_id = anchor.get("edition_id")
            witness_id = anchor.get("witness_id")
            if edition_id is not None and edition_id not in editions.get(source_id, set()):
                self.add("OBSERVATION_EDITION_MISSING", f"locator edition 不属于 source：{edition_id}", LEGACY_LEDGER_REFS["observations"], object_id=observation_id)
            if witness_id is not None and witness_id not in witnesses.get(source_id, set()):
                self.add("OBSERVATION_WITNESS_MISSING", f"locator witness 不属于 source：{witness_id}", LEGACY_LEDGER_REFS["observations"], object_id=observation_id)
            source = self.source_units.get(source_id)
            if (
                self.mode == "publish-ready"
                and isinstance(source, dict)
                and source.get("source_type")
                in {"book", "archive", "manuscript", "museum_object"}
                and not isinstance(witness_id, str)
            ):
                self.add(
                    "OBSERVATION_WITNESS_REQUIRED",
                    "公开使用的书籍、档案、手稿和馆藏 Observation 必须定位到 witness",
                    LEGACY_LEDGER_REFS["observations"],
                    object_id=observation_id,
                )
            if isinstance(source, dict) and source.get("source_type") == "museum_object" and anchor.get("locator_type") != "accession":
                self.add("MUSEUM_ACCESSION_REQUIRED", "博物馆对象 Observation 必须使用 accession locator", LEGACY_LEDGER_REFS["observations"], object_id=observation_id)

    def audit_source_coverage_decisions(self) -> None:
        """Require an auditable, non-duplicated disposition for each used source."""

        if not self.is_v2:
            return
        signed: dict[str, list[dict[str, Any]]] = defaultdict(list)
        path = LEGACY_LEDGER_REFS["source_coverage_decisions"]
        for row in self.ledger_rows.get("source_coverage_decisions", []):
            if row.get("status") != "signed":
                continue
            source_id = row.get("source_id")
            if not isinstance(source_id, str) or source_id not in self.source_units:
                self.add(
                    "SOURCE_COVERAGE_TARGET_MISSING",
                    f"来源覆盖决策引用不存在的 SourceUnit：{source_id!r}",
                    path,
                    object_id=self.ledger_object_id("source_coverage_decisions", row),
                )
                continue
            signed[source_id].append(row)
        for source_id, rows in signed.items():
            if len(rows) > 1:
                self.add(
                    "SOURCE_COVERAGE_DECISION_DUPLICATE",
                    "同一 SourceUnit 不得有多条现役 signed 覆盖决策",
                    path,
                    object_id=source_id,
                )
        if self.mode == "publish-ready":
            for source_id in self.source_units:
                if len(signed.get(source_id, [])) != 1:
                    self.add(
                        "SOURCE_COVERAGE_DECISION_EXACT_ONCE",
                        "publish-ready 要求每个 SourceUnit 恰有一条 signed 覆盖决策",
                        path,
                        object_id=source_id,
                    )

    def audit_work_identity(self) -> None:
        if not self.is_v2:
            return
        works = self.canonical["works"]
        parent_fields = {
            "textual_expression": ("embodies_work_id", "intellectual_work"),
            "material_manifestation": ("manifestation_of_id", None),
        }
        for work_id, row in works.items():
            if row.get("status") not in {"active", "hold"}:
                continue
            level = row.get("entity_level")
            if level not in parent_fields:
                continue
            field_name, expected_level = parent_fields[level]
            parent_id = row.get(field_name)
            parent = works.get(parent_id) if isinstance(parent_id, str) else None
            if parent is None or parent.get("status") != "active":
                self.add("WORK_PARENT_NOT_ACTIVE", f"{field_name} 必须引用 active Work", "canonical/works.jsonl", object_id=work_id)
                continue
            parent_level = parent.get("entity_level")
            if expected_level is not None and parent_level != expected_level:
                self.add("WORK_ENTITY_LEVEL_MISMATCH", f"{level} 必须引用 {expected_level}", "canonical/works.jsonl", object_id=work_id)
            if level == "material_manifestation" and parent_level not in {"intellectual_work", "textual_expression"}:
                self.add("WORK_MANIFESTATION_PARENT_INVALID", "material manifestation 只能引用 work/expression", "canonical/works.jsonl", object_id=work_id)
        for work_id in works:
            seen: set[str] = set()
            cursor = work_id
            while cursor in works:
                if cursor in seen:
                    self.add("WORK_IDENTITY_CYCLE", "作品层级引用存在环", "canonical/works.jsonl", object_id=work_id)
                    break
                seen.add(cursor)
                row = works[cursor]
                cursor = row.get("embodies_work_id") or row.get("manifestation_of_id")
                if not isinstance(cursor, str):
                    break
        classifications: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in self.ledger_rows.get("work_classifications", []):
            if row.get("status") == "signed" and isinstance(row.get("work_id"), str):
                work_id = row["work_id"]
                classifications[work_id].append(row)
                work = works.get(work_id)
                if work is None:
                    self.add("WORK_CLASSIFICATION_TARGET_MISSING", "作品分类引用不存在的 Work", LEGACY_LEDGER_REFS["work_classifications"], object_id=work_id)
                elif row.get("entity_level") != work.get("entity_level"):
                    self.add("WORK_CLASSIFICATION_LEVEL_MISMATCH", "作品分类与 Canonical Work 的 entity_level 不一致", LEGACY_LEDGER_REFS["work_classifications"], object_id=work_id)
        for work_id, rows in classifications.items():
            if len(rows) > 1:
                self.add("WORK_CLASSIFICATION_DUPLICATE", "同一 Work 不得有多条现役 signed classification", LEGACY_LEDGER_REFS["work_classifications"], object_id=work_id)
        clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
        work_cluster_membership: dict[str, list[str]] = defaultdict(list)
        for row in self.ledger_rows.get("work_identity_decisions", []):
            if row.get("status") != "signed":
                continue
            cluster_id = row.get("cluster_id")
            if isinstance(cluster_id, str):
                clusters[cluster_id].append(row)
            work_ids = row.get("work_ids") if isinstance(row.get("work_ids"), list) else []
            levels = {works[work_id].get("entity_level") for work_id in work_ids if work_id in works}
            if row.get("disposition") == "merge" and len(levels) > 1:
                self.add("WORK_CROSS_LEVEL_MERGE", "不同 entity_level 的作品不得 merge", LEGACY_LEDGER_REFS["work_identity_decisions"], object_id=cluster_id)
            for work_id in work_ids:
                if work_id not in works:
                    self.add("WORK_IDENTITY_TARGET_MISSING", f"作品身份决策引用不存在：{work_id}", LEGACY_LEDGER_REFS["work_identity_decisions"], object_id=cluster_id)
                elif isinstance(cluster_id, str):
                    work_cluster_membership[work_id].append(cluster_id)
        for cluster_id, rows in clusters.items():
            if len(rows) != 1:
                self.add("WORK_IDENTITY_CLUSTER_DUPLICATE", "work cluster 必须恰有一条 signed decision", LEGACY_LEDGER_REFS["work_identity_decisions"], object_id=cluster_id)
        for work_id, cluster_ids in work_cluster_membership.items():
            if len(set(cluster_ids)) > 1:
                self.add("WORK_IDENTITY_MULTI_CLUSTER", "同一 Work 不得同时属于多个现役身份 cluster", LEGACY_LEDGER_REFS["work_identity_decisions"], object_id=work_id)
        if self.mode == "publish-ready":
            for work_id, row in works.items():
                if row.get("status") != "active":
                    continue
                if len(classifications.get(work_id, [])) != 1:
                    self.add("WORK_CLASSIFICATION_EXACT_ONCE", "active Work 必须恰有一条 signed classification", LEGACY_LEDGER_REFS["work_classifications"], object_id=work_id)
                if len(work_cluster_membership.get(work_id, [])) != 1:
                    self.add("WORK_IDENTITY_EXACT_ONCE", "active Work 必须恰属于一个已审作品身份 cluster", LEGACY_LEDGER_REFS["work_identity_decisions"], object_id=work_id)

    def audit_quote_semantics(self) -> None:
        if not self.is_v2:
            return
        witness_ids = {
            item.get("witness_id")
            for source in self.source_units.values()
            for item in (source.get("witnesses") if isinstance(source.get("witnesses"), list) else [])
            if isinstance(item, dict) and isinstance(item.get("witness_id"), str)
        }
        audits: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for audit in self.ledger_rows.get("quote_attribution_audits", []):
            if audit.get("status") == "signed" and isinstance(audit.get("quote_id"), str):
                quote_id = audit["quote_id"]
                audits[quote_id].append(audit)
                quote = self.canonical["quotes"].get(quote_id)
                if quote is None:
                    self.add("QUOTE_ATTRIBUTION_TARGET_MISSING", "归属审查引用不存在的 Quote", LEGACY_LEDGER_REFS["quote_attribution_audits"], object_id=quote_id)
                    continue
                if audit.get("verdict") != quote.get("attribution_status"):
                    self.add("QUOTE_ATTRIBUTION_VERDICT_MISMATCH", "归属审查 verdict 与 Canonical Quote 不一致", LEGACY_LEDGER_REFS["quote_attribution_audits"], object_id=quote_id)
                for observation_id in (audit.get("evidence_refs") if isinstance(audit.get("evidence_refs"), list) else []):
                    if observation_id not in self.observations:
                        self.add("QUOTE_ATTRIBUTION_EVIDENCE_MISSING", f"归属审查证据不存在：{observation_id}", LEGACY_LEDGER_REFS["quote_attribution_audits"], object_id=quote_id)
                    elif observation_id not in self.coverage.get(quote_id, set()):
                        self.add("QUOTE_ATTRIBUTION_EVIDENCE_UNDECIDED", f"归属审查证据未被 Quote resolution 覆盖：{observation_id}", LEGACY_LEDGER_REFS["quote_attribution_audits"], object_id=quote_id)
        for quote_id, rows in audits.items():
            if len(rows) > 1:
                self.add("QUOTE_ATTRIBUTION_AUDIT_DUPLICATE", "同一 Quote 不得有多条现役 signed attribution audit", LEGACY_LEDGER_REFS["quote_attribution_audits"], object_id=quote_id)
        for quote_id, row in self.canonical["quotes"].items():
            if row.get("status") not in {"active", "hold"}:
                continue
            author_id = row.get("author_id")
            if author_id is not None and (author_id not in self.canonical["people"] or self.canonical["people"][author_id].get("status") != "active"):
                self.add("QUOTE_AUTHOR_NOT_ACTIVE", f"author_id 不是 active Person：{author_id}", "canonical/quotes.jsonl", object_id=quote_id)
            work_id = row.get("work_id")
            if work_id is not None and (work_id not in self.canonical["works"] or self.canonical["works"][work_id].get("status") != "active"):
                self.add("QUOTE_WORK_NOT_ACTIVE", f"work_id 不是 active Work：{work_id}", "canonical/quotes.jsonl", object_id=quote_id)
            speaker = row.get("speaker")
            if isinstance(speaker, dict) and speaker.get("type") in {"author", "person"}:
                person_id = speaker.get("person_id")
                if person_id not in self.canonical["people"] or self.canonical["people"][person_id].get("status") != "active":
                    self.add("QUOTE_SPEAKER_NOT_ACTIVE", f"speaker.person_id 不是 active Person：{person_id}", "canonical/quotes.jsonl", object_id=quote_id)
            if row.get("attribution_status") == "misattributed" and isinstance(speaker, dict) and speaker.get("person_id") == self.subject_id:
                self.add("MISATTRIBUTED_QUOTE_SUBJECT_SPEAKER", "misattributed Quote 不得把主人物写成事实 speaker", "canonical/quotes.jsonl", object_id=quote_id)
            claimed_speakers = row.get("claimed_speaker_ids")
            if isinstance(claimed_speakers, list):
                for claimed_id in claimed_speakers:
                    person = self.canonical["people"].get(claimed_id)
                    if person is None or person.get("status") != "active":
                        self.add("QUOTE_CLAIMED_SPEAKER_NOT_ACTIVE", f"claimed speaker 不是 active Person：{claimed_id}", "canonical/quotes.jsonl", object_id=quote_id)
            if (
                row.get("attribution_status") == "misattributed"
                and isinstance(claimed_speakers, list)
                and self.subject_id not in claimed_speakers
            ):
                self.add("MISATTRIBUTED_QUOTE_CLAIM_MISSING", "人物语录库中的 misattributed Quote 必须显式记录主人物为 claimed speaker", "canonical/quotes.jsonl", object_id=quote_id)
            forms = row.get("text_forms") if isinstance(row.get("text_forms"), list) else []
            if sum(1 for form in forms if isinstance(form, dict) and form.get("kind") == "base") != 1:
                self.add("QUOTE_BASE_TEXT_EXACT_ONCE", "Quote 必须恰有一个 base text form", "canonical/quotes.jsonl", object_id=quote_id)
            forms_by_id = {
                form.get("text_form_id"): form
                for form in forms
                if isinstance(form, dict) and isinstance(form.get("text_form_id"), str)
            }
            if len(forms_by_id) != len(
                [form for form in forms if isinstance(form, dict)]
            ):
                self.add("QUOTE_TEXT_FORM_ID_DUPLICATE", "text_form_id 不得重复", "canonical/quotes.jsonl", object_id=quote_id)
            for form in forms:
                if not isinstance(form, dict):
                    continue
                witness_id = form.get("witness_id")
                if witness_id is not None and witness_id not in witness_ids:
                    self.add("QUOTE_WITNESS_MISSING", f"text form witness 不存在：{witness_id}", "canonical/quotes.jsonl", object_id=quote_id)
                if form.get("kind") == "translation":
                    base_form = forms_by_id.get(form.get("base_text_form_id"))
                    if not isinstance(base_form, dict) or base_form.get("kind") != "base":
                        self.add("QUOTE_TRANSLATION_BASE_MISSING", "translation 必须一步引用本 Quote 的 base text form", "canonical/quotes.jsonl", object_id=quote_id)
                    for translator_id in (
                        form.get("translator_ids")
                        if isinstance(form.get("translator_ids"), list)
                        else []
                    ):
                        translator = self.canonical["people"].get(translator_id)
                        if translator is None or translator.get("status") != "active":
                            self.add("QUOTE_TRANSLATOR_NOT_ACTIVE", f"translator 不是 active Person：{translator_id}", "canonical/quotes.jsonl", object_id=quote_id)
                for observation_id in (form.get("evidence_refs") if isinstance(form.get("evidence_refs"), list) else []):
                    if observation_id not in self.observations:
                        self.add("QUOTE_TEXT_EVIDENCE_MISSING", f"text form 证据不存在：{observation_id}", "canonical/quotes.jsonl", object_id=quote_id)
                    elif observation_id not in self.coverage.get(quote_id, set()):
                        self.add("QUOTE_TEXT_EVIDENCE_UNDECIDED", f"text form 证据未被 Quote resolution 覆盖：{observation_id}", "canonical/quotes.jsonl", object_id=quote_id)
            if self.mode == "publish-ready" and row.get("status") == "active" and len(audits.get(quote_id, [])) != 1:
                self.add("QUOTE_ATTRIBUTION_AUDIT_EXACT_ONCE", "active Quote 必须恰有一条 signed attribution audit", LEGACY_LEDGER_REFS["quote_attribution_audits"], object_id=quote_id)

    def audit_controversy_positions(self) -> None:
        if not self.is_v2:
            return
        for controversy_id, row in self.canonical["controversies"].items():
            if row.get("status") not in {"active", "hold"}:
                continue
            positions = row.get("positions")
            if not isinstance(positions, list):
                continue
            seen: set[str] = set()
            for position in positions:
                if not isinstance(position, dict):
                    continue
                position_id = position.get("position_id")
                if isinstance(position_id, str):
                    if position_id in seen:
                        self.add("CONTROVERSY_POSITION_DUPLICATE", f"position_id 重复：{position_id}", "canonical/controversies.jsonl", object_id=controversy_id)
                    seen.add(position_id)
                for observation_id in (position.get("evidence_refs") if isinstance(position.get("evidence_refs"), list) else []):
                    observation = self.observations.get(observation_id)
                    if observation is None:
                        self.add("CONTROVERSY_POSITION_EVIDENCE_MISSING", f"立场证据不存在：{observation_id}", "canonical/controversies.jsonl", object_id=controversy_id)
                    elif observation_id not in self.coverage.get(controversy_id, set()):
                        self.add("CONTROVERSY_POSITION_EVIDENCE_UNDECIDED", f"立场证据未被同 controversy resolution 覆盖：{observation_id}", "canonical/controversies.jsonl", object_id=controversy_id)
                for source_id in (position.get("source_ids") if isinstance(position.get("source_ids"), list) else []):
                    if source_id not in self.source_units:
                        self.add("CONTROVERSY_POSITION_SOURCE_MISSING", f"立场来源不存在：{source_id}", "canonical/controversies.jsonl", object_id=controversy_id)

    def audit_media_assets(self) -> None:
        if not self.is_v2:
            return
        for row in self.ledger_rows.get("media_assets", []):
            asset_id = row.get("asset_id")
            expected_metadata_hash = row.get("metadata_sha256")
            actual_metadata_hash = governed_record_sha256(row)
            if expected_metadata_hash != actual_metadata_hash:
                self.add(
                    "MEDIA_METADATA_HASH_MISMATCH",
                    f"媒体治理元数据摘要不匹配：实际 {actual_metadata_hash}",
                    LEGACY_LEDGER_REFS["media_assets"],
                    object_id=asset_id,
                )
            if row.get("status") not in {"active", "hold"}:
                continue
            for field_name in ("depicted_person_ids", "creator_ids"):
                values = row.get(field_name) if isinstance(row.get(field_name), list) else []
                for person_id in values:
                    if person_id not in self.canonical["people"] or self.canonical["people"][person_id].get("status") != "active":
                        self.add("MEDIA_PERSON_NOT_ACTIVE", f"{field_name} 引用非 active Person：{person_id}", LEGACY_LEDGER_REFS["media_assets"], object_id=asset_id)
            source_id = row.get("source_id")
            if source_id not in self.source_units:
                self.add("MEDIA_SOURCE_MISSING", f"media source 不存在：{source_id}", LEGACY_LEDGER_REFS["media_assets"], object_id=asset_id)
            file_path = self.resolve_ref(row.get("file_ref"), LEGACY_LEDGER_REFS["media_assets"])
            if file_path is not None:
                if not file_path.is_file():
                    self.add("MEDIA_FILE_MISSING", "media file_ref 不存在", LEGACY_LEDGER_REFS["media_assets"], object_id=asset_id)
                elif isinstance(row.get("sha256"), str):
                    actual = hashlib.sha256(file_path.read_bytes()).hexdigest()
                    if actual != row.get("sha256"):
                        self.add("MEDIA_HASH_MISMATCH", f"媒体摘要不匹配：实际 {actual}", LEGACY_LEDGER_REFS["media_assets"], object_id=asset_id)
            if self.mode == "publish-ready" and row.get("status") == "active" and row.get("rights_status") in {"unknown", "restricted"}:
                self.add("MEDIA_RIGHTS_NOT_READY", "公开媒体必须完成 rights clearance", LEGACY_LEDGER_REFS["media_assets"], object_id=asset_id)
            if self.mode == "publish-ready" and row.get("status") == "active" and row.get("authenticity_status") in {"unverified", "disputed"}:
                self.add("MEDIA_AUTHENTICITY_NOT_READY", "公开媒体不得保留 unverified/disputed authenticity", LEGACY_LEDGER_REFS["media_assets"], object_id=asset_id)

    def audit_changesets_and_recommendations(self) -> None:
        if not self.is_v2:
            return
        changesets = {
            row.get("changeset_id"): row
            for row in self.ledger_rows.get("changesets", [])
            if row.get("status") == "applied" and isinstance(row.get("changeset_id"), str)
        }
        recommendations = {
            row.get("recommendation_id"): row
            for row in self.ledger_rows.get("model_recommendations", [])
            if isinstance(row.get("recommendation_id"), str)
        }

        def audit_artifact(
            row: dict[str, Any],
            *,
            ref_field: str,
            hash_field: str,
            code_prefix: str,
            object_id: str | None,
            path: str,
        ) -> None:
            artifact = self.resolve_ref(row.get(ref_field), path)
            if artifact is None:
                return
            if not artifact.is_file():
                self.add(f"{code_prefix}_ARTIFACT_MISSING", f"可重算原件不存在：{row.get(ref_field)!r}", path, object_id=object_id)
                return
            actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
            if actual != row.get(hash_field):
                self.add(f"{code_prefix}_HASH_MISMATCH", f"原件摘要不匹配：实际 {actual}", path, object_id=object_id)

        for changeset_id, row in changesets.items():
            audit_artifact(
                row,
                ref_field="artifact_ref",
                hash_field="applied_hash",
                code_prefix="CHANGESET",
                object_id=changeset_id,
                path=LEGACY_LEDGER_REFS["changesets"],
            )
        for recommendation_id, row in recommendations.items():
            audit_artifact(
                row,
                ref_field="input_scope_ref",
                hash_field="input_scope_sha256",
                code_prefix="RECOMMENDATION_INPUT",
                object_id=recommendation_id,
                path=LEGACY_LEDGER_REFS["model_recommendations"],
            )
            audit_artifact(
                row,
                ref_field="response_ref",
                hash_field="response_sha256",
                code_prefix="RECOMMENDATION_RESPONSE",
                object_id=recommendation_id,
                path=LEGACY_LEDGER_REFS["model_recommendations"],
            )
        governed_rows = [
            row
            for kind, rows in self.ledger_rows.items()
            if kind not in {"observations", "changesets", "model_recommendations"}
            for row in rows
            if row.get("status") in {"signed", None}
            or (kind == "media_assets" and row.get("status") in {"active", "hold", "retired"})
        ]
        for row in governed_rows:
            object_id = self.ledger_object_id("", row)
            changeset_id = row.get("changeset_id")
            if not isinstance(changeset_id, str) or changeset_id not in changesets:
                self.add("CHANGESET_RECEIPT_MISSING", f"正式治理行缺 applied ChangeSet 收据：{changeset_id!r}", "governance/*.jsonl", object_id=object_id)
            review = row.get("review")
            if not isinstance(review, dict):
                continue
            recommendation_refs = review.get("recommendation_refs") if isinstance(review.get("recommendation_refs"), list) else []
            for recommendation_id in recommendation_refs:
                recommendation = recommendations.get(recommendation_id)
                if recommendation is None:
                    self.add("RECOMMENDATION_PROVENANCE_MISSING", f"模型建议缺原始响应 hash 台账：{recommendation_id}", "governance/*.jsonl", object_id=object_id)
                elif recommendation.get("role") != "recommendation_only":
                    self.add("MODEL_ROLE_INVALID", "模型只能作为 recommendation_only", LEGACY_LEDGER_REFS["model_recommendations"], object_id=recommendation_id)

    def audit_external_verifications(self) -> None:
        if not self.is_v2:
            return
        path = LEGACY_LEDGER_REFS["external_verifications"]
        seen_ids: set[str] = set()
        for row in self.ledger_rows.get("external_verifications", []):
            verification_id = row.get("verification_id")
            if not isinstance(verification_id, str) or not verification_id:
                self.add(
                    "VERIFICATION_ID_MISSING",
                    "ExternalVerification 缺 verification_id",
                    path,
                    object_id=str(row.get("__contract_line__")),
                )
                continue
            self.audit_schema(
                SCHEMA_DEFINITION_REGISTRY["biography-external-verification-v1"],
                row,
                "SCHEMA_EXTERNAL_VERIFICATION_INVALID",
                path,
                object_id=verification_id,
            )
            self.audit_row_subject(row, path, verification_id)
            if self.namespace and not verification_id.startswith(f"ver-{self.namespace}-"):
                self.add(
                    "VERIFICATION_NAMESPACE_MISMATCH",
                    "ExternalVerification ID 未包含 manifest namespace",
                    path,
                    object_id=verification_id,
                )
            if verification_id in seen_ids:
                self.add(
                    "VERIFICATION_ID_DUPLICATE",
                    f"ExternalVerification ID 重复：{verification_id}",
                    path,
                    object_id=verification_id,
                )
            else:
                seen_ids.add(verification_id)
                self.verifications[verification_id] = row

            target_ids = row.get("target_ids")
            source_ids = row.get("source_ids")
            semantic_ok = True
            if not isinstance(target_ids, list) or not target_ids:
                self.add(
                    "VERIFICATION_TARGETS_INVALID",
                    "ExternalVerification 必须声明非空 target_ids",
                    path,
                    object_id=verification_id,
                )
                target_ids = []
                semantic_ok = False
            if not isinstance(source_ids, list) or not source_ids:
                self.add(
                    "VERIFICATION_SOURCES_INVALID",
                    "ExternalVerification 必须声明非空 source_ids",
                    path,
                    object_id=verification_id,
                )
                source_ids = []
                semantic_ok = False
            for target_id in target_ids:
                kind = self.all_ids.get(target_id) if isinstance(target_id, str) else None
                target = self.canonical.get(kind, {}).get(target_id) if kind else None
                if target is None:
                    self.add(
                        "VERIFICATION_TARGET_MISSING",
                        f"ExternalVerification target 不存在：{target_id!r}",
                        path,
                        object_id=verification_id,
                    )
                    semantic_ok = False
                elif target.get("status") not in {"active", "hold"}:
                    self.add(
                        "VERIFICATION_TARGET_NOT_RESOLVABLE",
                        f"ExternalVerification target 必须是 active/hold：{target_id}",
                        path,
                        object_id=verification_id,
                    )
                    semantic_ok = False
            for source_id in source_ids:
                if source_id not in self.source_units:
                    self.add(
                        "VERIFICATION_SOURCE_UNKNOWN",
                        f"ExternalVerification source 不在 registry：{source_id!r}",
                        path,
                        object_id=verification_id,
                    )
                    semantic_ok = False
            formal_ok = self.audit_formal_review(row.get("review"), path, verification_id)
            status = row.get("status")
            if status not in {"signed", "superseded"}:
                self.add(
                    "VERIFICATION_STATUS_INVALID",
                    "ExternalVerification status 必须是 signed 或 superseded",
                    path,
                    object_id=verification_id,
                )
            elif status == "signed" and formal_ok and semantic_ok:
                self.signed_verification_ids.add(verification_id)

        for kind, objects in self.canonical.items():
            for object_id, row in objects.items():
                if row.get("status") not in {"active", "hold"}:
                    continue
                ref_groups: list[tuple[str, Any]] = [("verification_refs", row.get("verification_refs", []))]
                if kind == "works" and isinstance(row.get("reader_explanation"), dict):
                    ref_groups.append(
                        (
                            "reader_explanation.verification_refs",
                            row["reader_explanation"].get("verification_refs", []),
                        )
                    )
                for field_name, refs in ref_groups:
                    if not isinstance(refs, list):
                        self.add(
                            "VERIFICATION_REFS_INVALID",
                            f"{field_name} 必须是数组",
                            f"canonical/{kind}.jsonl",
                            object_id=object_id,
                        )
                        continue
                    for verification_id in refs:
                        verification = self.verifications.get(verification_id)
                        if verification is None:
                            self.add(
                                "VERIFICATION_REF_MISSING",
                                f"{field_name} 引用不存在：{verification_id!r}",
                                f"canonical/{kind}.jsonl",
                                object_id=object_id,
                            )
                            continue
                        if verification_id not in self.signed_verification_ids:
                            self.add(
                                "VERIFICATION_NOT_SIGNED",
                                f"{field_name} 只能引用正式 signed verification：{verification_id}",
                                f"canonical/{kind}.jsonl",
                                object_id=object_id,
                            )
                        verification_targets = verification.get("target_ids")
                        if (
                            not isinstance(verification_targets, list)
                            or object_id not in verification_targets
                        ):
                            self.add(
                                "VERIFICATION_TARGET_BACKLINK_MISSING",
                                f"verification {verification_id} 未把当前 Canonical 列为 target",
                                f"canonical/{kind}.jsonl",
                                object_id=object_id,
                            )

        for verification_id in self.signed_verification_ids:
            verification = self.verifications[verification_id]
            target_ids = verification.get("target_ids")
            for target_id in (target_ids if isinstance(target_ids, list) else []):
                kind = self.all_ids.get(target_id) if isinstance(target_id, str) else None
                target = self.canonical.get(kind, {}).get(target_id) if kind else None
                if target is None or target.get("status") not in {"active", "hold"}:
                    continue
                target_refs = target.get("verification_refs")
                if not isinstance(target_refs, list) or verification_id not in target_refs:
                    self.add(
                        "VERIFICATION_BACKLINK_MISSING",
                        f"signed verification {verification_id} 未被 target Canonical 反链",
                        f"canonical/{kind}.jsonl",
                        object_id=target_id,
                    )

    def audit_source_backlinks(self) -> None:
        if not self.is_v2:
            return
        for observation_id, row in self.observations.items():
            source_id = row.get("source_id")
            source = self.source_units.get(source_id) if isinstance(source_id, str) else None
            observation_refs = source.get("observation_refs") if source is not None else None
            if source is not None and (
                not isinstance(observation_refs, list) or observation_id not in observation_refs
            ):
                self.add(
                    "SOURCE_OBSERVATION_BACKLINK_MISSING",
                    f"source {source_id} 未反链 Observation",
                    "source-registry.json",
                    object_id=observation_id,
                )
        for verification_id, row in self.verifications.items():
            source_ids = row.get("source_ids")
            for source_id in (source_ids if isinstance(source_ids, list) else []):
                source = self.source_units.get(source_id) if isinstance(source_id, str) else None
                verification_refs = source.get("verification_refs") if source is not None else None
                if source is not None and (
                    not isinstance(verification_refs, list)
                    or verification_id not in verification_refs
                ):
                    self.add(
                        "SOURCE_VERIFICATION_BACKLINK_MISSING",
                        f"source {source_id} 未反链 ExternalVerification",
                        "source-registry.json",
                        object_id=verification_id,
                    )
        for source_id, source in self.source_units.items():
            observation_refs = source.get("observation_refs")
            for observation_id in (
                observation_refs if isinstance(observation_refs, list) else []
            ):
                observation_row = self.observations.get(observation_id)
                if observation_row is None:
                    self.add(
                        "SOURCE_OBSERVATION_REF_MISSING",
                        f"source 反链不存在 Observation：{observation_id!r}",
                        "source-registry.json",
                        object_id=source_id,
                    )
                elif observation_row.get("source_id") != source_id:
                    self.add(
                        "SOURCE_OBSERVATION_REF_MISMATCH",
                        f"Observation {observation_id} 的 source_id 与反链不一致",
                        "source-registry.json",
                        object_id=source_id,
                    )
            verification_refs = source.get("verification_refs")
            for verification_id in (
                verification_refs if isinstance(verification_refs, list) else []
            ):
                verification = self.verifications.get(verification_id)
                if verification is None:
                    self.add(
                        "SOURCE_VERIFICATION_REF_MISSING",
                        f"source 反链不存在 ExternalVerification：{verification_id!r}",
                        "source-registry.json",
                        object_id=source_id,
                    )
                elif source_id not in verification.get("source_ids", []):
                    self.add(
                        "SOURCE_VERIFICATION_REF_MISMATCH",
                        f"ExternalVerification {verification_id} 的 source_ids 与反链不一致",
                        "source-registry.json",
                        object_id=source_id,
                    )

    def audit_evidence_closure(self) -> None:
        for kind, objects in self.canonical.items():
            for object_id, row in objects.items():
                status = row.get("status")
                if status not in {"active", "hold"}:
                    continue
                evidence_refs = row.get("evidence_refs")
                if not isinstance(evidence_refs, list) or not evidence_refs:
                    self.add(
                        "ACTIVE_OBJECT_EVIDENCE_MISSING"
                        if status == "active"
                        else "HOLD_OBJECT_EVIDENCE_MISSING",
                        f"{status} Canonical 必须有 evidence_refs",
                        f"canonical/{kind}.jsonl",
                        object_id=object_id,
                    )
                    continue
                ref_groups: list[tuple[str, Any, str, str, str]] = [
                    (
                        "evidence_refs",
                        evidence_refs,
                        "EVIDENCE_REF_INVALID",
                        "EVIDENCE_OBSERVATION_MISSING",
                        "EVIDENCE_NOT_DECIDED",
                    ),
                    (
                        "interpretation_refs",
                        row.get("interpretation_refs", []),
                        "INTERPRETATION_REF_INVALID",
                        "INTERPRETATION_OBSERVATION_MISSING",
                        "INTERPRETATION_NOT_DECIDED",
                    ),
                ]
                if kind == "works" and isinstance(row.get("reader_explanation"), dict):
                    explanation = row["reader_explanation"]
                    ref_groups.extend(
                        [
                            (
                                "reader_explanation.evidence_refs",
                                explanation.get("evidence_refs", []),
                                "EVIDENCE_REF_INVALID",
                                "EVIDENCE_OBSERVATION_MISSING",
                                "EVIDENCE_NOT_DECIDED",
                            ),
                            (
                                "reader_explanation.interpretation_refs",
                                explanation.get("interpretation_refs", []),
                                "INTERPRETATION_REF_INVALID",
                                "INTERPRETATION_OBSERVATION_MISSING",
                                "INTERPRETATION_NOT_DECIDED",
                            ),
                        ]
                    )
                decided = self.coverage.get(object_id, set())
                for field_name, refs, invalid_code, missing_code, undecided_code in ref_groups:
                    if not isinstance(refs, list):
                        self.add(
                            invalid_code,
                            f"{field_name} 必须是数组",
                            f"canonical/{kind}.jsonl",
                            object_id=object_id,
                        )
                        continue
                    if len(refs) != len(set(value for value in refs if isinstance(value, str))):
                        self.add(
                            "CANONICAL_OBSERVATION_REFS_DUPLICATE",
                            f"{field_name} 不得重复",
                            f"canonical/{kind}.jsonl",
                            object_id=object_id,
                        )
                    for observation_id in refs:
                        if not isinstance(observation_id, str):
                            self.add(
                                invalid_code,
                                f"{field_name} 含非字符串",
                                f"canonical/{kind}.jsonl",
                                object_id=object_id,
                            )
                            continue
                        if observation_id not in self.observations:
                            self.add(
                                missing_code,
                                f"{field_name} 引用不存在：{observation_id}",
                                f"canonical/{kind}.jsonl",
                                object_id=object_id,
                            )
                        if observation_id not in decided:
                            self.add(
                                undecided_code,
                                f"{field_name} 未被同 target 的 signed resolution 覆盖：{observation_id}",
                                f"canonical/{kind}.jsonl",
                                object_id=object_id,
                                severity="error" if self.is_v2 else "migration",
                            )

    def audit_publish_ready(self, editorial_refs: dict[str, Any]) -> None:
        publication = self.manifest.get("publication")
        projection = self.manifest.get("projection")
        if not isinstance(publication, dict) or publication.get("status") not in {
            "review",
            "published",
        }:
            self.add(
                "PUBLICATION_STATUS_NOT_READY",
                "publish-ready 要求 publication.status 为 review 或 published",
                "manifest.json#/publication/status",
            )
        else:
            route = projection.get("route_base") if isinstance(projection, dict) else None
            if publication.get("href") != route:
                self.add(
                    "PUBLICATION_HREF_NOT_READY",
                    "publish-ready 要求 publication.href 与 route_base 一致",
                    "manifest.json#/publication/href",
                )
            summary = publication.get("catalog_summary")
            if not isinstance(summary, str) or not summary.strip():
                self.add(
                    "PUBLICATION_SUMMARY_EMPTY",
                    "publish-ready 要求非空 catalog_summary",
                    "manifest.json#/publication/catalog_summary",
                )

        governance = self.manifest.get("governance")
        ledgers = governance.get("ledgers", []) if isinstance(governance, dict) else []
        required_flags = {
            item.get("kind"): item.get("required_for_publication")
            for item in ledgers
            if isinstance(item, dict)
        }
        for kind in sorted(REQUIRED_LEDGER_KINDS):
            if required_flags.get(kind) is not True:
                self.add(
                    "LEDGER_NOT_REQUIRED_FOR_PUBLICATION",
                    f"publish-ready 必需账本必须 required_for_publication=true：{kind}",
                    "manifest.json#/governance/ledgers",
                    object_id=kind,
                )

        def require_conditional_ledger(kind: str, condition: bool) -> None:
            if condition and required_flags.get(kind) is not True:
                self.add(
                    "CONDITIONAL_LEDGER_NOT_REQUIRED_FOR_PUBLICATION",
                    f"当前公开内容要求 {kind} 的 required_for_publication=true",
                    "manifest.json#/governance/ledgers",
                    object_id=kind,
                )

        require_conditional_ledger(
            "source_coverage_decisions", bool(self.source_units)
        )
        require_conditional_ledger(
            "work_classifications",
            any(row.get("status") == "active" for row in self.canonical["works"].values()),
        )
        require_conditional_ledger(
            "work_identity_decisions",
            any(row.get("status") == "active" for row in self.canonical["works"].values()),
        )
        require_conditional_ledger(
            "quote_attribution_audits",
            any(row.get("status") == "active" for row in self.canonical["quotes"].values()),
        )
        require_conditional_ledger(
            "media_assets",
            any(row.get("status") == "active" for row in self.ledger_rows.get("media_assets", [])),
        )

        editorial: dict[str, Any] = {}
        for kind, ref in editorial_refs.items():
            path = self.resolve_ref(ref, f"manifest.json#/editorial/{kind}")
            if path is not None:
                editorial[kind] = self.load_json(path)

        chapters_doc = editorial.get("chapters")
        chapters = chapters_doc.get("chapters") if isinstance(chapters_doc, dict) else None
        if not isinstance(chapters, list) or not chapters:
            self.add(
                "EDITORIAL_CHAPTERS_EMPTY",
                "publish-ready 要求 chapters.json 含非空 chapters",
                "editorial/chapters.json",
            )
            chapter_ids: list[str] = []
        else:
            chapter_ids = [
                item.get("chapter_id")
                for item in chapters
                if isinstance(item, dict) and isinstance(item.get("chapter_id"), str)
            ]

        paragraph_rows: dict[str, dict[str, Any]] = {}
        if isinstance(chapters, list):
            for chapter_index, chapter in enumerate(chapters):
                if not isinstance(chapter, dict):
                    continue
                paragraphs = chapter.get("paragraphs")
                if not isinstance(paragraphs, list):
                    continue
                for paragraph_index, paragraph in enumerate(paragraphs):
                    path = f"editorial/chapters.json#/chapters/{chapter_index}/paragraphs/{paragraph_index}"
                    if not isinstance(paragraph, dict):
                        self.add("EDITORIAL_PARAGRAPH_INVALID", "paragraph 必须是对象", path)
                        continue
                    paragraph_id = paragraph.get("paragraph_id")
                    if not isinstance(paragraph_id, str) or not paragraph_id:
                        self.add("EDITORIAL_PARAGRAPH_ID_MISSING", "公开段落必须有稳定 paragraph_id", path)
                        continue
                    if paragraph_id in paragraph_rows:
                        self.add("EDITORIAL_PARAGRAPH_ID_DUPLICATE", "paragraph_id 不得重复", path, object_id=paragraph_id)
                        continue
                    paragraph_rows[paragraph_id] = paragraph
                    evidence_refs = paragraph.get("evidence_refs")
                    if not isinstance(evidence_refs, list) or not evidence_refs:
                        self.add("EDITORIAL_PARAGRAPH_EVIDENCE_EMPTY", "公开段落必须有非空 evidence_refs", path, object_id=paragraph_id)
                        continue
                    for observation_id in evidence_refs:
                        admissions = self.signed_admissions.get(observation_id, [])
                        if observation_id not in self.observations:
                            self.add("EDITORIAL_PARAGRAPH_EVIDENCE_MISSING", f"段落证据不存在：{observation_id}", path, object_id=paragraph_id)
                        elif len(admissions) != 1 or admissions[0].get("verdict") != "accept":
                            self.add("EDITORIAL_PARAGRAPH_EVIDENCE_NOT_ACCEPTED", f"段落证据未被恰一次 accept：{observation_id}", path, object_id=paragraph_id)

        require_conditional_ledger("prose_risk_reviews", bool(paragraph_rows))
        prose_reviews: dict[str, list[dict[str, Any]]] = defaultdict(list)
        prose_path = LEGACY_LEDGER_REFS["prose_risk_reviews"]
        for review_row in self.ledger_rows.get("prose_risk_reviews", []):
            if review_row.get("status") != "signed":
                continue
            paragraph_id = review_row.get("paragraph_id")
            if not isinstance(paragraph_id, str) or paragraph_id not in paragraph_rows:
                self.add("PROSE_REVIEW_TARGET_MISSING", "prose review 引用不存在的 paragraph_id", prose_path, object_id=str(paragraph_id))
                continue
            prose_reviews[paragraph_id].append(review_row)
            if review_row.get("verdict") != "approved":
                self.add("PROSE_REVIEW_NOT_APPROVED", "公开段落的现役审查 verdict 必须为 approved", prose_path, object_id=paragraph_id)
            actual_text_hash = paragraph_text_sha256(paragraph_rows[paragraph_id])
            if review_row.get("text_sha256") != actual_text_hash:
                self.add("PROSE_REVIEW_TEXT_HASH_MISMATCH", f"段落正文已变化：实际 {actual_text_hash}", prose_path, object_id=paragraph_id)
            paragraph_evidence = set(paragraph_rows[paragraph_id].get("evidence_refs", []))
            for observation_id in review_row.get("evidence_refs", []):
                if observation_id not in paragraph_evidence:
                    self.add("PROSE_REVIEW_EVIDENCE_OUTSIDE_PARAGRAPH", f"prose review 引用了段落外证据：{observation_id}", prose_path, object_id=paragraph_id)
        for paragraph_id in paragraph_rows:
            if len(prose_reviews.get(paragraph_id, [])) != 1:
                self.add("PROSE_REVIEW_EXACT_ONCE", "每个公开段落必须恰有一条 signed prose risk review", prose_path, object_id=paragraph_id)

        order_doc = editorial.get("chapter_order")
        order = order_doc.get("order") if isinstance(order_doc, dict) else None
        if not isinstance(order, list) or not order:
            self.add(
                "EDITORIAL_CHAPTER_ORDER_EMPTY",
                "publish-ready 要求 chapter_order.json 含非空 order",
                "editorial/chapter_order.json",
            )
            order_ids: list[str] = []
        else:
            order_ids = [
                item.get("chapter_id")
                for item in order
                if isinstance(item, dict) and isinstance(item.get("chapter_id"), str)
            ]
        seqs = [item.get("seq") for item in order if isinstance(item, dict)] if isinstance(order, list) else []
        exact_chapter_closure = (
            bool(chapter_ids)
            and bool(order_ids)
            and len(chapter_ids) == len(chapters)
            and len(order_ids) == len(order)
            and len(chapter_ids) == len(set(chapter_ids))
            and len(order_ids) == len(set(order_ids))
            and set(chapter_ids) == set(order_ids)
            and seqs == list(range(1, len(order_ids) + 1))
        )
        if chapters and order and not exact_chapter_closure:
            self.add(
                "EDITORIAL_CHAPTER_ORDER_MISMATCH",
                "chapter_order 必须逐一、无重复覆盖 chapters，且 seq 从 1 连续递增",
                "editorial/chapter_order.json",
            )

        for kind in ("overview", "layout", "dossier"):
            value = editorial.get(kind)
            if not isinstance(value, dict) or not value:
                self.add(
                    f"EDITORIAL_{kind.upper()}_EMPTY",
                    f"publish-ready 要求 {kind}.json 为非空对象",
                    f"editorial/{kind}.json",
                )
            elif value.get("subject_id") not in {None, self.subject_id}:
                self.add(
                    "EDITORIAL_SUBJECT_MISMATCH",
                    f"{kind}.json subject_id 与 manifest 不一致",
                    f"editorial/{kind}.json",
                    object_id=kind,
                )
        for kind, value in (("chapters", chapters_doc), ("chapter_order", order_doc)):
            if isinstance(value, dict) and value.get("subject_id") not in {None, self.subject_id}:
                self.add(
                    "EDITORIAL_SUBJECT_MISMATCH",
                    f"{kind}.json subject_id 与 manifest 不一致",
                    f"editorial/{kind}.json",
                    object_id=kind,
                )


def audit_store(store_root: str | Path, *, mode: str = "audit") -> ContractAuditReport:
    """Audit a subject store without mutating it.

    ``strict-data`` checks the durable data/graph contract. ``publish-ready``
    adds publication metadata and Editorial completeness. ``strict`` remains a
    compatibility alias for ``strict-data`` while callers migrate.
    """

    normalized_mode = "strict-data" if mode == "strict" else mode
    if normalized_mode not in {"audit", "strict-data", "publish-ready"}:
        raise ValueError("mode must be 'audit', 'strict-data', or 'publish-ready'")
    return _Auditor(Path(store_root), normalized_mode).run()


def audit_corpus(corpus_root: str | Path, *, mode: str = "audit") -> ContractAuditReport:
    """Audit a declared multi-subject corpus and its isolation invariants."""

    normalized_mode = "strict-data" if mode == "strict" else mode
    if normalized_mode not in {"audit", "strict-data", "publish-ready"}:
        raise ValueError("mode must be 'audit', 'strict-data', or 'publish-ready'")
    root = Path(corpus_root).resolve()
    issues: list[ContractIssue] = []

    def add(code: str, message: str, path: str, *, severity: str = "error", object_id: str | None = None) -> None:
        issues.append(ContractIssue(code, message, path, severity, object_id))

    registry_path = root / "corpus.json"
    if not root.is_dir():
        add("CORPUS_ROOT_MISSING", "人物 corpus 目录不存在", str(root), severity="fatal")
        return ContractAuditReport(str(root), normalized_mode, "corpus", "biography-corpus-v1", issues)
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        add("CORPUS_REGISTRY_UNAVAILABLE", f"corpus.json 无法读取：{error}", "corpus.json", severity="fatal")
        return ContractAuditReport(str(root), normalized_mode, "corpus", None, issues)
    for detail in validate_schema_instance("BiographyCorpusV1", registry):
        add("SCHEMA_CORPUS_INVALID", detail, "corpus.json")
    entries = registry.get("subjects") if isinstance(registry, dict) else []
    if not isinstance(entries, list):
        entries = []
    uniqueness: dict[str, dict[str, str]] = {
        field_name: {}
        for field_name in ("slug", "subject_id", "id_namespace", "route_base", "store_ref")
    }
    global_ids: dict[str, str] = {}
    declared_store_refs: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        entry_path = f"corpus.json#/subjects/{index}"
        slug = entry.get("slug")
        for field_name, seen in uniqueness.items():
            value = entry.get(field_name)
            if not isinstance(value, str):
                continue
            if value in seen:
                add(
                    f"CORPUS_{field_name.upper()}_DUPLICATE",
                    f"{field_name} 已由 {seen[value]} 使用",
                    entry_path,
                    object_id=value,
                )
            else:
                seen[value] = str(slug)
        store_ref = entry.get("store_ref")
        if not isinstance(store_ref, str):
            continue
        declared_store_refs.add(Path(store_ref).as_posix())
        store_root = (root / store_ref).resolve()
        try:
            store_root.relative_to(root)
        except ValueError:
            add("CORPUS_STORE_PATH_ESCAPE", "store_ref 逃逸 corpus_root", entry_path, object_id=str(slug))
            continue
        child = audit_store(store_root, mode=normalized_mode)
        issues.extend(
            ContractIssue(
                issue.code,
                issue.message,
                f"{store_ref}/{issue.path}",
                issue.severity,
                issue.object_id,
            )
            for issue in child.issues
        )
        try:
            raw_manifest = json.loads((store_root / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(raw_manifest, dict):
            continue
        subject = raw_manifest.get("subject")
        projection = raw_manifest.get("projection")
        publication = raw_manifest.get("publication")
        if raw_manifest.get("schema_version") == MANIFEST_V2:
            route_base = projection.get("route_base") if isinstance(projection, dict) else None
        else:
            route_base = publication.get("href") if isinstance(publication, dict) else None
        expected = {
            "slug": subject.get("slug") if isinstance(subject, dict) else raw_manifest.get("subject"),
            "subject_id": subject.get("subject_id") if isinstance(subject, dict) else raw_manifest.get("subject_id"),
            "id_namespace": subject.get("id_namespace") if isinstance(subject, dict) else raw_manifest.get("id_namespace"),
            "route_base": route_base,
        }
        for field_name, value in expected.items():
            if entry.get(field_name) != value:
                add("CORPUS_DESCRIPTOR_MISMATCH", f"registry {field_name} 与 store manifest 不一致", entry_path, object_id=str(slug))
        canonical = raw_manifest.get("canonical") if isinstance(raw_manifest, dict) else None
        refs = canonical if isinstance(canonical, dict) else DEFAULT_CANONICAL_REFS
        for kind, ref in refs.items():
            if kind not in CANONICAL_KINDS or not isinstance(ref, str):
                continue
            path = (store_root / ref).resolve()
            try:
                path.relative_to(store_root)
            except ValueError:
                # The child audit already reports the invalid reference.  Do
                # not read it again while building the corpus-wide ID index.
                continue
            if not path.is_file():
                continue
            try:
                rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            id_field = ID_FIELDS[kind]
            for row in rows:
                object_id = row.get(id_field) if isinstance(row, dict) else None
                if not isinstance(object_id, str):
                    continue
                owner = global_ids.get(object_id)
                if owner is not None and owner != slug:
                    add("CORPUS_CANONICAL_ID_COLLISION", f"Canonical ID 已由 {owner} 使用", f"{store_ref}/{ref}", object_id=object_id)
                else:
                    global_ids[object_id] = str(slug)

    discovered_store_refs: set[str] = set()
    for manifest_path in root.rglob("manifest.json"):
        relative = manifest_path.parent.relative_to(root)
        if relative == Path(".") or any(part.startswith(".") for part in relative.parts):
            continue
        discovered_store_refs.add(relative.as_posix())
    for canonical_path in root.rglob("canonical"):
        if not canonical_path.is_dir():
            continue
        relative = canonical_path.parent.relative_to(root)
        if relative == Path(".") or any(part.startswith(".") for part in relative.parts):
            continue
        discovered_store_refs.add(relative.as_posix())
    for store_ref in sorted(discovered_store_refs - declared_store_refs):
        add(
            "CORPUS_STORE_UNREGISTERED",
            "磁盘中的人物 store 未登记到 corpus.json",
            store_ref,
            object_id=store_ref,
        )
    return ContractAuditReport(str(root), normalized_mode, "corpus", "biography-corpus-v1", issues)


def assert_store_ready(
    store_root: str | Path,
    *,
    phase: str,
    legacy_subject_ids: frozenset[str] | set[str] | None = None,
) -> ContractAuditReport:
    """Fail closed at compile/export.

    Public callers reject every v1 store by default.  A product that still has
    a named migration exception must pass an explicit stable-subject allowlist;
    this prevents a generic legacy branch from silently grandfathering future
    people.
    """

    if phase not in {"compile", "export"}:
        raise ValueError("phase must be 'compile' or 'export'")
    root = Path(store_root)
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        report = audit_store(root, mode="audit")
        raise ValueError(format_human_report(report))
    manifest_version = manifest.get("schema_version")
    if manifest_version == MANIFEST_V1:
        report = audit_store(root, mode="audit")
        allowed = frozenset(legacy_subject_ids or ())
        subject_id = manifest.get("subject_id")
        unreviewed_issues = [
            issue
            for issue in report.issues
            if issue.severity != "migration"
            or issue.code not in LEGACY_V1_MIGRATION_CODES
        ]
        if report.fatal_count or subject_id not in allowed or unreviewed_issues:
            raise ValueError(format_human_report(report))
        return report
    if manifest_version != MANIFEST_V2:
        report = audit_store(root, mode="audit")
        raise ValueError(format_human_report(report))
    publication = manifest.get("publication") if isinstance(manifest.get("publication"), dict) else {}
    if publication.get("status") == "draft":
        report = audit_store(root, mode="audit")
        if _is_pristine_v2_bootstrap(root, manifest, report):
            return report
    mode = "publish-ready" if phase == "export" and publication.get("status") in {"review", "published"} else "strict-data"
    report = audit_store(root, mode=mode)
    if report.issues:
        raise ValueError(format_human_report(report))
    return report


def _is_pristine_v2_bootstrap(
    root: Path,
    manifest: dict[str, Any],
    report: ContractAuditReport,
) -> bool:
    """Recognize only the exact, fact-free draft emitted by the public initializer.

    This narrow exception lets a freshly initialized store compile before its
    subject Person exists.  Missing declarations, alternate paths, non-empty
    ledgers, or editorial content must take the normal strict-data path.
    """

    if report.fatal_count:
        return False
    if {issue.code for issue in report.issues} - {"SUBJECT_PERSON_MISSING"}:
        return False

    canonical = manifest.get("canonical")
    editorial = manifest.get("editorial")
    governance = manifest.get("governance")
    if not isinstance(canonical, dict) or set(canonical) != set(DEFAULT_CANONICAL_REFS):
        return False
    expected_editorial = {**DEFAULT_EDITORIAL_REFS, "media": "editorial/media.json"}
    if not isinstance(editorial, dict) or editorial != expected_editorial:
        return False
    if not isinstance(governance, dict):
        return False
    source_descriptor = governance.get("source_registry")
    ledgers = governance.get("ledgers")
    if not isinstance(source_descriptor, dict) or not isinstance(ledgers, list):
        return False
    ledger_refs = {
        item.get("kind"): item.get("ref")
        for item in ledgers
        if isinstance(item, dict) and isinstance(item.get("kind"), str)
    }
    if len(ledger_refs) != len(ledgers) or set(ledger_refs) != set(LEDGER_SCHEMA_VERSIONS):
        return False

    declared_refs = [source_descriptor.get("ref"), *canonical.values(), *editorial.values(), *ledger_refs.values()]
    if not all(isinstance(ref, str) and ref for ref in declared_refs):
        return False
    required_files = manifest.get("required_files")
    if not isinstance(required_files, list) or set(required_files) != set(declared_refs):
        return False

    try:
        for ref in [*canonical.values(), *ledger_refs.values()]:
            path = (root / ref).resolve()
            path.relative_to(root.resolve())
            if not path.is_file() or any(
                line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            ):
                return False

        registry_path = (root / source_descriptor["ref"]).resolve()
        registry_path.relative_to(root.resolve())
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        if not isinstance(registry, dict) or registry.get("source_units") != []:
            return False

        subject = manifest.get("subject")
        subject_id = subject.get("subject_id") if isinstance(subject, dict) else None
        documents: dict[str, Any] = {}
        for kind, ref in editorial.items():
            document_path = (root / ref).resolve()
            document_path.relative_to(root.resolve())
            documents[kind] = json.loads(document_path.read_text(encoding="utf-8"))
        chapter_order = documents["chapter_order"]
        chapters = documents["chapters"]
        overview = documents["overview"]
        layout = documents["layout"]
        dossier = documents["dossier"]
        media = documents["media"]
        if chapter_order != {
            "schema_version": "biography-chapter-order-v1",
            "subject_id": subject_id,
            "order": [],
        }:
            return False
        if chapters != {
            "schema_version": "biography-editorial-chapters-v1",
            "subject_id": subject_id,
            "chapters": [],
        }:
            return False
        public_overview = {
            "schema_version": "biography-editorial-overview-v1",
            "subject_id": subject_id,
            "core_facts": [],
            "blocks": [],
        }
        product_overview_keys = {
            "schema_version",
            "display_name",
            "latin_name",
            "life_span",
            "lede",
            "core_facts",
            "blocks",
            "media",
        }
        product_overview_empty = (
            isinstance(overview, dict)
            and set(overview) == product_overview_keys
            and overview.get("schema_version") == "biography-overview-v1"
            and all(isinstance(overview.get(key), str) for key in ("display_name", "latin_name"))
            and overview.get("life_span") == ""
            and overview.get("lede") == ""
            and overview.get("core_facts") == []
            and overview.get("blocks") == []
            and overview.get("media") == {}
        )
        if overview != public_overview and not product_overview_empty:
            return False
        public_layout = {"schema_version": "biography-layout-v1", "subject_id": subject_id}
        product_layout = {
            "schema_version": "biography-layout-v1",
            "modules": [],
            "image_radius_px": 6,
            "control_radius_px": 3,
        }
        if layout not in (public_layout, product_layout):
            return False
        public_dossier = {
            "schema_version": "biography-dossier-config-v1",
            "subject_id": subject_id,
            "sections": [],
        }
        product_dossier_empty = (
            isinstance(dossier, dict)
            and set(dossier)
            == {"schema_version", "presentation", "relation_groups", "sections"}
            and dossier.get("schema_version") == "biography-dossier-config-v1"
            and isinstance(dossier.get("presentation"), dict)
            and all(
                isinstance(dossier["presentation"].get(key), str)
                for key in ("dossier_intro", "timeline_intro")
            )
            and dossier.get("relation_groups") == []
            and dossier.get("sections") == []
        )
        if dossier != public_dossier and not product_dossier_empty:
            return False
        public_media = {
            "schema_version": "biography-media-ledger-v1",
            "subject_id": subject_id,
            "assets": [],
            "selections": {},
        }
        if media not in ({}, public_media):
            return False
    except (KeyError, OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return False
    return True


def issue_codes(report: ContractAuditReport) -> set[str]:
    """Small test/report helper; the audit predicate remains `audit_store`."""

    return {issue.code for issue in report.issues}


def format_human_report(report: ContractAuditReport, *, limit: int = 50) -> str:
    counts = report.counts()
    lines = [
        (
            f"[{report.status}] mode={report.mode} subject={report.subject or 'unknown'} "
            f"manifest={report.manifest_schema_version or 'unknown'} "
            f"migration={counts['migration']} error={counts['error']} fatal={counts['fatal']}"
        )
    ]
    if report.issues:
        for issue in report.issues[:limit]:
            marker = {"migration": "MIGRATION", "error": "ERROR", "fatal": "FATAL"}.get(
                issue.severity, issue.severity.upper()
            )
            object_suffix = f" [{issue.object_id}]" if issue.object_id else ""
            lines.append(
                f"- {marker} {issue.code} {issue.path}{object_suffix}: {issue.message}"
            )
        remaining = len(report.issues) - limit
        if remaining > 0:
            lines.append(f"- … 其余 {remaining} 条省略；用 --json 查看完整报告。")
    return "\n".join(lines)


__all__ = [
    "CONTRACT_VERSION",
    "MANIFEST_V1",
    "MANIFEST_V2",
    "WINDOWS_RESERVED_BASENAMES",
    "SCHEMA_DEFINITION_REGISTRY",
    "ContractAuditReport",
    "ContractIssue",
    "assert_store_ready",
    "audit_corpus",
    "audit_store",
    "format_human_report",
    "issue_codes",
    "manifest_v2_skeleton",
    "local_ref_error",
    "paragraph_text_sha256",
    "governed_record_sha256",
    "normalize_manifest",
    "validate_schema_instance",
]

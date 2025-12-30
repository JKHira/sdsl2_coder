from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    path: Path
    raw: dict[str, Any]
    allowed_profiles: set[str]
    kinds_allowlist_by_profile: dict[str, set[str]]
    annotated_decl_required: set[str]
    annotation_only_required: set[str]
    annotation_only_and_bind_required: set[str]
    annotation_only_allowed: set[str]
    bind_target_allowed_kinds: set[str]
    bind_target_required_keys: set[str]
    rel_id_regex: re.Pattern[str]
    stable_id_prefix_required: bool
    contract_token_regex: re.Pattern[str]
    ssot_token_regex: re.Pattern[str]
    contract_token_allowed_fields: set[str]
    ssot_token_allowed_fields: set[str]
    topology_edge_required_fields: set[str]
    topology_edge_direction_vocab: set[str]


def load_config(path: Path) -> Config:
    if not path.exists():
        raise ConfigError(f"CONFIG_NOT_FOUND: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"CONFIG_INVALID_JSON: {path}: {exc}") from exc

    allowed_profiles = set(raw.get("repo_profile", {}).get("profiles", {}).get("allowed", []))
    kinds_allowlist_by_profile = {
        profile: set(kinds)
        for profile, kinds in raw.get("kinds", {})
        .get("allowlist_by_profile", {})
        .items()
    }
    required_form = raw.get("kinds", {}).get("required_statement_form", {})
    annotated_decl_required = set(required_form.get("AnnotatedDecl_required", []))
    annotation_only_required = set(required_form.get("AnnotationOnly_required", []))
    annotation_only_and_bind_required = set(
        required_form.get("AnnotationOnly_and_bind_required", [])
    )
    annotation_only_allowed = set(required_form.get("AnnotationOnly_allowed", []))

    bind_target = raw.get("kinds", {}).get("bind_target", {})
    bind_target_allowed_kinds = set(bind_target.get("allowed_kinds", []))
    bind_target_required_keys = set(bind_target.get("required_keys", []))

    rel_id_format = raw.get("repo_profile", {}).get("stable_id", {}).get(
        "rel_id_format", ""
    )
    rel_id_regex = re.compile(rel_id_format) if rel_id_format else re.compile(r"^$")

    stable_id_prefix_required = bool(
        raw.get("repo_profile", {}).get("stable_id", {}).get("id_prefix_required", False)
    )

    tokens = raw.get("tokens", {})
    contract_token_regex = re.compile(tokens.get("contract_token", {}).get("regex", "^$"))
    ssot_token_regex = re.compile(tokens.get("ssot_token", {}).get("regex", "^$"))
    placement = tokens.get("placement_closure", {})
    contract_token_allowed_fields = set(
        placement.get("contract_token_allowed_fields_closed_set", [])
    )
    ssot_token_allowed_fields = set(placement.get("ssot_token_allowed_fields_closed_set", []))

    topology = raw.get("topology_semantics", {})
    topology_edge_required_fields = set(topology.get("edge_required_fields", []))
    topology_edge_direction_vocab = set(topology.get("edge_direction_vocab", []))

    return Config(
        path=path,
        raw=raw,
        allowed_profiles=allowed_profiles,
        kinds_allowlist_by_profile=kinds_allowlist_by_profile,
        annotated_decl_required=annotated_decl_required,
        annotation_only_required=annotation_only_required,
        annotation_only_and_bind_required=annotation_only_and_bind_required,
        annotation_only_allowed=annotation_only_allowed,
        bind_target_allowed_kinds=bind_target_allowed_kinds,
        bind_target_required_keys=bind_target_required_keys,
        rel_id_regex=rel_id_regex,
        stable_id_prefix_required=stable_id_prefix_required,
        contract_token_regex=contract_token_regex,
        ssot_token_regex=ssot_token_regex,
        contract_token_allowed_fields=contract_token_allowed_fields,
        ssot_token_allowed_fields=ssot_token_allowed_fields,
        topology_edge_required_fields=topology_edge_required_fields,
        topology_edge_direction_vocab=topology_edge_direction_vocab,
    )

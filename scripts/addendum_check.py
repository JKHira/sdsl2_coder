#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.addendum_policy import load_addendum_policy
from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.lint import _capture_metadata, _parse_metadata_pairs
from sdslv2_builder.refs import RELID_RE, parse_internal_ref


PLACEHOLDER_RE = re.compile(r"\b(None|TBD|Opaque)\b")
CONTRACT_TOKEN_RE = re.compile(r"\bCONTRACT\.[A-Za-z0-9_.-]+\b")
DIRECTION_VOCAB = {"pub", "sub", "req", "rep", "rw", "call"}
ANNOTATION_KIND_RE = re.compile(r"^\s*@(?P<kind>[A-Za-z_][A-Za-z0-9_]*)\b")

EDGEINTENT_KEYS_REQUIRED = {"id", "from", "to"}
EDGEINTENT_KEYS_OPTIONAL = {"direction", "channel", "note", "owner", "contract_hint"}
EDGEINTENT_KEYS_ALLOWED = EDGEINTENT_KEYS_REQUIRED | EDGEINTENT_KEYS_OPTIONAL

DEFAULT_SEVERITY = {
    "ADD_STAGE_INVALID": "fail",
    "ADD_STAGE_IN_CONTRACT_PROFILE": "fail",
    "ADD_EDGEINTENT_PROFILE": "fail",
    "ADD_EDGEINTENT_KEYS": "fail",
    "ADD_EDGEINTENT_FORBIDDEN_KEYS": "fail",
    "ADD_EDGEINTENT_CONTRACT_HINT_TOKENS": "fail",
    "ADD_EDGEINTENT_UNKNOWN_KEYS": "fail",
    "ADD_L0_EDGE_FORBIDDEN": "fail",
    "ADD_L0_TERMINAL_FORBIDDEN": "fail",
    "ADD_L1_EDGEINTENT_FORBIDDEN": "diag",
    "ADD_L2_EDGEINTENT_FORBIDDEN": "fail",
    "ADD_PLACEHOLDER_IN_SDSL": "fail",
    "ADD_L0_KIND_FORBIDDEN": "fail",
    "ADD_EDGEINTENT_ID_INVALID": "fail",
    "ADD_EDGEINTENT_FROM_TO_INVALID": "fail",
    "ADD_EDGEINTENT_DIRECTION_INVALID": "fail",
    "ADD_STAGE_BELOW_REPO_MIN": "fail",
    "ADD_MIXED_STAGES_FORBIDDEN": "fail",
    "ADD_METADATA_DUPLICATE_KEY": "fail",
    "ADD_FILE_HEADER_UNREADABLE": "diag",
    "ADD_POLICY_NOT_FOUND": "diag",
    "ADD_POLICY_MULTIPLE_FOUND": "fail",
    "ADD_POLICY_PARSE_FAILED": "fail",
    "ADD_POLICY_SCHEMA_INVALID": "fail",
}


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _get_nested(policy: dict, keys: list[str], default):
    cur = policy
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _severity(policy: dict, code: str) -> str:
    severity = DEFAULT_SEVERITY.get(code, "fail")
    if code == "ADD_L1_EDGEINTENT_FORBIDDEN":
        mode = _get_nested(policy, ["stage_policy", "l1_edgeintent_mode"], "diag")
        severity = "fail" if str(mode).lower() == "fail" else "diag"
    if code == "ADD_L0_KIND_FORBIDDEN":
        mode = _get_nested(policy, ["stage_policy", "l0_kind_mode"], "fail")
        mode = str(mode).lower()
        if mode in {"diag", "fail", "ignore"}:
            severity = mode
    if code == "ADD_EDGEINTENT_UNKNOWN_KEYS":
        mode = _get_nested(policy, ["stage_policy", "edgeintent_unknown_keys"], "fail")
        mode = str(mode).lower()
        if mode in {"diag", "fail", "ignore"}:
            severity = mode
    return severity


def _emit_diag(
    diags: list[Diagnostic],
    code: str,
    message: str,
    expected: str,
    got: str,
    path: str,
) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def _strip_strings(text: str) -> str:
    out = []
    in_str = False
    escape = False
    for ch in text:
        if in_str:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        out.append(ch)
    return "".join(out)


def _strip_block_comments(text: str, in_block: bool) -> tuple[str, bool]:
    out: list[str] = []
    i = 0
    while i < len(text):
        if in_block:
            end = text.find("*/", i)
            if end == -1:
                return "".join(out), True
            i = end + 2
            in_block = False
            continue
        start = text.find("/*", i)
        if start == -1:
            out.append(text[i:])
            break
        out.append(text[i:start])
        i = start + 2
        in_block = True
    return "".join(out), in_block


def _iter_sdsl_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*.sdsl2") if p.is_file())


def _metadata_at(lines: list[str], line_index: int, diags: list[Diagnostic]) -> dict[str, str]:
    line = lines[line_index]
    brace_idx = line.find("{")
    if brace_idx == -1:
        return {}
    meta, _ = _capture_metadata(lines, line_index, brace_idx)
    pairs = _parse_metadata_pairs(meta)
    meta_map: dict[str, str] = {}
    for key, value in pairs:
        if key in meta_map:
            _emit_diag(
                diags,
                "ADD_METADATA_DUPLICATE_KEY",
                "Duplicate metadata key",
                "unique key",
                key,
                json_pointer("annotations", str(line_index), key),
            )
        meta_map[key] = value
    return meta_map


def _file_profile_stage(lines: list[str], diags: list[Diagnostic]) -> tuple[str | None, str | None]:
    for idx, line in enumerate(lines):
        if line.lstrip().startswith("@File"):
            meta = _metadata_at(lines, idx, diags)
            profile = meta.get("profile")
            stage = meta.get("stage")
            profile = _strip_quotes(profile) if profile else None
            stage = _strip_quotes(stage) if stage else None
            return profile, stage
    return None, None


def _check_placeholders(lines: list[str], diags: list[Diagnostic]) -> None:
    in_block = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "" or stripped.startswith("//"):
            continue
        line, in_block = _strip_block_comments(line, in_block)
        if line.strip() == "":
            continue
        if "//" in line:
            line = line.split("//", 1)[0]
        candidate = _strip_strings(line)
        if PLACEHOLDER_RE.search(candidate):
            _emit_diag(
                diags,
                "ADD_PLACEHOLDER_IN_SDSL",
                "Placeholder not allowed in SDSL statements",
                "no placeholders",
                stripped,
                json_pointer("statements", str(idx)),
            )


def _check_file(path: Path, policy: dict, diags: list[Diagnostic], stage_values: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    profile, stage = _file_profile_stage(lines, diags)
    stage_value = stage or "L2"

    allow_contract_stage = _get_nested(policy, ["stage_policy", "allow_contract_stage"], False)
    allow_l0_terminal = _get_nested(policy, ["stage_policy", "allow_l0_terminal"], False)
    repo_min_stage = str(_get_nested(policy, ["stage_policy", "repo_min_stage"], "L0"))

    if stage and stage_value not in {"L0", "L1", "L2"}:
        _emit_diag(
            diags,
            "ADD_STAGE_INVALID",
            "stage must be L0/L1/L2",
            "L0|L1|L2",
            stage_value,
            json_pointer("file_header", "stage"),
        )

    if profile and profile != "topology" and stage and not allow_contract_stage:
        _emit_diag(
            diags,
            "ADD_STAGE_IN_CONTRACT_PROFILE",
            "stage not allowed in contract profile",
            "omit stage",
            stage_value,
            json_pointer("file_header", "stage"),
        )

    if profile == "topology" and stage_value in {"L0", "L1", "L2"}:
        stage_values.append(stage_value)
        order = {"L0": 0, "L1": 1, "L2": 2}
        min_value = repo_min_stage if repo_min_stage in order else "L0"
        if order[stage_value] < order[min_value]:
            _emit_diag(
                diags,
                "ADD_STAGE_BELOW_REPO_MIN",
                "stage below repo_min_stage",
                min_value,
                stage_value,
                json_pointer("file_header", "stage"),
            )

    if profile is None:
        _emit_diag(
            diags,
            "ADD_FILE_HEADER_UNREADABLE",
            "@File header not readable for addendum checks",
            "@File { profile:\"topology\", stage:\"L*\" }",
            "missing",
            json_pointer("file_header"),
        )

    if profile != "topology":
        _check_placeholders(lines, diags)
        return

    for idx, line in enumerate(lines):
        match = ANNOTATION_KIND_RE.match(line)
        if not match:
            continue
        kind = match.group("kind")
        meta = _metadata_at(lines, idx, diags)

        if kind == "EdgeIntent":
            if profile != "topology":
                _emit_diag(
                    diags,
                    "ADD_EDGEINTENT_PROFILE",
                    "@EdgeIntent allowed only in topology",
                    "topology",
                    str(profile),
                    json_pointer("annotations", str(idx)),
                )
            for key in meta.keys():
                if key in {"contract_refs", "contract"}:
                    _emit_diag(
                        diags,
                        "ADD_EDGEINTENT_FORBIDDEN_KEYS",
                        "EdgeIntent forbids contract_refs/contract",
                        "no contract_refs/contract",
                        key,
                        json_pointer("annotations", str(idx), key),
                    )
            for key in meta.keys():
                if key not in EDGEINTENT_KEYS_ALLOWED:
                    _emit_diag(
                        diags,
                        "ADD_EDGEINTENT_UNKNOWN_KEYS",
                        "EdgeIntent has unknown keys",
                        "allowed keys only",
                        key,
                        json_pointer("annotations", str(idx), key),
                    )
            for key in EDGEINTENT_KEYS_REQUIRED:
                value = meta.get(key)
                if value is None or _strip_quotes(value) == "":
                    _emit_diag(
                        diags,
                        "ADD_EDGEINTENT_KEYS",
                        "EdgeIntent requires id/from/to",
                        "id/from/to present",
                        "missing",
                        json_pointer("annotations", str(idx), key),
                    )
            raw_id = meta.get("id")
            if raw_id:
                rel_id = _strip_quotes(raw_id)
                if not RELID_RE.match(rel_id):
                    _emit_diag(
                        diags,
                        "ADD_EDGEINTENT_ID_INVALID",
                        "EdgeIntent id must be RELID",
                        "UPPER_SNAKE_CASE",
                        rel_id,
                        json_pointer("annotations", str(idx), "id"),
                    )
            for key in ("from", "to"):
                raw_ref = meta.get(key)
                if raw_ref:
                    ref = parse_internal_ref(_strip_quotes(raw_ref))
                    if not ref or ref.kind != "Node":
                        _emit_diag(
                            diags,
                            "ADD_EDGEINTENT_FROM_TO_INVALID",
                            "EdgeIntent from/to must be @Node ref",
                            "@Node.RELID",
                            str(raw_ref),
                            json_pointer("annotations", str(idx), key),
                        )
            raw_direction = meta.get("direction")
            if raw_direction:
                direction = _strip_quotes(raw_direction)
                if direction not in DIRECTION_VOCAB:
                    _emit_diag(
                        diags,
                        "ADD_EDGEINTENT_DIRECTION_INVALID",
                        "EdgeIntent direction invalid",
                        "pub|sub|req|rep|rw|call",
                        direction,
                        json_pointer("annotations", str(idx), "direction"),
                    )
            hint = meta.get("contract_hint")
            if hint and CONTRACT_TOKEN_RE.search(_strip_quotes(hint)):
                _emit_diag(
                    diags,
                    "ADD_EDGEINTENT_CONTRACT_HINT_TOKENS",
                    "contract_hint must not include CONTRACT.* tokens",
                    "no CONTRACT.*",
                    hint,
                    json_pointer("annotations", str(idx), "contract_hint"),
                )

        if stage_value == "L0":
            if kind not in {"File", "Node", "EdgeIntent"}:
                _emit_diag(
                    diags,
                    "ADD_L0_KIND_FORBIDDEN",
                    "kind not allowed in L0",
                    "File|Node|EdgeIntent",
                    kind,
                    json_pointer("annotations", str(idx)),
                )
            if kind == "Edge":
                _emit_diag(
                    diags,
                    "ADD_L0_EDGE_FORBIDDEN",
                    "@Edge forbidden in L0",
                    "no @Edge",
                    "@Edge",
                    json_pointer("annotations", str(idx)),
                )
            if kind == "Flow" and "edges" in meta:
                _emit_diag(
                    diags,
                    "ADD_L0_EDGE_FORBIDDEN",
                    "@Flow.edges forbidden in L0",
                    "no @Flow.edges",
                    "edges",
                    json_pointer("annotations", str(idx), "edges"),
                )
            if kind == "Terminal" and not allow_l0_terminal:
                _emit_diag(
                    diags,
                    "ADD_L0_TERMINAL_FORBIDDEN",
                    "@Terminal forbidden in L0",
                    "no @Terminal",
                    "@Terminal",
                    json_pointer("annotations", str(idx)),
                )

        if stage_value == "L1" and kind == "EdgeIntent":
            _emit_diag(
                diags,
                "ADD_L1_EDGEINTENT_FORBIDDEN",
                "@EdgeIntent forbidden in L1",
                "no @EdgeIntent",
                "@EdgeIntent",
                json_pointer("annotations", str(idx)),
            )
        if stage_value == "L2" and kind == "EdgeIntent":
            _emit_diag(
                diags,
                "ADD_L2_EDGEINTENT_FORBIDDEN",
                "@EdgeIntent forbidden in L2",
                "no @EdgeIntent",
                "@EdgeIntent",
                json_pointer("annotations", str(idx)),
            )

    _check_placeholders(lines, diags)


def _filter_by_severity(diags: list[Diagnostic], policy: dict) -> tuple[list[Diagnostic], list[Diagnostic]]:
    failed: list[Diagnostic] = []
    kept: list[Diagnostic] = []
    for diag in diags:
        severity = _severity(policy, diag.code)
        if severity == "ignore":
            continue
        kept.append(diag)
        if severity == "fail":
            failed.append(diag)
    return kept, failed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", action="append", required=True, help="File or directory path.")
    ap.add_argument("--policy-path", default=None, help="Explicit policy path.")
    args = ap.parse_args()

    policy_path = Path(args.policy_path) if args.policy_path else None
    policy_result = load_addendum_policy(policy_path, ROOT)

    diags: list[Diagnostic] = list(policy_result.diagnostics)
    enabled = bool(_get_nested(policy_result.policy, ["addendum", "enabled"], False))

    if enabled:
        files: list[Path] = []
        stage_values: list[str] = []
        for raw in args.input:
            files.extend(_iter_sdsl_files(Path(raw)))
        for path in files:
            _check_file(path, policy_result.policy, diags, stage_values)
        allow_mixed = bool(_get_nested(policy_result.policy, ["stage_policy", "allow_mixed_stages"], True))
        if not allow_mixed:
            unique_stages = sorted(set(stage_values))
            if len(unique_stages) > 1:
                _emit_diag(
                    diags,
                    "ADD_MIXED_STAGES_FORBIDDEN",
                    "mixed stages are not allowed",
                    "single stage",
                    ",".join(unique_stages),
                    json_pointer("file_header", "stage"),
                )

    kept, failed = _filter_by_severity(diags, policy_result.policy)
    if kept:
        payload = [d.to_dict() for d in kept]
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

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

from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.lint import DIRECTION_VOCAB, _capture_metadata, _parse_metadata_pairs
from sdslv2_builder.op_yaml import load_yaml
from sdslv2_builder.refs import CONTRACT_TOKEN_RE, RELID_RE

PLACEHOLDERS = {"None", "TBD", "Opaque"}
ANNOTATION_KIND_RE = re.compile(r"^\s*@(?P<kind>[A-Za-z_][A-Za-z0-9_]*)\b")


def _diag(
    diags: list[Diagnostic],
    code: str,
    message: str,
    expected: str,
    got: str,
    path: str,
) -> None:
    diags.append(
        Diagnostic(code=code, message=message, expected=expected, got=got, path=path)
    )


def _print_diags(diags: list[Diagnostic]) -> None:
    payload = [d.to_dict() for d in diags]
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


def _is_placeholder(value: object) -> bool:
    return isinstance(value, str) and value in PLACEHOLDERS


def _resolve_path(project_root: Path, raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (project_root / path).resolve()
    return path


def _ensure_inside(project_root: Path, path: Path, code: str) -> None:
    try:
        path.resolve().relative_to(project_root.resolve())
    except ValueError as exc:
        raise ValueError(code) from exc


def _has_symlink_parent(path: Path, stop: Path) -> bool:
    for parent in [path, *path.parents]:
        if parent == stop:
            break
        if parent.is_symlink():
            return True
    return False


def _strip_quotes(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _parse_annotations(lines: list[str]) -> list[tuple[str, dict[str, str]]] | None:
    annotations: list[tuple[str, dict[str, str]]] = []
    for idx, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped == "" or stripped.startswith("//"):
            continue
        if not stripped.startswith("@"):
            continue
        match = ANNOTATION_KIND_RE.match(stripped)
        if not match:
            continue
        kind = match.group("kind")
        brace_idx = line.find("{")
        if brace_idx == -1:
            if kind == "Node":
                return None
            continue
        try:
            meta, _ = _capture_metadata(lines, idx, brace_idx)
        except ValueError:
            if kind == "Node":
                return None
            continue
        pairs = _parse_metadata_pairs(meta)
        meta_map: dict[str, str] = {}
        for key, value in pairs:
            if key in meta_map:
                if kind == "Node":
                    return None
                continue
            meta_map[key] = value
        annotations.append((kind, meta_map))
    return annotations


def _count_component_scope_matches(
    project_root: Path,
    rel_id: str,
    diags: list[Diagnostic],
) -> int:
    ssot_root = project_root / "sdsl2" / "topology"
    if not ssot_root.exists():
        _diag(
            diags,
            "E_DECISIONS_SCOPE_INVALID",
            "scope.kind=component requires topology files",
            "sdsl2/topology/*.sdsl2",
            "missing",
            json_pointer("scope", "value"),
        )
        return -1
    if ssot_root.is_symlink() or _has_symlink_parent(ssot_root, project_root):
        _diag(
            diags,
            "E_DECISIONS_SCOPE_INVALID",
            "scope.kind=component requires non-symlink topology",
            "non-symlink",
            str(ssot_root),
            json_pointer("scope", "value"),
        )
        return -1
    count = 0
    for path in sorted(ssot_root.rglob("*.sdsl2")):
        if not path.is_file():
            continue
        if path.is_symlink() or _has_symlink_parent(path, ssot_root):
            _diag(
                diags,
                "E_DECISIONS_SCOPE_INVALID",
                "scope.kind=component requires non-symlink topology",
                "non-symlink",
                str(path),
                json_pointer("scope", "value"),
            )
            return -1
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            _diag(
                diags,
                "E_DECISIONS_SCOPE_INVALID",
                "scope.kind=component requires readable topology",
                "readable UTF-8 file",
                str(exc),
                json_pointer("scope", "value"),
            )
            return -1
        annotations = _parse_annotations(text.splitlines())
        if annotations is None:
            _diag(
                diags,
                "E_DECISIONS_SCOPE_INVALID",
                "scope.kind=component requires parseable @Node metadata",
                "valid @Node { ... }",
                str(path),
                json_pointer("scope", "value"),
            )
            return -1
        for kind, meta in annotations:
            if kind != "Node":
                continue
            node_id = _strip_quotes(meta.get("id")) or ""
            if node_id == rel_id:
                count += 1
                break
    return count


def _validate_scope(
    scope: dict,
    project_root: Path,
    diags: list[Diagnostic],
) -> dict[str, str]:
    kind = scope.get("kind")
    value = scope.get("value")
    if kind not in {"file", "id_prefix", "component"}:
        _diag(
            diags,
            "E_DECISIONS_SCOPE_INVALID",
            "scope.kind invalid",
            "file|id_prefix|component",
            str(kind),
            json_pointer("scope", "kind"),
        )
    if not isinstance(value, str) or not value.strip():
        _diag(
            diags,
            "E_DECISIONS_SCOPE_INVALID",
            "scope.value must be non-empty string",
            "non-empty string",
            str(value),
            json_pointer("scope", "value"),
        )
        value = ""
    if _is_placeholder(kind) or _is_placeholder(value):
        _diag(
            diags,
            "E_DECISIONS_PLACEHOLDER_FORBIDDEN",
            "Placeholders are forbidden in decisions",
            "no None/TBD/Opaque",
            str(value),
            json_pointer("scope"),
        )
    if kind == "file" and value:
        if value.startswith("/") or ".." in Path(value).parts:
            _diag(
                diags,
                "E_DECISIONS_SCOPE_INVALID",
                "scope.value must be repo-relative path",
                "sdsl2/topology/*.sdsl2",
                value,
                json_pointer("scope", "value"),
            )
        raw_path = project_root / value
        if raw_path.is_symlink() or _has_symlink_parent(raw_path, project_root):
            _diag(
                diags,
                "E_DECISIONS_SCOPE_INVALID",
                "scope.value must not be symlink",
                "non-symlink file",
                str(raw_path),
                json_pointer("scope", "value"),
            )
        full = raw_path.resolve()
        try:
            full.relative_to(project_root.resolve())
        except ValueError:
            _diag(
                diags,
                "E_DECISIONS_SCOPE_INVALID",
                "scope.value outside project_root",
                "project_root/...",
                str(full),
                json_pointer("scope", "value"),
            )
        if not full.exists():
            _diag(
                diags,
                "E_DECISIONS_SCOPE_INVALID",
                "scope.value file not found",
                "existing sdsl2/topology/*.sdsl2",
                value,
                json_pointer("scope", "value"),
            )
        elif not full.is_file():
            _diag(
                diags,
                "E_DECISIONS_SCOPE_INVALID",
                "scope.value must be file",
                "file",
                value,
                json_pointer("scope", "value"),
            )
        if not value.startswith("sdsl2/topology/") or not value.endswith(".sdsl2"):
            _diag(
                diags,
                "E_DECISIONS_SCOPE_INVALID",
                "scope.value must be sdsl2/topology/*.sdsl2",
                "sdsl2/topology/*.sdsl2",
                value,
                json_pointer("scope", "value"),
            )
    if kind == "component" and value:
        count = _count_component_scope_matches(project_root, value, diags)
        if count < 0:
            return {"kind": str(kind or ""), "value": str(value or "")}
        if count == 0:
            _diag(
                diags,
                "E_DECISIONS_SCOPE_INVALID",
                "scope.value component not found or ambiguous",
                "unique @Node rel_id in topology",
                "not found",
                json_pointer("scope", "value"),
            )
        elif count > 1:
            _diag(
                diags,
                "E_DECISIONS_SCOPE_INVALID",
                "scope.value component not found or ambiguous",
                "unique @Node rel_id in topology",
                f"multiple files: {count}",
                json_pointer("scope", "value"),
            )
    return {"kind": str(kind or ""), "value": str(value or "")}


def parse_decisions_file(
    path: Path,
    project_root: Path,
) -> tuple[dict[str, object] | None, list[Diagnostic]]:
    diags: list[Diagnostic] = []
    try:
        data = load_yaml(path)
    except Exception as exc:
        _diag(
            diags,
            "E_DECISIONS_SCHEMA_INVALID",
            "decisions yaml parse failed",
            "valid YAML",
            str(exc),
            json_pointer(),
        )
        return None, diags
    if not isinstance(data, dict):
        _diag(
            diags,
            "E_DECISIONS_SCHEMA_INVALID",
            "decisions root must be object",
            "object",
            type(data).__name__,
            json_pointer(),
        )
        return None, diags

    allowed_keys = {"schema_version", "provenance", "scope", "edges"}
    for key in data.keys():
        if key not in allowed_keys:
            _diag(
                diags,
                "E_DECISIONS_UNKNOWN_FIELD",
                "Unknown top-level key",
                ",".join(sorted(allowed_keys)),
                key,
                json_pointer(key),
            )

    schema_version = data.get("schema_version")
    if not isinstance(schema_version, str) or not schema_version.strip():
        _diag(
            diags,
            "E_DECISIONS_SCHEMA_INVALID",
            "schema_version must be non-empty string",
            "non-empty string",
            str(schema_version),
            json_pointer("schema_version"),
        )
    if _is_placeholder(schema_version):
        _diag(
            diags,
            "E_DECISIONS_PLACEHOLDER_FORBIDDEN",
            "Placeholders are forbidden in decisions",
            "no None/TBD/Opaque",
            str(schema_version),
            json_pointer("schema_version"),
        )

    provenance = data.get("provenance")
    if not isinstance(provenance, dict):
        _diag(
            diags,
            "E_DECISIONS_SCHEMA_INVALID",
            "provenance must be object",
            "object",
            type(provenance).__name__,
            json_pointer("provenance"),
        )
        provenance = {}
    allowed_prov = {"author", "reviewed_by", "source_link"}
    for key in provenance.keys():
        if key not in allowed_prov:
            _diag(
                diags,
                "E_DECISIONS_UNKNOWN_FIELD",
                "Unknown provenance key",
                ",".join(sorted(allowed_prov)),
                key,
                json_pointer("provenance", key),
            )
    for key in sorted(allowed_prov):
        value = provenance.get(key)
        if not isinstance(value, str) or not value.strip():
            _diag(
                diags,
                "E_DECISIONS_FIELD_INVALID",
                f"provenance.{key} must be non-empty string",
                "non-empty string",
                str(value),
                json_pointer("provenance", key),
            )
        if _is_placeholder(value):
            _diag(
                diags,
                "E_DECISIONS_PLACEHOLDER_FORBIDDEN",
                "Placeholders are forbidden in decisions",
                "no None/TBD/Opaque",
                str(value),
                json_pointer("provenance", key),
            )

    scope_raw = data.get("scope")
    if not isinstance(scope_raw, dict):
        _diag(
            diags,
            "E_DECISIONS_SCHEMA_INVALID",
            "scope must be object",
            "object",
            type(scope_raw).__name__,
            json_pointer("scope"),
        )
        scope_raw = {}
    scope = _validate_scope(scope_raw, project_root, diags)

    edges_raw = data.get("edges")
    if not isinstance(edges_raw, list):
        _diag(
            diags,
            "E_DECISIONS_SCHEMA_INVALID",
            "edges must be list",
            "list",
            type(edges_raw).__name__,
            json_pointer("edges"),
        )
        edges_raw = []

    edges: list[dict[str, object]] = []
    edge_ids: list[str] = []
    edge_triplets: set[tuple[str, str, str]] = set()
    for idx, edge in enumerate(edges_raw):
        if not isinstance(edge, dict):
            _diag(
                diags,
                "E_DECISIONS_EDGE_INVALID",
                "EdgeDecision must be object",
                "object",
                type(edge).__name__,
                json_pointer("edges", str(idx)),
            )
            continue
        allowed_edge = {"id", "from", "to", "direction", "contract_refs"}
        for key in edge.keys():
            if key not in allowed_edge:
                _diag(
                    diags,
                    "E_DECISIONS_EDGE_INVALID",
                    "Unknown edge key",
                    ",".join(sorted(allowed_edge)),
                    key,
                    json_pointer("edges", str(idx), key),
                )
        rel_id = edge.get("id")
        from_id = edge.get("from")
        to_id = edge.get("to")
        direction = edge.get("direction")
        if not isinstance(rel_id, str) or not RELID_RE.match(rel_id):
            _diag(
                diags,
                "E_DECISIONS_EDGE_INVALID",
                "id must be RELID",
                "UPPER_SNAKE_CASE",
                str(rel_id),
                json_pointer("edges", str(idx), "id"),
            )
            rel_id = ""
        if not isinstance(from_id, str) or not RELID_RE.match(from_id):
            _diag(
                diags,
                "E_DECISIONS_EDGE_INVALID",
                "from must be RELID",
                "UPPER_SNAKE_CASE",
                str(from_id),
                json_pointer("edges", str(idx), "from"),
            )
            from_id = ""
        if not isinstance(to_id, str) or not RELID_RE.match(to_id):
            _diag(
                diags,
                "E_DECISIONS_EDGE_INVALID",
                "to must be RELID",
                "UPPER_SNAKE_CASE",
                str(to_id),
                json_pointer("edges", str(idx), "to"),
            )
            to_id = ""
        if direction not in DIRECTION_VOCAB:
            _diag(
                diags,
                "E_DECISIONS_EDGE_INVALID",
                "direction invalid",
                ",".join(sorted(DIRECTION_VOCAB)),
                str(direction),
                json_pointer("edges", str(idx), "direction"),
            )
            direction = ""

        if _is_placeholder(rel_id) or _is_placeholder(from_id) or _is_placeholder(to_id):
            _diag(
                diags,
                "E_DECISIONS_PLACEHOLDER_FORBIDDEN",
                "Placeholders are forbidden in decisions",
                "no None/TBD/Opaque",
                str(rel_id),
                json_pointer("edges", str(idx)),
            )

        contract_refs = edge.get("contract_refs")
        if not isinstance(contract_refs, list):
            _diag(
                diags,
                "E_DECISIONS_EDGE_INVALID",
                "contract_refs must be list",
                "list",
                type(contract_refs).__name__,
                json_pointer("edges", str(idx), "contract_refs"),
            )
            contract_refs = []
        ref_items: list[str] = []
        for ridx, ref in enumerate(contract_refs):
            if not isinstance(ref, str) or not CONTRACT_TOKEN_RE.match(ref):
                _diag(
                    diags,
                    "E_DECISIONS_EDGE_INVALID",
                    "contract_refs must be CONTRACT.*",
                    "CONTRACT.*",
                    str(ref),
                    json_pointer("edges", str(idx), "contract_refs", str(ridx)),
                )
                continue
            if _is_placeholder(ref):
                _diag(
                    diags,
                    "E_DECISIONS_PLACEHOLDER_FORBIDDEN",
                    "Placeholders are forbidden in decisions",
                    "no None/TBD/Opaque",
                    str(ref),
                    json_pointer("edges", str(idx), "contract_refs", str(ridx)),
                )
            ref_items.append(ref)
        if not ref_items:
            _diag(
                diags,
                "E_DECISIONS_EDGE_INVALID",
                "contract_refs must be non-empty",
                "non-empty list",
                "empty",
                json_pointer("edges", str(idx), "contract_refs"),
            )
        sorted_refs = sorted(dict.fromkeys(ref_items))
        if ref_items != sorted_refs:
            _diag(
                diags,
                "E_DECISIONS_LIST_NOT_SORTED",
                "contract_refs must be sorted and de-duplicated",
                "sorted unique list",
                "unsorted/dup",
                json_pointer("edges", str(idx), "contract_refs"),
            )

        if rel_id:
            edge_ids.append(rel_id)
        if from_id and to_id and direction:
            triplet = (from_id, to_id, direction)
            if triplet in edge_triplets:
                _diag(
                    diags,
                    "E_DECISIONS_DUPLICATE_EDGE",
                    "Duplicate (from,to,direction) tuple",
                    "unique tuple",
                    "duplicate",
                    json_pointer("edges", str(idx)),
                )
            edge_triplets.add(triplet)

        if scope.get("kind") == "component" and scope.get("value"):
            value = scope.get("value")
            if value not in {from_id, to_id}:
                _diag(
                    diags,
                    "E_DECISIONS_SCOPE_INVALID",
                    "component scope must match from/to",
                    "from==value or to==value",
                    value,
                    json_pointer("scope"),
                )

        edges.append(
            {
                "id": rel_id,
                "from": from_id,
                "to": to_id,
                "direction": direction,
                "contract_refs": sorted_refs,
            }
        )

    if edge_ids and edge_ids != sorted(edge_ids):
        _diag(
            diags,
            "E_DECISIONS_LIST_NOT_SORTED",
            "edges must be sorted by id",
            "sorted by id",
            "unsorted",
            json_pointer("edges"),
        )
    if len(edge_ids) != len(set(edge_ids)):
        _diag(
            diags,
            "E_DECISIONS_DUPLICATE_ID",
            "EdgeDecision id must be unique",
            "unique id",
            "duplicate",
            json_pointer("edges"),
        )

    return {"scope": scope, "edges": edges}, diags


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="decisions/edges.yaml")
    ap.add_argument(
        "--allow-nonstandard-path",
        action="store_true",
        help="Allow decisions file outside decisions/edges.yaml",
    )
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); input can be relative to it",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    path = _resolve_path(project_root, args.input)
    try:
        _ensure_inside(project_root, path, "E_DECISIONS_INPUT_OUTSIDE_PROJECT")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not path.exists():
        print("E_DECISIONS_INPUT_NOT_FOUND", file=sys.stderr)
        return 2
    if path.exists() and path.is_dir():
        print("E_DECISIONS_INPUT_IS_DIR", file=sys.stderr)
        return 2
    if path.is_symlink():
        print("E_DECISIONS_INPUT_SYMLINK", file=sys.stderr)
        return 2
    if not args.allow_nonstandard_path:
        expected = (project_root / "decisions" / "edges.yaml").resolve()
        if path.resolve() != expected:
            print("E_DECISIONS_INPUT_NOT_STANDARD_PATH", file=sys.stderr)
            return 2

    _, diags = parse_decisions_file(path, project_root)
    if diags:
        _print_diags(diags)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

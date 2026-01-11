#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.lint import _capture_metadata, _parse_metadata_pairs, _split_list_items
from sdslv2_builder.refs import parse_contract_ref, parse_internal_ref


def _strip_quotes(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _has_symlink_parent(path: Path, stop: Path) -> bool:
    for parent in [path, *path.parents]:
        if parent == stop:
            break
        if parent.is_symlink():
            return True
    return False


def _ensure_under_root(path: Path, root: Path, code: str) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        print(code, file=sys.stderr)
        return False
    return True


def _print_diags(diags: list[Diagnostic]) -> None:
    payload = [d.to_dict() for d in diags]
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


def _iter_annotations(lines: list[str]) -> list[tuple[str, dict[str, str] | None, int, int, list[str]]]:
    annotations: list[tuple[str, dict[str, str] | None, int, int, list[str]]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.lstrip().startswith("@"):
            i += 1
            continue
        kind = line.lstrip().split(None, 1)[0][1:]
        brace_idx = line.find("{")
        if brace_idx == -1:
            annotations.append((kind, None, i, i, []))
            i += 1
            continue
        meta, end_line = _capture_metadata(lines, i, brace_idx)
        pairs = _parse_metadata_pairs(meta)
        meta_map: dict[str, str] = {}
        dupes: list[str] = []
        for key, value in pairs:
            if key in meta_map and key not in dupes:
                dupes.append(key)
            meta_map[key] = value
        annotations.append((kind, meta_map, i, end_line, dupes))
        i = end_line + 1
    return annotations


def _collect_files(project_root: Path, root: Path, code_prefix: str) -> list[Path] | None:
    files: list[Path] = []
    if root.is_symlink() or _has_symlink_parent(root, project_root):
        print(f"E_{code_prefix}_ROOT_SYMLINK", file=sys.stderr)
        return None
    if not root.exists():
        print(f"E_{code_prefix}_ROOT_MISSING", file=sys.stderr)
        return None
    for path in sorted(root.rglob("*.sdsl2")):
        if not path.is_file():
            continue
        if path.is_symlink() or _has_symlink_parent(path, root):
            print(f"E_{code_prefix}_INPUT_SYMLINK", file=sys.stderr)
            return None
        if not _ensure_under_root(path, project_root, f"E_{code_prefix}_INPUT_OUTSIDE_PROJECT"):
            return None
        files.append(path)
    if not files:
        print(f"E_{code_prefix}_INPUT_NOT_FOUND", file=sys.stderr)
        return None
    return files


def _emit_diag(diags: list[Diagnostic], code: str, message: str, expected: str, got: str, path: str) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def _parse_contract_list(raw: str) -> list[str] | None:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        return _split_list_items(raw)
    if raw == "":
        return []
    return None


def _collect_contract_tokens_from_list(
    raw: str,
    diags: list[Diagnostic],
    path: str,
) -> set[str]:
    tokens: set[str] = set()
    items = _parse_contract_list(raw)
    if items is None:
        _emit_diag(
            diags,
            "E_CONTRACT_BIND_REFS_INVALID",
            "contract_refs must be a list",
            "list of CONTRACT.*",
            raw,
            path,
        )
        return tokens
    if items == []:
        _emit_diag(
            diags,
            "E_CONTRACT_BIND_REFS_EMPTY",
            "contract_refs must be non-empty",
            "non-empty list",
            "empty",
            path,
        )
        return tokens
    for idx_item, item in enumerate(items):
        token = item.strip()
        if len(token) >= 2 and token[0] == token[-1] == '"':
            token = token[1:-1]
        parsed = parse_contract_ref(token)
        if not parsed:
            _emit_diag(
                diags,
                "E_CONTRACT_BIND_TOKEN_INVALID",
                "contract token invalid",
                "CONTRACT.*",
                token,
                f"{path}/{idx_item}",
            )
            continue
        tokens.add(parsed.token)
    return tokens


def _collect_topology_tokens(path: Path, diags: list[Diagnostic]) -> set[str]:
    tokens: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        _emit_diag(
            diags,
            "E_CONTRACT_BIND_READ_FAILED",
            "Failed to read topology file",
            "readable UTF-8 file",
            f"{path}: {exc}",
            json_pointer(),
        )
        return tokens
    try:
        annotations = _iter_annotations(lines)
    except Exception as exc:
        _emit_diag(
            diags,
            "E_CONTRACT_BIND_METADATA_PARSE_FAILED",
            "Failed to parse annotations",
            "valid annotation metadata",
            str(exc),
            json_pointer(),
        )
        return tokens
    edge_index = 0
    for kind, meta, idx, _, dupes in annotations:
        if kind != "Edge":
            continue
        if meta is None:
            _emit_diag(
                diags,
                "E_CONTRACT_BIND_METADATA_MISSING",
                "Annotation must include metadata object",
                "{...}",
                "missing",
                json_pointer("annotations", str(idx)),
            )
            continue
        if dupes:
            for key in dupes:
                _emit_diag(
                    diags,
                    "E_CONTRACT_BIND_METADATA_DUPLICATE_KEY",
                    "Duplicate metadata key",
                    "unique key",
                    key,
                    json_pointer("annotations", str(idx), key),
                )
            continue
        raw_refs = meta.get("contract_refs")
        if raw_refs is None:
            edge_index += 1
            continue
        tokens.update(
            _collect_contract_tokens_from_list(
                raw_refs,
                diags,
                json_pointer("edges", str(edge_index), "contract_refs"),
            )
        )
        edge_index += 1
    return tokens


def _collect_contract_tokens(path: Path, diags: list[Diagnostic]) -> set[str]:
    tokens: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        _emit_diag(
            diags,
            "E_CONTRACT_BIND_READ_FAILED",
            "Failed to read contract file",
            "readable UTF-8 file",
            f"{path}: {exc}",
            json_pointer(),
        )
        return tokens
    try:
        annotations = _iter_annotations(lines)
    except Exception as exc:
        _emit_diag(
            diags,
            "E_CONTRACT_BIND_METADATA_PARSE_FAILED",
            "Failed to parse annotations",
            "valid annotation metadata",
            str(exc),
            json_pointer(),
        )
        return tokens
    for _, meta, idx, _, dupes in annotations:
        if meta is None:
            _emit_diag(
                diags,
                "E_CONTRACT_BIND_METADATA_MISSING",
                "Annotation must include metadata object",
                "{...}",
                "missing",
                json_pointer("annotations", str(idx)),
            )
            continue
        if dupes:
            for key in dupes:
                _emit_diag(
                    diags,
                    "E_CONTRACT_BIND_METADATA_DUPLICATE_KEY",
                    "Duplicate metadata key",
                    "unique key",
                    key,
                    json_pointer("annotations", str(idx), key),
                )
            continue

        raw_contract = meta.get("contract")
        if raw_contract:
            tokens.update(
                _collect_contract_tokens_from_list(
                    raw_contract,
                    diags,
                    json_pointer("annotations", str(idx), "contract"),
                )
            )

        raw_refs = meta.get("contract_refs")
        if raw_refs:
            tokens.update(
                _collect_contract_tokens_from_list(
                    raw_refs,
                    diags,
                    json_pointer("annotations", str(idx), "contract_refs"),
                )
            )

        raw_to = _strip_quotes(meta.get("to"))
        if raw_to:
            if "[" in raw_to or "]" in raw_to:
                continue
            parsed = parse_contract_ref(raw_to)
            if parsed:
                tokens.add(parsed.token)
            else:
                if raw_to.strip().startswith("CONTRACT."):
                    _emit_diag(
                        diags,
                        "E_CONTRACT_BIND_TOKEN_INVALID",
                        "contract token invalid",
                        "CONTRACT.*",
                        raw_to,
                        json_pointer("annotations", str(idx), "to"),
                    )
                elif parse_internal_ref(raw_to):
                    pass
    return tokens


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=None, help="Project root (defaults to repo root)")
    ap.add_argument("--topology-root", default="sdsl2/topology", help="Topology root under project")
    ap.add_argument("--contract-root", default="sdsl2/contract", help="Contract root under project")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    topo_root = (project_root / args.topology_root).resolve()
    contract_root = (project_root / args.contract_root).resolve()

    if not _ensure_under_root(topo_root, project_root, "E_CONTRACT_BIND_TOPOLOGY_OUTSIDE_PROJECT"):
        return 2
    if not _ensure_under_root(contract_root, project_root, "E_CONTRACT_BIND_CONTRACT_OUTSIDE_PROJECT"):
        return 2

    topo_files = _collect_files(project_root, topo_root, "CONTRACT_BIND_TOPOLOGY")
    if topo_files is None:
        return 2
    contract_files = _collect_files(project_root, contract_root, "CONTRACT_BIND_CONTRACT")
    if contract_files is None:
        return 2

    diags: list[Diagnostic] = []
    used_tokens: set[str] = set()
    for path in topo_files:
        used_tokens.update(_collect_topology_tokens(path, diags))

    declared_tokens: set[str] = set()
    for path in contract_files:
        declared_tokens.update(_collect_contract_tokens(path, diags))

    for token in sorted(used_tokens):
        if token not in declared_tokens:
            _emit_diag(
                diags,
                "E_CONTRACT_BIND_TOKEN_MISSING",
                "Contract token missing from contract profile",
                "token declared in contract",
                token,
                json_pointer("contract_refs", token),
            )

    if diags:
        _print_diags(diags)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

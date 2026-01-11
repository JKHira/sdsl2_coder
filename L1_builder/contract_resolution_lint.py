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
from sdslv2_builder.lint import _capture_metadata, _parse_metadata_pairs
from sdslv2_builder.refs import RELID_RE, parse_contract_ref, parse_internal_ref


DECL_KINDS = {"Structure", "Interface", "Function", "Const", "Type"}


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
        meta = meta.strip()
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


def _check_placeholders(
    annotations: list[tuple[str, dict[str, str] | None, int, int, list[str]]],
    diags: list[Diagnostic],
) -> None:
    placeholders = {"none", "tbd", "opaque"}
    for _, meta, idx, _, dupes in annotations:
        if meta is None or dupes:
            continue
        for key, raw in meta.items():
            value = _strip_quotes(raw) if isinstance(raw, str) else None
            if value is None:
                continue
            if value.strip().lower() in placeholders:
                _emit_diag(
                    diags,
                    "E_CONTRACT_RES_PLACEHOLDER_FORBIDDEN",
                    "Placeholder not allowed in SDSL metadata values",
                    "non-placeholder value",
                    value,
                    json_pointer("annotations", str(idx), key),
                )


def _collect_files(project_root: Path, inputs: list[str]) -> list[Path] | None:
    files: list[Path] = []
    contract_root = (project_root / "sdsl2" / "contract").resolve()
    if contract_root.is_symlink() or _has_symlink_parent(contract_root, project_root):
        print("E_CONTRACT_RES_CONTRACT_ROOT_SYMLINK", file=sys.stderr)
        return None
    for raw in inputs:
        path = Path(raw)
        if not path.is_absolute():
            path = (project_root / path).resolve()
        if not _ensure_under_root(path, project_root, "E_CONTRACT_RES_INPUT_OUTSIDE_PROJECT"):
            return None
        if not _ensure_under_root(path, contract_root, "E_CONTRACT_RES_INPUT_NOT_CONTRACT"):
            return None
        if path.is_symlink() or _has_symlink_parent(path, contract_root):
            print("E_CONTRACT_RES_INPUT_SYMLINK", file=sys.stderr)
            return None
        if path.is_dir():
            for file_path in sorted(path.rglob("*.sdsl2")):
                if file_path.is_symlink() or _has_symlink_parent(file_path, contract_root):
                    print("E_CONTRACT_RES_INPUT_SYMLINK", file=sys.stderr)
                    return None
                if file_path.is_file():
                    files.append(file_path)
        elif path.is_file():
            if path.suffix != ".sdsl2":
                print("E_CONTRACT_RES_INPUT_NOT_SDSL2", file=sys.stderr)
                return None
            files.append(path)
        else:
            print("E_CONTRACT_RES_INPUT_NOT_FILE", file=sys.stderr)
            return None
    if not files:
        print("E_CONTRACT_RES_INPUT_NOT_FOUND", file=sys.stderr)
        return None
    return files


def _emit_diag(diags: list[Diagnostic], code: str, message: str, expected: str, got: str, path: str) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def _check_file(path: Path, diags: list[Diagnostic]) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        _emit_diag(
            diags,
            "E_CONTRACT_RES_READ_FAILED",
            "Failed to read contract file",
            "readable UTF-8 file",
            f"{path}: {exc}",
            json_pointer(),
        )
        return
    annotations = _iter_annotations(lines)

    decl_counts = {kind: 0 for kind in DECL_KINDS}
    rule_count = 0
    declared_ids: set[tuple[str, str]] = set()
    file_profile: str | None = None
    file_id_prefix: str | None = None
    file_stage: str | None = None
    file_header_seen = False

    for kind, meta, idx, _, dupes in annotations:
        if meta is None:
            _emit_diag(
                diags,
                "E_CONTRACT_RES_METADATA_MISSING",
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
                    "E_CONTRACT_RES_METADATA_DUPLICATE_KEY",
                    "Duplicate metadata key",
                    "unique key",
                    key,
                    json_pointer("annotations", str(idx), key),
                )
            continue

        if kind == "File":
            if file_header_seen:
                _emit_diag(
                    diags,
                    "E_CONTRACT_RES_FILE_HEADER_DUPLICATE",
                    "Duplicate @File header",
                    "single @File",
                    "multiple",
                    json_pointer("file_header"),
                )
            file_header_seen = True
            file_profile = _strip_quotes(meta.get("profile"))
            file_id_prefix = _strip_quotes(meta.get("id_prefix"))
            file_stage = _strip_quotes(meta.get("stage"))

        if kind in DECL_KINDS:
            decl_counts[kind] += 1
            rel_id = _strip_quotes(meta.get("id"))
            if not rel_id or not RELID_RE.match(rel_id):
                _emit_diag(
                    diags,
                    "E_CONTRACT_RES_ID_INVALID",
                    "Declaration id must be RELID",
                    "UPPER_SNAKE_CASE",
                    rel_id or "missing",
                    json_pointer("annotations", str(idx), "id"),
                )
            else:
                if (kind, rel_id) in declared_ids:
                    _emit_diag(
                        diags,
                        "E_CONTRACT_RES_DECL_DUPLICATE",
                        "Duplicate declaration id",
                        "unique (kind,id)",
                        f"{kind}.{rel_id}",
                        json_pointer("annotations", str(idx), "id"),
                    )
                else:
                    declared_ids.add((kind, rel_id))

        if kind == "Rule":
            rule_count += 1

    for kind, meta, idx, _, dupes in annotations:
        if meta is None or dupes:
            continue
        if kind == "Rule":
            bind_raw = _strip_quotes(meta.get("bind"))
            if not bind_raw:
                _emit_diag(
                    diags,
                    "E_CONTRACT_RES_RULE_BIND_MISSING",
                    "@Rule requires bind",
                    "bind:@Kind.RELID",
                    "missing",
                    json_pointer("annotations", str(idx), "bind"),
                )
            else:
                parsed = parse_internal_ref(bind_raw)
                if not parsed:
                    _emit_diag(
                        diags,
                        "E_CONTRACT_RES_RULE_BIND_INVALID",
                        "@Rule bind must be internal ref",
                        "@Kind.RELID",
                        bind_raw,
                        json_pointer("annotations", str(idx), "bind"),
                    )
                elif (parsed.kind, parsed.rel_id) not in declared_ids:
                    _emit_diag(
                        diags,
                        "E_CONTRACT_RES_RULE_BIND_TARGET_MISSING",
                        "@Rule bind target missing",
                        "declared id",
                        bind_raw,
                        json_pointer("annotations", str(idx), "bind"),
                    )

        if kind == "Dep":
            dep_from = _strip_quotes(meta.get("from"))
            dep_to = _strip_quotes(meta.get("to"))
            if not dep_from:
                _emit_diag(
                    diags,
                    "E_CONTRACT_RES_DEP_FROM_MISSING",
                    "@Dep requires from",
                    "@Kind.RELID",
                    "missing",
                    json_pointer("annotations", str(idx), "from"),
                )
            else:
                parsed_from = parse_internal_ref(dep_from)
                if not parsed_from:
                    _emit_diag(
                        diags,
                        "E_CONTRACT_RES_DEP_FROM_INVALID",
                        "@Dep from must be internal ref",
                        "@Kind.RELID",
                        dep_from,
                        json_pointer("annotations", str(idx), "from"),
                    )
                elif (parsed_from.kind, parsed_from.rel_id) not in declared_ids:
                    _emit_diag(
                        diags,
                        "E_CONTRACT_RES_DEP_FROM_TARGET_MISSING",
                        "@Dep from target missing",
                        "declared id",
                        dep_from,
                        json_pointer("annotations", str(idx), "from"),
                    )

            if not dep_to:
                _emit_diag(
                    diags,
                    "E_CONTRACT_RES_DEP_TO_MISSING",
                    "@Dep requires to",
                    "@Kind.RELID or CONTRACT.*",
                    "missing",
                    json_pointer("annotations", str(idx), "to"),
                )
            else:
                if "[" in dep_to or "]" in dep_to:
                    _emit_diag(
                        diags,
                        "E_CONTRACT_RES_DEP_TO_INVALID",
                        "@Dep to must be single ref",
                        "single ref",
                        dep_to,
                        json_pointer("annotations", str(idx), "to"),
                    )
                else:
                    parsed_to = parse_internal_ref(dep_to)
                    if parsed_to:
                        if (parsed_to.kind, parsed_to.rel_id) not in declared_ids:
                            _emit_diag(
                                diags,
                                "E_CONTRACT_RES_DEP_TO_TARGET_MISSING",
                                "@Dep to target missing",
                                "declared id",
                                dep_to,
                                json_pointer("annotations", str(idx), "to"),
                            )
                    elif not parse_contract_ref(dep_to):
                        _emit_diag(
                            diags,
                            "E_CONTRACT_RES_DEP_TO_INVALID",
                            "@Dep to must be internal ref or CONTRACT.*",
                            "@Kind.RELID or CONTRACT.*",
                            dep_to,
                            json_pointer("annotations", str(idx), "to"),
                        )

    if not file_header_seen:
        _emit_diag(
            diags,
            "E_CONTRACT_RES_FILE_HEADER_MISSING",
            "Missing @File header",
            "@File { profile:\"contract\" }",
            "missing",
            json_pointer("file_header"),
        )
    else:
        if file_profile != "contract":
            _emit_diag(
                diags,
                "E_CONTRACT_RES_PROFILE_INVALID",
                "profile must be contract",
                "contract",
                str(file_profile),
                json_pointer("file_header", "profile"),
            )
        if not file_id_prefix or not RELID_RE.match(file_id_prefix):
            _emit_diag(
                diags,
                "E_CONTRACT_RES_ID_PREFIX_INVALID",
                "id_prefix must be RELID",
                "UPPER_SNAKE_CASE",
                file_id_prefix or "missing",
                json_pointer("file_header", "id_prefix"),
            )
        if file_stage is not None:
            _emit_diag(
                diags,
                "E_CONTRACT_RES_STAGE_FORBIDDEN",
                "@File.stage not allowed in contract profile",
                "omit stage",
                str(file_stage),
                json_pointer("file_header", "stage"),
            )

    if decl_counts["Interface"] == 0 and decl_counts["Function"] == 0:
        _emit_diag(
            diags,
            "E_CONTRACT_RES_API_MISSING",
            "Interface or Function required for API skeleton",
            "@Interface or @Function",
            "missing",
            json_pointer("summary", "api"),
        )
    if decl_counts["Structure"] == 0 and decl_counts["Type"] == 0:
        _emit_diag(
            diags,
            "E_CONTRACT_RES_TYPES_MISSING",
            "Structure or Type required for payload skeleton",
            "@Structure or @Type",
            "missing",
            json_pointer("summary", "types"),
        )
    if rule_count == 0:
        _emit_diag(
            diags,
            "E_CONTRACT_RES_RULE_MISSING",
            "Rule required to anchor constraints",
            "@Rule with bind",
            "missing",
            json_pointer("summary", "rules"),
        )
    _check_placeholders(annotations, diags)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", action="append", required=True, help="Contract .sdsl2 file or directory")
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); inputs can be relative to it",
    )
    ap.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="Treat missing resolution fields as failure",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    files = _collect_files(project_root, args.input)
    if files is None:
        return 2

    diags: list[Diagnostic] = []
    for path in files:
        _check_file(path, diags)

    if diags:
        _print_diags(diags)
        return 2 if args.fail_on_missing else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

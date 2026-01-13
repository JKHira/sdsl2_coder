#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from L1_builder.decisions_lint import parse_decisions_file
from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.lint import _capture_metadata, _parse_metadata_pairs, _split_list_items
from sdslv2_builder.op_yaml import load_yaml
from sdslv2_builder.refs import RELID_RE, parse_contract_ref, parse_internal_ref


PROFILE_REL_PATH = Path("policy") / "contract_resolution_profile.yaml"
ANNOTATION_KIND_RE = re.compile(r"^\s*@(?P<kind>[A-Za-z_][A-Za-z0-9_]*)\b")


def _emit_diag(
    diags: list[Diagnostic],
    code: str,
    message: str,
    expected: str,
    got: str,
    path: str,
) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def _print_diags(diags: list[Diagnostic]) -> None:
    payload = [d.to_dict() for d in diags]
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


def _strip_quotes(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _resolve_path(base: Path, raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (base / path).absolute()
    return path


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
        return False
    return True


def _iter_annotations(lines: list[str]) -> list[tuple[str, dict[str, str] | None, int, int, list[str]]]:
    annotations: list[tuple[str, dict[str, str] | None, int, int, list[str]]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        if not stripped.startswith("@"):
            i += 1
            continue
        match = ANNOTATION_KIND_RE.match(stripped)
        if match:
            kind = match.group("kind")
        else:
            kind = stripped.split(None, 1)[0][1:]
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


def _first_stmt_line(lines: list[str]) -> int | None:
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "" or stripped.startswith("//"):
            continue
        return idx
    return None


def _parse_rule_bind(value: str | None) -> object | None:
    if not value:
        return None
    parsed = parse_internal_ref(value)
    if parsed:
        return parsed
    value = value.strip()
    if value.startswith("@") and ".<" in value and value.endswith(">"):
        prefix, tail = value.split(".<", 1)
        rel_id = tail[:-1]
        if RELID_RE.match(rel_id):
            return parse_internal_ref(f"{prefix}.{rel_id}")
    return None


def _load_profile(project_root: Path, diags: list[Diagnostic]) -> dict[str, object] | None:
    path = project_root / PROFILE_REL_PATH
    if not path.exists():
        return None
    try:
        path.resolve().relative_to(project_root.resolve())
    except ValueError:
        _emit_diag(
            diags,
            "E_CONTRACT_RULE_PROFILE_OUTSIDE_PROJECT",
            "Contract profile must be under project_root",
            "project_root/...",
            str(path),
            json_pointer("profile"),
        )
        return None
    if path.is_symlink() or _has_symlink_parent(path, project_root):
        _emit_diag(
            diags,
            "E_CONTRACT_RULE_PROFILE_SYMLINK",
            "Contract profile must not be symlink",
            "non-symlink",
            str(path),
            json_pointer("profile"),
        )
        return None
    try:
        data = load_yaml(path)
    except Exception as exc:
        _emit_diag(
            diags,
            "E_CONTRACT_RULE_PROFILE_PARSE_FAILED",
            "Contract profile parse failed",
            "valid YAML",
            str(exc),
            json_pointer("profile"),
        )
        return None
    if not isinstance(data, dict):
        _emit_diag(
            diags,
            "E_CONTRACT_RULE_PROFILE_INVALID",
            "Contract profile must be object",
            "object",
            type(data).__name__,
            json_pointer("profile"),
        )
        return None
    return data


def _parse_rule_naming(
    profile: dict[str, object] | None,
    diags: list[Diagnostic],
) -> tuple[dict[str, list[str]], bool, bool]:
    prefix_bindings: dict[str, list[str]] = {}
    allow_unmatched = True
    require_bind = False
    if not profile:
        return prefix_bindings, allow_unmatched, require_bind
    rule_naming = profile.get("rule_naming")
    if rule_naming is None:
        return prefix_bindings, allow_unmatched, require_bind
    if not isinstance(rule_naming, dict):
        _emit_diag(
            diags,
            "E_CONTRACT_RULE_PROFILE_INVALID",
            "rule_naming must be object",
            "object",
            str(rule_naming),
            json_pointer("profile", "rule_naming"),
        )
        return prefix_bindings, allow_unmatched, require_bind
    allow_raw = rule_naming.get("allow_unmatched")
    if allow_raw is not None:
        if isinstance(allow_raw, bool):
            allow_unmatched = allow_raw
        else:
            _emit_diag(
                diags,
                "E_CONTRACT_RULE_PROFILE_INVALID",
                "rule_naming.allow_unmatched must be bool",
                "bool",
                str(allow_raw),
                json_pointer("profile", "rule_naming", "allow_unmatched"),
            )
    require_raw = rule_naming.get("require_bind")
    if require_raw is not None:
        if isinstance(require_raw, bool):
            require_bind = require_raw
        else:
            _emit_diag(
                diags,
                "E_CONTRACT_RULE_PROFILE_INVALID",
                "rule_naming.require_bind must be bool",
                "bool",
                str(require_raw),
                json_pointer("profile", "rule_naming", "require_bind"),
            )
    prefix_raw = rule_naming.get("prefix_bindings")
    if prefix_raw is None:
        return prefix_bindings, allow_unmatched, require_bind
    if not isinstance(prefix_raw, dict):
        _emit_diag(
            diags,
            "E_CONTRACT_RULE_PROFILE_INVALID",
            "rule_naming.prefix_bindings must be object",
            "object",
            str(prefix_raw),
            json_pointer("profile", "rule_naming", "prefix_bindings"),
        )
        return prefix_bindings, allow_unmatched, require_bind
    for prefix, kinds in prefix_raw.items():
        if not isinstance(prefix, str) or not prefix.strip():
            _emit_diag(
                diags,
                "E_CONTRACT_RULE_PROFILE_INVALID",
                "rule_naming.prefix_bindings key must be string",
                "string",
                str(prefix),
                json_pointer("profile", "rule_naming", "prefix_bindings"),
            )
            continue
        if not isinstance(kinds, list) or not all(isinstance(item, str) and item.strip() for item in kinds):
            _emit_diag(
                diags,
                "E_CONTRACT_RULE_PROFILE_INVALID",
                "rule_naming.prefix_bindings value must be list[str]",
                "list[str]",
                str(kinds),
                json_pointer("profile", "rule_naming", "prefix_bindings", prefix),
            )
            continue
        prefix_bindings[prefix] = [item.strip() for item in kinds]
    return prefix_bindings, allow_unmatched, require_bind


def _parse_rule_coverage(profile: dict[str, object] | None, diags: list[Diagnostic]) -> bool:
    if not profile:
        return False
    coverage = profile.get("rule_coverage")
    if coverage is None:
        return False
    if not isinstance(coverage, dict):
        _emit_diag(
            diags,
            "E_CONTRACT_RULE_PROFILE_INVALID",
            "rule_coverage must be object",
            "object",
            str(coverage),
            json_pointer("profile", "rule_coverage"),
        )
        return False
    require_raw = coverage.get("require_rule_contract")
    if require_raw is None:
        return False
    if not isinstance(require_raw, bool):
        _emit_diag(
            diags,
            "E_CONTRACT_RULE_PROFILE_INVALID",
            "rule_coverage.require_rule_contract must be bool",
            "bool",
            str(require_raw),
            json_pointer("profile", "rule_coverage", "require_rule_contract"),
        )
        return False
    return require_raw


def _collect_contract_files(project_root: Path, inputs: list[str]) -> tuple[list[Path] | None, list[Diagnostic]]:
    diags: list[Diagnostic] = []
    files: list[Path] = []
    contract_root = (project_root / "sdsl2" / "contract").absolute()
    if contract_root.is_symlink() or _has_symlink_parent(contract_root, project_root):
        _emit_diag(
            diags,
            "E_CONTRACT_RULE_CONTRACT_ROOT_SYMLINK",
            "Contract root must not be symlink",
            "non-symlink",
            str(contract_root),
            json_pointer("inputs"),
        )
        return None, diags
    for raw in inputs:
        path = Path(raw)
        if not path.is_absolute():
            path = (project_root / path).absolute()
        if path.is_symlink() or _has_symlink_parent(path, contract_root):
            _emit_diag(
                diags,
                "E_CONTRACT_RULE_INPUT_SYMLINK",
                "Input must not be symlink",
                "non-symlink",
                str(path),
                json_pointer("inputs"),
            )
            return None, diags
        if not _ensure_under_root(path, project_root, "E_CONTRACT_RULE_INPUT_OUTSIDE_PROJECT"):
            _emit_diag(
                diags,
                "E_CONTRACT_RULE_INPUT_OUTSIDE_PROJECT",
                "Input must be under project_root",
                "project_root/...",
                str(path),
                json_pointer("inputs"),
            )
            return None, diags
        if not _ensure_under_root(path, contract_root, "E_CONTRACT_RULE_INPUT_NOT_CONTRACT"):
            _emit_diag(
                diags,
                "E_CONTRACT_RULE_INPUT_NOT_CONTRACT",
                "Input must be under sdsl2/contract",
                "sdsl2/contract/...",
                str(path),
                json_pointer("inputs"),
            )
            return None, diags
        if path.is_dir():
            for file_path in sorted(path.rglob("*.sdsl2")):
                if file_path.is_symlink() or _has_symlink_parent(file_path, contract_root):
                    _emit_diag(
                        diags,
                        "E_CONTRACT_RULE_INPUT_SYMLINK",
                        "Input must not be symlink",
                        "non-symlink",
                        str(file_path),
                        json_pointer("inputs"),
                    )
                    return None, diags
                if file_path.is_file():
                    files.append(file_path)
        elif path.is_file():
            if path.suffix != ".sdsl2":
                _emit_diag(
                    diags,
                    "E_CONTRACT_RULE_INPUT_NOT_SDSL2",
                    "Input must be .sdsl2 file",
                    ".sdsl2",
                    str(path),
                    json_pointer("inputs"),
                )
                return None, diags
            files.append(path)
        else:
            _emit_diag(
                diags,
                "E_CONTRACT_RULE_INPUT_NOT_FILE",
                "Input must be file or directory",
                "file/dir",
                str(path),
                json_pointer("inputs"),
            )
            return None, diags
    if not files:
        _emit_diag(
            diags,
            "E_CONTRACT_RULE_INPUT_NOT_FOUND",
            "No contract files found",
            "existing .sdsl2 files",
            "missing",
            json_pointer("inputs"),
        )
        return None, diags
    return files, diags


def _parse_contract_list(
    raw_value: str,
    diags: list[Diagnostic],
    idx: int,
) -> list[str]:
    items = _split_list_items(raw_value)
    if not items:
        _emit_diag(
            diags,
            "E_CONTRACT_RULE_CONTRACT_INVALID",
            "contract must be list syntax",
            "contract:[\"CONTRACT.X\", ...]",
            raw_value,
            json_pointer("annotations", str(idx), "contract"),
        )
        return []
    tokens: list[str] = []
    for item_idx, raw in enumerate(items):
        token = raw.strip().strip('"')
        if not parse_contract_ref(token):
            _emit_diag(
                diags,
                "E_CONTRACT_RULE_CONTRACT_INVALID",
                "contract item must be CONTRACT.*",
                "CONTRACT.*",
                token,
                json_pointer("annotations", str(idx), "contract", str(item_idx)),
            )
            continue
        tokens.append(token)
    return tokens


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", action="append", required=True, help="Contract .sdsl2 file or directory")
    ap.add_argument(
        "--decisions-path",
        default="decisions/edges.yaml",
        help="decisions/edges.yaml path",
    )
    ap.add_argument(
        "--allow-nonstandard-path",
        action="store_true",
        help="Allow decisions file outside decisions/edges.yaml",
    )
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); inputs can be relative to it",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    files, file_diags = _collect_contract_files(project_root, args.input)
    if file_diags:
        _print_diags(file_diags)
        return 2
    if files is None:
        return 2

    decisions_path = _resolve_path(project_root, args.decisions_path)
    if decisions_path.is_symlink() or _has_symlink_parent(decisions_path, project_root):
        _print_diags([
            Diagnostic(
                code="E_CONTRACT_RULE_DECISIONS_SYMLINK",
                message="decisions path must not be symlink",
                expected="non-symlink",
                got=str(decisions_path),
                path=json_pointer("decisions"),
            )
        ])
        return 2
    if not _ensure_under_root(decisions_path, project_root, "E_CONTRACT_RULE_DECISIONS_OUTSIDE_PROJECT"):
        _print_diags([
            Diagnostic(
                code="E_CONTRACT_RULE_DECISIONS_OUTSIDE_PROJECT",
                message="decisions path must be under project_root",
                expected="project_root/...",
                got=str(decisions_path),
                path=json_pointer("decisions"),
            )
        ])
        return 2
    if not decisions_path.exists():
        _print_diags([
            Diagnostic(
                code="E_CONTRACT_RULE_DECISIONS_NOT_FOUND",
                message="decisions file not found",
                expected="existing file",
                got=str(decisions_path),
                path=json_pointer("decisions"),
            )
        ])
        return 2
    if decisions_path.is_dir():
        _print_diags([
            Diagnostic(
                code="E_CONTRACT_RULE_DECISIONS_IS_DIR",
                message="decisions path must be file",
                expected="file",
                got=str(decisions_path),
                path=json_pointer("decisions"),
            )
        ])
        return 2
    if not args.allow_nonstandard_path:
        expected = (project_root / "decisions" / "edges.yaml").resolve()
        if decisions_path.resolve() != expected:
            _print_diags([
                Diagnostic(
                    code="E_CONTRACT_RULE_DECISIONS_NOT_STANDARD_PATH",
                    message="decisions path must be decisions/edges.yaml",
                    expected=str(expected),
                    got=str(decisions_path),
                    path=json_pointer("decisions"),
                )
            ])
            return 2

    decisions, decision_diags = parse_decisions_file(decisions_path, project_root)
    if decision_diags:
        _print_diags(decision_diags)
        return 2
    if not decisions:
        _print_diags([
            Diagnostic(
                code="E_CONTRACT_RULE_DECISIONS_EMPTY",
                message="decisions file is empty",
                expected="non-empty decisions",
                got="empty",
                path=json_pointer("decisions"),
            )
        ])
        return 2

    profile_diags: list[Diagnostic] = []
    profile = _load_profile(project_root, profile_diags)
    prefix_bindings, allow_unmatched, require_bind = _parse_rule_naming(profile, profile_diags)
    require_rule_contract = _parse_rule_coverage(profile, profile_diags)
    if profile_diags:
        _print_diags(profile_diags)
        return 2

    decision_edges = decisions.get("edges", []) if isinstance(decisions, dict) else []
    decision_contracts: set[str] = set()
    for edge in decision_edges:
        if isinstance(edge, dict):
            refs = edge.get("contract_refs")
            if isinstance(refs, list):
                for ref in refs:
                    if isinstance(ref, str):
                        decision_contracts.add(ref)

    declared_contracts: set[str] = set()
    rule_contracts: set[str] = set()
    rule_entries: list[dict[str, object]] = []
    rule_index = 0

    for path in sorted(files, key=lambda p: p.as_posix()):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            _emit_diag(
                profile_diags,
                "E_CONTRACT_RULE_READ_FAILED",
                "Failed to read contract file",
                "readable UTF-8 file",
                f"{path}: {exc}",
                json_pointer(),
            )
            continue
        annotations = _iter_annotations(lines)
        first_stmt = _first_stmt_line(lines)

        file_headers = [(meta, idx) for kind, meta, idx, _, _ in annotations if kind == "File" and meta is not None]
        if not file_headers:
            _emit_diag(
                profile_diags,
                "E_CONTRACT_RULE_FILE_HEADER_MISSING",
                "Missing @File header",
                "@File { profile:\"contract\" }",
                "missing",
                json_pointer(),
            )
            continue
        if len(file_headers) > 1:
            _emit_diag(
                profile_diags,
                "E_CONTRACT_RULE_FILE_HEADER_DUPLICATE",
                "Duplicate @File headers",
                "single @File",
                ",".join(str(item[1] + 1) for item in file_headers),
                json_pointer("file_header"),
            )
            continue
        file_meta, _ = file_headers[0]
        if first_stmt is not None and file_headers[0][1] != first_stmt:
            _emit_diag(
                profile_diags,
                "E_CONTRACT_RULE_FILE_HEADER_NOT_FIRST",
                "@File must be the first non-comment statement",
                "first statement is @File",
                str(file_headers[0][1] + 1),
                json_pointer("file_header"),
            )
            continue
        file_profile = _strip_quotes(file_meta.get("profile"))
        if file_profile != "contract":
            _emit_diag(
                profile_diags,
                "E_CONTRACT_RULE_PROFILE_INVALID",
                "profile must be contract",
                "contract",
                str(file_profile),
                json_pointer("file_header", "profile"),
            )
            continue

        for kind, meta, idx, _, dupes in annotations:
            if meta is None or dupes:
                continue
            contract_raw = meta.get("contract")
            if isinstance(contract_raw, str) and contract_raw.strip():
                tokens = _parse_contract_list(contract_raw, profile_diags, idx)
                if tokens:
                    declared_contracts.update(tokens)
                    if kind == "Rule":
                        rule_contracts.update(tokens)
            if kind == "Rule":
                rule_id = _strip_quotes(meta.get("id"))
                bind_raw = _strip_quotes(meta.get("bind"))
                bind_ref = _parse_rule_bind(bind_raw)
                rule_entries.append(
                    {
                        "id": rule_id,
                        "bind": bind_ref,
                        "index": rule_index,
                        "line": idx + 1,
                    }
                )
                rule_index += 1

    if profile_diags:
        _print_diags(profile_diags)
        return 2

    rule_diags: list[Diagnostic] = []
    prefixes_sorted = sorted(prefix_bindings.keys(), key=len, reverse=True)
    for entry in rule_entries:
        rule_id = entry.get("id")
        if not isinstance(rule_id, str) or not RELID_RE.match(rule_id):
            continue
        matched: str | None = None
        for prefix in prefixes_sorted:
            if rule_id.startswith(prefix):
                matched = prefix
                break
        if matched is None:
            if not allow_unmatched:
                _emit_diag(
                    rule_diags,
                    "E_CONTRACT_RULE_PREFIX_INVALID",
                    "Rule id prefix not allowed",
                    "prefix in rule_naming.prefix_bindings",
                    rule_id,
                    json_pointer("rules", str(entry.get("index", 0)), "id"),
                )
            continue
        bind_ref = entry.get("bind")
        if not bind_ref:
            if require_bind:
                _emit_diag(
                    rule_diags,
                    "E_CONTRACT_RULE_BIND_MISSING",
                    "Rule bind required for prefix",
                    "bind:@Kind.RELID",
                    "missing",
                    json_pointer("rules", str(entry.get("index", 0)), "bind"),
                )
            continue
        if not hasattr(bind_ref, "kind"):
            _emit_diag(
                rule_diags,
                "E_CONTRACT_RULE_BIND_INVALID",
                "Rule bind must be internal ref",
                "@Kind.RELID",
                str(bind_ref),
                json_pointer("rules", str(entry.get("index", 0)), "bind"),
            )
            continue
        allowed = prefix_bindings.get(matched, [])
        if allowed and bind_ref.kind not in allowed:
            _emit_diag(
                rule_diags,
                "E_CONTRACT_RULE_BIND_KIND_INVALID",
                "Rule bind kind not allowed for prefix",
                ",".join(sorted(allowed)),
                bind_ref.kind,
                json_pointer("rules", str(entry.get("index", 0)), "bind"),
            )

    for token in sorted(decision_contracts):
        if token not in declared_contracts:
            _emit_diag(
                rule_diags,
                "E_CONTRACT_RULE_CONTRACT_MISSING",
                "contract_refs token missing from contract definitions",
                "declared CONTRACT.*",
                token,
                json_pointer("decisions", "contract_refs"),
            )
            continue
        if require_rule_contract and token not in rule_contracts:
            _emit_diag(
                rule_diags,
                "E_CONTRACT_RULE_COVERAGE_MISSING",
                "contract_refs token missing from @Rule coverage",
                "covered by @Rule contract list",
                token,
                json_pointer("decisions", "contract_refs"),
            )

    if rule_diags:
        _print_diags(rule_diags)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

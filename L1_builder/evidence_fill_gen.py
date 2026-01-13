#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import difflib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from L1_builder.decisions_lint import parse_decisions_file
from L1_builder.evidence_lint import validate_evidence_data
from L1_builder.evidence_repair import _compute_hash
from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.io_atomic import atomic_write_text
from sdslv2_builder.op_yaml import DuplicateKey, dump_yaml, load_yaml_with_duplicates


def _diag(
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


def _resolve_path(base: Path, raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (base / path).resolve()
    return path


def _has_symlink_parent(path: Path, stop: Path) -> bool:
    for parent in [path, *path.parents]:
        if parent == stop:
            break
        if parent.is_symlink():
            return True
    return False


def _git_rev(root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return "UNKNOWN"
    if proc.returncode != 0:
        return "UNKNOWN"
    return proc.stdout.strip() or "UNKNOWN"


def _build_source_rev(git_rev: str, generator_id: str) -> str:
    return f"{git_rev}|gen:{generator_id}"


def _dup_path(prefix: str, dup: DuplicateKey) -> str:
    if prefix:
        if dup.path:
            return prefix + dup.path
        return prefix
    return dup.path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--decisions-path", default="decisions/edges.yaml", help="decisions/edges.yaml path")
    ap.add_argument("--evidence-path", default="decisions/evidence.yaml", help="decisions/evidence.yaml path")
    ap.add_argument("--allow-nonstandard-path", action="store_true", help="Allow nonstandard paths")
    ap.add_argument("--out", default=None, help="Unified diff output path (default: stdout)")
    ap.add_argument("--generator-id", default="evidence_fill_gen_v0_1", help="generator id")
    ap.add_argument("--project-root", default=None, help="Project root (defaults to repo root)")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    decisions_path = _resolve_path(project_root, args.decisions_path)
    evidence_path = _resolve_path(project_root, args.evidence_path)

    for label, path in [("decisions", decisions_path), ("evidence", evidence_path)]:
        try:
            path.resolve().relative_to(project_root.resolve())
        except ValueError:
            _print_diags(
                [
                    Diagnostic(
                        code=f"E_EVIDENCE_FILL_{label.upper()}_OUTSIDE_PROJECT",
                        message=f"{label} path must be under project_root",
                        expected="project_root/...",
                        got=str(path),
                        path=json_pointer(label),
                    )
                ]
            )
            return 2
        if not path.exists():
            _print_diags(
                [
                    Diagnostic(
                        code=f"E_EVIDENCE_FILL_{label.upper()}_NOT_FOUND",
                        message=f"{label} path not found",
                        expected="existing file",
                        got=str(path),
                        path=json_pointer(label),
                    )
                ]
            )
            return 2
        if path.is_dir():
            _print_diags(
                [
                    Diagnostic(
                        code=f"E_EVIDENCE_FILL_{label.upper()}_IS_DIR",
                        message=f"{label} path must be file",
                        expected="file",
                        got=str(path),
                        path=json_pointer(label),
                    )
                ]
            )
            return 2
        if path.is_symlink() or _has_symlink_parent(path, project_root):
            _print_diags(
                [
                    Diagnostic(
                        code=f"E_EVIDENCE_FILL_{label.upper()}_SYMLINK",
                        message=f"{label} path must not be symlink",
                        expected="non-symlink",
                        got=str(path),
                        path=json_pointer(label),
                    )
                ]
            )
            return 2

    if not args.allow_nonstandard_path:
        expected_decisions = (project_root / "decisions" / "edges.yaml").resolve()
        expected_evidence = (project_root / "decisions" / "evidence.yaml").resolve()
        if decisions_path.resolve() != expected_decisions:
            _print_diags(
                [
                    Diagnostic(
                        code="E_EVIDENCE_FILL_DECISIONS_NOT_STANDARD",
                        message="decisions path must be decisions/edges.yaml",
                        expected=str(expected_decisions),
                        got=str(decisions_path),
                        path=json_pointer("decisions"),
                    )
                ]
            )
            return 2
        if evidence_path.resolve() != expected_evidence:
            _print_diags(
                [
                    Diagnostic(
                        code="E_EVIDENCE_FILL_EVIDENCE_NOT_STANDARD",
                        message="evidence path must be decisions/evidence.yaml",
                        expected=str(expected_evidence),
                        got=str(evidence_path),
                        path=json_pointer("evidence"),
                    )
                ]
            )
            return 2

    decisions, decision_diags = parse_decisions_file(decisions_path, project_root)
    if decision_diags:
        _print_diags(decision_diags)
        return 2

    try:
        evidence_data, duplicates = load_yaml_with_duplicates(evidence_path, allow_duplicates=True)
    except Exception as exc:
        _print_diags(
            [
                Diagnostic(
                    code="E_EVIDENCE_FILL_PARSE_FAILED",
                    message="evidence must be valid YAML",
                    expected="valid YAML",
                    got=str(exc),
                    path=json_pointer("evidence"),
                )
            ]
        )
        return 2
    if duplicates:
        dup_diags = [
            Diagnostic(
                code="E_EVIDENCE_FILL_DUPLICATE_KEY",
                message="duplicate key in evidence YAML",
                expected="unique key",
                got=dup.key,
                path=_dup_path(json_pointer("evidence"), dup),
            )
            for dup in duplicates
        ]
        _print_diags(dup_diags)
        return 2

    validated, evidence_diags = validate_evidence_data(evidence_data, decisions, project_root)
    if evidence_diags or validated is None:
        _print_diags(evidence_diags)
        return 2

    source_rev = _build_source_rev(_git_rev(project_root), args.generator_id)
    diags: list[Diagnostic] = []
    updated: dict[str, object] = {}
    validated_data = validated
    preferred_order = ["schema_version", "source_rev", "input_hash", "scope", "evidence"]
    for key in preferred_order:
        if key == "source_rev":
            updated[key] = source_rev
            continue
        if key in validated_data:
            updated[key] = validated_data[key]
    for key in validated_data.keys():
        if key in updated:
            continue
        updated[key] = validated_data[key]
    evidence_map = validated_data.get("evidence", {})
    if "evidence" in updated:
        if not isinstance(evidence_map, dict):
            _diag(
                diags,
                "E_EVIDENCE_FILL_INVALID",
                "evidence must be object",
                "object",
                type(evidence_map).__name__,
                json_pointer("evidence"),
            )
        else:
            new_map: dict[str, object] = {}
            for decision_id, entries in evidence_map.items():
                if not isinstance(entries, list):
                    _diag(
                        diags,
                        "E_EVIDENCE_FILL_INVALID",
                        "evidence entries must be list",
                        "list",
                        type(entries).__name__,
                        json_pointer("evidence", str(decision_id)),
                    )
                    continue
                new_entries: list[dict[str, object]] = []
                for idx, entry in enumerate(entries):
                    if not isinstance(entry, dict):
                        _diag(
                            diags,
                            "E_EVIDENCE_FILL_INVALID",
                            "evidence item must be object",
                            "object",
                            type(entry).__name__,
                            json_pointer("evidence", str(decision_id), str(idx)),
                        )
                        continue
                    source_path = entry.get("source_path", "")
                    locator = entry.get("locator", "")
                    path_ref = json_pointer("evidence", str(decision_id), str(idx), "content_hash")
                    new_hash = _compute_hash(project_root, source_path, locator, diags, path_ref)
                    new_entry = dict(entry)
                    if new_hash is not None:
                        new_entry["content_hash"] = new_hash
                    new_entries.append(new_entry)
                new_map[str(decision_id)] = new_entries
            updated["evidence"] = new_map

    if diags:
        _print_diags(diags)
        return 2

    try:
        old_text = evidence_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        _print_diags(
            [
                Diagnostic(
                    code="E_EVIDENCE_FILL_READ_FAILED",
                    message="evidence must be readable UTF-8",
                    expected="readable UTF-8 file",
                    got=str(exc),
                    path=json_pointer("evidence"),
                )
            ]
        )
        return 2
    new_text = dump_yaml(updated)
    diff = difflib.unified_diff(
        old_text.splitlines(),
        new_text.splitlines(),
        fromfile=str(evidence_path),
        tofile=str(evidence_path),
        lineterm="",
    )
    output = "\n".join(diff)
    if not output:
        _print_diags(
            [
                Diagnostic(
                    code="E_EVIDENCE_FILL_NO_CHANGE",
                    message="no content_hash updates",
                    expected="diff",
                    got="no change",
                    path=json_pointer("evidence"),
                )
            ]
        )
        return 2

    if args.out:
        out_path = _resolve_path(project_root, args.out)
        try:
            out_path.resolve().relative_to(project_root.resolve())
        except ValueError:
            _print_diags(
                [
                    Diagnostic(
                        code="E_EVIDENCE_FILL_OUTSIDE_PROJECT",
                        message="out must be under project_root",
                        expected="project_root/...",
                        got=str(out_path),
                        path=json_pointer("out"),
                    )
                ]
            )
            return 2
        if out_path.exists() and out_path.is_dir():
            _print_diags(
                [
                    Diagnostic(
                        code="E_EVIDENCE_FILL_OUT_IS_DIR",
                        message="out must be file",
                        expected="file",
                        got=str(out_path),
                        path=json_pointer("out"),
                    )
                ]
            )
            return 2
        if out_path.exists() and out_path.is_symlink():
            _print_diags(
                [
                    Diagnostic(
                        code="E_EVIDENCE_FILL_OUT_SYMLINK",
                        message="out must not be symlink",
                        expected="non-symlink",
                        got=str(out_path),
                        path=json_pointer("out"),
                    )
                ]
            )
            return 2
        if _has_symlink_parent(out_path, project_root):
            _print_diags(
                [
                    Diagnostic(
                        code="E_EVIDENCE_FILL_OUT_SYMLINK_PARENT",
                        message="out parent must not be symlink",
                        expected="non-symlink",
                        got=str(out_path),
                        path=json_pointer("out"),
                    )
                ]
            )
            return 2
        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            atomic_write_text(out_path, output + "\n", symlink_code="E_EVIDENCE_FILL_OUT_SYMLINK")
        except (ValueError, OSError) as exc:
            _print_diags(
                [
                    Diagnostic(
                        code="E_EVIDENCE_FILL_OUT_WRITE_FAILED",
                        message="out write failed",
                        expected="writable path",
                        got=str(out_path),
                        path=json_pointer("out"),
                    )
                ]
            )
            return 2
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

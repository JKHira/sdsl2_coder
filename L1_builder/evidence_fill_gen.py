#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ruff: noqa: E402

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
from sdslv2_builder.input_hash import compute_input_hash
from sdslv2_builder.op_yaml import DuplicateKey, dump_yaml, load_yaml_with_duplicates

TOOL_NAME = "evidence_fill_gen"
STAGE = "L1"
DEFAULT_OUT_REL = Path("OUTPUT") / "evidence_fill.patch"


def _diag(
    diags: list[Diagnostic],
    code: str,
    message: str,
    expected: str,
    got: str,
    path: str,
) -> None:
    diags.append(Diagnostic(code=code, message=message, expected=expected, got=got, path=path))


def _emit_result(
    status: str,
    diags: list[Diagnostic],
    inputs: list[str],
    outputs: list[str],
    diff_paths: list[str],
    source_rev: str | None = None,
    input_hash: str | None = None,
    summary: str | None = None,
    next_actions: list[str] | None = None,
    gaps_missing: list[str] | None = None,
    gaps_invalid: list[str] | None = None,
) -> None:
    codes = sorted({diag.code for diag in diags})
    payload = {
        "status": status,
        "tool": TOOL_NAME,
        "stage": STAGE,
        "source_rev": source_rev,
        "input_hash": input_hash,
        "inputs": inputs,
        "outputs": outputs,
        "diff_paths": diff_paths,
        "diagnostics": {"count": len(diags), "codes": codes},
        "gaps": {
            "missing": gaps_missing or [],
            "invalid": gaps_invalid or [],
        },
        "next_actions": next_actions or [],
    }
    print(json.dumps(payload, ensure_ascii=False))
    if summary:
        print(summary, file=sys.stderr)


def _resolve_path(base: Path, raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (base / path).resolve()
    return path


def _rel_path(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path)


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
    ap.add_argument("--out", default=None, help="Unified diff output path (default: OUTPUT/evidence_fill.patch)")
    ap.add_argument("--generator-id", default="evidence_fill_gen_v0_1", help="generator id")
    ap.add_argument("--project-root", default=None, help="Project root (defaults to repo root)")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    decisions_path = _resolve_path(project_root, args.decisions_path)
    evidence_path = _resolve_path(project_root, args.evidence_path)
    out_path = _resolve_path(project_root, args.out) if args.out else project_root / DEFAULT_OUT_REL

    inputs = [
        _rel_path(project_root, decisions_path),
        _rel_path(project_root, evidence_path),
    ]
    outputs = [_rel_path(project_root, out_path)]
    diff_paths = [_rel_path(project_root, out_path)]

    diags: list[Diagnostic] = []
    for label, path in [("decisions", decisions_path), ("evidence", evidence_path)]:
        try:
            path.resolve().relative_to(project_root.resolve())
        except ValueError:
            _diag(
                diags,
                f"E_EVIDENCE_FILL_{label.upper()}_OUTSIDE_PROJECT",
                f"{label} path must be under project_root",
                "project_root/...",
                str(path),
                json_pointer(label),
            )
        if not path.exists():
            _diag(
                diags,
                f"E_EVIDENCE_FILL_{label.upper()}_NOT_FOUND",
                f"{label} path not found",
                "existing file",
                str(path),
                json_pointer(label),
            )
        if path.exists() and path.is_dir():
            _diag(
                diags,
                f"E_EVIDENCE_FILL_{label.upper()}_IS_DIR",
                f"{label} path must be file",
                "file",
                str(path),
                json_pointer(label),
            )
        if path.exists() and (path.is_symlink() or _has_symlink_parent(path, project_root)):
            _diag(
                diags,
                f"E_EVIDENCE_FILL_{label.upper()}_SYMLINK",
                f"{label} path must not be symlink",
                "non-symlink",
                str(path),
                json_pointer(label),
            )

    if not args.allow_nonstandard_path:
        expected_decisions = (project_root / "decisions" / "edges.yaml").resolve()
        expected_evidence = (project_root / "decisions" / "evidence.yaml").resolve()
        if decisions_path.resolve() != expected_decisions:
            _diag(
                diags,
                "E_EVIDENCE_FILL_DECISIONS_NOT_STANDARD",
                "decisions path must be decisions/edges.yaml",
                str(expected_decisions),
                str(decisions_path),
                json_pointer("decisions"),
            )
        if evidence_path.resolve() != expected_evidence:
            _diag(
                diags,
                "E_EVIDENCE_FILL_EVIDENCE_NOT_STANDARD",
                "evidence path must be decisions/evidence.yaml",
                str(expected_evidence),
                str(evidence_path),
                json_pointer("evidence"),
            )

    if diags:
        _emit_result(
            "fail",
            diags,
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: input validation failed",
        )
        return 2

    decisions, decision_diags = parse_decisions_file(decisions_path, project_root)
    if decision_diags:
        _emit_result(
            "fail",
            decision_diags,
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: decisions validation failed",
        )
        return 2

    try:
        evidence_data, duplicates = load_yaml_with_duplicates(evidence_path, allow_duplicates=True)
    except Exception as exc:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_EVIDENCE_FILL_PARSE_FAILED",
                    message="evidence must be valid YAML",
                    expected="valid YAML",
                    got=str(exc),
                    path=json_pointer("evidence"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: evidence parse failed",
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
        _emit_result(
            "fail",
            dup_diags,
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: duplicate keys",
        )
        return 2

    validated, evidence_diags = validate_evidence_data(evidence_data, decisions, project_root)
    if evidence_diags or validated is None:
        _emit_result(
            "fail",
            evidence_diags,
            inputs,
            outputs,
            diff_paths,
            summary=f"{TOOL_NAME}: evidence validation failed",
        )
        return 2

    source_rev = _build_source_rev(_git_rev(project_root), args.generator_id)
    diags = []
    updated: dict[str, object] = {}
    validated_data = validated
    preferred_order = ["schema_version", "source_rev", "input_hash", "scope", "evidence"]
    for key in preferred_order:
        if key == "source_rev":
            updated[key] = source_rev
            continue
        if key == "input_hash":
            updated[key] = None
            continue
        if key in validated_data:
            updated[key] = validated_data[key]
    for key in validated_data.keys():
        if key in updated:
            continue
        updated[key] = validated_data[key]
    evidence_map = validated_data.get("evidence", {})
    source_inputs: set[Path] = set()
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
                        if isinstance(source_path, str) and source_path.strip():
                            source_inputs.add((project_root / source_path).resolve())
                    new_entries.append(new_entry)
                new_map[str(decision_id)] = new_entries
            updated["evidence"] = new_map

    if diags:
        _emit_result(
            "fail",
            diags,
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=None,
            summary=f"{TOOL_NAME}: evidence update failed",
        )
        return 2

    try:
        extra_inputs = [decisions_path, *sorted(source_inputs)]
        hash_result = compute_input_hash(
            project_root,
            include_decisions=False,
            extra_inputs=extra_inputs,
        )
    except (FileNotFoundError, ValueError, OSError, UnicodeDecodeError) as exc:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_EVIDENCE_FILL_INPUT_HASH_FAILED",
                    message="input_hash calculation failed",
                    expected="valid inputs",
                    got=str(exc),
                    path=json_pointer("input_hash"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            summary=f"{TOOL_NAME}: input_hash failed",
        )
        return 2

    updated["input_hash"] = hash_result.input_hash

    try:
        old_text = evidence_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_EVIDENCE_FILL_READ_FAILED",
                    message="evidence must be readable UTF-8",
                    expected="readable UTF-8 file",
                    got=str(exc),
                    path=json_pointer("evidence"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=hash_result.input_hash,
            summary=f"{TOOL_NAME}: read failed",
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
        _emit_result(
            "diag",
            [
                Diagnostic(
                    code="E_EVIDENCE_FILL_NO_CHANGE",
                    message="no content_hash updates",
                    expected="diff",
                    got="no change",
                    path=json_pointer("evidence"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=hash_result.input_hash,
            summary=f"{TOOL_NAME}: no changes required",
        )
        return 0

    try:
        out_path.resolve().relative_to(project_root.resolve())
    except ValueError:
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_EVIDENCE_FILL_OUTSIDE_PROJECT",
                    message="out must be under project_root",
                    expected="project_root/...",
                    got=str(out_path),
                    path=json_pointer("out"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=hash_result.input_hash,
            summary=f"{TOOL_NAME}: invalid output path",
        )
        return 2
    if out_path.exists() and out_path.is_dir():
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_EVIDENCE_FILL_OUT_IS_DIR",
                    message="out must be file",
                    expected="file",
                    got=str(out_path),
                    path=json_pointer("out"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=hash_result.input_hash,
            summary=f"{TOOL_NAME}: invalid output path",
        )
        return 2
    if out_path.exists() and out_path.is_symlink():
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_EVIDENCE_FILL_OUT_SYMLINK",
                    message="out must not be symlink",
                    expected="non-symlink",
                    got=str(out_path),
                    path=json_pointer("out"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=hash_result.input_hash,
            summary=f"{TOOL_NAME}: invalid output path",
        )
        return 2
    if _has_symlink_parent(out_path, project_root):
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_EVIDENCE_FILL_OUT_SYMLINK_PARENT",
                    message="out parent must not be symlink",
                    expected="non-symlink",
                    got=str(out_path),
                    path=json_pointer("out"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=hash_result.input_hash,
            summary=f"{TOOL_NAME}: invalid output path",
        )
        return 2
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_text(out_path, output + "\n", symlink_code="E_EVIDENCE_FILL_OUT_SYMLINK")
    except (ValueError, OSError):
        _emit_result(
            "fail",
            [
                Diagnostic(
                    code="E_EVIDENCE_FILL_OUT_WRITE_FAILED",
                    message="out write failed",
                    expected="writable path",
                    got=str(out_path),
                    path=json_pointer("out"),
                )
            ],
            inputs,
            outputs,
            diff_paths,
            source_rev=source_rev,
            input_hash=hash_result.input_hash,
            summary=f"{TOOL_NAME}: output write failed",
        )
        return 2

    _emit_result(
        "ok",
        [],
        inputs,
        outputs,
        diff_paths,
        source_rev=source_rev,
        input_hash=hash_result.input_hash,
        summary=f"{TOOL_NAME}: diff written",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

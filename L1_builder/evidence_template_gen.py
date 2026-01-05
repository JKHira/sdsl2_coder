#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from L1_builder.decisions_lint import parse_decisions_file
from sdslv2_builder.input_hash import compute_input_hash
from sdslv2_builder.op_yaml import dump_yaml


def _git_rev(root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return "UNKNOWN"
    if proc.returncode != 0:
        return "UNKNOWN"
    return proc.stdout.strip() or "UNKNOWN"


def _resolve_path(base: Path, raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (base / path).resolve()
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


def main() -> int:
    ap = argparse.ArgumentParser()
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
        "--out",
        default=None,
        help="Output path (default: OUTPUT/evidence_template.yaml)",
    )
    ap.add_argument(
        "--allow-decisions-output",
        action="store_true",
        help="Allow output under decisions/evidence.yaml",
    )
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); outputs must stay under OUTPUT/ or decisions/",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    decisions_path = _resolve_path(project_root, args.decisions_path)
    try:
        _ensure_inside(project_root, decisions_path, "E_EVIDENCE_TEMPLATE_INPUT_OUTSIDE_PROJECT")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not decisions_path.exists():
        print("E_EVIDENCE_TEMPLATE_DECISIONS_NOT_FOUND", file=sys.stderr)
        return 2
    if decisions_path.is_dir():
        print("E_EVIDENCE_TEMPLATE_DECISIONS_IS_DIR", file=sys.stderr)
        return 2
    if decisions_path.is_symlink():
        print("E_EVIDENCE_TEMPLATE_DECISIONS_SYMLINK", file=sys.stderr)
        return 2
    if not args.allow_nonstandard_path:
        expected = (project_root / "decisions" / "edges.yaml").resolve()
        if decisions_path.resolve() != expected:
            print("E_EVIDENCE_TEMPLATE_DECISIONS_NOT_STANDARD_PATH", file=sys.stderr)
            return 2

    decisions, diags = parse_decisions_file(decisions_path, project_root)
    if diags:
        payload = [d.to_dict() for d in diags]
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2

    try:
        input_hash = compute_input_hash(
            project_root,
            include_decisions=False,
            extra_inputs=[decisions_path],
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    decision_edges = decisions.get("edges", [])
    edges_by_id: list[tuple[str, list[str]]] = []
    for edge in decision_edges:
        if not isinstance(edge, dict):
            continue
        decision_id = edge.get("id")
        if not decision_id:
            continue
        contract_refs = edge.get("contract_refs", [])
        if not isinstance(contract_refs, list):
            contract_refs = []
        contract_refs_sorted = sorted({ref for ref in contract_refs if isinstance(ref, str) and ref})
        edges_by_id.append((str(decision_id), contract_refs_sorted))

    evidence_map: dict[str, list[dict[str, object]]] = {}
    for decision_id, contract_refs in sorted(edges_by_id, key=lambda item: item[0]):
        claims: list[dict[str, object]] = [{"kind": "edge", "decision_id": decision_id}]
        for ref in contract_refs:
            claims.append({"kind": "contract_ref", "decision_id": decision_id, "value": ref})
        evidence_map[decision_id] = [
            {
                "source_path": "",
                "locator": "",
                "content_hash": "",
                "claims": claims,
            }
        ]

    data = {
        "schema_version": "1.0",
        "source_rev": _git_rev(ROOT),
        "input_hash": input_hash.input_hash,
        "scope": decisions.get("scope", {}),
        "evidence": evidence_map,
    }

    if args.out:
        out_path = _resolve_path(project_root, args.out)
    else:
        out_path = (project_root / "OUTPUT" / "evidence_template.yaml").resolve()
    try:
        _ensure_inside(project_root, out_path, "E_EVIDENCE_TEMPLATE_OUTPUT_OUTSIDE_PROJECT")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if out_path.exists() and out_path.is_dir():
        print("E_EVIDENCE_TEMPLATE_OUTPUT_IS_DIR", file=sys.stderr)
        return 2
    if out_path.exists() and out_path.is_symlink():
        print("E_EVIDENCE_TEMPLATE_OUTPUT_SYMLINK", file=sys.stderr)
        return 2
    if _has_symlink_parent(out_path, project_root):
        print("E_EVIDENCE_TEMPLATE_OUTPUT_SYMLINK_PARENT", file=sys.stderr)
        return 2

    allowed_output = project_root / "OUTPUT"
    decisions_output = project_root / "decisions" / "evidence.yaml"
    if out_path.resolve().is_relative_to(allowed_output.resolve()):
        pass
    elif args.allow_decisions_output and out_path.resolve() == decisions_output.resolve():
        pass
    else:
        print("E_EVIDENCE_TEMPLATE_OUTPUT_OUTSIDE_OUTPUT", file=sys.stderr)
        return 2

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(dump_yaml(data), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

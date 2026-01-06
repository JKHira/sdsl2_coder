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

from sdslv2_builder.policy_utils import get_gate_severity, load_policy


def _run_gate(
    cmd: list[str],
    gate_key: str | None,
    policy: dict,
    verbose: bool,
    exception_overrides: set[str],
    default_severity: str | None = None,
) -> int:
    if verbose:
        print("+", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    if proc.returncode == 0:
        return 0
    if gate_key is None:
        severity = "FAIL"
    else:
        severity = get_gate_severity(policy, gate_key, default=default_severity or "FAIL")
    if gate_key and gate_key in exception_overrides and severity == "FAIL":
        severity = "DIAG"
    if severity in {"DIAG", "IGNORE"}:
        print(f"[{severity}] {gate_key}", file=sys.stderr)
        return 0
    return 2


def _list_draft_files(drafts_root: Path) -> list[Path]:
    files: list[Path] = []
    if not drafts_root.exists():
        return files
    intent_root = drafts_root / "intent"
    for path in sorted(drafts_root.rglob("*.yaml")):
        if intent_root in path.parents:
            continue
        if path.is_file():
            files.append(path)
    return files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--project-root",
        default=None,
        help="Project root (defaults to repo root); inputs can be relative to it",
    )
    ap.add_argument(
        "--decisions-path",
        default="decisions/edges.yaml",
        help="decisions/edges.yaml path",
    )
    ap.add_argument(
        "--evidence-path",
        default="decisions/evidence.yaml",
        help="decisions/evidence.yaml path",
    )
    ap.add_argument(
        "--allow-nonstandard-path",
        action="store_true",
        help="Allow decisions/evidence paths outside standard locations",
    )
    ap.add_argument(
        "--determinism-manifest",
        default=None,
        help="Run determinism_check.py with this manifest",
    )
    ap.add_argument(
        "--ssot-registry",
        default="OUTPUT/ssot/ssot_registry.json",
        help="SSOT registry path for token_registry_check",
    )
    ap.add_argument(
        "--contract-registry",
        default="OUTPUT/ssot/contract_registry.json",
        help="Contract registry path for token_registry_check",
    )
    ap.add_argument(
        "--evidence-repair-out",
        default=None,
        help="Write evidence repair diff to this path (default: stdout)",
    )
    ap.add_argument(
        "--policy-path",
        default=None,
        help="Explicit policy path for gate severities",
    )
    ap.add_argument(
        "--fail-on-unresolved",
        action="store_true",
        help="Treat UNRESOLVED token registry targets as failure",
    )
    ap.add_argument(
        "--exceptions-target",
        action="append",
        default=[],
        help="Gate key to downgrade to DIAG when exceptions are active",
    )
    ap.add_argument("--verbose", action="store_true", help="Print commands")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    py = sys.executable
    policy_path = Path(args.policy_path) if args.policy_path else None
    policy_result = load_policy(policy_path, project_root)
    if policy_result.diagnostics:
        payload = [d.to_dict() for d in policy_result.diagnostics]
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    policy = policy_result.policy

    exception_overrides = set(args.exceptions_target)

    dup_cmd = [
        py,
        str(ROOT / "L1_builder" / "duplicate_key_lint.py"),
        "--input",
        str(project_root / "drafts"),
        "--input",
        str(project_root / "decisions"),
        "--input",
        str(project_root / "policy"),
        "--input",
        str(project_root / ".sdsl" / "policy.yaml"),
        "--input",
        args.decisions_path,
        "--input",
        args.evidence_path,
        "--project-root",
        str(project_root),
    ]
    if _run_gate(dup_cmd, "duplicate_keys", policy, args.verbose, exception_overrides, default_severity="DIAG") != 0:
        return 2
    drafts_root = project_root / "drafts"
    for draft_path in _list_draft_files(drafts_root):
        cmd = [
            py,
            str(ROOT / "L0_builder" / "draft_lint.py"),
            "--input",
            str(draft_path),
            "--project-root",
            str(project_root),
        ]
        if _run_gate(cmd, "draft_schema", policy, args.verbose, exception_overrides) != 0:
            return 2

    intent_root = drafts_root / "intent"
    if intent_root.exists():
        cmd = [
            py,
            str(ROOT / "L1_builder" / "intent_lint.py"),
            "--input",
            str(intent_root),
            "--allow-empty",
            "--project-root",
            str(project_root),
        ]
        if args.allow_nonstandard_path:
            cmd.append("--allow-nonstandard-path")
        if _run_gate(cmd, "draft_schema", policy, args.verbose, exception_overrides) != 0:
            return 2

    schema_cmd = [
        py,
        str(ROOT / "L1_builder" / "schema_migration_check.py"),
        "--decisions-path",
        args.decisions_path,
        "--evidence-path",
        args.evidence_path,
        "--project-root",
        str(project_root),
    ]
    if _run_gate(schema_cmd, "schema_migration", policy, args.verbose, exception_overrides) != 0:
        return 2

    decisions_cmd = [
        py,
        str(ROOT / "L1_builder" / "decisions_lint.py"),
        "--input",
        args.decisions_path,
        "--project-root",
        str(project_root),
    ]
    if args.allow_nonstandard_path:
        decisions_cmd.append("--allow-nonstandard-path")
    if _run_gate(decisions_cmd, None, policy, args.verbose, exception_overrides) != 0:
        return 2

    evidence_cmd = [
        py,
        str(ROOT / "L1_builder" / "evidence_lint.py"),
        "--decisions-path",
        args.decisions_path,
        "--evidence-path",
        args.evidence_path,
        "--project-root",
        str(project_root),
    ]
    if args.allow_nonstandard_path:
        evidence_cmd.append("--allow-nonstandard-path")
    if _run_gate(evidence_cmd, "evidence_coverage", policy, args.verbose, exception_overrides) != 0:
        return 2

    repair_cmd = [
        py,
        str(ROOT / "L1_builder" / "evidence_repair.py"),
        "--decisions-path",
        args.decisions_path,
        "--evidence-path",
        args.evidence_path,
        "--project-root",
        str(project_root),
    ]
    if args.allow_nonstandard_path:
        repair_cmd.append("--allow-nonstandard-path")
    if args.evidence_repair_out:
        repair_cmd.extend(["--out", args.evidence_repair_out])
    if _run_gate(repair_cmd, "evidence_repair", policy, args.verbose, exception_overrides) != 0:
        return 2

    readiness_cmd = [
        py,
        str(ROOT / "L1_builder" / "readiness_check.py"),
        "--decisions-path",
        args.decisions_path,
        "--evidence-path",
        args.evidence_path,
        "--project-root",
        str(project_root),
    ]
    if args.allow_nonstandard_path:
        readiness_cmd.append("--allow-nonstandard-path")
    if _run_gate(readiness_cmd, "readiness_check", policy, args.verbose, exception_overrides) != 0:
        return 2

    no_ssot_cmd = [
        py,
        str(ROOT / "L1_builder" / "no_ssot_promotion_check.py"),
        "--project-root",
        str(project_root),
    ]
    if _run_gate(no_ssot_cmd, "no_ssot_promotion", policy, args.verbose, exception_overrides) != 0:
        return 2

    token_cmd = [
        py,
        str(ROOT / "L1_builder" / "token_registry_check.py"),
        "--ssot-registry",
        args.ssot_registry,
        "--contract-registry",
        args.contract_registry,
        "--project-root",
        str(project_root),
    ]
    if args.fail_on_unresolved:
        token_cmd.append("--fail-on-unresolved")
    token_gate_key = None if args.fail_on_unresolved else "token_registry"
    if _run_gate(token_cmd, token_gate_key, policy, args.verbose, exception_overrides) != 0:
        return 2

    if args.determinism_manifest:
        determinism_cmd = [
            py,
            str(ROOT / "scripts" / "determinism_check.py"),
            "--manifest",
            args.determinism_manifest,
        ]
        if _run_gate(determinism_cmd, "determinism", policy, args.verbose, exception_overrides) != 0:
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

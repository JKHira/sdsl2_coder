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


def _run_gate(cmd: list[str], gate_key: str | None, policy: dict, verbose: bool) -> int:
    if verbose:
        print("+", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    if proc.returncode == 0:
        return 0
    severity = "FAIL" if gate_key is None else get_gate_severity(policy, gate_key)
    if severity in {"DIAG", "IGNORE"}:
        print(f"[{severity}] {gate_key}", file=sys.stderr)
        return 0
    return 2


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
    ap.add_argument("--today", required=True, help="YYYY-MM-DD for exception_lint")
    ap.add_argument(
        "--publish",
        action="store_true",
        help="Run conformance_check and freshness_check for publish",
    )
    ap.add_argument(
        "--policy-path",
        default=None,
        help="Explicit policy path for gate severities",
    )
    ap.add_argument(
        "--verbose",
        action="store_true",
        help="Print commands",
    )
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else ROOT
    py = sys.executable
    policy_path = Path(args.policy_path) if args.policy_path else None
    policy_result = load_policy(policy_path, project_root)
    if policy_result.diagnostics:
        payload = [d.to_dict() for d in policy_result.diagnostics]
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    policy = policy_result.policy

    l1_cmd = [
        py,
        str(ROOT / "L1_builder" / "operational_gate.py"),
        "--decisions-path",
        args.decisions_path,
        "--evidence-path",
        args.evidence_path,
        "--project-root",
        str(project_root),
    ]
    if args.allow_nonstandard_path:
        l1_cmd.append("--allow-nonstandard-path")
    if args.policy_path:
        l1_cmd.extend(["--policy-path", args.policy_path])
    if _run_gate(l1_cmd, None, policy, args.verbose) != 0:
        return 2

    drift_cmd = [
        py,
        str(ROOT / "L1_builder" / "drift_check.py"),
        "--decisions-path",
        args.decisions_path,
        "--project-root",
        str(project_root),
    ]
    if args.allow_nonstandard_path:
        drift_cmd.append("--allow-nonstandard-path")
    if _run_gate(drift_cmd, None, policy, args.verbose) != 0:
        return 2

    exception_cmd = [
        py,
        str(ROOT / "L2_builder" / "exception_lint.py"),
        "--today",
        args.today,
        "--project-root",
        str(project_root),
    ]
    if _run_gate(exception_cmd, "l2_exception_check", policy, args.verbose) != 0:
        return 2

    if args.publish:
        conformance_cmd = [
            py,
            str(ROOT / "L2_builder" / "conformance_check.py"),
            "--project-root",
            str(project_root),
        ]
        if _run_gate(conformance_cmd, None, policy, args.verbose) != 0:
            return 2

        freshness_cmd = [
            py,
            str(ROOT / "L2_builder" / "freshness_check.py"),
            "--project-root",
            str(project_root),
        ]
        if _run_gate(freshness_cmd, None, policy, args.verbose) != 0:
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

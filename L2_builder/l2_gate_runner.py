#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from L2_builder.common import has_symlink_parent
from sdslv2_builder.op_yaml import load_yaml
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


def _run_drift_gate(cmd: list[str], policy: dict, verbose: bool) -> int:
    if verbose:
        print("+", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.returncode == 0:
        if proc.stderr:
            print(proc.stderr, end="", file=sys.stderr)
        return 0

    if not proc.stderr:
        return 2
    try:
        payload = json.loads(proc.stderr)
    except json.JSONDecodeError:
        print(proc.stderr, end="", file=sys.stderr)
        return 2
    if not isinstance(payload, list):
        print(proc.stderr, end="", file=sys.stderr)
        return 2

    drift_policy = policy.get("drift", {}) if isinstance(policy, dict) else {}
    allow_missing = bool(drift_policy.get("allow_missing_decisions_l0")) or bool(
        drift_policy.get("migration_window_l1")
    )
    allow_manual = bool(drift_policy.get("allow_manual_edges"))

    for item in payload:
        code = item.get("code") if isinstance(item, dict) else None
        if code == "E_DRIFT_DECISION_NOT_REFLECTED":
            if not allow_missing:
                print(proc.stderr, end="", file=sys.stderr)
                return 2
            continue
        if code == "E_DRIFT_MANUAL_EDGE":
            if not allow_manual:
                print(proc.stderr, end="", file=sys.stderr)
                return 2
            continue
        print(proc.stderr, end="", file=sys.stderr)
        return 2

    print(proc.stderr, end="", file=sys.stderr)
    print("[DIAG] drift_check", file=sys.stderr)
    return 0


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EXCEPTION_TARGET_TO_GATE = {
    "DRAFT-SCHEMA": "draft_schema",
    "EVIDENCE-COVERAGE": "evidence_coverage",
    "SCHEMA-MIGRATION": "schema_migration",
}


def _parse_date(value: str) -> date | None:
    if not DATE_RE.match(value):
        return None
    try:
        y, m, d = value.split("-")
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def _collect_exception_overrides(project_root: Path, today: date) -> set[str]:
    overrides: set[str] = set()
    exceptions_path = project_root / "policy" / "exceptions.yaml"
    if not exceptions_path.exists():
        return overrides
    if has_symlink_parent(exceptions_path, project_root) or exceptions_path.is_symlink():
        return overrides
    if exceptions_path.is_dir():
        return overrides
    try:
        exceptions_path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return overrides
    try:
        data = load_yaml(exceptions_path)
    except Exception:
        return overrides
    if not isinstance(data, dict):
        return overrides
    exceptions = data.get("exceptions")
    if not isinstance(exceptions, list):
        return overrides
    for item in exceptions:
        if not isinstance(item, dict):
            continue
        expires = item.get("expires")
        if not isinstance(expires, str):
            continue
        expires_date = _parse_date(expires)
        if not expires_date or expires_date < today:
            continue
        targets = item.get("targets")
        if not isinstance(targets, list):
            continue
        for target in targets:
            gate = EXCEPTION_TARGET_TO_GATE.get(target)
            if gate:
                overrides.add(gate)
    return overrides


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

    today = _parse_date(args.today)
    exception_overrides: set[str] = set()
    if today is not None:
        exception_overrides = _collect_exception_overrides(project_root, today)

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
    if args.publish:
        l1_cmd.append("--fail-on-unresolved")
    for gate in sorted(exception_overrides):
        l1_cmd.extend(["--exceptions-target", gate])
    if _run_gate(l1_cmd, None, policy, args.verbose) != 0:
        return 2

    contract_cmd = [
        py,
        str(ROOT / "L2_builder" / "contract_sdsl_lint.py"),
        "--input",
        str(project_root / "sdsl2" / "contract"),
        "--project-root",
        str(project_root),
    ]
    if _run_gate(contract_cmd, "contract_sdsl", policy, args.verbose) != 0:
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
    if _run_drift_gate(drift_cmd, policy, args.verbose) != 0:
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

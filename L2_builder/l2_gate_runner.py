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

from L2_builder.common import ensure_inside, has_symlink_parent, resolve_path
from sdslv2_builder.errors import Diagnostic, json_pointer
from sdslv2_builder.op_yaml import load_yaml
from sdslv2_builder.policy_utils import get_gate_severity, load_policy


def _run_gate(cmd: list[str], gate_key: str | None, policy: dict, verbose: bool, cwd: Path) -> int:
    if verbose:
        print("+", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
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


def _run_drift_gate(cmd: list[str], policy: dict, verbose: bool, cwd: Path) -> int:
    if verbose:
        print("+", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
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


def _print_diags(diags: list[Diagnostic]) -> None:
    payload = [d.to_dict() for d in diags]
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


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
        "--kernel-root",
        default=None,
        help="SSOT kernel source root (defaults to project root)",
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
        "--context-input",
        default=None,
        help="Topology .sdsl2 input for context_pack_gen (required with --publish)",
    )
    ap.add_argument(
        "--context-target",
        default=None,
        help="Target @Node.<RELID> for context_pack_gen (required with --publish)",
    )
    ap.add_argument(
        "--context-hops",
        default=None,
        type=int,
        help="Neighbor hops for context_pack_gen (optional)",
    )
    ap.add_argument(
        "--build-ssot",
        action="store_true",
        help="Build SSOT definitions and registries before running gates",
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

    if args.project_root:
        raw_root = Path(args.project_root)
        project_root = (ROOT / raw_root).resolve() if not raw_root.is_absolute() else raw_root.resolve()
    else:
        project_root = ROOT
    if args.kernel_root:
        raw_kernel = Path(args.kernel_root)
        kernel_root = (ROOT / raw_kernel).resolve() if not raw_kernel.is_absolute() else raw_kernel.resolve()
    else:
        kernel_root = project_root
    py = sys.executable
    policy_path = resolve_path(project_root, args.policy_path) if args.policy_path else None
    policy_result = load_policy(policy_path, project_root)
    if policy_result.diagnostics:
        payload = [d.to_dict() for d in policy_result.diagnostics]
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    policy = policy_result.policy

    today = _parse_date(args.today)
    exception_overrides: set[str] = set()
    if today is not None:
        exception_overrides = _collect_exception_overrides(project_root, today)

    if args.build_ssot:
        build_cmd = [
            py,
            str(ROOT / "ssot_kernel_builder" / "build_ssot_definitions.py"),
            "--project-root",
            str(project_root),
        ]
        if args.kernel_root:
            build_cmd.extend(["--kernel-root", str(kernel_root)])
        if _run_gate(build_cmd, None, policy, args.verbose, project_root) != 0:
            return 2
        contract_cmd = [
            py,
            str(ROOT / "L2_builder" / "contract_definitions_gen.py"),
            "--project-root",
            str(project_root),
        ]
        if _run_gate(contract_cmd, None, policy, args.verbose, project_root) != 0:
            return 2
        registry_cmd = [
            py,
            str(ROOT / "L2_builder" / "token_registry_gen.py"),
            "--project-root",
            str(project_root),
        ]
        if _run_gate(registry_cmd, None, policy, args.verbose, project_root) != 0:
            return 2
    elif args.publish:
        _print_diags(
            [
                Diagnostic(
                    code="E_L2_GATE_BUILD_SSOT_REQUIRED",
                    message="--build-ssot is required with --publish",
                    expected="--build-ssot",
                    got="missing",
                    path=json_pointer("publish"),
                )
            ]
        )
        return 2

    l1_cmd = [
        py,
        str(ROOT / "L1_builder" / "operational_gate.py"),
        "--decisions-path",
        args.decisions_path,
        "--evidence-path",
        args.evidence_path,
        "--project-root",
        str(project_root),
        "--today",
        args.today,
    ]
    if args.allow_nonstandard_path:
        l1_cmd.append("--allow-nonstandard-path")
    if args.policy_path:
        l1_cmd.extend(["--policy-path", args.policy_path])
    if args.publish:
        l1_cmd.append("--fail-on-unresolved")
    for gate in sorted(exception_overrides):
        l1_cmd.extend(["--exceptions-target", gate])
    if _run_gate(l1_cmd, None, policy, args.verbose, project_root) != 0:
        return 2

    contract_cmd = [
        py,
        str(ROOT / "L2_builder" / "contract_sdsl_lint.py"),
        "--input",
        str(project_root / "sdsl2" / "contract"),
        "--project-root",
        str(project_root),
    ]
    if _run_gate(contract_cmd, "contract_sdsl", policy, args.verbose, project_root) != 0:
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
    if _run_drift_gate(drift_cmd, policy, args.verbose, project_root) != 0:
        return 2

    exception_cmd = [
        py,
        str(ROOT / "L2_builder" / "exception_lint.py"),
        "--today",
        args.today,
        "--project-root",
        str(project_root),
    ]
    if _run_gate(exception_cmd, "l2_exception_check", policy, args.verbose, project_root) != 0:
        return 2

    if args.publish:
        source_cmd = [
            py,
            str(ROOT / "L2_builder" / "ssot_kernel_source_lint.py"),
            "--project-root",
            str(project_root),
        ]
        if args.kernel_root:
            source_cmd.extend(["--kernel-root", str(kernel_root)])
        if _run_gate(source_cmd, "ssot_kernel_source", policy, args.verbose, project_root) != 0:
            return 2

        kernel_cmd = [
            py,
            str(ROOT / "L2_builder" / "ssot_kernel_lint.py"),
            "--project-root",
            str(project_root),
        ]
        if _run_gate(kernel_cmd, "ssot_kernel", policy, args.verbose, project_root) != 0:
            return 2

        coverage_cmd = [
            py,
            str(ROOT / "L2_builder" / "ssot_kernel_coverage_check.py"),
            "--project-root",
            str(project_root),
        ]
        if _run_gate(coverage_cmd, "ssot_kernel_coverage", policy, args.verbose, project_root) != 0:
            return 2

        registry_cmd = [
            py,
            str(ROOT / "L2_builder" / "ssot_registry_consistency_check.py"),
            "--project-root",
            str(project_root),
        ]
        if _run_gate(registry_cmd, "ssot_registry_consistency", policy, args.verbose, project_root) != 0:
            return 2

        if not args.context_input or not args.context_target:
            _print_diags(
                [
                    Diagnostic(
                        code="E_L2_GATE_CONTEXT_PACK_REQUIRED",
                        message="context_input and context_target are required with --publish",
                        expected="--context-input + --context-target",
                        got="missing",
                        path=json_pointer("context"),
                    )
                ]
            )
            return 2
        if not isinstance(args.context_target, str) or not args.context_target.strip():
            _print_diags(
                [
                    Diagnostic(
                        code="E_L2_GATE_CONTEXT_TARGET_INVALID",
                        message="context_target must be non-empty string",
                        expected="@Node.<RELID>",
                        got=str(args.context_target),
                        path=json_pointer("context", "target"),
                    )
                ]
            )
            return 2
        context_input = resolve_path(project_root, args.context_input)
        try:
            ensure_inside(project_root, context_input, "E_L2_GATE_CONTEXT_OUTSIDE_PROJECT")
        except ValueError:
            _print_diags(
                [
                    Diagnostic(
                        code="E_L2_GATE_CONTEXT_OUTSIDE_PROJECT",
                        message="context_input must be under project_root",
                        expected="project_root/...",
                        got=str(context_input),
                        path=json_pointer("context", "input"),
                    )
                ]
            )
            return 2
        topo_root = (project_root / "sdsl2" / "topology").resolve()
        try:
            ensure_inside(topo_root, context_input, "E_L2_GATE_CONTEXT_NOT_SSOT")
        except ValueError:
            _print_diags(
                [
                    Diagnostic(
                        code="E_L2_GATE_CONTEXT_NOT_SSOT",
                        message="context_input must be under sdsl2/topology",
                        expected="sdsl2/topology/...",
                        got=str(context_input),
                        path=json_pointer("context", "input"),
                    )
                ]
            )
            return 2
        if context_input.is_symlink() or has_symlink_parent(context_input, project_root):
            _print_diags(
                [
                    Diagnostic(
                        code="E_L2_GATE_CONTEXT_INPUT_SYMLINK",
                        message="context_input must not be symlink",
                        expected="non-symlink",
                        got=str(context_input),
                        path=json_pointer("context", "input"),
                    )
                ]
            )
            return 2
        if not context_input.exists() or context_input.is_dir():
            _print_diags(
                [
                    Diagnostic(
                        code="E_L2_GATE_CONTEXT_INPUT_INVALID",
                        message="context_input must be an existing file",
                        expected="existing .sdsl2 file",
                        got=str(context_input),
                        path=json_pointer("context", "input"),
                    )
                ]
            )
            return 2
        if context_input.suffix != ".sdsl2":
            _print_diags(
                [
                    Diagnostic(
                        code="E_L2_GATE_CONTEXT_INPUT_INVALID",
                        message="context_input must be .sdsl2",
                        expected=".sdsl2",
                        got=str(context_input),
                        path=json_pointer("context", "input"),
                    )
                ]
            )
            return 2
        context_cmd = [
            py,
            str(ROOT / "L2_builder" / "context_pack_gen.py"),
            "--input",
            str(context_input),
            "--target",
            str(args.context_target),
            "--project-root",
            str(project_root),
        ]
        if args.context_hops is not None:
            context_cmd.extend(["--hops", str(args.context_hops)])
        if _run_gate(context_cmd, None, policy, args.verbose, project_root) != 0:
            return 2

        bundle_cmd = [
            py,
            str(ROOT / "L2_builder" / "bundle_doc_gen.py"),
            "--project-root",
            str(project_root),
        ]
        if _run_gate(bundle_cmd, None, policy, args.verbose, project_root) != 0:
            return 2

        skeleton_cmd = [
            py,
            str(ROOT / "L2_builder" / "implementation_skeleton_gen.py"),
            "--project-root",
            str(project_root),
        ]
        if _run_gate(skeleton_cmd, None, policy, args.verbose, project_root) != 0:
            return 2

        conformance_cmd = [
            py,
            str(ROOT / "L2_builder" / "conformance_check.py"),
            "--project-root",
            str(project_root),
        ]
        if _run_gate(conformance_cmd, None, policy, args.verbose, project_root) != 0:
            return 2

        freshness_cmd = [
            py,
            str(ROOT / "L2_builder" / "freshness_check.py"),
            "--project-root",
            str(project_root),
        ]
        if _run_gate(freshness_cmd, None, policy, args.verbose, project_root) != 0:
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

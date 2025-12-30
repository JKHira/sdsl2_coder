#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(cmd))
    return subprocess.run(cmd, capture_output=True, text=True)


def load_manifest(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"MANIFEST_NOT_FOUND: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"MANIFEST_INVALID_JSON: {exc}") from exc


def resolve_path(raw: str) -> Path:
    p = Path(raw)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p


def normalize_diags(diags: list[dict]) -> list[dict]:
    return sorted(
        diags,
        key=lambda d: (
            d.get("code", ""),
            d.get("path", ""),
            d.get("message", ""),
            d.get("expected", ""),
            d.get("got", ""),
        ),
    )


def load_diags_from_text(text: str) -> list[dict]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"DIAGNOSTICS_INVALID_JSON: {exc}") from exc
    if not isinstance(data, list):
        raise SystemExit("DIAGNOSTICS_NOT_LIST")
    return data


def load_diags_from_file(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"DIAGNOSTICS_GOLDEN_NOT_FOUND: {path}")
    return load_diags_from_text(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--manifest",
        default="tests/determinism_manifest.json",
        help="Path to determinism manifest JSON.",
    )
    ap.add_argument(
        "--allow-empty",
        action="store_true",
        help="Exit 0 when no cases are configured.",
    )
    args = ap.parse_args()

    manifest_path = resolve_path(args.manifest)
    manifest = load_manifest(manifest_path)
    cases = manifest.get("cases", [])
    if not isinstance(cases, list):
        raise SystemExit("MANIFEST_CASES_NOT_LIST")
    if not cases:
        print("No determinism cases configured.")
        return 0 if args.allow_empty else 2

    failures = 0
    py = sys.executable

    for case in cases:
        expect = case.get("expect")
        ledger = resolve_path(case.get("ledger", "")) if case.get("ledger") else None
        output = resolve_path(case.get("output", "")) if case.get("output") else None
        golden = resolve_path(case.get("golden", "")) if case.get("golden") else None
        input_path = resolve_path(case.get("input", "")) if case.get("input") else None
        contract_case = case.get("contract_case")

        if expect:
            phase = expect.get("phase", "run")
            expected_code = int(expect.get("exit_code", 2))
            diag_golden = expect.get("diagnostics_golden")
            if diag_golden:
                diag_golden = resolve_path(diag_golden)

            if phase == "contract":
                if not contract_case:
                    print("[FAIL] contract_case missing")
                    failures += 1
                    continue
                contract_res = run_cmd([py, "scripts/contract_builder_check.py", "--case", str(contract_case)])
                if contract_res.returncode != expected_code:
                    print(f"[FAIL] contract exit code {contract_res.returncode} != {expected_code}: {contract_case}")
                    if contract_res.stderr:
                        print(contract_res.stderr.strip())
                    failures += 1
                    continue
                if diag_golden:
                    got = normalize_diags(load_diags_from_text(contract_res.stderr))
                    expected = normalize_diags(load_diags_from_file(diag_golden))
                    if got != expected:
                        print(f"[FAIL] diagnostics mismatch: {contract_case}")
                        failures += 1
                        continue
                print(f"[OK] {contract_case} (expected failure)")
                continue

            if phase == "contract_success":
                if golden is None or not golden.exists():
                    print(f"[FAIL] golden not found: {golden}")
                    failures += 1
                    continue
                if not golden.is_file():
                    print(f"[FAIL] golden is not a file: {golden}")
                    failures += 1
                    continue

                case_name = str(contract_case) if contract_case else "FULL"
                first = run_cmd(
                    [
                        py,
                        "scripts/contract_golden_check.py",
                        "--emit-stdout",
                        "--case",
                        case_name,
                        "--golden",
                        str(golden),
                    ]
                )
                if first.returncode != 0:
                    print("[FAIL] contract success run failed")
                    if first.stderr:
                        print(first.stderr.strip())
                    failures += 1
                    continue

                second = run_cmd(
                    [
                        py,
                        "scripts/contract_golden_check.py",
                        "--emit-stdout",
                        "--case",
                        case_name,
                        "--golden",
                        str(golden),
                    ]
                )
                if second.returncode != 0:
                    print("[FAIL] contract success re-run failed")
                    if second.stderr:
                        print(second.stderr.strip())
                    failures += 1
                    continue

                first_hash = sha256_text(first.stdout)
                second_hash = sha256_text(second.stdout)
                if first_hash != second_hash:
                    print("[FAIL] contract output non-deterministic")
                    failures += 1
                    continue

                if first.stdout.encode("utf-8") != golden.read_bytes():
                    print(f"[FAIL] contract output differs from golden: {golden}")
                    failures += 1
                    continue
                print("[OK] contract golden (deterministic)")
                continue

            if phase == "lint":
                if input_path is None or not input_path.exists():
                    print(f"[FAIL] lint input not found: {input_path}")
                    failures += 1
                    continue
                lint_res = run_cmd([py, "-m", "sdslv2_builder.lint", "--input", str(input_path)])
                if lint_res.returncode != expected_code:
                    print(f"[FAIL] lint exit code {lint_res.returncode} != {expected_code}: {input_path}")
                    if lint_res.stderr:
                        print(lint_res.stderr.strip())
                    failures += 1
                    continue
                if diag_golden:
                    got = normalize_diags(load_diags_from_text(lint_res.stderr))
                    expected = normalize_diags(load_diags_from_file(diag_golden))
                    if got != expected:
                        print(f"[FAIL] diagnostics mismatch: {input_path}")
                        failures += 1
                        continue
                print(f"[OK] {input_path.name} (expected failure)")
                continue

            if ledger is None or not ledger.exists():
                print(f"[FAIL] ledger not found: {ledger}")
                failures += 1
                continue

            if output is not None and output.parent.exists():
                shutil.rmtree(output.parent)

            run_res = run_cmd([py, "-m", "sdslv2_builder.run", "--ledger", str(ledger), "--out-dir", "OUTPUT"])
            if phase == "run":
                if run_res.returncode != expected_code:
                    print(f"[FAIL] run exit code {run_res.returncode} != {expected_code}: {ledger}")
                    if run_res.stderr:
                        print(run_res.stderr.strip())
                    failures += 1
                    continue
                if diag_golden:
                    got = normalize_diags(load_diags_from_text(run_res.stderr))
                    expected = normalize_diags(load_diags_from_file(diag_golden))
                    if got != expected:
                        print(f"[FAIL] diagnostics mismatch: {ledger}")
                        failures += 1
                        continue
                print(f"[OK] {ledger.name} (expected failure)")
                continue

            if run_res.returncode != 0:
                print(f"[FAIL] run failed unexpectedly: {ledger}")
                if run_res.stderr:
                    print(run_res.stderr.strip())
                failures += 1
                continue

            lint_res = run_cmd([py, "-m", "sdslv2_builder.lint", "--input", "OUTPUT"])
            if lint_res.returncode != expected_code:
                print(f"[FAIL] lint exit code {lint_res.returncode} != {expected_code}: {ledger}")
                if lint_res.stderr:
                    print(lint_res.stderr.strip())
                failures += 1
                continue
            if diag_golden:
                got = normalize_diags(load_diags_from_text(lint_res.stderr))
                expected = normalize_diags(load_diags_from_file(diag_golden))
                if got != expected:
                    print(f"[FAIL] diagnostics mismatch: {ledger}")
                    failures += 1
                    continue
            print(f"[OK] {ledger.name} (expected failure)")
            continue

        if ledger is None or not ledger.exists():
            print(f"[FAIL] ledger not found: {ledger}")
            failures += 1
            continue
        if golden is None or not golden.exists():
            print(f"[FAIL] golden not found: {golden}")
            failures += 1
            continue
        if not golden.is_file():
            print(f"[FAIL] golden is not a file: {golden}")
            failures += 1
            continue

        if output is not None and output.parent.exists():
            shutil.rmtree(output.parent)

        run_res = run_cmd([py, "-m", "sdslv2_builder.run", "--ledger", str(ledger), "--out-dir", "OUTPUT"])
        if run_res.returncode != 0:
            print(f"[FAIL] run failed: {ledger}")
            if run_res.stderr:
                print(run_res.stderr.strip())
            failures += 1
            continue

        lint_res = run_cmd([py, "-m", "sdslv2_builder.lint", "--input", "OUTPUT"])
        if lint_res.returncode != 0:
            print(f"[FAIL] lint failed: {ledger}")
            if lint_res.stderr:
                print(lint_res.stderr.strip())
            failures += 1
            continue

        if output is None or not output.exists():
            print(f"[FAIL] output not found: {output}")
            failures += 1
            continue
        if not output.is_file():
            print(f"[FAIL] output is not a file: {output}")
            failures += 1
            continue

        first_hash = sha256_file(output)
        run_res = run_cmd([py, "-m", "sdslv2_builder.run", "--ledger", str(ledger), "--out-dir", "OUTPUT"])
        if run_res.returncode != 0:
            print(f"[FAIL] re-run failed: {ledger}")
            if run_res.stderr:
                print(run_res.stderr.strip())
            failures += 1
            continue
        second_hash = sha256_file(output)
        if first_hash != second_hash:
            print(f"[FAIL] non-deterministic output: {output}")
            failures += 1
            continue

        if output.read_bytes() != golden.read_bytes():
            print(f"[FAIL] output differs from golden: {output}")
            failures += 1
            continue

        print(f"[OK] {ledger.name}")

    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

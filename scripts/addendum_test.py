#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True)


def _canonical_json(text: str) -> str:
    text = text.strip()
    if text == "":
        data = []
    else:
        data = json.loads(text)
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True, help="Path to addendum manifest JSON.")
    ap.add_argument("--update", action="store_true", help="Update diagnostics golden files.")
    args = ap.parse_args()

    manifest = Path(args.manifest)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    version = data.get("version")
    if version != "addendum-manifest-v0.1":
        print(f"E_ADDENDUM_MANIFEST_VERSION: {version}", file=sys.stderr)
        return 2
    policy = data.get("policy")
    base = manifest.parent
    policy_path: Path | None = None
    if policy:
        policy_path = (base / policy).resolve()
        if not policy_path.exists():
            print(f"E_ADDENDUM_POLICY_NOT_FOUND: {policy_path}", file=sys.stderr)
            return 2
    cases = data.get("cases", [])
    if not isinstance(cases, list):
        print("E_ADDENDUM_MANIFEST_INVALID", file=sys.stderr)
        return 2

    for case in cases:
        input_path = case.get("input")
        expect = case.get("expect", {})
        if not isinstance(expect, dict):
            print("E_ADDENDUM_CASE_EXPECT_INVALID", file=sys.stderr)
            return 2
        exit_code = int(expect.get("exit_code", 0))
        golden = expect.get("diagnostics_golden")
        if not input_path:
            print("E_ADDENDUM_CASE_MISSING_INPUT", file=sys.stderr)
            return 2

        input_path = str((base / input_path).resolve())
        cmd = [sys.executable, str(ROOT / "scripts" / "addendum_check.py"), "--input", input_path]
        if policy_path:
            cmd += ["--policy-path", str(policy_path)]
        proc = _run(cmd)
        if proc.stdout.strip():
            print(f"[FAIL] unexpected stdout: {input_path}", file=sys.stderr)
            return 2

        if proc.returncode != exit_code:
            print(f"[FAIL] {input_path} exit_code {proc.returncode} != {exit_code}", file=sys.stderr)
            return 2

        stderr_text = proc.stderr.strip()
        if golden:
            golden_path = (base / golden).resolve()
            if args.update:
                golden_path.parent.mkdir(parents=True, exist_ok=True)
                golden_path.write_text(_canonical_json(stderr_text), encoding="utf-8")
                print(f"[OK] updated {golden_path}")
            else:
                if not golden_path.exists():
                    print(f"[FAIL] golden not found: {golden_path}", file=sys.stderr)
                    return 2
                expected = _canonical_json(golden_path.read_text(encoding="utf-8"))
                got = _canonical_json(stderr_text)
                if got != expected:
                    print(f"[FAIL] diagnostics differ: {golden_path}", file=sys.stderr)
                    print("[HINT] re-run with --update to refresh goldens", file=sys.stderr)
                    return 2
        else:
            if stderr_text:
                print(f"[FAIL] unexpected diagnostics: {input_path}", file=sys.stderr)
                return 2

    print("[OK] addendum manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

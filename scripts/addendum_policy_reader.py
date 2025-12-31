#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.addendum_policy import load_addendum_policy


FAIL_CODES = {
    "ADD_POLICY_MULTIPLE_FOUND",
    "ADD_POLICY_PARSE_FAILED",
    "ADD_POLICY_SCHEMA_INVALID",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy-path", default=None, help="Explicit policy path.")
    args = ap.parse_args()

    policy_path = Path(args.policy_path) if args.policy_path else None
    result = load_addendum_policy(policy_path, ROOT)

    if result.diagnostics:
        payload = [d.to_dict() for d in result.diagnostics]
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)

    print(json.dumps(result.policy, ensure_ascii=False, indent=2))

    if any(d.code in FAIL_CODES for d in result.diagnostics):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

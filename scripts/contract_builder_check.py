#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.contract import ContractBuilder
from sdslv2_builder.errors import BuilderError
from sdslv2_builder.refs import parse_internal_ref


def _emit_diag(err: BuilderError) -> None:
    payload = [err.diagnostic.to_dict()]
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


def case_fail_relid() -> None:
    builder = ContractBuilder()
    builder.file("bad")  # RELID violation


def case_fail_rule_bind_missing() -> None:
    builder = ContractBuilder()
    builder.file("P0_C_FAIL_RULE")
    builder.rule("RULE_MISSING_BIND", bind=None)


def case_fail_dep_to_invalid() -> None:
    builder = ContractBuilder()
    builder.file("P0_C_FAIL_DEP")
    from_ref = parse_internal_ref("@Structure.AAA")
    if from_ref is None:
        raise RuntimeError("INTERNAL_REF_PARSE_FAILED")
    builder.dep(from_ref=from_ref, to="BAD_TOKEN")


def case_fail_refs_not_internal() -> None:
    builder = ContractBuilder()
    builder.file("P0_C_FAIL_REFS")
    builder.structure("BASIC", decl="struct Basic {}\n", refs=["NOT_A_REF"])


def case_fail_contract_not_contractref() -> None:
    builder = ContractBuilder()
    builder.file("P0_C_FAIL_CONTRACT")
    builder.structure("BASIC", decl="struct Basic {}\n", contract=["BAD_TOKEN"])


def case_fail_ssot_not_ssotref() -> None:
    builder = ContractBuilder()
    builder.file("P0_C_FAIL_SSOT")
    builder.structure("BASIC", decl="struct Basic {}\n", ssot=["BAD_TOKEN"])


def case_fail_kind_forbidden() -> None:
    from sdslv2_builder.contract import Decl

    builder = ContractBuilder()
    builder.file("P0_C_FAIL_KIND")
    builder._decls.append(
        Decl(
            kind="Node",
            rel_id="BAD_NODE",
            decl="struct Bad {}\n",
            bind=None,
            title=None,
            desc=None,
            refs=[],
            contract=[],
            ssot=[],
        )
    )
    builder.build()


CASES = {
    "FAIL_RELID": case_fail_relid,
    "FAIL_RULE_BIND_MISSING": case_fail_rule_bind_missing,
    "FAIL_DEP_TO_INVALID": case_fail_dep_to_invalid,
    "FAIL_REFS_NOT_INTERNAL": case_fail_refs_not_internal,
    "FAIL_CONTRACT_NOT_CONTRACTREF": case_fail_contract_not_contractref,
    "FAIL_SSOT_NOT_SSOTREF": case_fail_ssot_not_ssotref,
    "FAIL_KIND_FORBIDDEN": case_fail_kind_forbidden,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True, help="Failure case name.")
    args = ap.parse_args()

    handler = CASES.get(args.case)
    if handler is None:
        print(f"UNKNOWN_CASE: {args.case}", file=sys.stderr)
        return 2

    try:
        handler()
    except BuilderError as err:
        _emit_diag(err)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

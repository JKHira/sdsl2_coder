#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdslv2_builder.contract import ContractBuilder
from sdslv2_builder.contract_writer import write_contract
from sdslv2_builder.refs import parse_contract_ref, parse_internal_ref, parse_ssot_ref


def _must_ref(value, label: str):
    if value is None:
        raise RuntimeError(f"REF_PARSE_FAILED: {label}")
    return value


def build_full() -> str:
    builder = ContractBuilder()
    builder.file("P0_C_FULL")
    builder.doc_meta(
        "DOCMETA",
        title="Full Contract",
        desc="All metadata fields present",
        refs=[_must_ref(parse_internal_ref("@Structure.COMMAND"), "DOCMETA_REF")],
        ssot=[_must_ref(parse_ssot_ref("SSOT.SpecSheet"), "DOCMETA_SSOT")],
    )
    builder.structure(
        "COMMAND",
        decl="struct Command {\n  id: s\n}\n",
        bind=_must_ref(parse_internal_ref("@Interface.CONTROL"), "STRUCT_BIND"),
        title="Command Payload",
        desc="Control command definition",
        refs=[_must_ref(parse_internal_ref("@Type.STATUS"), "STRUCT_REF")],
        contract=[_must_ref(parse_contract_ref("CONTRACT.CommandSpec"), "STRUCT_CONTRACT")],
        ssot=[_must_ref(parse_ssot_ref("SSOT.StructureDoc"), "STRUCT_SSOT")],
    )
    builder.interface(
        "CONTROL",
        decl="interface Control {}\n",
        title="Control API",
        desc="Control boundary",
        refs=[_must_ref(parse_internal_ref("@Structure.COMMAND"), "IF_REF")],
        contract=[_must_ref(parse_contract_ref("CONTRACT.ControlSpec"), "IF_CONTRACT")],
        ssot=[_must_ref(parse_ssot_ref("SSOT.InterfaceDoc"), "IF_SSOT")],
    )
    builder.function(
        "SEND_COMMAND",
        decl="f send(Command): Command\n",
        bind=_must_ref(parse_internal_ref("@Interface.CONTROL"), "FUNC_BIND"),
        title="Send Command",
        desc="Dispatch command to control plane",
        refs=[_must_ref(parse_internal_ref("@Structure.COMMAND"), "FUNC_REF")],
    )
    builder.const(
        "RETRY_MAX",
        decl="const RETRY_MAX = 3\n",
        title="Retry Limit",
    )
    builder.type_alias(
        "STATUS",
        decl='type STATUS = "OK"|"NG"\n',
        desc="Command status",
    )
    builder.dep(
        from_ref=_must_ref(parse_internal_ref("@Structure.COMMAND"), "DEP_FROM"),
        to=_must_ref(parse_contract_ref("CONTRACT.ExternalSpec"), "DEP_TO"),
        ssot=[_must_ref(parse_ssot_ref("SSOT.DependencyDoc"), "DEP_SSOT")],
    )
    builder.rule(
        "RULE_COMMAND",
        bind=_must_ref(parse_internal_ref("@Structure.COMMAND"), "RULE_BIND"),
        refs=[_must_ref(parse_internal_ref("@Interface.CONTROL"), "RULE_REF")],
        contract=[_must_ref(parse_contract_ref("CONTRACT.RuleSpec"), "RULE_CONTRACT")],
        ssot=[_must_ref(parse_ssot_ref("SSOT.RuleDoc"), "RULE_SSOT")],
    )
    return write_contract(builder.build())


def build_minimal() -> str:
    builder = ContractBuilder()
    builder.file("P0_C_MIN")
    builder.structure("BASIC", decl="struct Basic {}\n")
    return write_contract(builder.build())


def build_escape() -> str:
    builder = ContractBuilder()
    builder.file("P0_C_ESCAPE")
    builder.doc_meta(
        "DOCMETA",
        title='Quote "Q"',
        desc="Path C:\\Temp\\file",
    )
    builder.structure(
        "ESCAPE",
        decl="struct Escape {\n  note: s\n}\n",
        title='Title "T"',
        desc="Slash \\\\ and quote \"",
    )
    return write_contract(builder.build())


def build_ordering() -> str:
    builder = ContractBuilder()
    builder.file("P0_C_ORDER")
    builder.function("ZETA", decl="f zeta(): s\n")
    builder.const("GAMMA", decl="const GAMMA = 1\n")
    builder.interface("BETA", decl="interface Beta {}\n")
    builder.type_alias("OMEGA", decl='type OMEGA = "A"|"B"\n')
    builder.structure("B_STRUCT", decl="struct BStruct {}\n")
    builder.structure("A_STRUCT", decl="struct AStruct {}\n")
    return write_contract(builder.build())


def build_p3_schema_validation_excerpt() -> str:
    builder = ContractBuilder()
    builder.file("P3_SCHEMA_VALIDATION")
    builder.structure(
        "P3_C_VRTD_VERSIONED_REFERENCE",
        decl="struct VersionedReference { name:s, version:s? }\n",
    )
    builder.structure(
        "P3_C_VEB_VALIDATION_RESULT",
        decl="struct ValidationResult { valid:b, skip_reason:s?, error_code:s?, state_transition:s? }\n",
    )
    builder.const(
        "P3_C_MTRT_RELOAD_CHANNEL_CONST",
        decl='const RELOAD_CHANNEL = "master:reload"\n',
    )
    builder.rule(
        "P3_C_VEB_ERROR_CODE",
        bind=_must_ref(parse_internal_ref("@Structure.P3_C_VEB_VALIDATION_RESULT"), "RULE_BIND"),
        contract=[_must_ref(parse_contract_ref("CONTRACT.ErrorCode"), "RULE_CONTRACT")],
        ssot=[_must_ref(parse_ssot_ref("SSOT.ValidationErrors"), "RULE_SSOT")],
    )
    return write_contract(builder.build())


def build_p5_execution_message_excerpt() -> str:
    builder = ContractBuilder()
    builder.file("P5_EXECUTION_MESSAGE")

    builder.structure(
        "P5_C_PCC_EMIDL_ID_MODEL_OUTPUT_ID",
        decl="struct ModelOutputId { value: UUID }\n",
    )
    builder.structure(
        "P5_C_PCC_EMIDL_ID_SIGNAL_ID",
        decl="struct SignalId { value: UUID }\n",
    )
    builder.structure(
        "P5_C_PCC_EMIDL_ID_INTENT_ID",
        decl="struct IntentId { value: UUID }\n",
    )
    builder.structure(
        "P5_C_PCC_EMIDL_ID_CLORD_ID",
        decl="struct ClOrdId { value: UUID }\n",
    )
    builder.structure(
        "P5_C_PCC_EMIDL_ID_VENUE_ORDER_ID",
        decl="struct VenueOrderId { value: s }\n",
    )
    builder.structure(
        "P5_C_PCC_EMIDL_ID_TRADE_ID",
        decl="struct TradeId { value: s }\n",
    )

    builder.structure(
        "P5_C_MSEP_EMIDL_L5_STRATEGY_SIGNAL",
        decl=(
            "struct StrategySignal {\n"
            "  signal_id: SignalId,\n"
            "  model_output_id: ModelOutputId?,\n"
            "  instrument_id: s,\n"
            "  direction: \"BUY\"|\"SELL\",\n"
            "  timestamp_ns: i64,\n"
            "}\n"
        ),
    )
    builder.structure(
        "P5_C_BMOM_EMIDL_BM_EXECUTION_INTENT",
        decl=(
            "struct ExecutionIntent {\n"
            "  intent_id: IntentId,\n"
            "  signal_id: SignalId,\n"
            "  instrument_id: s,\n"
            "  side: \"BUY\"|\"SELL\",\n"
            "  quantity: Decimal,\n"
            "  timestamp_ns: i64,\n"
            "}\n"
        ),
    )

    builder.structure(
        "P5_C_MOMEA_EMIDL_L6_ORDER_SUBMIT_REQUEST",
        decl=(
            "struct OrderSubmitRequest {\n"
            "  client_order_id: ClOrdId,\n"
            "  signal_id: SignalId,\n"
            "  instrument_id: s,\n"
            "  side: \"BUY\"|\"SELL\",\n"
            "  quantity: Decimal,\n"
            "  timestamp_ns: i64,\n"
            "}\n"
        ),
    )
    builder.structure(
        "P5_C_MOMEA_EMIDL_L6_ORDER_ACCEPTED",
        decl=(
            "struct OrderAccepted {\n"
            "  client_order_id: ClOrdId,\n"
            "  venue_order_id: VenueOrderId,\n"
            "  accepted_at_ns: i64,\n"
            "}\n"
        ),
    )
    builder.structure(
        "P5_C_MOMEA_EMIDL_L6_ORDER_REJECTED",
        decl=(
            "struct OrderRejected {\n"
            "  client_order_id: ClOrdId,\n"
            "  reason: s,\n"
            "  error_code: s?,\n"
            "  rejected_at_ns: i64,\n"
            "}\n"
        ),
    )
    builder.structure(
        "P5_C_MOMEA_EMIDL_L6_ORDER_FILLED",
        decl=(
            "struct OrderFilled {\n"
            "  client_order_id: ClOrdId,\n"
            "  venue_order_id: VenueOrderId,\n"
            "  trade_id: TradeId,\n"
            "  fill_price: Decimal,\n"
            "  fill_quantity: Decimal,\n"
            "  remaining_quantity: Decimal,\n"
            "  is_fully_filled: b,\n"
            "  filled_at_ns: i64,\n"
            "}\n"
        ),
    )
    builder.rule(
        "P5_C_PCC_CLORDID_L6",
        bind=_must_ref(
            parse_internal_ref("@Structure.P5_C_PCC_EMIDL_ID_INTENT_ID"),
            "RULE_BIND",
        ),
        refs=[
            _must_ref(
                parse_internal_ref("@Structure.P5_C_PCC_EMIDL_ID_CLORD_ID"),
                "RULE_REF",
            )
        ],
    )
    builder.rule(
        "P5_C_BMOM_LINK_SIGNAL",
        bind=_must_ref(
            parse_internal_ref("@Structure.P5_C_PCC_EMIDL_ID_SIGNAL_ID"),
            "RULE_BIND",
        ),
    )
    builder.rule(
        "P5_C_RIR_RETRY_MAX",
        bind=_must_ref(
            parse_internal_ref("@Structure.P5_C_PCC_EMIDL_ID_SIGNAL_ID"),
            "RULE_BIND",
        ),
        contract=[_must_ref(parse_contract_ref("CONTRACT.RetryLimit"), "RULE_CONTRACT")],
    )
    builder.rule(
        "P5_C_SSK_REDIS_ORDERS",
        bind=_must_ref(
            parse_internal_ref("@Structure.P5_C_PCC_EMIDL_ID_CLORD_ID"),
            "RULE_BIND",
        ),
        ssot=[_must_ref(parse_ssot_ref("SSOT.RedisKeyCatalog"), "RULE_SSOT")],
    )
    builder.rule(
        "P5_C_MOMEA_CLORDID_MAP",
        bind=_must_ref(
            parse_internal_ref("@Structure.P5_C_MOMEA_EMIDL_L6_ORDER_SUBMIT_REQUEST"),
            "RULE_BIND",
        ),
        refs=[
            _must_ref(
                parse_internal_ref("@Structure.P5_C_PCC_EMIDL_ID_CLORD_ID"),
                "RULE_REF_CLORD",
            ),
            _must_ref(
                parse_internal_ref("@Structure.P5_C_PCC_EMIDL_ID_INTENT_ID"),
                "RULE_REF_INTENT",
            ),
        ],
    )
    builder.rule(
        "P5_C_MOMEA_TOPIC_EXECUTION_ORDERS_SUBMIT",
        bind=_must_ref(
            parse_internal_ref("@Structure.P5_C_MOMEA_EMIDL_L6_ORDER_SUBMIT_REQUEST"),
            "RULE_BIND",
        ),
        refs=[
            _must_ref(
                parse_internal_ref("@Structure.P5_C_MOMEA_EMIDL_L6_ORDER_SUBMIT_REQUEST"),
                "RULE_REF",
            )
        ],
    )
    builder.rule(
        "P5_C_MOMEA_TOPIC_EXECUTION_ORDERS_STATE",
        bind=_must_ref(
            parse_internal_ref("@Structure.P5_C_MOMEA_EMIDL_L6_ORDER_ACCEPTED"),
            "RULE_BIND",
        ),
        refs=[
            _must_ref(
                parse_internal_ref("@Structure.P5_C_MOMEA_EMIDL_L6_ORDER_ACCEPTED"),
                "RULE_REF_A",
            ),
            _must_ref(
                parse_internal_ref("@Structure.P5_C_MOMEA_EMIDL_L6_ORDER_REJECTED"),
                "RULE_REF_R",
            ),
            _must_ref(
                parse_internal_ref("@Structure.P5_C_MOMEA_EMIDL_L6_ORDER_FILLED"),
                "RULE_REF_F",
            ),
        ],
    )
    builder.rule(
        "P5_C_MSEP_TOPIC_STRATEGY_SIGNALS",
        bind=_must_ref(
            parse_internal_ref("@Structure.P5_C_MSEP_EMIDL_L5_STRATEGY_SIGNAL"),
            "RULE_BIND",
        ),
    )
    builder.rule(
        "P5_C_BMOM_TOPIC_EXECUTION_INTENTS",
        bind=_must_ref(
            parse_internal_ref("@Structure.P5_C_BMOM_EMIDL_BM_EXECUTION_INTENT"),
            "RULE_BIND",
        ),
    )
    return write_contract(builder.build())


CASES = {
    "FULL": build_full,
    "MIN": build_minimal,
    "ESCAPE": build_escape,
    "ORDERING": build_ordering,
    "P3_SCHEMA_VALIDATION_EXCERPT": build_p3_schema_validation_excerpt,
    "P5_EXECUTION_MESSAGE_EXCERPT": build_p5_execution_message_excerpt,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true", help="Update golden file.")
    ap.add_argument("--emit-stdout", action="store_true", help="Emit contract output to stdout.")
    ap.add_argument("--case", default="FULL", help="Contract case name.")
    ap.add_argument(
        "--golden",
        default="tests/goldens/P0_C_FULL/contract.sdsl2",
        help="Path to golden file.",
    )
    args = ap.parse_args()

    builder = CASES.get(args.case)
    if builder is None:
        print(f"UNKNOWN_CASE: {args.case}")
        return 2
    output = builder()
    golden_path = Path(args.golden)

    if args.emit_stdout:
        sys.stdout.write(output)
        return 0

    if args.update:
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(output, encoding="utf-8")
        print(f"[OK] updated {golden_path}")
        return 0

    if not golden_path.exists():
        print(f"[FAIL] golden not found: {golden_path}")
        return 2
    expected = golden_path.read_text(encoding="utf-8")
    if output != expected:
        print(f"[FAIL] contract output differs: {golden_path}")
        return 2
    print("[OK] contract golden")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .errors import Diagnostic
from .ledger import load_ledger, validate_ledger
from .topology import build_topology_model
from .writer import write_topology


def _print_diagnostics(diags: list[Diagnostic]) -> None:
    payload = [d.to_dict() for d in diags]
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


def _ensure_output_root(path: Path) -> Path:
    root = path.resolve()
    if root.name != "OUTPUT":
        raise SystemExit("E_OUTPUT_DIR_INVALID: out-dir must be OUTPUT")
    root.mkdir(parents=True, exist_ok=True)
    return root


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", required=True, help="Path to topology ledger (v0.1).")
    ap.add_argument("--out-dir", required=True, help="Output directory (must be OUTPUT).")
    args = ap.parse_args()

    ledger_path = Path(args.ledger)
    if not ledger_path.exists():
        print(f"E_LEDGER_NOT_FOUND: {ledger_path}", file=sys.stderr)
        return 2

    output_root = _ensure_output_root(Path(args.out_dir))
    data = load_ledger(ledger_path)
    topology_input, diagnostics = validate_ledger(data, output_root)
    if diagnostics:
        _print_diagnostics(diagnostics)
        return 2
    if topology_input is None:
        print("E_LEDGER_SCHEMA_INVALID: no topology input", file=sys.stderr)
        return 2

    model = build_topology_model(topology_input)
    text = write_topology(model)

    output_path = topology_input.output_path
    if output_path is None:
        output_path = output_root / topology_input.id_prefix / "topology.sdsl2"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

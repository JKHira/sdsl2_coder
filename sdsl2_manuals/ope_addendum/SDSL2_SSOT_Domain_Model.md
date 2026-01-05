# SDSL2 and TS SSOT Kernel Domain Model

Scope: Define SSOT domain boundaries and integration rules.
Non-scope: Grammar/semantics changes; TS implementation details.

## Definitions
- Authority/precedence: Manual is SSOT for syntax/semantics; this spec adds integration rules; Manual wins on conflict.
- TS SSOT Kernel Definitions: Const data, types, enums, interfaces.
- TS SSOT Kernel Runtime: Runtime functions, guards, builders, validation helpers.
- SDSL2 Contract: Boundary schemas/APIs/invariants.
- SDSL2 Topology: Graph Facts (see Manual 9.4).
- SSOTRef: "SSOT.*" token used in ssot:[...] (see Manual 9.3).
- Distribution Boundary: Neutral JSON derived from TS Definitions.
- Registry: Explicit list of SSOTRef tokens and targets.
- Contract Registry: Explicit list/allowlist of CONTRACT.* tokens.

## Rules
- Domain authority is per domain; each domain is primary for its own content.
- TS Definitions MUST contain only const data/types/enums/interfaces.
- TS Runtime MUST contain only runtime functions/guards/builders/validation helpers.
- TS Definitions/Runtime MUST NOT contain Topology Graph Facts.
- SDSL2 Contract MUST NOT duplicate TS tables/constants; it is authoritative for boundary schemas/invariants only.
- SDSL2 Topology MUST be the only source of Graph Facts (see Manual 9.4).
- Cross-language boundary requirements MUST be declared in SDSL2 Contract rules/invariants and enforced at service/protocol boundaries; internal TS helpers are exempt.
- TS Definitions MUST emit Distribution Boundary JSON at OUTPUT/ssot/ssot_definitions.json.
- Registry MUST be emitted at OUTPUT/ssot/ssot_registry.json and be deterministic (UTF-8, LF, stable key/array order).
- Non-TS consumers MUST use the Distribution Boundary and MUST NOT import TS sources.
- TS source import includes ssot_definitions.ts/ssot_runtime.ts at build/runtime or vendoring TS sources; allowed: OUTPUT/ssot/ssot_definitions.json or generated bindings.
- SDSL2 MAY reference TS Definitions only via ssot:["SSOT.*"] tokens.
- Each SSOTRef token used by SDSL2 MUST exist in Registry.
- Each CONTRACT.* token used by SDSL2 MUST exist in Contract Registry or allowlist.
- SSOTRef tokens MUST be explicit in Registry and MUST NOT be derived from TS symbol names.
- Registry entries MUST include token and target; MAY include kind/since/deprecated.
- Registry target MUST use <path>#/<json_pointer> format.
- TS SSOT Kernel MUST NOT depend on SDSL2 artifacts.
- ssot_definitions.json and ssot_registry.json MUST include top-level source_rev and schema_version.

## CI Gates (Normative)
- SSOT-DIST: Canonical JSON determinism (UTF-8, LF, stable key/array order, no insignificant whitespace); mismatch FAIL.
- SSOT-CONSUME: Non-TS consumers use JSON only; TS source import FAIL.
- SDSL-SSOT-REF: SDSL2 ssot tokens must exist in Registry; missing token FAIL.
- DRIFT-SSOTREF-USAGE: Registry token unused in SDSL2 -> DIAG (evaluated over all parsed SDSL2 files).

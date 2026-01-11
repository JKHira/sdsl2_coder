# SSOT Kernel Builder

Scope: Build SSOT kernel distribution boundary JSON and registry map from ssot_definitions.ts.
Non-scope: TypeScript compilation, runtime codegen, or SDSL2 parsing.

## Inputs
- ssot_kernel_builder/ssot_definitions.ts
- ssot_kernel_builder/ssot_runtime.ts (runtime only; not used by builder)

## Outputs
- OUTPUT/ssot/ssot_definitions.json
- OUTPUT/ssot/ssot_registry_map.json

## Usage
- Build definitions + registry map:
  python3 ssot_kernel_builder/build_ssot_definitions.py --project-root /repo

- Generate registries:
  python3 L2_builder/token_registry_gen.py --project-root /repo

- L2 checks:
  python3 L2_builder/ssot_kernel_lint.py --project-root /repo
  python3 L2_builder/ssot_registry_consistency_check.py --project-root /repo

## Constraints
- ssot_definitions.ts MUST contain a JSON-compatible SSOT_DEFINITIONS object (double quotes, no trailing commas).
- Outputs are written only under OUTPUT/ssot and must not be symlinks.
- ssot_definitions.json must be canonical JSON (sorted keys, LF, trailing newline).

# SDSL2 Input Hash Specification

Scope: Define input_hash format, normalization, and base input set.
Non-scope: Tool implementation beyond normalization.

## Definitions
- input_hash: Deterministic digest string for an input set.
- Input Set: Ordered list of input files used to produce an artifact.
- content_hash: sha256 digest of normalized file content.

## Rules
- input_hash MUST be formatted as "sha256:<hex>" with lowercase hex.
- File paths MUST be repo-relative and use "/" separators.
- File content MUST be UTF-8 and LF-normalized. Whitespace MUST NOT be trimmed.
- Whitespace-only changes MUST affect input_hash.
- input_hash normalization is distinct from Evidence content_hash normalization; implementations MUST NOT apply trimming rules from SDSL2_Decision_Evidence_Spec.md.
- Input Set MUST be sorted lexically by normalized path.
- For each input file, content_hash MUST be computed over normalized content using sha256.
- input_hash MUST be computed over the concatenation of entries: "<path>\\n<content_hash>\\n" in input order.

### Base Input Set (Closed)
- SSOT files defined by SDSL2_SSOT_File_Layout_Spec.md.
- SSOT files MUST be enumerated using the same glob rules and lexical path order as CI parse order.
- Explicit Inputs defined by SDSL2_Decisions_Spec.md.
- Policy files MUST NOT be included unless explicitly required by the producing spec.
- Draft Artifacts and Intent YAML MUST use SSOT files only (Explicit Inputs excluded).

### Extensions
- A producing spec MAY declare additional inputs; those inputs MUST be included in input_hash.
- If no additional inputs are declared, the Base Input Set applies.
- For CI status artifacts, producing specs SHOULD include .sdsl/policy.yaml and policy/exceptions.yaml.

### Failure
- Missing files in the Input Set MUST FAIL.
- Symlinks in the Input Set MUST FAIL (see SDSL2_SSOT_File_Layout_Spec.md).

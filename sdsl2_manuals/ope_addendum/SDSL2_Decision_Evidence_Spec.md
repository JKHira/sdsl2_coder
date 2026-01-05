# SDSL2 Decision Evidence Specification

Scope: Define non-SSOT Evidence Map artifacts for decisions.
Non-scope: Grammar/semantics changes; Promote or Drift inputs.

## Definitions
- Evidence Map: decisions/evidence.yaml mapping decision_id to Evidence Item list.
- Evidence Item: A structured reference to a source location plus claims.
- Claim: A normalized statement describing what an Evidence Item supports.
- Schema Version: Evidence schema version in MAJOR.MINOR form.

## Rules
- Evidence Map MUST be stored at decisions/evidence.yaml.
- Evidence Map is non-SSOT and MUST NOT be used by Promote or Drift.
- Evidence Map MUST follow Common Operational YAML Conventions (SDSLv2_Manual_Addendum_Core.md).
- schema_version MUST be non-empty MAJOR.MINOR; readers accept same MAJOR only.
- MINOR compatibility MUST be additive optional fields only; no meaning change.
- MAJOR mismatch is incompatible; any allowance is via SCHEMA-MIGRATION gate.
- input_hash MUST follow SDSL2_InputHash_Spec.md.

### Evidence Map Top-Level Schema (Closed Set)
- Top-level keys in order: schema_version, source_rev, input_hash, scope, evidence.
- scope MUST follow decisions/edges.yaml scope rules (see SDSL2_Decisions_Spec.md).
- scope MUST match decisions/edges.yaml scope for the same decision set.
- Placeholders (None/TBD/Opaque) are forbidden.

### evidence
- evidence MUST be a map from decision_id to evidence item list.
- decision_id MUST be a key that exists in decisions/edges.yaml.
- decision_id MUST be unique in decisions/edges.yaml (see SDSL2_Decisions_Spec.md).
- evidence map keys MUST be sorted lexically.
- Evidence item lists MUST be stable-ordered and de-duplicated.

### Evidence Item
- Evidence Item MUST be a map with keys: source_path, locator, content_hash, note, claims.
- note MAY be omitted; if present it MUST be a string.
- source_path MUST be a normalized repo-relative path (no URLs).
- source_path MUST start with: design/ | docs/ | specs/ | src/ | policy/attestations/.
- source_path MUST NOT be under drafts/, OUTPUT/, sdsl2/, decisions/.
- locator MUST be one of:
  - L<start>-L<end>
  - H:<heading>#L<start>-L<end>
- locator SHOULD include a disambiguator (heading path).
- Locator line numbers MUST be based on LF-normalized text; a trailing newline counts as an empty line.
- content_hash MUST be algorithm-prefixed (example: sha256:<hex>).
- Hash normalization MUST use LF and trim trailing whitespace before hashing.

### claims
- claims MUST be a non-empty list with stable order.
- claims stable order MUST be (kind, decision_id, value) with kind order edge before contract_ref.
- Claim MUST be a map with keys: kind, decision_id, value.
- claim.kind MUST be a string and one of: "edge" | "contract_ref".
- claim.decision_id MUST be present for all claim kinds.
- claim.value MUST be present for kind:contract_ref.
- claim.value MUST be a "CONTRACT.*" token.

### Coverage Rules
- Each contract_refs token in decisions/edges.yaml MUST have at least one claim with kind:contract_ref and matching value.
- Evidence coverage is enforced by READINESS-CHECK and EVIDENCE-COVERAGE (see SDSL2_CI_Gates_Spec.md).

### Evidence Quality
- Evidence validity MUST be checked against current repo state using locator + content_hash.
- Periodic review or sampling SHOULD be required by policy.
- Attestation-only evidence MUST be represented as an Evidence Item whose source_path is under policy/attestations/.

### Evidence Repair
- evidence-repair MUST be proposal-only with unified diff output (no auto-apply in CI).
- evidence-repair MUST fail when multiple candidates exist for a single Evidence Item.

## Example (Non-normative)
```yaml
# decisions/evidence.yaml
schema_version: "1.0"
source_rev: "abc123"
input_hash: "deadbeef"
scope:
  kind: "file"
  value: "sdsl2/topology/example.sdsl2"
evidence:
  CTRL_TO_EXEC:
    - source_path: "design/edges.md"
      locator: "H:Control Path#L10-L20"
      content_hash: "sha256:0123abcd"
      claims:
        - kind: "edge"
          decision_id: "CTRL_TO_EXEC"
        - kind: "contract_ref"
          decision_id: "CTRL_TO_EXEC"
          value: "CONTRACT.SignedControlCommand"
```

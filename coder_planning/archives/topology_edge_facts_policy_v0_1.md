# Topology Edge Facts Policy v0.1

Goal:
- Add edges without inference.
- Keep decisions reproducible and reviewable.

## Allowed evidence (OK)
- A single @Rule line explicitly enumerates two or more @Structure/@Function items.
- The body explicitly shows interaction (call/publish/subscribe/read/write).

## Disallowed evidence (NG)
- "Likely" or implied relationships not stated in the text.
- Generalizing Rule-to-Edge without explicit evidence.

## Evidence handling
- Do not add evidence fields to the ledger (unknown keys are rejected).
- Use a separate notes file per case and reference it from source.evidence_note.

## Direction mapping (Closed Set only)
- call: explicit method/function call.
- pub/sub: explicit publish/subscribe.
- req/rep: explicit request/response.
- rw: explicit state read/write (DB/Redis get/set/xadd).

## contract_refs selection
- Use CONTRACT.* tokens explicitly present in the evidence line.
- If no CONTRACT.* is present, do not create the edge.

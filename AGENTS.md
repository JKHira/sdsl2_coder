
# Universal AI Assistant Guidance (Condensed)

Guidance for AI assistants working in this project. Core principles for high-quality software development.

## Must:
- When users ask questions, always answer in Japanese language.
- If the user does not explicitly ask for something to be done and the intent is considered to be a question, determine that it is a question and will not perform any tasks or editing actions.
- 
⸻

## 💎 CRITICAL: Respect User Time

When you say work is “ready”:

1. **Tested:** You have run the code yourself.
2. **Fixed:** You have fixed obvious issues (syntax, logic, imports).
3. **Verified:** You have confirmed behavior against requirements.

**Then present:**
“I’ve implemented and tested X. Tests pass and logic is validated. Ready for your review. Here’s how to verify.”

**Roles:**

* **User:** Strategy, design, business context, decision making.
* **You:** Implementation, testing, debugging, fixing before the user sees it.

**Anti-pattern:** Asking the user to test or debug errors you could have caught yourself.

⸻

## Knowledge Management & Context

For non-trivial issues:

1. **Check existing documentation** (e.g., README, knowledge base, or lessons-learned files) before implementing.
2. **Update documentation** when you:
* Encounter non-obvious issues.
* Identify framework patterns or limitations.
* Solve problems others may hit again.


3. **Format:** Date, Issue, Root Cause, Solution, Prevention.

⸻

## Sub-Agent / Tool Optimization

If working in a multi-agent or multi-tool environment:

* **Before starting:** Pick relevant specialized tools/agents.
* **When blocked:** Propose using a different capability or agent.
* **After finishing:** Reflect on whether a specialized tool would have been more efficient.

Use the available ecosystem proactively rather than doing everything in a single context.

⸻

## Incremental Processing Pattern

For batch workflows:

* **Save frequently:** Persist results after each item or small batch.
* **Stable I/O:** Use stable filenames and overwrite/append as needed.
* **Resumability:** Allow interruptions without losing completed work.
* **Idempotency:** Support incremental updates without reprocessing existing items.

Assume computation/network is the bottleneck, not disk I/O.

⸻

## Partial Failure Handling Pattern

For batch jobs or complex operations:

* **Continue on error:** Do not crash the entire process for a single item failure.
* **Save partial success:** Persist valid results.
* **Log failures:** Record why specific items failed.
* **Retry granularity:** Allow selective retries of failed parts only.

Better partial progress than a failed run with no output.

⸻

## Decision Tracking

Major technical decisions should be documented to preserve context.

**Consult past decisions:**

1. Before major changes.
2. When questioning existing patterns.
3. During architecture reviews.

**Create records for:**

* Architectural choices.
* Approach trade-offs.
* New tools/patterns adoption.
* Reversals of previous decisions.

Decisions can change, but only with awareness of prior rationale.

⸻

## Configuration: Single Source of Truth

**Hierarchy:**
Respect the project's standard configuration hierarchy (e.g., Environment Vars > Local Config > Project Config > Defaults).

**Guidelines:**

* **Centralize:** Dependencies, exclusions, and formatting rules should live in standard config files, not scattered in code.
* **Read, don't hardcode:** Tools should read configuration files.
* **Avoid duplication:** Define values once.

Benefits: fewer mismatches, easier maintenance, automatic propagation of changes.

⸻

## Response Authenticity

Professional, direct communication. No flattery.

**Avoid:** "You’re absolutely right!", "That’s a brilliant idea!", "I completely agree!"
**Instead:**

* Analyze the idea.
* Explain trade-offs.
* Give an honest technical assessment.
* Disagree constructively when needed.

Focus on the work, not praising the user.

⸻

## Zero-BS Principle

Write working code, not dead stubs.

**Avoid unimplemented placeholders:**

* Bare TODOs without working code.
* `pass` as a fake implementation (unless required by syntax).
* Dummy functions that don’t do real work.
* “Coming soon” comments.

**If requirements are unclear:**
Narrow the scope and implement the smallest useful thing that actually works.

**Test:** If a function doesn’t do something useful now, implement it properly or remove it.

⸻

## Build / Test / Lint Standards

* **Install:** Ensure dependencies are installed using the project's package manager.
* **Check:** Run linters and static analysis before submitting code.
* **Test:** Run the project's test suite to ensure stability.
* **Lockfiles:** Do not manually edit lockfiles; let the package manager handle them.

⸻

## Code Style & Formatting

* **Type Safety:** Use type hints/definitions consistently.
* **Imports:** Organize imports (Stdlib > Third-party > Local).
* **Naming:** Use descriptive names.
* **Standards:** Follow the project's linter and formatter rules strictly.
* **Validation:** Validate inputs at system boundaries.

⸻

## File Organization

* **Domain Locality:** Place utilities next to their domain modules.
* **Discoverability:** Keep modules well-structured.
* **Separation:** Distinctly separate source code, tests, and documentation.

⸻

## Service Testing After Code Changes

After code changes:

1. **Static Check:** Run linters/type-checkers.
2. **Runtime Check:** Start the affected service/module to catch runtime config errors.
3. **Verify:** Test basic functionality (e.g., a sample request).
4. **Cleanup:** Stop the service to free resources.

Common runtime issues: Invalid API calls, circular dependencies, missing env vars, port conflicts.

⸻

## Implementation Philosophy

A minimal, pragmatic approach:

* **Simplicity first:** Occam’s Razor—simplest working solution.
* **Emergent complexity:** Complex behavior should emerge from simple components.
* **Present-focused:** Build what is needed now, not for hypothetical futures.

**Design Principles:**

1. **Ruthless Simplicity:** Minimize abstractions. Challenge complexity.
2. **Architectural Integrity:** Keep patterns clean but implement them simply.
3. **Library Usage:** Use libraries as intended. Don't reinvent the wheel.

**Development Approach:**

* **Vertical Slices:** Implement full end-to-end flows early.
* **80/20 Rule:** Deliver high-value features first.
* **Refactor:** Refactor as patterns emerge, not beforehand.

⸻

## “Analyze First, Don’t Code” Pattern

For complex tasks, start with analysis, not code.

**Use when:** Implementing new features, complex refactors, optimizing performance, or debugging unfamiliar bugs.

**Analysis output should include:**

1. Problem decomposition.
2. 2–3 approach options with trade-offs.
3. Recommended approach with rationale.
4. High-level implementation plan.

Complement with Test-First and Error-First thinking.

⸻

## Decision-Making Questions

Ask yourself:

1. Do we truly need this now?
2. Is this the simplest workable solution?
3. Can we solve this more directly?
4. Does added complexity pay for itself?
5. How maintainable is this later?

**Simplify aggressively:** Internal abstractions, future-proofing, rare edge cases.
**Justify complexity:** Security, data integrity, core UX.

⸻

## Modular Design Philosophy

Optimize modules for both humans and AI tools.

**Key concepts:**

1. **Bricks & Studs:** Self-contained units with clear public contracts (APIs/interfaces).
2. **Start with the Contract:** Define the input/output/behavior first.
3. **Build in Isolation:** Internals should not leak. Consumers only import the public interface.
4. **Regenerate, don’t Patch:** If the contract holds, implementation details can be rewritten/regenerated easily.

**Cycle:** Spec → Isolated Build → Behavior Tests → Regenerate when needed.



Implementation Philosophy

This document is the central reference for how we build software in this project.

⸻

Core Philosophy

We follow a Zen-like minimalism that values simplicity and clarity:
	•	Wabi-sabi: Keep only what’s essential; every line must earn its place.
	•	Occam’s Razor: As simple as possible, but no simpler.
	•	Trust in emergence: Build small, well-defined components; let architecture emerge.
	•	Present focus: Solve today’s real needs, not hypothetical futures.
	•	Pragmatic trust: Talk to external systems directly; handle failures instead of over-defending.

Good architecture comes from simple, readable code and clear documentation, not from heavy upfront complexity.

⸻

Core Design Principles

1. Ruthless Simplicity
	•	Take KISS literally.
	•	Minimize abstractions; every layer must justify its existence.
	•	Start minimal, grow only when needed.
	•	Avoid “future-proofing” for imaginary requirements.
	•	Regularly challenge complexity and remove it.

2. Architectural Integrity, Minimal Implementation
	•	Keep key patterns (MCP, SSE, separate I/O channels, etc.).
	•	Implement them in the simplest possible way.
	•	Prefer “scrappy but structured” over “perfect but heavy.”
	•	Optimize for complete end-to-end flows, not perfect components in isolation.

3. Library vs Custom Code

No rigid rule; make contextual trade-offs and be ready to change your mind.

Evolution pattern:
	•	Start simple with custom code.
	•	Adopt a library when requirements grow.
	•	Drop the library and go back to custom if you outgrow it.

Use custom code when:
	•	Requirements are simple and clear.
	•	The problem is domain-specific.
	•	You’d be fighting a library or hacking around it.
	•	You need full control.

Use libraries when:
	•	They solve complex, well-known problems (auth, crypto, encoding, etc.).
	•	They fit your needs without major workarounds.
	•	They are mature and battle-tested.
	•	Configuration can adapt them sufficiently.

Judgment questions:
	•	Are we working with the library or against it?
	•	Is integration clean or full of hacks?
	•	Will future needs stay within its capabilities?
	•	Is the problem complex enough to warrant the dependency?

Misalignment signs:
	•	More time on workarounds than on real work.
	•	Custom solution has become fragile and sprawling.
	•	Heavy wrappers/monkey-patching.
	•	Library assumptions conflict with domain realities.

Stay flexible:
	•	Complexity is only moved, not destroyed.
	•	Isolate integration points so you can swap approaches.
	•	There’s no shame in moving custom → library or library → custom as needs evolve.

⸻

Technical Implementation Guidelines

API Layer
	•	Only essential endpoints.
	•	Minimal middleware, focused validation.
	•	Clear, useful error responses.
	•	Consistent patterns across endpoints.

Database & Storage
	•	Simple schemas aligned to current needs.
	•	Use TEXT/JSON early; avoid premature over-normalization.
	•	Add indexes only when profiling shows you need them.
	•	Delay advanced DB features until justified.

MCP Implementation
	•	Streamlined MCP client; minimal error handling.
	•	Prefer FastMCP; fall back to low-level only when necessary.
	•	Focus on core functionality, not elaborate state machines.
	•	Simple connection lifecycle and basic health checks.

SSE & Real-time
	•	Basic SSE connection management.
	•	Simple, resource-based subscriptions.
	•	Direct event delivery; no complex routing fabric.
	•	Minimal state tracking for connections.

Event System
	•	Simple topic-based pub/sub.
	•	Direct delivery, minimal pattern matching.
	•	Small, clear payloads.
	•	Basic subscriber error handling.

LLM Integration
	•	Direct integration with PydanticAI.
	•	Minimal response transformation.
	•	Handle only common error cases.
	•	Skip advanced caching initially.

Message Routing
	•	Simple queue-based processing.
	•	Direct routing logic, few action types.
	•	Straightforward integration between components.

⸻

Development Approach

Vertical Slices
	•	Build full end-to-end slices first.
	•	Start from core user journeys.
	•	Get data flowing through all layers early.
	•	Add breadth only after core flows work reliably.

Iterative Implementation
	•	Use 80/20: prioritize high-value, low-effort work.
	•	One working feature > many half-finished ones.
	•	Validate with real usage before scaling.
	•	Refactor as stable patterns emerge.

Testing Strategy
	•	Emphasize integration and end-to-end tests for critical paths.
	•	Design for manual testability.
	•	Add unit tests for complex logic and edge cases.
	•	Rough target: ~60% unit, 30% integration, 10% e2e.

Error Handling
	•	Handle common failure cases robustly.
	•	Log enough context for debugging.
	•	Provide user-facing errors that are clear and actionable.
	•	Fail fast and visibly during development.

⸻

Decision-Making Framework

When deciding on an implementation:
	1.	Necessity: Do we actually need this now?
	2.	Simplicity: What is the simplest solution that works?
	3.	Directness: Can we get there more directly?
	4.	Value: Does the added complexity pay for itself?
	5.	Maintenance: Will this be easy to understand and change later?

⸻

Where to Embrace vs Reduce Complexity

Embrace complexity in:
	1.	Security (no shortcuts).
	2.	Data integrity and consistency.
	3.	Core user experience and primary flows.
	4.	Error visibility and diagnosability.

Aggressively simplify:
	1.	Internal abstractions and intermediate layers.
	2.	“Future-proof” code for imaginary scenarios.
	3.	Rare edge cases (handle common cases first).
	4.	Framework usage (use the 10% that matters).
	5.	State management (prefer explicit, simple state).

⸻

Practical Examples

Good: Direct SSE Implementation

class SseManager:
    def __init__(self):
        self.connections = {}  # connection_id -> {resource_id, user_id, queue}

    async def add_connection(self, resource_id, user_id):
        connection_id = str(uuid.uuid4())
        queue = asyncio.Queue()
        self.connections[connection_id] = {
            "resource_id": resource_id,
            "user_id": user_id,
            "queue": queue,
        }
        return queue, connection_id

    async def send_event(self, resource_id, event_type, data):
        for conn in self.connections.values():
            if conn["resource_id"] == resource_id:
                await conn["queue"].put({"event": event_type, "data": data})

Bad: Over-engineered SSE
	•	Multiple indices and registries.
	•	Background cleanup tasks by default.
	•	Complex metrics and state machines before they’re needed.
	•	50+ lines of indirection for simple behavior.

Good: Simple MCP Client

class McpClient:
    def __init__(self, endpoint: str, service_name: str):
        self.endpoint = endpoint
        self.service_name = service_name
        self.client = None

    async def connect(self):
        if self.client is not None:
            return
        try:
            async with sse_client(self.endpoint) as (read_stream, write_stream):
                self.client = ClientSession(read_stream, write_stream)
                await self.client.initialize()
        except Exception as e:
            self.client = None
            raise RuntimeError(f"Failed to connect to {self.service_name}: {e}")

    async def call_tool(self, name: str, arguments: dict):
        if not self.client:
            await self.connect()
        return await self.client.call_tool(name=name, arguments=arguments)

Bad: Over-engineered MCP Client
	•	Rich connection states and retry strategies out of the gate.
	•	Health check tasks and complex metrics before proving need.
	•	Large, hard-to-reason-about state machines.

⸻

Remember
	•	It’s easier to add complexity later than to remove it.
	•	Code you don’t write cannot break.
	•	Clarity beats cleverness.
	•	The best code is often the simplest solution that fully solves the real problem.

This philosophy is the baseline for all implementation decisions in this project.


===

---

# Modular Design Standards: Contracts & Specs

**Objective:** Isolate modules to enable parallel generation and prevent tight coupling.
**Execution Model:** When generating a module, the worker/agent sees **only**:

1. Target Module **Contract** (The interface).
2. Target Module **Spec** (The implementation plan).
3. **Contracts** of dependencies.
*Worker never sees other modules’ source code or specs.*

---

## 1. Artifact Definitions

| Artifact     | Scope        | Purpose                                            | Visibility     |
| ------------ | ------------ | -------------------------------------------------- | -------------- |
| **Contract** | **Public**   | Stable agreement on inputs, outputs, and behavior. | All consumers. |
| **Spec**     | **Internal** | Implementation details, logic, and test plans.     | Builder only.  |

* **Contracts** must follow Semantic Versioning (SemVer).
* **Specs** can change freely as long as the Contract is satisfied.

---

## 2. Core Principles

1. **Interface First:** Write the Contract before the Spec.
2. **Black Box:** Dependencies are referenced **strictly** via their Contracts.
3. **Isolation:** A module must be regenerable without reading external source code.
4. **Testability:** Every promise in the Contract must map to a test in the Spec.

---

## 3. File Standards

Naming convention:

* `{module_id}.contract.md`
* `{module_id}.spec.md`

---

## 4. The Contract (Public Surface)

**Content:**

* **Metadata:** Module ID, Version, Dependencies (Concept + Contract Path).
* **Role:** High-level purpose (no implementation details).
* **Public API:** Signatures, types, side effects, pre/post-conditions.
* **Data Models:** JSON schemas or type definitions for I/O.
* **Error Model:** Public error codes and retry logic.
* **Config:** Consumer-facing configuration (Env vars).
* **Conformance:** Testable criteria for verification.

**Forbidden:** Internal helper functions, private logic, internal file paths.

---

## 5. The Spec (Internal Blueprint)

**Content:**

* **Traceability:** Mapping Contract requirements to implementation steps.
* **Internal Architecture:** Classes, data flow, state management.
* **Dependency Usage:** *How* dependencies are called (based on their Contracts).
* **Logging & Observability:** Internal log levels and formats.
* **Error Handling:** Internal exception mapping to Public Error Codes.
* **Internal Config:** Private knobs/settings.
* **Test Plan:** Unit/Integration tests covering Conformance criteria.

**Goal:** Precise enough for deterministic generation, but does not restate the Contract.

---

## 6. Dependency Rules

* **Contracts** declare dependencies explicitly.
* **Specs** use dependencies only as defined in their respective Contracts.
* **Workers** are strictly forbidden from peeking at dependency source code.

---

## 7. AI Worker Protocol

Instructions for the Agent/LLM generating the code:

1. **Read** the target Contract and Spec.
2. **Read** dependency Contracts (ignore their implementations).
3. **Plan** the file structure and classes based on the Spec.
4. **Generate** code that satisfies the Contract's Public API.
5. **Implement** the specific internal logic defined in the Spec.
6. **Create Tests** that verify the Conformance Criteria.
7. **Output** only the files defined in the Spec's file plan.
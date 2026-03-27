# ADR 002: Agent communication pattern

## Status

Accepted

## Context

Multiple specialised agents (Research, Analysis, Writer, Quality) must cooperate under the LangGraph orchestrator. Communication patterns affect:

- **Debuggability** — can we replay what each agent saw?
- **Validation** — no untyped blobs at boundaries (portfolio standard: Pydantic at boundaries).
- **Cost attribution** — which agent incurred which LLM calls?
- **Testability** — unit tests without spinning the whole graph.

Patterns considered:

1. **Shared graph state (single reducer-backed state object)** — agents read/write defined fields; orchestrator passes state between nodes.
2. **Message passing only** — agents send messages; no shared structure (heavier, more boilerplate for this use case).
3. **Direct agent-to-agent calls** — bypass orchestrator (harder to enforce checkpoints, logging, and persistence).

## Decision

Use a **single, versioned orchestration state model** (shared graph state) with **explicit fields per phase** and **immutable-style updates** where practical:

- **Research** outputs populate `research_bundle` (or equivalent) with source-linked artefacts.
- **Analysis** outputs populate `analysis_artefact` derived from `research_bundle`.
- **Human checkpoint** updates `human_decision` and optional `approved_bundle_ref` / edited content references.
- **Writer** reads approved inputs only; writes `draft_report`.
- **Quality** reads `draft_report` and writes `quality_result` and optional `revision_notes`.

Each agent is invoked **only** by the orchestrator (or a nested subgraph with the same logging rules), not by another agent directly.

## Rationale

- Aligns with LangGraph’s state-centric design and checkpointing.
- **One place** to attach correlation IDs, run IDs, and per-step cost records.
- Pydantic models can validate each slice of state at node boundaries, matching the AI engineering playbook.
- Avoids hidden coupling between agents (no private channels).

## Consequences

### Positive

- Clear data flow for documentation and code review.
- Easier to implement “replay run from checkpoint” for support.

### Negative

- State schema evolves over time — requires migration or versioning discipline (see implementation plan).

### Mitigations

- Version fields (`state_schema_version`) and document breaking changes in CHANGELOG / ADRs.
- Keep agent nodes thin: validate input slice → call service → validate output slice.

## Links

- `docs/architecture.md` — agent flow
- `docs/decisions/001-orchestration-framework.md` — LangGraph
- `docs/decisions/004-human-checkpoint-design.md` — what gets approved in state

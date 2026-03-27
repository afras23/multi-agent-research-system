# ADR 004: Human checkpoint design

## Status

Accepted

## Context

The business problem (`docs/problem-definition.md`) requires **human judgement** before expensive or sensitive **report generation**. The architecture places a **human checkpoint between research/analysis and writer/quality**.

The checkpoint must be:

- **Explicit** — no silent continuation to drafting.
- **Durable** — survives API restarts; analysts can return later.
- **Auditable** — who approved, when, and what version of artefacts was released for drafting.
- **API-driven** — fits REST (or future UI) with clear states.

## Decision

Implement the checkpoint as a **first-class paused state** in the LangGraph workflow:

1. After **Analysis Agent** completes and state validates, the orchestrator transitions to **`awaiting_human_review`** (or equivalent terminal-for-automation state).
2. The run **does not** invoke Writer until a **human decision** is recorded via an API:
   - **Approve** — optionally with **edits** to structured fields or attached notes; advances to Writer.
   - **Reject / abort** — ends run with a documented reason (no draft billable to “successful” metrics if product defines that).
3. **Resume** is implemented by loading the persisted checkpoint and **injecting** the human decision into state, then **continuing** the graph from the approved edge.

Authorisation (which roles may approve) is **out of scope for this ADR** but must be enforced before Phase 1 is “production-ready” if multi-tenant.

## Rationale

- **Interrupt semantics** in LangGraph match “pause until human” without polling inside agent code.
- **Separation of concerns:** agents never ask “is this approved?” — the orchestrator only schedules Writer when the human gate is satisfied.
- **Audit:** human action is one record: actor, timestamp, decision, artefact version/hash.

## Consequences

### Positive

- Clear product story: “Nothing is drafted without explicit approval.”
- Testable via API integration tests (mock human approval).

### Negative

- **Latency:** runs may stall for hours or days — TTL and reminder policies may be needed later (not blocking Phase 0).

### Mitigations

- Expose run **status** and **next required action** in API responses (`metadata` block per portfolio standard).
- Log structured events for `human_checkpoint_pending` and `human_checkpoint_resolved`.

## API shape (non-binding sketch)

Exact paths and models belong in implementation; directionally:

- `POST .../runs` — start research run.
- `GET .../runs/{run_id}` — status, current phase, whether human input needed.
- `POST .../runs/{run_id}/human-decision` — approve | reject | abort with payload.

## Links

- `docs/problem-definition.md` — why the gate exists
- `docs/architecture.md` — diagram
- `docs/decisions/002-agent-communication-pattern.md` — state fields for decisions
- `docs/decisions/003-state-persistence-strategy.md` — resume after approval

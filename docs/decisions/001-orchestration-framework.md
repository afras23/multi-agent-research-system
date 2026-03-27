# ADR 001: Orchestration framework (LangGraph vs CrewAI vs custom)

## Status

Accepted

## Context

The multi-agent research system requires a control plane that:

- Expresses **sequential and conditional** flows (including loops with caps).
- Supports **interrupt / resume** for a **human checkpoint** between research and report generation.
- Persists **checkpoints** so runs survive restarts.
- Fits a **Python**, **async**, **FastAPI** service with dependency injection and testability.

Candidates considered:

1. **LangGraph** — graph/state-machine layer on top of LangChain primitives; first-class checkpoints and human-in-the-loop patterns.
2. **CrewAI** — role-based agents and tasks; strong for demos, less explicit graph control and persistence semantics in many setups.
3. **Custom orchestrator** — full control, minimal dependencies, highest build cost and ongoing maintenance.

## Decision

Use **LangGraph** as the orchestration framework for the research workflow state machine.

## Rationale

- **State machine fit:** Research → Analysis → **interrupt** → Writer → Quality maps naturally to a graph with an explicit interrupt node before drafting.
- **Checkpoints:** LangGraph’s checkpoint model aligns with ADR 003 (persistence strategy) and production requirements for resume and audit.
- **Ecosystem:** Documentation and patterns for multi-step LLM workflows reduce bespoke control-flow bugs.
- **CrewAI:** Higher-level abstractions can obscure checkpoint boundaries and complicate strict **per-agent cost attribution** unless extended; less ideal when the portfolio standard expects explicit service-layer orchestration.
- **Custom:** Acceptable only if LangGraph introduced unacceptable risk; for this portfolio scope, reinventing persistence + interrupt semantics is unnecessary.

## Consequences

### Positive

- Clear mapping from architecture diagram to code (nodes, edges, interrupt).
- Easier implementation of human gates and bounded revision loops.

### Negative

- Dependency on LangGraph/LangChain stack — version pinning and upgrade discipline required.
- Team must keep graph definitions readable (avoid “smart” dynamic graphs without documentation).

### Mitigations

- Wrap graph construction in a small, testable module; inject persistence and LLM clients.
- Lock dependency versions in `requirements.txt`; run CI on upgrades.

## Links

- `docs/architecture.md` — orchestrator diagram
- `docs/decisions/003-state-persistence-strategy.md` — checkpoint storage
- `docs/decisions/004-human-checkpoint-design.md` — human interrupt

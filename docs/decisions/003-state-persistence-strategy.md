# ADR 003: State persistence strategy

## Status

Accepted

## Context

Runs may be long (research + analysis + human wait + drafting). The system must:

- **Persist** orchestration checkpoints and artefact metadata across process restarts.
- Support **human checkpoint** — run remains idle but **resumable** with a stable identifier.
- Align with the portfolio standard: **PostgreSQL** for production relational data, **async** access.

Options considered:

1. **PostgreSQL + LangGraph checkpoint tables** — store serialised checkpoints and run metadata in the app database.
2. **Redis only** — fast, but durability and query patterns for audit/history are weaker unless combined with something else.
3. **File-based checkpoints** — simple locally; poor fit for multi-instance deployment and backup story.

## Decision

Use **PostgreSQL** as the **system of record** for research run metadata and **checkpoint payloads** (or references to blob storage if artefacts grow large — see consequences). The application uses **async** SQLAlchemy (or equivalent) and migrations (Alembic) per portfolio standard.

**Implementation detail (to be fixed in build phases):** LangGraph’s checkpoint saver is configured to use a **PostgreSQL-backed** implementation compatible with the chosen LangGraph version, with tables owned by the application schema.

## Rationale

- Matches **PORTFOLIO-ENGINEERING-STANDARD** (Postgres, migrations, CI with real Postgres).
- Supports **audit** queries (run status, who approved, when) alongside technical checkpoints.
- **Redis** may still appear later for **rate limiting or ephemeral locks**, but not as the sole durability store for workflow state.

## Consequences

### Positive

- Single operational datastore for runs in early phases; simpler backup/replication story.
- Fits existing patterns: repositories, idempotent APIs, structured logging of DB errors.

### Negative

- Large artefacts (full raw HTML dumps) can bloat rows — may need **offload to object storage** with DB holding pointers only.

### Mitigations

- Store **summaries and references** in checkpoint state; cap embedded payload sizes via settings.
- Add blob strategy in a later phase if evaluation shows storage pressure.

## Implementation alignment (as built)

- **Research run records and serialised orchestration state** live in **PostgreSQL** via `TaskRepository` / Alembic models (task status, JSON state, messages, audit-friendly fields).
- The **compiled LangGraph** uses an in-memory **`MemorySaver`** checkpointer for interrupt/resume mechanics within a process; **long-lived truth** for “what to show the analyst” and **post-restart continuity** is the **persisted `ResearchState`** in Postgres, reloaded on approve/reject and listing.
- A future iteration may swap `MemorySaver` for a Postgres-backed LangGraph checkpointer without changing the external API; see `app/orchestration/graph.py`.

## Links

- `docs/architecture.md` — persistence layer
- `docs/decisions/001-orchestration-framework.md` — LangGraph checkpoints
- `docs/decisions/004-human-checkpoint-design.md` — paused run lifecycle

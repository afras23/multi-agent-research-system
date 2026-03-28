# Changelog

All notable changes to this project are tracked by **implementation phase** (see `docs/implementation-plan.md`).

## Phase 0 — Problem framing and architecture (documentation)

- Problem definition, architecture doc with Mermaid diagrams.
- ADRs **001–004** (orchestration, agent communication, persistence, human checkpoint).
- Implementation plan with phased outcomes.

## Phase 1 — Project skeleton and platform baseline

- FastAPI app, correlation ID middleware, structured JSON logging.
- Pydantic Settings, `.env.example`, health / ready / metrics routes.
- PostgreSQL + async SQLAlchemy, Alembic initial migration.
- Docker multi-stage image, `docker-compose`, Makefile, CI (Ruff, pytest, Postgres).

## Phase 2 — AI client, cost tracking, run registry

- `LlmClient` with retries, circuit breaker, per-call and daily USD limits.
- Cost ledger fields (model, tokens, cost, latency, attribution).
- Task/repository layer for run lifecycle.

## Phase 3 — LangGraph orchestrator and agents

- LangGraph graph: Research → Analysis → Checkpoint → Writer → Quality.
- `ResearchState` and agent implementations (prompt-backed).
- Checkpoint integration with persistence.

## Phase 4 — Human checkpoint API and audit trail

- Approve / reject endpoints, reviewer identity, persisted decisions.
- Integration tests for checkpoint flows.

## Phase 5 — Prompts, quality loop, evaluation harness

- Versioned prompts, quality rubric JSON, writer/quality behaviour.
- **`eval/test_set.jsonl`**, **`scripts/evaluate.py`**, **`make evaluate`** with mocked LLM.
- **`app/eval/`** grading and report schema.

## Phase 6 — Documentation, polish, definition of done

- README case study, Mermaid architecture, evaluation snapshot, **Architecture Decisions** table.
- **`docs/runbook.md`** (health, costs, stuck tasks, logs, quality, errors, new agents).
- **`docs/definition-of-done-checklist.md`** (DoD PASS/FAIL).
- **`CHANGELOG.md`** (this file).
- ADR 003 updated with implementation note (Postgres task state vs LangGraph `MemorySaver`).

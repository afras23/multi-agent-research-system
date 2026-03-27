# Implementation Plan

## Principles

- Follow **one phase at a time**; each phase has clear acceptance criteria and maps to the engineering playbook and portfolio standard.
- **No application code in Phase 0** — documentation and decisions only (this plan + problem + architecture + ADRs).
- Production direction: **Python 3.12**, **FastAPI**, **Pydantic Settings**, **async** I/O, **PostgreSQL**, **structured logging**, **per-agent and daily cost limits**.

## Phase 0 — Problem framing and architecture (documentation only)

**Deliverables:** `docs/problem-definition.md`, `docs/architecture.md`, `docs/decisions/*.md`, this `docs/implementation-plan.md`.

**Acceptance criteria:**

- [ ] Problem statement reflects analyst workflow (6+ hours manual, multi-step process).
- [ ] Architecture includes LangGraph orchestrator, four agents, human checkpoint placement, persistence, per-agent cost tracking (diagram present).
- [ ] At least four ADRs cover orchestration, communication, persistence, and human checkpoint.
- [ ] Implementation plan lists six build phases with outcomes.

---

## Phase 1 — Project skeleton and platform baseline

**Goal:** Runnable API shell matching portfolio layout: config, logging, health/ready/metrics, Docker, Makefile, CI, `.env.example`, empty or stub routes only where needed — **no full agent logic yet**.

**Outcomes:**

- FastAPI app factory, correlation ID middleware, structured JSON logging.
- Pydantic Settings; no hardcoded secrets.
- PostgreSQL via async SQLAlchemy; Alembic initial migration (even if minimal).
- `docker-compose` with healthy DB + app; non-root image, HEALTHCHECK.
- CI: ruff, mypy, pytest against real Postgres.
- API response envelope per portfolio standard for stub endpoints.

**Acceptance criteria:**

- [ ] `docker-compose up` brings up API; `/api/v1/health` and `/api/v1/health/ready` behave as specified.
- [ ] `make lint`, `make test`, `make typecheck` exist and pass.
- [ ] `.env.example` documents all variables.

---

## Phase 2 — AI client, cost tracking, and run registry

**Goal:** Injectable **AI client wrapper** (mockable in tests) with retries, token and USD logging, **per-call** and **daily aggregate** limits; database models for **research runs** (status, correlation id, timestamps).

**Outcomes:**

- Cost ledger entries including `model`, `tokens_in`, `tokens_out`, `cost_usd`, `latency_ms`, `agent_step` (or equivalent attribution field).
- Repository layer for run lifecycle persistence.
- Unit tests for cost math, limit enforcement, and client retry behaviour (mocked provider).

**Acceptance criteria:**

- [ ] No route calls LLM without service + client indirection.
- [ ] Cost limit exceeded returns controlled error (no crash); logged with structured fields.
- [ ] Metrics endpoint exposes cost-related summaries per standard.

---

## Phase 3 — LangGraph orchestrator and agent stubs

**Goal:** Wire **LangGraph** graph with **Research → Analysis → interrupt (human) → Writer → Quality**; agents initially **stub** or minimal prompts behind interfaces; **checkpoint persistence** to PostgreSQL per ADR 003.

**Outcomes:**

- Graph module with explicit state model (Pydantic) slices per ADR 002.
- Checkpoint save/load verified with integration tests.
- Human-pending state reachable without executing real external search (fixtures).

**Acceptance criteria:**

- [ ] End-to-end **test** (integration) runs graph to `awaiting_human_review` with mocks.
- [ ] Resume after injecting human decision reaches terminal success/failure deterministically in tests.

---

## Phase 4 — Human checkpoint API and audit trail

**Goal:** Expose **run status** and **human decision** endpoints; persist decisions with user identity placeholder or auth-ready fields; ensure **audit log** entries for approvals/rejections.

**Outcomes:**

- API to list/get run, submit human decision, resume orchestration.
- Audit records linked to run id and artefact version/hash.

**Acceptance criteria:**

- [ ] Integration tests cover approve and reject paths.
- [ ] No draft generated when rejected (verified by state or absence of writer output).

---

## Phase 5 — Real agent behaviours, prompts, and quality loop

**Goal:** Replace stubs with **versioned prompts**, real LLM calls behind the client, validation of structured outputs (Pydantic), **Quality Agent** rules with **bounded** writer revision loop; optional retrieval/search integration behind adapters.

**Outcomes:**

- Prompt files or registry with versions; evaluation harness skeleton (`make evaluate` target).
- Writer/Quality loop respects max revisions from settings.

**Acceptance criteria:**

- [ ] Evaluation script runs on fixture set (can use mock provider in CI).
- [ ] Prompt injection mitigations applied to user-provided briefs per security section of portfolio standard.

---

## Phase 6 — Production hardening, documentation, and demo path

**Goal:** Meet **Definition of Done** from project rules: 40+ tests, runbook, README case study structure, sample inputs under `tests/fixtures/sample_inputs/`, ADR count satisfied, load/error testing as appropriate.

**Outcomes:**

- `docs/runbook.md`, README with architecture snippet and evaluation numbers when available.
- Rate limiting / production CORS as required; graceful degradation when cost limit hit.
- Full `docker-compose` demo processes sample brief end-to-end (with documented API keys).

**Acceptance criteria:**

- [ ] `make test` passes with coverage threshold; CI green.
- [ ] New engineer can follow README in under five minutes for local demo (keys permitting).
- [ ] No `TODO`/`FIXME` in committed code; logging and error patterns match playbook.

---

## Phase dependency graph (summary)

```text
Phase 0 (docs)
    → Phase 1 (platform)
        → Phase 2 (AI + runs)
            → Phase 3 (LangGraph + checkpoints)
                → Phase 4 (human API + audit)
                    → Phase 5 (real agents + eval)
                        → Phase 6 (hardening + docs)
```

## Related documents

- `docs/problem-definition.md`
- `docs/architecture.md`
- `docs/decisions/001-orchestration-framework.md`
- `docs/decisions/002-agent-communication-pattern.md`
- `docs/decisions/003-state-persistence-strategy.md`
- `docs/decisions/004-human-checkpoint-design.md`

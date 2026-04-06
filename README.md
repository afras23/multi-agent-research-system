# Multi-Agent Research System

## AI Agents Collaborate to Produce Company Research Reports

## 6 hours → 10 minutes | Cited sources | Quality scoring | Human oversight

---

### The Problem

Analyst teams at consulting and investment firms spend **6+ hours** per company research report. Work is fragmented across manual search, synthesis, drafting, and review. Quality is inconsistent, sources are easy to miss, and senior time is consumed by repetitive review instead of judgment calls.

### The Solution

This repository implements a **multi-agent system** in which specialised AI agents handle **research**, **analysis**, **writing**, and **quality checking**, coordinated by a **LangGraph** state machine. A **human approval checkpoint** sits **before** report generation so a senior analyst can approve or reject the research and analysis bundle. The pipeline produces **structured Markdown reports** with **source citations** and **automated quality scoring**, with **per-agent cost attribution** and configurable budgets.

### Architecture

```mermaid
flowchart TB
    subgraph clients["Clients"]
        API["HTTP API / UI"]
    end

    subgraph orchestrator["Orchestrator — LangGraph state machine"]
        direction TB
        START([Start / resume])
        R["Research Agent"]
        A["Analysis Agent"]
        HC{{"Human checkpoint\n(research → report)"}}
        W["Writer Agent"]
        Q["Quality Agent"]
        END_NODE([Complete / fail / await human])

        START --> R
        R --> A
        A --> HC
        HC -->|"approve / edit"| W
        HC -->|"reject / abort"| END_NODE
        W --> Q
        Q -->|"pass"| END_NODE
        Q -->|"revise (bounded)"| W
    end

    subgraph persistence["State persistence layer"]
        SP[("Run state store\n(checkpoints, status, artefacts)")]
    end

    subgraph cost["Cost tracking"]
        CT["Per-agent ledger\n(tokens, USD, latency, model)"]
        AGG["Daily / run aggregates"]
    end

    API --> START
    R --> SP
    A --> SP
    HC --> SP
    W --> SP
    Q --> SP

    R --> CT
    A --> CT
    W --> CT
    Q --> CT
    CT --> AGG
```

*(Same diagram as [`docs/architecture.md`](docs/architecture.md).)*

### How It Works

1. **Submit** a company name and research brief via the API.
2. **Research Agent** plans topic areas and gathers structured findings (parallel sub-tasks with timeouts).
3. **Analysis Agent** synthesises themes, risks, and opportunities from those findings.
4. The system **pauses for human review**: a senior analyst **approves** or **rejects** (with reason) via the API.
5. On approval, **Writer Agent** produces a structured Markdown report with explicit `[Source: …]` citations.
6. **Quality Agent** scores the draft (coverage, completeness, accuracy, coherence) and records a recommendation.
7. The **final report** is available with **quality score**, **agent cost breakdown**, and **message log** for auditability.

### Evaluation Results

Offline evaluation uses **`eval/test_set.jsonl`** (20+ scenarios) and a **mocked OpenAI client** so runs are **reproducible in CI** without billing. Dollar costs and latency in that harness reflect **token estimates on mock responses**, not live production traffic; they are useful for **relative per-agent attribution** and **pipeline checks**.

Latest run (see `eval/results/eval_2026-03-28.json` after `make evaluate`):

```json
{
  "timestamp": "2026-03-28T00:10:26.996187+00:00",
  "model": "gpt-4o",
  "test_cases": 20,
  "pass_rate": 0.9,
  "avg_quality_score": 64.25,
  "avg_sections_present": 5.95,
  "avg_topic_coverage": 1.0,
  "avg_citation_count": 6.95,
  "avg_cost_per_task_usd": 0.0018,
  "avg_latency_ms": 7.17,
  "cost_by_agent": {
    "research": 0.001,
    "analysis": 0.00025,
    "writer": 0.00025,
    "quality": 0.00025
  },
  "failures": [
    {
      "company": "EvalQualityGateFail",
      "reason": "quality score 50.0 below minimum 60.0"
    },
    {
      "company": "EvalSectionOmitCo",
      "reason": "missing section: Risks and Opportunities"
    }
  ]
}
```

**Pass criteria** in the harness: quality score ≥ configured minimum, all expected section headings present, and ≥80% of expected topic phrases found in the report. Two rows are intentionally seeded to fail (quality floor and missing section) to exercise failure reporting.

### Key Features

- **Four specialised agents** — Research, Analysis, Writer, Quality
- **LangGraph** state machine for orchestration and checkpoints
- **Human approval checkpoint** (REST API: approve / reject, reviewer identity stored)
- **State persistence** — tasks are resumable after approval (`PostgreSQL` + Alembic)
- **Per-agent cost tracking** and daily / per-request USD limits
- **Parallel execution** for research sub-tasks (configurable concurrency and sub-task timeouts)
- **Automated quality scoring** — source coverage, completeness, accuracy, coherence
- **Inter-agent and step logging** for debugging and audit trails
- **Structured JSON logging** with **correlation IDs**

### Tech Stack

**Python 3.12**, **FastAPI**, **LangGraph**, **OpenAI** (e.g. **GPT-4o**), **PostgreSQL** (async SQLAlchemy + **asyncpg**), **Docker** / **Docker Compose**, **GitHub Actions** (Ruff, Mypy, Pytest), **Alembic** migrations.

### How to Run

**Goal:** go from clone to a working API in a few minutes.

#### Quick start (Docker)

```bash
git clone https://github.com/afras23/multi-agent-research-system.git
cd multi-agent-research-system
cp .env.example .env
# Set OPENAI_API_KEY and match DB_* to docker-compose defaults (see .env.example)
docker compose up -d --build
```

If **port 8000 is already in use**, set e.g. `API_PORT=8001` in `.env` or run `API_PORT=8001 docker compose up -d` and open the matching port in the browser.

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs) (or your `API_PORT`)
- **Run DB migrations** (required before first API use): from the host with Postgres reachable on the mapped port, `export DATABASE_URL=postgresql+asyncpg://appuser:apppass@127.0.0.1:5432/research_db` then `make migrate`, **or** `docker compose exec app python -m alembic upgrade head` (same URL as in Compose).

**Start a research task:**

```bash
curl -s -X POST http://localhost:8000/api/v1/research \
  -H "Content-Type: application/json" \
  -d '{"company_name": "Stripe", "research_brief": "Competitive position in payments"}'
```

A sample payload also lives at [`tests/fixtures/sample_inputs/sample_research_brief.json`](tests/fixtures/sample_inputs/sample_research_brief.json).

**Tests and evaluation:**

```bash
make test       # pytest
make evaluate   # offline harness → eval/results/eval_YYYY-MM-DD.json
```

#### 1. Prerequisites

- **Python 3.12+** (project targets 3.12; 3.11 often works for local dev)
- **PostgreSQL 16** (or use Docker Compose for the database)
- **OpenAI API key** for live LLM calls (optional for running tests; CI uses mocks)

#### 2. Configure environment

```bash
cp .env.example .env
# Edit .env: set DATABASE_URL, OPENAI_API_KEY, and optional cost limits
```

All variables are documented in `.env.example`.

#### 3. Install dependencies

```bash
make dev
# or: pip install -r requirements.txt && pip install -r requirements-dev.txt
```

#### 4. Database migrations

Ensure PostgreSQL is reachable, then:

```bash
make migrate
```

#### 5. Run the API (local)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 6. Run with Docker Compose (app + Postgres)

```bash
docker compose up --build
```

The API listens on **port 8000** by default. The image runs as a **non-root** user and exposes a **HEALTHCHECK** against `/api/v1/health`.

#### 7. Quick checks

```bash
# Liveness
curl -s http://127.0.0.1:8000/api/v1/health | jq .

# Readiness (includes DB)
curl -s http://127.0.0.1:8000/api/v1/health/ready | jq .

# Metrics summary
curl -s http://127.0.0.1:8000/api/v1/metrics | jq .
```

#### 8. Start a research task (example)

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/research \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Example Corp",
    "research_brief": "Summarise competitive position and key risks for the next 12 months.",
    "industry_context": "Enterprise software, US and EU"
  }' | jq .
```

Use the returned `task_id` to poll task status, submit approval or rejection, and fetch the final report when `status` is `completed`. See **`docs/runbook.md`** for endpoint summary and operational notes.

#### 9. Quality gates (developer)

```bash
make lint      # ruff check
make format    # ruff format
make typecheck # mypy app/
make test      # pytest
```

#### 10. Offline evaluation harness

```bash
make evaluate
```

Writes **`eval/results/eval_YYYY-MM-DD.json`** (gitignored). Requires project root on `PYTHONPATH` (the Makefile sets this).

### Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| **LangGraph** over CrewAI | Explicit control over agent flow, interrupts, and checkpoints; fits per-agent cost attribution |
| **Shared orchestration state** over ad hoc message passing | Single auditable `ResearchState` (Pydantic), persisted to PostgreSQL, clear hand-offs |
| **PostgreSQL** for run state | Resumable tasks, audit trail, same DB as task metadata (see ADR 003 for LangGraph checkpointer details) |
| **API-based checkpoint** | No extra queue or webhook infra; approve/reject are first-class REST operations |

See [`docs/decisions/`](docs/decisions/) for full ADRs (001–004).

---

### Documentation

| Document | Purpose |
|----------|---------|
| [`docs/architecture.md`](docs/architecture.md) | Architecture and Mermaid diagrams |
| [`docs/problem-definition.md`](docs/problem-definition.md) | Problem scope |
| [`docs/decisions/`](docs/decisions/) | ADRs 001–004 |
| [`docs/runbook.md`](docs/runbook.md) | Operations, monitoring, troubleshooting |
| [`CHANGELOG.md`](CHANGELOG.md) | Phase history |

### License

See repository root for license terms (if applicable).

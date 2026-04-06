# Multi-Agent Research System

![CI](https://github.com/afras23/multi-agent-research-system/actions/workflows/ci.yml/badge.svg)

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

Offline evaluation runs the pipeline against **`eval/test_set.jsonl`** using **mocked OpenAI responses** for reproducible, CI-friendly runs. Results are regenerated locally with `make evaluate` (the generated JSON output is not committed).

Latest run metrics:

| Metric | Value |
|--------|-------|
| Test cases | 20 |
| Pass rate | 0.90 |
| Avg quality score | 64.25 |
| Avg sections present | 5.95 |
| Avg topic coverage | 1.0 |
| Avg citation count | 6.95 |
| Avg cost per task (USD) | 0.0018 |
| Avg latency (ms) | 7.17 |

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

#### Local development (optional)

```bash
cp .env.example .env
make dev
make migrate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

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

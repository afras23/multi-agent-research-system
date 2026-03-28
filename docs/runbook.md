# Runbook — Multi-Agent Research System

Operational notes for running, monitoring, and extending the API.

## How to check system health

| Check | Command / path | Expected |
|-------|----------------|----------|
| **Liveness** | `GET /api/v1/health` | `200`, `data.status` healthy |
| **Readiness** (DB) | `GET /api/v1/health/ready` | `200`, database connectivity OK |
| **Metrics** | `GET /api/v1/metrics` | UTC-day aggregates, cost vs daily limit |

Example:

```bash
curl -s http://127.0.0.1:8000/api/v1/health | jq .
curl -s http://127.0.0.1:8000/api/v1/health/ready | jq .
curl -s http://127.0.0.1:8000/api/v1/metrics | jq .
```

All responses use the standard envelope: `status`, `data` / `error`, `metadata` (includes `correlation_id`).

## How to monitor agent costs

1. **Per task** — `GET /api/v1/research/{task_id}` returns `agent_costs` (USD, tokens) per agent step name (`research_agent`, `analysis_agent`, `writer_agent`, `quality_agent`).
2. **Aggregated (UTC day)** — `GET /api/v1/metrics` uses `TaskRepository.aggregate_operational_metrics`: task counts, spend vs `MAX_DAILY_COST_USD`, etc.
3. **Logs** — Each LLM completion logs `model`, `tokens_in`, `tokens_out`, `cost_usd`, `latency_ms`, `prompt_version` (search for `LLM call completed`).

Tune limits via `.env`: `MAX_DAILY_COST_USD`, `MAX_REQUEST_COST_USD`.

## How to handle stuck tasks (`awaiting_approval` for too long)

Runs intentionally **pause** until a human decision:

1. **`GET /api/v1/research/{task_id}`** — confirm `status` is `awaiting_approval` and `checkpoint_status` is `pending`.
2. Either:
   - **`POST /api/v1/research/{task_id}/approve`** with body `{"reviewer": "..."}` to continue to writer + quality, or
   - **`POST /api/v1/research/{task_id}/reject`** with `reviewer` + `reason` to end without a final report.

If the UI never called approve/reject, the task is **not stuck** — it is waiting for an operator. For abandoned runs, **reject** with a reason so the row reaches a terminal state.

If approve fails (500), check logs for DB errors and that migrations are applied.

## How to view inter-agent communication logs

- **API** — `GET /api/v1/research/{task_id}` includes **`agent_messages`**: `agent_name`, `message_type`, `content` (output lines from each agent step).
- **Persistence** — Messages are stored with the task (see message repository); use the same endpoint after restarts.

For raw server logs, filter by **`task_id`** or **`correlation_id`** (request header `X-Correlation-ID` optional).

## How to interpret quality scores

When the pipeline completes, **`GET /api/v1/research/{task_id}/report`** includes **`quality_score`** (when present):

| Field | Meaning |
|-------|---------|
| `overall_score` | Composite 0–100 |
| `source_coverage` | Citations / sources vs expectations |
| `completeness` | Structure and section coverage |
| `accuracy` | Consistency with findings |
| `coherence` | Readability and flow |
| `recommendation` | `approve` \| `revise` \| `reject` (model output) |

The Quality Agent prompts are versioned under `app/services/ai/prompts/`; scores are produced by the LLM against a JSON rubric and validated with Pydantic.

## Common error codes and recovery

Errors return `{"status": "error", "error": {"code": "...", "message": "...", "details": {...}}, "metadata": {...}}`.

| Code | HTTP | Meaning | Recovery |
|------|------|---------|----------|
| `TASK_NOT_FOUND` | 404 | Invalid `task_id` | Use list/get with correct UUID |
| `REPORT_NOT_READY` | 409 | Pipeline still running or awaiting approval | Poll task; approve if waiting |
| `REPORT_NOT_FOUND` | 404 | Failed, rejected, or no draft | Inspect `status`, `failure_reason`, `rejection_reason` |
| `COST_LIMIT` | 503 | Daily or per-request cap | Raise limits or wait for UTC day rollover |
| `RATE_LIMITED` | 429 | OpenAI rate limit | Back off; check provider status |
| `RETRYABLE` | 503 | Transient LLM/network (incl. circuit open) | Retry request; inspect logs |
| `AGENT_TIMEOUT` | 504 | Agent exceeded wall-clock budget | Increase `AGENT_TIMEOUT_SECONDS` or simplify brief |
| `AGENT_FAILED` | 500 | Agent raised after logging | Check `errors` on task detail |
| `DATABASE_UNAVAILABLE` | 503 | DB connection failed | Restore Postgres, verify `DATABASE_URL` |

## How to add a new agent type

1. **State** — Extend `ResearchState` in `app/orchestration/state.py` with fields the new step reads/writes (keep Pydantic).
2. **Agent class** — Subclass `BaseAgent`, implement `_execute`, use injected `LlmClient` + `Settings`; call `_track_cost` for each LLM call.
3. **Graph** — Add a node in `app/orchestration/graph.py`, wire edges and routing (`route_if_failed`, etc.).
4. **Dependencies** — Register the agent in `app/main.py` `GraphDependencies` and lifespan.
5. **Persistence** — Ensure new fields serialize in `model_dump(mode="json")` for `TaskRepository.save_state`.
6. **API** — Expose any new summary fields via schemas if clients need them.
7. **Tests** — Unit test the agent with mocked OpenAI; add orchestration test if behaviour is new.

Avoid direct agent-to-agent calls; only the graph invokes agents.

## Research workflow (API)

1. **`POST /api/v1/research`** — Create task; pipeline runs until **awaiting approval** or failure. Response **202** with `task_id` and `status`.
2. **`GET /api/v1/research/{task_id}`** — Inspect status, checkpoint state, agent messages, costs.
3. **`POST /api/v1/research/{task_id}/approve`** — Body includes `reviewer`. Resumes graph to writing and quality.
4. **`POST /api/v1/research/{task_id}/reject`** — Body includes `reviewer` and `reason`. Terminal **rejected** state; no report.
5. **`GET /api/v1/research/{task_id}/report`** — Final Markdown when `status` is **completed**.

## Configuration

- Load from **environment** / `.env` (see `.env.example`).
- **Cost limits**: `MAX_DAILY_COST_USD`, `MAX_REQUEST_COST_USD`.
- **Agents**: `AGENT_TIMEOUT_SECONDS`, `MAX_PARALLEL_AGENTS`, `RESEARCH_SUBTASK_TIMEOUT_SECONDS` (see `Settings`).

## Database

- **Migrations**: `make migrate` or `python -m alembic upgrade head` with `DATABASE_URL` set.
- Docker: after `docker compose up`, run migrations against the exposed DB port or `docker compose exec app python -m alembic upgrade head`.

## Logging

- Structured **JSON** logs; pass **`X-Correlation-ID`** for cross-service tracing.

## Offline evaluation

- **`make evaluate`** — mocked LLM, writes `eval/results/eval_YYYY-MM-DD.json` (gitignored).

## CI parity

```bash
make lint && make typecheck && make test
```

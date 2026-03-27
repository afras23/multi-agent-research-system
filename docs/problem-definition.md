# Problem Definition

## Summary

Consulting and investment firms need **repeatable, auditable company research** that matches analyst quality while cutting manual effort. Today, producing a single company research report is slow, fragmented, and expensive in senior time.

## Business context

**Who:** Analyst teams at consulting and investment firms (strategy, due diligence, sector coverage, corporate development).

**Pain:** A typical **company research report** takes **six or more hours** of senior analyst time per company when done manually.

**Current manual workflow (as-is):**

1. **Search** multiple sources (filings, news, data vendors, internal notes, sector primers).
2. **Read** and triage large volumes of text; reconcile conflicting facts.
3. **Synthesise** themes, risks, and investment or advisory implications.
4. **Draft** narrative sections in house style (executive summary, business overview, financials, risks, outlook).
5. **Review** for accuracy, compliance tone, and consistency with firm standards.
6. **Format** for delivery (client memo, IC pack, slide outline).

Each step involves context switching, duplicate effort across sources, and weak reuse of prior work. Quality depends on individual experience; throughput is capped by calendar time.

## Problem statement

The organisation needs a system that:

- **Reduces wall-clock and labour** for a first complete draft and structured research pack, without removing expert judgement where it matters.
- **Preserves traceability** from claims in the output back to sources and reasoning steps.
- **Enforces governance**: cost controls, human approval at defined gates, and observability suitable for production (logging, metrics, audit-friendly records).

## Goals (measurable direction)

| Goal | Target direction |
|------|------------------|
| Time to first structured draft | Meaningfully below 6+ analyst hours for comparable scope (exact KPI set in Phase 1 non-functional requirements) |
| Source traceability | Every material claim in the report mappable to gathered evidence or flagged as inference |
| Human control | Explicit checkpoint before high-stakes generation steps |
| Operational safety | Per-request and daily cost limits; refusal rather than silent overspend |

## Non-goals (for this product definition)

- Fully autonomous publishing without human review for regulated or client-facing outputs.
- Replacing legal, tax, or compliance sign-off; the system assists research and drafting, not statutory filings.
- Guaranteeing investment performance or recommendations; outputs are research support, not personal financial advice.

## Success criteria (qualitative)

Stakeholders should be able to:

1. **Start** a research job with a clear brief (company, scope, audience).
2. **Inspect** intermediate artefacts (sources, extracted facts, analysis notes) before committing to a full report draft.
3. **Resume** work after interruption without losing state.
4. **Explain** how a conclusion was reached using logged steps and citations where designed.

This document is the Phase 0 anchor for `docs/architecture.md`, ADRs in `docs/decisions/`, and the phased build in `docs/implementation-plan.md`.

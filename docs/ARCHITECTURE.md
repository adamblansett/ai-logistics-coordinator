# AI Logistics Coordinator — Architecture Blueprint

## Overview

Open-source, self-hosted AI logistics coordination platform for freight tracking, shipment route optimization, carrier communications, and inventory discrepancy alerts.

## Domain Modules (`backend/app/`)

- **`tracking/`** — Carrier webhook & X12 EDI 214 event normalizer (`B10`, `AT7`, `MS1`, `G62`, `L11`), SLA delay calculator, exception deduplication/escalation, and dispatcher resolution workflow.
- **`routing/`** — Multi-constraint lane & carrier selection optimizer (`BALANCED`, `LOWEST_COST`, `FASTEST_TRANSIT`, `HIGHEST_RELIABILITY`, `LOWEST_CARBON`), active corridor disruption alerts, and reviewable re-routing recommendations.
- **`comms/`** — Grounded carrier email/EDI portal message drafting (`DETENTION_NOTICE`, `BOL_CORRECTION`, `APPOINTMENT_RESCHEDULE`, `DELAY_ESCALATION`, `DISCREPANCY_CLAIM`) strictly gated behind dispatcher approval before sending.
- **`inventory/`** — Deterministic ASN/BOL vs. receiving count reconciler, shrinkage & financial exposure calculation, and SKU discrepancy alerts (`SHORTAGE`, `OVERAGE`, `DAMAGED`, `UNEXPECTED_SKU`).
- **`llm/`** — Ordered local-first `LLMRouter` (`mock` / `ollama` / `gemini`) with automatic fallback and deterministic cloud PII redaction (`app/core/security.py`).
- **`core/audit.py`** — Immutable SHA-256 hash-chained `audit_logs` ledger verifiable via `GET /api/v1/audit/verify`.

## API Surface (`/api/v1`)

| Prefix | Capabilities |
| :--- | :--- |
| `/health`, `/health/live`, `/health/ready` | Service liveness and DB readiness (`SELECT 1`) probes |
| `/dashboard/summary` | Cross-module live KPIs and recent audit activity |
| `/demo/seed` | Idempotent demo scenario seeder |
| `/tracking/*` | Shipments CRUD, webhook & `/edi214` ingestion, exception queue |
| `/routing/*` | Carrier lanes, disruption alerts, `/optimize`, recommendation decisions |
| `/comms/*` | Grounded `/draft`, pre-approval edits, `/decision`, gated `/send` |
| `/inventory/*` | `/reconcile` runs, reconciliation ledger, SKU alert updates |
| `/audit`, `/audit/verify` | Filterable audit log query and cryptographic chain verification |

## Security & Operational Invariants

1. **Fail-Fast Production Validation:** `validate_production_security()` refuses startup in `APP_ENV=production` if default dev secrets or wildcard CORS origins remain active.
2. **Cloud PII Redaction:** `GeminiLLMProvider` runs `redact_pii()` across both system and user prompts before outbound cloud requests whenever `LLM_REDACT_PII_FOR_CLOUD=true`.
3. **Human-in-the-Loop Approvals:** Carrier communications cannot transition to `SENT` unless `status == "APPROVED"` (enforced with HTTP `409 Conflict`), and route recommendations require explicit `APPROVED`/`REJECTED` decisions.
4. **Tamper-Evident Audit Trail:** Every entity creation and state transition appends a sequence-numbered, SHA-256 hash-chained row to `audit_logs`.
5. **Webhook Signature Verification:** Incoming webhook payloads validate HMAC-SHA256 `X-Webhook-Signature` headers when `WEBHOOK_SIGNING_SECRET` is configured.
6. **Non-Root Containers:** Both the FastAPI API image and Nginx frontend image run as non-root users with `/api/v1/health/live` and `/api/v1/health/ready` probes.

# AI Logistics Coordinator

> Open-source, self-hosted AI logistics coordination platform for freight tracking, shipment route optimization, carrier communications, and inventory discrepancy alerts.

**Roadmap Stage:** Phase 1 — Core Professional & Enterprise Operations · **Status:** Phase 1 MVP Implemented

## Implemented Core Capabilities

- **Freight Tracking (`backend/app/tracking/`):** Ingests JSON carrier webhooks (with optional HMAC-SHA256 `X-Webhook-Signature` verification) and X12 **EDI 214** payloads (`B10`, `AT7`, `MS1`, `G62`, `L11`), normalizes carrier status codes, detects SLA ETA slips and operational exceptions (`ETA_SLIP`, `DETENTION`, `CUSTOMS_HOLD`, `WEATHER_DISRUPTION`, `PORT_CONGESTION`, `TEMPERATURE_EXCURSION`), and manages exception acknowledgment/resolution queues.
- **Route Optimization (`backend/app/routing/`):** Evaluates active carrier lanes across multi-constraint objectives (`BALANCED`, `LOWEST_COST`, `FASTEST_TRANSIT`, `HIGHEST_RELIABILITY`, `LOWEST_CARBON`), incorporates live corridor disruption penalties and reefer/weight/budget/transit limits, generates grounded rationales, and applies dispatcher-approved re-routes to shipments.
- **Carrier Communications (`backend/app/comms/`):** Generates structured carrier drafts (`DETENTION_NOTICE`, `BOL_CORRECTION`, `APPOINTMENT_RESCHEDULE`, `DELAY_ESCALATION`, `DISCREPANCY_CLAIM`) grounded in live shipment BOL/PRO telemetry and open alerts, enforcing strict human-in-the-loop approval before outbound dispatch (`POST /api/v1/comms/{id}/send` returns `409 Conflict` unless `APPROVED`).
- **Inventory Alerts (`backend/app/inventory/`):** Reconciles expected ASN/BOL line counts against warehouse receiving and damage counts, computes financial exposure and shrinkage percentages, raises SKU-level alerts (`SHORTAGE`, `OVERAGE`, `DAMAGED`, `UNEXPECTED_SKU`), and rolls up resolution back to parent reconciliations.
- **Operations Control Tower UI (`frontend/`):** React 18 + TypeScript + Tailwind Control Tower with KPI summary dashboard, one-click demo scenario seeding, shipment & EDI 214 ingestion console, multi-constraint route optimizer, guarded carrier outbox, inventory reconciler, and tamper-evident audit chain verifier.

## Architecture & Engineering Standards

- **Backend (`backend/`):** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2 async ORM + Alembic migrations (`backend/alembic/`), typed settings with production fail-fast validation, pure ASGI security-header middleware, and SHA-256 hash-chained `audit_logs` (`/api/v1/audit/verify`).
- **Frontend (`frontend/`):** React 18, TypeScript, Vite, Tailwind CSS, and Vitest + Testing Library unit tests served behind unprivileged Nginx in production.
- **Privacy & AI Guardrails:** Local-first `LLMRouter` supporting offline deterministic `mock` execution, local `ollama` inference, and guarded cloud `gemini` fallback with deterministic outbound PII scrubbing (`EMAIL`, `PHONE`, `SSN`, `API_KEY`) when `LLM_REDACT_PII_FOR_CLOUD=true`.
- **Containers & CI (`.github/workflows/ci.yml`):** Multi-stage Dockerfiles, PostgreSQL (`pgvector`) + Redis Compose topology, Ruff + Mypy + Pytest checks, TypeScript + Vitest + Vite build, `npm audit`, and Trivy filesystem scanning.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the domain module architecture and API surface.

## Quickstart

### Backend (Local Dev & Tests)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Load a realistic demo workspace (5 shipments, EDI 214 exceptions, 6 carrier lanes, disruptions, pending drafts, and inventory alerts):

```bash
curl -X POST http://127.0.0.1:8000/api/v1/demo/seed
```

Verify lint, types, and tests:

```bash
ruff check app tests
mypy app
pytest -v
```

### Frontend (Local Dev & Tests)

```bash
cd frontend
npm ci
npm run dev
```

Verify typecheck, unit tests, and production bundle:

```bash
npx tsc --noEmit
npm run test
npm run build
```

### Docker Compose

```bash
docker compose up --build
```

- Frontend UI: `http://localhost:3000`
- Backend API & OpenAPI Docs: `http://localhost:8000/docs`

---

## License

Licensed under the [MIT License](LICENSE).

# AI Logistics Coordinator

> Open-source, self-hosted AI logistics coordination platform for freight tracking, shipment route optimization, carrier communications, and inventory discrepancy alerts.

**Roadmap Stage:** Phase 1 & Phase 2 Operations · **Status:** Phase 2 Hardening, Workers & Operational Memory Implemented

## Implemented Core Capabilities

- **Freight Tracking (`backend/app/tracking/`):** Ingests JSON carrier webhooks (with optional HMAC-SHA256 `X-Webhook-Signature` verification) and X12 **EDI 214** payloads (`B10`, `AT7`, `MS1`, `G62`, `L11`), normalizes carrier status codes, detects SLA ETA slips and operational exceptions (`ETA_SLIP`, `DETENTION`, `CUSTOMS_HOLD`, `WEATHER_DISRUPTION`, `PORT_CONGESTION`, `TEMPERATURE_EXCURSION`), and auto-indexes resolved exceptions into operational memory.
- **Route Optimization (`backend/app/routing/`):** Evaluates active carrier lanes across multi-constraint objectives (`BALANCED`, `LOWEST_COST`, `FASTEST_TRANSIT`, `HIGHEST_RELIABILITY`, `LOWEST_CARBON`), incorporates live corridor disruption penalties, reefer/weight/budget/transit limits, and historical operational memory context, and applies dispatcher-approved re-routes to shipments.
- **Carrier Communications (`backend/app/comms/`):** Generates structured carrier drafts grounded in live shipment BOL/PRO telemetry, open alerts, and historical operational memory, enforcing strict `409 Conflict` approval gating before dispatching via `simulated`, `smtp`, or HMAC-signed `webhook` delivery adapters with retries and receipts.
- **Inventory Alerts (`backend/app/inventory/`):** Reconciles expected ASN/BOL line counts against warehouse receiving and damage counts, computes financial exposure and shrinkage percentages, raises SKU-level alerts (`SHORTAGE`, `OVERAGE`, `DAMAGED`, `UNEXPECTED_SKU`), and rolls up resolution back to parent reconciliations.
- **Operational Memory & Async Workers (`backend/app/memory/`, `backend/app/workers/`):** Deterministic L2-normalized vector indexing & semantic search (`pgvector`-ready) for playbooks and past resolutions, plus Celery + Redis periodic SLA breach sweeps and resilient bulk EDI 214 ingestion (`/api/v1/workers/*`).
- **Auth, RBAC & Production Hardening (`backend/app/core/`):** HS256 JWT + `X-API-Key` authentication (`VIEWER`, `WAREHOUSE`, `DISPATCHER`, `WEBHOOK_INGESTOR`, `ADMIN`) with verified actor attribution in audit logs, sliding-window `RateLimitMiddleware`, optional OpenTelemetry instrumentation, and container startup migrations (`backend/entrypoint.sh`).
- **Operations Control Tower UI (`frontend/`):** React 18 + TypeScript + Tailwind Control Tower with KPI summary dashboard, one-click demo scenario seeding, Sign-In modal, shipment & EDI 214 ingestion console, route optimizer, guarded carrier outbox with delivery receipts, inventory reconciler, Memory & Ops workbench, and audit chain verifier.

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

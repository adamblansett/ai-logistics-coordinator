from typing import Any

import httpx

from app.core.config import Settings
from app.core.security import redact_pii
from app.llm.base import LLMRequest, LLMResponse


def _format_list(items: list[Any], fallback: str = "None") -> str:
    if not items:
        return fallback
    return "; ".join(str(item) for item in items)


class MockLLMProvider:
    """Offline deterministic provider that generates domain-grounded logistics text."""

    name = "mock"
    model = "deterministic-logistics-v1"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        ctx = request.context
        if request.task_type == "carrier_comm":
            content = self._render_carrier_comm(ctx)
        elif request.task_type == "route_rationale":
            content = self._render_route_rationale(ctx)
        elif request.task_type == "exception_summary":
            content = self._render_exception_summary(ctx)
        else:
            content = self._render_inventory_discrepancy(ctx)

        return LLMResponse(
            provider=self.name,
            model=self.model,
            content=content,
            pii_redacted=False,
            redacted_categories=[],
            fallback_used=False,
        )

    def _render_carrier_comm(self, ctx: dict[str, Any]) -> str:
        comm_type = str(ctx.get("comm_type", "DELAY_ESCALATION"))
        ref = str(ctx.get("reference_number", "N/A"))
        bol = str(ctx.get("bol_number", "N/A"))
        pro = str(ctx.get("pro_number", "N/A"))
        carrier = str(ctx.get("carrier_name", "Carrier Dispatch"))
        recipient = str(ctx.get("recipient_name", "Dispatch Team"))
        origin = str(ctx.get("origin", "Origin"))
        destination = str(ctx.get("destination", "Destination"))
        location = str(ctx.get("last_location", origin))
        delay_minutes = int(ctx.get("delay_minutes", 0) or 0)
        delay_hours = round(delay_minutes / 60.0, 1)
        sla_eta = str(ctx.get("sla_eta", "Scheduled SLA"))
        current_eta = str(ctx.get("current_eta", "Updated ETA pending"))
        exceptions = ctx.get("open_exceptions") or []
        alerts = ctx.get("open_inventory_alerts") or []
        notes = str(ctx.get("custom_notes", "")).strip()

        subject_map = {
            "DETENTION_NOTICE": f"Detention Notice & Clock Verification — Load {ref} (BOL {bol})",
            "BOL_CORRECTION": f"BOL / Documentation Correction Request — Load {ref} (PRO {pro})",
            "APPOINTMENT_RESCHEDULE": (
                f"Delivery Appointment Reschedule — Load {ref} ({destination})"
            ),
            "DELAY_ESCALATION": f"SLA Delay Escalation & Revised ETA — Load {ref} (BOL {bol})",
            "DISCREPANCY_CLAIM": (
                f"OS&D / Receiving Discrepancy Claim Notice — Load {ref} (BOL {bol})"
            ),
        }
        subject = subject_map.get(comm_type, f"Shipment Coordination — Load {ref} (BOL {bol})")

        lines = [
            f"SUBJECT: {subject}",
            "",
            f"Hello {recipient},",
            "",
            (
                f"We are coordinating with {carrier} regarding Shipment {ref} "
                f"(BOL: {bol} | PRO: {pro}) moving from {origin} to {destination}."
            ),
            (
                f"Current operational telemetry places the load at {location} with an SLA ETA of "
                f"{sla_eta} and current projected ETA of {current_eta} "
                f"({delay_minutes} min / {delay_hours} hr variance)."
            ),
        ]

        if comm_type == "DETENTION_NOTICE":
            lines.append(
                "Please confirm dock arrival/departure timestamps and detention authorization "
                "codes so accessorial billing can be reconciled against gate logs."
            )
        elif comm_type == "BOL_CORRECTION":
            lines.append(
                "Please apply the corrected piece count, freight class, and consignee reference "
                "details on the revised BOL prior to final delivery sign-off."
            )
        elif comm_type == "APPOINTMENT_RESCHEDULE":
            lines.append(
                f"Given the current {delay_minutes}-minute transit variance, please lock in the "
                f"next available receiving window at {destination} and confirm the appointment ID."
            )
        elif comm_type == "DISCREPANCY_CLAIM":
            lines.append(
                "Receiving reconciliation flagged physical variance on arrival. Please preserve "
                "signed POD/OSD exceptions and driver check-in records for formal claim processing."
            )
        else:
            lines.append(
                "Please provide an updated driver check-call, root-cause mitigation plan, and "
                "revised recovery ETA within 60 minutes."
            )

        if exceptions:
            lines.append(f"Active Tracking Exceptions: {_format_list(exceptions)}.")
        if alerts:
            lines.append(f"Linked Inventory Alerts: {_format_list(alerts)}.")
        if notes:
            lines.append(f"Dispatcher Notes: {notes}")

        lines.extend(["", "Thank you,", "Operations Dispatch — AI Logistics Coordinator"])
        return "\n".join(lines)

    def _render_route_rationale(self, ctx: dict[str, Any]) -> str:
        origin = str(ctx.get("origin_region", "Origin"))
        destination = str(ctx.get("destination_region", "Destination"))
        objective = str(ctx.get("objective", "BALANCED"))
        carrier = str(ctx.get("recommended_carrier_name", "Recommended Carrier"))
        scac = str(ctx.get("recommended_carrier_scac", "SCAC"))
        mode = str(ctx.get("recommended_mode", "FTL"))
        cost = float(ctx.get("estimated_cost_usd", 0.0))
        hours = int(ctx.get("estimated_transit_hours", 0))
        reliability = float(ctx.get("estimated_reliability", 0.0)) * 100.0
        carbon = float(ctx.get("estimated_carbon_kg", 0.0))
        score = float(ctx.get("composite_score", 0.0))
        disruptions = ctx.get("active_disruptions") or []
        runner_up = ctx.get("runner_up")

        parts = [
            (
                f"Selected {carrier} ({scac}, {mode}) for {origin} -> {destination} under "
                f"objective {objective} with composite score {score:.1f}/100."
            ),
            (
                f"Projected metrics: ${cost:,.2f} total cost, {hours}h transit, "
                f"{reliability:.1f}% adjusted on-time reliability, and {carbon:,.1f} kg CO2e."
            ),
        ]
        if disruptions:
            parts.append(f"Disruption adjustments applied for: {_format_list(disruptions)}.")
        else:
            parts.append("No active corridor disruptions penalized candidate lanes.")

        if isinstance(runner_up, dict):
            r_name = runner_up.get("carrier_name", "Runner-up")
            r_cost = float(runner_up.get("estimated_cost_usd", 0.0))
            r_hours = int(runner_up.get("estimated_transit_hours", 0))
            r_score = float(runner_up.get("composite_score", 0.0))
            parts.append(
                f"Outranked {r_name} (score {r_score:.1f}, ${r_cost:,.2f}, {r_hours}h) "
                "on weighted objective criteria."
            )
        return " ".join(parts)

    def _render_exception_summary(self, ctx: dict[str, Any]) -> str:
        exc_type = str(ctx.get("exception_type", "ETA_SLIP"))
        ref = str(ctx.get("reference_number", "Shipment"))
        delay = int(ctx.get("delay_minutes", 0) or 0)
        location = str(ctx.get("location", "in transit"))
        return (
            f"{exc_type} detected for {ref} near {location} ({delay} min variance vs SLA). "
            "Recommend verifying carrier check-call and evaluating alternate lane options."
        )

    def _render_inventory_discrepancy(self, ctx: dict[str, Any]) -> str:
        asn = str(ctx.get("asn_number", "ASN"))
        bol = str(ctx.get("bol_number", "BOL"))
        wh = str(ctx.get("warehouse_code", "WH"))
        expected_units = int(ctx.get("expected_total_units", 0))
        received_units = int(ctx.get("received_total_units", 0))
        damaged_units = int(ctx.get("damaged_total_units", 0))
        variance = int(ctx.get("variance_units", 0))
        shrinkage = float(ctx.get("shrinkage_pct", 0.0))
        impact = float(ctx.get("financial_impact_usd", 0.0))
        issues = ctx.get("issues") or []

        if not issues:
            return (
                f"ASN {asn} (BOL {bol}) reconciled cleanly at {wh}: "
                f"{received_units}/{expected_units} units received, 0 variance ($0.00 exposure)."
            )

        issue_summaries = [
            f"{i.get('sku')}: {i.get('alert_type')} ({i.get('variance_qty')} units, "
            f"${float(i.get('financial_impact_usd', 0.0)):,.2f})"
            for i in issues[:4]
        ]
        return (
            f"ASN {asn} (BOL {bol}) at {wh} recorded {variance} unit variance "
            f"({received_units} received vs {expected_units} expected, {damaged_units} damaged; "
            f"{shrinkage:.2f}% shrinkage, ${impact:,.2f} financial exposure). "
            f"Key exceptions: {'; '.join(issue_summaries)}. "
            "Recommend dock recount verification and carrier OS&D claim review."
        )


class OllamaLLMProvider:
    """Local-first Ollama inference provider via /api/chat."""

    name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_default_model
        self.timeout_seconds = settings.llm_timeout_seconds

    async def generate(self, request: LLMRequest) -> LLMResponse:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(url, json=payload)
            if response.status_code != 200:
                raise RuntimeError(f"Ollama returned HTTP {response.status_code}")
            data = response.json()

        content = str(data.get("message", {}).get("content", "")).strip()
        if not content:
            raise RuntimeError("Ollama returned empty completion content")

        return LLMResponse(
            provider=self.name,
            model=self.model,
            content=content,
            pii_redacted=False,
            redacted_categories=[],
            fallback_used=False,
        )


class GeminiLLMProvider:
    """Cloud Gemini provider enforcing outbound PII redaction when enabled."""

    name = "gemini"

    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.gemini_api_key.strip()
        self.model = settings.gemini_default_model
        self.redact_pii_enabled = settings.llm_redact_pii_for_cloud
        self.timeout_seconds = settings.llm_timeout_seconds

    async def generate(self, request: LLMRequest) -> LLMResponse:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY not configured")

        system_text = request.system_prompt
        user_text = request.user_prompt
        pii_redacted = False
        categories: list[str] = []

        if self.redact_pii_enabled:
            system_text, sys_cats = redact_pii(system_text)
            user_text, usr_cats = redact_pii(user_text)
            pii_redacted = True
            categories = sorted(set(sys_cats) | set(usr_cats))

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        payload = {
            "system_instruction": {"parts": [{"text": system_text}]},
            "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                url,
                params={"key": self.api_key},
                json=payload,
            )
            if response.status_code != 200:
                raise RuntimeError(f"Gemini returned HTTP {response.status_code}")
            data = response.json()

        candidates = data.get("candidates") or []
        parts = (candidates[0].get("content") or {}).get("parts") or [] if candidates else []
        content = "".join(str(part.get("text", "")) for part in parts).strip()
        if not content:
            raise RuntimeError("Gemini returned empty completion content")

        return LLMResponse(
            provider=self.name,
            model=self.model,
            content=content,
            pii_redacted=pii_redacted,
            redacted_categories=categories,
            fallback_used=False,
        )

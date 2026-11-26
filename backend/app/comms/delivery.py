import asyncio
import hashlib
import hmac
import json
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

import httpx

from app.comms.models import CarrierCommunication
from app.core.config import Settings


@dataclass(slots=True)
class DeliveryReceipt:
    external_message_id: str
    delivery_mode: str
    attempts: int
    status: str
    detail: str


async def _send_smtp(comm: CarrierCommunication, settings: Settings) -> tuple[str, str]:
    if not settings.smtp_host.strip():
        raise RuntimeError("SMTP_HOST must be configured when COMM_DELIVERY_MODE=smtp.")

    msg = EmailMessage()
    msg["Subject"] = comm.subject
    msg["From"] = settings.smtp_from_email
    msg["To"] = comm.recipient_contact
    msg.set_content(comm.body)

    def _blocking_send() -> None:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10.0) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)

    await asyncio.to_thread(_blocking_send)
    ext_id = f"SMTP-{comm.id[:8].upper()}"
    return ext_id, f"Delivered via SMTP host {settings.smtp_host}:{settings.smtp_port}"


async def _send_webhook(comm: CarrierCommunication, settings: Settings) -> tuple[str, str]:
    url = settings.carrier_webhook_url.strip()
    if not url:
        raise RuntimeError(
            "CARRIER_WEBHOOK_URL must be configured when COMM_DELIVERY_MODE=webhook."
        )

    payload_bytes = json.dumps(
        {
            "communication_id": comm.id,
            "shipment_id": comm.shipment_id,
            "comm_type": comm.comm_type,
            "channel": comm.channel,
            "recipient_name": comm.recipient_name,
            "recipient_contact": comm.recipient_contact,
            "subject": comm.subject,
            "body": comm.body,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    signature = hmac.new(
        settings.auth_secret_key.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    async with httpx.AsyncClient(timeout=settings.carrier_webhook_timeout_seconds) as client:
        response = await client.post(
            url,
            content=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Logistics-Signature": f"sha256={signature}",
            },
        )
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(f"Carrier webhook returned HTTP {response.status_code}")

        ext_id = f"WHK-{comm.id[:8].upper()}"
        try:
            resp_data = response.json()
            if isinstance(resp_data, dict) and resp_data.get("message_id"):
                ext_id = str(resp_data["message_id"])
        except Exception:
            pass
        return ext_id, f"Delivered via carrier webhook HTTP {response.status_code}"


async def deliver_communication(
    comm: CarrierCommunication,
    settings: Settings,
) -> DeliveryReceipt:
    """Dispatch an approved carrier communication via simulated, SMTP, or webhook adapter."""
    mode = settings.comm_delivery_mode.lower()
    if mode == "simulated":
        return DeliveryReceipt(
            external_message_id=f"MSG-{comm.id[:8].upper()}",
            delivery_mode="simulated",
            attempts=1,
            status="DELIVERED",
            detail="Recorded in local simulated carrier outbox.",
        )

    max_attempts = max(1, settings.delivery_max_retries)
    last_error = ""
    for attempt in range(1, max_attempts + 1):
        try:
            if mode == "smtp":
                ext_id, detail = await _send_smtp(comm, settings)
            elif mode == "webhook":
                ext_id, detail = await _send_webhook(comm, settings)
            else:
                raise RuntimeError(f"Unsupported COMM_DELIVERY_MODE: {mode}")
            return DeliveryReceipt(
                external_message_id=ext_id,
                delivery_mode=mode,
                attempts=attempt,
                status="DELIVERED",
                detail=detail,
            )
        except Exception as exc:
            last_error = str(exc)
            if attempt < max_attempts:
                await asyncio.sleep(0.05 * attempt)

    raise RuntimeError(
        f"Outbound {mode} delivery failed after {max_attempts} attempt(s): {last_error}"
    )

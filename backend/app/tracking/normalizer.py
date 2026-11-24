from dataclasses import dataclass
from datetime import UTC, datetime

from app.db.base import ensure_utc, utcnow
from app.tracking.schemas import WebhookEventCreate

_EDI_STATUS_MAP: dict[str, str] = {
    "X3": "PICKED_UP",
    "AF": "IN_TRANSIT",
    "X6": "IN_TRANSIT",
    "AG": "IN_TRANSIT",
    "SD": "DELAYED",
    "A3": "EXCEPTION",
    "CD": "EXCEPTION",
    "NS": "EXCEPTION",
    "X1": "OUT_FOR_DELIVERY",
    "D1": "DELIVERED",
    "X2": "DELIVERED",
}

_EDI_REASON_MAP: dict[str, str] = {
    "BG": "WEATHER",
    "W1": "WEATHER",
    "P1": "PORT_CONGESTION",
    "PC": "PORT_CONGESTION",
    "BD": "MECHANICAL",
    "M1": "MECHANICAL",
    "DT": "DETENTION",
    "D1": "DETENTION",
    "CH": "CUSTOMS_HOLD",
    "C1": "CUSTOMS_HOLD",
    "TC": "TEMP_EXCURSION",
}

_WEBHOOK_STATUS_MAP: dict[str, tuple[str, str | None]] = {
    "PLANNED": ("PLANNED", None),
    "PICKED_UP": ("PICKED_UP", None),
    "PICKUP": ("PICKED_UP", None),
    "X3": ("PICKED_UP", None),
    "IN_TRANSIT": ("IN_TRANSIT", None),
    "TRANSIT": ("IN_TRANSIT", None),
    "AF": ("IN_TRANSIT", None),
    "X6": ("IN_TRANSIT", None),
    "DELAYED": ("DELAYED", None),
    "DELAY": ("DELAYED", None),
    "SD": ("DELAYED", None),
    "WEATHER_DELAY": ("DELAYED", "WEATHER"),
    "WEATHER": ("DELAYED", "WEATHER"),
    "PORT_CONGESTION": ("DELAYED", "PORT_CONGESTION"),
    "CUSTOMS_HOLD": ("EXCEPTION", "CUSTOMS_HOLD"),
    "DETENTION": ("DELAYED", "DETENTION"),
    "MECHANICAL": ("EXCEPTION", "MECHANICAL"),
    "TEMP_EXCURSION": ("EXCEPTION", "TEMP_EXCURSION"),
    "TEMPERATURE_EXCURSION": ("EXCEPTION", "TEMP_EXCURSION"),
    "EXCEPTION": ("EXCEPTION", None),
    "OUT_FOR_DELIVERY": ("OUT_FOR_DELIVERY", None),
    "X1": ("OUT_FOR_DELIVERY", None),
    "DELIVERED": ("DELIVERED", None),
    "D1": ("DELIVERED", None),
}

_WEBHOOK_REASON_ALIASES: dict[str, str] = {
    "WEATHER": "WEATHER",
    "WEATHER_DELAY": "WEATHER",
    "STORM": "WEATHER",
    "PORT_CONGESTION": "PORT_CONGESTION",
    "PORT": "PORT_CONGESTION",
    "DETENTION": "DETENTION",
    "DOCK_DETENTION": "DETENTION",
    "CUSTOMS": "CUSTOMS_HOLD",
    "CUSTOMS_HOLD": "CUSTOMS_HOLD",
    "TEMP_EXCURSION": "TEMP_EXCURSION",
    "TEMPERATURE_EXCURSION": "TEMP_EXCURSION",
    "MECHANICAL": "MECHANICAL",
    "BREAKDOWN": "MECHANICAL",
}


@dataclass(slots=True)
class NormalizedEvent:
    source_format: str
    raw_code: str
    normalized_status: str
    reason_code: str | None
    location: str
    event_timestamp: datetime
    reported_eta: datetime | None
    notes: str
    carrier_scac: str | None = None
    bol_number: str | None = None
    pro_number: str | None = None
    reference_number: str | None = None


def _parse_edi_datetime(date_str: str, time_str: str) -> datetime | None:
    clean_date = date_str.strip()
    if len(clean_date) != 8 or not clean_date.isdigit():
        return None
    clean_time = time_str.strip()
    hhmm = clean_time[:4] if len(clean_time) >= 4 and clean_time[:4].isdigit() else "0000"
    try:
        parsed = datetime.strptime(f"{clean_date}{hhmm}", "%Y%m%d%H%M")
        return parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


def parse_edi_214(raw_edi: str) -> NormalizedEvent:
    """Parse an X12 EDI 214 carrier shipment status payload into a NormalizedEvent."""
    cleaned = raw_edi.strip()
    if not cleaned:
        raise ValueError("EDI 214 payload is empty.")

    element_sep = "*"
    segment_term = "~"
    if cleaned.startswith("ISA") and len(cleaned) >= 106:
        element_sep = cleaned[3]
        segment_term = cleaned[105]

    if segment_term in cleaned:
        raw_segments = [seg.strip() for seg in cleaned.split(segment_term) if seg.strip()]
    else:
        raw_segments = [seg.strip() for seg in cleaned.splitlines() if seg.strip()]

    b10_parts: list[str] | None = None
    at7_parts: list[str] | None = None
    ms1_parts: list[str] | None = None
    g62_parts: list[str] | None = None
    l11_ref: str | None = None

    for seg in raw_segments:
        parts = [p.strip() for p in seg.split(element_sep)]
        tag = parts[0].upper()
        if tag == "B10" and b10_parts is None:
            b10_parts = parts
        elif tag == "AT7" and at7_parts is None:
            at7_parts = parts
        elif tag == "MS1" and ms1_parts is None:
            ms1_parts = parts
        elif tag == "G62" and len(parts) >= 3 and parts[1] in {"17", "68", "69"}:
            g62_parts = parts
        elif tag == "L11" and len(parts) >= 2 and parts[1] and l11_ref is None:
            l11_ref = parts[1]

    if b10_parts is None:
        raise ValueError("Invalid EDI 214 payload: missing required B10 segment.")
    if at7_parts is None:
        raise ValueError("Invalid EDI 214 payload: missing required AT7 segment.")

    def _elem(parts: list[str], idx: int) -> str:
        return parts[idx].strip() if idx < len(parts) else ""

    pro_number = _elem(b10_parts, 1) or None
    bol_number = _elem(b10_parts, 2) or None
    carrier_scac = _elem(b10_parts, 3).upper() or None
    reference_number = l11_ref or bol_number or pro_number

    elem1 = _elem(at7_parts, 1).upper()
    elem2 = _elem(at7_parts, 2).upper()
    elem3 = _elem(at7_parts, 3).upper()
    elem4 = _elem(at7_parts, 4).upper()
    elem5 = _elem(at7_parts, 5)
    elem6 = _elem(at7_parts, 6)

    if elem1 in _EDI_STATUS_MAP:
        raw_code = elem1
        reason_candidates = [elem2, elem4]
    elif elem3 in _EDI_STATUS_MAP:
        raw_code = elem3
        reason_candidates = [elem4, elem2]
    else:
        raw_code = elem1 or elem3
        reason_candidates = [elem2, elem4]

    if not raw_code:
        raise ValueError("Invalid EDI 214 payload: AT7 segment contains no status code.")

    normalized_status = _EDI_STATUS_MAP.get(raw_code, "IN_TRANSIT")
    reason_code: str | None = None
    for candidate in reason_candidates:
        if candidate in _EDI_REASON_MAP:
            reason_code = _EDI_REASON_MAP[candidate]
            break
    if reason_code is None:
        for candidate in reason_candidates:
            if candidate and candidate != "NS":
                reason_code = candidate
                break

    event_timestamp = _parse_edi_datetime(elem5, elem6) or utcnow()

    location = "In Transit"
    if ms1_parts is not None:
        city = _elem(ms1_parts, 1).title()
        state = _elem(ms1_parts, 2).upper()
        country = _elem(ms1_parts, 3).upper()
        loc_bits = [bit for bit in (city, state) if bit]
        if loc_bits:
            location = ", ".join(loc_bits)
            if country and country != "US":
                location = f"{location} ({country})"

    reported_eta: datetime | None = None
    if g62_parts is not None:
        reported_eta = _parse_edi_datetime(_elem(g62_parts, 2), _elem(g62_parts, 4))

    notes_bits = [f"EDI 214 AT7={raw_code}"]
    if reason_code:
        notes_bits.append(f"Reason={reason_code}")
    if carrier_scac:
        notes_bits.append(f"SCAC={carrier_scac}")

    return NormalizedEvent(
        source_format="EDI_214",
        raw_code=raw_code,
        normalized_status=normalized_status,
        reason_code=reason_code,
        location=location,
        event_timestamp=event_timestamp,
        reported_eta=reported_eta,
        notes="; ".join(notes_bits),
        carrier_scac=carrier_scac,
        bol_number=bol_number,
        pro_number=pro_number,
        reference_number=reference_number,
    )


def normalize_webhook_event(payload: WebhookEventCreate) -> NormalizedEvent:
    """Normalize a JSON carrier webhook payload into canonical tracking state."""
    raw_token = (payload.event_code or payload.status or "IN_TRANSIT").strip().upper()
    canonical_key = raw_token.replace("-", "_").replace(" ", "_")

    if canonical_key in _WEBHOOK_STATUS_MAP:
        normalized_status, mapped_reason = _WEBHOOK_STATUS_MAP[canonical_key]
    elif canonical_key in _EDI_STATUS_MAP:
        normalized_status = _EDI_STATUS_MAP[canonical_key]
        mapped_reason = None
    else:
        normalized_status = "IN_TRANSIT"
        mapped_reason = None

    explicit_reason: str | None = None
    if payload.reason_code:
        reason_key = payload.reason_code.strip().upper().replace("-", "_").replace(" ", "_")
        explicit_reason = _WEBHOOK_REASON_ALIASES.get(
            reason_key, _EDI_REASON_MAP.get(reason_key, reason_key)
        )

    reason_code = explicit_reason or mapped_reason
    event_ts = ensure_utc(payload.event_timestamp) if payload.event_timestamp else utcnow()
    reported_eta = ensure_utc(payload.reported_eta) if payload.reported_eta else None

    return NormalizedEvent(
        source_format="WEBHOOK_JSON",
        raw_code=raw_token,
        normalized_status=normalized_status,
        reason_code=reason_code,
        location=payload.location.strip() or "In Transit",
        event_timestamp=event_ts,
        reported_eta=reported_eta,
        notes=payload.notes.strip() or f"Webhook event {raw_token}",
    )

from dataclasses import dataclass

from app.inventory.schemas import ExpectedLineItem, ReceivedLineItem


@dataclass(slots=True)
class DiscrepancyFinding:
    sku: str
    description: str
    alert_type: str
    severity: str
    expected_qty: int
    received_qty: int
    damaged_qty: int
    variance_qty: int
    financial_impact_usd: float


@dataclass(slots=True)
class ReconciliationResult:
    expected_total_units: int
    received_total_units: int
    damaged_total_units: int
    variance_units: int
    shrinkage_pct: float
    financial_impact_usd: float
    issues: list[DiscrepancyFinding]


def _classify_severity(
    *,
    alert_type: str,
    impact_usd: float,
    shrinkage_pct: float,
) -> str:
    if impact_usd >= 5000.0 or shrinkage_pct >= 10.0:
        return "CRITICAL"
    if impact_usd >= 1500.0 or shrinkage_pct >= 5.0:
        return "HIGH"
    if impact_usd >= 300.0 or alert_type in {"DAMAGED", "UNEXPECTED_SKU"}:
        return "MEDIUM"
    return "LOW"


def reconcile_counts(
    expected_lines: list[ExpectedLineItem],
    received_lines: list[ReceivedLineItem],
) -> ReconciliationResult:
    """Deterministically reconcile expected ASN/BOL quantities against warehouse receiving."""
    expected_agg: dict[str, dict[str, float | int | str]] = {}
    for exp_item in expected_lines:
        sku = exp_item.sku.strip().upper()
        if sku not in expected_agg:
            expected_agg[sku] = {
                "description": exp_item.description.strip() or sku,
                "qty": exp_item.expected_qty,
                "unit_cost": float(exp_item.unit_cost_usd),
            }
        else:
            expected_agg[sku]["qty"] = int(expected_agg[sku]["qty"]) + exp_item.expected_qty
            if exp_item.unit_cost_usd > 0:
                expected_agg[sku]["unit_cost"] = float(exp_item.unit_cost_usd)

    received_agg: dict[str, dict[str, float | int | str]] = {}
    for rec_item in received_lines:
        sku = rec_item.sku.strip().upper()
        if sku not in received_agg:
            received_agg[sku] = {
                "description": rec_item.description.strip(),
                "qty": rec_item.received_qty,
                "damaged": rec_item.damaged_qty,
                "unit_cost": (
                    float(rec_item.unit_cost_usd) if rec_item.unit_cost_usd is not None else 0.0
                ),
            }
        else:
            received_agg[sku]["qty"] = int(received_agg[sku]["qty"]) + rec_item.received_qty
            received_agg[sku]["damaged"] = (
                int(received_agg[sku]["damaged"]) + rec_item.damaged_qty
            )
            if rec_item.unit_cost_usd is not None and rec_item.unit_cost_usd > 0:
                received_agg[sku]["unit_cost"] = float(rec_item.unit_cost_usd)

    expected_total_units = sum(int(val["qty"]) for val in expected_agg.values())
    received_total_units = sum(int(val["qty"]) for val in received_agg.values())
    damaged_total_units = sum(int(val["damaged"]) for val in received_agg.values())
    variance_units = received_total_units - expected_total_units

    issues: list[DiscrepancyFinding] = []
    lost_units_on_expected = 0

    for sku, exp_data in expected_agg.items():
        exp_qty = int(exp_data["qty"])
        desc = str(exp_data["description"])
        unit_cost = float(exp_data["unit_cost"])

        rec_data = received_agg.get(sku)
        rec_qty = int(rec_data["qty"]) if rec_data else 0
        dmg_qty = int(rec_data["damaged"]) if rec_data else 0

        if rec_qty < exp_qty:
            short_units = exp_qty - rec_qty
            lost_units_on_expected += short_units
            impact = round(short_units * unit_cost, 2)
            sku_shrink = (short_units / exp_qty * 100.0) if exp_qty > 0 else 0.0
            issues.append(
                DiscrepancyFinding(
                    sku=sku,
                    description=desc,
                    alert_type="SHORTAGE",
                    severity=_classify_severity(
                        alert_type="SHORTAGE",
                        impact_usd=impact,
                        shrinkage_pct=sku_shrink,
                    ),
                    expected_qty=exp_qty,
                    received_qty=rec_qty,
                    damaged_qty=dmg_qty,
                    variance_qty=rec_qty - exp_qty,
                    financial_impact_usd=impact,
                )
            )
        elif rec_qty > exp_qty:
            over_units = rec_qty - exp_qty
            impact = round(over_units * unit_cost, 2)
            issues.append(
                DiscrepancyFinding(
                    sku=sku,
                    description=desc,
                    alert_type="OVERAGE",
                    severity=_classify_severity(
                        alert_type="OVERAGE",
                        impact_usd=impact,
                        shrinkage_pct=0.0,
                    ),
                    expected_qty=exp_qty,
                    received_qty=rec_qty,
                    damaged_qty=dmg_qty,
                    variance_qty=over_units,
                    financial_impact_usd=impact,
                )
            )

        if dmg_qty > 0:
            counted_damaged = min(dmg_qty, rec_qty) if rec_qty > 0 else dmg_qty
            lost_units_on_expected += counted_damaged
            dmg_impact = round(dmg_qty * unit_cost, 2)
            denom = max(exp_qty, rec_qty, 1)
            dmg_shrink = (dmg_qty / denom) * 100.0
            issues.append(
                DiscrepancyFinding(
                    sku=sku,
                    description=desc,
                    alert_type="DAMAGED",
                    severity=_classify_severity(
                        alert_type="DAMAGED",
                        impact_usd=dmg_impact,
                        shrinkage_pct=dmg_shrink,
                    ),
                    expected_qty=exp_qty,
                    received_qty=rec_qty,
                    damaged_qty=dmg_qty,
                    variance_qty=-dmg_qty,
                    financial_impact_usd=dmg_impact,
                )
            )

    for sku, rec_data in received_agg.items():
        if sku in expected_agg:
            continue
        rec_qty = int(rec_data["qty"])
        dmg_qty = int(rec_data["damaged"])
        unit_cost = float(rec_data["unit_cost"])
        desc = str(rec_data["description"]) or f"Unexpected SKU {sku}"
        impact = round(rec_qty * unit_cost, 2)
        issues.append(
            DiscrepancyFinding(
                sku=sku,
                description=desc,
                alert_type="UNEXPECTED_SKU",
                severity=_classify_severity(
                    alert_type="UNEXPECTED_SKU",
                    impact_usd=impact,
                    shrinkage_pct=0.0,
                ),
                expected_qty=0,
                received_qty=rec_qty,
                damaged_qty=dmg_qty,
                variance_qty=rec_qty,
                financial_impact_usd=impact,
            )
        )

    shrinkage_pct = (
        round((lost_units_on_expected / expected_total_units) * 100.0, 2)
        if expected_total_units > 0
        else 0.0
    )
    financial_impact_usd = round(sum(item.financial_impact_usd for item in issues), 2)

    return ReconciliationResult(
        expected_total_units=expected_total_units,
        received_total_units=received_total_units,
        damaged_total_units=damaged_total_units,
        variance_units=variance_units,
        shrinkage_pct=shrinkage_pct,
        financial_impact_usd=financial_impact_usd,
        issues=issues,
    )

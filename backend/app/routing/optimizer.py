from dataclasses import dataclass

from app.routing.models import CarrierLane, DisruptionAlert

_SEVERITY_PENALTY: dict[str, float] = {
    "LOW": 0.03,
    "MEDIUM": 0.07,
    "HIGH": 0.14,
    "CRITICAL": 0.25,
}

# Objective weights: (cost, transit, reliability, carbon)
_OBJECTIVE_WEIGHTS: dict[str, tuple[float, float, float, float]] = {
    "BALANCED": (0.30, 0.25, 0.30, 0.15),
    "LOWEST_COST": (0.65, 0.15, 0.15, 0.05),
    "FASTEST_TRANSIT": (0.15, 0.65, 0.15, 0.05),
    "HIGHEST_RELIABILITY": (0.15, 0.15, 0.65, 0.05),
    "LOWEST_CARBON": (0.15, 0.10, 0.15, 0.60),
}


@dataclass(slots=True)
class ScoredOption:
    lane_id: str
    carrier_scac: str
    carrier_name: str
    mode: str
    estimated_cost_usd: float
    estimated_transit_hours: int
    estimated_reliability: float
    estimated_carbon_kg: float
    composite_score: float


def _norm_lower_better(value: float, min_val: float, max_val: float) -> float:
    if max_val <= min_val:
        return 1.0
    return (max_val - value) / (max_val - min_val)


def _norm_higher_better(value: float, min_val: float, max_val: float) -> float:
    if max_val <= min_val:
        return 1.0
    return (value - min_val) / (max_val - min_val)


def evaluate_lanes(
    lanes: list[CarrierLane],
    disruptions: list[DisruptionAlert],
    *,
    weight_lbs: float,
    temperature_controlled: bool,
    objective: str = "BALANCED",
    max_budget_usd: float | None = None,
    max_transit_hours: int | None = None,
) -> list[ScoredOption]:
    """Score eligible carrier lanes under active disruptions and constraints."""
    active_disruptions = [d for d in disruptions if d.active]
    total_cost_pct = sum(d.cost_surcharge_pct for d in active_disruptions)
    total_added_hours = sum(d.added_transit_hours for d in active_disruptions)
    disruption_rel_penalty = sum(
        _SEVERITY_PENALTY.get(d.severity.upper(), 0.07) for d in active_disruptions
    )

    candidates: list[dict[str, float | int | str]] = []
    for lane in lanes:
        if not lane.active:
            continue
        if weight_lbs > lane.max_weight_lbs:
            continue
        if temperature_controlled and not lane.supports_reefer:
            continue

        effective_cost = round(
            lane.base_rate_usd
            * (1.0 + lane.fuel_surcharge_pct / 100.0)
            * (1.0 + total_cost_pct / 100.0),
            2,
        )
        effective_hours = int(lane.transit_hours + total_added_hours)
        raw_rel = lane.on_time_rate - (lane.disruption_risk_score * 0.15) - disruption_rel_penalty
        effective_rel = round(max(0.1, min(0.999, raw_rel)), 4)
        estimated_carbon = round(
            lane.carbon_kg_per_ton_mile * (weight_lbs / 2000.0) * (lane.transit_hours * 42.0),
            2,
        )

        if max_budget_usd is not None and effective_cost > max_budget_usd:
            continue
        if max_transit_hours is not None and effective_hours > max_transit_hours:
            continue

        candidates.append(
            {
                "lane_id": lane.id,
                "carrier_scac": lane.carrier_scac,
                "carrier_name": lane.carrier_name,
                "mode": lane.mode,
                "cost": effective_cost,
                "hours": effective_hours,
                "rel": effective_rel,
                "carbon": estimated_carbon,
            }
        )

    if not candidates:
        return []

    costs = [float(c["cost"]) for c in candidates]
    hours_list = [float(c["hours"]) for c in candidates]
    rels = [float(c["rel"]) for c in candidates]
    carbons = [float(c["carbon"]) for c in candidates]

    min_cost, max_cost = min(costs), max(costs)
    min_hours, max_hours = min(hours_list), max(hours_list)
    min_rel, max_rel = min(rels), max(rels)
    min_carbon, max_carbon = min(carbons), max(carbons)

    w_cost, w_transit, w_rel, w_carbon = _OBJECTIVE_WEIGHTS.get(
        objective.upper(), _OBJECTIVE_WEIGHTS["BALANCED"]
    )

    scored: list[ScoredOption] = []
    for c in candidates:
        cost_val = float(c["cost"])
        hours_val = int(c["hours"])
        rel_val = float(c["rel"])
        carbon_val = float(c["carbon"])

        n_cost = _norm_lower_better(cost_val, min_cost, max_cost)
        n_hours = _norm_lower_better(float(hours_val), min_hours, max_hours)
        n_rel = _norm_higher_better(rel_val, min_rel, max_rel)
        n_carbon = _norm_lower_better(carbon_val, min_carbon, max_carbon)

        composite = round(
            100.0
            * (
                (w_cost * n_cost)
                + (w_transit * n_hours)
                + (w_rel * n_rel)
                + (w_carbon * n_carbon)
            ),
            2,
        )
        scored.append(
            ScoredOption(
                lane_id=str(c["lane_id"]),
                carrier_scac=str(c["carrier_scac"]),
                carrier_name=str(c["carrier_name"]),
                mode=str(c["mode"]),
                estimated_cost_usd=cost_val,
                estimated_transit_hours=hours_val,
                estimated_reliability=rel_val,
                estimated_carbon_kg=carbon_val,
                composite_score=composite,
            )
        )

    scored.sort(
        key=lambda item: (
            -item.composite_score,
            item.estimated_cost_usd,
            item.estimated_transit_hours,
            -item.estimated_reliability,
            item.carrier_scac,
        )
    )
    return scored

import { useState } from 'react';
import { AlertTriangle, Check, Plus, Route, ShieldAlert, X } from 'lucide-react';
import { api } from '../api/client';
import type {
  CarrierLane,
  DisruptionAlert,
  RouteRecommendation,
  Shipment,
} from '../types/logistics';
import { StatusBadge } from './StatusBadge';

interface RoutingPanelProps {
  shipments: Shipment[];
  lanes: CarrierLane[];
  disruptions: DisruptionAlert[];
  recommendations: RouteRecommendation[];
  onRefresh: () => Promise<void>;
  onError: (message: string) => void;
}

export function RoutingPanel({
  shipments,
  lanes,
  disruptions,
  recommendations,
  onRefresh,
  onError,
}: RoutingPanelProps) {
  const [shipmentId, setShipmentId] = useState('');
  const [originRegion, setOriginRegion] = useState('Los Angeles, CA');
  const [destinationRegion, setDestinationRegion] = useState('Chicago, IL');
  const [objective, setObjective] = useState('BALANCED');
  const [weightLbs, setWeightLbs] = useState('32000');
  const [reeferOnly, setReeferOnly] = useState(false);
  const [maxBudget, setMaxBudget] = useState('');
  const [maxHours, setMaxHours] = useState('');
  const [busy, setBusy] = useState(false);

  const [showAddDisruption, setShowAddDisruption] = useState(false);
  const [disRegion, setDisRegion] = useState('Chicago, IL');
  const [disType, setDisType] = useState('WEATHER');
  const [disSeverity, setDisSeverity] = useState('HIGH');
  const [disHours, setDisHours] = useState('6');
  const [disPct, setDisPct] = useState('5');
  const [disDesc, setDisDesc] = useState('Heavy ice storm impacting terminal gate turn times.');

  async function handleOptimize(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const payload: Record<string, unknown> = {
        objective,
        actor: 'dispatcher-ui',
      };
      if (shipmentId) {
        payload.shipment_id = shipmentId;
      } else {
        payload.origin_region = originRegion;
        payload.destination_region = destinationRegion;
        payload.weight_lbs = Number(weightLbs) || 15000;
        payload.temperature_controlled = reeferOnly;
      }
      if (maxBudget.trim()) payload.max_budget_usd = Number(maxBudget);
      if (maxHours.trim()) payload.max_transit_hours = Number(maxHours);

      await api.optimizeRoute(payload);
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Route optimization failed');
    } finally {
      setBusy(false);
    }
  }

  async function handleDecision(recId: string, decision: 'APPROVED' | 'REJECTED') {
    setBusy(true);
    try {
      await api.decideRecommendation(
        recId,
        decision,
        decision === 'APPROVED' ? 'Approved in Route Optimizer' : 'Rejected by dispatcher'
      );
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to decide recommendation');
    } finally {
      setBusy(false);
    }
  }

  async function handleToggleDisruption(d: DisruptionAlert) {
    setBusy(true);
    try {
      await api.toggleDisruption(d.id, !d.active);
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to toggle disruption');
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateDisruption(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.createDisruption({
        region: disRegion,
        disruption_type: disType,
        severity: disSeverity,
        added_transit_hours: Number(disHours) || 0,
        cost_surcharge_pct: Number(disPct) || 0,
        description: disDesc,
        active: true,
        actor: 'dispatcher-ui',
      });
      setShowAddDisruption(false);
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to create disruption');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-12">
        {/* Route Optimizer Form */}
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-5">
          <div className="flex items-center gap-2">
            <Route className="h-4 w-4 text-indigo-600" />
            <h2 className="text-sm font-semibold text-slate-900">
              Multi-Constraint Route Optimizer
            </h2>
          </div>

          <form onSubmit={(e) => void handleOptimize(e)} className="mt-4 space-y-3 text-xs">
            <div>
              <label className="block font-medium text-slate-700">
                Target Shipment (optional — overrides corridor &amp; cargo specs)
              </label>
              <select
                aria-label="Target Shipment"
                value={shipmentId}
                onChange={(e) => setShipmentId(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-2.5 py-1.5"
              >
                <option value="">Custom Corridor Query</option>
                {shipments.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.reference_number} ({s.origin} → {s.destination}
                    {s.temperature_controlled ? ', Reefer' : ''})
                  </option>
                ))}
              </select>
            </div>

            {!shipmentId && (
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-medium text-slate-700">Origin Region</label>
                  <input
                    required
                    value={originRegion}
                    onChange={(e) => setOriginRegion(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-300 px-2.5 py-1.5"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700">Destination Region</label>
                  <input
                    required
                    value={destinationRegion}
                    onChange={(e) => setDestinationRegion(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-300 px-2.5 py-1.5"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700">Weight (lbs)</label>
                  <input
                    type="number"
                    min={100}
                    value={weightLbs}
                    onChange={(e) => setWeightLbs(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-300 px-2.5 py-1.5"
                  />
                </div>
                <label className="mt-5 flex items-center gap-2 font-medium text-slate-700">
                  <input
                    type="checkbox"
                    checked={reeferOnly}
                    onChange={(e) => setReeferOnly(e.target.checked)}
                  />
                  Require Reefer
                </label>
              </div>
            )}

            <div className="grid grid-cols-3 gap-2">
              <div className="col-span-3 sm:col-span-1">
                <label className="block font-medium text-slate-700">Objective</label>
                <select
                  aria-label="Optimization Objective"
                  value={objective}
                  onChange={(e) => setObjective(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5"
                >
                  <option value="BALANCED">BALANCED</option>
                  <option value="LOWEST_COST">LOWEST COST</option>
                  <option value="FASTEST_TRANSIT">FASTEST TRANSIT</option>
                  <option value="HIGHEST_RELIABILITY">HIGHEST RELIABILITY</option>
                  <option value="LOWEST_CARBON">LOWEST CARBON</option>
                </select>
              </div>
              <div>
                <label className="block font-medium text-slate-700">Max Budget ($)</label>
                <input
                  type="number"
                  min={1}
                  placeholder="Optional"
                  value={maxBudget}
                  onChange={(e) => setMaxBudget(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700">Max Hours</label>
                <input
                  type="number"
                  min={1}
                  placeholder="Optional"
                  value={maxHours}
                  onChange={(e) => setMaxHours(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-lg bg-indigo-600 py-2 font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
            >
              Run Route Optimization
            </button>
          </form>

          {/* Disruption Alerts */}
          <div className="mt-6 border-t border-slate-200 pt-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <ShieldAlert className="h-4 w-4 text-amber-600" />
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-700">
                  Corridor Disruptions ({disruptions.length})
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowAddDisruption((p) => !p)}
                className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600"
              >
                <Plus className="h-3.5 w-3.5" />
                Add Disruption
              </button>
            </div>

            {showAddDisruption && (
              <form
                onSubmit={(e) => void handleCreateDisruption(e)}
                className="mt-2 space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs"
              >
                <div className="grid grid-cols-3 gap-2">
                  <input
                    required
                    value={disRegion}
                    onChange={(e) => setDisRegion(e.target.value)}
                    placeholder="Region"
                    className="rounded border border-slate-300 px-2 py-1"
                  />
                  <select
                    value={disType}
                    onChange={(e) => setDisType(e.target.value)}
                    className="rounded border border-slate-300 px-2 py-1"
                  >
                    <option value="WEATHER">WEATHER</option>
                    <option value="PORT_CONGESTION">PORT_CONGESTION</option>
                    <option value="HIGHWAY_CLOSURE">HIGHWAY_CLOSURE</option>
                  </select>
                  <select
                    value={disSeverity}
                    onChange={(e) => setDisSeverity(e.target.value)}
                    className="rounded border border-slate-300 px-2 py-1"
                  >
                    <option value="LOW">LOW</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="HIGH">HIGH</option>
                    <option value="CRITICAL">CRITICAL</option>
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="number"
                    value={disHours}
                    onChange={(e) => setDisHours(e.target.value)}
                    placeholder="+Transit hrs"
                    className="rounded border border-slate-300 px-2 py-1"
                  />
                  <input
                    type="number"
                    value={disPct}
                    onChange={(e) => setDisPct(e.target.value)}
                    placeholder="+Cost %"
                    className="rounded border border-slate-300 px-2 py-1"
                  />
                </div>
                <input
                  required
                  value={disDesc}
                  onChange={(e) => setDisDesc(e.target.value)}
                  className="w-full rounded border border-slate-300 px-2 py-1"
                />
                <button
                  type="submit"
                  className="w-full rounded bg-amber-600 py-1.5 font-semibold text-white"
                >
                  Save Disruption Alert
                </button>
              </form>
            )}

            <div className="mt-2 space-y-2">
              {disruptions.map((d) => (
                <div
                  key={d.id}
                  className="flex items-start justify-between gap-2 rounded-lg border border-slate-200 p-2.5 text-xs"
                >
                  <div>
                    <div className="flex items-center gap-1.5">
                      <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
                      <span className="font-semibold text-slate-900">{d.region}</span>
                      <StatusBadge value={d.severity} />
                    </div>
                    <p className="mt-1 text-[11px] text-slate-600">
                      +{d.added_transit_hours}h · +{d.cost_surcharge_pct}% cost — {d.description}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void handleToggleDisruption(d)}
                    className={`rounded px-2 py-1 text-[11px] font-semibold ${
                      d.active
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    {d.active ? 'Active' : 'Muted'}
                  </button>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Recommendations & Lanes */}
        <section className="space-y-6 lg:col-span-7">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900">
              Route Recommendations ({recommendations.length})
            </h3>
            <div className="mt-3 space-y-3">
              {recommendations.length === 0 ? (
                <p className="text-xs text-slate-500">
                  Run the optimizer to evaluate active carrier lanes and generate recommendations.
                </p>
              ) : (
                recommendations.map((rec) => (
                  <div
                    key={rec.id}
                    className="rounded-lg border border-slate-200 bg-slate-50/70 p-4 text-xs"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-slate-900">
                            {rec.recommended_carrier_name} ({rec.recommended_carrier_scac})
                          </span>
                          <StatusBadge value={rec.status} />
                          <span className="rounded bg-indigo-100 px-2 py-0.5 text-[10px] font-semibold text-indigo-800">
                            {rec.objective}
                          </span>
                        </div>
                        <p className="mt-0.5 text-slate-600">
                          {rec.origin_region} → {rec.destination_region} ({rec.recommended_mode})
                        </p>
                      </div>
                      <div className="text-right">
                        <span className="text-base font-bold text-indigo-700">
                          {rec.composite_score.toFixed(1)}
                        </span>
                        <span className="ml-1 text-[11px] text-slate-500">/ 100</span>
                      </div>
                    </div>

                    <div className="mt-2 grid grid-cols-4 gap-2 rounded bg-white p-2 text-center border border-slate-200">
                      <div>
                        <p className="text-[10px] text-slate-500">Cost</p>
                        <p className="font-semibold text-slate-900">
                          ${rec.estimated_cost_usd.toLocaleString()}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-slate-500">Transit</p>
                        <p className="font-semibold text-slate-900">
                          {rec.estimated_transit_hours}h
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-slate-500">Reliability</p>
                        <p className="font-semibold text-slate-900">
                          {(rec.estimated_reliability * 100).toFixed(1)}%
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-slate-500">CO2e</p>
                        <p className="font-semibold text-slate-900">
                          {rec.estimated_carbon_kg.toFixed(0)} kg
                        </p>
                      </div>
                    </div>

                    <p className="mt-2 leading-relaxed text-slate-700">{rec.rationale}</p>

                    {rec.alternatives.length > 1 && (
                      <div className="mt-2 text-[11px] text-slate-500">
                        Alternatives:{' '}
                        {rec.alternatives
                          .slice(1, 3)
                          .map(
                            (alt) =>
                              `${alt.carrier_scac} ($${alt.estimated_cost_usd.toLocaleString()}, ${alt.estimated_transit_hours}h, score ${alt.composite_score})`
                          )
                          .join(' · ')}
                      </div>
                    )}

                    {rec.status === 'PENDING_REVIEW' && (
                      <div className="mt-3 flex items-center gap-2">
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void handleDecision(rec.id, 'APPROVED')}
                          className="inline-flex items-center gap-1 rounded-md bg-emerald-600 px-3 py-1.5 font-semibold text-white hover:bg-emerald-700"
                        >
                          <Check className="h-3.5 w-3.5" />
                          Approve Route
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void handleDecision(rec.id, 'REJECTED')}
                          className="inline-flex items-center gap-1 rounded-md border border-rose-300 bg-white px-3 py-1.5 font-semibold text-rose-700 hover:bg-rose-50"
                        >
                          <X className="h-3.5 w-3.5" />
                          Reject
                        </button>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Carrier Lanes Table */}
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900">
              Configured Carrier Lanes ({lanes.length})
            </h3>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-200 text-[11px] uppercase text-slate-500">
                  <tr>
                    <th className="py-2 pr-3">Carrier</th>
                    <th className="py-2 pr-3">Corridor</th>
                    <th className="py-2 pr-3">Mode</th>
                    <th className="py-2 pr-3">Base Rate</th>
                    <th className="py-2 pr-3">Transit</th>
                    <th className="py-2">Reefer</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {lanes.map((lane) => (
                    <tr key={lane.id}>
                      <td className="py-2 pr-3 font-medium text-slate-900">
                        {lane.carrier_name} ({lane.carrier_scac})
                      </td>
                      <td className="py-2 pr-3 text-slate-600">
                        {lane.origin_region} → {lane.destination_region}
                      </td>
                      <td className="py-2 pr-3">{lane.mode}</td>
                      <td className="py-2 pr-3">${lane.base_rate_usd.toLocaleString()}</td>
                      <td className="py-2 pr-3">{lane.transit_hours}h</td>
                      <td className="py-2">{lane.supports_reefer ? 'Yes' : 'No'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

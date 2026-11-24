import { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle2, FileCode2, Plus, Search, Send, Truck } from 'lucide-react';
import { api } from '../api/client';
import type { Shipment, ShipmentDetail, TrackingException } from '../types/logistics';
import { StatusBadge } from './StatusBadge';

interface TrackingPanelProps {
  shipments: Shipment[];
  exceptions: TrackingException[];
  onRefresh: () => Promise<void>;
  onError: (message: string) => void;
}

export function TrackingPanel({
  shipments,
  exceptions,
  onRefresh,
  onError,
}: TrackingPanelProps) {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [selectedId, setSelectedId] = useState<string>('');
  const [detail, setDetail] = useState<ShipmentDetail | null>(null);
  const [ingestMode, setIngestMode] = useState<'webhook' | 'edi214'>('webhook');
  const [eventCode, setEventCode] = useState('DELAYED');
  const [reasonCode, setReasonCode] = useState('WEATHER');
  const [location, setLocation] = useState('Memphis, TN');
  const [notes, setNotes] = useState('Winter squall delaying interstate corridor by 4 hours.');
  const [etaOffsetHours, setEtaOffsetHours] = useState('18');
  const [rawEdi, setRawEdi] = useState('');
  const [busy, setBusy] = useState(false);

  const [showCreate, setShowCreate] = useState(false);
  const [newRef, setNewRef] = useState('');
  const [newBol, setNewBol] = useState('');
  const [newPro, setNewPro] = useState('');
  const [newCarrierScac, setNewCarrierScac] = useState('JBHT');
  const [newCarrierName, setNewCarrierName] = useState('J.B. Hunt Transport');
  const [newOrigin, setNewOrigin] = useState('Chicago, IL');
  const [newDestination, setNewDestination] = useState('Dallas, TX');

  useEffect(() => {
    if (!selectedId && shipments.length > 0) {
      setSelectedId(shipments[0].id);
    }
  }, [selectedId, shipments]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    async function loadDetail() {
      try {
        const res = await api.getShipmentDetail(selectedId);
        if (!cancelled) setDetail(res);
      } catch (err) {
        if (!cancelled) {
          onError(err instanceof Error ? err.message : 'Failed to load shipment detail');
        }
      }
    }
    void loadDetail();
    return () => {
      cancelled = true;
    };
  }, [selectedId, shipments, onError]);

  const filteredShipments = shipments.filter((item) => {
    if (statusFilter && item.status !== statusFilter) return false;
    if (!search.trim()) return true;
    const q = search.trim().toLowerCase();
    return (
      item.reference_number.toLowerCase().includes(q) ||
      item.bol_number.toLowerCase().includes(q) ||
      item.pro_number.toLowerCase().includes(q) ||
      item.carrier_name.toLowerCase().includes(q) ||
      item.origin.toLowerCase().includes(q) ||
      item.destination.toLowerCase().includes(q)
    );
  });

  async function handleCreateShipment(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const sla = new Date(Date.now() + 24 * 3600 * 1000).toISOString();
      const created = await api.createShipment({
        reference_number: newRef,
        bol_number: newBol,
        pro_number: newPro,
        carrier_scac: newCarrierScac,
        carrier_name: newCarrierName,
        mode: 'FTL',
        origin: newOrigin,
        destination: newDestination,
        sla_eta: sla,
        weight_lbs: 32000,
      });
      setShowCreate(false);
      setNewRef('');
      setNewBol('');
      setNewPro('');
      setSelectedId(created.id);
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to create shipment');
    } finally {
      setBusy(false);
    }
  }

  async function handleIngestEvent(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      if (ingestMode === 'edi214') {
        await api.ingestEdi214(rawEdi);
      } else if (selectedId) {
        const hours = Number(etaOffsetHours) || 12;
        await api.ingestShipmentEvent(selectedId, {
          event_code: eventCode,
          reason_code: reasonCode || null,
          location,
          reported_eta: new Date(Date.now() + hours * 3600 * 1000).toISOString(),
          notes,
          actor: 'dispatcher-ui',
        });
      }
      await onRefresh();
      if (selectedId) {
        const fresh = await api.getShipmentDetail(selectedId);
        setDetail(fresh);
      }
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to ingest tracking event');
    } finally {
      setBusy(false);
    }
  }

  function loadSampleEdi() {
    const target = detail ?? shipments[0];
    const pro = target?.pro_number ?? 'PRO-7701';
    const bol = target?.bol_number ?? 'BOL-9011001';
    const scac = target?.carrier_scac ?? 'CRST';
    const dateStr = new Date(Date.now() + 36 * 3600 * 1000)
      .toISOString()
      .slice(0, 10)
      .replace(/-/g, '');
    setIngestMode('edi214');
    setRawEdi(
      `B10*${pro}*${bol}*${scac}~AT7**NS*SD*BG*20261124*1530~MS1*OMAHA*NE*US~G62*17*${dateStr}~`
    );
  }

  async function handleExceptionAction(
    exceptionId: string,
    nextStatus: 'ACKNOWLEDGED' | 'RESOLVED'
  ) {
    setBusy(true);
    try {
      await api.updateException(
        exceptionId,
        nextStatus,
        nextStatus === 'RESOLVED' ? 'Resolved by dispatcher in control tower.' : 'Acknowledged.'
      );
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to update exception');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-12">
        {/* Shipments List */}
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Truck className="h-4 w-4 text-indigo-600" />
              <h2 className="text-sm font-semibold text-slate-900">
                Tracked Shipments ({filteredShipments.length})
              </h2>
            </div>
            <button
              type="button"
              onClick={() => setShowCreate((prev) => !prev)}
              className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            >
              <Plus className="h-3.5 w-3.5" />
              New Shipment
            </button>
          </div>

          {showCreate && (
            <form
              onSubmit={(e) => void handleCreateShipment(e)}
              className="mt-3 space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs"
            >
              <div className="grid grid-cols-3 gap-2">
                <input
                  required
                  placeholder="Ref (SHP-109)"
                  value={newRef}
                  onChange={(e) => setNewRef(e.target.value)}
                  className="rounded border border-slate-300 px-2 py-1.5"
                />
                <input
                  required
                  placeholder="BOL #"
                  value={newBol}
                  onChange={(e) => setNewBol(e.target.value)}
                  className="rounded border border-slate-300 px-2 py-1.5"
                />
                <input
                  required
                  placeholder="PRO #"
                  value={newPro}
                  onChange={(e) => setNewPro(e.target.value)}
                  className="rounded border border-slate-300 px-2 py-1.5"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <input
                  required
                  placeholder="Carrier SCAC"
                  value={newCarrierScac}
                  onChange={(e) => setNewCarrierScac(e.target.value)}
                  className="rounded border border-slate-300 px-2 py-1.5"
                />
                <input
                  required
                  placeholder="Carrier Name"
                  value={newCarrierName}
                  onChange={(e) => setNewCarrierName(e.target.value)}
                  className="rounded border border-slate-300 px-2 py-1.5"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <input
                  required
                  placeholder="Origin"
                  value={newOrigin}
                  onChange={(e) => setNewOrigin(e.target.value)}
                  className="rounded border border-slate-300 px-2 py-1.5"
                />
                <input
                  required
                  placeholder="Destination"
                  value={newDestination}
                  onChange={(e) => setNewDestination(e.target.value)}
                  className="rounded border border-slate-300 px-2 py-1.5"
                />
              </div>
              <button
                type="submit"
                disabled={busy}
                className="w-full rounded bg-indigo-600 py-1.5 font-semibold text-white hover:bg-indigo-700"
              >
                Create Shipment
              </button>
            </form>
          )}

          <div className="mt-3 flex gap-2">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-400" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search ref, BOL, carrier, lane..."
                className="w-full rounded-lg border border-slate-200 py-1.5 pl-8 pr-2 text-xs focus:border-indigo-400 focus:outline-none"
              />
            </div>
            <select
              aria-label="Filter shipments by status"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-lg border border-slate-200 px-2 py-1.5 text-xs"
            >
              <option value="">All Statuses</option>
              <option value="DELAYED">DELAYED</option>
              <option value="EXCEPTION">EXCEPTION</option>
              <option value="IN_TRANSIT">IN_TRANSIT</option>
              <option value="DELIVERED">DELIVERED</option>
            </select>
          </div>

          <div className="mt-3 max-h-96 space-y-2 overflow-y-auto">
            {filteredShipments.length === 0 ? (
              <p className="py-6 text-center text-xs text-slate-500">No matching shipments.</p>
            ) : (
              filteredShipments.map((shipment) => (
                <button
                  key={shipment.id}
                  type="button"
                  onClick={() => setSelectedId(shipment.id)}
                  className={`w-full rounded-lg border p-3 text-left transition ${
                    selectedId === shipment.id
                      ? 'border-indigo-400 bg-indigo-50/50'
                      : 'border-slate-200 bg-white hover:bg-slate-50'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold text-slate-900">
                      {shipment.reference_number}
                    </span>
                    <StatusBadge value={shipment.status} />
                  </div>
                  <p className="mt-1 text-xs text-slate-700">
                    {shipment.origin} → {shipment.destination}
                  </p>
                  <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500">
                    <span>
                      {shipment.carrier_name} ({shipment.carrier_scac})
                    </span>
                    <span>
                      {shipment.delay_minutes > 0
                        ? `+${shipment.delay_minutes}m delay`
                        : 'On SLA'}
                    </span>
                  </div>
                </button>
              ))
            )}
          </div>
        </section>

        {/* Shipment Detail + Milestone Ingestion */}
        <section className="space-y-6 lg:col-span-7">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            {detail ? (
              <div>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-base font-bold text-slate-900">
                        {detail.reference_number}
                      </h3>
                      <StatusBadge value={detail.status} />
                      {detail.temperature_controlled && (
                        <span className="rounded-full bg-cyan-100 px-2 py-0.5 text-[10px] font-semibold text-cyan-800">
                          REEFER
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-slate-600">
                      BOL: <span className="font-mono">{detail.bol_number}</span> · PRO:{' '}
                      <span className="font-mono">{detail.pro_number}</span> · {detail.carrier_name}{' '}
                      ({detail.mode})
                    </p>
                  </div>
                  <div className="text-right text-xs">
                    <p className="font-medium text-slate-700">
                      Last Location: {detail.last_location}
                    </p>
                    <p className="text-slate-500">Delay Variance: {detail.delay_minutes} min</p>
                  </div>
                </div>

                <h4 className="mt-4 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Normalized Milestone Timeline ({detail.events.length})
                </h4>
                <div className="mt-2 max-h-44 space-y-2 overflow-y-auto">
                  {detail.events.length === 0 ? (
                    <p className="text-xs text-slate-500">No tracking events ingested yet.</p>
                  ) : (
                    detail.events.map((ev) => (
                      <div
                        key={ev.id}
                        className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-xs"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <StatusBadge value={ev.normalized_status} />
                            <span className="font-medium text-slate-800">{ev.location}</span>
                            {ev.reason_code && (
                              <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[10px] font-semibold text-slate-700">
                                {ev.reason_code}
                              </span>
                            )}
                          </div>
                          <span className="font-mono text-[11px] text-slate-500">
                            {ev.source_format} ({ev.raw_code})
                          </span>
                        </div>
                        {ev.notes && <p className="mt-1 text-[11px] text-slate-600">{ev.notes}</p>}
                      </div>
                    ))
                  )}
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-500">
                Select a shipment to inspect milestones and SLA status.
              </p>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <FileCode2 className="h-4 w-4 text-indigo-600" />
                <h3 className="text-sm font-semibold text-slate-900">
                  Ingest Carrier Event (Webhook JSON / X12 EDI 214)
                </h3>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIngestMode('webhook')}
                  className={`rounded-md px-2.5 py-1 text-xs font-semibold ${
                    ingestMode === 'webhook'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-slate-100 text-slate-700'
                  }`}
                >
                  Webhook JSON
                </button>
                <button
                  type="button"
                  onClick={() => setIngestMode('edi214')}
                  className={`rounded-md px-2.5 py-1 text-xs font-semibold ${
                    ingestMode === 'edi214'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-slate-100 text-slate-700'
                  }`}
                >
                  Raw EDI 214
                </button>
                <button
                  type="button"
                  onClick={loadSampleEdi}
                  className="rounded-md border border-indigo-200 px-2.5 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-50"
                >
                  Sample EDI 214
                </button>
              </div>
            </div>

            <form onSubmit={(e) => void handleIngestEvent(e)} className="mt-3 space-y-3 text-xs">
              {ingestMode === 'edi214' ? (
                <div>
                  <label className="block font-medium text-slate-700">
                    X12 EDI 214 Payload (auto-matches shipment by BOL / PRO)
                  </label>
                  <textarea
                    required
                    rows={3}
                    value={rawEdi}
                    onChange={(e) => setRawEdi(e.target.value)}
                    placeholder="B10*PRO-7701*BOL-9011001*CRST~AT7**NS*SD*BG*20261124*1530~MS1*OMAHA*NE*US~"
                    className="mt-1 w-full rounded-lg border border-slate-300 p-2 font-mono text-xs"
                  />
                </div>
              ) : (
                <div className="grid gap-2 sm:grid-cols-2">
                  <div>
                    <label className="block font-medium text-slate-700">Event Code</label>
                    <select
                      value={eventCode}
                      onChange={(e) => setEventCode(e.target.value)}
                      className="mt-1 w-full rounded-lg border border-slate-300 px-2.5 py-1.5"
                    >
                      <option value="IN_TRANSIT">IN_TRANSIT</option>
                      <option value="DELAYED">DELAYED</option>
                      <option value="DETENTION">DETENTION</option>
                      <option value="CUSTOMS_HOLD">CUSTOMS_HOLD</option>
                      <option value="PORT_CONGESTION">PORT_CONGESTION</option>
                      <option value="TEMP_EXCURSION">TEMP_EXCURSION</option>
                      <option value="DELIVERED">DELIVERED</option>
                    </select>
                  </div>
                  <div>
                    <label className="block font-medium text-slate-700">Reason Code</label>
                    <input
                      value={reasonCode}
                      onChange={(e) => setReasonCode(e.target.value)}
                      placeholder="WEATHER / DETENTION / NONE"
                      className="mt-1 w-full rounded-lg border border-slate-300 px-2.5 py-1.5"
                    />
                  </div>
                  <div>
                    <label className="block font-medium text-slate-700">Current Location</label>
                    <input
                      required
                      value={location}
                      onChange={(e) => setLocation(e.target.value)}
                      className="mt-1 w-full rounded-lg border border-slate-300 px-2.5 py-1.5"
                    />
                  </div>
                  <div>
                    <label className="block font-medium text-slate-700">
                      New Projected ETA (hours from now)
                    </label>
                    <input
                      type="number"
                      min={1}
                      value={etaOffsetHours}
                      onChange={(e) => setEtaOffsetHours(e.target.value)}
                      className="mt-1 w-full rounded-lg border border-slate-300 px-2.5 py-1.5"
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <label className="block font-medium text-slate-700">Notes</label>
                    <input
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      className="mt-1 w-full rounded-lg border border-slate-300 px-2.5 py-1.5"
                    />
                  </div>
                </div>
              )}

              <button
                type="submit"
                disabled={busy || (ingestMode === 'webhook' && !selectedId)}
                className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
              >
                <Send className="h-3.5 w-3.5" />
                {ingestMode === 'edi214' ? 'Ingest EDI 214 Payload' : 'Ingest Webhook Event'}
              </button>
            </form>
          </div>
        </section>
      </div>

      {/* Exception Queue */}
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-2">
          <AlertCircle className="h-4 w-4 text-rose-600" />
          <h3 className="text-sm font-semibold text-slate-900">
            SLA &amp; Exception Queue ({exceptions.length})
          </h3>
        </div>
        <div className="mt-3 space-y-2">
          {exceptions.length === 0 ? (
            <p className="text-xs text-slate-500">No tracking exceptions detected.</p>
          ) : (
            exceptions.map((exc) => (
              <div
                key={exc.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 p-3 text-xs"
              >
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge value={exc.severity} />
                    <StatusBadge value={exc.status} />
                    <span className="font-semibold text-slate-900">{exc.exception_type}</span>
                    <span className="text-slate-500">({exc.delay_minutes} min variance)</span>
                  </div>
                  <p className="text-slate-600">{exc.summary}</p>
                </div>
                {exc.status !== 'RESOLVED' ? (
                  <div className="flex items-center gap-2">
                    {exc.status === 'OPEN' && (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void handleExceptionAction(exc.id, 'ACKNOWLEDGED')}
                        className="rounded-md border border-amber-300 bg-amber-50 px-3 py-1.5 font-semibold text-amber-800 hover:bg-amber-100"
                      >
                        Acknowledge
                      </button>
                    )}
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void handleExceptionAction(exc.id, 'RESOLVED')}
                      className="inline-flex items-center gap-1 rounded-md bg-emerald-600 px-3 py-1.5 font-semibold text-white hover:bg-emerald-700"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Resolve
                    </button>
                  </div>
                ) : (
                  <span className="text-[11px] text-emerald-700">
                    Resolved: {exc.resolution_notes ?? 'Closed'}
                  </span>
                )}
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}

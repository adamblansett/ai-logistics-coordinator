import { useState } from 'react';
import { AlertOctagon, CheckCircle2, FileWarning, MessageSquare, PackageCheck } from 'lucide-react';
import { api } from '../api/client';
import type { InventoryAlert, InventoryReconciliation, Shipment } from '../types/logistics';
import { StatusBadge } from './StatusBadge';

interface InventoryPanelProps {
  shipments: Shipment[];
  reconciliations: InventoryReconciliation[];
  alerts: InventoryAlert[];
  onRefresh: () => Promise<void>;
  onDraftClaim: (shipmentId: string) => void;
  onError: (message: string) => void;
}

export function InventoryPanel({
  shipments,
  reconciliations,
  alerts,
  onRefresh,
  onDraftClaim,
  onError,
}: InventoryPanelProps) {
  const [shipmentId, setShipmentId] = useState('');
  const [asnNumber, setAsnNumber] = useState('ASN-550120');
  const [bolNumber, setBolNumber] = useState('BOL-9011002');
  const [warehouseCode, setWarehouseCode] = useState('ATL-FC1');
  const [sku, setSku] = useState('SKU-IND-880');
  const [description, setDescription] = useState('Precision Hydraulic Valves');
  const [expectedQty, setExpectedQty] = useState('100');
  const [unitCost, setUnitCost] = useState('185');
  const [receivedQty, setReceivedQty] = useState('92');
  const [damagedQty, setDamagedQty] = useState('2');
  const [busy, setBusy] = useState(false);

  async function handleReconcile(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.runReconciliation({
        shipment_id: shipmentId || null,
        asn_number: asnNumber,
        bol_number: bolNumber,
        warehouse_code: warehouseCode,
        expected_lines: [
          {
            sku,
            description,
            expected_qty: Number(expectedQty) || 0,
            unit_cost_usd: Number(unitCost) || 0,
          },
        ],
        received_lines: [
          {
            sku,
            received_qty: Number(receivedQty) || 0,
            damaged_qty: Number(damagedQty) || 0,
          },
        ],
        actor: 'warehouse-ui',
      });
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Inventory reconciliation failed');
    } finally {
      setBusy(false);
    }
  }

  async function handleAlertAction(
    alertId: string,
    status: 'INVESTIGATING' | 'CLAIM_FILED' | 'RESOLVED'
  ) {
    setBusy(true);
    try {
      await api.updateInventoryAlert(
        alertId,
        status,
        status === 'RESOLVED' ? 'Credit memo / recount reconciled.' : `Marked ${status}`
      );
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to update inventory alert');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-12">
        {/* Reconciler Form */}
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-5">
          <div className="flex items-center gap-2">
            <PackageCheck className="h-4 w-4 text-indigo-600" />
            <h2 className="text-sm font-semibold text-slate-900">
              ASN / BOL Receiving Reconciler
            </h2>
          </div>

          <form onSubmit={(e) => void handleReconcile(e)} className="mt-4 space-y-3 text-xs">
            <div>
              <label className="block font-medium text-slate-700">Linked Shipment (optional)</label>
              <select
                aria-label="Linked Shipment"
                value={shipmentId}
                onChange={(e) => setShipmentId(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-2.5 py-1.5"
              >
                <option value="">Standalone Warehouse Receipt</option>
                {shipments.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.reference_number} ({s.bol_number})
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="block font-medium text-slate-700">ASN #</label>
                <input
                  required
                  value={asnNumber}
                  onChange={(e) => setAsnNumber(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700">BOL #</label>
                <input
                  required
                  value={bolNumber}
                  onChange={(e) => setBolNumber(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700">Warehouse</label>
                <input
                  required
                  value={warehouseCode}
                  onChange={(e) => setWarehouseCode(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block font-medium text-slate-700">SKU</label>
                <input
                  required
                  value={sku}
                  onChange={(e) => setSku(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700">Description</label>
                <input
                  required
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5"
                />
              </div>
            </div>

            <div className="grid grid-cols-4 gap-2">
              <div>
                <label className="block font-medium text-slate-700">Expected</label>
                <input
                  type="number"
                  min={0}
                  value={expectedQty}
                  onChange={(e) => setExpectedQty(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700">Received</label>
                <input
                  type="number"
                  min={0}
                  value={receivedQty}
                  onChange={(e) => setReceivedQty(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700">Damaged</label>
                <input
                  type="number"
                  min={0}
                  value={damagedQty}
                  onChange={(e) => setDamagedQty(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700">Unit $</label>
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={unitCost}
                  onChange={(e) => setUnitCost(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-lg bg-indigo-600 py-2 font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
            >
              Reconcile ASN vs. Receiving
            </button>
          </form>
        </section>

        {/* Reconciliations History */}
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-7">
          <div className="flex items-center gap-2">
            <FileWarning className="h-4 w-4 text-indigo-600" />
            <h2 className="text-sm font-semibold text-slate-900">
              Reconciliation Ledger ({reconciliations.length})
            </h2>
          </div>

          <div className="mt-3 space-y-3">
            {reconciliations.length === 0 ? (
              <p className="text-xs text-slate-500">No inventory reconciliations recorded yet.</p>
            ) : (
              reconciliations.map((rec) => (
                <div
                  key={rec.id}
                  className="rounded-lg border border-slate-200 bg-slate-50/70 p-4 text-xs"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-900">{rec.asn_number}</span>
                      <StatusBadge value={rec.status} />
                      <span className="font-mono text-[11px] text-slate-500">
                        {rec.warehouse_code} · BOL {rec.bol_number}
                      </span>
                    </div>
                    <div className="font-semibold text-slate-900">
                      Exposure: ${rec.financial_impact_usd.toLocaleString()} ({rec.shrinkage_pct}%
                      shrinkage)
                    </div>
                  </div>
                  <p className="mt-1.5 text-[11px] text-slate-600">
                    Expected {rec.expected_total_units} · Received {rec.received_total_units} ·
                    Damaged {rec.damaged_total_units} · Variance {rec.variance_units}
                  </p>
                  <p className="mt-2 leading-relaxed text-slate-700">{rec.ai_summary}</p>
                </div>
              ))
            )}
          </div>
        </section>
      </div>

      {/* Inventory Discrepancy Alerts */}
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-2">
          <AlertOctagon className="h-4 w-4 text-rose-600" />
          <h3 className="text-sm font-semibold text-slate-900">
            Discrepancy &amp; Shrinkage Alerts ({alerts.length})
          </h3>
        </div>
        <div className="mt-3 space-y-2">
          {alerts.length === 0 ? (
            <p className="text-xs text-slate-500">No active inventory discrepancy alerts.</p>
          ) : (
            alerts.map((alert) => (
              <div
                key={alert.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 p-3 text-xs"
              >
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge value={alert.severity} />
                    <StatusBadge value={alert.status} />
                    <span className="font-mono font-semibold text-slate-900">{alert.sku}</span>
                    <span className="font-semibold text-slate-800">{alert.alert_type}</span>
                    <span className="font-semibold text-rose-700">
                      ${alert.financial_impact_usd.toLocaleString()}
                    </span>
                  </div>
                  <p className="text-slate-600">
                    {alert.description} — Expected {alert.expected_qty}, Received{' '}
                    {alert.received_qty}, Damaged {alert.damaged_qty} (Variance {alert.variance_qty})
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {alert.shipment_id && alert.status !== 'RESOLVED' && (
                    <button
                      type="button"
                      onClick={() => onDraftClaim(alert.shipment_id as string)}
                      className="inline-flex items-center gap-1 rounded-md border border-indigo-200 bg-indigo-50 px-2.5 py-1.5 font-semibold text-indigo-700 hover:bg-indigo-100"
                    >
                      <MessageSquare className="h-3.5 w-3.5" />
                      Draft Claim in Comms
                    </button>
                  )}
                  {alert.status === 'OPEN' && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void handleAlertAction(alert.id, 'INVESTIGATING')}
                      className="rounded-md border border-amber-300 bg-amber-50 px-2.5 py-1.5 font-semibold text-amber-800"
                    >
                      Investigate
                    </button>
                  )}
                  {(alert.status === 'OPEN' || alert.status === 'INVESTIGATING') && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void handleAlertAction(alert.id, 'CLAIM_FILED')}
                      className="rounded-md border border-indigo-300 bg-white px-2.5 py-1.5 font-semibold text-indigo-700"
                    >
                      File Claim
                    </button>
                  )}
                  {alert.status !== 'RESOLVED' && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void handleAlertAction(alert.id, 'RESOLVED')}
                      className="inline-flex items-center gap-1 rounded-md bg-emerald-600 px-3 py-1.5 font-semibold text-white hover:bg-emerald-700"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Resolve
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}

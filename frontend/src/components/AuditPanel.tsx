import { useState } from 'react';
import { ShieldAlert, ShieldCheck } from 'lucide-react';
import { api } from '../api/client';
import type { AuditLogEntry, AuditVerifyResult } from '../types/logistics';
import { StatusBadge } from './StatusBadge';

interface AuditPanelProps {
  logs: AuditLogEntry[];
  entityFilter: string;
  onFilterChange: (entityType: string) => void;
  onError: (message: string) => void;
}

export function AuditPanel({
  logs,
  entityFilter,
  onFilterChange,
  onError,
}: AuditPanelProps) {
  const [verifyResult, setVerifyResult] = useState<AuditVerifyResult | null>(null);
  const [verifying, setVerifying] = useState(false);

  async function handleVerify() {
    setVerifying(true);
    try {
      const result = await api.verifyAuditChain();
      setVerifyResult(result);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Audit chain verification failed');
    } finally {
      setVerifying(false);
    }
  }

  return (
    <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">
            Tamper-Evident SHA-256 Audit Trail ({logs.length})
          </h2>
          <p className="text-xs text-slate-500">
            Every state change across tracking, routing, carrier approvals, and inventory is
            cryptographically chained.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Filter audit logs by entity"
            value={entityFilter}
            onChange={(e) => onFilterChange(e.target.value)}
            className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs"
          >
            <option value="">All Entities</option>
            <option value="shipment">shipment</option>
            <option value="tracking_exception">tracking_exception</option>
            <option value="route_recommendation">route_recommendation</option>
            <option value="carrier_comm">carrier_comm</option>
            <option value="inventory_reconciliation">inventory_reconciliation</option>
            <option value="inventory_alert">inventory_alert</option>
          </select>

          <button
            type="button"
            disabled={verifying}
            onClick={() => void handleVerify()}
            className="inline-flex items-center gap-1.5 rounded-lg bg-slate-900 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
          >
            <ShieldCheck className="h-4 w-4" />
            {verifying ? 'Verifying...' : 'Verify Hash Chain'}
          </button>
        </div>
      </div>

      {verifyResult && (
        <div
          className={`flex items-center gap-2 rounded-lg border px-4 py-2.5 text-xs font-medium ${
            verifyResult.valid
              ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
              : 'border-rose-200 bg-rose-50 text-rose-800'
          }`}
        >
          {verifyResult.valid ? (
            <ShieldCheck className="h-4 w-4 shrink-0" />
          ) : (
            <ShieldAlert className="h-4 w-4 shrink-0" />
          )}
          <span>
            {verifyResult.valid
              ? `Hash Chain Verified: all ${verifyResult.checked_entries} entries intact.`
              : `Chain Integrity Failure at entry ${verifyResult.first_broken_id ?? 'unknown'} (${verifyResult.checked_entries} checked).`}
          </span>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-slate-200 text-[11px] uppercase text-slate-500">
            <tr>
              <th className="py-2 pr-3">Seq</th>
              <th className="py-2 pr-3">Entity</th>
              <th className="py-2 pr-3">Action</th>
              <th className="py-2 pr-3">Transition</th>
              <th className="py-2 pr-3">Actor</th>
              <th className="py-2">Entry Hash</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {logs.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-6 text-center text-slate-500">
                  No audit entries match the current filter.
                </td>
              </tr>
            ) : (
              logs.map((entry) => (
                <tr key={entry.id}>
                  <td className="py-2 pr-3 font-mono text-slate-500">#{entry.sequence_number}</td>
                  <td className="py-2 pr-3 font-medium text-slate-900">{entry.entity_type}</td>
                  <td className="py-2 pr-3 font-mono text-[11px] text-slate-800">
                    {entry.action}
                  </td>
                  <td className="py-2 pr-3">
                    <div className="flex items-center gap-1.5">
                      {entry.previous_state && (
                        <span className="text-[11px] text-slate-500">{entry.previous_state} →</span>
                      )}
                      {entry.new_state && <StatusBadge value={entry.new_state} />}
                    </div>
                  </td>
                  <td className="py-2 pr-3 text-slate-600">{entry.actor}</td>
                  <td className="py-2 font-mono text-[11px] text-slate-500">
                    {entry.entry_hash.slice(0, 14)}…
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

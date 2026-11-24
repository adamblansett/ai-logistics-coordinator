import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Cpu,
  MessageSquare,
  PackageCheck,
  Route,
  ShieldCheck,
  Sparkles,
  Truck,
} from 'lucide-react';
import type { DashboardSummary, TabKey } from '../types/logistics';
import { StatusBadge } from './StatusBadge';

interface OverviewPanelProps {
  summary: DashboardSummary | null;
  seeding: boolean;
  onSeedDemo: () => Promise<void>;
  onNavigate: (tab: TabKey) => void;
}

export function OverviewPanel({
  summary,
  seeding,
  onSeedDemo,
  onNavigate,
}: OverviewPanelProps) {
  const isEmpty = !summary || summary.total_shipments === 0;

  return (
    <div className="space-y-6">
      {isEmpty && (
        <section className="rounded-xl border border-indigo-200 bg-indigo-50/70 p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="max-w-2xl">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-indigo-700">
                <Sparkles className="h-4 w-4" />
                Empty Control Tower Workspace
              </div>
              <h2 className="mt-1 text-lg font-bold text-slate-900">
                Load Realistic Freight Operations Data
              </h2>
              <p className="mt-1 text-sm text-slate-600">
                Populate 5 active shipments across FTL, LTL, and Intermodal lanes, EDI 214 &amp;
                webhook exceptions, active weather/port disruptions, carrier routing options,
                pending communication drafts, and ASN/BOL inventory discrepancies.
              </p>
            </div>
            <button
              type="button"
              onClick={() => void onSeedDemo()}
              disabled={seeding}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Sparkles className="h-4 w-4" />
              {seeding ? 'Seeding Workspace...' : 'Load Demo Logistics Scenario'}
            </button>
          </div>
        </section>
      )}

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Active Shipments</span>
            <Truck className="h-4 w-4 text-indigo-600" />
          </div>
          <p className="mt-2 text-2xl font-bold text-slate-900">
            {summary?.total_shipments ?? 0}
          </p>
          <p className="mt-1 text-xs text-slate-600">
            {summary?.delayed_shipments ?? 0} delayed or in exception
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Tracking Exceptions</span>
            <AlertTriangle className="h-4 w-4 text-amber-600" />
          </div>
          <p className="mt-2 text-2xl font-bold text-slate-900">
            {summary?.open_tracking_exceptions ?? 0}
          </p>
          <p className="mt-1 text-xs text-slate-600">
            {summary?.critical_exceptions ?? 0} critical · {summary?.active_disruptions ?? 0}{' '}
            active disruptions
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Pending Approvals</span>
            <MessageSquare className="h-4 w-4 text-sky-600" />
          </div>
          <p className="mt-2 text-2xl font-bold text-slate-900">
            {(summary?.pending_route_recommendations ?? 0) +
              (summary?.pending_comm_approvals ?? 0)}
          </p>
          <p className="mt-1 text-xs text-slate-600">
            {summary?.pending_route_recommendations ?? 0} routes ·{' '}
            {summary?.pending_comm_approvals ?? 0} comms ({summary?.sent_comms ?? 0} sent)
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Inventory Exposure</span>
            <PackageCheck className="h-4 w-4 text-rose-600" />
          </div>
          <p className="mt-2 text-2xl font-bold text-slate-900">
            ${(summary?.inventory_exposure_usd ?? 0).toLocaleString()}
          </p>
          <p className="mt-1 text-xs text-slate-600">
            {summary?.open_inventory_alerts ?? 0} open discrepancy alerts
          </p>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          {
            tab: 'tracking' as TabKey,
            title: 'Freight Tracking',
            summary:
              'Normalized EDI 214 & webhook milestone ingestion with SLA slip detection and exception queues.',
            icon: Truck,
          },
          {
            tab: 'routing' as TabKey,
            title: 'Route Optimization',
            summary:
              'Multi-constraint lane cost, transit-time, reliability, carbon, and disruption re-routing.',
            icon: Route,
          },
          {
            tab: 'comms' as TabKey,
            title: 'Carrier Communications',
            summary:
              'Grounded detention, BOL, and appointment drafts strictly gated behind dispatcher approval.',
            icon: MessageSquare,
          },
          {
            tab: 'inventory' as TabKey,
            title: 'Inventory Alerts',
            summary:
              'ASN/BOL vs. warehouse receiving count reconciliation with financial exposure escalation.',
            icon: PackageCheck,
          },
        ].map((card) => {
          const Icon = card.icon;
          return (
            <button
              key={card.tab}
              type="button"
              onClick={() => onNavigate(card.tab)}
              className="group flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-5 text-left shadow-sm transition hover:border-indigo-300 hover:shadow"
            >
              <div>
                <div className="flex items-center justify-between">
                  <Icon className="h-5 w-5 text-indigo-600" />
                  <ArrowRight className="h-4 w-4 text-slate-400 transition group-hover:translate-x-0.5 group-hover:text-indigo-600" />
                </div>
                <h3 className="mt-3 text-sm font-semibold text-slate-900">{card.title}</h3>
                <p className="mt-1 text-xs leading-relaxed text-slate-600">{card.summary}</p>
              </div>
              <span className="mt-4 text-xs font-semibold text-indigo-600">Open Workspace</span>
            </button>
          );
        })}
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900">
              Recent Immutable Audit Activity
            </h3>
            <button
              type="button"
              onClick={() => onNavigate('audit')}
              className="text-xs font-semibold text-indigo-600 hover:text-indigo-700"
            >
              View Full Chain ({summary?.total_audit_entries ?? 0})
            </button>
          </div>
          {summary && summary.recent_audit_logs.length > 0 ? (
            <div className="mt-3 divide-y divide-slate-100">
              {summary.recent_audit_logs.slice(0, 6).map((entry) => (
                <div
                  key={entry.id}
                  className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-xs"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[11px] text-slate-400">
                      #{entry.sequence_number}
                    </span>
                    <span className="font-semibold text-slate-800">{entry.entity_type}</span>
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-700">
                      {entry.action}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-slate-500">
                    {entry.new_state && <StatusBadge value={entry.new_state} />}
                    <span>{entry.actor}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-xs text-slate-500">
              No audit events recorded yet. Load the demo scenario or ingest a shipment event to
              begin tracking tamper-evident transitions.
            </p>
          )}
        </div>

        <div className="space-y-4">
          <div className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-5">
            <Cpu className="mt-0.5 h-5 w-5 shrink-0 text-indigo-600" />
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Local-First LLM Routing</h3>
              <p className="mt-1 text-xs text-slate-600">
                Supports offline deterministic mock execution, local Ollama inference, and guarded
                cloud Gemini fallback with outbound PII redaction.
              </p>
            </div>
          </div>
          <div className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-5">
            <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Production Security Baseline</h3>
              <p className="mt-1 text-xs text-slate-600">
                Human-in-the-loop sign-off for route overrides and outbound comms, HMAC webhook
                verification, and SHA-256 hash-chained audit logs.
              </p>
              <div className="mt-2 inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700">
                <CheckCircle2 className="h-3.5 w-3.5" />
                Audit Chain Ready
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

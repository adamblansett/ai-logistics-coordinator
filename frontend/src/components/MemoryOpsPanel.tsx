import { useState } from 'react';
import { Brain, Cpu, Play, Plus, Search, Upload } from 'lucide-react';
import { api } from '../api/client';
import type {
  MemorySearchHit,
  OperationalMemory,
  WorkerDispatchResponse,
} from '../types/logistics';
import { StatusBadge } from './StatusBadge';

interface MemoryOpsPanelProps {
  memories: OperationalMemory[];
  onRefresh: () => Promise<void>;
  onError: (message: string) => void;
}

export function MemoryOpsPanel({ memories, onRefresh, onError }: MemoryOpsPanelProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchHits, setSearchHits] = useState<MemorySearchHit[] | null>(null);
  const [searching, setSearching] = useState(false);

  const [category, setCategory] = useState('ROUTE_PLAYBOOK');
  const [corridor, setCorridor] = useState('Los Angeles, CA -> Chicago, IL');
  const [carrierScac, setCarrierScac] = useState('BNSF');
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');

  const [sweepResult, setSweepResult] = useState<WorkerDispatchResponse | null>(null);
  const [batchText, setBatchText] = useState(
    'B10*PRO-7703*BOL-9011003*JBHT~AT7*X1*NS***20261126*0830~MS1*ALLENTOWN*PA*US~'
  );
  const [batchResult, setBatchResult] = useState<WorkerDispatchResponse | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!searchQuery.trim()) {
      setSearchHits(null);
      return;
    }
    setSearching(true);
    try {
      const hits = await api.searchMemories(searchQuery.trim());
      setSearchHits(hits);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Memory search failed.');
    } finally {
      setSearching(false);
    }
  }

  async function handleCreateMemory(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.createMemory({
        category,
        corridor: corridor.trim() || null,
        carrier_scac: carrierScac.trim() || null,
        title,
        content,
        actor: 'dispatcher-ui',
      });
      setTitle('');
      setContent('');
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to save operational memory.');
    } finally {
      setBusy(false);
    }
  }

  async function handleSlaSweep() {
    setBusy(true);
    try {
      const res = await api.triggerSlaSweep();
      setSweepResult(res);
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : 'SLA breach sweep failed.');
    } finally {
      setBusy(false);
    }
  }

  async function handleEdiBatch(e: React.FormEvent) {
    e.preventDefault();
    const payloads = batchText
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    if (payloads.length === 0) return;

    setBusy(true);
    try {
      const res = await api.triggerEdiBatch(payloads);
      setBatchResult(res);
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Bulk EDI 214 batch ingestion failed.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-12">
      {/* Operational Memory Search & Indexing */}
      <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-7">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Brain className="h-4 w-4 text-indigo-600" />
            <h2 className="text-sm font-semibold text-slate-900">
              Operational Memory (`pgvector`-ready Playbooks &amp; Resolutions)
            </h2>
          </div>
          <span className="text-xs text-slate-500">{memories.length} indexed</span>
        </div>

        <form onSubmit={(e) => void handleSearch(e)} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-400" />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search historical resolutions, carriers, corridors (e.g. winter storm BNSF)..."
              className="w-full rounded-lg border border-slate-300 py-1.5 pl-8 pr-2 text-xs"
            />
          </div>
          <button
            type="submit"
            disabled={searching}
            className="rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700"
          >
            {searching ? 'Searching...' : 'Semantic Search'}
          </button>
          {searchHits !== null && (
            <button
              type="button"
              onClick={() => {
                setSearchQuery('');
                setSearchHits(null);
              }}
              className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs text-slate-700"
            >
              Clear
            </button>
          )}
        </form>

        <div className="max-h-72 space-y-2 overflow-y-auto">
          {searchHits !== null ? (
            searchHits.length === 0 ? (
              <p className="text-xs text-slate-500">No semantic matches found.</p>
            ) : (
              searchHits.map((hit) => (
                <article
                  key={hit.memory.id}
                  className="rounded-lg border border-indigo-200 bg-indigo-50/40 p-3 text-xs"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <StatusBadge value={hit.memory.category} />
                      <span className="font-semibold text-slate-900">{hit.memory.title}</span>
                    </div>
                    <span className="rounded bg-indigo-100 px-2 py-0.5 font-mono text-[11px] font-semibold text-indigo-800">
                      score {(hit.score * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="mt-1 text-slate-700">{hit.memory.content}</p>
                </article>
              ))
            )
          ) : memories.length === 0 ? (
            <p className="text-xs text-slate-500">
              No operational memories indexed yet. Resolve a tracking exception or add a playbook
              below.
            </p>
          ) : (
            memories.map((mem) => (
              <article
                key={mem.id}
                className="rounded-lg border border-slate-200 bg-slate-50/60 p-3 text-xs"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <StatusBadge value={mem.category} />
                    <span className="font-semibold text-slate-900">{mem.title}</span>
                  </div>
                  <span className="text-[11px] text-slate-500">
                    {mem.corridor ?? 'Global'} {mem.carrier_scac ? `· ${mem.carrier_scac}` : ''}
                  </span>
                </div>
                <p className="mt-1 text-slate-600">{mem.content}</p>
              </article>
            ))
          )}
        </div>

        <form
          onSubmit={(e) => void handleCreateMemory(e)}
          className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs"
        >
          <div className="flex items-center gap-1.5 font-semibold text-slate-800">
            <Plus className="h-3.5 w-3.5 text-indigo-600" />
            Index New Operational Playbook
          </div>
          <div className="grid grid-cols-3 gap-2">
            <select
              aria-label="Memory Category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="rounded border border-slate-300 bg-white px-2 py-1.5"
            >
              <option value="ROUTE_PLAYBOOK">ROUTE_PLAYBOOK</option>
              <option value="TRACKING_EXCEPTION">TRACKING_EXCEPTION</option>
              <option value="CARRIER_PERFORMANCE">CARRIER_PERFORMANCE</option>
              <option value="OSD_CLAIM">OSD_CLAIM</option>
              <option value="GENERAL">GENERAL</option>
            </select>
            <input
              value={corridor}
              onChange={(e) => setCorridor(e.target.value)}
              placeholder="Corridor"
              className="rounded border border-slate-300 bg-white px-2 py-1.5"
            />
            <input
              value={carrierScac}
              onChange={(e) => setCarrierScac(e.target.value)}
              placeholder="SCAC"
              className="rounded border border-slate-300 bg-white px-2 py-1.5"
            />
          </div>
          <input
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Playbook Title (e.g. Laredo Customs Pre-Clearance SOP)"
            className="w-full rounded border border-slate-300 bg-white px-2.5 py-1.5"
          />
          <textarea
            required
            rows={2}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Operational resolution or guidance..."
            className="w-full rounded border border-slate-300 bg-white p-2"
          />
          <button
            type="submit"
            disabled={busy}
            className="rounded-lg bg-slate-900 px-3.5 py-1.5 font-semibold text-white hover:bg-slate-800"
          >
            Index Playbook Memory
          </button>
        </form>
      </section>

      {/* Background Workers & Batch EDI */}
      <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-5">
        <div className="flex items-center gap-2">
          <Cpu className="h-4 w-4 text-indigo-600" />
          <h2 className="text-sm font-semibold text-slate-900">
            Async Workers &amp; Bulk Operations
          </h2>
        </div>

        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-xs">
          <h3 className="font-semibold text-slate-900">SLA Breach Sweep Worker</h3>
          <p className="mt-1 text-slate-600">
            Scan active shipments past SLA ETA and auto-open or escalate `ETA_SLIP` exceptions.
          </p>
          <button
            type="button"
            disabled={busy}
            onClick={() => void handleSlaSweep()}
            className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-1.5 font-semibold text-white hover:bg-indigo-700"
          >
            <Play className="h-3.5 w-3.5" />
            Run SLA Breach Sweep
          </button>

          {sweepResult && (
            <div className="mt-3 rounded border border-emerald-200 bg-emerald-50 p-2.5 text-[11px] text-emerald-900">
              Mode: <span className="font-mono">{sweepResult.execution_mode}</span> · Checked{' '}
              {String(sweepResult.summary.checked_shipments ?? 0)} · Breached{' '}
              {String(sweepResult.summary.breached_shipments ?? 0)} · Exceptions updated{' '}
              {String(sweepResult.summary.exceptions_opened_or_updated ?? 0)}
            </div>
          )}
        </div>

        <form
          onSubmit={(e) => void handleEdiBatch(e)}
          className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4 text-xs"
        >
          <div className="flex items-center gap-1.5 font-semibold text-slate-900">
            <Upload className="h-3.5 w-3.5 text-indigo-600" />
            Bulk EDI 214 Batch Ingestion
          </div>
          <p className="text-slate-600">
            One X12 EDI 214 payload per line. Valid messages ingest cleanly even if individual rows
            fail.
          </p>
          <textarea
            rows={4}
            value={batchText}
            onChange={(e) => setBatchText(e.target.value)}
            className="w-full rounded border border-slate-300 bg-white p-2 font-mono text-[11px]"
          />
          <button
            type="submit"
            disabled={busy}
            className="rounded-lg bg-slate-900 px-3.5 py-1.5 font-semibold text-white hover:bg-slate-800"
          >
            Ingest EDI 214 Batch
          </button>

          {batchResult && (
            <div className="rounded border border-indigo-200 bg-indigo-50 p-2.5 text-[11px] text-indigo-900">
              Processed {String(batchResult.summary.total ?? 0)} messages: Succeeded{' '}
              {String(batchResult.summary.succeeded ?? 0)}, Failed{' '}
              {String(batchResult.summary.failed ?? 0)}.
            </div>
          )}
        </form>
      </section>
    </div>
  );
}

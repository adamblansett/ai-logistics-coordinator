import { useEffect, useState } from 'react';
import { Check, Lock, MessageSquare, Pencil, Send, ShieldCheck, X } from 'lucide-react';
import { api } from '../api/client';
import type { CarrierCommunication, Shipment } from '../types/logistics';
import { StatusBadge } from './StatusBadge';

interface CommsPanelProps {
  shipments: Shipment[];
  comms: CarrierCommunication[];
  initialShipmentId?: string;
  initialCommType?: string;
  onRefresh: () => Promise<void>;
  onError: (message: string) => void;
}

export function CommsPanel({
  shipments,
  comms,
  initialShipmentId,
  initialCommType,
  onRefresh,
  onError,
}: CommsPanelProps) {
  const [shipmentId, setShipmentId] = useState(initialShipmentId || '');
  const [commType, setCommType] = useState(initialCommType || 'DETENTION_NOTICE');
  const [channel, setChannel] = useState('EMAIL');
  const [recipientName, setRecipientName] = useState('Carrier Terminal Dispatch');
  const [recipientContact, setRecipientContact] = useState('dispatch@carrier-example.com');
  const [customNotes, setCustomNotes] = useState(
    'Please confirm dock check-in timestamps and updated recovery ETA.'
  );
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editSubject, setEditSubject] = useState('');
  const [editBody, setEditBody] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (initialShipmentId) setShipmentId(initialShipmentId);
    if (initialCommType) setCommType(initialCommType);
  }, [initialShipmentId, initialCommType]);

  const selectedShipment = shipmentId || shipments[0]?.id || '';

  async function handleDraft(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedShipment) {
      onError('Create or load a shipment before drafting carrier communications.');
      return;
    }
    setBusy(true);
    try {
      await api.draftComm({
        shipment_id: selectedShipment,
        comm_type: commType,
        channel,
        recipient_name: recipientName,
        recipient_contact: recipientContact,
        custom_notes: customNotes,
        actor: 'dispatcher-ui',
      });
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to generate draft');
    } finally {
      setBusy(false);
    }
  }

  function startEdit(comm: CarrierCommunication) {
    setEditingId(comm.id);
    setEditSubject(comm.subject);
    setEditBody(comm.body);
  }

  async function saveEdit(commId: string) {
    setBusy(true);
    try {
      await api.updateCommDraft(commId, { subject: editSubject, body: editBody });
      setEditingId(null);
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to update draft');
    } finally {
      setBusy(false);
    }
  }

  async function handleDecision(commId: string, decision: 'APPROVED' | 'REJECTED') {
    setBusy(true);
    try {
      await api.decideComm(
        commId,
        decision,
        decision === 'APPROVED' ? 'Approved by dispatcher' : 'Rejected by dispatcher'
      );
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to decide communication');
    } finally {
      setBusy(false);
    }
  }

  async function handleSend(commId: string) {
    setBusy(true);
    try {
      await api.sendComm(commId);
      await onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to send communication');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-12">
      {/* Draft Generator */}
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-4">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-4 w-4 text-indigo-600" />
          <h2 className="text-sm font-semibold text-slate-900">Draft Carrier Communication</h2>
        </div>
        <p className="mt-1 text-xs text-slate-500">
          Every draft is grounded in live shipment BOL/PRO telemetry and gated behind dispatcher
          approval prior to send.
        </p>

        <form onSubmit={(e) => void handleDraft(e)} className="mt-4 space-y-3 text-xs">
          <div>
            <label className="block font-medium text-slate-700">Shipment</label>
            <select
              aria-label="Communication Shipment"
              value={selectedShipment}
              onChange={(e) => setShipmentId(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-2.5 py-1.5"
            >
              {shipments.length === 0 && <option value="">No shipments available</option>}
              {shipments.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.reference_number} — {s.carrier_name} ({s.bol_number})
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block font-medium text-slate-700">Message Type</label>
              <select
                aria-label="Communication Type"
                value={commType}
                onChange={(e) => setCommType(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5"
              >
                <option value="DETENTION_NOTICE">DETENTION NOTICE</option>
                <option value="BOL_CORRECTION">BOL CORRECTION</option>
                <option value="APPOINTMENT_RESCHEDULE">APPOINTMENT RESCHEDULE</option>
                <option value="DELAY_ESCALATION">DELAY ESCALATION</option>
                <option value="DISCREPANCY_CLAIM">DISCREPANCY CLAIM</option>
              </select>
            </div>
            <div>
              <label className="block font-medium text-slate-700">Channel</label>
              <select
                aria-label="Channel"
                value={channel}
                onChange={(e) => setChannel(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5"
              >
                <option value="EMAIL">EMAIL</option>
                <option value="EDI_PORTAL">EDI PORTAL</option>
                <option value="CARRIER_WEBHOOK">CARRIER WEBHOOK</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block font-medium text-slate-700">Recipient Name</label>
            <input
              required
              value={recipientName}
              onChange={(e) => setRecipientName(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-2.5 py-1.5"
            />
          </div>

          <div>
            <label className="block font-medium text-slate-700">Recipient Contact</label>
            <input
              required
              value={recipientContact}
              onChange={(e) => setRecipientContact(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-2.5 py-1.5"
            />
          </div>

          <div>
            <label className="block font-medium text-slate-700">Dispatcher Notes</label>
            <textarea
              rows={3}
              value={customNotes}
              onChange={(e) => setCustomNotes(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 p-2"
            />
          </div>

          <button
            type="submit"
            disabled={busy || !selectedShipment}
            className="w-full rounded-lg bg-indigo-600 py-2 font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
          >
            Generate Grounded Draft
          </button>
        </form>
      </section>

      {/* Approval & Dispatch Queue */}
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-8">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-900">
            Carrier Outbox &amp; Approval Queue ({comms.length})
          </h2>
          <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700">
            <ShieldCheck className="h-4 w-4" />
            Human-in-the-Loop Gating Enforced
          </span>
        </div>

        <div className="mt-4 space-y-4">
          {comms.length === 0 ? (
            <p className="text-xs text-slate-500">No carrier communication drafts yet.</p>
          ) : (
            comms.map((comm) => {
              const isEditable = comm.status === 'PENDING_APPROVAL' || comm.status === 'DRAFT';
              const isEditing = editingId === comm.id;

              return (
                <article
                  key={comm.id}
                  className="rounded-xl border border-slate-200 bg-slate-50/60 p-4 text-xs"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusBadge value={comm.status} />
                      <span className="font-semibold text-slate-900">
                        {comm.comm_type.replace(/_/g, ' ')}
                      </span>
                      <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[10px] font-medium text-slate-700">
                        {comm.channel}
                      </span>
                      <span className="text-slate-500">
                        via {comm.llm_provider}
                        {comm.pii_redacted ? ' (PII scrubbed)' : ''}
                      </span>
                    </div>
                    <span className="text-[11px] text-slate-500">
                      To: {comm.recipient_name} ({comm.recipient_contact})
                    </span>
                  </div>

                  {isEditing ? (
                    <div className="mt-3 space-y-2">
                      <input
                        value={editSubject}
                        onChange={(e) => setEditSubject(e.target.value)}
                        className="w-full rounded border border-slate-300 bg-white px-2.5 py-1.5 font-semibold"
                      />
                      <textarea
                        rows={6}
                        value={editBody}
                        onChange={(e) => setEditBody(e.target.value)}
                        className="w-full rounded border border-slate-300 bg-white p-2 font-sans"
                      />
                      <div className="flex gap-2">
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void saveEdit(comm.id)}
                          className="rounded bg-indigo-600 px-3 py-1.5 font-semibold text-white"
                        >
                          Save Edits
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditingId(null)}
                          className="rounded border border-slate-300 bg-white px-3 py-1.5"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <h3 className="mt-2.5 text-sm font-semibold text-slate-900">
                        {comm.subject}
                      </h3>
                      <pre className="mt-2 whitespace-pre-wrap rounded-lg border border-slate-200 bg-white p-3 font-sans text-xs leading-relaxed text-slate-700">
                        {comm.body}
                      </pre>
                    </>
                  )}

                  <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
                    <span className="rounded bg-indigo-50 px-2 py-0.5 text-indigo-800">
                      BOL: {String(comm.grounding_facts.bol_number ?? 'N/A')}
                    </span>
                    <span className="rounded bg-indigo-50 px-2 py-0.5 text-indigo-800">
                      PRO: {String(comm.grounding_facts.pro_number ?? 'N/A')}
                    </span>
                    <span className="rounded bg-indigo-50 px-2 py-0.5 text-indigo-800">
                      Delay: {String(comm.grounding_facts.delay_minutes ?? 0)}m
                    </span>
                    {comm.external_message_id && (
                      <span className="rounded bg-emerald-50 px-2 py-0.5 font-mono text-emerald-800">
                        Sent ID: {comm.external_message_id}
                      </span>
                    )}
                  </div>

                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    {isEditable && !isEditing && (
                      <>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => startEdit(comm)}
                          className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-3 py-1.5 font-semibold text-slate-700 hover:bg-slate-50"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                          Edit Draft
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void handleDecision(comm.id, 'APPROVED')}
                          className="inline-flex items-center gap-1 rounded-md bg-emerald-600 px-3 py-1.5 font-semibold text-white hover:bg-emerald-700"
                        >
                          <Check className="h-3.5 w-3.5" />
                          Approve Draft
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void handleDecision(comm.id, 'REJECTED')}
                          className="inline-flex items-center gap-1 rounded-md border border-rose-300 bg-white px-3 py-1.5 font-semibold text-rose-700 hover:bg-rose-50"
                        >
                          <X className="h-3.5 w-3.5" />
                          Reject
                        </button>
                      </>
                    )}

                    {comm.status === 'APPROVED' && (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void handleSend(comm.id)}
                        className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-3.5 py-1.5 font-semibold text-white hover:bg-indigo-700"
                      >
                        <Send className="h-3.5 w-3.5" />
                        Dispatch to Carrier
                      </button>
                    )}

                    {comm.status === 'PENDING_APPROVAL' && (
                      <span className="inline-flex items-center gap-1 text-[11px] text-amber-700">
                        <Lock className="h-3 w-3" />
                        Send locked until approved
                      </span>
                    )}
                  </div>
                </article>
              );
            })
          )}
        </div>
      </section>
    </div>
  );
}

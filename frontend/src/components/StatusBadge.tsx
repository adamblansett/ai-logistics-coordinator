const BADGE_STYLES: Record<string, string> = {
  CRITICAL: 'bg-rose-100 text-rose-800 border-rose-200',
  HIGH: 'bg-orange-100 text-orange-800 border-orange-200',
  MEDIUM: 'bg-amber-100 text-amber-800 border-amber-200',
  LOW: 'bg-slate-100 text-slate-700 border-slate-200',

  DELAYED: 'bg-amber-100 text-amber-800 border-amber-200',
  EXCEPTION: 'bg-rose-100 text-rose-800 border-rose-200',
  IN_TRANSIT: 'bg-sky-100 text-sky-800 border-sky-200',
  PICKED_UP: 'bg-indigo-100 text-indigo-800 border-indigo-200',
  OUT_FOR_DELIVERY: 'bg-cyan-100 text-cyan-800 border-cyan-200',
  DELIVERED: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  PLANNED: 'bg-slate-100 text-slate-700 border-slate-200',

  OPEN: 'bg-rose-100 text-rose-800 border-rose-200',
  ACKNOWLEDGED: 'bg-amber-100 text-amber-800 border-amber-200',
  INVESTIGATING: 'bg-amber-100 text-amber-800 border-amber-200',
  CLAIM_FILED: 'bg-indigo-100 text-indigo-800 border-indigo-200',
  RESOLVED: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  MATCHED: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  DISCREPANCY_OPEN: 'bg-rose-100 text-rose-800 border-rose-200',

  PENDING_REVIEW: 'bg-amber-100 text-amber-800 border-amber-200',
  PENDING_APPROVAL: 'bg-amber-100 text-amber-800 border-amber-200',
  DRAFT: 'bg-slate-100 text-slate-700 border-slate-200',
  APPROVED: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  SENT: 'bg-indigo-100 text-indigo-800 border-indigo-200',
  REJECTED: 'bg-rose-100 text-rose-800 border-rose-200',
};

export function StatusBadge({ value }: { value: string }) {
  const key = value.toUpperCase();
  const style = BADGE_STYLES[key] ?? 'bg-slate-100 text-slate-700 border-slate-200';
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-semibold tracking-wide ${style}`}
    >
      {key.replace(/_/g, ' ')}
    </span>
  );
}

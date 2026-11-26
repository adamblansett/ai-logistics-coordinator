import type {
  AuditLogEntry,
  AuditVerifyResult,
  AuthPrincipal,
  AuthTokenResponse,
  CarrierCommunication,
  CarrierLane,
  DashboardSummary,
  DemoSeedResponse,
  DisruptionAlert,
  HealthStatus,
  InventoryAlert,
  InventoryReconciliation,
  MemorySearchHit,
  OperationalMemory,
  RouteRecommendation,
  Shipment,
  ShipmentDetail,
  TrackingException,
  WorkerDispatchResponse,
} from '../types/logistics';

const TOKEN_STORAGE_KEY = 'ai_logistics_jwt';
let memoryToken: string | null = null;

export function getAuthToken(): string | null {
  if (memoryToken) return memoryToken;
  try {
    return typeof window !== 'undefined' ? window.sessionStorage.getItem(TOKEN_STORAGE_KEY) : null;
  } catch {
    return null;
  }
}

export function setAuthToken(token: string | null): void {
  memoryToken = token;
  try {
    if (typeof window !== 'undefined') {
      if (token) {
        window.sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
      } else {
        window.sessionStorage.removeItem(TOKEN_STORAGE_KEY);
      }
    }
  } catch {
    // Ignore storage quota or sandbox errors
  }
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((init?.headers as Record<string, string> | undefined) ?? {}),
  };
  if (token && !headers.Authorization) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...init,
    headers,
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const errBody = (await response.json()) as { detail?: string };
      if (errBody?.detail) {
        message = typeof errBody.detail === 'string' ? errBody.detail : JSON.stringify(errBody.detail);
      }
    } catch {
      // Ignore parse errors for non-JSON error payloads
    }
    throw new Error(message);
  }

  return (await response.json()) as T;
}

export const api = {
  getHealth: (): Promise<HealthStatus> => requestJson('/api/v1/health'),
  getDashboardSummary: (): Promise<DashboardSummary> => requestJson('/api/v1/dashboard/summary'),
  seedDemo: (): Promise<DemoSeedResponse> =>
    requestJson('/api/v1/demo/seed', { method: 'POST' }),

  // Tracking
  listShipments: (params?: { status?: string; search?: string }): Promise<Shipment[]> => {
    const q = new URLSearchParams();
    if (params?.status) q.set('status', params.status);
    if (params?.search) q.set('search', params.search);
    const suffix = q.toString() ? `?${q.toString()}` : '';
    return requestJson(`/api/v1/tracking/shipments${suffix}`);
  },
  getShipmentDetail: (shipmentId: string): Promise<ShipmentDetail> =>
    requestJson(`/api/v1/tracking/shipments/${shipmentId}`),
  createShipment: (payload: Record<string, unknown>): Promise<Shipment> =>
    requestJson('/api/v1/tracking/shipments', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  ingestShipmentEvent: (
    shipmentId: string,
    payload: Record<string, unknown>
  ): Promise<unknown> =>
    requestJson(`/api/v1/tracking/shipments/${shipmentId}/events`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  ingestEdi214: (rawEdi214: string): Promise<unknown> =>
    requestJson('/api/v1/tracking/edi214', {
      method: 'POST',
      body: JSON.stringify({ raw_edi_214: rawEdi214, actor: 'control-tower-ui' }),
    }),
  listExceptions: (): Promise<TrackingException[]> => requestJson('/api/v1/tracking/exceptions'),
  updateException: (
    exceptionId: string,
    status: 'ACKNOWLEDGED' | 'RESOLVED',
    resolutionNotes?: string
  ): Promise<TrackingException> =>
    requestJson(`/api/v1/tracking/exceptions/${exceptionId}`, {
      method: 'PATCH',
      body: JSON.stringify({
        status,
        resolution_notes: resolutionNotes ?? null,
        actor: 'dispatcher-ui',
      }),
    }),

  // Routing
  listLanes: (): Promise<CarrierLane[]> => requestJson('/api/v1/routing/lanes'),
  createLane: (payload: Record<string, unknown>): Promise<CarrierLane> =>
    requestJson('/api/v1/routing/lanes', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  listDisruptions: (): Promise<DisruptionAlert[]> => requestJson('/api/v1/routing/disruptions'),
  createDisruption: (payload: Record<string, unknown>): Promise<DisruptionAlert> =>
    requestJson('/api/v1/routing/disruptions', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  toggleDisruption: (disruptionId: string, active: boolean): Promise<DisruptionAlert> =>
    requestJson(`/api/v1/routing/disruptions/${disruptionId}`, {
      method: 'PATCH',
      body: JSON.stringify({ active, actor: 'dispatcher-ui' }),
    }),
  optimizeRoute: (payload: Record<string, unknown>): Promise<RouteRecommendation> =>
    requestJson('/api/v1/routing/optimize', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  listRecommendations: (): Promise<RouteRecommendation[]> =>
    requestJson('/api/v1/routing/recommendations'),
  decideRecommendation: (
    recId: string,
    decision: 'APPROVED' | 'REJECTED',
    notes?: string
  ): Promise<RouteRecommendation> =>
    requestJson(`/api/v1/routing/recommendations/${recId}/decision`, {
      method: 'POST',
      body: JSON.stringify({ decision, actor: 'dispatcher-ui', notes: notes ?? null }),
    }),

  // Comms
  listComms: (): Promise<CarrierCommunication[]> => requestJson('/api/v1/comms'),
  draftComm: (payload: Record<string, unknown>): Promise<CarrierCommunication> =>
    requestJson('/api/v1/comms/draft', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateCommDraft: (
    commId: string,
    payload: { subject?: string; body?: string }
  ): Promise<CarrierCommunication> =>
    requestJson(`/api/v1/comms/${commId}`, {
      method: 'PATCH',
      body: JSON.stringify({ ...payload, actor: 'dispatcher-ui' }),
    }),
  decideComm: (
    commId: string,
    decision: 'APPROVED' | 'REJECTED',
    notes?: string
  ): Promise<CarrierCommunication> =>
    requestJson(`/api/v1/comms/${commId}/decision`, {
      method: 'POST',
      body: JSON.stringify({ decision, actor: 'dispatcher-ui', notes: notes ?? null }),
    }),
  sendComm: (commId: string): Promise<CarrierCommunication> =>
    requestJson(`/api/v1/comms/${commId}/send`, {
      method: 'POST',
      body: JSON.stringify({ actor: 'dispatcher-ui' }),
    }),

  // Inventory
  listReconciliations: (): Promise<InventoryReconciliation[]> =>
    requestJson('/api/v1/inventory/reconciliations'),
  runReconciliation: (payload: Record<string, unknown>): Promise<InventoryReconciliation> =>
    requestJson('/api/v1/inventory/reconcile', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  listInventoryAlerts: (): Promise<InventoryAlert[]> => requestJson('/api/v1/inventory/alerts'),
  updateInventoryAlert: (
    alertId: string,
    status: 'INVESTIGATING' | 'CLAIM_FILED' | 'RESOLVED',
    resolutionNotes?: string
  ): Promise<InventoryAlert> =>
    requestJson(`/api/v1/inventory/alerts/${alertId}`, {
      method: 'PATCH',
      body: JSON.stringify({
        status,
        resolution_notes: resolutionNotes ?? null,
        actor: 'inventory-analyst-ui',
      }),
    }),

  // Auth
  getMe: (): Promise<AuthPrincipal> => requestJson('/api/v1/auth/me'),
  login: (username: string, password: string): Promise<AuthTokenResponse> =>
    requestJson('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  registerUser: (username: string, password: string, role: string): Promise<unknown> =>
    requestJson('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, password, role }),
    }),

  // Operational Memory
  listMemories: (category?: string): Promise<OperationalMemory[]> => {
    const suffix = category ? `?category=${encodeURIComponent(category)}` : '';
    return requestJson(`/api/v1/memory${suffix}`);
  },
  createMemory: (payload: Record<string, unknown>): Promise<OperationalMemory> =>
    requestJson('/api/v1/memory', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  searchMemories: (query: string, category?: string): Promise<MemorySearchHit[]> => {
    const q = new URLSearchParams({ q: query });
    if (category) q.set('category', category);
    return requestJson(`/api/v1/memory/search?${q.toString()}`);
  },

  // Workers
  triggerSlaSweep: (): Promise<WorkerDispatchResponse> =>
    requestJson('/api/v1/workers/sla-sweep', { method: 'POST' }),
  triggerEdiBatch: (payloads: string[]): Promise<WorkerDispatchResponse> =>
    requestJson('/api/v1/workers/edi214-batch', {
      method: 'POST',
      body: JSON.stringify({ payloads, actor: 'control-tower-ui' }),
    }),

  // Audit
  listAuditLogs: (entityType?: string): Promise<AuditLogEntry[]> => {
    const suffix = entityType ? `?entity_type=${encodeURIComponent(entityType)}&limit=100` : '?limit=100';
    return requestJson(`/api/v1/audit${suffix}`);
  },
  verifyAuditChain: (): Promise<AuditVerifyResult> => requestJson('/api/v1/audit/verify'),
};

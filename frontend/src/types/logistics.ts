export type TabKey =
  | 'overview'
  | 'tracking'
  | 'routing'
  | 'comms'
  | 'inventory'
  | 'memory'
  | 'audit';

export interface HealthStatus {
  status: string;
  service: string;
  app_name: string;
  version: string;
  environment: string;
  llm_provider: string;
  database?: string;
  auth_enabled?: boolean;
  rate_limit_enabled?: boolean;
  otel_enabled?: boolean;
}

export interface AuthPrincipal {
  username: string;
  role: string;
  auth_method: string;
  authenticated: boolean;
  auth_enabled: boolean;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  username: string;
  role: string;
}

export interface OperationalMemory {
  id: string;
  category: string;
  entity_id: string | null;
  corridor: string | null;
  carrier_scac: string | null;
  title: string;
  content: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface MemorySearchHit {
  memory: OperationalMemory;
  score: number;
}

export interface WorkerDispatchResponse {
  execution_mode: string;
  queued: boolean;
  task_id: string | null;
  summary: Record<string, unknown>;
}

export interface AuditLogEntry {
  id: string;
  sequence_number: number;
  entity_type: string;
  entity_id: string;
  action: string;
  actor: string;
  previous_state: string | null;
  new_state: string | null;
  details: Record<string, unknown>;
  prev_hash: string;
  entry_hash: string;
  created_at: string;
}

export interface AuditVerifyResult {
  valid: boolean;
  checked_entries: number;
  first_broken_id: string | null;
}

export interface DashboardSummary {
  total_shipments: number;
  delayed_shipments: number;
  open_tracking_exceptions: number;
  critical_exceptions: number;
  active_disruptions: number;
  pending_route_recommendations: number;
  pending_comm_approvals: number;
  sent_comms: number;
  open_inventory_alerts: number;
  inventory_exposure_usd: number;
  total_audit_entries: number;
  recent_audit_logs: AuditLogEntry[];
}

export interface DemoSeedResponse {
  seeded: boolean;
  message: string;
  counts: Record<string, number>;
}

export interface Shipment {
  id: string;
  reference_number: string;
  bol_number: string;
  pro_number: string;
  carrier_scac: string;
  carrier_name: string;
  mode: string;
  origin: string;
  destination: string;
  last_location: string;
  status: string;
  sla_eta: string;
  current_eta: string;
  delay_minutes: number;
  weight_lbs: number;
  temperature_controlled: boolean;
  created_at: string;
  updated_at: string;
}

export interface TrackingEvent {
  id: string;
  shipment_id: string;
  source_format: string;
  raw_code: string;
  normalized_status: string;
  reason_code: string | null;
  location: string;
  event_timestamp: string;
  reported_eta: string | null;
  notes: string;
  raw_payload: string;
  created_at: string;
}

export interface TrackingException {
  id: string;
  shipment_id: string;
  exception_type: string;
  severity: string;
  status: string;
  delay_minutes: number;
  summary: string;
  resolution_notes: string | null;
  detected_at: string;
  resolved_at: string | null;
}

export interface ShipmentDetail extends Shipment {
  events: TrackingEvent[];
  exceptions: TrackingException[];
}

export interface CarrierLane {
  id: string;
  carrier_scac: string;
  carrier_name: string;
  origin_region: string;
  destination_region: string;
  mode: string;
  base_rate_usd: number;
  fuel_surcharge_pct: number;
  transit_hours: number;
  on_time_rate: number;
  carbon_kg_per_ton_mile: number;
  supports_reefer: boolean;
  max_weight_lbs: number;
  disruption_risk_score: number;
  active: boolean;
  created_at: string;
}

export interface DisruptionAlert {
  id: string;
  region: string;
  disruption_type: string;
  severity: string;
  added_transit_hours: number;
  cost_surcharge_pct: number;
  description: string;
  active: boolean;
  created_at: string;
}

export interface RouteAlternative {
  lane_id: string;
  carrier_scac: string;
  carrier_name: string;
  mode: string;
  estimated_cost_usd: number;
  estimated_transit_hours: number;
  estimated_reliability: number;
  estimated_carbon_kg: number;
  composite_score: number;
}

export interface RouteRecommendation {
  id: string;
  shipment_id: string | null;
  origin_region: string;
  destination_region: string;
  objective: string;
  recommended_lane_id: string;
  recommended_carrier_scac: string;
  recommended_carrier_name: string;
  recommended_mode: string;
  estimated_cost_usd: number;
  estimated_transit_hours: number;
  estimated_reliability: number;
  estimated_carbon_kg: number;
  composite_score: number;
  alternatives: RouteAlternative[];
  rationale: string;
  llm_provider: string;
  status: string;
  reviewed_by: string | null;
  review_notes: string | null;
  created_at: string;
  reviewed_at: string | null;
}

export interface CarrierCommunication {
  id: string;
  shipment_id: string;
  comm_type: string;
  channel: string;
  recipient_name: string;
  recipient_contact: string;
  subject: string;
  body: string;
  grounding_facts: Record<string, unknown>;
  llm_provider: string;
  llm_model: string;
  pii_redacted: boolean;
  redacted_categories: string[];
  status: string;
  created_by: string;
  reviewed_by: string | null;
  review_notes: string | null;
  external_message_id: string | null;
  delivery_attempts?: number;
  delivery_receipt?: Record<string, unknown>;
  created_at: string;
  reviewed_at: string | null;
  sent_at: string | null;
}

export interface DiscrepancyItem {
  sku: string;
  description: string;
  alert_type: string;
  severity: string;
  expected_qty: number;
  received_qty: number;
  damaged_qty: number;
  variance_qty: number;
  financial_impact_usd: number;
}

export interface InventoryReconciliation {
  id: string;
  shipment_id: string | null;
  asn_number: string;
  bol_number: string;
  warehouse_code: string;
  expected_total_units: number;
  received_total_units: number;
  damaged_total_units: number;
  variance_units: number;
  shrinkage_pct: number;
  financial_impact_usd: number;
  status: string;
  discrepancies: DiscrepancyItem[];
  ai_summary: string;
  llm_provider: string;
  reconciled_by: string;
  created_at: string;
}

export interface InventoryAlert {
  id: string;
  reconciliation_id: string;
  shipment_id: string | null;
  sku: string;
  description: string;
  alert_type: string;
  severity: string;
  expected_qty: number;
  received_qty: number;
  damaged_qty: number;
  variance_qty: number;
  financial_impact_usd: number;
  status: string;
  resolution_notes: string | null;
  created_at: string;
  resolved_at: string | null;
}

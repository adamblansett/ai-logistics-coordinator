import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from '../App';

function jsonResponse(data: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  };
}

function createWorkspaceFetchMock(overrides?: {
  empty?: boolean;
  commStatus?: 'PENDING_APPROVAL' | 'APPROVED' | 'SENT';
}) {
  const empty = overrides?.empty ?? false;
  let commStatus = overrides?.commStatus ?? 'PENDING_APPROVAL';
  let recStatus = 'PENDING_REVIEW';
  let alertStatus = 'OPEN';

  const sampleShipment = {
    id: 'shp-1',
    reference_number: 'SHP-2026-1001',
    bol_number: 'BOL-9011001',
    pro_number: 'PRO-7701',
    carrier_scac: 'CRST',
    carrier_name: 'CrestLine Cold Chain',
    mode: 'FTL',
    origin: 'Los Angeles, CA',
    destination: 'Chicago, IL',
    last_location: 'North Platte, NE',
    status: 'DELAYED',
    sla_eta: '2026-11-25T10:00:00Z',
    current_eta: '2026-11-25T19:00:00Z',
    delay_minutes: 540,
    weight_lbs: 34500,
    temperature_controlled: true,
    created_at: '2026-11-24T10:00:00Z',
    updated_at: '2026-11-24T12:00:00Z',
  };

  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = (init?.method ?? 'GET').toUpperCase();

    if (url === '/api/v1/health') {
      return jsonResponse({
        status: 'ok',
        service: 'ai-logistics-coordinator',
        app_name: 'AI Logistics Coordinator',
        version: '0.1.0',
        environment: 'test',
        llm_provider: 'mock',
        database: 'ok',
        auth_enabled: false,
      });
    }

    if (url === '/api/v1/auth/me') {
      return jsonResponse({
        username: 'dev-admin',
        role: 'ADMIN',
        auth_method: 'dev_anonymous',
        authenticated: false,
        auth_enabled: false,
      });
    }

    if (url === '/api/v1/auth/login' && method === 'POST') {
      return jsonResponse({
        access_token: 'mock-jwt-token',
        token_type: 'bearer',
        expires_in: 28800,
        username: 'dispatcher',
        role: 'DISPATCHER',
      });
    }

    if (url.startsWith('/api/v1/memory/search')) {
      return jsonResponse([
        {
          memory: {
            id: 'mem-1',
            category: 'ROUTE_PLAYBOOK',
            entity_id: null,
            corridor: 'Los Angeles, CA -> Chicago, IL',
            carrier_scac: 'BNSF',
            title: 'Winter Storm I-80 Reefer Intermodal Fallback',
            content: 'Use BNSF Cold Intermodal during lake-effect snow advisories.',
            metadata: {},
            created_at: '2026-11-26T10:00:00Z',
          },
          score: 0.91,
        },
      ]);
    }

    if (url.startsWith('/api/v1/memory')) {
      return jsonResponse([]);
    }

    if (url === '/api/v1/workers/sla-sweep' && method === 'POST') {
      return jsonResponse({
        execution_mode: 'inline',
        queued: false,
        task_id: null,
        summary: {
          checked_shipments: 5,
          breached_shipments: 2,
          exceptions_opened_or_updated: 1,
        },
      });
    }

    if (url === '/api/v1/demo/seed' && method === 'POST') {
      return jsonResponse({
        seeded: true,
        message: 'Seeded demo workspace.',
        counts: { shipments: 5 },
      });
    }

    if (url === '/api/v1/dashboard/summary') {
      return jsonResponse({
        total_shipments: empty ? 0 : 5,
        delayed_shipments: empty ? 0 : 4,
        open_tracking_exceptions: empty ? 0 : 4,
        critical_exceptions: empty ? 0 : 1,
        active_disruptions: empty ? 0 : 2,
        pending_route_recommendations: empty ? 0 : recStatus === 'PENDING_REVIEW' ? 1 : 0,
        pending_comm_approvals: empty ? 0 : commStatus === 'PENDING_APPROVAL' ? 1 : 0,
        sent_comms: commStatus === 'SENT' ? 1 : 0,
        open_inventory_alerts: empty ? 0 : alertStatus === 'RESOLVED' ? 0 : 2,
        inventory_exposure_usd: empty ? 0 : 2775.0,
        total_audit_entries: empty ? 0 : 18,
        recent_audit_logs: [],
      });
    }

    if (url.startsWith('/api/v1/tracking/shipments/shp-1')) {
      return jsonResponse({
        ...sampleShipment,
        events: [
          {
            id: 'ev-1',
            shipment_id: 'shp-1',
            source_format: 'EDI_214',
            raw_code: 'SD',
            normalized_status: 'DELAYED',
            reason_code: 'WEATHER',
            location: 'North Platte, NE',
            event_timestamp: '2026-11-24T12:00:00Z',
            reported_eta: '2026-11-25T19:00:00Z',
            notes: 'EDI 214 AT7=SD; Reason=WEATHER',
            raw_payload: '{}',
            created_at: '2026-11-24T12:00:00Z',
          },
        ],
        exceptions: [],
      });
    }

    if (url.startsWith('/api/v1/tracking/shipments')) {
      return jsonResponse(empty ? [] : [sampleShipment]);
    }

    if (url === '/api/v1/tracking/edi214' && method === 'POST') {
      return jsonResponse({ event: {}, shipment: sampleShipment, exception: null });
    }

    if (url === '/api/v1/tracking/exceptions') {
      return jsonResponse(
        empty
          ? []
          : [
              {
                id: 'exc-1',
                shipment_id: 'shp-1',
                exception_type: 'WEATHER_DISRUPTION',
                severity: 'CRITICAL',
                status: 'OPEN',
                delay_minutes: 540,
                summary: 'Winter storm delay near North Platte, NE',
                resolution_notes: null,
                detected_at: '2026-11-24T12:00:00Z',
                resolved_at: null,
              },
            ]
      );
    }

    if (url === '/api/v1/routing/lanes') {
      return jsonResponse(
        empty
          ? []
          : [
              {
                id: 'lane-1',
                carrier_scac: 'BNSF',
                carrier_name: 'BNSF Cold Intermodal',
                origin_region: 'Los Angeles, CA',
                destination_region: 'Chicago, IL',
                mode: 'INTERMODAL',
                base_rate_usd: 2490,
                fuel_surcharge_pct: 9,
                transit_hours: 56,
                on_time_rate: 0.96,
                carbon_kg_per_ton_mile: 0.06,
                supports_reefer: true,
                max_weight_lbs: 44000,
                disruption_risk_score: 0.08,
                active: true,
                created_at: '2026-11-24T10:00:00Z',
              },
            ]
      );
    }

    if (url === '/api/v1/routing/disruptions') {
      return jsonResponse([]);
    }

    if (url === '/api/v1/routing/recommendations') {
      return jsonResponse(
        empty
          ? []
          : [
              {
                id: 'rec-1',
                shipment_id: 'shp-1',
                origin_region: 'Los Angeles, CA',
                destination_region: 'Chicago, IL',
                objective: 'BALANCED',
                recommended_lane_id: 'lane-1',
                recommended_carrier_scac: 'BNSF',
                recommended_carrier_name: 'BNSF Cold Intermodal',
                recommended_mode: 'INTERMODAL',
                estimated_cost_usd: 2890,
                estimated_transit_hours: 64,
                estimated_reliability: 0.88,
                estimated_carbon_kg: 2436,
                composite_score: 84.2,
                alternatives: [],
                rationale: 'Selected BNSF Cold Intermodal for lowest disruption risk.',
                llm_provider: 'mock',
                status: recStatus,
                reviewed_by: null,
                review_notes: null,
                created_at: '2026-11-24T12:00:00Z',
                reviewed_at: null,
              },
            ]
      );
    }

    if (url === '/api/v1/routing/recommendations/rec-1/decision' && method === 'POST') {
      recStatus = 'APPROVED';
      return jsonResponse({ id: 'rec-1', status: 'APPROVED' });
    }

    if (url === '/api/v1/comms') {
      return jsonResponse(
        empty
          ? []
          : [
              {
                id: 'comm-1',
                shipment_id: 'shp-1',
                comm_type: 'DELAY_ESCALATION',
                channel: 'EMAIL',
                recipient_name: 'CrestLine Control Desk',
                recipient_contact: 'ops@crestline-example.com',
                subject: 'SLA Delay Escalation — SHP-2026-1001',
                body: 'Grounded update for BOL-9011001.',
                grounding_facts: { bol_number: 'BOL-9011001', pro_number: 'PRO-7701', delay_minutes: 540 },
                llm_provider: 'mock',
                llm_model: 'deterministic-logistics-v1',
                pii_redacted: false,
                redacted_categories: [],
                status: commStatus,
                created_by: 'demo-seed',
                reviewed_by: null,
                review_notes: null,
                external_message_id: commStatus === 'SENT' ? 'MSG-COMM1' : null,
                created_at: '2026-11-24T12:00:00Z',
                reviewed_at: null,
                sent_at: null,
              },
            ]
      );
    }

    if (url === '/api/v1/comms/comm-1/decision' && method === 'POST') {
      commStatus = 'APPROVED';
      return jsonResponse({ id: 'comm-1', status: 'APPROVED' });
    }

    if (url === '/api/v1/comms/comm-1/send' && method === 'POST') {
      commStatus = 'SENT';
      return jsonResponse({ id: 'comm-1', status: 'SENT', external_message_id: 'MSG-COMM1' });
    }

    if (url === '/api/v1/inventory/reconciliations') {
      return jsonResponse([]);
    }

    if (url === '/api/v1/inventory/alerts') {
      return jsonResponse(
        empty
          ? []
          : [
              {
                id: 'inv-1',
                reconciliation_id: 'rec-inv-1',
                shipment_id: 'shp-1',
                sku: 'SKU-IND-880',
                description: 'Precision Hydraulic Valves',
                alert_type: 'SHORTAGE',
                severity: 'CRITICAL',
                expected_qty: 100,
                received_qty: 88,
                damaged_qty: 0,
                variance_qty: -12,
                financial_impact_usd: 2220.0,
                status: alertStatus,
                resolution_notes: null,
                created_at: '2026-11-24T12:00:00Z',
                resolved_at: null,
              },
            ]
      );
    }

    if (url === '/api/v1/inventory/alerts/inv-1' && method === 'PATCH') {
      alertStatus = 'RESOLVED';
      return jsonResponse({ id: 'inv-1', status: 'RESOLVED' });
    }

    if (url.startsWith('/api/v1/audit/verify')) {
      return jsonResponse({ valid: true, checked_entries: 18, first_broken_id: null });
    }

    if (url.startsWith('/api/v1/audit')) {
      return jsonResponse(
        empty
          ? []
          : [
              {
                id: 'aud-1',
                sequence_number: 1,
                entity_type: 'shipment',
                entity_id: 'shp-1',
                action: 'CREATED',
                actor: 'demo-seed',
                previous_state: null,
                new_state: 'PLANNED',
                details: {},
                prev_hash: 'GENESIS',
                entry_hash: 'abcdef1234567890abcdef1234567890',
                created_at: '2026-11-24T10:00:00Z',
              },
            ]
      );
    }

    return jsonResponse({});
  });
}

describe('AI Logistics Coordinator Control Tower UI', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders live API health, empty-state demo CTA, and seeds workspace', async () => {
    const user = userEvent.setup();
    const mockFetch = createWorkspaceFetchMock({ empty: true });
    vi.stubGlobal('fetch', mockFetch);

    render(<App />);

    expect(screen.getByRole('heading', { name: 'AI Logistics Coordinator' })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/API Healthy \(mock\)/i)).toBeInTheDocument();
    });
    expect(mockFetch).toHaveBeenCalledWith('/api/v1/health');

    const seedButton = await screen.findByRole('button', {
      name: /Load Demo Logistics Scenario/i,
    });
    await user.click(seedButton);
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/v1/demo/seed',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('navigates across tracking, routing, comms approval gating, inventory, and audit verify', async () => {
    const user = userEvent.setup();
    const mockFetch = createWorkspaceFetchMock();
    vi.stubGlobal('fetch', mockFetch);

    render(<App />);
    await waitFor(() => {
      expect(screen.getByText(/API Healthy \(mock\)/i)).toBeInTheDocument();
    });

    const nav = screen.getByRole('navigation', { name: /Control tower sections/i });

    // Freight Tracking tab + EDI 214 ingestion
    await user.click(within(nav).getByRole('button', { name: /Freight Tracking/i }));
    expect(await screen.findByRole('heading', { name: 'SHP-2026-1001' })).toBeInTheDocument();
    expect(screen.getByText('WEATHER_DISRUPTION')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Sample EDI 214/i }));
    await user.click(screen.getByRole('button', { name: /Ingest EDI 214 Payload/i }));
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/tracking/edi214',
        expect.objectContaining({ method: 'POST' })
      );
    });

    // Route Optimizer tab + Approve recommendation
    await user.click(within(nav).getByRole('button', { name: /Route Optimizer/i }));
    expect(
      await screen.findByText(/Selected BNSF Cold Intermodal for lowest disruption risk/i)
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Approve Route/i }));
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/routing/recommendations/rec-1/decision',
        expect.objectContaining({ method: 'POST' })
      );
    });

    // Carrier Comms tab + Approve then Send gating
    await user.click(within(nav).getByRole('button', { name: /Carrier Comms/i }));
    expect(await screen.findByText(/Send locked until approved/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Dispatch to Carrier/i })).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Approve Draft/i }));
    const dispatchButton = await screen.findByRole('button', { name: /Dispatch to Carrier/i });
    await user.click(dispatchButton);
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/comms/comm-1/send',
        expect.objectContaining({ method: 'POST' })
      );
    });

    // Inventory Alerts tab + Resolve alert
    await user.click(within(nav).getByRole('button', { name: /Inventory Alerts/i }));
    expect(await screen.findByText('SKU-IND-880')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /^Resolve$/i }));
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/inventory/alerts/inv-1',
        expect.objectContaining({ method: 'PATCH' })
      );
    });

    // Audit Trail tab + Verify Hash Chain
    await user.click(within(nav).getByRole('button', { name: /Audit Trail/i }));
    await user.click(screen.getByRole('button', { name: /Verify Hash Chain/i }));
    expect(
      await screen.findByText(/Hash Chain Verified: all 18 entries intact/i)
    ).toBeInTheDocument();

    // Memory & Ops tab + Semantic Search + SLA Sweep
    await user.click(within(nav).getByRole('button', { name: /Memory & Ops/i }));
    const searchInput = await screen.findByPlaceholderText(/Search historical resolutions/i);
    await user.type(searchInput, 'winter storm BNSF');
    await user.click(screen.getByRole('button', { name: /Semantic Search/i }));
    expect(
      await screen.findByText(/Winter Storm I-80 Reefer Intermodal Fallback/i)
    ).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Run SLA Breach Sweep/i }));
    expect(await screen.findByText(/Breached 2/i)).toBeInTheDocument();

    // Sign-In modal submits /api/v1/auth/login
    await user.click(screen.getByRole('button', { name: /Sign In/i }));
    await user.click(screen.getByRole('button', { name: /Authenticate/i }));
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/auth/login',
        expect.objectContaining({ method: 'POST' })
      );
    });
  });
});

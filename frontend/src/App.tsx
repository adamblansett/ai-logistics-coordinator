import { useCallback, useEffect, useState } from 'react';
import {
  Activity,
  AlertCircle,
  Brain,
  LayoutDashboard,
  LogIn,
  LogOut,
  MessageSquare,
  PackageCheck,
  RefreshCw,
  Route,
  ShieldCheck,
  Sparkles,
  Truck,
  UserCheck,
  X,
} from 'lucide-react';
import { api, getAuthToken, setAuthToken } from './api/client';
import { AuditPanel } from './components/AuditPanel';
import { CommsPanel } from './components/CommsPanel';
import { InventoryPanel } from './components/InventoryPanel';
import { MemoryOpsPanel } from './components/MemoryOpsPanel';
import { OverviewPanel } from './components/OverviewPanel';
import { RoutingPanel } from './components/RoutingPanel';
import { TrackingPanel } from './components/TrackingPanel';
import type {
  AuditLogEntry,
  AuthPrincipal,
  CarrierCommunication,
  CarrierLane,
  DashboardSummary,
  DisruptionAlert,
  HealthStatus,
  InventoryAlert,
  InventoryReconciliation,
  OperationalMemory,
  RouteRecommendation,
  Shipment,
  TabKey,
  TrackingException,
} from './types/logistics';

export default function App() {
  const [activeTab, setActiveTab] = useState<TabKey>('overview');
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [principal, setPrincipal] = useState<AuthPrincipal | null>(null);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [loginUser, setLoginUser] = useState('dispatcher');
  const [loginPassword, setLoginPassword] = useState('dispatch123!');
  const [authBusy, setAuthBusy] = useState(false);

  const [offline, setOffline] = useState(false);
  const [loading, setLoading] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [exceptions, setExceptions] = useState<TrackingException[]>([]);
  const [lanes, setLanes] = useState<CarrierLane[]>([]);
  const [disruptions, setDisruptions] = useState<DisruptionAlert[]>([]);
  const [recommendations, setRecommendations] = useState<RouteRecommendation[]>([]);
  const [comms, setComms] = useState<CarrierCommunication[]>([]);
  const [reconciliations, setReconciliations] = useState<InventoryReconciliation[]>([]);
  const [inventoryAlerts, setInventoryAlerts] = useState<InventoryAlert[]>([]);
  const [memories, setMemories] = useState<OperationalMemory[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [auditFilter, setAuditFilter] = useState('');

  const [draftPrefill, setDraftPrefill] = useState<{
    shipmentId?: string;
    commType?: string;
  }>({});

  const refreshWorkspace = useCallback(
    async (entityFilter = auditFilter) => {
      setLoading(true);
      try {
        const [
          meRes,
          summaryRes,
          shipmentsRes,
          exceptionsRes,
          lanesRes,
          disruptionsRes,
          recsRes,
          commsRes,
          reconRes,
          invAlertsRes,
          memoriesRes,
          auditRes,
        ] = await Promise.all([
          api.getMe().catch(() => null),
          api.getDashboardSummary(),
          api.listShipments(),
          api.listExceptions(),
          api.listLanes(),
          api.listDisruptions(),
          api.listRecommendations(),
          api.listComms(),
          api.listReconciliations(),
          api.listInventoryAlerts(),
          api.listMemories().catch(() => [] as OperationalMemory[]),
          api.listAuditLogs(entityFilter || undefined),
        ]);

        if (meRes) setPrincipal(meRes);
        setSummary(summaryRes);
        setShipments(shipmentsRes);
        setExceptions(exceptionsRes);
        setLanes(lanesRes);
        setDisruptions(disruptionsRes);
        setRecommendations(recsRes);
        setComms(commsRes);
        setReconciliations(reconRes);
        setInventoryAlerts(invAlertsRes);
        setMemories(memoriesRes);
        setAuditLogs(auditRes);
      } catch (err) {
        setErrorBanner(err instanceof Error ? err.message : 'Failed to refresh workspace data.');
      } finally {
        setLoading(false);
      }
    },
    [auditFilter]
  );

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      try {
        const response = await fetch('/api/v1/health');
        if (!response.ok) {
          if (!cancelled) setOffline(true);
          return;
        }
        const payload = (await response.json()) as HealthStatus;
        if (!cancelled) {
          setHealth(payload);
          setOffline(false);
          if (payload.auth_enabled && !getAuthToken()) {
            setShowAuthModal(true);
            return;
          }
          await refreshWorkspace('');
        }
      } catch {
        if (!cancelled) setOffline(true);
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [refreshWorkspace]);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setAuthBusy(true);
    setErrorBanner(null);
    try {
      const tokenRes = await api.login(loginUser, loginPassword);
      setAuthToken(tokenRes.access_token);
      setShowAuthModal(false);
      await refreshWorkspace();
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : 'Sign-in failed.');
    } finally {
      setAuthBusy(false);
    }
  }

  async function handleLogout() {
    setAuthToken(null);
    setPrincipal(null);
    if (health?.auth_enabled) {
      setShowAuthModal(true);
    } else {
      await refreshWorkspace();
    }
  }

  async function handleSeedDemo() {
    setSeeding(true);
    setErrorBanner(null);
    try {
      await api.seedDemo();
      await refreshWorkspace();
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : 'Failed to seed demo workspace.');
    } finally {
      setSeeding(false);
    }
  }

  async function handleAuditFilterChange(entityType: string) {
    setAuditFilter(entityType);
    try {
      const logs = await api.listAuditLogs(entityType || undefined);
      setAuditLogs(logs);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : 'Failed to filter audit logs.');
    }
  }

  function handleDraftClaim(shipmentId: string) {
    setDraftPrefill({ shipmentId, commType: 'DISCREPANCY_CLAIM' });
    setActiveTab('comms');
  }

  const tabs: { key: TabKey; label: string; icon: typeof LayoutDashboard; count?: number }[] = [
    { key: 'overview', label: 'Overview', icon: LayoutDashboard },
    {
      key: 'tracking',
      label: 'Freight Tracking',
      icon: Truck,
      count: summary?.open_tracking_exceptions,
    },
    {
      key: 'routing',
      label: 'Route Optimizer',
      icon: Route,
      count: summary?.pending_route_recommendations,
    },
    {
      key: 'comms',
      label: 'Carrier Comms',
      icon: MessageSquare,
      count: summary?.pending_comm_approvals,
    },
    {
      key: 'inventory',
      label: 'Inventory Alerts',
      icon: PackageCheck,
      count: summary?.open_inventory_alerts,
    },
    { key: 'memory', label: 'Memory & Ops', icon: Brain },
    { key: 'audit', label: 'Audit Trail', icon: ShieldCheck },
  ];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-indigo-600">
                Phase 2 — Operations Control Tower
              </p>
              <h1 className="mt-0.5 text-2xl font-bold tracking-tight text-slate-900">
                AI Logistics Coordinator
              </h1>
              <p className="mt-0.5 text-xs text-slate-600">
                Self-hosted freight tracking, route optimization, human-approved carrier
                communications, operational memory, and ASN/BOL discrepancy alerting.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {summary?.total_shipments === 0 && !offline && (
                <button
                  type="button"
                  onClick={() => void handleSeedDemo()}
                  disabled={seeding}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  {seeding ? 'Seeding...' : 'Seed Demo Data'}
                </button>
              )}

              {!offline && (
                <button
                  type="button"
                  onClick={() => void refreshWorkspace()}
                  disabled={loading}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
                  Refresh
                </button>
              )}

              {!offline && (
                principal?.authenticated ? (
                  <div className="flex items-center gap-1.5 rounded-lg border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-800">
                    <UserCheck className="h-3.5 w-3.5" />
                    <span>
                      {principal.username} ({principal.role})
                    </span>
                    <button
                      type="button"
                      onClick={() => void handleLogout()}
                      className="ml-1 rounded p-0.5 hover:bg-emerald-100"
                      title="Sign out"
                    >
                      <LogOut className="h-3 w-3" />
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setShowAuthModal(true)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                  >
                    <LogIn className="h-3.5 w-3.5" />
                    Sign In
                  </button>
                )
              )}

              <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3.5 py-1.5 text-xs font-medium">
                <Activity
                  className={`h-3.5 w-3.5 ${
                    health?.status === 'ok'
                      ? 'text-emerald-600'
                      : offline
                      ? 'text-amber-600'
                      : 'text-slate-400'
                  }`}
                />
                <span>
                  {health?.status === 'ok'
                    ? `API Healthy (${health.llm_provider})`
                    : offline
                    ? 'Offline Starter Preview'
                    : 'Checking API...'}
                </span>
              </div>
            </div>
          </div>

          <nav aria-label="Control tower sections" className="mt-4 flex flex-wrap gap-1.5">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.key;
              return (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setActiveTab(tab.key)}
                  className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                    isActive
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  <span>{tab.label}</span>
                  {typeof tab.count === 'number' && tab.count > 0 && (
                    <span
                      className={`rounded-full px-1.5 py-0.2 text-[10px] font-bold ${
                        isActive
                          ? 'bg-white/20 text-white'
                          : 'bg-amber-100 text-amber-800'
                      }`}
                    >
                      {tab.count}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>
      </header>

      {showAuthModal && (
        <div
          role="dialog"
          aria-label="Operator Sign In"
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
        >
          <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-5 shadow-xl">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-900">Control Tower Sign In</h2>
              {!health?.auth_enabled && (
                <button
                  type="button"
                  aria-label="Close sign in"
                  onClick={() => setShowAuthModal(false)}
                  className="rounded p-1 text-slate-400 hover:bg-slate-100"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
            <p className="mt-1 text-xs text-slate-500">
              Sign in with JWT credentials for verified RBAC attribution.
            </p>
            <form onSubmit={(e) => void handleLogin(e)} className="mt-3 space-y-3 text-xs">
              <div>
                <label className="block font-medium text-slate-700">Username</label>
                <input
                  required
                  aria-label="Username"
                  value={loginUser}
                  onChange={(e) => setLoginUser(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-2.5 py-1.5"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700">Password</label>
                <input
                  required
                  type="password"
                  aria-label="Password"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-2.5 py-1.5"
                />
              </div>
              <button
                type="submit"
                disabled={authBusy}
                className="w-full rounded-lg bg-indigo-600 py-2 font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
              >
                {authBusy ? 'Signing In...' : 'Authenticate'}
              </button>
            </form>
          </div>
        </div>
      )}

      <main className="mx-auto max-w-6xl space-y-6 px-6 py-6">
        {errorBanner && (
          <div
            role="alert"
            className="flex items-center justify-between gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs font-medium text-rose-800"
          >
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{errorBanner}</span>
            </div>
            <button
              type="button"
              aria-label="Dismiss error"
              onClick={() => setErrorBanner(null)}
              className="rounded p-1 hover:bg-rose-100"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {activeTab === 'overview' && (
          <OverviewPanel
            summary={summary}
            seeding={seeding}
            onSeedDemo={handleSeedDemo}
            onNavigate={setActiveTab}
          />
        )}

        {activeTab === 'tracking' && (
          <TrackingPanel
            shipments={shipments}
            exceptions={exceptions}
            onRefresh={() => refreshWorkspace()}
            onError={(msg) => setErrorBanner(msg)}
          />
        )}

        {activeTab === 'routing' && (
          <RoutingPanel
            shipments={shipments}
            lanes={lanes}
            disruptions={disruptions}
            recommendations={recommendations}
            onRefresh={() => refreshWorkspace()}
            onError={(msg) => setErrorBanner(msg)}
          />
        )}

        {activeTab === 'comms' && (
          <CommsPanel
            shipments={shipments}
            comms={comms}
            initialShipmentId={draftPrefill.shipmentId}
            initialCommType={draftPrefill.commType}
            onRefresh={() => refreshWorkspace()}
            onError={(msg) => setErrorBanner(msg)}
          />
        )}

        {activeTab === 'inventory' && (
          <InventoryPanel
            shipments={shipments}
            reconciliations={reconciliations}
            alerts={inventoryAlerts}
            onRefresh={() => refreshWorkspace()}
            onDraftClaim={handleDraftClaim}
            onError={(msg) => setErrorBanner(msg)}
          />
        )}

        {activeTab === 'memory' && (
          <MemoryOpsPanel
            memories={memories}
            onRefresh={() => refreshWorkspace()}
            onError={(msg) => setErrorBanner(msg)}
          />
        )}

        {activeTab === 'audit' && (
          <AuditPanel
            logs={auditLogs}
            entityFilter={auditFilter}
            onFilterChange={(val) => void handleAuditFilterChange(val)}
            onError={(msg) => setErrorBanner(msg)}
          />
        )}
      </main>
    </div>
  );
}

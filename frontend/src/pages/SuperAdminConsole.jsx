import { useEffect, useState } from "react";
import {
  adminFetch,
  fetchSuperAdminAudit,
  fetchSuperAdminInvoices,
  fetchSuperAdminMetrics,
  fetchSuperAdminProjects,
  fetchSuperAdminTenants,
  overrideTenantPlan,
  runDemo,
  setTenantStatus,
} from "../api";
import { ADMIN_KEY_STORAGE, useAuth } from "../auth";
import MonacoDiffViewer from "../components/MonacoDiffViewer";

function getRenewalWhatsAppUrl(tenant) {
  const name = tenant.owner_name || tenant.name || "Customer";
  const plan = (tenant.plan || "PRO").toUpperCase();
  const text = `Hi ${name}! Hope you are finding ShadowFix AI helpful for your repositories. Your ShadowFix ${plan} Plan subscription is due for monthly renewal. You can renew seamlessly via this link: https://razorpay.me/@shivamkumar98. Let me know once done so your high-speed AI pipeline stays active. Thank you!`;
  return `https://api.whatsapp.com/send?text=${encodeURIComponent(text)}`;
}

const TABS = [
  "Master KPI",
  "User Admins & Workspaces",
  "Global Projects",
  "Financials & Invoices",
  "Incidents",
  "Security & Audit",
];

export default function SuperAdminConsole() {
  const { isSuperAdmin } = useAuth();
  const [adminKey, setAdminKey] = useState(
    () => sessionStorage.getItem(ADMIN_KEY_STORAGE) || ""
  );
  const [tab, setTab] = useState("Master KPI");
  const [metrics, setMetrics] = useState(null);
  const [tenants, setTenants] = useState([]);
  const [projects, setProjects] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [audit, setAudit] = useState([]);
  const [dossier, setDossier] = useState(null);
  const [selectedIncidentId, setSelectedIncidentId] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function loadAll(key = adminKey) {
    try {
      const [m, t, p, inv, aud, d] = await Promise.all([
        fetchSuperAdminMetrics(key).catch(() => null),
        fetchSuperAdminTenants(key).catch(() => ({ tenants: [] })),
        fetchSuperAdminProjects(key).catch(() => ({ projects: [] })),
        fetchSuperAdminInvoices(key).catch(() => ({ invoices: [] })),
        fetchSuperAdminAudit(key).catch(() => ({ audit: [] })),
        adminFetch("/api/admin/dossier", key).catch(() => null),
      ]);

      if (m) setMetrics(m);
      if (t) setTenants(t.tenants || []);
      if (p) setProjects(p.projects || []);
      if (inv) setInvoices(inv.invoices || []);
      if (aud) setAudit(aud.audit || []);
      if (d) {
        setDossier(d);
        if (!selectedIncidentId && d.incidents?.[0]) {
          setSelectedIncidentId(d.incidents[0].id);
        }
      }
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadAll(adminKey);
    const interval = setInterval(() => loadAll(adminKey), 5000);
    return () => clearInterval(interval);
  }, [adminKey]);

  async function toggleKill() {
    setError("");
    try {
      const next = !metrics?.global_kill_switch && !dossier?.control?.kill_switch;
      await adminFetch("/api/admin/kill-switch", adminKey, {
        method: "POST",
        body: JSON.stringify({ enabled: next }),
      });
      setMessage(next ? "Global kill switch is ON. All runs stopped." : "Global kill switch is OFF.");
      await loadAll();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handlePlanOverride(tenantId, newPlan) {
    setError("");
    try {
      await overrideTenantPlan(adminKey, tenantId, newPlan);
      setMessage(`Tenant plan updated to ${newPlan}.`);
      await loadAll();
      setTimeout(() => setMessage(""), 3000);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleStatusToggle(tenantId, currentStatus) {
    setError("");
    const nextStatus = currentStatus === "active" ? "suspended" : "active";
    try {
      await setTenantStatus(adminKey, tenantId, nextStatus);
      setMessage(`Tenant ${tenantId} status set to ${nextStatus}.`);
      await loadAll();
      setTimeout(() => setMessage(""), 3000);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleApprove(incidentId) {
    setError("");
    try {
      const body = await adminFetch(`/api/admin/approve/${incidentId}`, adminKey, {
        method: "POST",
      });
      setMessage(`${body.mode} · ${body.expires_in_seconds}s · ${body.message}`);
      await loadAll();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleRunDemo() {
    setBusy(true);
    setError("");
    try {
      const res = await runDemo();
      setMessage(`Incident ${res.id} queued and executing.`);
      setTab("Incidents");
      setSelectedIncidentId(res.id);
      await loadAll();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const selectedIncident =
    dossier?.incidents?.find((item) => item.id === selectedIncidentId) ||
    dossier?.incidents?.[0];

  return (
    <main className="mx-auto max-w-7xl px-6 py-10">
      {/* ── Super Admin Top Header ── */}
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-8">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-mint/20 text-xs">👑</span>
            <p className="font-mono text-xs font-bold tracking-[0.2em] text-mint uppercase">
              MASTER SUPER ADMIN DESK
            </p>
          </div>
          <h1 className="mt-2 text-3xl font-black tracking-tight">Platform Control Center</h1>
          <p className="mt-1 text-sm text-mute">
            Full bird's-eye control over all User Admins, imported projects, active subscriptions, revenue (MRR), and system guardrails.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={handleRunDemo}
            disabled={busy}
            className="rounded-full bg-mint px-4 py-2 text-xs font-extrabold text-ink shadow transition hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Executing..." : "⚡ Run Shopkart Test Incident"}
          </button>
          <button
            type="button"
            onClick={toggleKill}
            className={`rounded-full px-4 py-2 text-xs font-bold transition border ${
              metrics?.global_kill_switch
                ? "bg-heat text-white border-heat animate-pulse"
                : "border-line text-mute hover:text-paper"
            }`}
          >
            {metrics?.global_kill_switch ? "⚠️ Turn Kill Switch OFF" : "Emergency Kill Switch"}
          </button>
        </div>
      </div>

      {/* ── Admin Key & Alert Banners ── */}
      <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <label className="text-xs font-bold text-mute uppercase font-mono">Master Key:</label>
          <input
            type="password"
            value={adminKey}
            onChange={(e) => {
              setAdminKey(e.target.value);
              sessionStorage.setItem(ADMIN_KEY_STORAGE, e.target.value);
            }}
            className="rounded-xl border border-line bg-ink px-3 py-1.5 font-mono text-xs text-paper focus:border-brand focus:outline-none"
          />
        </div>

        {message && (
          <span className="rounded-xl border border-mint/30 bg-mint/10 px-4 py-1.5 text-xs font-bold text-mint">
            {message}
          </span>
        )}
        {error && (
          <span className="rounded-xl border border-heat/30 bg-heat/10 px-4 py-1.5 text-xs font-bold text-heat">
            {error}
          </span>
        )}
      </div>

      {/* ── KPI Metric Cards ── */}
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <div className="card p-5">
          <p className="font-mono text-xs font-bold text-mute uppercase">Monthly Revenue</p>
          <p className="mt-2 text-3xl font-black text-mint">
            ${metrics?.mrr || 0} <span className="text-xs text-mute font-normal">MRR</span>
          </p>
          <p className="mt-1 text-[11px] text-mute">Across all active plans</p>
        </div>

        <div className="card p-5">
          <p className="font-mono text-xs font-bold text-mute uppercase">Total Tenants</p>
          <p className="mt-2 text-3xl font-black text-paper">{metrics?.total_tenants || 0}</p>
          <p className="mt-1 text-[11px] text-mute">Registered User Admins</p>
        </div>

        <div className="card p-5">
          <p className="font-mono text-xs font-bold text-mute uppercase">Global Projects</p>
          <p className="mt-2 text-3xl font-black text-paper">{metrics?.total_projects || 0}</p>
          <p className="mt-1 text-[11px] text-mute">Imported Repositories</p>
        </div>

        <div className="card p-5">
          <p className="font-mono text-xs font-bold text-mute uppercase">Platform Incidents</p>
          <p className="mt-2 text-3xl font-black text-paper">{metrics?.total_incidents || 0}</p>
          <p className="mt-1 text-[11px] text-mute">{metrics?.active_incidents || 0} in progress</p>
        </div>

        <div className="card p-5">
          <p className="font-mono text-xs font-bold text-mute uppercase">Platform Status</p>
          <div className="mt-2 flex items-center gap-2">
            <span
              className={`h-3 w-3 rounded-full ${
                metrics?.global_kill_switch ? "bg-heat animate-ping" : "bg-mint"
              }`}
            />
            <span className="text-lg font-bold">
              {metrics?.global_kill_switch ? "KILLED" : "HEALTHY"}
            </span>
          </div>
          <p className="mt-1 text-[11px] text-mute">Multi-agent desk operational</p>
        </div>
      </div>

      {/* ── Navigation Tabs ── */}
      <div className="mt-10 flex flex-wrap gap-2 border-b border-line pb-3">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`rounded-full px-5 py-2 text-xs font-bold transition ${
              tab === t
                ? "bg-brand text-white shadow-md shadow-brand/20"
                : "border border-line text-mute hover:text-paper"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* ── Tab 1: Master KPI ── */}
      {tab === "Master KPI" && (
        <div className="mt-8 space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            <div className="card p-6">
              <h3 className="text-base font-bold text-paper">Subscription Distribution</h3>
              <p className="mt-1 text-xs text-mute">Breakdown of customer workspaces by tier</p>
              <div className="mt-5 space-y-3 font-mono text-xs">
                {["free", "pro", "ultra", "pro_max"].map((plan) => {
                  const count = metrics?.plan_distribution?.[plan] || 0;
                  return (
                    <div key={plan} className="flex items-center justify-between rounded-xl bg-ink/70 px-4 py-3">
                      <span className="font-bold uppercase text-paper">{plan}</span>
                      <span className="rounded-full bg-brand/20 px-3 py-1 font-bold text-mint">
                        {count} workspace{count === 1 ? "" : "s"}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="card p-6">
              <h3 className="text-base font-bold text-paper">System Health & Integrations</h3>
              <p className="mt-1 text-xs text-mute">Active vector database and AI engines</p>
              <div className="mt-5 space-y-3 font-mono text-xs">
                <div className="flex items-center justify-between rounded-xl bg-ink/70 px-4 py-3">
                  <span>Qdrant AST Vector DB</span>
                  <span className="text-mint font-bold">Disk (Operational)</span>
                </div>
                <div className="flex items-center justify-between rounded-xl bg-ink/70 px-4 py-3">
                  <span>Repair Engine</span>
                  <span className="text-mint font-bold">Gemini 2.5 Pro / Deterministic</span>
                </div>
                <div className="flex items-center justify-between rounded-xl bg-ink/70 px-4 py-3">
                  <span>AWS STS JIT Ledger</span>
                  <span className="text-mint font-bold">15-Minute Ephemeral Sessions</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Tab 2: User Admins & Workspaces ── */}
      {tab === "User Admins & Workspaces" && (
        <div className="mt-8">
          <div className="overflow-x-auto rounded-2xl border border-line bg-panel">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-line bg-ink/70 font-mono uppercase text-mute">
                <tr>
                  <th className="px-5 py-3">Workspace / Organization</th>
                  <th className="px-5 py-3">Owner & Email</th>
                  <th className="px-5 py-3">Projects</th>
                  <th className="px-5 py-3">Current Plan</th>
                  <th className="px-5 py-3">Super Admin Plan Override</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/60">
                {tenants.map((t) => (
                  <tr key={t.id} className="hover:bg-panel-2">
                    <td className="px-5 py-4 font-bold text-paper">
                      {t.name}
                      <p className="font-mono text-[10px] text-mute">{t.id}</p>
                    </td>
                    <td className="px-5 py-4">
                      <p className="font-semibold text-paper">{t.owner_name}</p>
                      <p className="font-mono text-[11px] text-mute">{t.owner_email}</p>
                    </td>
                    <td className="px-5 py-4 font-mono font-bold text-mint">
                      {t.projects_count} repo{t.projects_count === 1 ? "" : "s"}
                    </td>
                    <td className="px-5 py-4 font-mono font-bold uppercase text-paper">
                      <span className="rounded-full bg-brand/20 px-2.5 py-0.5 text-mint">
                        {t.plan}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <select
                        value={t.plan}
                        onChange={(e) => handlePlanOverride(t.id, e.target.value)}
                        className="rounded-xl border border-line bg-ink px-3 py-1 font-mono text-xs text-paper focus:border-brand focus:outline-none"
                      >
                        <option value="free">FREE ($0)</option>
                        <option value="pro">PRO ($29)</option>
                        <option value="ultra">ULTRA ($99)</option>
                        <option value="pro_max">PRO MAX ($249)</option>
                      </select>
                    </td>
                    <td className="px-5 py-4">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase font-mono ${
                          t.status === "active" ? "bg-mint/15 text-mint" : "bg-heat/15 text-heat"
                        }`}
                      >
                        {t.status}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-right">
                      <button
                        type="button"
                        onClick={() => handleStatusToggle(t.id, t.status)}
                        className={`rounded-full px-3 py-1 text-xs font-semibold ${
                          t.status === "active"
                            ? "text-heat hover:bg-heat/10"
                            : "text-mint hover:bg-mint/10"
                        }`}
                      >
                        {t.status === "active" ? "Suspend" : "Activate"}
                      </button>
                      <a
                        href={getRenewalWhatsAppUrl(t)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="ml-2 inline-block rounded-full bg-mint/15 px-3 py-1 text-xs font-semibold text-mint hover:bg-mint/25 transition"
                        title="Send 1-Click WhatsApp Renewal Message"
                      >
                        WhatsApp Renewal
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Tab 3: Global Projects ── */}
      {tab === "Global Projects" && (
        <div className="mt-8">
          <div className="overflow-x-auto rounded-2xl border border-line bg-panel">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-line bg-ink/70 font-mono uppercase text-mute">
                <tr>
                  <th className="px-5 py-3">Project Name</th>
                  <th className="px-5 py-3">Tenant / Workspace</th>
                  <th className="px-5 py-3">Repository URL</th>
                  <th className="px-5 py-3">Branch</th>
                  <th className="px-5 py-3">AST Chunks</th>
                  <th className="px-5 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/60">
                {projects.map((p) => (
                  <tr key={p.id} className="hover:bg-panel-2 font-mono">
                    <td className="px-5 py-4 font-bold text-paper font-sans">{p.name}</td>
                    <td className="px-5 py-4 text-mute font-sans">{p.tenant_name}</td>
                    <td className="px-5 py-4 text-mint truncate max-w-xs">{p.repo_url}</td>
                    <td className="px-5 py-4 text-paper">{p.branch}</td>
                    <td className="px-5 py-4 text-mint">{p.files_indexed} files</td>
                    <td className="px-5 py-4 font-sans">
                      <span className="rounded-full bg-mint/15 px-2 py-0.5 text-[10px] text-mint">
                        {p.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Tab 4: Financials & Invoices ── */}
      {tab === "Financials & Invoices" && (
        <div className="mt-8">
          <div className="overflow-x-auto rounded-2xl border border-line bg-panel">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-line bg-ink/70 font-mono uppercase text-mute">
                <tr>
                  <th className="px-5 py-3">Invoice ID</th>
                  <th className="px-5 py-3">Customer / Workspace</th>
                  <th className="px-5 py-3">Plan</th>
                  <th className="px-5 py-3">Amount</th>
                  <th className="px-5 py-3">Method</th>
                  <th className="px-5 py-3">Date</th>
                  <th className="px-5 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/60 font-mono">
                {invoices.map((inv) => (
                  <tr key={inv.id} className="hover:bg-panel-2">
                    <td className="px-5 py-3.5 font-bold text-paper">{inv.id}</td>
                    <td className="px-5 py-3.5 text-paper font-sans">{inv.tenant_name}</td>
                    <td className="px-5 py-3.5 uppercase font-bold text-mint">{inv.plan}</td>
                    <td className="px-5 py-3.5 font-bold text-paper">${inv.amount} USD</td>
                    <td className="px-5 py-3.5 text-mute">{inv.payment_method}</td>
                    <td className="px-5 py-3.5 text-mute">{new Date(inv.date).toLocaleString()}</td>
                    <td className="px-5 py-3.5">
                      <span className="rounded-full bg-mint/15 px-2 py-0.5 text-[10px] text-mint">
                        {inv.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Tab 5: Incidents ── */}
      {tab === "Incidents" && (
        <div className="mt-8 grid gap-6 lg:grid-cols-[340px_1fr]">
          <div className="card p-4 space-y-2 max-h-[600px] overflow-y-auto">
            <p className="font-mono text-xs font-bold text-mute uppercase px-2 mb-3">All Incidents</p>
            {dossier?.incidents?.map((inc) => (
              <button
                key={inc.id}
                type="button"
                onClick={() => setSelectedIncidentId(inc.id)}
                className={`w-full rounded-xl p-3 text-left transition ${
                  selectedIncidentId === inc.id
                    ? "bg-brand/20 border border-brand text-paper"
                    : "border border-line/60 bg-ink/60 hover:bg-panel-2 text-mute"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold text-paper">{inc.id}</span>
                  <span className="rounded-full bg-mint/15 px-2 py-0.5 font-mono text-[10px] text-mint uppercase">
                    {inc.status}
                  </span>
                </div>
                <p className="mt-1 font-mono text-[11px] truncate">{inc.target}</p>
              </button>
            ))}
          </div>

          <div className="card p-6">
            {selectedIncident ? (
              <div>
                <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line pb-4">
                  <div>
                    <h3 className="text-xl font-bold font-mono">{selectedIncident.id}</h3>
                    <p className="text-xs text-mute font-mono">Tenant: {selectedIncident.tenant_id}</p>
                  </div>
                  {selectedIncident.status === "awaiting_approval" && (
                    <button
                      type="button"
                      onClick={() => handleApprove(selectedIncident.id)}
                      className="rounded-full bg-mint px-5 py-2 text-xs font-bold text-ink shadow hover:opacity-90"
                    >
                      ✓ Approve AWS Deploy Session (900s)
                    </button>
                  )}
                </div>

                <div className="mt-6">
                  <h4 className="text-xs font-bold text-mute uppercase font-mono mb-2">Code Diff</h4>
                  <MonacoDiffViewer
                    original={selectedIncident.report?.coder?.original || ""}
                    modified={selectedIncident.report?.coder?.patched || ""}
                  />
                </div>
              </div>
            ) : (
              <div className="text-center text-mute text-sm py-12">Select an incident to view.</div>
            )}
          </div>
        </div>
      )}

      {/* ── Tab 6: Security & Audit ── */}
      {tab === "Security & Audit" && (
        <div className="mt-8">
          <div className="overflow-x-auto rounded-2xl border border-line bg-panel">
            <table className="w-full text-left text-xs font-mono">
              <thead className="border-b border-line bg-ink/70 uppercase text-mute">
                <tr>
                  <th className="px-5 py-3">Timestamp</th>
                  <th className="px-5 py-3">Action</th>
                  <th className="px-5 py-3">Detail</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/60">
                {audit.map((aud, idx) => (
                  <tr key={idx} className="hover:bg-panel-2">
                    <td className="px-5 py-3 text-mute">{new Date(aud.at).toLocaleString()}</td>
                    <td className="px-5 py-3 font-bold uppercase text-mint">{aud.action}</td>
                    <td className="px-5 py-3 text-paper">{aud.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </main>
  );
}

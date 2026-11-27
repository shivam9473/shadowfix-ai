import { useEffect, useState } from "react";
import {
  adminFetch,
  fetchSuperAdminAudit,
  fetchSuperAdminInvoices,
  fetchSuperAdminMetrics,
  fetchSuperAdminProjects,
  fetchSuperAdminTenants,
  fetchSuperAdminTenantAiConfig,
  updateSuperAdminTenantAiConfig,
  overrideTenantPlan,
  runDemo,
  setTenantStatus,
} from "../api";
import { ADMIN_KEY_STORAGE, useAuth } from "../auth";
import MonacoDiffViewer from "../components/MonacoDiffViewer";

function getRenewalWhatsAppUrl(tenant) {
  const name = tenant.owner_name || tenant.name || "Customer";
  const plan = (tenant.plan || "PRO").toUpperCase();
  const phone = (tenant.owner_phone || tenant.phone || "").replace(/[^0-9]/g, "");
  const text = `Hi ${name}! Hope you are finding ShadowFix AI helpful for your repositories. Your ShadowFix ${plan} Plan subscription is due for monthly renewal. You can renew seamlessly via this link: https://razorpay.me/@shivamkumar98. Let me know once done so your high-speed AI pipeline stays active. Thank you!`;
  if (phone) {
    return `https://api.whatsapp.com/send?phone=${phone}&text=${encodeURIComponent(text)}`;
  }
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
  const [aiModalTenant, setAiModalTenant] = useState(null);
  const [aiForm, setAiForm] = useState({
    provider: "auto",
    active_model: "gemini-2.5-pro",
    api_key: "",
    monthly_token_quota: 500000,
    reset_usage: false,
    aws_access_key_id: "",
    aws_secret_access_key: "",
    aws_region: "us-east-1",
  });
  const [aiLoading, setAiLoading] = useState(false);
  const [aiSaving, setAiSaving] = useState(false);
  const [aiStats, setAiStats] = useState(null);

  async function handleOpenAiModal(t) {
    setAiModalTenant(t);
    setAiLoading(true);
    setAiStats(null);
    try {
      const cfg = await fetchSuperAdminTenantAiConfig(adminKey, t.id);
      setAiStats(cfg);
      setAiForm({
        provider: cfg.provider || "auto",
        active_model: cfg.active_model || "gemini-2.5-pro",
        api_key: cfg.api_key || "",
        monthly_token_quota: cfg.monthly_token_quota || 500000,
        reset_usage: false,
        aws_access_key_id: cfg.aws_access_key_id || "",
        aws_secret_access_key: "",
        aws_region: cfg.aws_region || "us-east-1",
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setAiLoading(false);
    }
  }

  async function handleSaveAiModal(e) {
    e.preventDefault();
    if (!aiModalTenant) return;
    setAiSaving(true);
    setError("");
    try {
      await updateSuperAdminTenantAiConfig(adminKey, aiModalTenant.id, aiForm);
      setMessage(`✓ AI configuration saved for ${aiModalTenant.name}`);
      setAiModalTenant(null);
      await loadAll();
      setTimeout(() => setMessage(""), 4000);
    } catch (err) {
      setError(err.message);
    } finally {
      setAiSaving(false);
    }
  }

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

      async function handleSendSms(tenant) {
    let targetPhone = tenant.owner_phone || tenant.phone || "";
    if (!targetPhone) {
      targetPhone = window.prompt(`Enter phone / WhatsApp number for ${tenant.name || "Customer"}:`, "+91");
      if (!targetPhone || targetPhone.trim() === "+91" || !targetPhone.trim()) {
        return;
      }
    }

    try {
      setBusy(true);
      setMessage("");
      setError("");
      const res = await adminFetch(`/api/superadmin/tenants/${tenant.id}/send-sms`, adminKey, {
        method: "POST",
        body: JSON.stringify({ phone: targetPhone.trim() }),
      });
      if (res.status === "sent") {
        setMessage(`✓ SMS sent to ${res.to}! (${res.gateway || "Carrier"})`);
        setError("");
        loadAll(adminKey);
      } else {
        setError(res.detail || res.message || "Failed to dispatch SMS.");
      }
      setTimeout(() => { setMessage(""); setError(""); }, 8000);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleSendEmail(tenantId) {
    try {
      setBusy(true);
      setMessage("");
      setError("");
      const res = await adminFetch(`/api/superadmin/tenants/${tenantId}/send-email`, adminKey, {
        method: "POST",
        body: JSON.stringify({}),
      });
      if (res.status === "sent") {
        setMessage(`✓ Email sent via Resend to ${res.to}!`);
        setError("");
      } else {
        setError(res.detail || res.message || "Email failed to send");
      }
      setTimeout(() => { setMessage(""); setError(""); }, 8000);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
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
                  <th className="px-5 py-3">AI Engine & Tokens</th>
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
                      {t.owner_phone && (
                        <p className="font-mono text-[11px] text-mint">📱 {t.owner_phone}</p>
                      )}
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
                      <div className="flex flex-col gap-1 min-w-[130px]">
                        <div className="flex items-center gap-1.5 font-mono text-[11px]">
                          <span className="font-bold text-mint">{t.ai_summary?.active_model || "gemini-2.5-pro"}</span>
                          <span className="text-[9px] uppercase px-1 rounded bg-brand/15 text-paper">
                            {t.ai_summary?.provider || "auto"}
                          </span>
                        </div>
                        <div className="w-full bg-ink rounded-full h-1.5 overflow-hidden border border-line">
                          <div
                            className={`h-full rounded-full transition-all ${
                              (t.ai_summary?.percent_used || 0) > 85 ? "bg-heat" : "bg-mint"
                            }`}
                            style={{ width: `${Math.min(100, t.ai_summary?.percent_used || 0)}%` }}
                          />
                        </div>
                        <div className="flex justify-between items-center text-[10px] font-mono text-mute">
                          <span>{((t.ai_summary?.tokens_used_this_month || 0) / 1000).toFixed(1)}k / {((t.ai_summary?.monthly_token_quota || 500000) / 1000).toFixed(0)}k</span>
                          <span className={(t.ai_summary?.percent_used || 0) > 85 ? "text-heat font-bold" : "text-paper"}>
                            {t.ai_summary?.percent_used || 0}%
                          </span>
                        </div>
                      </div>
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
                        WhatsApp
                      </a>
                      <button
                        type="button"
                        onClick={() => handleSendEmail(t.id)}
                        className="ml-1.5 rounded-full bg-brand/15 px-3 py-1 text-xs font-semibold text-paper hover:bg-brand/30 transition"
                        title="Send Official Renewal Email via Resend"
                      >
                        Email
                      </button>
                      <button
                        type="button"
                        onClick={() => handleSendSms(t)}
                        className="ml-1.5 rounded-full bg-heat/15 px-3 py-1 text-xs font-semibold text-heat hover:bg-heat/30 transition"
                        title="Send Direct Phone Number SMS"
                      >
                        SMS
                      </button>
                      <button
                        type="button"
                        onClick={() => handleOpenAiModal(t)}
                        className="ml-1.5 rounded-full bg-brand/20 px-3 py-1 text-xs font-semibold text-mint hover:bg-brand/35 transition"
                        title="Configure AI Engine, Provider Keys & Token Quotas"
                      >
                        AI Config
                      </button>
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

      {/* ── Super Admin AI Engine & Token Provisioning Modal ── */}
      {aiModalTenant && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="relative w-full max-w-xl rounded-2xl border border-line bg-panel p-6 shadow-2xl overflow-y-auto max-h-[90vh]">
            <div className="flex items-start justify-between border-b border-line pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-lg font-bold text-paper font-sans">
                    AI Engine & Token Provisioning
                  </h3>
                  <span className="rounded-full bg-brand/20 px-2.5 py-0.5 text-xs font-mono font-bold text-mint uppercase">
                    {aiModalTenant.plan} Plan
                  </span>
                </div>
                <p className="mt-1 text-xs text-mute font-mono">
                  Tenant: <span className="text-paper">{aiModalTenant.name}</span> ({aiModalTenant.id})
                </p>
              </div>
              <button
                type="button"
                onClick={() => setAiModalTenant(null)}
                className="rounded-full p-1.5 text-mute hover:bg-ink hover:text-paper transition"
              >
                ✕
              </button>
            </div>

            {aiLoading ? (
              <div className="py-12 text-center font-mono text-sm text-mute">
                Loading tenant AI credentials & quota metrics...
              </div>
            ) : (
              <form onSubmit={handleSaveAiModal} className="mt-5 space-y-4">
                {/* ── Token Usage Progress Bar ── */}
                {aiStats && (
                  <div className="rounded-xl border border-line/60 bg-ink/70 p-4 font-mono">
                    <div className="flex items-center justify-between text-xs mb-1.5">
                      <span className="text-mute uppercase text-[10px] tracking-wider">Monthly Token Consumption</span>
                      <span className={`font-bold ${aiStats.percent_used > 85 ? "text-heat" : "text-mint"}`}>
                        {aiStats.percent_used}% Used
                      </span>
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-panel border border-line/50">
                      <div
                        className={`h-full transition-all duration-300 ${
                          aiStats.percent_used > 85 ? "bg-heat" : "bg-mint"
                        }`}
                        style={{ width: `${Math.min(100, aiStats.percent_used)}%` }}
                      />
                    </div>
                    <div className="mt-2 grid grid-cols-3 gap-2 text-center text-[10px]">
                      <div className="rounded bg-panel/70 p-1.5">
                        <p className="text-mute">Used This Month</p>
                        <p className="font-bold text-paper mt-0.5">{(aiStats.tokens_used_this_month).toLocaleString()}</p>
                      </div>
                      <div className="rounded bg-panel/70 p-1.5">
                        <p className="text-mute">Remaining</p>
                        <p className="font-bold text-mint mt-0.5">{(aiStats.tokens_remaining).toLocaleString()}</p>
                      </div>
                      <div className="rounded bg-panel/70 p-1.5">
                        <p className="text-mute">Quota Limit</p>
                        <p className="font-bold text-paper mt-0.5">{(aiStats.monthly_token_quota).toLocaleString()}</p>
                      </div>
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-mono text-mute mb-1">
                      Assigned AI Provider
                    </label>
                    <select
                      value={aiForm.provider}
                      onChange={(e) => setAiForm({ ...aiForm, provider: e.target.value })}
                      className="w-full rounded-xl border border-line bg-ink px-3 py-2 text-xs text-paper focus:border-brand focus:outline-none font-mono"
                    >
                      <option value="auto">Auto / Multi-Model Fallback</option>
                      <option value="openai">OpenAI (GPT-4o / GPT-4o-mini)</option>
                      <option value="anthropic">Anthropic (Claude 3.5 Sonnet / Haiku)</option>
                      <option value="gemini">Google Gemini (Gemini 2.5 Pro / Flash)</option>
                      <option value="aws_bedrock">AWS Bedrock Cloud (Enterprise)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-mono text-mute mb-1">
                      Active Model Architecture
                    </label>
                    <select
                      value={aiForm.active_model}
                      onChange={(e) => setAiForm({ ...aiForm, active_model: e.target.value })}
                      className="w-full rounded-xl border border-line bg-ink px-3 py-2 text-xs text-paper focus:border-brand focus:outline-none font-mono"
                    >
                      <optgroup label="Ultra & Enterprise Tier (High-Reasoning)">
                        <option value="claude-3-5-sonnet">Claude 3.5 Sonnet (Anthropic)</option>
                        <option value="gpt-4o">GPT-4o (OpenAI)</option>
                        <option value="gemini-2.5-pro">Gemini 2.5 Pro (Google)</option>
                        <option value="aws-bedrock-claude-3-5">Claude 3.5 on AWS Bedrock</option>
                      </optgroup>
                      <optgroup label="Pro & Fast Tier">
                        <option value="gpt-4o-mini">GPT-4o Mini (OpenAI)</option>
                        <option value="claude-3-5-haiku">Claude 3.5 Haiku (Anthropic)</option>
                        <option value="gemini-flash">Gemini 3.8 Flash (Google)</option>
                      </optgroup>
                    </select>
                  </div>
                </div>

                {/* ── API Key Input (Admin provisioned or BYOK) ── */}
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="text-xs font-mono text-mute">
                      Dedicated Provider API Key
                    </label>
                    {aiStats?.has_custom_key && (
                      <span className="text-[10px] font-mono text-mint">
                        ✓ Key active (Source: {aiStats.api_key_source})
                      </span>
                    )}
                  </div>
                  <input
                    type="password"
                    value={aiForm.api_key}
                    onChange={(e) => setAiForm({ ...aiForm, api_key: e.target.value })}
                    placeholder={aiStats?.has_custom_key ? "Leave blank to keep current key, or type new key" : "e.g. sk-ant-api03-... or sk-proj-..."}
                    className="w-full rounded-xl border border-line bg-ink px-3 py-2 text-xs text-paper focus:border-brand focus:outline-none font-mono"
                  />
                  <p className="mt-1 text-[10px] text-mute font-mono">
                    SuperAdmin can provision dedicated Anthropic, OpenAI or Gemini keys per tenant, or let user BYOK.
                  </p>
                </div>

                {/* ── AWS Bedrock Cloud Credentials (If Selected) ── */}
                {aiForm.provider === "aws_bedrock" && (
                  <div className="rounded-xl border border-line/60 bg-ink/40 p-3 space-y-3 font-mono">
                    <p className="text-[11px] font-bold text-mint">AWS Bedrock Cloud Credentials</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                      <div>
                        <label className="text-[10px] text-mute block mb-0.5">AWS Access Key ID</label>
                        <input
                          type="text"
                          value={aiForm.aws_access_key_id}
                          onChange={(e) => setAiForm({ ...aiForm, aws_access_key_id: e.target.value })}
                          placeholder="AKIA..."
                          className="w-full rounded-lg border border-line bg-ink px-2.5 py-1.5 text-xs text-paper focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-mute block mb-0.5">AWS Region</label>
                        <input
                          type="text"
                          value={aiForm.aws_region}
                          onChange={(e) => setAiForm({ ...aiForm, aws_region: e.target.value })}
                          placeholder="us-east-1"
                          className="w-full rounded-lg border border-line bg-ink px-2.5 py-1.5 text-xs text-paper focus:outline-none"
                        />
                      </div>
                    </div>
                    <div>
                      <label className="text-[10px] text-mute block mb-0.5">AWS Secret Access Key</label>
                      <input
                        type="password"
                        value={aiForm.aws_secret_access_key}
                        onChange={(e) => setAiForm({ ...aiForm, aws_secret_access_key: e.target.value })}
                        placeholder="Secret key (leave blank to keep)"
                        className="w-full rounded-lg border border-line bg-ink px-2.5 py-1.5 text-xs text-paper focus:outline-none"
                      />
                    </div>
                  </div>
                )}

                {/* ── Monthly Quota & Reset ── */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 items-center">
                  <div>
                    <label className="block text-xs font-mono text-mute mb-1">
                      Monthly Token Quota Limit
                    </label>
                    <input
                      type="number"
                      step="50000"
                      min="50000"
                      value={aiForm.monthly_token_quota}
                      onChange={(e) => setAiForm({ ...aiForm, monthly_token_quota: parseInt(e.target.value) || 0 })}
                      className="w-full rounded-xl border border-line bg-ink px-3 py-2 text-xs text-paper focus:border-brand focus:outline-none font-mono"
                    />
                  </div>

                  <div className="pt-4">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={aiForm.reset_usage}
                        onChange={(e) => setAiForm({ ...aiForm, reset_usage: e.target.checked })}
                        className="rounded border-line bg-ink text-brand focus:ring-0"
                      />
                      <span className="text-xs font-mono text-paper">
                        Reset Token Usage Count to 0
                      </span>
                    </label>
                  </div>
                </div>

                <div className="flex justify-end gap-3 border-t border-line pt-4">
                  <button
                    type="button"
                    onClick={() => setAiModalTenant(null)}
                    className="rounded-xl border border-line px-4 py-2 text-xs font-semibold text-mute hover:bg-ink hover:text-paper transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={aiSaving}
                    className="rounded-xl bg-brand px-5 py-2 text-xs font-semibold text-paper hover:bg-brand/80 transition disabled:opacity-50"
                  >
                    {aiSaving ? "Saving..." : "Save AI Configuration"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </main>
  );
}

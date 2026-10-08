import { useEffect, useState } from "react";
import { adminFetch, runDemo } from "../api";
import MonacoDiffViewer from "../components/MonacoDiffViewer";

const TABS = ["Incidents", "Knowledge", "Memory", "Security", "Visitors", "Audit"];

export default function SuperAdminConsole() {
  const [adminKey, setAdminKey] = useState("change-me");
  const [dossier, setDossier] = useState(null);
  const [tab, setTab] = useState("Incidents");
  const [selected, setSelected] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load(key = adminKey) {
    try {
      const body = await adminFetch("/api/admin/dossier", key);
      setDossier(body);
      setError("");
      setSelected((current) => current || body.incidents[0]?.id || "");
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load(adminKey);
    const timer = setInterval(() => load(adminKey), 4000);
    return () => clearInterval(timer);
  }, [adminKey]);

  async function toggleKill() {
    setError("");
    try {
      const next = !dossier?.control?.kill_switch;
      const body = await adminFetch("/api/admin/kill-switch", adminKey, {
        method: "POST",
        body: JSON.stringify({ enabled: next }),
      });
      setMessage(body.kill_switch ? "Kill switch is on. New runs stop." : "Kill switch is off.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function approve(id) {
    setError("");
    try {
      const body = await adminFetch(`/api/admin/approve/${id}`, adminKey, { method: "POST" });
      setMessage(`${body.mode} · ${body.expires_in_seconds}s · ${body.message}`);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function reproduce() {
    setBusy(true);
    setError("");
    try {
      const created = await runDemo();
      setMessage(`Incident ${created.id} is running.`);
      setTab("Incidents");
      setSelected(created.id);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const incident = dossier?.incidents?.find((item) => item.id === selected) || dossier?.incidents?.[0];

  return (
    <main className="mx-auto max-w-7xl px-6 py-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-xs tracking-[0.16em] text-lime">SUPER ADMIN</p>
          <h1 className="mt-2 text-3xl">Full desk</h1>
          <p className="mt-2 max-w-2xl text-sm text-mute">
            Every incident, agent report, indexed file, memory note, visitor, and approval lives here.
            Keys stay on the server. This page only shows whether each integration is configured.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button type="button" onClick={reproduce} disabled={busy} className="rounded-full bg-lime px-4 py-2 text-sm font-semibold text-ink disabled:opacity-60">
            {busy ? "Starting" : "Run Shopkart incident"}
          </button>
          <button type="button" onClick={toggleKill} className="rounded-full border border-line px-4 py-2 text-sm">
            {dossier?.control?.kill_switch ? "Turn kill switch off" : "Turn kill switch on"}
          </button>
        </div>
      </div>

      <label className="mt-6 block max-w-md text-sm text-mute">
        Admin key
        <input
          value={adminKey}
          onChange={(event) => setAdminKey(event.target.value)}
          className="mt-2 w-full rounded border border-line bg-ink px-3 py-2 font-mono text-sm text-paper"
        />
      </label>
      {error && <p className="mt-4 text-sm text-heat">{error}</p>}
      {message && <p className="mt-4 text-sm text-lime">{message}</p>}

      {dossier && (
        <>
          <section className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Visitors" value={dossier.control.visitors} />
            <Stat label="Kill switch" value={dossier.control.kill_switch ? "on" : "off"} />
            <Stat label="Waiting" value={dossier.control.pending.length} />
            <Stat label="Incidents" value={dossier.incidents.length} />
          </section>

          <section className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Flag label="Gemini" on={dossier.system.gemini_configured} detail={`${dossier.system.flash_model} / ${dossier.system.pro_model}`} />
            <Flag label="E2B sandbox" on={dossier.system.e2b_configured} detail="cloud execution" />
            <Flag label="Deploy role" on={dossier.system.deploy_role_configured} detail="15-minute STS" />
            <Flag label="GitHub PR" on={dossier.system.github_publish_armed} detail="preview until armed" />
            <Flag label="Qdrant" on={dossier.system.qdrant_mode !== ""} detail={`${dossier.system.qdrant_mode} · ${dossier.system.qdrant_collection}`} />
            <Flag label="Resend" on={dossier.system.resend_configured} detail="signed webhooks" />
            <Flag label="Temporal" on={dossier.system.temporal_configured} detail="durable wait" />
            <Flag label="Mem0" on={dossier.system.mem0_configured} detail="file memory if unset" />
          </section>

          <div className="mt-6 flex flex-wrap gap-2">
            {TABS.map((name) => (
              <button
                key={name}
                type="button"
                onClick={() => setTab(name)}
                className={`rounded-full px-4 py-1.5 text-sm ${tab === name ? "bg-lime text-ink" : "border border-line text-mute"}`}
              >
                {name}
              </button>
            ))}
          </div>

          <section className="mt-6">
            {tab === "Incidents" && (
              <Incidents dossier={dossier} incident={incident} onSelect={setSelected} onApprove={approve} />
            )}
            {tab === "Knowledge" && <Knowledge rows={dossier.knowledge} />}
            {tab === "Memory" && <Memory rows={dossier.memory} />}
            {tab === "Security" && <Security dossier={dossier} />}
            {tab === "Visitors" && <Visitors dossier={dossier} />}
            {tab === "Audit" && <Audit rows={dossier.audit} />}
          </section>
        </>
      )}
    </main>
  );
}

function Incidents({ dossier, incident, onSelect, onApprove }) {
  return (
    <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
      <div className="space-y-2">
        {dossier.incidents.length === 0 && <p className="text-sm text-mute">No incidents yet. Run the Shopkart crash.</p>}
        {dossier.incidents.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onSelect(item.id)}
            className={`block w-full rounded-lg border px-3 py-3 text-left ${incident?.id === item.id ? "border-lime" : "border-line"}`}
          >
            <div className="font-mono text-xs">{item.id}</div>
            <div className="mt-1 text-sm">{item.status}</div>
            <div className="text-xs text-mute">{item.tenant_id}</div>
          </button>
        ))}
      </div>
      {incident && <IncidentDetail incident={incident} onApprove={onApprove} />}
    </div>
  );
}

function IncidentDetail({ incident, onApprove }) {
  const report = incident.report || {};
  const breaker = report.breaker || {};
  const sre = report.sre || {};
  const detective = report.detective || {};
  const coder = report.coder || {};
  const review = report.review || {};
  const deploy = report.deploy || null;

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-line bg-panel p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-mono text-sm">{incident.id}</h2>
            <p className="mt-1 text-sm text-mute">
              {incident.tenant_id} · {incident.target} · {incident.created_at}
            </p>
          </div>
          {incident.status === "awaiting_approval" && (
            <button type="button" onClick={() => onApprove(incident.id)} className="rounded-full bg-lime px-4 py-2 text-sm font-semibold text-ink">
              Approve 15-minute deploy
            </button>
          )}
        </div>
        {incident.error && <p className="mt-3 text-sm text-heat">{incident.error}</p>}
        <ol className="mt-4 space-y-1">
          {(incident.events || []).map((event, index) => (
            <li key={`${event.stage}-${index}`} className="font-mono text-xs text-mute">
              <span className="text-paper">{event.stage}</span> {event.status} {event.summary || ""}
            </li>
          ))}
        </ol>
      </div>

      <Panel title="Breaker">
        <Facts
          rows={[
            ["Error", breaker.error],
            ["Endpoint", breaker.endpoint],
            ["Coupon", breaker.coupon],
            ["Playwright", breaker.playwright],
            ["HTTP probe", breaker.http_probe],
            ["Toxiproxy", breaker.chaos?.toxiproxy],
            ["Locust", breaker.chaos?.locust?.reason],
          ]}
        />
        <p className="mt-3 text-sm">{breaker.dom}</p>
        <Pre text={breaker.stack} />
      </Panel>

      <Panel title="SRE">
        <p className="text-sm">{sre.summary || "Waiting for the SRE pass."}</p>
        <Facts
          rows={[
            ["AWS write", sre.aws_write],
            ["STS", sre.sts],
            ["S3", sre.s3],
            ["CloudFront", sre.cloudfront],
            ["Grafana", sre.grafana],
            ["Workflow present", String(sre.github_actions?.present ?? "")],
          ]}
        />
      </Panel>

      <Panel title="Detective">
        <p className="font-mono text-xs text-lime">{detective.culprit_path || "No culprit yet."}</p>
        <ul className="mt-3 space-y-2">
          {(detective.culprits || []).map((hit) => (
            <li key={`${hit.path}-${hit.symbol}`} className="flex justify-between gap-4 font-mono text-xs">
              <span>
                {hit.symbol} · {hit.path}
              </span>
              <span className="text-mute">{Number(hit.score).toFixed(3)}</span>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel title="Coder">
        <Facts
          rows={[
            ["Model", coder.model],
            ["File", coder.path],
            ["Ansible", coder.ansible ? "present" : "none"],
          ]}
        />
        <div className="mt-4">
          <MonacoDiffViewer original={coder.original || ""} patched={coder.patched || ""} />
        </div>
      </Panel>

      <Panel title="Reviewer">
        <Facts
          rows={[
            ["Score", review.eval_score != null ? `${review.eval_score} / ${review.threshold}` : ""],
            ["Passed", String(review.passed ?? "")],
            ["Secret scan", review.secret_scan],
            ["Judge", review.judge],
            ["Sandbox", review.sandbox?.status],
            ["Sandbox note", review.sandbox?.reason],
            ["PR", review.pr?.status],
            ["PR title", review.pr?.title],
          ]}
        />
        {review.pr?.body && <Pre text={review.pr.body} />}
      </Panel>

      <Panel title="Deploy">
        {deploy ? (
          <Facts
            rows={[
              ["Mode", deploy.mode],
              ["Expires", `${deploy.expires_in_seconds}s`],
              ["Key prefix", deploy.access_key_id_prefix],
              ["Message", deploy.message],
            ]}
          />
        ) : (
          <p className="text-sm text-mute">No credentials have been minted. Approval is the only mint path.</p>
        )}
      </Panel>
    </div>
  );
}

function Knowledge({ rows }) {
  return (
    <div className="space-y-4">
      {rows.map((tenant) => (
        <Panel key={tenant.tenant_id} title={`${tenant.tenant_id} · ${tenant.count} chunks`}>
          <ul className="space-y-2">
            {tenant.chunks.map((chunk) => (
              <li key={`${chunk.path}-${chunk.symbol}-${chunk.start_line}`} className="grid grid-cols-[1fr_auto_auto] gap-3 font-mono text-xs">
                <span>{chunk.path}</span>
                <span>{chunk.symbol}</span>
                <span className="text-mute">
                  {chunk.language} · {chunk.parser} · L{chunk.start_line}
                </span>
              </li>
            ))}
          </ul>
        </Panel>
      ))}
    </div>
  );
}

function Memory({ rows }) {
  return (
    <div className="space-y-4">
      {rows.map((tenant) => (
        <Panel key={tenant.tenant_id} title={tenant.tenant_id}>
          <h3 className="font-mono text-xs text-mute">EPISODIC</h3>
          <Notes rows={tenant.episodic} />
          <h3 className="mt-4 font-mono text-xs text-mute">PROCEDURAL</h3>
          <Notes rows={tenant.procedural} />
        </Panel>
      ))}
    </div>
  );
}

function Notes({ rows }) {
  if (!rows.length) return <p className="mt-2 text-sm text-mute">Empty.</p>;
  return (
    <ul className="mt-2 space-y-2">
      {rows.map((row, index) => (
        <li key={`${row.at}-${index}`} className="text-sm">
          <span className="font-mono text-xs text-mute">{row.at}</span>
          <p className="mt-1 whitespace-pre-wrap">{row.text}</p>
        </li>
      ))}
    </ul>
  );
}

function Security({ dossier }) {
  const security = dossier.security;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title="Rules">
        <p className="text-sm">{security.tenant_filter}</p>
        <p className="mt-3 text-sm">{security.sandbox}</p>
        <p className="mt-3 text-sm">{security.aws}</p>
        <p className="mt-3 font-mono text-xs text-lime">STS session {security.session_seconds}s</p>
      </Panel>
      <Panel title="Blocked Ansible modules">
        <ul className="space-y-1 font-mono text-xs">
          {security.blocked_modules.map((name) => (
            <li key={name}>{name}</li>
          ))}
        </ul>
      </Panel>
      <Panel title="Registered targets">
        {Object.entries(security.registered_targets).map(([tenant, targets]) => (
          <div key={tenant} className="mb-3">
            <div className="font-mono text-xs text-lime">{tenant}</div>
            {targets.map((target) => (
              <div key={target} className="text-sm">
                {target}
              </div>
            ))}
          </div>
        ))}
      </Panel>
      <Panel title="Quotas">
        {dossier.control.quotas.length === 0 && <p className="text-sm text-mute">No usage yet.</p>}
        {dossier.control.quotas.map((row) => (
          <div key={row.tenant_id} className="flex justify-between font-mono text-xs">
            <span>{row.tenant_id}</span>
            <span>
              {row.used} / {row.limit} today
            </span>
          </div>
        ))}
        <p className="mt-3 text-sm text-mute">Daily cap is {dossier.system.quota_per_day} runs per tenant. Eval threshold is {dossier.system.eval_threshold}.</p>
      </Panel>
    </div>
  );
}

function Visitors({ dossier }) {
  return (
    <Panel title={`${dossier.control.visitors} distinct visitors`}>
      {dossier.visitors.length === 0 && <p className="text-sm text-mute">No API traffic yet.</p>}
      <ul className="space-y-2">
        {dossier.visitors.map((row, index) => (
          <li key={`${row.at}-${index}`} className="flex justify-between gap-4 font-mono text-xs">
            <span>{row.path}</span>
            <span className="text-mute">
              {row.visitor} · {row.at}
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Audit({ rows }) {
  return (
    <Panel title="Admin actions">
      {rows.length === 0 && <p className="text-sm text-mute">No approvals or kill-switch changes yet.</p>}
      <ul className="space-y-2">
        {rows.map((row, index) => (
          <li key={`${row.at}-${index}`} className="font-mono text-xs">
            <span className="text-lime">{row.action}</span> {row.detail}
            <span className="ml-3 text-mute">{row.at}</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Panel({ title, children }) {
  return (
    <section className="rounded-lg border border-line bg-panel p-4">
      <h2 className="font-mono text-xs tracking-[0.12em] text-mute">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function Facts({ rows }) {
  return (
    <dl className="mt-3 space-y-2">
      {rows.filter(([, value]) => value).map(([label, value]) => (
        <div key={label} className="grid grid-cols-[140px_1fr] gap-3 text-sm">
          <dt className="text-mute">{label}</dt>
          <dd className="break-words">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function Pre({ text }) {
  if (!text) return null;
  return <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap font-mono text-xs text-mute">{text}</pre>;
}

function Stat({ label, value }) {
  return (
    <div className="rounded-lg border border-line bg-panel p-4">
      <div className="font-mono text-xs text-mute">{label}</div>
      <div className="mt-2 text-2xl">{value}</div>
    </div>
  );
}

function Flag({ label, on, detail }) {
  return (
    <div className="rounded-lg border border-line bg-panel p-4">
      <div className="font-mono text-xs text-mute">{label}</div>
      <div className={`mt-2 text-sm ${on ? "text-lime" : "text-paper"}`}>{on ? "ready" : "not set"}</div>
      <div className="mt-1 text-xs text-mute">{detail}</div>
    </div>
  );
}

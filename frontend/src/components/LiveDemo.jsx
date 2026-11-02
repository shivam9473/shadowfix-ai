import { useState } from "react";
import { Link } from "react-router-dom";
import { runDemo } from "../api";
import ReactFlowGraph from "./ReactFlowGraph";
import { useIncident } from "../hooks/useIncident";

const STATUS_STYLE = {
  idle: "bg-line text-mute",
  queued: "bg-line text-mute",
  running: "bg-brand/20 text-brand",
  awaiting_approval: "bg-mint/15 text-mint",
  deployed: "bg-mint/15 text-mint",
  failed: "bg-heat/15 text-heat",
  halted: "bg-heat/15 text-heat",
};

export default function LiveDemo() {
  const [id, setId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const { incident, error: loadError } = useIncident(id);

  async function reproduce() {
    setBusy(true);
    setError("");
    try {
      const created = await runDemo();
      setId(created.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const status = incident?.status || "idle";
  const review = incident?.report?.review;
  const detective = incident?.report?.detective;

  return (
    <div className="card overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line px-6 py-4">
        <div className="flex items-center gap-3">
          <span className="flex gap-1.5" aria-hidden="true">
            <i className="h-2.5 w-2.5 rounded-full bg-heat/70" />
            <i className="h-2.5 w-2.5 rounded-full bg-brand/70" />
            <i className="h-2.5 w-2.5 rounded-full bg-mint/70" />
          </span>
          <span className="font-mono text-xs text-mute">shopkart://local</span>
        </div>
        <button
          type="button"
          onClick={reproduce}
          disabled={busy}
          className="rounded-full bg-brand px-5 py-2 text-sm font-bold text-white transition-colors hover:bg-brand-deep disabled:opacity-60"
        >
          {busy ? "Starting…" : "Reproduce the Shopkart crash"}
        </button>
      </div>

      {(error || loadError) && (
        <p role="alert" className="border-b border-line px-6 py-3 text-sm text-heat">
          {error || loadError}. Start the backend on port 8000, then try again.
        </p>
      )}

      <div className="grid gap-6 p-6 lg:grid-cols-[1.5fr_0.8fr]">
        <div>
          <h3 className="mb-3 text-sm font-bold text-mute">Agent graph</h3>
          <ReactFlowGraph events={incident?.events || []} status={status} />
          <ol className="mt-4 max-h-40 space-y-1.5 overflow-auto">
            {(incident?.events || []).length === 0 && (
              <li className="text-sm text-mute">No run yet. Reproduce the crash to watch the five agents work.</li>
            )}
            {(incident?.events || []).map((event, index) => (
              <li key={`${event.stage}-${index}`} className="font-mono text-xs text-mute">
                <span className="text-paper">{event.stage}</span> {event.status} {event.summary || ""}
              </li>
            ))}
          </ol>
        </div>

        <aside className="rounded-2xl border border-line bg-ink/60 p-5">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-mute">Incident</h3>
            <span className={`rounded-full px-3 py-1 text-xs font-bold ${STATUS_STYLE[status] || STATUS_STYLE.idle}`}>
              {status.replace("_", " ")}
            </span>
          </div>
          <dl className="mt-4 space-y-3 text-sm">
            <Row label="Tenant" value={incident?.tenant_id || "shopkart"} />
            <Row label="Culprit" value={detective?.culprit_symbol || "—"} />
            <Row label="Eval score" value={review ? `${review.eval_score} / ${review.threshold}` : "—"} />
            <Row label="Sandbox" value={review?.sandbox?.status || "—"} />
          </dl>
          {id ? (
            <Link
              to={`/incident/${id}`}
              className="mt-6 inline-flex rounded-full border border-line px-4 py-2 text-sm font-semibold transition-colors hover:border-mint hover:text-mint"
            >
              Open the diff
            </Link>
          ) : (
            <p className="mt-6 text-xs leading-relaxed text-mute">
              Nothing deploys from here. An admin approval is the only action that mints credentials.
            </p>
          )}
        </aside>
      </div>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-mute">{label}</dt>
      <dd className="text-right font-mono text-xs">{value}</dd>
    </div>
  );
}

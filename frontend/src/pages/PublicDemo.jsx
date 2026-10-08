import { useState } from "react";
import { Link } from "react-router-dom";
import { runDemo } from "../api";
import ReactFlowGraph from "../components/ReactFlowGraph";
import { useIncident } from "../hooks/useIncident";

export default function PublicDemo() {
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

  const review = incident?.report?.review;
  const detective = incident?.report?.detective;

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <p className="font-mono text-xs tracking-[0.16em] text-lime">QA · SELF-HEAL · SRE</p>
      <h1 className="mt-3 max-w-3xl text-4xl leading-tight">
        Reproduce the crash, name the file, and wait for a 15-minute deploy approval.
      </h1>
      <p className="mt-4 max-w-2xl text-mute">
        This demo runs the Shopkart checkout. Coupon SHADOW is a 100% discount implemented as a
        divisor, so the API raises ZeroDivisionError. Five agents diagnose it. Nothing is deployed
        until an admin approves.
      </p>
      <button
        type="button"
        onClick={reproduce}
        disabled={busy}
        className="mt-6 rounded-full bg-lime px-5 py-2 text-sm font-semibold text-ink disabled:opacity-60"
      >
        {busy ? "Starting" : "Reproduce the Shopkart crash"}
      </button>
      {(error || loadError) && <p className="mt-4 text-sm text-heat">{error || loadError}</p>}

      <section className="mt-10 grid gap-6 lg:grid-cols-[1.4fr_0.8fr]">
        <div>
          <h2 className="mb-3 font-mono text-xs tracking-[0.14em] text-mute">AGENT GRAPH</h2>
          <ReactFlowGraph events={incident?.events || []} status={incident?.status || "queued"} />
        </div>
        <aside className="rounded-lg border border-line bg-panel p-5">
          <h2 className="font-mono text-xs tracking-[0.14em] text-mute">INCIDENT</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <Row label="Status" value={incident?.status || "idle"} />
            <Row label="Tenant" value={incident?.tenant_id || "shopkart"} />
            <Row label="Culprit" value={detective?.culprit_symbol || "—"} />
            <Row label="Eval" value={review ? `${review.eval_score} / ${review.threshold}` : "—"} />
            <Row label="Sandbox" value={review?.sandbox?.status || "—"} />
          </dl>
          {id && (
            <Link to={`/incident/${id}`} className="mt-6 inline-block text-sm text-lime">
              Open the diff
            </Link>
          )}
        </aside>
      </section>

      <ol className="mt-8 space-y-2">
        {(incident?.events || []).map((event, index) => (
          <li key={`${event.stage}-${index}`} className="font-mono text-xs text-mute">
            <span className="text-paper">{event.stage}</span> {event.status} {event.summary || ""}
          </li>
        ))}
      </ol>
    </main>
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

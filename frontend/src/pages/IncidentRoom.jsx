import { Link, useParams } from "react-router-dom";
import MonacoDiffViewer from "../components/MonacoDiffViewer";
import ReactFlowGraph from "../components/ReactFlowGraph";
import { useIncident } from "../hooks/useIncident";

export default function IncidentRoom() {
  const { id } = useParams();
  const { incident, error } = useIncident(id);
  const coder = incident?.report?.coder;
  const review = incident?.report?.review;

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <Link to="/" className="font-mono text-xs text-mute">
        Back to demo
      </Link>
      <h1 className="mt-3 font-mono text-lg">{id}</h1>
      {error && <p className="mt-4 text-sm text-heat">{error}</p>}
      <div className="mt-6">
        <ReactFlowGraph events={incident?.events || []} status={incident?.status || "queued"} />
      </div>
      <div className="mt-6 flex flex-wrap gap-6 text-sm">
        <span>Status {incident?.status || "loading"}</span>
        <span>Score {review ? review.eval_score : "—"}</span>
        <span>PR {review?.pr?.status || "—"}</span>
        <span>Sandbox {review?.sandbox?.reason || review?.sandbox?.status || "—"}</span>
      </div>
      <div className="mt-6">
        <MonacoDiffViewer original={coder?.original || ""} patched={coder?.patched || ""} />
      </div>
      {incident?.status === "awaiting_approval" && (
        <p className="mt-4 text-sm text-mute">
          The patch is waiting in the <Link to="/console" className="text-lime">admin console</Link>.
          Approval is the only path that mints credentials.
        </p>
      )}
    </main>
  );
}

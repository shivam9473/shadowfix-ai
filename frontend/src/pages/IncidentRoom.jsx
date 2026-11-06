import { Link, useParams } from "react-router-dom";
import MonacoDiffViewer from "../components/MonacoDiffViewer";
import ReactFlowGraph from "../components/ReactFlowGraph";
import { useIncident } from "../hooks/useIncident";

export default function IncidentRoom() {
  const { id } = useParams();
  const { incident, error } = useIncident(id);
  const coder = incident?.report?.coder;
  const review = incident?.report?.review;
  const breaker = incident?.report?.breaker;
  const detective = incident?.report?.detective;

  const isCustomProject = !!incident?.project_name || !!incident?.project_id;

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      {/* ── Breadcrumb / Back Link ── */}
      <div className="flex items-center justify-between">
        <Link
          to={isCustomProject ? "/projects" : "/demo"}
          className="flex items-center gap-1.5 font-mono text-xs text-mute transition hover:text-mint"
        >
          <span>←</span> Back to {isCustomProject ? "Repositories" : "Live Demo"}
        </Link>
        <span className="font-mono text-xs text-mute">{id}</span>
      </div>

      {/* ── Header ── */}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-4 border-b border-line pb-6">
        <div>
          <div className="flex items-center gap-2.5">
            <span
              className={`rounded-full px-3 py-0.5 font-mono text-xs font-bold uppercase ${
                isCustomProject ? "bg-brand/20 text-brand" : "bg-mint/20 text-mint"
              }`}
            >
              {isCustomProject ? incident?.project_name || "Custom Codebase" : "Shopkart Demo Target"}
            </span>
            <span className="font-mono text-xs text-mute">
              Target: <strong className="text-paper">{incident?.target}</strong>
            </span>
          </div>
          <h1 className="mt-2 text-2xl font-black tracking-tight font-mono">
            Incident: {id}
          </h1>
          {detective?.culprit_path && (
            <p className="mt-1 font-mono text-xs text-mint">
              📍 Pinpointed Culprit: <strong>{detective.culprit_path}</strong>{" "}
              {detective.culprit_symbol && `(${detective.culprit_symbol})`}
            </p>
          )}
        </div>

        <div className="flex items-center gap-3">
          <span
            className={`rounded-full px-4 py-1.5 text-xs font-extrabold uppercase font-mono ${
              incident?.status === "awaiting_approval"
                ? "bg-mint/20 text-mint border border-mint/40"
                : incident?.status === "deployed"
                ? "bg-brand/20 text-brand"
                : incident?.status === "failed"
                ? "bg-heat/20 text-heat"
                : "bg-ink border border-line text-mute"
            }`}
          >
            {incident?.status || "queued"}
          </span>
        </div>
      </div>

      {error && <p className="mt-4 text-sm text-heat">{error}</p>}

      {/* ── Multi-Agent ReactFlow Pipeline Graph ── */}
      <div className="mt-8">
        <ReactFlowGraph events={incident?.events || []} status={incident?.status || "queued"} />
      </div>

      {/* ── Key Metrics Pills ── */}
      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4 font-mono text-xs">
        <div className="card p-3">
          <span className="text-mute block text-[10px] uppercase">Review Score</span>
          <span className="font-bold text-mint text-sm">{review ? `${review.eval_score} / 100` : "—"}</span>
        </div>
        <div className="card p-3">
          <span className="text-mute block text-[10px] uppercase">PR Status</span>
          <span className="font-bold text-paper text-sm">{review?.pr?.status || "preview"}</span>
        </div>
        <div className="card p-3">
          <span className="text-mute block text-[10px] uppercase">AI Model</span>
          <span className="font-bold text-paper text-sm">{coder?.model || "intelligent"}</span>
        </div>
        <div className="card p-3">
          <span className="text-mute block text-[10px] uppercase">Breaker Kind</span>
          <span className="font-bold text-mint text-sm">{breaker?.kind || "crash"}</span>
        </div>
      </div>

      {/* ── 5-Factor Evaluation Rubric Card ── */}
      {review?.eval_rubric && (
        <div className="mt-8 rounded-2xl border border-line bg-panel-2/60 p-6 shadow-md">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-4">
            <div>
              <span className="font-mono text-xs font-bold uppercase text-mint">Quality & Safety Gate</span>
              <h3 className="text-lg font-bold text-paper">Rigorous 5-Factor Evaluation Rubric</h3>
            </div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs text-mute">Passing Threshold: 85/100</span>
              <span className={`rounded-full px-3 py-1 font-mono text-xs font-black ${
                review.eval_score >= 85 ? "bg-mint/20 text-mint border border-mint/40" : "bg-heat/20 text-heat"
              }`}>
                {review.eval_score} / 100 ({review.passed ? "PASSED" : "FAILED"})
              </span>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-2 sm:grid-cols-5 gap-3 font-mono text-xs">
            <div className="rounded-xl border border-line bg-ink/70 p-3">
              <span className="text-mute block text-[10px] uppercase">Security Guardrails</span>
              <span className="text-base font-bold text-mint">{review.eval_rubric.security} / 25</span>
            </div>
            <div className="rounded-xl border border-line bg-ink/70 p-3">
              <span className="text-mute block text-[10px] uppercase">Defect Elimination</span>
              <span className="text-base font-bold text-mint">{review.eval_rubric.defect_elimination} / 30</span>
            </div>
            <div className="rounded-xl border border-line bg-ink/70 p-3">
              <span className="text-mute block text-[10px] uppercase">Syntax & AST</span>
              <span className="text-base font-bold text-mint">{review.eval_rubric.syntax_integrity} / 20</span>
            </div>
            <div className="rounded-xl border border-line bg-ink/70 p-3">
              <span className="text-mute block text-[10px] uppercase">Regression Safety</span>
              <span className="text-base font-bold text-mint">{review.eval_rubric.regression_safety} / 15</span>
            </div>
            <div className="rounded-xl border border-line bg-ink/70 p-3">
              <span className="text-mute block text-[10px] uppercase">Code Quality</span>
              <span className="text-base font-bold text-mint">{review.eval_rubric.code_quality} / 10</span>
            </div>
          </div>

          {review.eval_rubric.breakdown && review.eval_rubric.breakdown.length > 0 && (
            <div className="mt-4 space-y-1 rounded-xl bg-ink/50 p-3 text-xs text-mute font-mono">
              {review.eval_rubric.breakdown.map((item, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <span className="text-mint">✓</span>
                  <span>{item}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Breaker Crash & Traceback ── */}
      {breaker?.stack && (
        <div className="mt-8 rounded-2xl border border-heat/30 bg-heat/5 p-5">
          <div className="flex items-center justify-between mb-2">
            <span className="font-mono text-xs font-bold uppercase text-heat flex items-center gap-1.5">
              <span>⚠️</span> Breaker Captured Crash Traceback
            </span>
            <span className="font-mono text-[11px] text-mute">{breaker.error}</span>
          </div>
          <div className="rounded-xl bg-ink p-3 font-mono text-xs text-heat border border-heat/20 overflow-x-auto">
            <pre className="text-[11px] leading-relaxed whitespace-pre-wrap">{breaker.stack}</pre>
          </div>
        </div>
      )}

      {/* ── Monaco Code Diff ── */}
      <div className="mt-8">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-mono text-xs font-bold uppercase text-mute">
            AI Code Repair Diff — {coder?.path || detective?.culprit_path || "Culprit File"}
          </h3>
          <span className="font-mono text-[11px] text-mute">Original (Left) vs Patched (Right)</span>
        </div>
        <MonacoDiffViewer original={coder?.original || ""} patched={coder?.patched || ""} />
      </div>

      {/* ── Approval Footer ── */}
      {incident?.status === "awaiting_approval" && (
        <div className="mt-6 rounded-2xl border border-mint/40 bg-mint/10 p-5 text-sm text-paper flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="font-bold text-mint">✓ Autonomous Repair Verification Complete</p>
            <p className="mt-0.5 text-xs text-mute">
              Patch verified and scored. An admin approval is the only path that mints a 15-minute AWS deploy session.
            </p>
          </div>
          <Link
            to="/console"
            className="rounded-full bg-mint px-5 py-2 text-xs font-extrabold text-ink shadow hover:opacity-90"
          >
            Review in Admin Console →
          </Link>
        </div>
      )}
    </main>
  );
}

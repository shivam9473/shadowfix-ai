import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { deleteProject, fetchProjects, importProject, runProjectIncident } from "../api";
import { useAuth } from "../auth";

export default function Projects() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  // Fix Desk Modal State
  const [activeProjForFix, setActiveProjForFix] = useState(null);
  const [fixMode, setFixMode] = useState("probe"); // "probe" | "traceback" | "scan"
  const [probeUrl, setProbeUrl] = useState("");
  const [tracebackInput, setTracebackInput] = useState("");
  const [testPayload, setTestPayload] = useState("");
  const [runningFix, setRunningFix] = useState(false);

  const [form, setForm] = useState({
    name: "",
    repo_url: "",
    branch: "main",
    target_url: "http://127.0.0.1:8010",
    language: "python",
  });

  async function loadProjects() {
    setLoading(true);
    try {
      const data = await fetchProjects();
      setProjects(data.projects || []);
      setError("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadProjects();
  }, []);

  async function handleImport(e) {
    e.preventDefault();
    if (!form.name || !form.repo_url) {
      setError("Project name and repository URL are required.");
      return;
    }
    setImporting(true);
    setError("");
    try {
      const res = await importProject(form);
      setNotice(`Repository "${res.project.name}" imported and indexed into Qdrant.`);
      setShowModal(false);
      setForm({
        name: "",
        repo_url: "",
        branch: "main",
        target_url: "http://127.0.0.1:8010",
        language: "python",
      });
      await loadProjects();
      setTimeout(() => setNotice(""), 4000);
    } catch (err) {
      setError(err.message);
    } finally {
      setImporting(false);
    }
  }

  async function handleDelete(projectId, name) {
    if (!window.confirm(`Delete project "${name}"?`)) return;
    try {
      await deleteProject(projectId);
      setProjects((prev) => prev.filter((p) => p.id !== projectId));
    } catch (err) {
      setError(err.message);
    }
  }

  function openFixModal(project) {
    setActiveProjForFix(project);
    setProbeUrl(project.target_url || "http://localhost:3000");
    setTracebackInput("");
    setTestPayload("");
    setFixMode("probe");
    setError("");
  }

  async function handleLaunchFixDesk(e) {
    e.preventDefault();
    if (!activeProjForFix) return;

    setRunningFix(true);
    setError("");
    try {
      const runConfig = {
        mode: fixMode,
        target_url: probeUrl.trim(),
        traceback: tracebackInput.trim(),
        test_payload: testPayload.trim(),
      };
      const incident = await runProjectIncident(activeProjForFix.id, runConfig);
      setActiveProjForFix(null);
      navigate(`/incident/${incident.id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setRunningFix(false);
    }
  }

  return (
    <main className="mx-auto max-w-7xl px-6 py-12">
      {/* ── Top Header ── */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line pb-8">
        <div>
          <div className="flex items-center gap-3">
            <span className="rounded-full bg-brand/20 px-3 py-1 font-mono text-xs font-bold text-mint uppercase">
              {user?.tenant_name || "Workspace"}
            </span>
            <span className="rounded-full border border-line px-3 py-1 font-mono text-xs text-mute">
              Plan: <strong className="text-paper uppercase">{user?.plan || "free"}</strong>
            </span>
          </div>
          <h1 className="mt-3 text-3xl font-extrabold tracking-tight">Imported Repositories</h1>
          <p className="mt-1 text-sm text-mute">
            Cursor & Claude style repository desk: connect your local/remote codebase, probe running endpoints or paste error logs to auto-repair.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/pricing"
            className="rounded-full border border-line px-5 py-2.5 text-sm font-semibold transition-colors hover:border-brand hover:text-paper"
          >
            Upgrade Plan
          </Link>
          <button
            type="button"
            onClick={() => setShowModal(true)}
            className="flex items-center gap-2 rounded-full bg-brand px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-brand/20 transition-transform hover:scale-[1.02] active:scale-95"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Import Repository
          </button>
        </div>
      </div>

      {/* ── Notices & Errors ── */}
      {notice && (
        <div className="mt-6 rounded-xl border border-mint/30 bg-mint/10 px-4 py-3 text-sm text-mint">
          {notice}
        </div>
      )}
      {error && (
        <div className="mt-6 rounded-xl border border-heat/30 bg-heat/10 px-4 py-3 text-sm text-heat">
          {error}
        </div>
      )}

      {/* ── Projects List ── */}
      {loading ? (
        <div className="mt-12 text-center text-sm text-mute">Loading repositories...</div>
      ) : projects.length === 0 ? (
        <div className="card mt-12 p-12 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-brand/15 text-brand">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z" />
              <path d="M6 6h10" />
              <path d="M6 10h10" />
            </svg>
          </div>
          <h3 className="mt-4 text-lg font-bold">No repositories imported yet</h3>
          <p className="mx-auto mt-2 max-w-md text-sm text-mute">
            Import your first GitHub repository or local codebase to index symbols into Qdrant and run autonomous bug fixes.
          </p>
          <button
            type="button"
            onClick={() => setShowModal(true)}
            className="mt-6 rounded-full bg-brand px-6 py-2.5 text-sm font-bold text-white shadow-md transition hover:bg-brand-deep"
          >
            Import Repository
          </button>
        </div>
      ) : (
        <div className="mt-8 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {projects.map((proj) => (
            <div key={proj.id} className="card flex flex-col justify-between p-6">
              <div>
                <div className="flex items-start justify-between gap-3">
                  <span className="flex h-10 w-10 flex-none items-center justify-center rounded-xl bg-brand/15 text-brand">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="16 18 22 12 16 6" />
                      <polyline points="8 6 2 12 8 18" />
                    </svg>
                  </span>
                  <span className="rounded-full bg-mint/15 px-2.5 py-0.5 font-mono text-[11px] font-bold text-mint">
                    {proj.status}
                  </span>
                </div>

                <h3 className="mt-4 text-lg font-bold">{proj.name}</h3>
                <p className="mt-1 truncate font-mono text-xs text-mute">{proj.repo_url}</p>

                <div className="mt-5 space-y-2 rounded-xl border border-line/60 bg-ink/60 p-3 text-xs">
                  <div className="flex justify-between">
                    <span className="text-mute">Branch:</span>
                    <span className="font-mono font-semibold text-paper">{proj.branch}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-mute">Target Endpoint:</span>
                    <span className="truncate font-mono font-semibold text-paper max-w-[160px]">
                      {proj.target_url || "Local"}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-mute">AST Index:</span>
                    <span className="font-mono font-semibold text-mint">{proj.files_indexed} files</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-mute">Language:</span>
                    <span className="font-mono uppercase text-paper">{proj.language}</span>
                  </div>
                </div>
              </div>

              <div className="mt-6 flex items-center justify-between gap-2 border-t border-line/70 pt-4">
                <button
                  type="button"
                  onClick={() => openFixModal(proj)}
                  className="rounded-full bg-mint px-4 py-2 text-xs font-bold text-ink shadow transition hover:opacity-90 flex items-center gap-1.5"
                >
                  <span>⚡</span> Trigger Bug Fix
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(proj.id, proj.name)}
                  className="rounded-full px-3 py-1.5 text-xs text-heat hover:bg-heat/10"
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Fix Desk Modal ── */}
      {activeProjForFix && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
          <div className="card w-full max-w-xl p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-line pb-4">
              <div>
                <span className="font-mono text-xs font-bold text-mint uppercase">Autonomous Fix Desk</span>
                <h3 className="text-xl font-extrabold text-paper">{activeProjForFix.name}</h3>
              </div>
              <button
                type="button"
                onClick={() => setActiveProjForFix(null)}
                className="text-mute hover:text-paper"
              >
                ✕
              </button>
            </div>

            <p className="mt-3 text-xs text-mute">
              Choose how ShadowFix should detect or reproduce the crash on this codebase:
            </p>

            {/* Mode Selector Tabs */}
            <div className="mt-4 grid grid-cols-3 gap-2 rounded-xl bg-ink/70 p-1.5 text-xs font-bold">
              <button
                type="button"
                onClick={() => setFixMode("probe")}
                className={`rounded-lg py-2 transition ${
                  fixMode === "probe" ? "bg-brand text-white shadow" : "text-mute hover:text-paper"
                }`}
              >
                🌐 Probe Server URL
              </button>
              <button
                type="button"
                onClick={() => setFixMode("traceback")}
                className={`rounded-lg py-2 transition ${
                  fixMode === "traceback" ? "bg-brand text-white shadow" : "text-mute hover:text-paper"
                }`}
              >
                📋 Paste Crash Log
              </button>
              <button
                type="button"
                onClick={() => setFixMode("scan")}
                className={`rounded-lg py-2 transition ${
                  fixMode === "scan" ? "bg-brand text-white shadow" : "text-mute hover:text-paper"
                }`}
              >
                🤖 Codebase Bug Scan
              </button>
            </div>

            <form onSubmit={handleLaunchFixDesk} className="mt-5 space-y-4">
              {fixMode === "probe" && (
                <div>
                  <label className="block text-xs font-bold text-mute uppercase">Target Endpoint URL</label>
                  <input
                    type="text"
                    required
                    placeholder="http://localhost:3000/api/checkout or https://api.mycorp.com"
                    value={probeUrl}
                    onChange={(e) => setProbeUrl(e.target.value)}
                    className="mt-1.5 w-full rounded-xl border border-line bg-ink px-4 py-2.5 text-xs font-mono text-paper focus:border-brand focus:outline-none"
                  />
                  <p className="mt-1.5 text-[11px] text-mute">
                    ShadowFix Breaker will probe this URL running on your local machine or server to detect 500 runtime errors.
                  </p>

                  <div className="mt-3">
                    <label className="block text-xs font-bold text-mute uppercase">Test Payload JSON (Optional)</label>
                    <input
                      type="text"
                      placeholder='{"items":[{"price":20,"qty":2}],"coupon":"SAVE100"}'
                      value={testPayload}
                      onChange={(e) => setTestPayload(e.target.value)}
                      className="mt-1.5 w-full rounded-xl border border-line bg-ink px-4 py-2 text-xs font-mono text-paper focus:border-brand focus:outline-none"
                    />
                  </div>
                </div>
              )}

              {fixMode === "traceback" && (
                <div>
                  <label className="block text-xs font-bold text-mute uppercase">Paste Terminal Error / Traceback</label>
                  <textarea
                    rows={6}
                    required
                    placeholder={`Traceback (most recent call last):\n  File "server.py", line 42, in checkout\n    return total / (1 - discount)\nZeroDivisionError: division by zero`}
                    value={tracebackInput}
                    onChange={(e) => setTracebackInput(e.target.value)}
                    className="mt-1.5 w-full rounded-xl border border-line bg-ink p-3 text-xs font-mono text-paper focus:border-brand focus:outline-none"
                  />
                  <p className="mt-1.5 text-[11px] text-mute">
                    Paste any unhandled exception or crash log from your machine console. The Detective agent will locate the exact culprit AST chunk.
                  </p>
                </div>
              )}

              {fixMode === "scan" && (
                <div className="rounded-xl border border-line/70 bg-ink/50 p-4 text-xs text-mute">
                  <p className="font-bold text-paper mb-1">🤖 Autonomous Code Inspection</p>
                  <p>
                    ShadowFix will analyze the imported repository files, identify error-prone logic (division without checks, unhandled exceptions, type mismatches), and automatically draft a verified patch.
                  </p>
                </div>
              )}

              <div className="mt-6 flex justify-end gap-3 pt-4 border-t border-line">
                <button
                  type="button"
                  onClick={() => setActiveProjForFix(null)}
                  className="rounded-full border border-line px-5 py-2 text-xs font-semibold hover:bg-panel-2"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={runningFix}
                  className="rounded-full bg-mint px-6 py-2 text-xs font-extrabold text-ink shadow hover:opacity-90 disabled:opacity-50"
                >
                  {runningFix ? "Launching Fix Desk..." : "⚡ Start Autonomous Fix"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Import Modal ── */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="card w-full max-w-lg p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-line pb-4">
              <h3 className="text-xl font-extrabold">Import Repository</h3>
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="text-mute hover:text-paper"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleImport} className="mt-6 space-y-4">
              <div>
                <label className="block text-xs font-bold text-mute uppercase">Project Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Acme Checkout API"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="mt-1.5 w-full rounded-xl border border-line bg-ink px-4 py-2.5 text-sm text-paper focus:border-brand focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-mute uppercase">GitHub Repository URL or Local Directory</label>
                <input
                  type="text"
                  required
                  placeholder="https://github.com/username/repository or local path"
                  value={form.repo_url}
                  onChange={(e) => setForm({ ...form, repo_url: e.target.value })}
                  className="mt-1.5 w-full rounded-xl border border-line bg-ink px-4 py-2.5 text-sm text-paper focus:border-brand focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-mute uppercase">Branch</label>
                  <input
                    type="text"
                    value={form.branch}
                    onChange={(e) => setForm({ ...form, branch: e.target.value })}
                    className="mt-1.5 w-full rounded-xl border border-line bg-ink px-4 py-2.5 text-sm text-paper focus:border-brand focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-mute uppercase">Language</label>
                  <select
                    value={form.language}
                    onChange={(e) => setForm({ ...form, language: e.target.value })}
                    className="mt-1.5 w-full rounded-xl border border-line bg-ink px-4 py-2.5 text-sm text-paper focus:border-brand focus:outline-none"
                  >
                    <option value="python">Python</option>
                    <option value="javascript">JavaScript / TypeScript</option>
                    <option value="go">Go</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-mute uppercase">Target Endpoint URL (Optional)</label>
                <input
                  type="text"
                  placeholder="http://localhost:3000 or http://127.0.0.1:8010"
                  value={form.target_url}
                  onChange={(e) => setForm({ ...form, target_url: e.target.value })}
                  className="mt-1.5 w-full rounded-xl border border-line bg-ink px-4 py-2.5 text-sm text-paper focus:border-brand focus:outline-none"
                />
                <p className="mt-1 text-[11px] text-mute">
                  The endpoint where your app runs on your machine or cloud.
                </p>
              </div>

              <div className="mt-6 flex justify-end gap-3 pt-4 border-t border-line">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="rounded-full border border-line px-5 py-2 text-sm font-semibold hover:bg-panel-2"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={importing}
                  className="rounded-full bg-brand px-6 py-2 text-sm font-bold text-white shadow hover:bg-brand-deep disabled:opacity-50"
                >
                  {importing ? "Cloning & Indexing..." : "Start Import"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}

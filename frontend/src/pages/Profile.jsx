import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { fetchUserAiConfig, updateUserAiConfig } from "../api";

function formatDate(iso) {
  if (!iso) return "N/A";
  try {
    return new Date(iso).toLocaleDateString("en-IN", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch {
    return "N/A";
  }
}

export default function Profile() {
  const { user, signOut, adminKey, saveAdminKey } = useAuth();
  const navigate = useNavigate();
  const [keyInput, setKeyInput] = useState(adminKey || "");
  const [keySaved, setKeySaved] = useState(false);
  const [keyError, setKeyError] = useState("");
  const [keyBusy, setKeyBusy] = useState(false);

  const [aiConfig, setAiConfig] = useState(null);
  const [aiLoading, setAiLoading] = useState(true);
  const [aiModelInput, setAiModelInput] = useState("");
  const [aiProviderInput, setAiProviderInput] = useState("auto");
  const [aiKeyInput, setAiKeyInput] = useState("");
  const [aiSaving, setAiSaving] = useState(false);
  const [aiSaved, setAiSaved] = useState(false);
  const [aiError, setAiError] = useState("");

  async function loadAiConfig() {
    try {
      setAiLoading(true);
      const data = await fetchUserAiConfig();
      setAiConfig(data);
      setAiModelInput(data.active_model || "");
      setAiProviderInput(data.provider || "auto");
    } catch (err) {
      console.warn("AI config fetch error:", err);
    } finally {
      setAiLoading(false);
    }
  }

  useEffect(() => {
    if (user) loadAiConfig();
  }, [user]);

  async function handleSaveAiConfig(e) {
    e.preventDefault();
    setAiSaving(true);
    setAiError("");
    setAiSaved(false);
    try {
      const payload = {
        active_model: aiModelInput,
        provider: aiProviderInput,
      };
      if (aiKeyInput.trim()) {
        payload.api_key = aiKeyInput.trim();
      }
      await updateUserAiConfig(payload);
      setAiSaved(true);
      setAiKeyInput("");
      await loadAiConfig();
      setTimeout(() => setAiSaved(false), 3000);
    } catch (err) {
      setAiError(err.message);
    } finally {
      setAiSaving(false);
    }
  }

  if (!user) {
    navigate("/login", { replace: true });
    return null;
  }

  const initials = user.name
    .trim()
    .split(" ")
    .map((w) => w[0]?.toUpperCase() || "")
    .slice(0, 2)
    .join("");

  function handleLogout() {
    signOut();
    navigate("/");
  }

  async function handleSaveKey(e) {
    e.preventDefault();
    const trimmed = keyInput.trim();
    if (!trimmed) {
      setKeyError("Enter the admin key.");
      return;
    }
    setKeyBusy(true);
    setKeyError("");
    try {
      const res = await fetch("/api/admin/dossier", {
        headers: { "X-Admin-Key": trimmed },
      });
      if (!res.ok) throw new Error("Invalid admin key — server returned 401.");
      saveAdminKey(trimmed);
      setKeySaved(true);
      setTimeout(() => setKeySaved(false), 3000);
    } catch (err) {
      setKeyError(err.message);
    } finally {
      setKeyBusy(false);
    }
  }

  function handleClearKey() {
    saveAdminKey("");
    setKeyInput("");
    setKeySaved(false);
    setKeyError("");
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-14">
      {/* ── Avatar + basic info ── */}
      <div className="card flex flex-col items-center gap-5 p-8 text-center sm:flex-row sm:text-left">
        <span className="flex h-20 w-20 flex-none items-center justify-center rounded-full bg-brand/20 text-3xl font-extrabold text-brand">
          {initials}
        </span>
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-extrabold tracking-tight">{user.name}</h1>
          <p className="mt-1 break-all text-sm text-mute">{user.email}</p>
          {user.joinedAt && (
            <p className="mt-1 text-xs text-mute">
              Member since {formatDate(user.joinedAt)}
            </p>
          )}
        </div>
      </div>

      {/* ── Account details ── */}
      <section className="card mt-6 p-6">
        <h2 className="font-mono text-xs tracking-widest text-mute">ACCOUNT DETAILS</h2>
        <dl className="mt-4 space-y-3 text-sm">
          <div className="grid grid-cols-[120px_1fr] gap-3">
            <dt className="text-mute">Full name</dt>
            <dd className="font-semibold">{user.name}</dd>
          </div>
          <div className="grid grid-cols-[120px_1fr] gap-3">
            <dt className="text-mute">Email</dt>
            <dd className="break-all font-semibold">{user.email}</dd>
          </div>
          {user.joinedAt && (
            <div className="grid grid-cols-[120px_1fr] gap-3">
              <dt className="text-mute">Joined</dt>
              <dd className="font-semibold">{formatDate(user.joinedAt)}</dd>
            </div>
          )}
          <div className="grid grid-cols-[120px_1fr] gap-3">
            <dt className="text-mute">Storage</dt>
            <dd className="font-semibold text-mute">This browser only (localStorage)</dd>
          </div>
        </dl>
      </section>

      {/* ── AI Engine & Token Usage ── */}
      <section className="card mt-6 p-6">
        <div className="flex items-center justify-between border-b border-line pb-3">
          <div>
            <h2 className="font-mono text-xs tracking-widest text-mute">AI ENGINE & TOKEN USAGE</h2>
            <p className="mt-1 text-sm text-paper font-semibold">
              Model Selection & Monthly Quota Consumption
            </p>
          </div>
          {aiConfig && (
            <span className="rounded-full bg-brand/20 px-3 py-1 font-mono text-xs font-bold text-mint uppercase">
              {aiConfig.plan_name || aiConfig.plan} Plan
            </span>
          )}
        </div>

        {aiLoading ? (
          <p className="mt-4 font-mono text-xs text-mute">Loading AI quota metrics...</p>
        ) : aiConfig ? (
          <div className="mt-5 space-y-5">
            {/* ── Token Progress Bar ── */}
            <div className="rounded-xl border border-line/60 bg-ink/70 p-4 font-mono">
              <div className="flex items-center justify-between text-xs mb-1.5">
                <span className="text-mute uppercase text-[10px] tracking-wider">Monthly Tokens Used</span>
                <span className={`font-bold ${aiConfig.percent_used > 85 ? "text-heat" : "text-mint"}`}>
                  {aiConfig.percent_used}% Used
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-panel border border-line/50">
                <div
                  className={`h-full transition-all duration-300 ${
                    aiConfig.percent_used > 85 ? "bg-heat" : "bg-mint"
                  }`}
                  style={{ width: `${Math.min(100, aiConfig.percent_used)}%` }}
                />
              </div>
              <div className="mt-2.5 grid grid-cols-3 gap-2 text-center text-[11px]">
                <div className="rounded bg-panel/70 p-2">
                  <p className="text-mute text-[10px]">Used</p>
                  <p className="font-bold text-paper mt-0.5">{(aiConfig.tokens_used_this_month).toLocaleString()}</p>
                </div>
                <div className="rounded bg-panel/70 p-2">
                  <p className="text-mute text-[10px]">Remaining</p>
                  <p className="font-bold text-mint mt-0.5">{(aiConfig.tokens_remaining).toLocaleString()}</p>
                </div>
                <div className="rounded bg-panel/70 p-2">
                  <p className="text-mute text-[10px]">Monthly Limit</p>
                  <p className="font-bold text-paper mt-0.5">{(aiConfig.monthly_token_quota).toLocaleString()}</p>
                </div>
              </div>
            </div>

            {/* ── Model & Key Form ── */}
            <form onSubmit={handleSaveAiConfig} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-mono text-mute mb-1">
                    Active AI Model
                  </label>
                  <select
                    value={aiModelInput}
                    onChange={(e) => setAiModelInput(e.target.value)}
                    className="w-full rounded-xl border border-line bg-ink px-3 py-2 text-xs text-paper focus:border-brand focus:outline-none font-mono"
                  >
                    {(aiConfig.allowed_models || []).map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                  <p className="mt-1 text-[10px] text-mute font-mono">
                    {aiConfig.plan === "ultra" || aiConfig.plan === "pro_max"
                      ? "✓ Ultra features unlocked: Claude 3.5 Sonnet & GPT-4o available."
                      : "Upgrade to Ultra for Claude 3.5 Sonnet & GPT-4o."}
                  </p>
                </div>

                <div>
                  <label className="block text-xs font-mono text-mute mb-1">
                    Provider Preference
                  </label>
                  <select
                    value={aiProviderInput}
                    onChange={(e) => setAiProviderInput(e.target.value)}
                    className="w-full rounded-xl border border-line bg-ink px-3 py-2 text-xs text-paper focus:border-brand focus:outline-none font-mono"
                  >
                    <option value="auto">Auto / Multi-Model Fallback</option>
                    <option value="openai">OpenAI (GPT)</option>
                    <option value="anthropic">Anthropic (Claude)</option>
                    <option value="gemini">Google Gemini</option>
                    <option value="aws_bedrock">AWS Bedrock Cloud</option>
                  </select>
                </div>
              </div>

              <div>
                <div className="flex justify-between items-center mb-1">
                  <label className="text-xs font-mono text-mute">
                    Custom Provider API Key (BYOK)
                  </label>
                  {aiConfig.has_custom_key && (
                    <span className="text-[10px] font-mono text-mint">
                      ✓ Key Active ({aiConfig.api_key_source === "superadmin" ? "Provisioned by Admin" : "Your Custom Key"})
                    </span>
                  )}
                </div>
                <input
                  type="password"
                  value={aiKeyInput}
                  onChange={(e) => setAiKeyInput(e.target.value)}
                  placeholder={aiConfig.has_custom_key ? `Current key: ${aiConfig.api_key} (leave blank to keep)` : "Paste your own OpenAI / Anthropic / Gemini API key"}
                  className="w-full rounded-xl border border-line bg-ink px-3 py-2 text-xs text-paper focus:border-brand focus:outline-none font-mono"
                />
                <p className="mt-1 text-[10px] text-mute font-mono">
                  You can use your own personal API key or use the team key configured by your SuperAdmin.
                </p>
              </div>

              <div className="flex items-center justify-between pt-2">
                <div>
                  {aiSaved && <span className="text-xs text-mint font-mono">✓ AI Model & Key updated successfully!</span>}
                  {aiError && <span className="text-xs text-heat font-mono">✕ {aiError}</span>}
                </div>
                <button
                  type="submit"
                  disabled={aiSaving}
                  className="rounded-xl bg-brand px-5 py-2.5 text-xs font-bold text-white hover:bg-brand/80 transition disabled:opacity-50"
                >
                  {aiSaving ? "Saving…" : "Save AI Settings"}
                </button>
              </div>
            </form>
          </div>
        ) : null}
      </section>

      {/* ── Admin key ── */}
      <section className="card mt-6 p-6">
        <h2 className="font-mono text-xs tracking-widest text-mute">ADMIN ACCESS</h2>
        <p className="mt-3 text-sm leading-relaxed text-mute">
          Paste your admin key to unlock the{" "}
          <span className="text-mint font-semibold">Admin console</span> link in the navbar.
          The key is validated against the server and stored in this tab only (sessionStorage).
        </p>
        <form onSubmit={handleSaveKey} className="mt-5 flex flex-col gap-3 sm:flex-row">
          <input
            type="password"
            value={keyInput}
            onChange={(e) => {
              setKeyInput(e.target.value);
              setKeyError("");
              setKeySaved(false);
            }}
            placeholder="e.g. Shadowfix@4321"
            className="flex-1 rounded-xl border border-line bg-ink px-4 py-3 text-sm text-paper placeholder:text-mute/60 transition-colors focus:border-brand focus:outline-none"
          />
          <button
            type="submit"
            disabled={keyBusy}
            className="rounded-xl bg-brand px-5 py-3 text-sm font-bold text-white transition-colors hover:bg-brand-deep disabled:opacity-60"
          >
            {keyBusy ? "Verifying…" : "Save key"}
          </button>
          {adminKey && (
            <button
              type="button"
              onClick={handleClearKey}
              className="rounded-xl border border-heat/50 px-5 py-3 text-sm font-semibold text-heat transition-colors hover:bg-heat/10"
            >
              Clear
            </button>
          )}
        </form>
        {keySaved && (
          <p className="mt-3 text-sm text-mint">
            ✓ Admin key saved — Admin console is now accessible from the navbar.
          </p>
        )}
        {keyError && (
          <p className="mt-3 text-sm text-heat">{keyError}</p>
        )}
        {adminKey && !keySaved && !keyError && (
          <p className="mt-3 text-xs text-mint">✓ Admin key is active in this session.</p>
        )}
      </section>

      {/* ── Session / logout ── */}
      <section className="card mt-6 p-6">
        <h2 className="font-mono text-xs tracking-widest text-mute">SESSION</h2>
        <p className="mt-3 text-sm leading-relaxed text-mute">
          Logging out clears your session and the active admin key from this tab.
        </p>
        <button
          type="button"
          onClick={handleLogout}
          className="mt-5 rounded-xl border border-heat/50 px-5 py-3 text-sm font-bold text-heat transition-colors hover:bg-heat/10"
        >
          Log out
        </button>
      </section>
    </main>
  );
}

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

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

import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import AuthShell, { Field, PasswordInput, inputClass } from "../components/AuthShell";
import { ADMIN_KEY_STORAGE, useAuth } from "../auth";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function Login() {
  const { user, signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const redirectTo = location.state?.from || "/demo";
  const [mode, setMode] = useState("account");

  if (user && mode === "account") return <Navigate to={redirectTo} replace />;

  return (
    <AuthShell
      title="Welcome back"
      sub="Log in to run incidents and review patches."
      footer={
        <>
          New to ShadowFix?{" "}
          <Link to="/signup" className="font-bold text-brand hover:text-mint">
            Create an account
          </Link>
        </>
      }
    >
      <div className="mb-6 grid grid-cols-2 gap-1 rounded-full border border-line bg-panel p-1" role="tablist" aria-label="Login method">
        {[
          ["account", "Email"],
          ["admin", "Admin key"],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={mode === id}
            onClick={() => setMode(id)}
            className={`rounded-full py-2 text-sm font-bold transition-colors ${
              mode === id ? "bg-brand text-white" : "text-mute hover:text-paper"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      {mode === "account" ? (
        <EmailForm signIn={signIn} onDone={() => navigate(redirectTo, { replace: true })} />
      ) : (
        <AdminKeyForm onDone={() => navigate("/console", { replace: true })} />
      )}
    </AuthShell>
  );
}

function EmailForm({ signIn, onDone }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    const next = {};
    if (!EMAIL_RE.test(email.trim())) next.email = "Enter a valid email, like you@company.com.";
    if (!password) next.password = "Enter your password.";
    setErrors(next);
    setFormError("");
    if (Object.keys(next).length) return;
    setBusy(true);
    try {
      await signIn({ email, password });
      onDone();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-5">
      <Field label="Email" id="email" error={errors.email}>
        <input
          id="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@company.com"
          aria-invalid={errors.email ? true : undefined}
          aria-describedby={errors.email ? "email-error" : undefined}
          className={inputClass}
        />
      </Field>
      <Field label="Password" id="password" error={errors.password}>
        <PasswordInput
          id="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          invalid={!!errors.password}
          describedBy={errors.password ? "password-error" : undefined}
        />
      </Field>
      <div aria-live="polite">
        {formError && (
          <p role="alert" className="rounded-xl border border-heat/40 bg-heat/10 px-4 py-3 text-sm text-heat">
            {formError}
          </p>
        )}
      </div>
      <button
        type="submit"
        disabled={busy}
        className="w-full rounded-full bg-brand py-3.5 text-sm font-bold text-white shadow-[0_0_40px_-10px_var(--color-brand)] transition-colors hover:bg-brand-deep disabled:opacity-60"
      >
        {busy ? "Logging in…" : "Log in"}
      </button>
      <p className="text-center text-xs leading-relaxed text-mute">
        Accounts are stored in this browser only. The backend does not have user accounts yet.
      </p>
    </form>
  );
}

function AdminKeyForm({ onDone }) {
  const { saveAdminKey } = useAuth();
  const [key, setKey] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    const trimmed = key.trim();
    if (!trimmed) { setError("Enter the admin key."); return; }
    setBusy(true);
    try {
      const res = await fetch("/api/admin/dossier", { headers: { "X-Admin-Key": trimmed } });
      if (!res.ok) throw new Error("Invalid admin key — server returned 401.");
      saveAdminKey(trimmed);
      onDone();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-5">
      <Field
        label="Admin key"
        id="admin-key"
        error={error}
        hint="Enter your admin key. It is validated against the server and stored in this tab only."
      >
        <PasswordInput
          id="admin-key"
          value={key}
          onChange={(e) => { setKey(e.target.value); setError(""); }}
          autoComplete="off"
          invalid={!!error}
          describedBy={error ? "admin-key-error" : undefined}
        />
      </Field>
      <button
        type="submit"
        disabled={busy}
        className="w-full rounded-full bg-brand py-3.5 text-sm font-bold text-white shadow-[0_0_40px_-10px_var(--color-brand)] transition-colors hover:bg-brand-deep disabled:opacity-60"
      >
        {busy ? "Verifying…" : "Open admin console"}
      </button>
    </form>
  );
}

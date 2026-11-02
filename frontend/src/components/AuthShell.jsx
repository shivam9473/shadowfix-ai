import { useState } from "react";
import { Link } from "react-router-dom";
import Logo from "./Logo";

const POINTS = [
  "Reproduce a crash and see the real traceback",
  "Review a scored patch before anything ships",
  "Approve one 15-minute deploy session at a time",
];

export default function AuthShell({ title, sub, children, footer }) {
  return (
    <main className="grid min-h-[calc(100vh-7rem)] lg:grid-cols-[1.05fr_1fr]">
      <aside className="glow-top relative hidden overflow-hidden border-r border-line bg-ink-2 p-12 lg:flex lg:flex-col lg:justify-between">
        <Link to="/" aria-label="ShadowFix home">
          <Logo />
        </Link>
        <div>
          <h2 className="max-w-md text-4xl font-extrabold leading-tight tracking-tight">
            Agents fix the crash. You keep the final say.
          </h2>
          <ul className="mt-8 space-y-4">
            {POINTS.map((point) => (
              <li key={point} className="flex items-start gap-3 text-mute">
                <span className="mt-1 flex h-5 w-5 flex-none items-center justify-center rounded-full bg-mint/15 text-[11px] font-bold text-mint">
                  ✓
                </span>
                {point}
              </li>
            ))}
          </ul>
        </div>
        <div className="card max-w-sm p-4">
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs text-mute">incident · shopkart</span>
            <span className="rounded-full bg-mint/15 px-2.5 py-0.5 text-[11px] font-bold text-mint">awaiting approval</span>
          </div>
          <p className="mt-3 text-sm font-bold">ZeroDivisionError in compute_total</p>
          <p className="mt-1 text-xs text-mute">Patch scored 92 / 85. Waiting for an admin.</p>
        </div>
      </aside>

      <section className="flex items-center justify-center px-6 py-14">
        <div className="w-full max-w-md">
          <h1 className="text-3xl font-extrabold tracking-tight">{title}</h1>
          <p className="mt-2 text-mute">{sub}</p>
          <div className="mt-8">{children}</div>
          {footer && <p className="mt-8 text-center text-sm text-mute">{footer}</p>}
        </div>
      </section>
    </main>
  );
}

export function Field({ label, id, error, hint, children }) {
  return (
    <div>
      <label htmlFor={id} className="mb-2 block text-sm font-bold">
        {label}
      </label>
      {children}
      {error ? (
        <p id={`${id}-error`} className="mt-1.5 text-sm text-heat">
          {error}
        </p>
      ) : (
        hint && <p className="mt-1.5 text-xs text-mute">{hint}</p>
      )}
    </div>
  );
}

export const inputClass =
  "w-full rounded-xl border border-line bg-ink px-4 py-3 text-sm text-paper placeholder:text-mute/60 transition-colors focus:border-brand focus:outline-none aria-[invalid=true]:border-heat";

export function PasswordInput({ id, value, onChange, autoComplete, invalid, describedBy }) {
  const [shown, setShown] = useState(false);
  return (
    <div className="relative">
      <input
        id={id}
        type={shown ? "text" : "password"}
        value={value}
        onChange={onChange}
        autoComplete={autoComplete}
        aria-invalid={invalid || undefined}
        aria-describedby={describedBy}
        className={`${inputClass} pr-16`}
      />
      <button
        type="button"
        onClick={() => setShown((v) => !v)}
        className="absolute inset-y-0 right-3 my-auto h-8 rounded-lg px-2 text-xs font-bold text-mute hover:text-paper"
      >
        {shown ? "Hide" : "Show"}
      </button>
    </div>
  );
}

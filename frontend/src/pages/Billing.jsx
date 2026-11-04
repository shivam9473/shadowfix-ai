import { useEffect, useState } from "react";
import { fetchCurrentBilling, fetchPlans, upgradePlan } from "../api";
import { useAuth } from "../auth";

export default function Billing() {
  const { user, refreshUser } = useAuth();
  const [plans, setPlans] = useState([]);
  const [billing, setBilling] = useState(null);
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState("");
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [cardNumber, setCardNumber] = useState("4242 •••• •••• 4242");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  async function loadData() {
    setLoading(true);
    try {
      const [pRes, bRes] = await Promise.all([fetchPlans(), fetchCurrentBilling()]);
      setPlans(pRes.plans || []);
      setBilling(bRes);
      setError("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  async function handleConfirmUpgrade() {
    if (!selectedPlan) return;
    setUpgrading(selectedPlan.id);
    setError("");
    try {
      const res = await upgradePlan(selectedPlan.id, "card_visa_4242");
      setNotice(`Successfully upgraded to ${selectedPlan.name}! Quota updated.`);
      setShowModal(false);
      await loadData();
      await refreshUser();
      setTimeout(() => setNotice(""), 4000);
    } catch (err) {
      setError(err.message);
    } finally {
      setUpgrading("");
    }
  }

  const currentPlanId = billing?.plan || user?.plan || "free";

  return (
    <main className="mx-auto max-w-7xl px-6 py-12">
      {/* ── Top Header ── */}
      <div className="text-center">
        <p className="font-mono text-xs font-bold uppercase tracking-widest text-mint">
          SaaS Subscriptions
        </p>
        <h1 className="mt-3 text-4xl font-extrabold tracking-tight">
          Flexible Plans for Engineering Desks
        </h1>
        <p className="mx-auto mt-3 max-w-2xl text-sm leading-relaxed text-mute">
          Choose the right autonomous QA and repair power for your team. From single projects to multi-repository enterprise desks with automated AWS sessions and multi-model consensus.
        </p>
      </div>

      {/* ── Current Plan Card ── */}
      {billing && (
        <div className="card mx-auto mt-10 max-w-2xl p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="font-mono text-xs text-mute uppercase">Current Workspace Plan</p>
              <div className="mt-1 flex items-center gap-3">
                <h3 className="text-2xl font-black uppercase text-paper">{currentPlanId}</h3>
                <span className="rounded-full bg-mint/20 px-3 py-0.5 text-xs font-bold text-mint">
                  Active
                </span>
              </div>
            </div>
            <div className="text-right">
              <p className="text-xs text-mute">Daily Incidents Used</p>
              <p className="mt-1 font-mono text-lg font-bold text-paper">
                {billing.quota_used_today} / {billing.quota_limit}
              </p>
            </div>
          </div>
        </div>
      )}

      {notice && (
        <div className="mx-auto mt-6 max-w-3xl rounded-xl border border-mint/30 bg-mint/10 px-4 py-3 text-center text-sm text-mint">
          {notice}
        </div>
      )}
      {error && (
        <div className="mx-auto mt-6 max-w-3xl rounded-xl border border-heat/30 bg-heat/10 px-4 py-3 text-center text-sm text-heat">
          {error}
        </div>
      )}

      {/* ── Plans Grid ── */}
      <div className="mt-12 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        {plans.map((p) => {
          const isCurrent = p.id === currentPlanId;
          const isProMax = p.id === "pro_max";

          return (
            <div
              key={p.id}
              className={`card relative flex flex-col justify-between p-6 transition-all ${
                isProMax
                  ? "border-mint/50 shadow-xl shadow-mint/5 ring-1 ring-mint/30"
                  : isCurrent
                  ? "border-brand ring-1 ring-brand/30"
                  : ""
              }`}
            >
              {isProMax && (
                <span className="absolute -top-3 right-6 rounded-full bg-mint px-3 py-0.5 font-mono text-[10px] font-extrabold uppercase text-ink">
                  Most Powerful
                </span>
              )}

              <div>
                <h3 className="text-xl font-bold">{p.name}</h3>
                <div className="mt-3 flex items-baseline gap-1">
                  <span className="text-4xl font-extrabold">${p.price_monthly}</span>
                  <span className="text-xs text-mute">/ month</span>
                </div>
                <p className="mt-2 font-mono text-xs text-mint">AI: {p.ai_model}</p>

                <div className="my-6 border-t border-line/60" />

                <ul className="space-y-3 text-xs text-paper">
                  {p.features.map((feat, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <span className="text-mint font-bold">✓</span>
                      <span>{feat}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="mt-8 pt-4 border-t border-line/60">
                {isCurrent ? (
                  <button
                    type="button"
                    disabled
                    className="w-full rounded-full border border-mint/40 bg-mint/10 py-2.5 text-xs font-bold text-mint"
                  >
                    Current Plan
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedPlan(p);
                      setShowModal(true);
                    }}
                    className={`w-full rounded-full py-2.5 text-xs font-bold transition shadow ${
                      isProMax
                        ? "bg-mint text-ink hover:opacity-90 font-extrabold"
                        : "bg-brand text-white hover:bg-brand-deep"
                    }`}
                  >
                    Select {p.name}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Invoices Section ── */}
      {billing?.invoices?.length > 0 && (
        <section className="mt-16 border-t border-line pt-10">
          <h2 className="text-xl font-extrabold tracking-tight">Billing & Invoices</h2>
          <div className="mt-4 overflow-x-auto rounded-2xl border border-line bg-panel">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-line bg-ink/70 text-mute uppercase font-mono">
                <tr>
                  <th className="px-5 py-3">Invoice ID</th>
                  <th className="px-5 py-3">Date</th>
                  <th className="px-5 py-3">Plan</th>
                  <th className="px-5 py-3">Amount</th>
                  <th className="px-5 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/60 font-mono">
                {billing.invoices.map((inv) => (
                  <tr key={inv.id} className="hover:bg-panel-2">
                    <td className="px-5 py-3.5 font-bold text-paper">{inv.id}</td>
                    <td className="px-5 py-3.5 text-mute">{new Date(inv.date).toLocaleDateString()}</td>
                    <td className="px-5 py-3.5 font-bold uppercase text-mint">{inv.plan}</td>
                    <td className="px-5 py-3.5 font-bold text-paper">${inv.amount} USD</td>
                    <td className="px-5 py-3.5">
                      <span className="rounded-full bg-mint/15 px-2 py-0.5 text-[10px] text-mint">
                        {inv.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* ── Upgrade Confirmation Modal ── */}
      {showModal && selectedPlan && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
          <div className="card w-full max-w-md p-6 shadow-2xl">
            <h3 className="text-xl font-extrabold">Confirm Subscription Upgrade</h3>
            <p className="mt-1 text-xs text-mute">
              Upgrade your workspace to the <strong>{selectedPlan.name}</strong> plan.
            </p>

            <div className="mt-5 rounded-xl border border-line bg-ink p-4">
              <div className="flex justify-between text-sm">
                <span className="text-mute">Selected Tier</span>
                <span className="font-bold uppercase text-paper">{selectedPlan.name}</span>
              </div>
              <div className="mt-2 flex justify-between text-sm">
                <span className="text-mute">Billed Amount</span>
                <span className="font-black text-mint text-base">${selectedPlan.price_monthly} / mo</span>
              </div>
              <div className="mt-2 flex justify-between text-sm">
                <span className="text-mute">Daily Incidents</span>
                <span className="font-mono text-paper">{selectedPlan.daily_incidents} runs</span>
              </div>
            </div>

            <div className="mt-5">
              <label className="block text-xs font-bold text-mute uppercase">Payment Method</label>
              <div className="mt-1 flex items-center justify-between rounded-xl border border-line bg-panel-2 px-4 py-2.5 text-xs text-paper">
                <span className="font-mono">💳 Visa ending in 4242</span>
                <span className="text-mint font-bold">Simulated</span>
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-3 pt-4 border-t border-line">
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="rounded-full border border-line px-5 py-2 text-xs font-semibold hover:bg-panel-2"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmUpgrade}
                disabled={upgrading !== ""}
                className="rounded-full bg-brand px-6 py-2 text-xs font-bold text-white shadow hover:bg-brand-deep disabled:opacity-50"
              >
                {upgrading ? "Activating..." : "Confirm & Pay"}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

import { useEffect, useState } from "react";
import {
  fetchCurrentBilling,
  fetchPlans,
  createRazorpayOrder,
  verifyRazorpayPayment,
  createPaypalOrder,
  capturePaypalOrder,
  refundInvoice,
  upgradePlan,
} from "../api";
import { useAuth } from "../auth";

function loadScript(src) {
  return new Promise((resolve) => {
    const existing = document.querySelector(`script[src="${src}"]`);
    if (existing) return resolve(true);
    const script = document.createElement("script");
    script.src = src;
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}

export default function Billing() {
  const { user, refreshUser } = useAuth();
  const [plans, setPlans] = useState([]);
  const [gateways, setGateways] = useState({});
  const [billing, setBilling] = useState(null);
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState("");
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("razorpay"); // 'razorpay' | 'paypal' | 'sandbox'
  const [refundingId, setRefundingId] = useState("");

  async function loadData() {
    setLoading(true);
    try {
      const [pRes, bRes] = await Promise.all([fetchPlans(), fetchCurrentBilling()]);
      setPlans(pRes.plans || []);
      setGateways(pRes.gateways || {});
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
    // Preload Razorpay checkout script
    loadScript("https://checkout.razorpay.com/v1/checkout.js");
  }, []);

  // ── Razorpay Payment Handler ──
  async function handleRazorpayPayment() {
    if (!selectedPlan) return;
    setUpgrading("razorpay");
    setError("");

    try {
      const orderRes = await createRazorpayOrder(selectedPlan.id, "INR");
      const order = orderRes.order;

      // If in sandbox mode without Razorpay script or mock order
      if (order.sandbox_mode && (!window.Razorpay || !gateways.razorpay?.configured)) {
        // Complete mock checkout
        const verifyRes = await verifyRazorpayPayment({
          order_id: order.order_id,
          payment_id: `pay_mock_${Date.now()}`,
          signature: "sandbox_verified",
          plan: selectedPlan.id,
          currency: "INR",
        });
        setNotice(`Payment successful! Upgraded to ${selectedPlan.name} (Simulated Sandbox).`);
        setShowModal(false);
        await loadData();
        await refreshUser();
        return;
      }

      // Standard Razorpay Modal
      const loaded = await loadScript("https://checkout.razorpay.com/v1/checkout.js");
      if (!loaded || !window.Razorpay) {
        throw new Error("Unable to load Razorpay Checkout SDK. Please check your network connection.");
      }

      const options = {
        key: order.key_id,
        amount: order.amount,
        currency: order.currency,
        name: "ShadowFix AI",
        description: `Upgrade to ${selectedPlan.name} Plan`,
        image: "https://cdn-icons-png.flaticon.com/512/2099/2099058.png",
        order_id: order.order_id,
        prefill: {
          name: user?.name || "Developer",
          email: user?.email || "dev@shadowfix.ai",
        },
        theme: {
          color: "#059669",
        },
        handler: async function (response) {
          try {
            setUpgrading("verifying");
            await verifyRazorpayPayment({
              order_id: response.razorpay_order_id || order.order_id,
              payment_id: response.razorpay_payment_id,
              signature: response.razorpay_signature,
              plan: selectedPlan.id,
              currency: order.currency,
            });
            setNotice(`Payment verified! Upgraded to ${selectedPlan.name} Plan.`);
            setShowModal(false);
            await loadData();
            await refreshUser();
          } catch (vErr) {
            setError(`Payment verification failed: ${vErr.message}`);
          } finally {
            setUpgrading("");
          }
        },
        modal: {
          ondismiss: function () {
            setUpgrading("");
          },
        },
      };

      const rzp = new window.Razorpay(options);
      rzp.on("payment.failed", function (response) {
        setError(`Payment failed: ${response.error.description || "Unknown error"}`);
        setUpgrading("");
      });
      rzp.open();
    } catch (err) {
      setError(err.message);
      setUpgrading("");
    }
  }

  // ── PayPal Payment Handler ──
  async function handlePaypalPayment() {
    if (!selectedPlan) return;
    setUpgrading("paypal");
    setError("");

    try {
      const orderRes = await createPaypalOrder(selectedPlan.id);
      const order = orderRes.order;

      // Capture PayPal order
      const captureRes = await capturePaypalOrder({
        order_id: order.order_id,
        plan: selectedPlan.id,
      });

      setNotice(`PayPal payment captured! Upgraded to ${selectedPlan.name} Plan.`);
      setShowModal(false);
      await loadData();
      await refreshUser();
    } catch (err) {
      setError(`PayPal payment failed: ${err.message}`);
    } finally {
      setUpgrading("");
    }
  }

  // ── Instant Sandbox Test ──
  async function handleSandboxUpgrade() {
    if (!selectedPlan) return;
    setUpgrading("sandbox");
    setError("");
    try {
      await upgradePlan(selectedPlan.id, "instant_sandbox_qa");
      setNotice(`Upgraded to ${selectedPlan.name} via Sandbox Test Mode!`);
      setShowModal(false);
      await loadData();
      await refreshUser();
    } catch (err) {
      setError(err.message);
    } finally {
      setUpgrading("");
    }
  }

  // ── Refund Action ──
  async function handleRefund(invoiceId) {
    if (!confirm("Are you sure you want to refund this invoice? Your workspace will downgrade to the Free plan.")) {
      return;
    }
    setRefundingId(invoiceId);
    setError("");
    try {
      await refundInvoice(invoiceId, "User requested refund from billing console");
      setNotice(`Refund processed for ${invoiceId}. Plan downgraded to Free.`);
      await loadData();
      await refreshUser();
    } catch (err) {
      setError(err.message);
    } finally {
      setRefundingId("");
    }
  }

  const currentPlanId = billing?.plan || user?.plan || "free";
  const rzpPaymentLink = gateways?.razorpay?.payment_link || "https://razorpay.me/@shivamkumar98";

  return (
    <main className="mx-auto max-w-7xl px-6 py-12">
      {/* ── Top Header ── */}
      <div className="text-center">
        <p className="font-mono text-xs font-bold uppercase tracking-widest text-mint">
          SaaS Subscriptions & Payments
        </p>
        <h1 className="mt-3 text-4xl font-extrabold tracking-tight">
          Flexible Plans for Production Engineering
        </h1>
        <p className="mx-auto mt-3 max-w-2xl text-sm leading-relaxed text-mute">
          Choose the right autonomous QA and repair power for your team. Supports Razorpay (UPI, NetBanking, Cards) and PayPal Checkout with real-time webhooks and durable records.
        </p>

        {/* ── Gateway Status Badges ── */}
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          <div className="flex items-center gap-2 rounded-full border border-line bg-panel px-4 py-1.5 text-xs">
            <span className="h-2 w-2 rounded-full bg-mint animate-pulse" />
            <span className="font-semibold text-paper">Razorpay:</span>
            <span className="text-mint font-mono font-bold">UPI / Cards / NetBanking</span>
            <a
              href={rzpPaymentLink}
              target="_blank"
              rel="noreferrer"
              className="ml-2 rounded-md bg-mint/15 px-2 py-0.5 text-[10px] font-bold text-mint hover:bg-mint/25"
            >
              @shivamkumar98 ↗
            </a>
          </div>
          <div className="flex items-center gap-2 rounded-full border border-line bg-panel px-4 py-1.5 text-xs">
            <span className="h-2 w-2 rounded-full bg-blue-400" />
            <span className="font-semibold text-paper">PayPal:</span>
            <span className="text-blue-400 font-mono font-bold">Sandbox (Active)</span>
          </div>
        </div>
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
                {p.price_monthly > 0 && (
                  <p className="mt-1 font-mono text-xs text-mute">
                    ≈ ₹{Math.round(p.price_monthly * 85).toLocaleString("en-IN")} INR
                  </p>
                )}
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
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-extrabold tracking-tight">Payment Records & Invoices</h2>
            <span className="text-xs text-mute">{billing.invoices.length} transaction(s) recorded</span>
          </div>

          <div className="mt-4 overflow-x-auto rounded-2xl border border-line bg-panel">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-line bg-ink/70 text-mute uppercase font-mono">
                <tr>
                  <th className="px-5 py-3">Invoice ID</th>
                  <th className="px-5 py-3">Date</th>
                  <th className="px-5 py-3">Gateway</th>
                  <th className="px-5 py-3">Plan</th>
                  <th className="px-5 py-3">Amount</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/60 font-mono">
                {billing.invoices.map((inv) => (
                  <tr key={inv.id} className="hover:bg-panel-2">
                    <td className="px-5 py-3.5 font-bold text-paper">{inv.id}</td>
                    <td className="px-5 py-3.5 text-mute">{new Date(inv.date).toLocaleDateString()}</td>
                    <td className="px-5 py-3.5 font-bold uppercase">
                      <span
                        className={`rounded-md px-2 py-0.5 text-[10px] ${
                          inv.gateway === "razorpay"
                            ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                            : inv.gateway === "paypal"
                            ? "bg-blue-500/15 text-blue-400 border border-blue-500/30"
                            : "bg-slate-500/15 text-slate-400 border border-slate-500/30"
                        }`}
                      >
                        {inv.gateway || "card"}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 font-bold uppercase text-mint">{inv.plan}</td>
                    <td className="px-5 py-3.5 font-bold text-paper">
                      {inv.currency === "INR" ? `₹${inv.amount}` : `$${inv.amount} USD`}
                    </td>
                    <td className="px-5 py-3.5">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                          inv.status === "paid"
                            ? "bg-mint/15 text-mint"
                            : inv.status === "refunded"
                            ? "bg-yellow-500/15 text-yellow-400"
                            : "bg-heat/15 text-heat"
                        }`}
                      >
                        {inv.status}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      {inv.status === "paid" && (
                        <button
                          type="button"
                          onClick={() => handleRefund(inv.id)}
                          disabled={refundingId === inv.id}
                          className="rounded border border-line px-2.5 py-1 text-[10px] text-mute hover:border-heat hover:text-heat transition"
                        >
                          {refundingId === inv.id ? "Refunding..." : "Refund"}
                        </button>
                      )}
                      {inv.status === "refunded" && (
                        <span className="text-[10px] text-mute">Refunded</span>
                      )}
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
          <div className="card w-full max-w-lg p-6 shadow-2xl">
            <div className="flex items-center justify-between">
              <h3 className="text-xl font-extrabold">Complete Subscription Upgrade</h3>
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="text-mute hover:text-paper text-sm"
              >
                ✕
              </button>
            </div>
            <p className="mt-1 text-xs text-mute">
              Upgrade your engineering workspace to <strong>{selectedPlan.name}</strong>.
            </p>

            {/* Plan Summary Card */}
            <div className="mt-5 rounded-xl border border-line bg-ink p-4 space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-mute">Selected Tier</span>
                <span className="font-bold uppercase text-paper">{selectedPlan.name}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-mute">Monthly Amount</span>
                <span className="font-black text-mint text-base">
                  ${selectedPlan.price_monthly} USD (≈ ₹{Math.round(selectedPlan.price_monthly * 85).toLocaleString("en-IN")})
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-mute">Incident Quota</span>
                <span className="font-mono text-paper">{selectedPlan.daily_incidents} runs / day</span>
              </div>
            </div>

            {/* Payment Gateway Selector */}
            <div className="mt-5">
              <label className="block text-xs font-bold text-mute uppercase tracking-wider mb-2">
                Select Payment Gateway
              </label>

              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => setPaymentMethod("razorpay")}
                  className={`flex flex-col items-center justify-center p-3 rounded-xl border text-xs font-bold transition ${
                    paymentMethod === "razorpay"
                      ? "border-emerald-500 bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500"
                      : "border-line bg-panel hover:bg-panel-2 text-mute"
                  }`}
                >
                  <span className="text-base mb-1">⚡</span>
                  <span>Razorpay</span>
                  <span className="text-[10px] font-mono text-mute mt-0.5">UPI / Cards</span>
                </button>

                <button
                  type="button"
                  onClick={() => setPaymentMethod("paypal")}
                  className={`flex flex-col items-center justify-center p-3 rounded-xl border text-xs font-bold transition ${
                    paymentMethod === "paypal"
                      ? "border-blue-500 bg-blue-500/10 text-blue-400 ring-1 ring-blue-500"
                      : "border-line bg-panel hover:bg-panel-2 text-mute"
                  }`}
                >
                  <span className="text-base mb-1">🅿️</span>
                  <span>PayPal</span>
                  <span className="text-[10px] font-mono text-mute mt-0.5">Sandbox USD</span>
                </button>

                <button
                  type="button"
                  onClick={() => setPaymentMethod("sandbox")}
                  className={`flex flex-col items-center justify-center p-3 rounded-xl border text-xs font-bold transition ${
                    paymentMethod === "sandbox"
                      ? "border-mint bg-mint/10 text-mint ring-1 ring-mint"
                      : "border-line bg-panel hover:bg-panel-2 text-mute"
                  }`}
                >
                  <span className="text-base mb-1">🧪</span>
                  <span>Sandbox Test</span>
                  <span className="text-[10px] font-mono text-mute mt-0.5">Instant QA</span>
                </button>
              </div>
            </div>

            {/* Gateway Details & Action Panel */}
            <div className="mt-5 rounded-xl border border-line bg-panel-2 p-4">
              {paymentMethod === "razorpay" && (
                <div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-paper">Razorpay Gateway:</span>
                    <span className="text-mint font-bold">Standard Modal + UPI Link</span>
                  </div>
                  <p className="mt-1 text-[11px] text-mute leading-relaxed">
                    Pay securely using Google Pay, PhonePe, Paytm, Credit/Debit cards, or NetBanking.
                  </p>

                  <div className="mt-4 flex flex-col gap-2">
                    <button
                      type="button"
                      onClick={handleRazorpayPayment}
                      disabled={upgrading !== ""}
                      className="w-full rounded-full bg-emerald-600 py-2.5 text-xs font-bold text-white shadow hover:bg-emerald-500 disabled:opacity-50 transition"
                    >
                      {upgrading === "razorpay"
                        ? "Opening Razorpay..."
                        : upgrading === "verifying"
                        ? "Verifying Payment Signature..."
                        : `Pay ₹${Math.round(selectedPlan.price_monthly * 85).toLocaleString("en-IN")} via Razorpay Modal`}
                    </button>

                    <div className="flex items-center gap-2 pt-1">
                      <span className="text-[10px] text-mute">Or pay directly at handle:</span>
                      <a
                        href={rzpPaymentLink}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[10px] font-bold text-mint hover:underline font-mono"
                      >
                        {rzpPaymentLink} ↗
                      </a>
                    </div>
                  </div>
                </div>
              )}

              {paymentMethod === "paypal" && (
                <div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-paper">PayPal Checkout (v2):</span>
                    <span className="text-blue-400 font-bold">Sandbox Mode</span>
                  </div>
                  <p className="mt-1 text-[11px] text-mute leading-relaxed">
                    Direct integration with PayPal OAuth v2 Order Creation & Capture API using configured developer keys.
                  </p>
                  <button
                    type="button"
                    onClick={handlePaypalPayment}
                    disabled={upgrading !== ""}
                    className="mt-4 w-full rounded-full bg-blue-600 py-2.5 text-xs font-bold text-white shadow hover:bg-blue-500 disabled:opacity-50 transition"
                  >
                    {upgrading === "paypal"
                      ? "Processing PayPal Order..."
                      : `Pay $${selectedPlan.price_monthly} USD with PayPal`}
                  </button>
                </div>
              )}

              {paymentMethod === "sandbox" && (
                <div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-paper">Developer Test Mode:</span>
                    <span className="text-mint font-bold">1-Click Instant</span>
                  </div>
                  <p className="mt-1 text-[11px] text-mute leading-relaxed">
                    Instantly simulate a successful upgrade to test daily incident quotas and repository import limits without live charges.
                  </p>
                  <button
                    type="button"
                    onClick={handleSandboxUpgrade}
                    disabled={upgrading !== ""}
                    className="mt-4 w-full rounded-full bg-brand py-2.5 text-xs font-bold text-white shadow hover:bg-brand-deep disabled:opacity-50 transition"
                  >
                    {upgrading === "sandbox" ? "Activating..." : "Instant Activate Plan (Test Mode)"}
                  </button>
                </div>
              )}
            </div>

            <div className="mt-6 flex justify-end gap-3 pt-3 border-t border-line">
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="rounded-full border border-line px-5 py-2 text-xs font-semibold hover:bg-panel-2"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

export async function runDemo() {
  const token = localStorage.getItem("shadowfix.token") || "";
  const response = await fetch("/api/demo/run", {
    method: "POST",
    headers: { "X-Session-Token": token },
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function getIncident(id) {
  const token = localStorage.getItem("shadowfix.token") || "";
  const response = await fetch(`/api/incidents/${id}`, {
    headers: { "X-Session-Token": token },
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function listIncidents() {
  const token = localStorage.getItem("shadowfix.token") || "";
  const response = await fetch("/api/incidents", {
    headers: { "X-Session-Token": token },
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function adminFetch(path, adminKey, options = {}) {
  const token = localStorage.getItem("shadowfix.token") || "";
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (adminKey) {
    headers["X-Admin-Key"] = adminKey;
  }
  if (token) {
    headers["X-Session-Token"] = token;
  }

  const response = await fetch(path, {
    ...options,
    headers,
  });
  const text = await response.text();
  const body = text ? JSON.parse(text) : {};
  if (!response.ok) throw new Error(body.detail || text);
  return body;
}

// ── Projects API ──
export async function fetchProjects() {
  const token = localStorage.getItem("shadowfix.token") || "";
  const res = await fetch("/api/projects", {
    headers: { "X-Session-Token": token },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function importProject(projectData) {
  const token = localStorage.getItem("shadowfix.token") || "";
  const res = await fetch("/api/projects/import", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Token": token,
    },
    body: JSON.stringify(projectData),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "Failed to import project.");
  return body;
}

export async function deleteProject(projectId) {
  const token = localStorage.getItem("shadowfix.token") || "";
  const res = await fetch(`/api/projects/${projectId}`, {
    method: "DELETE",
    headers: { "X-Session-Token": token },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function runProjectIncident(projectId, runConfig = {}) {
  const token = localStorage.getItem("shadowfix.token") || "";
  const res = await fetch(`/api/projects/${projectId}/run`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Token": token,
    },
    body: JSON.stringify(runConfig),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "Failed to start incident.");
  return body;
}

export async function fetchProjectBugs(projectId) {
  const token = localStorage.getItem("shadowfix.token") || "";
  const res = await fetch(`/api/projects/${projectId}/bugs`, {
    headers: { "X-Session-Token": token },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fixProjectBug(projectId, bugData) {
  const token = localStorage.getItem("shadowfix.token") || "";
  const res = await fetch(`/api/projects/${projectId}/fix-bug`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Token": token,
    },
    body: JSON.stringify(bugData),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "Failed to trigger bug fix.");
  return body;
}

// ── Billing API ──
export async function fetchPlans() {
  const res = await fetch("/api/billing/plans");
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchCurrentBilling() {
  const token = localStorage.getItem("shadowfix.token") || "";
  const res = await fetch("/api/billing/current", {
    headers: { "X-Session-Token": token },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function upgradePlan(planName, paymentMethod = "card_demo") {
  const token = localStorage.getItem("shadowfix.token") || "";
  const res = await fetch("/api/billing/upgrade", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Token": token,
    },
    body: JSON.stringify({ plan: planName, payment_method: paymentMethod }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "Upgrade failed.");
  return body;
}

// ── Super Admin APIs ──
export async function fetchSuperAdminMetrics(adminKey) {
  return adminFetch("/api/superadmin/metrics", adminKey);
}

export async function fetchSuperAdminTenants(adminKey) {
  return adminFetch("/api/superadmin/tenants", adminKey);
}

export async function overrideTenantPlan(adminKey, tenantId, newPlan) {
  return adminFetch(`/api/superadmin/tenants/${tenantId}/plan`, adminKey, {
    method: "POST",
    body: JSON.stringify({ plan: newPlan }),
  });
}

export async function setTenantStatus(adminKey, tenantId, status) {
  return adminFetch(`/api/superadmin/tenants/${tenantId}/status`, adminKey, {
    method: "POST",
    body: JSON.stringify({ status }),
  });
}

export async function fetchSuperAdminProjects(adminKey) {
  return adminFetch("/api/superadmin/projects", adminKey);
}

export async function fetchSuperAdminInvoices(adminKey) {
  return adminFetch("/api/superadmin/invoices", adminKey);
}

export async function fetchSuperAdminAudit(adminKey) {
  return adminFetch("/api/superadmin/audit", adminKey);
}

// ── Payment Gateway APIs (Razorpay & PayPal) ──
export async function createRazorpayOrder(planId, currency = "INR") {
  const token = localStorage.getItem("shadowfix.token") || "";
  const res = await fetch("/api/billing/razorpay/create-order", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Token": token,
    },
    body: JSON.stringify({ plan: planId, currency }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "Failed to create Razorpay order.");
  return body;
}

export async function verifyRazorpayPayment(paymentData) {
  const token = localStorage.getItem("shadowfix.token") || "";
  const res = await fetch("/api/billing/razorpay/verify-payment", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Token": token,
    },
    body: JSON.stringify(paymentData),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "Razorpay payment verification failed.");
  return body;
}

export async function createPaypalOrder(planId) {
  const token = localStorage.getItem("shadowfix.token") || "";
  const res = await fetch("/api/billing/paypal/create-order", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Token": token,
    },
    body: JSON.stringify({ plan: planId }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "Failed to create PayPal order.");
  return body;
}

export async function capturePaypalOrder(captureData) {
  const token = localStorage.getItem("shadowfix.token") || "";
  const res = await fetch("/api/billing/paypal/capture-order", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Token": token,
    },
    body: JSON.stringify(captureData),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "PayPal capture failed.");
  return body;
}

export async function refundInvoice(invoiceId, reason = "") {
  const token = localStorage.getItem("shadowfix.token") || "";
  const res = await fetch("/api/billing/refund", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Token": token,
    },
    body: JSON.stringify({ invoice_id: invoiceId, reason }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "Refund failed.");
  return body;
}

// ── Chaos & Load Testing APIs (Locust, Toxiproxy, JMeter) ──
export async function runChaosTest(params) {
  const token = localStorage.getItem("shadowfix.token") || "";
  const res = await fetch("/api/testing/chaos/run", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Token": token,
    },
    body: JSON.stringify(params),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "Chaos test failed.");
  return body;
}

// ── Figma Visual UI Testing & Auto-Repair APIs ──
export async function auditFigmaUI(params) {
  const token = localStorage.getItem("shadowfix.token") || "";
  const res = await fetch("/api/testing/figma/audit", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Token": token,
    },
    body: JSON.stringify(params),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "Figma UI audit failed.");
  return body;
}

export async function fixFigmaBugs(params) {
  const token = localStorage.getItem("shadowfix.token") || "";
  const res = await fetch("/api/testing/figma/fix-bugs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Token": token,
    },
    body: JSON.stringify(params),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || "Figma auto-fix failed.");
  return body;
}

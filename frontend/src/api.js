export async function runDemo() {
  const response = await fetch("/api/demo/run", { method: "POST" });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function getIncident(id) {
  const response = await fetch(`/api/incidents/${id}`);
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

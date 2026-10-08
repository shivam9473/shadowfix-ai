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
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Key": adminKey,
      ...(options.headers || {}),
    },
  });
  const text = await response.text();
  const body = text ? JSON.parse(text) : {};
  if (!response.ok) throw new Error(body.detail || text);
  return body;
}

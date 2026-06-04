const API_BASE = "http://localhost:8000/api/v1";

export async function fetchPods() {
  const res = await fetch(`${API_BASE}/demo/pods`);
  return res.json();
}

export async function scaleService(service: string, replicas: number) {
  const res = await fetch(`${API_BASE}/demo/scale`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ service, replicas })
  });
  return res.json();
}

export async function startLoadTest(target_rps: number) {
  const res = await fetch(`${API_BASE}/demo/loadtest/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_rps })
  });
  return res.json();
}

export async function stopLoadTest() {
  const res = await fetch(`${API_BASE}/demo/loadtest/stop`, {
    method: "POST"
  });
  return res.json();
}

export async function calculateSalary(payload: any) {
  const res = await fetch(`${API_BASE}/salary/calculate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return res.json();
}

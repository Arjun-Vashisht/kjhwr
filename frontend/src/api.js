// Small fetch wrapper. In production the API is on the same origin.
const BASE = import.meta.env.VITE_API_URL || "";

export async function get(path, params = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null)
  ).toString();
  const res = await fetch(`${BASE}/api/${path}${qs ? `?${qs}` : ""}`);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* body wasn't json */
    }
    throw new Error(detail);
  }
  return res.json();
}

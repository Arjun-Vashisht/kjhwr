const UK = "Europe/London";

export const mw = (v) => (v == null ? "–" : `${Math.round(v).toLocaleString("en-GB")} MW`);

export const gwh = (mwh) =>
  mwh == null ? "–" : `${(mwh / 1000).toLocaleString("en-GB", { maximumFractionDigits: 0 })} GWh`;

export const pct = (v) => (v == null ? "–" : `${(v * 100).toFixed(1)}%`);

export const signedMw = (v) =>
  v == null ? "–" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(Math.round(v)).toLocaleString("en-GB")} MW`;

export const clock = (iso) =>
  new Date(iso).toLocaleTimeString("en-GB", { timeZone: UK, hour: "2-digit", minute: "2-digit" });

export const dayLabel = (isoDate) =>
  new Date(`${isoDate}T12:00:00Z`).toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });

export const stamp = (iso) =>
  new Date(iso).toLocaleString("en-GB", {
    timeZone: UK,
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });

export const shortDate = (iso) =>
  new Date(iso).toLocaleDateString("en-GB", { timeZone: UK, day: "numeric", month: "short" });

export function addDays(isoDate, n) {
  const d = new Date(`${isoDate}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

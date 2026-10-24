import { useEffect, useState } from "react";
import { get } from "./api";
import DecisionView from "./components/DecisionView";
import AccuracyView from "./components/AccuracyView";

const TABS = [
  { id: "day", label: "Day-ahead view" },
  { id: "accuracy", label: "Forecast accuracy" },
];

export default function App() {
  const [tab, setTab] = useState("day");
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    get("meta").then(setMeta).catch((e) => setError(e.message));
  }, []);

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden>
            <svg viewBox="0 0 24 24" width="22" height="22">
              <path d="M3 8h11a3 3 0 1 0-3-3M3 12h15a3 3 0 1 1-3 3M3 16h8" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </span>
          <span>Windcast</span>
        </div>
        <nav className="tabs" role="tablist">
          {TABS.map((t) => (
            <button
              key={t.id}
              role="tab"
              aria-selected={tab === t.id}
              className={tab === t.id ? "tab active" : "tab"}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="page">
        {error && (
          <p className="notice">
            Couldn’t load data: {error}. Check the API is running and the January 2026 snapshot exists.
          </p>
        )}
        {!meta && !error && <p className="muted">Loading January 2026 data…</p>}
        {meta && tab === "day" && <DecisionView meta={meta} />}
        {meta && tab === "accuracy" && <AccuracyView meta={meta} />}
      </main>

      <footer className="foot">
        Data: Elexon BMRS – FUELHH (wind outturn) and WINDFOR (wind forecast), national level. Times are UK local.
      </footer>
    </div>
  );
}

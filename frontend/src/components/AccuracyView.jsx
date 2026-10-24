import { useEffect, useState } from "react";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { get } from "../api";
import { gwh, mw, pct, shortDate, signedMw, stamp } from "../format";

const BLUE = "#2563a8";
const INK = "#1d2b36";
const AMBER = "#b7791f";
const GRID = "#d5dde3";
const AXIS = { stroke: "#6b7c88", fontSize: 12 };
const gw = (v) => `${(v / 1000).toFixed(0)} GW`;

export default function AccuracyView({ meta }) {
  const [mode, setMode] = useState("gate");
  const [gate, setGate] = useState(meta.default_gate);
  const [hIndex, setHIndex] = useState(meta.horizons.indexOf(24));
  const [data, setData] = useState(null);
  const [curve, setCurve] = useState(null);
  const [error, setError] = useState(null);

  const horizon = meta.horizons[hIndex];

  useEffect(() => {
    get("horizons").then(setCurve).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    setError(null);
    const params = mode === "gate" ? { gate } : { horizon };
    get("accuracy", params)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [mode, gate, horizon]);

  const m = data?.metrics;
  const leadForMarker = mode === "gate" ? m?.mean_lead_hours : horizon;

  return (
    <section>
      <div className="controls">
        <div className="segmented" role="radiogroup" aria-label="How to pick the forecast">
          <button role="radio" aria-checked={mode === "gate"} className={mode === "gate" ? "on" : ""} onClick={() => setMode("gate")}>
            As seen at the auction
          </button>
          <button role="radio" aria-checked={mode === "lead"} className={mode === "lead" ? "on" : ""} onClick={() => setMode("lead")}>
            At a fixed lead time
          </button>
        </div>

        {mode === "gate" ? (
          <label className="field">
            Auction
            <select value={gate} onChange={(e) => setGate(e.target.value)}>
              {meta.gates.map((g) => (
                <option key={g.time} value={g.time}>
                  {g.label}, closes {g.time}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <label className="field slider">
            Forecast issued at least <strong>{horizon} h</strong> ahead
            <input
              type="range"
              min={0}
              max={meta.horizons.length - 1}
              value={hIndex}
              onChange={(e) => setHIndex(Number(e.target.value))}
            />
          </label>
        )}
      </div>

      {error && <p className="notice">{error}</p>}

      {m && m.n > 0 && (
        <div className="answer">
          <p className="answer-line">
            Across the month the forecast was off by <strong>{mw(m.mae)}</strong> per half hour on average, about{" "}
            {pct(m.nmae)} of typical wind output.
          </p>
          <p className="muted">
            It {m.bias > 0 ? "over-forecast" : "under-forecast"} by {mw(Math.abs(m.bias))} on average. Eight half-hours
            in ten, the forecast was between {mw(Math.abs(m.p10))} {m.p10 < 0 ? "too low" : "too high"} and{" "}
            {mw(Math.abs(m.p90))} {m.p90 < 0 ? "too low" : "too high"}. Typical lead time{" "}
            {m.mean_lead_hours.toFixed(1)} h.
          </p>
        </div>
      )}

      {m && m.n > 0 && (
        <dl className="facts">
          <div>
            <dt>Mean absolute error</dt>
            <dd>{mw(m.mae)}</dd>
          </div>
          <div>
            <dt>Root mean square error</dt>
            <dd>{mw(m.rmse)}</dd>
          </div>
          <div>
            <dt>Bias (forecast − actual)</dt>
            <dd>{signedMw(m.bias)}</dd>
          </div>
          <div>
            <dt>95% of misses smaller than</dt>
            <dd>{mw(m.p95_abs)}</dd>
          </div>
          <div>
            <dt>Points compared</dt>
            <dd>{m.n.toLocaleString("en-GB")}</dd>
          </div>
        </dl>
      )}

      {curve && (
        <Panel
          title="Error grows the further ahead you look"
          note="Mean absolute error and the 10–90% error spread, for forecasts issued at least this many hours before delivery. The marker shows the current selection."
        >
          <HorizonChart rows={curve} marker={leadForMarker} />
        </Panel>
      )}

      {data && data.series.length > 0 && (
        <>
          <Panel title="Forecast against actual, whole month">
            <SeriesChart series={data.series} />
          </Panel>

          <div className="two-up">
            <Panel title="How big the misses were" note="Forecast minus actual. Right of zero means less wind came than forecast.">
              <Histogram bins={data.histogram} />
            </Panel>
            <Panel title="Misses by time of day" note="Average size of the miss and its direction, by UK hour.">
              <ByHour rows={data.by_hour} />
            </Panel>
          </div>

          <Panel title="Daily wind energy" note="Total per delivery day. This is what the day-ahead volume actually rests on.">
            <Daily rows={data.daily} />
          </Panel>
        </>
      )}
    </section>
  );
}

function Panel({ title, note, children }) {
  return (
    <div className="panel">
      <h2>{title}</h2>
      {note && <p className="muted small">{note}</p>}
      {children}
    </div>
  );
}

function HorizonChart({ rows, marker }) {
  const data = rows.map((r) => ({ ...r, spread: [r.p10, r.p90] }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={data} margin={{ top: 10, right: 16, bottom: 0, left: 8 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="horizon" type="number" domain={[0, "dataMax"]} ticks={[0, 6, 12, 24, 36, 48]} unit=" h" {...AXIS} />
        <YAxis width={64} tickFormatter={(v) => `${Math.round(v / 100) / 10} GW`} {...AXIS} />
        <Tooltip formatter={(v, name) => (Array.isArray(v) ? `${mw(v[0])} to ${mw(v[1])}` : mw(v))} labelFormatter={(h) => `${h} h ahead`} />
        <Legend iconType="plainline" wrapperStyle={{ fontSize: 13 }} />
        <ReferenceLine y={0} stroke="#9aa9b4" />
        <Area dataKey="spread" name="10–90% error spread" legendType="square" fill={BLUE} fillOpacity={0.12} stroke="none" isAnimationActive={false} />
        <Line dataKey="mae" name="Mean absolute error" stroke={BLUE} strokeWidth={2.25} dot={{ r: 2.5 }} isAnimationActive={false} />
        <Line dataKey="bias" name="Bias" stroke={AMBER} strokeWidth={1.5} dot={false} isAnimationActive={false} />
        {marker != null && <ReferenceLine x={marker} stroke={INK} strokeDasharray="3 3" />}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

function SeriesChart({ series }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={series} margin={{ top: 10, right: 16, bottom: 0, left: 8 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="time" tickFormatter={shortDate} minTickGap={50} {...AXIS} />
        <YAxis width={64} tickFormatter={gw} {...AXIS} />
        <Tooltip formatter={(v) => mw(v)} labelFormatter={stamp} />
        <Legend iconType="plainline" wrapperStyle={{ fontSize: 13 }} />
        <Line dataKey="actual" name="Actual" stroke={INK} strokeWidth={1.25} dot={false} isAnimationActive={false} />
        <Line dataKey="forecast" name="Forecast" stroke={BLUE} strokeWidth={1.25} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function Histogram({ bins }) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={bins} margin={{ top: 10, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="from" tickFormatter={(v) => `${v / 1000} GW`} minTickGap={24} {...AXIS} />
        <YAxis width={40} {...AXIS} />
        <Tooltip formatter={(v) => [v, "half-hours"]} labelFormatter={(_, p) => (p?.[0] ? `${signedMw(p[0].payload.from)} to ${signedMw(p[0].payload.to)}` : "")} />
        <Bar dataKey="count" isAnimationActive={false}>
          {bins.map((b) => (
            <Cell key={b.from} fill={b.from >= 0 ? AMBER : BLUE} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function ByHour({ rows }) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <ComposedChart data={rows} margin={{ top: 10, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="hour" tickFormatter={(h) => `${String(h).padStart(2, "0")}:00`} minTickGap={16} {...AXIS} />
        <YAxis width={56} tickFormatter={(v) => `${(v / 1000).toFixed(1)} GW`} {...AXIS} />
        <Tooltip formatter={(v) => mw(v)} labelFormatter={(h) => `${String(h).padStart(2, "0")}:00`} />
        <ReferenceLine y={0} stroke="#9aa9b4" />
        <Bar dataKey="mae" name="Average miss" fill={BLUE} fillOpacity={0.75} isAnimationActive={false} />
        <Line dataKey="bias" name="Bias" stroke={AMBER} strokeWidth={2} dot={false} isAnimationActive={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

function Daily({ rows }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={rows} margin={{ top: 10, right: 16, bottom: 0, left: 8 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="day" tickFormatter={(d) => d.slice(8)} {...AXIS} />
        <YAxis width={64} tickFormatter={(v) => `${Math.round(v / 1000)} GWh`} {...AXIS} />
        <Tooltip formatter={(v) => gwh(v)} />
        <Legend wrapperStyle={{ fontSize: 13 }} />
        <Bar dataKey="forecast_mwh" name="Forecast" fill={BLUE} isAnimationActive={false} />
        <Bar dataKey="actual_mwh" name="Actual" fill={INK} fillOpacity={0.7} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}

import { useEffect, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { get } from "../api";
import { addDays, clock, dayLabel, gwh, mw, signedMw, stamp } from "../format";

const COLORS = { forecast: "#2563a8", actual: "#1d2b36", band: "#2563a8" };

export default function DecisionView({ meta }) {
  // start on the middle of the month, more interesting than 2 Jan
  const [day, setDay] = useState("2026-01-15");
  const [gate, setGate] = useState(meta.default_gate);
  const [showActual, setShowActual] = useState(true);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setError(null);
    get("decision", { day, gate })
      .then(setData)
      .catch((e) => setError(e.message));
  }, [day, gate]);

  const first = meta.first_delivery_day;
  const last = meta.last_delivery_day;
  const gateInfo = meta.gates.find((g) => g.time === gate);

  return (
    <section>
      <div className="controls">
        <div className="daypicker">
          <button onClick={() => setDay(addDays(day, -1))} disabled={day <= first} aria-label="Previous day">
            ‹
          </button>
          <input
            type="date"
            value={day}
            min={first}
            max={last}
            onChange={(e) => e.target.value && setDay(e.target.value)}
            aria-label="Delivery day"
          />
          <button onClick={() => setDay(addDays(day, 1))} disabled={day >= last} aria-label="Next day">
            ›
          </button>
        </div>

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

        <label className="check">
          <input type="checkbox" checked={showActual} onChange={(e) => setShowActual(e.target.checked)} />
          Show what actually happened
        </label>
      </div>

      {error && <p className="notice">{error}</p>}
      {data && <DayBody data={data} gateInfo={gateInfo} showActual={showActual} />}
    </section>
  );
}

function DayBody({ data, gateInfo, showActual }) {
  const { energy, metrics, band } = data;

  if (!data.forecast_published) {
    return <p className="notice">No forecast was published before this gate for {dayLabel(data.day)}.</p>;
  }

  const miss = energy ? energy.forecast_mwh - energy.actual_mwh : null;
  const inRange = energy && energy.actual_mwh >= energy.range_mwh[0] && energy.actual_mwh <= energy.range_mwh[1];

  return (
    <>
      <div className="answer">
        <p className="answer-line">
          The forecast says <strong>{gwh(energy?.forecast_mwh)}</strong> of wind on {dayLabel(data.day)}. Going by
          how it has missed this month, expect between {gwh(energy?.range_mwh[0])} and {gwh(energy?.range_mwh[1])}.
        </p>
        <p className="muted">
          From the forecast published {stamp(data.forecast_published)}, the latest one available before the{" "}
          {gateInfo?.label} gate at {clock(data.gate_utc)} the day before. Delivery runs 23:00 to 23:00.
        </p>
      </div>

      <div className="chart-wrap">
        <ResponsiveContainer width="100%" height={340}>
          <ComposedChart data={data.series} margin={{ top: 10, right: 16, bottom: 0, left: 8 }}>
            <CartesianGrid stroke="#d5dde3" vertical={false} />
            <XAxis dataKey="time" tickFormatter={clock} minTickGap={40} stroke="#6b7c88" fontSize={12} />
            <YAxis
              stroke="#6b7c88"
              fontSize={12}
              width={64}
              tickFormatter={(v) => `${(v / 1000).toFixed(0)} GW`}
            />
            <Tooltip content={<DayTooltip showActual={showActual} />} />
            <Legend iconType="plainline" wrapperStyle={{ fontSize: 13 }} />
            <Area
              dataKey={(d) => (d.low == null ? null : [d.low, d.high])}
              name="Likely range (10–90%)"
              legendType="square"
              stroke="none"
              fill={COLORS.band}
              fillOpacity={0.14}
              connectNulls
              isAnimationActive={false}
            />
            <Line
              dataKey="forecast"
              name="Forecast at gate"
              stroke={COLORS.forecast}
              strokeWidth={2.25}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
            {showActual && (
              <Line
                dataKey="actual"
                name="Actual"
                stroke={COLORS.actual}
                strokeWidth={1.5}
                strokeDasharray="4 3"
                dot={false}
                connectNulls
                isAnimationActive={false}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {showActual && energy && (
        <div className="outcome">
          <h2>How it turned out</h2>
          <dl className="facts">
            <div>
              <dt>Actual wind energy</dt>
              <dd>{gwh(energy.actual_mwh)}</dd>
            </div>
            <div>
              <dt>Forecast miss for the day</dt>
              <dd className={miss > 0 ? "warn" : ""}>
                {miss > 0 ? "over by " : "under by "}
                {gwh(Math.abs(miss))}
              </dd>
            </div>
            <div>
              <dt>Average half-hour miss</dt>
              <dd>{mw(metrics.mae)}</dd>
            </div>
            <div>
              <dt>Worst half-hour miss</dt>
              <dd>{mw(metrics.max_abs)}</dd>
            </div>
          </dl>
          <p className="muted small">
            {inRange
              ? "The actual total landed inside the likely range."
              : "The actual total fell outside the likely range, roughly 1 day in 5 should."}{" "}
            {miss > 0
              ? "Less wind came than forecast, so a desk buying on this forecast would have been short."
              : "More wind came than forecast, so a desk buying on this forecast would have been long."}{" "}
            The range comes from how wrong this same forecast was on the other {band.other_days} days in the month.
          </p>
        </div>
      )}
    </>
  );
}

function DayTooltip({ active, payload, showActual }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="tip">
      <div className="tip-time">{clock(p.time)}</div>
      {p.forecast != null && <div>Forecast {mw(p.forecast)}</div>}
      {p.low != null && (
        <div className="muted">
          Range {mw(p.low)} – {mw(p.high)}
        </div>
      )}
      {showActual && p.actual != null && <div>Actual {mw(p.actual)}</div>}
      {showActual && p.actual != null && p.forecast != null && (
        <div className="muted">Miss {signedMw(p.forecast - p.actual)}</div>
      )}
    </div>
  );
}

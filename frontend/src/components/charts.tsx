import { useLayoutEffect, useRef, useState, type ReactNode } from "react";

import { formatCompact, formatInt, formatNumber } from "../lib/format";
import { niceTicks } from "../lib/scale";

/** One value of a single-series chart. */
export interface Datum {
  key: string | number;
  /** Axis label (short). */
  label: string;
  /** Tooltip / table label (long); defaults to `label`. */
  name?: string;
  value: number;
  /** Second line of the tooltip. */
  detail?: string;
}

/** Width of an element, kept up to date with a ResizeObserver. */
function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, width] as const;
}

interface TipState {
  x: number;
  y: number;
  datum: Datum;
}

function Tooltip({ tip, unit }: { tip: TipState | null; unit: string }) {
  if (!tip) return null;
  // Value leads, label follows; text goes in as React text nodes (never HTML)
  return (
    <div className="tooltip" style={{ left: tip.x, top: tip.y }} role="status">
      <strong>
        {formatInt(tip.datum.value)} {unit}
      </strong>
      <span>{tip.datum.name ?? tip.datum.label}</span>
      {tip.datum.detail && <span>{tip.datum.detail}</span>}
    </div>
  );
}

const MARGIN = { top: 20, right: 8, bottom: 26, left: 44 };

/** Path of a column with a 4px rounded top and a square base on the baseline. */
function columnPath(x: number, y: number, width: number, height: number): string {
  const r = Math.min(4, width / 2, height);
  return [
    `M${x},${y + height}`,
    `V${y + r}`,
    `Q${x},${y} ${x + r},${y}`,
    `H${x + width - r}`,
    `Q${x + width},${y} ${x + width},${y + r}`,
    `V${y + height}`,
    "Z",
  ].join(" ");
}

function YAxis({ ticks, y, width }: { ticks: number[]; y: (v: number) => number; width: number }) {
  return (
    <g>
      {ticks.map((t) => (
        <g key={t}>
          <line
            className={t === 0 ? "baseline" : "gridline"}
            x1={MARGIN.left}
            x2={width - MARGIN.right}
            y1={y(t)}
            y2={y(t)}
          />
          <text x={MARGIN.left - 8} y={y(t)} dy="0.32em" textAnchor="end">
            {formatCompact(t)}
          </text>
        </g>
      ))}
    </g>
  );
}

interface ColumnChartProps {
  data: Datum[];
  height?: number;
  unit?: string;
  /** Show the axis label of every n-th column (hours: every 3rd). */
  labelEvery?: number;
  ariaLabel: string;
}

/** Vertical columns: one per category, ordered by the category (hour, weekday, month). */
export function ColumnChart({
  data,
  height = 220,
  unit = "incendios",
  labelEvery = 1,
  ariaLabel,
}: ColumnChartProps) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);

  const max = Math.max(...data.map((d) => d.value), 0);
  const ticks = niceTicks(max);
  const top = ticks.at(-1) || 1; // || not ??: an empty chart has a top tick of 0
  const plotH = height - MARGIN.top - MARGIN.bottom;
  const plotW = Math.max(0, width - MARGIN.left - MARGIN.right);
  const band = data.length ? plotW / data.length : 0;
  const barW = Math.max(2, Math.min(24, band - 2)); // <= 24px, >= 2px surface gap
  const y = (v: number) => MARGIN.top + plotH - (v / top) * plotH;
  const peak = data.reduce((best, d, i) => (d.value > data[best].value ? i : best), 0);

  const show = (i: number | null) => setActive(i);
  const tip: TipState | null =
    active === null || !data[active]
      ? null
      : {
          x: MARGIN.left + band * active + band / 2,
          y: y(data[active].value),
          datum: data[active],
        };

  return (
    <div ref={ref} className={`chart${active !== null ? " has-active" : ""}`}>
      {width > 0 && data.length > 0 && (
        <svg width={width} height={height} role="img" aria-label={ariaLabel}>
          <YAxis ticks={ticks} y={y} width={width} />
          {data.map((d, i) => {
            const x = MARGIN.left + band * i + (band - barW) / 2;
            const h = Math.max(0, MARGIN.top + plotH - y(d.value));
            return (
              <g key={d.key}>
                <path
                  className={`bar${active === i ? " active" : ""}`}
                  d={columnPath(x, y(d.value), barW, h)}
                />
                {i % labelEvery === 0 && (
                  <text x={x + barW / 2} y={height - 8} textAnchor="middle">
                    {d.label}
                  </text>
                )}
                {/* The whole band is the hit target, not just the painted column */}
                <rect
                  className="hit"
                  x={MARGIN.left + band * i}
                  y={MARGIN.top}
                  width={band}
                  height={plotH}
                  tabIndex={0}
                  aria-label={`${d.name ?? d.label}: ${formatInt(d.value)} ${unit}`}
                  onPointerEnter={() => show(i)}
                  onPointerLeave={() => show(null)}
                  onFocus={() => show(i)}
                  onBlur={() => show(null)}
                />
              </g>
            );
          })}
          {/* One selective direct label: the peak */}
          {data[peak] && (
            <text
              className="value-label"
              x={MARGIN.left + band * peak + band / 2}
              y={y(data[peak].value) - 6}
              textAnchor="middle"
            >
              {formatCompact(data[peak].value)}
            </text>
          )}
        </svg>
      )}
      <Tooltip tip={tip} unit={unit} />
    </div>
  );
}

interface LineChartProps {
  data: Datum[];
  height?: number;
  unit?: string;
  labelEvery?: number;
  ariaLabel: string;
}

/** Line over an ordered axis (years), with a crosshair that snaps to the nearest point. */
export function LineChart({
  data,
  height = 220,
  unit = "incendios",
  labelEvery = 1,
  ariaLabel,
}: LineChartProps) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);

  const max = Math.max(...data.map((d) => d.value), 0);
  const ticks = niceTicks(max);
  const top = ticks.at(-1) || 1; // || not ??: an empty chart has a top tick of 0
  const plotH = height - MARGIN.top - MARGIN.bottom;
  const plotW = Math.max(0, width - MARGIN.left - MARGIN.right - 12);
  const step = data.length > 1 ? plotW / (data.length - 1) : 0;
  const x = (i: number) => MARGIN.left + 6 + step * i;
  const y = (v: number) => MARGIN.top + plotH - (v / top) * plotH;
  const points = data.map((d, i) => `${x(i)},${y(d.value)}`);
  const baseY = y(0);
  const peak = data.reduce((best, d, i) => (d.value > data[best].value ? i : best), 0);
  const last = data.length - 1;

  const nearest = (clientX: number, element: SVGSVGElement) => {
    const left = element.getBoundingClientRect().left;
    const i = Math.round((clientX - left - x(0)) / (step || 1));
    return Math.max(0, Math.min(last, i));
  };

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "ArrowRight") setActive((a) => Math.min(last, (a ?? -1) + 1));
    if (event.key === "ArrowLeft") setActive((a) => Math.max(0, (a ?? 1) - 1));
  };

  const tip: TipState | null =
    active === null || !data[active]
      ? null
      : { x: x(active), y: y(data[active].value), datum: data[active] };

  return (
    <div ref={ref} className="chart">
      {width > 0 && data.length > 1 && (
        <svg
          width={width}
          height={height}
          role="img"
          aria-label={`${ariaLabel}. Use las flechas para recorrer los valores.`}
          tabIndex={0}
          onKeyDown={onKeyDown}
          onFocus={() => setActive((a) => a ?? last)}
          onBlur={() => setActive(null)}
          onPointerMove={(e) => setActive(nearest(e.clientX, e.currentTarget))}
          onPointerLeave={() => setActive(null)}
        >
          <YAxis ticks={ticks} y={y} width={width} />
          <polygon
            className="area"
            points={`${x(0)},${baseY} ${points.join(" ")} ${x(last)},${baseY}`}
          />
          <polyline className="line" points={points.join(" ")} />
          {data.map(
            (d, i) =>
              i % labelEvery === 0 && (
                <text key={d.key} x={x(i)} y={height - 8} textAnchor="middle">
                  {d.label}
                </text>
              ),
          )}
          {active !== null && (
            <line
              className="crosshair"
              x1={x(active)}
              x2={x(active)}
              y1={MARGIN.top}
              y2={baseY}
            />
          )}
          {/* Direct labels only on the peak and the last value */}
          {[...new Set([peak, last])].map((i) => (
            <g key={i}>
              <circle className="dot" cx={x(i)} cy={y(data[i].value)} r={4} />
              <text
                className="value-label"
                x={x(i)}
                y={y(data[i].value) - 10}
                textAnchor={i === last ? "end" : "middle"}
              >
                {formatCompact(data[i].value)}
              </text>
            </g>
          ))}
          {active !== null && (
            <circle className="dot" cx={x(active)} cy={y(data[active].value)} r={5} />
          )}
        </svg>
      )}
      <Tooltip tip={tip} unit={unit} />
    </div>
  );
}

/** Horizontal bars, sorted by value: rankings with long category names (states, causes). */
export function BarList({ data, unit = "incendios" }: { data: Datum[]; unit?: string }) {
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div className="bars" role="list">
      {data.map((d) => (
        <div
          key={d.key}
          className="bar-row"
          role="listitem"
          tabIndex={0}
          title={d.detail ? `${d.name ?? d.label} · ${d.detail}` : (d.name ?? d.label)}
        >
          <span className="bar-label">{d.label}</span>
          <span className="bar-track">
            <span className="bar-fill" style={{ width: `${(d.value / max) * 85}%` }} />
            <span className="bar-value">{formatCompact(d.value)}</span>
          </span>
          <span className="sr-only">
            {formatInt(d.value)} {unit}
          </span>
        </div>
      ))}
    </div>
  );
}

/** Table view of a chart: every value reachable without hovering. */
export function DataTable({ data, unit }: { data: Datum[]; unit: string }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th scope="col">Grupo</th>
            <th scope="col" className="num">
              {unit[0].toUpperCase() + unit.slice(1)}
            </th>
            <th scope="col">Detalle</th>
          </tr>
        </thead>
        <tbody>
          {data.map((d) => (
            <tr key={d.key}>
              <td>{d.name ?? d.label}</td>
              <td className="num">{formatInt(d.value)}</td>
              <td>{d.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface ChartCardProps {
  title: string;
  subtitle: string;
  data: Datum[];
  unit?: string;
  children: ReactNode;
}

/** Card with a chart and a switch to its table view. */
export function ChartCard({ title, subtitle, data, unit = "incendios", children }: ChartCardProps) {
  const [view, setView] = useState<"chart" | "table">("chart");
  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h3 className="card-title">{title}</h3>
          <p className="card-subtitle">{subtitle}</p>
        </div>
        <div className="segmented small" role="group" aria-label={`Vista de ${title}`}>
          <button aria-pressed={view === "chart"} onClick={() => setView("chart")}>
            Gráfico
          </button>
          <button aria-pressed={view === "table"} onClick={() => setView("table")}>
            Tabla
          </button>
        </div>
      </div>
      {view === "chart" ? children : <DataTable data={data} unit={unit} />}
    </section>
  );
}

/** "12,3 M acres · media 83,9" for the second tooltip line. */
export function acresDetail(acres: number, avg: number): string {
  return `${formatCompact(acres)} acres · media ${formatNumber(avg)} acres`;
}

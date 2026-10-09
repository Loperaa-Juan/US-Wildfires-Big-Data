import { CircleAlert, CircleCheck, Flame, LoaderCircle, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

import { acresDetail, BarList, ChartCard, ColumnChart, LineChart, type Datum } from "./components/charts";
import { HotspotTable } from "./components/HotspotTable";
import { MapPanel, type Focus } from "./components/MapPanel";
import { api } from "./lib/api";
import {
  causeLabel,
  formatCompact,
  formatHour,
  formatInt,
  monthLabel,
  weekdayLabel,
} from "./lib/format";
import type { Cells, Health, StatRow, TableStat } from "./lib/types";
import { useTheme } from "./theme";

type Stats = Record<TableStat, StatRow[]>;

interface Data {
  health: Health | null;
  stats: Partial<Stats>;
  grid: Cells | null;
  hotspots: Cells | null;
  failed: string[];
  loading: boolean;
}

const TABLE_STATS: TableStat[] = ["hour", "weekday", "month", "year", "state", "cause"];

/** Everything the dashboard shows comes from the API once, on load. */
function useDashboardData(): Data {
  const [data, setData] = useState<Data>({
    health: null,
    stats: {},
    grid: null,
    hotspots: null,
    failed: [],
    loading: true,
  });

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    // allSettled: one failing result (e.g. Spark has not run yet) must not blank the rest
    Promise.allSettled([
      api.health(signal),
      api.cells("grid", signal),
      api.cells("hotspots", signal),
      ...TABLE_STATS.map((name) => api.stats(name, signal)),
    ]).then((results) => {
      if (signal.aborted) return;
      const [health, grid, hotspots, ...tables] = results;
      const value = <T,>(r: PromiseSettledResult<T>) => (r.status === "fulfilled" ? r.value : null);
      const stats: Partial<Stats> = {};
      const failed: string[] = [];
      tables.forEach((r, i) => {
        const v = value(r);
        if (v && "results" in v) stats[TABLE_STATS[i]] = v.results;
        else failed.push(`/stats/${TABLE_STATS[i]}`);
      });
      if (health.status === "rejected") failed.unshift("/health");
      if (grid.status === "rejected") failed.push("/stats/grid");
      if (hotspots.status === "rejected") failed.push("/stats/hotspots");
      setData({
        health: value(health) as Health | null,
        grid: value(grid) as Cells | null,
        hotspots: value(hotspots) as Cells | null,
        stats,
        failed,
        loading: false,
      });
    });
    return () => controller.abort();
  }, []);

  return data;
}

const toData = (rows: StatRow[] = [], label: (row: StatRow) => string, name = label): Datum[] =>
  rows.map((row) => ({
    key: row._id,
    label: label(row),
    name: name(row),
    value: row.fires,
    detail: acresDetail(row.acres_burned, row.avg_acres),
  }));

const byValue = (a: Datum, b: Datum) => b.value - a.value;

export default function App() {
  const { theme, toggle } = useTheme();
  const { health, stats, grid, hotspots, failed, loading } = useDashboardData();
  const [focus, setFocus] = useState<Focus | null>(null);

  const hours = toData(stats.hour, (r) => String(r._id), (r) => `${formatHour(Number(r._id))} h`);
  const weekdays = toData(stats.weekday, (r) => weekdayLabel(r.name ?? ""));
  const months = toData(stats.month, (r) => monthLabel(Number(r._id)));
  const years = toData(stats.year, (r) => String(r._id));
  const states = toData(stats.state, (r) => String(r._id)).sort(byValue);
  const causes = toData(stats.cause, (r) => causeLabel(String(r._id))).sort(byValue);

  const totalAcres = (stats.year ?? []).reduce((sum, r) => sum + r.acres_burned, 0);
  const peakHour = hours.reduce<Datum | null>((best, d) => (!best || d.value > best.value ? d : best), null);
  const peakYear = years.reduce<Datum | null>((best, d) => (!best || d.value > best.value ? d : best), null);
  const firesWithHour = hours.reduce((sum, d) => sum + d.value, 0);

  return (
    <main className="app">
      <header className="header">
        <div>
          <p className="brand">
            <Flame size={18} aria-hidden /> Big Data geoespacial · 1992–2015
          </p>
          <h1 className="hero-value">{health ? formatInt(health.fires) : "—"}</h1>
          <p className="hero-label">incendios forestales registrados en Estados Unidos</p>
        </div>
        <div className="header-actions">
          <ApiStatus loading={loading} ok={Boolean(health)} />
          <button
            className="icon-button"
            onClick={toggle}
            aria-label={theme === "dark" ? "Usar tema claro" : "Usar tema oscuro"}
            title={theme === "dark" ? "Tema claro" : "Tema oscuro"}
          >
            {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </div>
      </header>

      {failed.length > 0 && !loading && (
        <div className="message error" role="alert">
          <CircleAlert size={16} aria-hidden />
          <span>
            No se pudieron cargar: {failed.join(", ")}. Compruebe que la API está levantada y que
            la etapa de Spark terminó (<code>docker compose ps</code>).
          </span>
        </div>
      )}

      <div className="tiles">
        <Tile label="Superficie quemada" value={formatCompact(totalAcres)} note="acres, suma 1992–2015" />
        <Tile
          label="Año con más incendios"
          value={peakYear?.label ?? "—"}
          note={peakYear ? `${formatInt(peakYear.value)} incendios` : undefined}
        />
        <Tile
          label="Hora pico de detección"
          value={peakHour ? formatHour(Number(peakHour.key)) : "—"}
          note={peakHour ? `${formatInt(peakHour.value)} incendios` : undefined}
        />
        <Tile
          label="Celdas con incendios"
          value={grid ? formatInt(grid.returned) : "—"}
          note="grilla de 0,5° × 0,5°"
        />
        <Tile
          label="Hotspots"
          value={hotspots ? formatInt(hotspots.returned) : "—"}
          note="celdas con z-score ≥ 2"
        />
      </div>

      <MapPanel
        grid={grid}
        hotspots={hotspots}
        causes={causes.map((c) => String(c.key))}
        states={states.map((s) => String(s.key)).sort()}
        years={years.map((y) => Number(y.key))}
        theme={theme}
        focus={focus}
      />

      <h2 className="section-title">Cuándo ocurren · agregaciones temporales de Spark</h2>
      <div className="grid-2">
        <ChartCard
          title="Por hora de detección"
          subtitle={`Solo los ${formatCompact(firesWithHour)} incendios con hora registrada (el 47 % no la tiene)`}
          data={hours}
        >
          <ColumnChart data={hours} labelEvery={3} ariaLabel="Incendios por hora de detección" />
        </ChartCard>
        <ChartCard title="Por año" subtitle="Incendios descubiertos cada año" data={years}>
          <LineChart data={years} labelEvery={4} ariaLabel="Incendios por año, 1992 a 2015" />
        </ChartCard>
        <ChartCard title="Por mes" subtitle="Total de los 24 años por mes del año" data={months}>
          <ColumnChart data={months} ariaLabel="Incendios por mes del año" />
        </ChartCard>
        <ChartCard title="Por día de la semana" subtitle="Total de los 24 años por día" data={weekdays}>
          <ColumnChart data={weekdays} ariaLabel="Incendios por día de la semana" />
        </ChartCard>
      </div>

      <h2 className="section-title">Dónde y por qué · agregaciones espaciales de Spark</h2>
      <div className="grid-3">
        <ChartCard title="Estados con más incendios" subtitle="Los 15 primeros de 52" data={states}>
          <BarList data={states.slice(0, 15)} />
        </ChartCard>
        <ChartCard title="Causas" subtitle="Causa registrada de cada incendio" data={causes}>
          <BarList data={causes} />
        </ChartCard>
        <HotspotTable
          hotspots={hotspots}
          onSelect={(cell) => setFocus((f) => ({ cell, nonce: (f?.nonce ?? 0) + 1 }))}
        />
      </div>
    </main>
  );
}

function ApiStatus({ loading, ok }: { loading: boolean; ok: boolean }) {
  if (loading) {
    return (
      <span className="status" data-state="loading">
        <LoaderCircle size={15} aria-hidden /> Conectando con la API…
      </span>
    );
  }
  return (
    <span className="status" data-state={ok ? "ok" : "error"}>
      {ok ? <CircleCheck size={15} aria-hidden /> : <CircleAlert size={15} aria-hidden />}
      {ok ? "API y MongoDB en línea" : "API sin conexión"}
    </span>
  );
}

function Tile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="card tile">
      <p className="tile-label">{label}</p>
      <p className="tile-value">{value}</p>
      {note && <p className="tile-note">{note}</p>}
    </div>
  );
}

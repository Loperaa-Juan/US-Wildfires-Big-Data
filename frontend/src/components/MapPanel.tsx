import type { Layer, LeafletMouseEvent, Map as LeafletMap, PathOptions } from "leaflet";
import { CircleAlert, Crosshair, Eraser, Hexagon, LocateFixed, Search, Square } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  Circle,
  CircleMarker,
  GeoJSON,
  MapContainer,
  Polygon,
  Polyline,
  TileLayer,
  Tooltip,
  useMap,
  useMapEvents,
} from "react-leaflet";

import { api, ApiError, requests, type Request } from "../lib/api";
import {
  causeLabel,
  formatCompact,
  formatDate,
  formatInt,
  formatLonLat,
  formatNumber,
} from "../lib/format";
import { boundsPolygon, toLatLng, toPolygon } from "../lib/geo";
import { classify, quantileBreaks } from "../lib/scale";
import type { Cell, Cells, FireFilters, Fires, PolygonGeometry, Position } from "../lib/types";
import type { Theme } from "../theme";

type Mode = "near" | "nearest" | "within";
type CellLayer = "all" | "hotspots";

const MODES: { id: Mode; label: string; operator: string; icon: typeof Crosshair }[] = [
  { id: "near", label: "Radio", operator: "$near", icon: Crosshair },
  { id: "nearest", label: "Más cercanos", operator: "$geoNear", icon: LocateFixed },
  { id: "within", label: "Polígono", operator: "$geoWithin", icon: Hexagon },
];

const HINTS: Record<Mode, string> = {
  near: "Haga clic en el mapa: incendios dentro del radio, del más cercano al más lejano.",
  nearest: "Haga clic en el mapa: incendios más cercanos con su distancia en km.",
  within: "Haga clic para marcar los vértices del polígono y luego pulse «Consultar».",
};

// Esri's gray canvas basemaps: no API key, and muted enough for the data to stand out
const TILES: Record<Theme, string> = {
  light:
    "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
  dark: "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
};

const ATTRIBUTION = "Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors";

const RAMP_CLASSES = 5;

/** Leaflet draws on a canvas, which cannot read CSS variables: resolve them per theme. */
function themeColors(theme: Theme) {
  const css = getComputedStyle(document.documentElement);
  const get = (name: string) => css.getPropertyValue(name).trim();
  return {
    ramp: Array.from({ length: RAMP_CLASSES }, (_, i) => get(`--ramp-${i + 1}`)),
    ink: get("--ink"),
    surface: get("--surface"),
    query: get("--series-query"),
    theme,
  };
}

/** Tooltip content built with text nodes: API values never go in as HTML. */
function tipElement(title: string, lines: string[]): HTMLElement {
  const root = document.createElement("div");
  const strong = document.createElement("strong");
  strong.textContent = title;
  root.append(strong);
  for (const line of lines) {
    const span = document.createElement("span");
    span.textContent = line;
    root.append(span);
  }
  return root;
}

function cellTip(cell: Cell): HTMLElement {
  const p = cell.properties;
  const lines = [
    `${formatCompact(p.acres_burned)} acres quemados`,
    formatLonLat(p.center.coordinates),
  ];
  if (p.rank) lines.unshift(`Hotspot n.º ${p.rank} · z = ${formatNumber(p.zscore ?? 0)}`);
  return tipElement(`${formatInt(p.fires)} incendios`, lines);
}

function MapClicks({ onClick }: { onClick: (position: Position) => void }) {
  useMapEvents({
    click: (event: LeafletMouseEvent) => onClick([event.latlng.lng, event.latlng.lat]),
  });
  return null;
}

function MapReady({ onReady }: { onReady: (map: LeafletMap) => void }) {
  const map = useMap();
  useEffect(() => onReady(map), [map, onReady]);
  return null;
}

export interface Focus {
  cell: Cell;
  nonce: number; // re-focus the same cell when clicked again
}

interface MapPanelProps {
  grid: Cells | null;
  hotspots: Cells | null;
  causes: string[];
  states: string[];
  years: number[];
  theme: Theme;
  focus: Focus | null;
}

export function MapPanel({ grid, hotspots, causes, states, years, theme, focus }: MapPanelProps) {
  const [map, setMap] = useState<LeafletMap | null>(null);
  const [cellLayer, setCellLayer] = useState<CellLayer>("all");
  const [mode, setMode] = useState<Mode>("near");
  const [radiusKm, setRadiusKm] = useState(25);
  const [limit, setLimit] = useState(200);
  const [filters, setFilters] = useState<FireFilters>({});
  const [center, setCenter] = useState<Position | null>(null);
  const [vertices, setVertices] = useState<Position[]>([]);
  const [area, setArea] = useState<PolygonGeometry | null>(null);
  const [result, setResult] = useState<Fires | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Theme colors are read from the CSS once the theme attribute is applied
  const colors = useMemo(() => themeColors(theme), [theme]);

  // Class limits from the full grid, so both layers share one legend
  const breaks = useMemo(
    () => quantileBreaks(grid?.features.map((f) => f.properties.fires) ?? [], RAMP_CLASSES),
    [grid],
  );

  // The request follows the current inputs; it is null until there is a point or a polygon
  const request: Request | null = useMemo(() => {
    if (mode === "within") return area ? requests.within(area, limit, filters) : null;
    if (!center) return null;
    const [lon, lat] = center;
    const query = { lat: +lat.toFixed(4), lon: +lon.toFixed(4), radius_km: radiusKm, limit, ...filters };
    return mode === "near" ? requests.near(query) : requests.nearest(query);
  }, [mode, center, area, radiusKm, limit, filters]);

  const requestKey = request ? request.path + JSON.stringify(request.body ?? "") : "";

  // Fetching is synchronizing with an external system: an effect keyed by the request,
  // aborting the previous one so a slow response never overwrites a newer one
  useEffect(() => {
    if (!request) return;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    api
      .fires(request, controller.signal)
      .then(setResult)
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setError(e instanceof ApiError ? e.message : "No se pudo conectar con la API.");
        setResult(null);
      })
      .finally(() => !controller.signal.aborted && setLoading(false));
    return () => controller.abort();
    // requestKey identifies the request: a new object with the same content is not refetched
  }, [requestKey]);

  // Fly to a hotspot picked in the ranking table
  useEffect(() => {
    if (!map || !focus) return;
    const ring = focus.cell.geometry.coordinates[0].map(toLatLng);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    map.flyToBounds(ring, { maxZoom: 9, padding: [40, 40], animate: !reduce });
  }, [map, focus]);

  const changeMode = (next: Mode) => {
    setMode(next);
    setResult(null);
    setError(null);
    setVertices([]);
    setArea(null);
  };

  const onMapClick = (position: Position) => {
    if (mode === "within") {
      setVertices((v) => [...v, position]);
    } else {
      setCenter(position);
    }
  };

  const queryPolygon = () => setArea(toPolygon(vertices));

  const queryView = () => {
    if (!map) return;
    const b = map.getBounds();
    const polygon = boundsPolygon(b.getWest(), b.getSouth(), b.getEast(), b.getNorth());
    setVertices(polygon.coordinates[0].slice(0, -1));
    setArea(polygon);
  };

  const clear = () => {
    setCenter(null);
    setVertices([]);
    setArea(null);
    setResult(null);
    setError(null);
  };

  const setFilter = (key: keyof FireFilters, value: string) =>
    setFilters((f) => ({ ...f, [key]: value || undefined }));

  const cellStyle = (feature?: { properties: { fires: number } }): PathOptions => ({
    stroke: false,
    fillColor: colors.ramp[classify(feature?.properties.fires ?? 0, breaks)],
    fillOpacity: 0.6,
  });

  // Hotspots are drawn over the grid as an outline; alone, they also get their fill
  const hotspotStyle = (feature?: { properties: { fires: number } }): PathOptions => ({
    ...cellStyle(feature),
    fillOpacity: cellLayer === "hotspots" ? 0.6 : 0,
    stroke: true,
    color: colors.ink,
    weight: 1.5,
    opacity: 0.85,
  });

  const onEachCell = (feature: Cell, layer: Layer) => {
    layer.bindTooltip(() => cellTip(feature), { sticky: true, className: "map-tip" });
  };

  const polygonPositions = (area?.coordinates[0] ?? vertices).map(toLatLng);

  return (
    <section className="card" aria-labelledby="map-title">
      <div className="card-head">
        <div>
          <h2 className="card-title" id="map-title">
            Mapa de incendios y consultas geoespaciales
          </h2>
          <p className="card-subtitle">
            Celdas de {formatNumber(0.5)}° calculadas por Spark · consultas en vivo sobre MongoDB
            con índice <code>2dsphere</code>
          </p>
        </div>
        <div className="segmented small" role="group" aria-label="Capa de celdas">
          <button aria-pressed={cellLayer === "all"} onClick={() => setCellLayer("all")}>
            Grilla y hotspots
          </button>
          <button aria-pressed={cellLayer === "hotspots"} onClick={() => setCellLayer("hotspots")}>
            Solo hotspots
          </button>
        </div>
      </div>

      <div className="toolbar">
        <div className="segmented" role="group" aria-label="Tipo de consulta">
          {MODES.map(({ id, label, operator, icon: Icon }) => (
            <button key={id} aria-pressed={mode === id} onClick={() => changeMode(id)}>
              <Icon size={15} aria-hidden />
              {label} <code>{operator}</code>
            </button>
          ))}
        </div>
        {mode !== "within" && (
          <label className="field">
            <span>
              Radio: <output>{radiusKm} km</output>
            </span>
            <input
              type="range"
              min={1}
              max={500}
              value={radiusKm}
              onChange={(e) => setRadiusKm(Number(e.target.value))}
            />
          </label>
        )}
        <label className="field">
          Límite
          <select value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
            {[50, 200, 500, 1000].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Causa
          <select value={filters.cause ?? ""} onChange={(e) => setFilter("cause", e.target.value)}>
            <option value="">Todas</option>
            {causes.map((c) => (
              <option key={c} value={c}>
                {causeLabel(c)}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Estado
          <select value={filters.state ?? ""} onChange={(e) => setFilter("state", e.target.value)}>
            <option value="">Todos</option>
            {states.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Año
          <select value={filters.year ?? ""} onChange={(e) => setFilter("year", e.target.value)}>
            <option value="">Todos</option>
            {years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </label>
        {mode === "within" && (
          <>
            <button className="button primary" disabled={vertices.length < 3} onClick={queryPolygon}>
              <Search size={15} aria-hidden /> Consultar
            </button>
            <button className="button" disabled={!map} onClick={queryView}>
              <Square size={15} aria-hidden /> Usar vista actual
            </button>
          </>
        )}
        <button className="button" onClick={clear}>
          <Eraser size={15} aria-hidden /> Limpiar
        </button>
      </div>

      <div className="map-layout">
        <div className="map-frame" data-mode={mode}>
          <MapContainer
            center={[39, -98]}
            zoom={4}
            minZoom={3}
            preferCanvas
            worldCopyJump
            aria-label="Mapa de incendios"
          >
            <MapReady onReady={setMap} />
            <TileLayer key={theme} url={TILES[theme]} attribution={ATTRIBUTION} />
            {grid && cellLayer === "all" && (
              <GeoJSON
                // Re-created when the theme or the class limits change
                key={`grid-${theme}-${breaks.join()}`}
                data={grid}
                style={cellStyle as never}
                onEachFeature={onEachCell as never}
              />
            )}
            {hotspots && (
              <GeoJSON
                key={`hotspots-${cellLayer}-${theme}-${breaks.join()}`}
                data={hotspots}
                style={hotspotStyle as never}
                onEachFeature={onEachCell as never}
              />
            )}
            <MapClicks onClick={onMapClick} />

            {mode !== "within" && center && (
              <Circle
                center={toLatLng(center)}
                radius={radiusKm * 1000}
                pathOptions={{ color: colors.query, weight: 2, fillOpacity: 0.06 }}
                interactive={false}
              />
            )}
            {mode === "within" && polygonPositions.length > 0 && (
              area ? (
                <Polygon
                  positions={polygonPositions}
                  pathOptions={{ color: colors.query, weight: 2, fillOpacity: 0.06 }}
                  interactive={false}
                />
              ) : (
                <Polyline
                  positions={polygonPositions}
                  pathOptions={{ color: colors.query, weight: 2 }}
                  interactive={false}
                />
              )
            )}
            {mode === "within" &&
              !area &&
              vertices.map((v, i) => (
                <CircleMarker
                  key={i}
                  center={toLatLng(v)}
                  radius={4}
                  pathOptions={{ color: colors.surface, weight: 2, fillColor: colors.query, fillOpacity: 1 }}
                  interactive={false}
                />
              ))}

            {result?.features.map((fire) => (
              <CircleMarker
                key={fire.id}
                center={toLatLng(fire.geometry.coordinates)}
                radius={5}
                // 2px surface ring keeps overlapping points apart
                pathOptions={{ color: colors.surface, weight: 2, fillColor: colors.query, fillOpacity: 1 }}
              >
                <Tooltip className="map-tip">
                  <strong>{formatNumber(fire.properties.fire_size)} acres</strong>
                  <span>
                    {causeLabel(fire.properties.stat_cause_descr)} ·{" "}
                    {formatDate(fire.properties.discovery_date)}
                  </span>
                  <span>
                    {fire.properties.county ?? "Sin condado"}, {fire.properties.state}
                  </span>
                  {fire.properties.distance_km !== undefined && (
                    <span>a {formatNumber(fire.properties.distance_km)} km</span>
                  )}
                </Tooltip>
              </CircleMarker>
            ))}
          </MapContainer>

          <p className="map-hint">{HINTS[mode]}</p>

          <div className="legend" aria-label="Leyenda">
            <p className="legend-title">Incendios por celda</p>
            <div className="legend-steps">
              {colors.ramp.map((color, i) => (
                <div className="legend-step" key={color}>
                  <div className="legend-swatch" style={{ background: color }} />
                  <span>
                    {i === 0 ? `< ${formatCompact(breaks[0] ?? 0)}` : `${formatCompact(breaks[i - 1] ?? 0)}+`}
                  </span>
                </div>
              ))}
            </div>
            <div className="legend-keys">
              <span className="legend-key">
                <span className="key-outline" /> Hotspot (z ≥ 2)
              </span>
              <span className="legend-key">
                <span className="key-dot" /> Resultado de la consulta
              </span>
            </div>
          </div>
        </div>

        <Results request={request} result={result} error={error} loading={loading} />
      </div>
    </section>
  );
}

function Results({
  request,
  result,
  error,
  loading,
}: {
  request: Request | null;
  result: Fires | null;
  error: string | null;
  loading: boolean;
}) {
  const fires = result?.features ?? [];
  const acres = fires.reduce((sum, f) => sum + f.properties.fire_size, 0);
  const counts = new Map<string, number>();
  for (const f of fires) {
    counts.set(f.properties.stat_cause_descr, (counts.get(f.properties.stat_cause_descr) ?? 0) + 1);
  }
  const topCause = [...counts.entries()].sort((a, b) => b[1] - a[1])[0];
  const withDistance = fires.some((f) => f.properties.distance_km !== undefined);

  return (
    <aside className="results" aria-busy={loading} aria-live="polite">
      <h3 className="card-title">Resultado</h3>
      {request ? (
        <div className="request">
          <b>{request.method}</b> /api{request.path}
          {request.body !== undefined && (
            <>
              <br />
              {JSON.stringify(request.body).slice(0, 160)}
              {JSON.stringify(request.body).length > 160 && "…"}
            </>
          )}
        </div>
      ) : (
        <p className="empty">Elija un tipo de consulta y marque un punto o un polígono en el mapa.</p>
      )}

      {error && (
        <div className="message error" role="alert">
          <CircleAlert size={16} aria-hidden />
          <span>{error}</span>
        </div>
      )}

      {result && (
        <div className="results-body">
          <div className="results-summary">
            <div className="mini-stat">
              <p>Incendios devueltos</p>
              <strong>{formatInt(result.returned)}</strong>
              {result.total !== undefined && (
                <p>de {formatInt(result.total)} dentro del polígono</p>
              )}
            </div>
            <div className="mini-stat">
              <p>Superficie quemada</p>
              <strong>{formatCompact(acres)}</strong>
              <p>acres</p>
            </div>
            {topCause && (
              <div className="mini-stat" style={{ gridColumn: "1 / -1" }}>
                <p>Causa más frecuente</p>
                <strong>{causeLabel(topCause[0])}</strong>
                <p>{formatInt(topCause[1])} incendios</p>
              </div>
            )}
          </div>

          {fires.length === 0 ? (
            <p className="empty">Ningún incendio cumple la consulta.</p>
          ) : (
            <div className="table-wrap" style={{ marginTop: 12 }}>
              <table>
                <thead>
                  <tr>
                    <th scope="col">Fecha</th>
                    <th scope="col">Causa</th>
                    <th scope="col" className="num">
                      Acres
                    </th>
                    <th scope="col">Estado</th>
                    {withDistance && (
                      <th scope="col" className="num">
                        km
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {fires.slice(0, 200).map((f) => (
                    <tr key={f.id}>
                      <td>{formatDate(f.properties.discovery_date)}</td>
                      <td>{causeLabel(f.properties.stat_cause_descr)}</td>
                      <td className="num">{formatNumber(f.properties.fire_size)}</td>
                      <td>{f.properties.state}</td>
                      {withDistance && (
                        <td className="num">{formatNumber(f.properties.distance_km ?? 0)}</td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </aside>
  );
}

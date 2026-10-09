import { formatCompact, formatInt, formatLonLat, formatNumber } from "../lib/format";
import type { Cell, Cells } from "../lib/types";

/** Ranking of the Spark hotspots; picking a row flies the map to that cell. */
export function HotspotTable({
  hotspots,
  onSelect,
}: {
  hotspots: Cells | null;
  onSelect: (cell: Cell) => void;
}) {
  const top = [...(hotspots?.features ?? [])]
    .sort((a, b) => (a.properties.rank ?? 0) - (b.properties.rank ?? 0))
    .slice(0, 25);

  const select = (cell: Cell) => {
    onSelect(cell);
    document.getElementById("map-title")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h3 className="card-title">Ranking de hotspots</h3>
          <p className="card-subtitle">
            Celdas con más incendios que la media + 2 desviaciones. Elija una para verla en el mapa.
          </p>
        </div>
      </div>
      {top.length === 0 ? (
        <p className="empty">Sin hotspots: ¿terminó la etapa de Spark?</p>
      ) : (
        <div className="table-wrap" style={{ maxHeight: 520 }}>
          <table>
            <thead>
              <tr>
                <th scope="col" className="num">
                  #
                </th>
                <th scope="col">Centro de la celda</th>
                <th scope="col" className="num">
                  Incendios
                </th>
                <th scope="col" className="num">
                  z
                </th>
                <th scope="col" className="num">
                  Acres
                </th>
              </tr>
            </thead>
            <tbody>
              {top.map((cell) => (
                <tr
                  key={cell.id}
                  className="clickable"
                  tabIndex={0}
                  role="button"
                  aria-label={`Ver hotspot ${cell.properties.rank} en el mapa`}
                  onClick={() => select(cell)}
                  onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && select(cell)}
                >
                  <td className="num">{cell.properties.rank}</td>
                  <td>{formatLonLat(cell.properties.center.coordinates)}</td>
                  <td className="num">{formatInt(cell.properties.fires)}</td>
                  <td className="num">{formatNumber(cell.properties.zscore ?? 0)}</td>
                  <td className="num">{formatCompact(cell.properties.acres_burned)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

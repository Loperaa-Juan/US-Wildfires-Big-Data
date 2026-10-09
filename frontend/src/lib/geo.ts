import type { PolygonGeometry, Position } from "./types";

/** Clicked vertices -> GeoJSON Polygon: one ring, closed (first point repeated at the end). */
export function toPolygon(vertices: Position[]): PolygonGeometry {
  if (vertices.length < 3) throw new Error("Un polígono necesita al menos 3 vértices");
  return { type: "Polygon", coordinates: [[...vertices, vertices[0]]] };
}

/** Map view bounds -> rectangle polygon, counterclockwise like the Spark grid cells. */
export function boundsPolygon(west: number, south: number, east: number, north: number) {
  // Leaflet can report longitudes past ±180 when the world wraps; MongoDB rejects them
  const clampLon = (lon: number) => Math.max(-180, Math.min(180, lon));
  const clampLat = (lat: number) => Math.max(-90, Math.min(90, lat));
  const [w, e] = [clampLon(west), clampLon(east)];
  const [s, n] = [clampLat(south), clampLat(north)];
  return toPolygon([
    [w, s],
    [e, s],
    [e, n],
    [w, n],
  ]);
}

/** [lon, lat] -> Leaflet's [lat, lon]. */
export const toLatLng = ([lon, lat]: Position): [number, number] => [lat, lon];

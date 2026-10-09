// Shapes of the Flask API responses (src/us_wildfires_big_data/api).

export type Position = [lon: number, lat: number]; // GeoJSON order

export interface PointGeometry {
  type: "Point";
  coordinates: Position;
}

export interface PolygonGeometry {
  type: "Polygon";
  coordinates: Position[][];
}

export interface Feature<G, P> {
  type: "Feature";
  id: string | number;
  geometry: G;
  properties: P;
}

export interface FeatureCollection<G, P> {
  type: "FeatureCollection";
  returned: number;
  /** Only /fires/within: how many fires match, even past the limit. */
  total?: number;
  features: Feature<G, P>[];
}

/** A fire as stored by etl/load_mongo.py. */
export interface FireProps {
  fod_id: number;
  fire_year: number;
  stat_cause_descr: string;
  fire_size: number;
  fire_size_class: string;
  owner_descr: string;
  state: string;
  county: string | null;
  discovery_date: string;
  discovery_hour: number | null;
  /** Only /fires/nearest ($geoNear). */
  distance_km?: number;
}

/** A grid cell computed by Spark (fires_by_grid, fires_hotspots). */
export interface CellProps {
  cell_x: number;
  cell_y: number;
  fires: number;
  acres_burned: number;
  avg_acres: number;
  center: PointGeometry;
  /** Only hotspots. */
  zscore?: number;
  rank?: number;
}

export type Fire = Feature<PointGeometry, FireProps>;
export type Cell = Feature<PolygonGeometry, CellProps>;
export type Fires = FeatureCollection<PointGeometry, FireProps>;
export type Cells = FeatureCollection<PolygonGeometry, CellProps>;

/** One group of a non-spatial Spark result (/stats/hour, /stats/state, ...). */
export interface StatRow {
  _id: number | string;
  fires: number;
  acres_burned: number;
  avg_acres: number;
  /** Weekday and month names. */
  name?: string;
}

export interface StatsResponse {
  result: string;
  returned: number;
  results: StatRow[];
}

export interface Health {
  status: string;
  fires: number;
}

export type TableStat = "hour" | "weekday" | "month" | "year" | "state" | "cause";

/** Optional filters every fire query accepts. */
export interface FireFilters {
  cause?: string;
  state?: string;
  year?: string;
}

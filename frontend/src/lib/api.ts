import type {
  Cells,
  FireFilters,
  Fires,
  Health,
  PolygonGeometry,
  StatsResponse,
  TableStat,
} from "./types";

// Same-origin path: nginx (production) and the Vite dev server forward /api to the Flask API,
// so the browser never needs CORS.
const BASE = import.meta.env.VITE_API_BASE ?? "/api";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

type Params = Record<string, string | number | undefined>;

/** Query string without empty values, so optional filters are simply left out. */
export function queryString(params: Params): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

/** The request as the API sees it (without the /api prefix), shown in the UI. */
export interface Request {
  method: "GET" | "POST";
  path: string;
  body?: unknown;
}

async function send<T>(request: Request, signal?: AbortSignal): Promise<T> {
  const response = await fetch(BASE + request.path, {
    method: request.method,
    signal,
    headers: request.body ? { "Content-Type": "application/json" } : undefined,
    body: request.body ? JSON.stringify(request.body) : undefined,
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    // The API answers errors as {error, message}; e.g. a self-intersecting polygon
    throw new ApiError(body?.message ?? response.statusText, response.status);
  }
  return body as T;
}

export interface RadiusQuery extends FireFilters {
  lat: number;
  lon: number;
  radius_km: number;
  limit: number;
}

export const requests = {
  near: (q: RadiusQuery): Request => ({
    method: "GET",
    path: `/fires/near${queryString({ ...q })}`,
  }),
  nearest: ({ radius_km, ...q }: RadiusQuery): Request => ({
    method: "GET",
    // /fires/nearest calls the radius max_km
    path: `/fires/nearest${queryString({ ...q, max_km: radius_km })}`,
  }),
  within: (area: PolygonGeometry, limit: number, filters: FireFilters): Request => ({
    method: "POST",
    path: `/fires/within${queryString({ limit, ...filters })}`,
    body: area,
  }),
};

export const api = {
  health: (signal?: AbortSignal) => send<Health>({ method: "GET", path: "/health" }, signal),
  stats: (name: TableStat, signal?: AbortSignal) =>
    send<StatsResponse>({ method: "GET", path: `/stats/${name}` }, signal),
  cells: (name: "grid" | "hotspots", signal?: AbortSignal) =>
    send<Cells>({ method: "GET", path: `/stats/${name}` }, signal),
  fires: (request: Request, signal?: AbortSignal) => send<Fires>(request, signal),
};

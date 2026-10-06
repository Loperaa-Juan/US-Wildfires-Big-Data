"""Request parameters -> MongoDB queries, and MongoDB documents -> JSON. Pure functions: no
Flask and no database, so they can be tested on their own.

Invalid input raises BadRequest; the app turns it into a 400 JSON response.
"""

from datetime import datetime
from typing import Any

from werkzeug.exceptions import BadRequest

EARTH_RADIUS_KM = 6378.1
DEFAULT_LIMIT = 100
MAX_LIMIT = 1000
MAX_RADIUS_KM = 500

# Spark results (spark/analysis.py): URL name -> (collection, sort)
STATS = {
    "grid": ("fires_by_grid", [("fires", -1)]),
    "hotspots": ("fires_hotspots", [("rank", 1)]),
    "hour": ("fires_by_hour", [("_id", 1)]),
    "weekday": ("fires_by_weekday", [("_id", 1)]),
    "month": ("fires_by_month", [("_id", 1)]),
    "year": ("fires_by_year", [("_id", 1)]),
    "state": ("fires_by_state", [("fires", -1)]),
    "cause": ("fires_by_cause", [("fires", -1)]),
}
# Spark results whose documents are grid cells with a GeoJSON polygon
GEO_STATS = {"grid", "hotspots"}


# --- Parameters ----------------------------------------------------------------------------


def number(
    args: dict, name: str, low: float, high: float, default: float | None = None
) -> float:
    """Required (or `default`) float parameter within [low, high]."""
    raw = args.get(name)
    if raw is None or raw == "":
        if default is None:
            raise BadRequest(f"'{name}' is required")
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise BadRequest(f"'{name}' must be a number, got {raw!r}") from None
    if not low <= value <= high:
        raise BadRequest(
            f"'{name}' must be between {low:g} and {high:g}, got {value:g}"
        )
    return value


def limit(args: dict, maximum: int = MAX_LIMIT) -> int:
    return int(number(args, "limit", 1, maximum, DEFAULT_LIMIT))


def point(args: dict) -> dict:
    """GeoJSON Point from the `lat` and `lon` parameters."""
    lat = number(args, "lat", -90, 90)
    lon = number(args, "lon", -180, 180)
    return {"type": "Point", "coordinates": [lon, lat]}  # GeoJSON order: [lon, lat]


def polygon(body: Any) -> dict:
    """GeoJSON Polygon or MultiPolygon from a request body: a bare geometry or a Feature."""
    if not isinstance(body, dict):
        raise BadRequest("The body must be a GeoJSON Polygon, MultiPolygon or Feature")
    geometry = body.get("geometry") if body.get("type") == "Feature" else body
    if not isinstance(geometry, dict) or geometry.get("type") not in {
        "Polygon",
        "MultiPolygon",
    }:
        raise BadRequest("The geometry must be a GeoJSON Polygon or MultiPolygon")
    if not isinstance(geometry.get("coordinates"), list):
        raise BadRequest("The geometry has no 'coordinates' list")
    return {"type": geometry["type"], "coordinates": geometry["coordinates"]}


def filters(args: dict) -> dict:
    """Optional filters on the fire properties: cause, state and year."""
    query: dict = {}
    if args.get("cause"):
        query["properties.stat_cause_descr"] = args["cause"]
    if args.get("state"):
        query["properties.state"] = args["state"].upper()
    if args.get("year"):
        query["properties.fire_year"] = int(number(args, "year", 1992, 2015))
    return query


# --- Queries -------------------------------------------------------------------------------


def near_query(center: dict, radius_km: float, extra: dict) -> dict:
    """$near: fires within `radius_km` of `center`, sorted from nearest to farthest."""
    return {
        "geometry": {"$near": {"$geometry": center, "$maxDistance": radius_km * 1000}},
        **extra,
    }


def within_query(area: dict, extra: dict) -> dict:
    """$geoWithin: fires inside a polygon. Unsorted, so it can use the 2dsphere index alone."""
    return {"geometry": {"$geoWithin": {"$geometry": area}}, **extra}


def geo_near_pipeline(center: dict, max_km: float, extra: dict, n: int) -> list[dict]:
    """$geoNear aggregation: nearest fires with their distance in km (`distance_km`).

    $geoNear must be the first stage. Unlike $near it returns the distance and can be followed
    by more stages; here a $group could be added to summarize the nearest fires.
    """
    return [
        {
            "$geoNear": {
                "near": center,
                "key": "geometry",
                "distanceField": "distance_km",
                "distanceMultiplier": 0.001,  # meters -> km
                "maxDistance": max_km * 1000,
                "query": extra,
                "spherical": True,
            }
        },
        {"$limit": n},
    ]


# --- Documents -> JSON ---------------------------------------------------------------------


def _plain(value: Any) -> Any:
    """Dates as ISO strings (YYYY-MM-DD for the date-only discovery_date)."""
    if isinstance(value, datetime):
        return (
            value.date().isoformat()
            if value.time() == datetime.min.time()
            else value.isoformat()
        )
    return value


def to_feature(doc: dict) -> dict:
    """MongoDB document (fire or grid cell) -> GeoJSON Feature with its `_id` as `id`."""
    doc = dict(doc)
    geometry = doc.pop("geometry")
    feature_id = doc.pop("_id")
    doc.pop("type", None)
    properties = doc.pop("properties", {})
    properties = {k: _plain(v) for k, v in {**properties, **doc}.items()}
    return {
        "type": "Feature",
        "id": feature_id,
        "geometry": geometry,
        "properties": properties,
    }


def feature_collection(docs: list[dict], **meta: Any) -> dict:
    features = [to_feature(d) for d in docs]
    return {
        "type": "FeatureCollection",
        **meta,
        "returned": len(features),
        "features": features,
    }

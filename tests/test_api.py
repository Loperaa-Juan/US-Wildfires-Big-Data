"""Flask API. The validation tests need no database; the query tests run against a real
MongoDB (MONGO_URI, a throwaway `wildfires_test` database) and are skipped without one,
because the geospatial operators ($near, $geoWithin, $geoNear) need a real 2dsphere index."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from pymongo import GEOSPHERE, MongoClient
from pymongo.errors import PyMongoError
from werkzeug.exceptions import BadRequest

from us_wildfires_big_data.api import queries as q
from us_wildfires_big_data.api.app import create_app
from us_wildfires_big_data.config import MONGO_COLLECTION, MONGO_URI

# --- Query building (no database) ----------------------------------------------------------


def test_point_uses_geojson_lon_lat_order():
    assert q.point({"lat": "34.05", "lon": "-118.25"}) == {
        "type": "Point",
        "coordinates": [-118.25, 34.05],
    }


@pytest.mark.parametrize(
    "args",
    [
        {"lon": "0"},
        {"lat": "91", "lon": "0"},
        {"lat": "0", "lon": "-181"},
        {"lat": "x", "lon": "0"},
    ],
)
def test_point_rejects_missing_or_out_of_range(args):
    with pytest.raises(BadRequest):
        q.point(args)


def test_polygon_accepts_geometry_or_feature():
    ring = [[[0, 0], [1, 0], [1, 1], [0, 0]]]
    geometry = {"type": "Polygon", "coordinates": ring}
    assert q.polygon(geometry) == geometry
    assert (
        q.polygon({"type": "Feature", "properties": {}, "geometry": geometry})
        == geometry
    )


@pytest.mark.parametrize(
    "body", [None, [], {"type": "Point", "coordinates": [0, 0]}, {"type": "Polygon"}]
)
def test_polygon_rejects_other_input(body):
    with pytest.raises(BadRequest):
        q.polygon(body)


def test_near_query_converts_km_to_meters():
    center = {"type": "Point", "coordinates": [0, 0]}
    query = q.near_query(center, 2.5, {"properties.state": "CA"})
    assert query["geometry"]["$near"]["$maxDistance"] == 2500
    assert query["properties.state"] == "CA"


def test_filters_are_optional():
    assert q.filters({}) == {}
    assert q.filters({"cause": "Arson", "state": "ca", "year": "2005"}) == {
        "properties.stat_cause_descr": "Arson",
        "properties.state": "CA",
        "properties.fire_year": 2005,
    }


def test_to_feature_moves_id_and_formats_dates():
    doc = {
        "_id": 7,
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [1, 2]},
        "properties": {"discovery_date": datetime(2005, 2, 2, tzinfo=UTC)},
        "distance_km": 1.5,
    }
    assert q.to_feature(doc) == {
        "type": "Feature",
        "id": 7,
        "geometry": {"type": "Point", "coordinates": [1, 2]},
        "properties": {"discovery_date": "2005-02-02", "distance_km": 1.5},
    }


# --- HTTP validation (no database: requests fail before any query) ------------------------


@pytest.fixture
def offline_client():
    return create_app(db=MagicMock()).test_client()


@pytest.mark.parametrize(
    "url",
    [
        "/fires/near?lon=0",
        "/fires/near?lat=0&lon=0&radius_km=10000",
        "/fires/near?lat=0&lon=0&limit=0",
        "/fires/nearest?lat=abc&lon=0",
        "/fires/near?lat=0&lon=0&year=1800",
    ],
)
def test_bad_parameters_return_400_json(offline_client, url):
    response = offline_client.get(url)
    assert response.status_code == 400
    assert response.get_json()["error"] == "Bad Request"


def test_within_requires_a_polygon(offline_client):
    response = offline_client.post(
        "/fires/within", json={"type": "Point", "coordinates": [0, 0]}
    )
    assert response.status_code == 400


def test_unknown_stats_return_404(offline_client):
    response = offline_client.get("/stats/nope")
    assert response.status_code == 404
    assert "hotspots" in response.get_json()["message"]


# --- Queries against MongoDB ---------------------------------------------------------------

# Three fires in Los Angeles at known distances from LA_CENTER, and one in San Francisco
LA_CENTER = (34.05, -118.25)


def fire(fod_id, lon, lat, cause="Arson", year=2005):
    return {
        "_id": fod_id,
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "fod_id": fod_id,
            "fire_year": year,
            "stat_cause_descr": cause,
            "state": "CA",
            "discovery_date": datetime(year, 2, 2, tzinfo=UTC),
        },
    }


@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=1000)
    try:
        client.admin.command("ping")
    except PyMongoError:
        pytest.skip(f"No MongoDB at {MONGO_URI}")
    client.drop_database("wildfires_test")
    test_db = client["wildfires_test"]
    fires = test_db[MONGO_COLLECTION]
    fires.create_index([("geometry", GEOSPHERE)])
    fires.insert_many(
        [
            fire(1, -118.25, 34.05),  # at the center
            fire(2, -118.25, 34.10, cause="Lightning"),  # ~5.6 km north
            fire(3, -118.25, 34.20, year=2010),  # ~16.7 km north
            fire(4, -122.42, 37.77),  # San Francisco, ~550 km away
        ]
    )
    test_db["fires_by_hour"].insert_many(
        [{"_id": 13, "hour": 13, "fires": 5}, {"_id": 8, "hour": 8, "fires": 2}]
    )
    test_db["fires_hotspots"].insert_one(
        {
            "_id": "-237_68",
            "rank": 1,
            "fires": 3,
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-118.5, 34],
                        [-118, 34],
                        [-118, 34.5],
                        [-118.5, 34.5],
                        [-118.5, 34],
                    ]
                ],
            },
        }
    )
    yield test_db
    client.drop_database("wildfires_test")
    client.close()


@pytest.fixture(scope="module")
def client(db):
    return create_app(db=db).test_client()


def ids(response):
    return [f["id"] for f in response.get_json()["features"]]


def test_health(client):
    assert client.get("/health").get_json() == {"status": "ok", "fires": 4}


def test_near_returns_fires_in_radius_nearest_first(client):
    lat, lon = LA_CENTER
    assert ids(client.get(f"/fires/near?lat={lat}&lon={lon}&radius_km=10")) == [1, 2]
    assert ids(client.get(f"/fires/near?lat={lat}&lon={lon}&radius_km=20")) == [1, 2, 3]


def test_near_applies_filters_and_limit(client):
    lat, lon = LA_CENTER
    url = f"/fires/near?lat={lat}&lon={lon}&radius_km=20"
    assert ids(client.get(url + "&cause=Lightning")) == [2]
    assert ids(client.get(url + "&limit=1")) == [1]


def test_within_returns_fires_inside_polygon(client):
    los_angeles = {
        "type": "Polygon",
        "coordinates": [
            [[-118.5, 34], [-118, 34], [-118, 34.3], [-118.5, 34.3], [-118.5, 34]]
        ],
    }
    body = client.post("/fires/within", json=los_angeles).get_json()
    assert sorted(f["id"] for f in body["features"]) == [1, 2, 3]
    assert body["total"] == 3
    assert (
        client.post("/fires/within?year=2010", json=los_angeles).get_json()["total"]
        == 1
    )


def test_within_rejects_invalid_polygon_with_400(client):
    bow_tie = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]],
    }
    response = client.post("/fires/within", json=bow_tie)
    assert response.status_code == 400


def test_nearest_returns_distance_in_km(client):
    lat, lon = LA_CENTER
    features = client.get(f"/fires/nearest?lat={lat}&lon={lon}&max_km=20").get_json()[
        "features"
    ]
    assert [f["id"] for f in features] == [1, 2, 3]
    distances = [f["properties"]["distance_km"] for f in features]
    assert distances[0] == 0
    assert 5.5 < distances[1] < 5.7  # 0.05° of latitude ≈ 5.56 km
    assert 16.6 < distances[2] < 16.8


def test_stats_sorted_and_geo_stats_as_geojson(client):
    hours = client.get("/stats/hour").get_json()
    assert [r["hour"] for r in hours["results"]] == [8, 13]
    hotspots = client.get("/stats/hotspots").get_json()
    assert hotspots["type"] == "FeatureCollection"
    assert hotspots["features"][0]["geometry"]["type"] == "Polygon"

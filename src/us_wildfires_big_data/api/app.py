"""
Flask API over the fires in MongoDB (etl/load_mongo.py) and the Spark results
(spark/analysis.py).
"""

from flask import Flask, jsonify, request
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import OperationFailure
from werkzeug.exceptions import HTTPException, NotFound

from us_wildfires_big_data.api import queries as q
from us_wildfires_big_data.config import MONGO_COLLECTION, MONGO_DB, MONGO_URI


def create_app(db: Database | None = None) -> Flask:
    """Application factory. Tests pass their own database; gunicorn uses MONGO_URI/MONGO_DB."""
    app = Flask(__name__)
    app.json.sort_keys = False  # keep "type" first in the GeoJSON output
    if db is None:
        # One client per process: gunicorn calls create_app in every worker
        db = MongoClient(MONGO_URI)[MONGO_DB]
    fires = db[MONGO_COLLECTION]

    @app.errorhandler(HTTPException)
    def http_error(error: HTTPException):
        return jsonify(error=error.name, message=error.description), error.code

    @app.errorhandler(OperationFailure)
    def mongo_rejected(error: OperationFailure):
        # e.g. a self-intersecting polygon, which the 2dsphere index cannot query
        message = error.details.get("errmsg") if error.details else str(error)
        return jsonify(error="Bad Request", message=message), 400

    @app.get("/health")
    def health():
        db.command("ping")
        return jsonify(status="ok", fires=fires.estimated_document_count())

    @app.get("/fires/near")
    def near():
        center = q.point(request.args)
        radius_km = q.number(request.args, "radius_km", 0, q.MAX_RADIUS_KM, 10)
        n = q.limit(request.args)
        query = q.near_query(center, radius_km, q.filters(request.args))
        docs = list(fires.find(query).limit(n))
        return jsonify(
            q.feature_collection(docs, center=center, radius_km=radius_km, limit=n)
        )

    @app.post("/fires/within")
    def within():
        area = q.polygon(request.get_json(silent=True))
        n = q.limit(request.args)
        query = q.within_query(area, q.filters(request.args))
        return jsonify(
            q.feature_collection(
                list(fires.find(query).limit(n)),
                total=fires.count_documents(query),
                limit=n,
            )
        )

    @app.get("/fires/nearest")
    def nearest():
        center = q.point(request.args)
        max_km = q.number(request.args, "max_km", 0, q.MAX_RADIUS_KM, 50)
        n = q.limit(request.args)
        pipeline = q.geo_near_pipeline(center, max_km, q.filters(request.args), n)
        docs = list(fires.aggregate(pipeline))
        for doc in docs:
            doc["distance_km"] = round(doc["distance_km"], 3)
        return jsonify(
            q.feature_collection(docs, center=center, max_km=max_km, limit=n)
        )

    @app.get("/stats")
    def stats_index():
        return jsonify(
            {name: f"/stats/{name}" for name in q.STATS}
            | {"_note": "Computed by the Spark stage (spark/analysis.py)"}
        )

    @app.get("/stats/<name>")
    def stats(name: str):
        if name not in q.STATS:
            raise NotFound(f"Unknown result '{name}'. Available: {', '.join(q.STATS)}")
        collection, sort = q.STATS[name]
        n = q.limit(request.args, maximum=10_000) if "limit" in request.args else 0
        docs = list(db[collection].find().sort(sort).limit(n))  # limit 0 = all
        if name in q.GEO_STATS:
            return jsonify(q.feature_collection(docs, result=name))
        return jsonify(result=name, returned=len(docs), results=docs)

    return app


if __name__ == "__main__":
    create_app().run(debug=True)

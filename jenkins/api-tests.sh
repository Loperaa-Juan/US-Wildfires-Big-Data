#!/usr/bin/env bash
# Basic tests against a running API, run by the Jenkinsfile on the staging stack before deploying.
# Each check calls one endpoint with curl and checks the JSON response with jq. Every check runs,
# then the script exits with 1 if any failed, which fails the build and stops the deploy.
#
# Usage: jenkins/api-tests.sh http://api:5000
set -uo pipefail

API="${1:?usage: $0 <API base URL, e.g. http://api:5000>}"
failures=0

# Downtown Los Angeles, and a polygon around the LA basin (the README example)
LAT=34.05
LON=-118.25
LA_POLYGON='{"type": "Polygon", "coordinates": [[[-118.7, 33.7], [-117.9, 33.7], [-117.9, 34.4], [-118.7, 34.4], [-118.7, 33.7]]]}'

# check <description> <jq expression that must be true> <curl arguments...>
check() {
    local description="$1" expression="$2"
    shift 2
    local body=""
    if body=$(curl -fsS --max-time 30 "$@") && jq -e "$expression" <<<"$body" >/dev/null; then
        echo "PASS  $description"
    else
        echo "FAIL  $description"
        echo "      expected: $expression"
        echo "      response: ${body:0:500}"
        failures=$((failures + 1))
    fi
}

# check_status <description> <expected HTTP status> <curl arguments...>
check_status() {
    local description="$1" expected="$2"
    shift 2
    local status
    status=$(curl -sS --max-time 30 -o /dev/null -w '%{http_code}' "$@")
    if [[ "$status" == "$expected" ]]; then
        echo "PASS  $description"
    else
        echo "FAIL  $description (expected HTTP $expected, got $status)"
        failures=$((failures + 1))
    fi
}

echo "Testing the API at $API"

check "GET /health: MongoDB answers and the fires are loaded" \
    '.status == "ok" and .fires > 0' \
    "$API/health"

check "GET /fires/near: fires within 50 km of Los Angeles, as GeoJSON points" \
    '.type == "FeatureCollection" and .returned > 0 and .returned <= 5
     and (.features | length) == .returned
     and all(.features[]; .type == "Feature" and .geometry.type == "Point")' \
    "$API/fires/near?lat=$LAT&lon=$LON&radius_km=50&limit=5"

check "POST /fires/within: fires inside the LA polygon" \
    '.type == "FeatureCollection" and .returned > 0 and .total >= .returned' \
    -X POST -H 'Content-Type: application/json' -d "$LA_POLYGON" \
    "$API/fires/within?limit=10"

check "GET /fires/nearest: nearest fires sorted by distance, all within max_km" \
    '.returned > 0
     and ([.features[].properties.distance_km] | . == sort)
     and all(.features[]; .properties.distance_km <= 50)' \
    "$API/fires/nearest?lat=$LAT&lon=$LON&max_km=50&limit=5"

check "GET /stats/hotspots: Spark hotspots, as GeoJSON" \
    '.type == "FeatureCollection" and .result == "hotspots" and .returned > 0' \
    "$API/stats/hotspots?limit=5"

check_status "GET /fires/near without lat: rejected with 400" 400 \
    "$API/fires/near?lon=$LON"

if ((failures > 0)); then
    echo "$failures API check(s) failed"
    exit 1
fi
echo "All API checks passed"

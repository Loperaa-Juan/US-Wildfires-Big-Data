"""Deliberately failing test, to show that a failing test blocks the deploy
(jenkins/JENKINS.md, C3). Delete this file to make the pipeline green again."""

from us_wildfires_big_data.api import queries as q


def test_point_order_demo_failure():
    # Wrong on purpose: GeoJSON stores [lon, lat], so the real result is [-118.25, 34.05]
    assert q.point({"lat": "34.05", "lon": "-118.25"})["coordinates"] == [34.05, -118.25]

import { describe, expect, it } from "vitest";

import { queryString, requests } from "./api";
import { causeLabel, formatDate, formatHour, formatInt, formatLonLat, monthLabel } from "./format";
import { boundsPolygon, toLatLng, toPolygon } from "./geo";
import { classify, niceRound, niceTicks, quantileBreaks } from "./scale";

describe("queryString", () => {
  it("leaves out empty and undefined values", () => {
    expect(queryString({ lat: 34.05, cause: "", state: undefined, limit: 10 })).toBe(
      "?lat=34.05&limit=10",
    );
  });

  it("is empty when there is nothing to send", () => {
    expect(queryString({ cause: "" })).toBe("");
  });
});

describe("requests", () => {
  const query = { lat: 34, lon: -118.2, radius_km: 25, limit: 100 };

  it("$near sends the radius as radius_km", () => {
    expect(requests.near(query)).toEqual({
      method: "GET",
      path: "/fires/near?lat=34&lon=-118.2&radius_km=25&limit=100",
    });
  });

  it("$geoNear sends the radius as max_km", () => {
    expect(requests.nearest({ ...query, cause: "Arson" }).path).toBe(
      "/fires/nearest?lat=34&lon=-118.2&limit=100&cause=Arson&max_km=25",
    );
  });

  it("$geoWithin posts the polygon and puts limit and filters in the URL", () => {
    const area = toPolygon([
      [0, 0],
      [1, 0],
      [1, 1],
    ]);
    expect(requests.within(area, 50, { year: "2005" })).toEqual({
      method: "POST",
      path: "/fires/within?limit=50&year=2005",
      body: area,
    });
  });
});

describe("toPolygon", () => {
  it("closes the ring with the first vertex", () => {
    const ring = toPolygon([
      [-120, 40],
      [-119, 40],
      [-119, 41],
    ]).coordinates[0];
    expect(ring).toHaveLength(4);
    expect(ring.at(-1)).toEqual(ring[0]);
  });

  it("rejects fewer than 3 vertices", () => {
    expect(() =>
      toPolygon([
        [0, 0],
        [1, 1],
      ]),
    ).toThrow();
  });
});

describe("boundsPolygon", () => {
  it("builds a counterclockwise rectangle and clamps wrapped longitudes", () => {
    const ring = boundsPolygon(-200, 20, -60, 50).coordinates[0];
    expect(ring).toEqual([
      [-180, 20],
      [-60, 20],
      [-60, 50],
      [-180, 50],
      [-180, 20],
    ]);
  });
});

describe("toLatLng", () => {
  it("swaps GeoJSON [lon, lat] into Leaflet [lat, lon]", () => {
    expect(toLatLng([-118.2, 34])).toEqual([34, -118.2]);
  });
});

describe("scale", () => {
  it("rounds class limits to 2 significant digits", () => {
    expect(niceRound(1287)).toBe(1300);
    expect(niceRound(47)).toBe(47);
    expect(niceRound(0)).toBe(0);
  });

  it("puts about the same number of values in each quantile class", () => {
    const values = Array.from({ length: 100 }, (_, i) => i + 1);
    const breaks = quantileBreaks(values, 5);
    expect(breaks).toEqual([21, 41, 61, 81]);
    const sizes = [0, 0, 0, 0, 0];
    for (const v of values) sizes[classify(v, breaks)]++;
    expect(sizes).toEqual([20, 20, 20, 20, 20]);
  });

  it("drops repeated limits of skewed data instead of creating empty classes", () => {
    const skewed = [...Array(90).fill(1), 50, 100, 500, 1000, 5000, 9000, 9500, 9800, 9900, 10476];
    const breaks = quantileBreaks(skewed, 5);
    expect(new Set(breaks).size).toBe(breaks.length);
    expect(classify(10476, breaks)).toBe(breaks.length);
  });

  it("classifies by the upper limit of each class", () => {
    expect(classify(5, [10, 100])).toBe(0);
    expect(classify(10, [10, 100])).toBe(1);
    expect(classify(1000, [10, 100])).toBe(2);
  });

  it("makes clean axis ticks that reach the maximum", () => {
    expect(niceTicks(106292)).toEqual([0, 50000, 100000, 150000]);
    expect(niceTicks(0)).toEqual([0]);
  });
});

describe("format", () => {
  it("groups thousands with a period", () => {
    expect(formatInt(1878525)).toBe("1.878.525");
  });

  it("formats hours, coordinates and labels in Spanish", () => {
    expect(formatHour(7)).toBe("07:00");
    expect(formatLonLat([-120.75, 40.25])).toBe("40,25° N · 120,75° O");
    expect(monthLabel(8)).toBe("Ago");
    expect(causeLabel("Lightning")).toBe("Rayo");
    expect(causeLabel("Unknown cause")).toBe("Unknown cause");
  });
});

describe("formatDate", () => {
  it("reads the UTC date, whatever the browser's time zone", () => {
    expect(formatDate("2005-02-02")).toBe("2 feb 2005");
    expect(formatDate("2011-12-29")).toBe("29 dic 2011");
  });
});

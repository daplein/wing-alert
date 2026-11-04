import assert from "node:assert/strict";
import { test } from "node:test";

import { addReading, answerObs, recordAll } from "../src/obs.js";

class FakeKv {
  constructor() {
    this.values = new Map();
    this.options = new Map();
  }
  async get(key) {
    return this.values.has(key) ? JSON.parse(this.values.get(key)) : null;
  }
  async put(key, value, options) {
    this.values.set(key, value);
    this.options.set(key, options);
  }
}

const reading = (time, wind) => ({ time, wind, gust: null, direction: 90, wave_height: null, wave_period: null });
const station = (id, readings) => ({ id, source: { kind: "fake", readings } });

// A fetch that answers every ERDDAP call with the given rows.
function erddapFetch(rows) {
  const table = { columnNames: ["time", "WindSpeed", "Gust", "WindDirection", "WaveHeight", "WavePeriod"], rows };
  return async () => new Response(JSON.stringify({ table }));
}

test("fr_10_3 readings are sorted, one per station and time", () => {
  let entry = { stations: {} };
  entry = addReading(entry, { station: "m2", reading: reading("2026-11-04T19:00Z", 20) });
  entry = addReading(entry, { station: "m2", reading: reading("2026-11-04T18:00Z", 19) });
  entry = addReading(entry, { station: "m2", reading: reading("2026-11-04T19:00Z", 21) });
  assert.deepEqual(entry.stations.m2.map((r) => [r.time, r.wind]), [
    ["2026-11-04T18:00Z", 19],
    ["2026-11-04T19:00Z", 21],
  ]);
});

test("fr_10_3 records under one key per utc day, kept 8 days", async () => {
  const kv = new FakeKv();
  const fetchFn = erddapFetch([
    ["2026-11-04T23:00:00Z", 10, null, 90, null, null],
    ["2026-11-05T00:00:00Z", 12, null, 90, null, null],
  ]);
  const count = await recordAll(kv, new Date("2026-11-05T00:07Z"), fetchFn, [
    { id: "m2", source: { kind: "erddap", station: "M2" } },
  ]);
  assert.equal(count, 2);
  assert.equal((await kv.get("obs:2026-11-04")).stations.m2[0].wind, 10);
  assert.equal((await kv.get("obs:2026-11-05")).stations.m2[0].wind, 12);
  assert.equal(kv.options.get("obs:2026-11-05").expirationTtl, 8 * 24 * 3600);
});

test("fr_10_3 keeps readings from earlier runs", async () => {
  const kv = new FakeKv();
  const stations = [{ id: "m2", source: { kind: "erddap", station: "M2" } }];
  await recordAll(kv, new Date(), erddapFetch([["2026-11-04T18:00:00Z", 10, null, 90, null, null]]), stations);
  await recordAll(kv, new Date(), erddapFetch([["2026-11-04T19:00:00Z", 11, null, 90, null, null]]), stations);
  assert.equal((await kv.get("obs:2026-11-04")).stations.m2.length, 2);
});

test("fr_10_4 a failing station is skipped, the others are stored", async () => {
  const kv = new FakeKv();
  const stations = [station("broken", []), { id: "m2", source: { kind: "erddap", station: "M2" } }];
  const count = await recordAll(kv, new Date(), erddapFetch([["2026-11-04T18:00:00Z", 10, null, 90, null, null]]), stations);
  assert.equal(count, 1);
  assert.deepEqual(Object.keys((await kv.get("obs:2026-11-04")).stations), ["m2"]);
});

test("fr_10_5 obs answers a day's readings with station details and open cors", async () => {
  const kv = new FakeKv();
  await kv.put("obs:2026-11-04", JSON.stringify({ stations: { m2: [reading("2026-11-04T18:00Z", 10)] } }));
  const response = await answerObs(new Request("https://w.dev/obs?day=2026-11-04"), kv);
  const body = await response.json();
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("Access-Control-Allow-Origin"), "*");
  assert.equal(body.stations.m2[0].wind, 10);
  assert.deepEqual(body.about.map((s) => s.id), ["dublin_bay", "m2", "m5"]);
  assert.equal(body.about[0].lat, 53.3319);
});

test("fr_10_5 obs answers an empty day and rejects bad requests", async () => {
  const kv = new FakeKv();
  const empty = await answerObs(new Request("https://w.dev/obs?day=2026-01-01"), kv);
  assert.deepEqual((await empty.json()).stations, {});
  assert.equal((await answerObs(new Request("https://w.dev/obs?day=today"), kv)).status, 400);
  assert.equal((await answerObs(new Request("https://w.dev/other"), kv)).status, 404);
});

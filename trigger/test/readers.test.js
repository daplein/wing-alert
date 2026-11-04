import assert from "node:assert/strict";
import { test } from "node:test";

import { erddapUrl, parseEastPier, parseErddap, parseIrishLights, read } from "../src/readers.js";

const FEED = {
  LatestAISDataFeed: [
    { MMSI: "992501123", AverageWindSpeed: "9", DateTransmitted: "04/11/2026 22:30:00" },
    {
      MMSI: "992501301",
      AverageWindSpeed: "20",
      GustSpeed: "33",
      WindDirection: "73",
      WaveHeight: "2.000",
      WavePeriod: "5",
      DateTransmitted: "04/11/2026 22:32:00",
    },
  ],
};
const PAGE = `<input type="hidden" name="latestais" id="latestais" value="${JSON.stringify(FEED).replace(/"/g, "&quot;")}" />`;

const ERDDAP = {
  table: {
    columnNames: ["time", "WindSpeed", "Gust", "WindDirection", "WaveHeight", "WavePeriod"],
    rows: [
      ["2026-11-04T18:00:00Z", 19.696, 23.453, 68.0, 1.172, 4.336],
      ["2026-11-04T19:00:00Z", 20.606, null, 71.0, null, 4.336],
    ],
  },
};

test("fr_10_2 dublin bay buoy reading comes from the page's hidden field", () => {
  assert.deepEqual(parseIrishLights(PAGE, "992501301"), [
    { time: "2026-11-04T22:32Z", wind: 20, gust: 33, direction: 73, wave_height: 2, wave_period: 5 },
  ]);
});

test("fr_10_2 missing values become null", () => {
  const [reading] = parseIrishLights(PAGE, "992501123");
  assert.equal(reading.wind, 9);
  assert.equal(reading.gust, null);
});

test("fr_10_4 changed page or missing buoy fails loudly", () => {
  assert.throws(() => parseIrishLights("<html></html>", "992501301"), /No latestais/);
  assert.throws(() => parseIrishLights(PAGE, "1"), /No reading for MMSI 1/);
});

test("fr_10_2 erddap rows become readings, rounded to 0.1", () => {
  assert.deepEqual(parseErddap(ERDDAP), [
    { time: "2026-11-04T18:00Z", wind: 19.7, gust: 23.5, direction: 68, wave_height: 1.2, wave_period: 4.3 },
    { time: "2026-11-04T19:00Z", wind: 20.6, gust: null, direction: 71, wave_height: null, wave_period: 4.3 },
  ]);
});

test("fr_10_2 erddap asks for the last 3 hours of one station", () => {
  const url = erddapUrl("M5", new Date("2026-11-04T22:07:00Z"));
  assert.match(url, /IWBNetwork\.json\?time,WindSpeed,Gust,WindDirection,WaveHeight,WavePeriod&/);
  assert.match(url, /station_id=%22M5%22&time%3E=2026-11-04T19:07:00.000Z$/);
});

test("fr_10_4 a source that answers with an error fails", async () => {
  const fetchFn = async () => new Response("down", { status: 503 });
  await assert.rejects(read({ kind: "erddap", station: "M2" }, new Date(), fetchFn), /503/);
});

test("fr_10_2 read fetches and parses the right source", async () => {
  const fetchFn = async () => new Response(JSON.stringify(ERDDAP));
  const readings = await read({ kind: "erddap", station: "M2" }, new Date(), fetchFn);
  assert.equal(readings.length, 2);
  await assert.rejects(read({ kind: "carrier_pigeon" }, new Date()), /Unknown source/);
});

const EAST_PIER = {
  reading: { received_utc: "2026-11-04T23:04:14.205Z", wind_kt: 25.46 },
  window_10min: { samples: 10, mean_wind_kt: 22.82, max_gust_kt: 28.57, vector_mean_dir_deg: 98.8 },
};

test("fr_10_2 east pier reading is its 10-minute block in knots", () => {
  assert.deepEqual(parseEastPier(EAST_PIER), [
    { time: "2026-11-04T23:04Z", wind: 22.8, gust: 28.6, direction: 98.8, wave_height: null, wave_period: null },
  ]);
});

test("fr_10_4 east pier without a full 10-minute block fails", () => {
  const short = { ...EAST_PIER, window_10min: { ...EAST_PIER.window_10min, samples: 2 } };
  assert.throws(() => parseEastPier(short), /no full 10-minute block/);
});

test("fr_10_2 read fetches the east pier station", async () => {
  const fetchFn = async (url) => {
    assert.match(url, /eastpier\.dublinbaybuoy\.com\/latest$/);
    return new Response(JSON.stringify(EAST_PIER));
  };
  assert.equal((await read({ kind: "east_pier" }, new Date(), fetchFn))[0].wind, 22.8);
});

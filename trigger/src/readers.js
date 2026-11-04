// Turn each source's answer into readings (FR-10.2).
// A reading: { time: "2026-11-04T22:32Z", wind, gust, direction, wave_height, wave_period }.

const IRISH_LIGHTS_URL = "https://cilpublic.cil.ie/MetOcean/MetOcean.aspx";
const ERDDAP_URL = "https://erddap.marine.ie/erddap/tabledap/IWBNetwork.json";
const ERDDAP_COLUMNS = "time,WindSpeed,Gust,WindDirection,WaveHeight,WavePeriod";
const ERDDAP_LOOKBACK_HOURS = 3;

export async function read(source, now, fetchFn = fetch) {
  if (source.kind === "irish_lights") return readIrishLights(source.mmsi, fetchFn);
  if (source.kind === "erddap") return readErddap(source.station, now, fetchFn);
  throw new Error(`Unknown source kind "${source.kind}"`);
}

async function readIrishLights(mmsi, fetchFn) {
  return parseIrishLights(await fetchText(IRISH_LIGHTS_URL, fetchFn), mmsi);
}

async function readErddap(station, now, fetchFn) {
  return parseErddap(JSON.parse(await fetchText(erddapUrl(station, now), fetchFn)));
}

export function erddapUrl(station, now) {
  const since = new Date(now.getTime() - ERDDAP_LOOKBACK_HOURS * 3600_000);
  // ERDDAP wants the quotes and ">" encoded, but "&" and "=" as they are.
  return `${ERDDAP_URL}?${ERDDAP_COLUMNS}&station_id=%22${station}%22&time%3E=${since.toISOString()}`;
}

async function fetchText(url, fetchFn) {
  const response = await fetchFn(url, { headers: { "User-Agent": "wing-alert" } });
  if (!response.ok) throw new Error(`${url} answered ${response.status}`);
  return response.text();
}

// The page carries the latest readings as JSON in a hidden field; times are UTC.
export function parseIrishLights(html, mmsi) {
  const match = html.match(/id="latestais" value="([^"]*)"/);
  if (!match) throw new Error("No latestais field on the MetOcean page");
  const feed = JSON.parse(unescapeHtml(match[1])).LatestAISDataFeed;
  const row = feed.find((item) => item.MMSI === mmsi);
  if (!row) throw new Error(`No reading for MMSI ${mmsi}`);
  return [
    {
      time: irishLightsTime(row.DateTransmitted),
      wind: number(row.AverageWindSpeed),
      gust: number(row.GustSpeed),
      direction: number(row.WindDirection),
      wave_height: number(row.WaveHeight),
      wave_period: number(row.WavePeriod),
    },
  ];
}

// ERDDAP already gives knots and UTC.
export function parseErddap(body) {
  const { columnNames, rows } = body.table;
  const at = (row, name) => row[columnNames.indexOf(name)];
  return rows.map((row) => ({
    time: at(row, "time").replace(/:00Z$/, "Z"),
    wind: number(at(row, "WindSpeed")),
    gust: number(at(row, "Gust")),
    direction: number(at(row, "WindDirection")),
    wave_height: number(at(row, "WaveHeight")),
    wave_period: number(at(row, "WavePeriod")),
  }));
}

function irishLightsTime(text) {
  const [, day, month, year, hour, minute] = text.match(/(\d\d)\/(\d\d)\/(\d{4}) (\d\d):(\d\d)/);
  return `${year}-${month}-${day}T${hour}:${minute}Z`;
}

function number(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.round(parsed * 10) / 10 : null;
}

function unescapeHtml(text) {
  return text
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
}

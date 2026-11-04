// Record live readings in KV and serve them (FR-10.1 to FR-10.5).
import { read } from "./readers.js";
import { STATIONS, describe } from "./stations.js";

const KEEP_SECONDS = 8 * 24 * 3600;
const DAY = /^\d{4}-\d{2}-\d{2}$/;

export async function recordAll(kv, now, fetchFn = fetch, stations = STATIONS) {
  const readings = await readAll(stations, now, fetchFn);
  for (const day of new Set(readings.map(({ reading }) => reading.time.slice(0, 10)))) {
    const stored = (await kv.get(dayKey(day), "json")) ?? { stations: {} };
    const sameDay = readings.filter(({ reading }) => reading.time.startsWith(day));
    const merged = sameDay.reduce((entry, item) => addReading(entry, item), stored);
    await kv.put(dayKey(day), JSON.stringify(merged), { expirationTtl: KEEP_SECONDS });
  }
  return readings.length;
}

// A failing station is logged and skipped (FR-10.4).
async function readAll(stations, now, fetchFn) {
  const results = await Promise.allSettled(stations.map((s) => read(s.source, now, fetchFn)));
  return results.flatMap((result, index) => {
    const station = stations[index].id;
    if (result.status === "fulfilled") return result.value.map((reading) => ({ station, reading }));
    console.warn(`No reading from ${station}: ${result.reason.message}`);
    return [];
  });
}

export function addReading(entry, { station, reading }) {
  const others = (entry.stations[station] ?? []).filter((old) => old.time !== reading.time);
  const readings = [...others, reading].sort((a, b) => a.time.localeCompare(b.time));
  return { stations: { ...entry.stations, [station]: readings } };
}

export async function answerObs(request, kv) {
  const url = new URL(request.url);
  if (url.pathname !== "/obs") return reply({ error: "Not found" }, 404);
  const day = url.searchParams.get("day") ?? "";
  if (!DAY.test(day)) return reply({ error: "Use /obs?day=YYYY-MM-DD" }, 400);
  const stored = (await kv.get(dayKey(day), "json")) ?? { stations: {} };
  return reply({ day, stations: stored.stations, about: STATIONS.map(describe) }, 200);
}

function reply(body, status) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
      "Cache-Control": "public, max-age=300",
    },
  });
}

function dayKey(day) {
  return `obs:${day}`;
}

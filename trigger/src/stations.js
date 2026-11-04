// Live stations recorded every hour (spec slice 10, FR-10.7).
// Adding a station is one entry here; a new kind of source also needs a reader.
export const STATIONS = [
  {
    id: "east_pier",
    name: "East Pier",
    lat: 53.3002,
    lon: -6.1242,
    waves: false,
    source: { kind: "east_pier" },
  },
  {
    id: "dublin_bay",
    name: "Dublin Bay Buoy",
    lat: 53.3319,
    lon: -6.0774,
    waves: true,
    source: { kind: "irish_lights", mmsi: "992501301" },
  },
  {
    id: "m2",
    name: "M2 buoy",
    lat: 53.4836,
    lon: -5.4302,
    waves: true,
    source: { kind: "erddap", station: "M2" },
  },
  {
    id: "m5",
    name: "M5 buoy",
    lat: 51.6904,
    lon: -6.7043,
    waves: true,
    source: { kind: "erddap", station: "M5" },
  },
];

export function describe(station) {
  const { id, name, lat, lon, waves } = station;
  return { id, name, lat, lon, waves };
}

# wing-alert spec

Status: **draft, in review**. Slices are built one PR at a time, in order.

## Goal

Tell the Wicklow wingfoiling crew when the wind is good, where to go, and how dangerous the shore break is. Keep a record of every day so we can look back at what we missed and spot patterns.

- **Push:** a short WhatsApp alert when a spot has a rideable window, with a link to the site. WhatsApp only ever gets alerts and links, never the full report.
- **Pull:** a GitHub Pages site with today's report, a map, and every past day.
- **Look back:** a weekly page on the site. WhatsApp gets a one-line link to it.

It runs on GitHub Actions and free data, with a free Cloudflare Worker as its alarm clock (slice 7). There's no server and no app.

## For the crew: how you'll get the alerts

**The bot can't post in our WhatsApp group.** WhatsApp only lets automated messages into groups through Meta's official business platform. That means a registered business account, approved message templates and paid messages: too much hassle for a hobby project.

What we can do for free:

- **Alerts go to individuals.** Each message goes to one person's WhatsApp, using a free service called CallMeBot. David gets them first. Anyone in the crew who wants their own alerts can register with CallMeBot (about a minute) and give David the key it sends back.
- **A website for everyone.** The daily report, map and spot guide live on a public web page. The link gets pinned in the group, so anyone can check it anytime.
- **Later: Telegram.** A Telegram bot *can* post into a group, with the map image, for free. If the crew is up for a Telegram group, that's the next step.

## Overview

### Daily job (twice a day)

```mermaid
flowchart LR
    cron([Cloudflare Worker cron<br/>05:17 + 15:17 UTC]):::ext
    spots[(config/spots.yaml)]
    wind[(Open-Meteo<br/>wind forecast)]:::ext
    sea[(Open-Meteo Marine<br/>waves, swell, sea level)]:::ext
    state[(state.json<br/>alerts already sent)]
    archive[(data/ archive<br/>JSON per run)]

    score[Score each spot,<br/>each hour]:::hot
    windows[Find rideable<br/>windows]:::hot
    risk[Shore break<br/>warning level]
    new{New or changed<br/>since last alert?}:::hot
    send[WhatsApp alert<br/>via CallMeBot]:::hot
    site[Build site +<br/>wind map]
    me([David's WhatsApp]):::ext
    pages([GitHub Pages]):::ext

    cron --> score
    spots --> score
    wind --> score
    score --> windows
    sea --> risk
    windows --> risk
    risk --> new
    state <--> new
    new -- yes --> send --> me
    windows --> archive
    risk --> archive
    archive --> site --> pages

    classDef hot fill:#EB1F1F,stroke:#9E0F14,stroke-width:3px,color:#fff,font-weight:bold
    classDef ext fill:#5B3FD9,stroke:#3A2899,stroke-width:3px,color:#fff,font-weight:bold
```

Wind decides **whether** to alert. Waves and tide decide **how loud the warning is**; they never stop an alert.

### Weekly job (Sunday evening)

```mermaid
flowchart LR
    cron([Cloudflare Worker cron<br/>Sunday 18:17 UTC]):::ext
    archive[(data/ archive<br/>last 7 days)]
    sent[(state.json<br/>what we alerted)]
    review[Weekly summary<br/>best days, missed windows]:::hot
    me([David's WhatsApp]):::ext
    pages([GitHub Pages<br/>week page]):::ext

    cron --> review
    archive --> review
    sent --> review
    review --> me
    review --> pages

    classDef hot fill:#EB1F1F,stroke:#9E0F14,stroke-width:3px,color:#fff,font-weight:bold
    classDef ext fill:#5B3FD9,stroke:#3A2899,stroke-width:3px,color:#fff,font-weight:bold
```

## Spots

Coordinates come from David's spot guide where it has them, otherwise from OpenStreetMap. Wicklow Harbour is approximate. Good wind directions are where the wind blows **from**, read clockwise round the compass (N → E → S → W). Degrees are for the config: N = 0°, E = 90°, S = 180°, W = 270°.

> **To confirm.** Arklow, Buckroney and Seapoint come from David. Ennereilly, Brittas and Magheramore are proposed from the OpenStreetMap coastline: the range runs from cross-shore on one side, through onshore, to cross-shore on the other. Ennereilly faces SE (no northerly, per David); Brittas and Magheramore face ESE.

| ID | Spot | Lat, Lon | Wind read at (FR-1.11) | Tide station | Good directions (wind from) | Notes |
|---|---|---|---|---|---|---|
| `arklow` | Arklow South Beach / The Cove | 52.7878, -6.1434 | 52.7878, -6.07 | Arklow | NNW → E → SSW (337–202°) | The main spot. Sheltered corner by Arklow Rock |
| `ennereilly` | Ennereilly | 52.837, -6.105 (approx.) | 52.837, -6.05 | Arklow | NE → E → SW (45–225°) | Just south of Buckroney. No northerly |
| `buckroney` | Buckroney | 52.8462, -6.0931 | 52.8462, -6.04 | Arklow | E → S → WSW (90–248°) | Faces WSW-ish: WSW is cross-shore. No northerly. Rocks to the north |
| `brittas` | Brittas Bay | 52.8831, -6.0575 | 52.8831, -5.98 | Arklow (approx., halfway to Wicklow) | NNE → E → SSW (20–200°) | |
| `magheramore` | Magheramore | 52.9310, -6.0225 | 52.931, -5.97 | Wicklow | NNE → E → SSW (20–200°) | Tricky, on the wish list |
| `wicklow_harbour` | Wicklow Harbour | 52.982, -6.035 (approx.) | 52.982, -6.00 | Wicklow | NW → N (280–20°) | Launch from the harbour |
| `seapoint` | Seapoint, Dún Laoghaire | 53.2972, -6.1589 | 53.31, -6.12 | Dublin Port | W → N → E (260–90°) | **Sheltered**: the westerly spot, and the safe option on wild easterly days |

A spot can be marked `sheltered: true` (Seapoint). See FR-4.5.

Each "wind read at" point is the first sea cell of the forecast model off that beach, 3–5 km out (checked 1 Nov 2026 by moving east until the wind jumped).

All spots, thresholds and directions live in `config/spots.yaml` and `config/settings.yaml`, so changing them needs no code change.

## Data sources

| Data | Source | Key? | Used in |
|---|---|---|---|
| Hourly wind speed, gusts, direction (kn) | [Open-Meteo forecast API](https://open-meteo.com/en/docs), `best_match` model, `timezone=Europe/Dublin` | No | Slice 1 |
| Sunrise, sunset | Open-Meteo forecast API (`daily`) | No | Slice 1 |
| Wave height and period, swell height and period | [Open-Meteo Marine API](https://open-meteo.com/en/docs/marine-weather-api) | No | Slice 4 |
| Tide predictions (Arklow, Wicklow, Dublin Port) | [Marine Institute ERDDAP](https://erddap.marine.ie/erddap/tabledap/IMI-TidePrediction.html), `IMI-TidePrediction` | No | Slice 6 |
| WhatsApp delivery | [CallMeBot](https://www.callmebot.com/blog/free-api-whatsapp-messages/): free, unofficial, text only, personal use | API key (secret) | Slice 1 |

Checked on 2026-11-01: both Open-Meteo APIs answer for every spot with no key. The marine grid is coarse: Arklow to Magheramore share one point about 7 km offshore, and Seapoint uses one out in Dublin Bay. That's fine for swell, but too coarse for tides, hence slice 6. Tide predictions are for planning, not navigation.

---

## Slice 1: Forecast, wind check, WhatsApp alert

Branch `feat/wind-alert`.

**Requirements**

- **FR-1.1** Load spots and thresholds from YAML. An invalid config fails the run with a clear message.
- **FR-1.2** For each spot, fetch the hourly forecast for today and tomorrow (Europe/Dublin): wind speed, gusts, direction in knots, plus sunrise and sunset.
- **FR-1.3** An hour is **good** when all of these hold:
  - mean wind between `min_wind` and `max_wind` (defaults 10 and 40 kn)
  - gusts at or below `max_gust` (default 45 kn)
  - direction inside the spot's good range (ranges may wrap through north, e.g. 280–20°)
  - the whole hour fits between sunrise + 30 min and sunset − 30 min (the 13:00 forecast stands for 13:00–14:00)
  - the hour hasn't already ended (the current hour still counts)
- **FR-1.4** A **window** is at least `min_window_hours` (default 2) consecutive good hours at one spot. It reports the start (first good hour), end (last good hour + 1 h), wind range, max gust and main direction (the circular mean as a 16-point compass name, e.g. ENE).
- **FR-1.5** Rank windows by length, then by mean wind closest to `ideal_wind` (default 20 kn). The best one goes first in the message.
- **FR-1.6** Send one WhatsApp message per run, to each configured recipient, with one short line per window (spot, hours, wind range, direction), grouped by day, best first. No hourly detail: that's on the site. If there are no new windows, send nothing.
- **FR-1.7** Don't repeat yourself. `state.json` keeps, per date, a signature of the windows already sent. Send only when a day's windows are new or have changed, and list only those days. A window that changes by an hour at either end counts as changed. A day whose windows disappear is not reported. Entries older than 14 days are pruned. The workflow commits `state.json` back to the repo.
- **FR-1.8** If a data source fails, retry once, then fail the run. GitHub emails David about failed workflows, so no extra error alert is needed.
- **FR-1.9** Recipients (phone number + CallMeBot key each) come from one secret, `WHATSAPP_RECIPIENTS`, and only ever from environment variables. They never appear in logs, files or the site; error messages name a recipient by position only.
- **FR-1.10** With no recipients configured, the job prints the message instead of sending it and doesn't update `state.json`, so it can run safely before the secret exists. `--dry-run` also skips the archive (FR-2.1): nothing is written at all.
- **FR-1.11** Wind is read at a **sea point** a few km off each beach (`wind_at` in `config/spots.yaml`), not at the beach itself. The forecast model's cell on the beach counts as land, which slows the wind: on 1 Nov 2026 it said 8–9 kn at Arklow while David rode 14–20 kn, and the first sea cell said 17 kn. The beach position is still used for the map and the marine data.
- **FR-1.12** A Cloudflare Worker starts the daily job on time (slice 7). GitHub's own cron stays as a late backup, in case the Worker fails. A run that comes twice is harmless: FR-1.7 stops repeat alerts, and the site shows the latest run.

**Example message**

```
🪁 Wing alert
Thu 6 Nov
• Arklow South Beach 13:00–17:00 · 18–22 kn ENE, gusts 27
• Brittas Bay 14:00–16:00 · 16–19 kn NE, gusts 24
Fri 7 Nov
• Seapoint 10:00–12:00 · 15–18 kn W, gusts 26
```

From slice 2 the message ends with the day page link, and from slice 4 risky windows get ⚠️ or 🚨.

**Schedule:** all times are UTC (an hour later in Irish summer time). The daily job runs at 05:17 and 15:17, the weekly on Sunday at 18:17, all started by the Cloudflare Worker (slice 7). GitHub's cron runs the daily job again at 06:47 and 16:47 as a backup (FR-1.12). A `workflow_dispatch` trigger allows manual runs.

## Slice 2: Daily archive and GitHub Pages site

Branch `feat/site`.

- **FR-2.1** Every daily run writes `data/YYYY/MM/YYYY-MM-DDTHH.json`: the forecast as issued, every hour's scores, and the windows (whole days, including hours already past, ranked as in FR-1.5). Plain JSON, easy to scrape. The workflow commits it.
- **FR-2.2** Every run builds a static site from `data/` (Python + Jinja templates, no framework) and deploys it with GitHub's official Pages actions. The built site is not committed.
- **FR-2.3** **Day page:**
  - top: "Best spot" with its window, or "Nothing rideable"
  - the wind map (from slice 3)
  - a table of all spots ranked, with hourly wind and good hours highlighted
  - links to the previous and next day
- **FR-2.9** If the Pages deploy fails, try once more. The data is already committed by then, so a failed deploy only leaves the site one run behind.
- **FR-2.8** The site works on a phone first. The hourly maps are a horizontal swipe strip on a phone (one map per screen, the next one peeking in) and a 2×2 grid on a wider screen. The hourly table scrolls sideways with the spot names pinned on the left.
- **FR-2.4** **Front page** is today's day page, plus a list of past days. A day page is built from the last run issued that day, and shows every date that run covers (today and tomorrow).
- **FR-2.5** The WhatsApp alert ends with a link to the day page.
- **FR-2.6** The site shows "Forecast from Open-Meteo" with a link (required by their terms).
- **FR-2.7** **Spots page:** one section per spot, rendered from `docs/spots/<id>.md` (launch points, parking by wind direction, hazards, seasonal notes, map link). The day page links each spot name to its section. Editing a spot's Markdown file is all it takes to update the page.

**Size check:** about 20 KB of JSON per run plus a 150 KB map per day is roughly 70 MB a year. That's far under the 1 GB Pages and repo guidance.

## Slice 3: Wind map

Branch `feat/wind-map`.

- **FR-3.1** One PNG per hour shown (09:00, 12:00, 15:00, 18:00), each a full map of the coast from Wicklow Harbour to Arklow, sized for a phone screen. The page lays them out (FR-2.8). Seapoint is 40 km further north, so it gets its own small inset map; otherwise the Wicklow spots end up squashed together. The inset sits in the top-left corner, over empty land (Dublin Bay is north and a little west of Wicklow), with a light grey frame, a matching "Dublin Bay" tab in its top-left corner and a small "↑ 40 km north" note under it. The image is cropped to its content, so there is no empty band between the title, the map and the legend.
- **FR-3.2** Each spot has a dot and an arrow pointing where the wind blows **to**, coloured by strength: grey < 10 kn, green 10–20, orange 20–30, red > 30. The label (name, mean/gust in knots) sits on the land side of the dot and the arrow just out at sea, so they never overlap whichever way the wind blows. Labels have no box: the name is dark slate, the numbers bold in the arrow's colour (a shade darker for grey and orange so they stay readable), both with a thin white outline so they read on land and sea. The dot is white with a dark ring. Arrows of spots close together (Buckroney and Ennereilly are 1 km apart) are spread along the coast so they don't touch.
- **FR-3.3** The base map comes from OpenStreetMap coastline data, with attribution on the image.
- **FR-3.4** Each run writes the maps for every date it covers (today and tomorrow) as `data/YYYY/MM/YYYY-MM-DD-HH.png`, overwriting the earlier ones, and the workflow commits them. Past maps never need re-rendering. At about 4 × 45 KB per date and a few versions per date in git history, that's roughly 200 MB a year: fine for a few years, and old map versions can be squashed out of history if it ever matters.
- **FR-3.5** The coastline is a simplified OpenStreetMap extract stored in the repo (`wing_alert/assets/coastline.json`), so no map tiles are fetched at run time.
- **FR-3.6** Land and sea have different colours (pale green-sand and blue), so the coast is easy to read. A pale blue band of shallows runs along the sea side of the shore, the way nautical charts show it. Land shapes are built from the same coastline lines: OpenStreetMap keeps land on the left of each way, and this coast faces east, so each open stretch is closed off far inland to the west. Small closed rings are islands.

## Slice 4: Tides, swell, shore break warning

Branch `feat/shore-break`.

- **FR-4.1** For each spot, fetch hourly wave height and period, and swell height and period, from the Marine API. (Tides come from slice 6.)
- **FR-4.2** Find high and low tide times from a sea level curve (peaks and troughs; a flat stretch counts once; swings under 0.2 m are dropped). They stay out of the alert to keep it short. *Replaced by slice 6: the curve now comes from each spot's tide station, not the Marine API's coarse model.*
- **FR-4.3** Give each window a **shore break level**: none, ⚠️ watch out, or 🚨 dangerous. It's based on the worst hour in the window:
  - wave height above the spot's `watch_wave_m` / `danger_wave_m` (defaults 0.8 m / 1.5 m)
  - one level up if the swell period is 10 s or longer (long swell dumps harder)
  - one level up if the tide is at the spot's `worse_at` state (`high`, `low` or `none`; default `none` until the crew tells us). "At high tide" means within 1.5 h of it.
  - the two step-ups only apply when the waves are at least half of `watch_wave_m`, so a flat sea never warns
  - spots can override `watch_wave_m` / `danger_wave_m`; `long_period_s` (10 s) is in the settings
- **FR-4.4** The warning never removes a window. If the Marine API fails, alerts still go out, just without warnings. In the alert it's just the ⚠️ or 🚨 emoji on that window's line; the reasons (swell, period, tide times) are on the day page.
- **FR-4.5** When a day has a 🚨 window at an exposed spot and a `sheltered` spot also has a window that day, the alert adds one line: `Sheltered option: Seapoint 12:00–16:00`.

## Slice 5: Weekly summary

Branch `feat/weekly`.

- **FR-5.1** On Sundays at 18:17 UTC (same workflow, started by the Worker as `job: weekly`; also runnable by hand), read the last 7 days of `data/` (Monday to the run day) and `state.json`.
- **FR-5.2** For each day, take the windows from that day's **morning run** (the shortest-range, most accurate forecast). List the best days and spots of the week.
- **FR-5.3** Mark each window as **alerted** if a sent alert listed an overlapping window at that spot, otherwise **missed** (the forecast didn't see it coming). Alerts are only recorded once `WHATSAPP_RECIPIENTS` is set, so until then every window shows as missed.
- **FR-5.4** Save the summary as `data/weeks/<monday>.json` (state.json forgets after 14 days, so the week is computed once and kept). Publish a week page on the site, linked from the front page, and send one WhatsApp line with the link, e.g. `🪁 Week of 3 Nov: 3 good days, 1 missed → <link>`.

---

## Slice 6: Tides per spot

Branch `feat/station-tides`.

Tides along this coast are odd. Near Arklow the main twice-a-day tide almost cancels out (the Irish Sea's tide pivots around a point close to Courtown), so Arklow has a small, lopsided tide with long stands and sometimes a double high water, while Wicklow, Bray and Dublin have a normal one about 2–3 times bigger. On 2 Nov 2026:

| Station | High water | Low water | Range |
|---|---|---|---|
| Arklow | ~05:50, ~17:45 (long stand 10:00–15:00) | ~09:15, ~23:00 | 0.8 m |
| Wicklow | ~04:50, ~17:00 | ~10:15, ~23:25 | 1.9 m |
| Dublin Port | ~05:00, ~17:25 | ~10:25, ~23:30 | 2.7 m |

So one tide line for the whole coast is wrong, and the Marine API's modelled sea level is too coarse to show this.

- **FR-6.1** Tide predictions come from the [Marine Institute](https://erddap.marine.ie/erddap/tabledap/IMI-TidePrediction.html) (ERDDAP dataset `IMI-TidePrediction`, free, no key, 5-minute steps, height above chart datum). Each spot names its station in `config/spots.yaml` (`tide_station`). Each station is fetched once per run, for today and tomorrow plus 3 h either side so tides at midnight are found.
- **FR-6.2** High and low waters are found as in FR-4.2. They feed the shore break rule (FR-4.3), so "worse at high tide" uses the spot's own high water.
- **FR-6.3** The snapshot keeps, per station, its name, the levels every 30 minutes and the high/low waters; each spot records its station.
- **FR-6.4** **Tide chart** on the day page, in place of the single "Tides:" line: one line per station over the day (00:00–24:00, height in m), with the hours where any spot is rideable shaded. A small inline SVG, so it scales on a phone and follows dark mode.
- **FR-6.5** **Table:** under each spot name, its station's tides that day, one line each: `HW 05:50 17:45` and `LW 09:15 23:00`.
- **FR-6.6** **Map:** each spot's label adds the tide at that hour: `HW` or `LW` within 1 h of it, otherwise `↑` (rising) or `↓` (falling).
- **FR-6.7** If the tide service fails, the run carries on without tides (no chart, no tide lines, no tide step-up in the shore break), like FR-4.4.

## Slice 7: Reliable schedule

Branch `feat/cloudflare-trigger`.

GitHub's cron is too unreliable to time an alert. GitHub runs scheduled workflows "best effort" from one shared queue, and free public repos have no guarantee. From 2 to 4 Nov 2026, 4 of 12 scheduled runs never ran and the rest started 6 to 8 hours late: the morning alert arrived around 13:00. Runs started by hand or through the API (`workflow_dispatch`) don't wait in that queue: they start within seconds.

So a free Cloudflare Worker is the alarm clock, and GitHub still does all the work.

```mermaid
flowchart LR
    worker([Cloudflare Worker<br/>cron, on the minute]):::hot
    api[GitHub API<br/>workflow_dispatch]:::hot
    job[daily.yml<br/>same job as before]:::hot
    backup([GitHub cron<br/>late backup]):::ext

    worker -- token, Actions: write --> api --> job
    backup -.-> job

    classDef hot fill:#EB1F1F,stroke:#9E0F14,stroke-width:3px,color:#fff,font-weight:bold
    classDef ext fill:#5B3FD9,stroke:#3A2899,stroke-width:3px,color:#fff,font-weight:bold
```

- **FR-7.1** A Cloudflare Worker (`trigger/`, free plan) has three cron triggers: `17 5 * * *` and `17 15 * * *` (daily) and `17 18 * * SUN` (weekly).
- **FR-7.2** On each trigger it calls GitHub's API to run `daily.yml` on `main` with `job: daily` or `job: weekly`. If the call fails, it retries once, then fails, so the error shows in the Worker's logs.
- **FR-7.3** It authenticates with a fine-grained GitHub token limited to this repo, with only the **Actions: read and write** permission. The token lives only in the Worker's secret `GITHUB_TOKEN`, never in a file, log or commit.
- **FR-7.4** GitHub's cron keeps the daily job at 06:47 and 16:47 as a backup, in case the Worker or its token fails. The weekly job has no GitHub backup: it has no repeat guard, so it must only run once.
- **FR-7.5** The Worker's code stays tiny: a lookup from cron to job, and one API call. The lookup has a unit test (`node --test`) that runs in CI.

## Project layout (planned)

```
config/spots.yaml          spots and directions
config/settings.yaml       thresholds
wing_alert/
  config.py                load + validate YAML
  forecast.py              Open-Meteo client
  scoring.py               good hours, windows, ranking
  message.py               alert text
  whatsapp.py              CallMeBot sender
  state.py                 state.json read/write, change detection
  main.py                  wiring: build parts, run the daily job
tests/
.github/workflows/daily.yml
trigger/                   Cloudflare Worker that starts the jobs (slice 7)
```

Python 3.12+, `uv`, `httpx`, `pyyaml`, `pytest`, `respx`, `ruff`. Later: `jinja2` (slice 2), `matplotlib` (slice 3).

## Setup David does once

1. Register with CallMeBot: add their number, send "I allow callmebot to send me messages", and receive the API key.
2. Add the repo secret `WHATSAPP_RECIPIENTS`: one `phone:apikey` pair per line (David first, crew members as they register).
3. Turn on GitHub Pages with "GitHub Actions" as the source (slice 2).
4. Create a fine-grained GitHub token (Settings → Developer settings → Fine-grained tokens): repository access **only `daplein/wing-alert`**, permission **Actions: Read and write**, the longest expiry allowed. Put its expiry date in a calendar (slice 7).
5. Create a free Cloudflare account. In `trigger/`, run `npx wrangler login`, then `npx wrangler deploy`, then `npx wrangler secret put GITHUB_TOKEN` (paste the token) (slice 7).

## Non-goals

- No app, no server, no accounts.
- No checking against Windguru or other forecasts. Spot checks are done by hand.
- No WhatsApp groups (not possible with CallMeBot).

## Future work

- Telegram group with the map image itself.
- Model agreement: compare several models (ICON, UKMO, HARMONIE) and show "3/3 agree".
- Met Éireann HARMONIE point forecast as an extra source.
- Live observations: Marine Institute buoys (M2, M5), the Dublin Bay / Dún Laoghaire buoy near Seapoint. Use them in the weekly "forecast vs what happened".
- **Patterns:** explore the archive and years of Open-Meteo historical data, e.g. "the wind backs northerly in spring afternoons" (likely sea breeze).
- Crew session log (where, when, how it was) to tune thresholds per spot.
- Suggest where to park and launch by wind direction (e.g. Arklow: P1 in north-easterly, P2 in southerly, P3 when it's 20 kn+ or the shore break is big).
- Seasonal notes from the spot guide to test against the data, e.g. Arklow spring north-westerlies that last for weeks, mostly southerly summers.
- Animated wind map, or a full wind field over the sea.
- WhatsApp images and groups through Meta's official Cloud API.

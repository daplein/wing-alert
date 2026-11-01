# wing-alert

Wingfoiling conditions for the Wicklow coast. A scheduled GitHub Action checks the forecast for the crew's spots and sends a short WhatsApp alert when there's a rideable window.

**Daily report:** https://daplein.github.io/wing-alert/ (forecast table, wind map, tides and shore break warnings, spot guides, weekly reports)

The spec is [docs/specs/wing-alert.md](docs/specs/wing-alert.md). Spot guides are in [docs/spots/](docs/spots/).

## Run it

```bash
uv sync
uv run python -m wing_alert --dry-run   # print today's alert, send nothing
uv run python -m wing_alert.weekly        # weekly summary for the last 7 days
uv run python -m wing_alert.site          # build the site from data/ into _site/
uv run pytest                           # tests + coverage
```

Spots and thresholds live in [config/](config/).

## Get the alerts on WhatsApp

1. Register with [CallMeBot](https://www.callmebot.com/blog/free-api-whatsapp-messages/) and get your API key.
2. Add a line `phone:apikey` to the repo secret `WHATSAPP_RECIPIENTS` (one line per person).

Without that secret, the daily job only prints the alert in its log.

Forecast data: [Open-Meteo](https://open-meteo.com/).

## License

MIT

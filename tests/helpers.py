from datetime import date, datetime, timedelta

from wing_alert.config import Settings, Spot
from wing_alert.forecast import Daylight, HourForecast, SpotForecast
from wing_alert.scoring import Window

DAY = date(2026, 11, 6)
MORNING = datetime(2026, 11, 6, 7, 0)
SUNRISE = datetime(2026, 11, 6, 7, 30)
SUNSET = datetime(2026, 11, 6, 16, 50)

ARKLOW = Spot("arklow", "Arklow South Beach", 52.79, -6.14, 337, 202)
SEAPOINT = Spot("seapoint", "Seapoint", 53.30, -6.16, 260, 90, sheltered=True)
SETTINGS = Settings()


def hours(start: datetime, winds: list[float], gust: float = 25, direction: float = 70):
    return [
        HourForecast(start + timedelta(hours=i), wind, gust, direction)
        for i, wind in enumerate(winds)
    ]


def forecast(spot: Spot, hour_list: list[HourForecast]) -> SpotForecast:
    days = {hour.time.date() for hour in hour_list} | {DAY}
    daylight = {
        day: Daylight(
            SUNRISE.replace(year=day.year, month=day.month, day=day.day),
            SUNSET.replace(year=day.year, month=day.month, day=day.day),
        )
        for day in days
    }
    return SpotForecast(spot, hour_list, daylight)


def window(spot: Spot, start: datetime, winds: list[float], **kwargs) -> Window:
    return Window(spot, hours(start, winds, **kwargs))


def open_meteo_payload(start: datetime, winds: list[float | None], direction: float = 70):
    times = [(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(len(winds))]
    return {
        "hourly": {
            "time": times,
            "wind_speed_10m": winds,
            "wind_gusts_10m": [None if w is None else w + 6 for w in winds],
            "wind_direction_10m": [direction] * len(winds),
        },
        "daily": {
            "time": [start.date().isoformat()],
            "sunrise": [SUNRISE.strftime("%Y-%m-%dT%H:%M")],
            "sunset": [SUNSET.strftime("%Y-%m-%dT%H:%M")],
        },
    }


def sea_payload(start: datetime, waves: list[float | None], period: float = 6):
    times = [(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(len(waves))]
    return {
        "hourly": {
            "time": times,
            "wave_height": waves,
            "wave_period": [period] * len(waves),
            "swell_wave_period": [period] * len(waves),
        }
    }


def tide_csv(start_utc: datetime, levels: list[float], step_minutes: int = 30) -> str:
    """An ERDDAP CSV answer: header, units, then one row per level."""
    rows = ["time,Water_Level", "UTC,m"]
    for index, level in enumerate(levels):
        when = start_utc + timedelta(minutes=step_minutes * index)
        rows.append(f"{when:%Y-%m-%dT%H:%M:%SZ},{level}")
    return "\n".join(rows) + "\n"

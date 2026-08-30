"""
Open-Meteo Weather API Integration.
Provides free, no-API-key weather forecasts for destination cities.
"""

import json
import logging
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

# WMO Weather Interpretation Codes (WW)
WMO_CODE_MAP: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def _map_wmo_code(code: int | None) -> str:
    if code is None:
        return "Clear / Mild"
    return WMO_CODE_MAP.get(code, "Partly cloudy")


def get_forecast(city: str, days: int = 5) -> list[dict[str, Any]]:
    """
    Fetches real weather forecast for a given city from Open-Meteo.
    Returns a list of daily forecast dictionaries containing date, condition,
    temp_high, temp_low, and rain_probability.

    Raises Exception on network/API failure so callers can catch and handle fallback.
    """
    clean_city = city.strip()
    if not clean_city:
        raise ValueError("City name cannot be empty")

    encoded_city = urllib.parse.quote(clean_city)
    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_city}&count=1"

    req = urllib.request.Request(
        geo_url,
        headers={"User-Agent": "AITripPlanner/1.0"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        geo_data = json.loads(resp.read().decode("utf-8"))

    results = geo_data.get("results")
    if not results or not isinstance(results, list):
        raise ValueError(f"City '{clean_city}' not found in Open-Meteo geocoding database")

    first_hit = results[0]
    lat = first_hit.get("latitude")
    lon = first_hit.get("longitude")

    if lat is None or lon is None:
        raise ValueError(f"Coordinates missing for city '{clean_city}'")

    forecast_days = max(1, min(days, 14))
    forecast_url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&"
        f"daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max&"
        f"timezone=auto&forecast_days={forecast_days}"
    )

    req_fc = urllib.request.Request(
        forecast_url,
        headers={"User-Agent": "AITripPlanner/1.0"},
    )
    with urllib.request.urlopen(req_fc, timeout=10) as resp_fc:
        fc_data = json.loads(resp_fc.read().decode("utf-8"))

    daily = fc_data.get("daily", {})
    times = daily.get("time", [])
    codes = daily.get("weathercode", [])
    t_max = daily.get("temperature_2m_max", [])
    t_min = daily.get("temperature_2m_min", [])
    rain_probs = daily.get("precipitation_probability_max", [])

    forecast_list: list[dict[str, Any]] = []
    for i in range(len(times)):
        date_str = times[i]
        code = codes[i] if i < len(codes) else None
        high = float(t_max[i]) if i < len(t_max) and t_max[i] is not None else 30.0
        low = float(t_min[i]) if i < len(t_min) and t_min[i] is not None else 20.0
        rain_p = int(rain_probs[i]) if i < len(rain_probs) and rain_probs[i] is not None else 0

        forecast_list.append({
            "date": date_str,
            "condition": _map_wmo_code(code),
            "temp_high": high,
            "temp_low": low,
            "rain_probability": rain_p,
        })

    return forecast_list


def format_forecast_summary(forecast: list[dict[str, Any]] | None) -> str:
    """
    Formats a list of daily forecast dicts into a clean text summary for agent prompt context.
    """
    if not forecast:
        return "Weather data unavailable (seasonal weather guidelines apply)."

    lines = []
    for idx, day in enumerate(forecast, 1):
        d_str = day.get("date", f"Day {idx}")
        cond = day.get("condition", "Mild")
        high = day.get("temp_high", 30)
        low = day.get("temp_low", 20)
        rain_p = day.get("rain_probability", 0)
        lines.append(f"Day {idx} ({d_str}): {cond}, High {high:.1f}°C / Low {low:.1f}°C, Rain Probability: {rain_p}%")

    return "\n".join(lines)

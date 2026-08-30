"""
Unit tests for Open-Meteo weather tools integration and failure fallback resiliency.
"""

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest
from trip_planner.tools.weather_tools import format_forecast_summary, get_forecast


def test_get_forecast_successful_parse():
    """Verifies forecast fetching and WMO weathercode parsing with mocked HTTP responses."""
    mock_geo_resp = json.dumps({
        "results": [{"latitude": 17.6868, "longitude": 83.2185}]
    }).encode("utf-8")

    mock_fc_resp = json.dumps({
        "daily": {
            "time": ["2026-08-30", "2026-08-31"],
            "weathercode": [0, 61],
            "temperature_2m_max": [32.5, 29.0],
            "temperature_2m_min": [24.0, 23.5],
            "precipitation_probability_max": [10, 75],
        }
    }).encode("utf-8")

    mock_geo = MagicMock()
    mock_geo.read.return_value = mock_geo_resp
    mock_geo.__enter__.return_value = mock_geo

    mock_fc = MagicMock()
    mock_fc.read.return_value = mock_fc_resp
    mock_fc.__enter__.return_value = mock_fc

    with patch("urllib.request.urlopen", side_effect=[mock_geo, mock_fc]):
        forecast = get_forecast("Visakhapatnam", days=2)

        assert isinstance(forecast, list)
        assert len(forecast) == 2
        assert forecast[0]["date"] == "2026-08-30"
        assert forecast[0]["condition"] == "Clear sky"
        assert forecast[0]["temp_high"] == 32.5
        assert forecast[0]["rain_probability"] == 10

        assert forecast[1]["date"] == "2026-08-31"
        assert forecast[1]["condition"] == "Slight rain"
        assert forecast[1]["rain_probability"] == 75


def test_get_forecast_city_not_found_raises():
    """Verifies that empty/invalid geocoding results raise a ValueError."""
    mock_geo_resp = json.dumps({"results": []}).encode("utf-8")
    mock_geo = MagicMock()
    mock_geo.read.return_value = mock_geo_resp
    mock_geo.__enter__.return_value = mock_geo

    with patch("urllib.request.urlopen", return_value=mock_geo):
        with pytest.raises(ValueError, match="not found"):
            get_forecast("NonExistentCityXYZ123", days=2)


def test_format_forecast_summary():
    """Verifies forecast formatting summary string for agent prompt context."""
    forecast = [
        {"date": "2026-08-30", "condition": "Clear sky", "temp_high": 33.0, "temp_low": 24.0, "rain_probability": 5},
        {"date": "2026-08-31", "condition": "Moderate rain", "temp_high": 28.5, "temp_low": 22.0, "rain_probability": 80},
    ]

    summary = format_forecast_summary(forecast)
    assert "Day 1 (2026-08-30): Clear sky" in summary
    assert "Rain Probability: 80%" in summary

    empty_summary = format_forecast_summary(None)
    assert "Weather data unavailable" in empty_summary


def test_weather_api_failure_fallback_resiliency():
    """
    CRITICAL RESILIENCY TEST:
    Simulates Open-Meteo network/HTTP failure (URLError/HTTPError) and verifies that
    get_forecast raises an exception, allowing app.py's try/except to catch it cleanly
    and fall back to 'Weather data unavailable' without crashing the job.
    """
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network unreachable")):
        with pytest.raises(Exception):
            get_forecast("Hyderabad", days=3)

    # Verify fallback formatting
    fallback_text = format_forecast_summary(None)
    assert "Weather data unavailable" in fallback_text

import os
from unittest.mock import MagicMock, patch

import pytest

from multi_tool_agent.tools import (
    evaluate_best_usage_windows,
    get_carbon_intensity,
    get_carbon_intensity_forecast,
)


def test_evaluate_best_usage_windows_requires_two_points():
    result = evaluate_best_usage_windows(
        [{"carbonIntensity": 100, "datetime": "2026-05-08T00:00:00.000Z"}]
    )
    assert "error" in result


def test_evaluate_best_usage_windows_daytime_best_when_available():
    forecast = [
        {"carbonIntensity": 320, "datetime": "2026-05-08T00:00:00.000Z"},
        {"carbonIntensity": 300, "datetime": "2026-05-08T01:00:00.000Z"},
        {"carbonIntensity": 220, "datetime": "2026-05-08T07:00:00.000Z"},
        {"carbonIntensity": 180, "datetime": "2026-05-08T08:00:00.000Z"},
    ]

    result = evaluate_best_usage_windows(forecast)

    assert result["best_overall"]["start_hour"] == "07:00"
    assert result["is_best_during_daytime"] is True


@patch("multi_tool_agent.tools.request.urlopen")
def test_get_carbon_intensity_parses_success_response(mock_urlopen):
    payload = (
        b'{"zone":"IE","forecast":[{"carbonIntensity":311,'
        b'"datetime":"2026-05-08T21:00:00.000Z"}]}'
    )
    mock_response = MagicMock()
    mock_response.read.return_value = payload
    mock_urlopen.return_value.__enter__.return_value = mock_response

    result = get_carbon_intensity("ie")

    assert result["zone"] == "IE"
    assert isinstance(result["forecast"], list)
    assert result["forecast"][0]["carbonIntensity"] == 311


@patch("multi_tool_agent.tools.request.urlopen")
def test_get_carbon_intensity_forecast_response_shape(mock_urlopen):
    payload = (
        b'{"zone":"IE","forecast":[{"carbonIntensity":351,'
        b'"datetime":"2026-05-08T21:00:00.000Z"}],'
        b'"updatedAt":"2026-05-08T21:10:02.249Z",'
        b'"temporalGranularity":"hourly"}'
    )
    mock_response = MagicMock()
    mock_response.read.return_value = payload
    mock_urlopen.return_value.__enter__.return_value = mock_response

    result = get_carbon_intensity_forecast("IE")

    assert result["zone"] == "IE"
    assert isinstance(result["forecast"], list)
    assert result["forecast"][0]["carbonIntensity"] == 351
    assert result["temporalGranularity"] == "hourly"


@patch("multi_tool_agent.tools.request.urlopen")
def test_get_carbon_intensity_forecast_parses_success_response(mock_urlopen):
    payload = (
        b'{"zone":"IE","forecast":[{"carbonIntensity":320,'
        b'"datetime":"2026-05-08T00:00:00.000Z"}]}'
    )
    mock_response = MagicMock()
    mock_response.read.return_value = payload
    mock_urlopen.return_value.__enter__.return_value = mock_response

    result = get_carbon_intensity_forecast("IE", horizon_hours=24)

    assert result["zone"] == "IE"
    assert isinstance(result["forecast"], list)
    assert result["forecast"][0]["carbonIntensity"] == 320


def test_live_electricity_maps_forecast_smoke():
    api_key = os.environ.get("ELEC_MAP_API_KEY")
    if not api_key:
        pytest.skip("ELEC_MAP_API_KEY not set")

    result = get_carbon_intensity_forecast("IE", horizon_hours=2)

    if "error" in result:
        if "403" in result["error"] or "Forbidden" in result["error"]:
            pytest.skip("Electricity Maps key is not authorized for this endpoint")
        pytest.fail(f"Electricity Maps live call failed: {result['error']}")

    assert result["zone"] == "IE"
    assert isinstance(result.get("forecast"), list)

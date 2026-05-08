from __future__ import annotations

import json
import os
from typing import Any
from urllib import parse, request
from urllib.error import HTTPError, URLError

from dotenv import load_dotenv

from .observability import store

load_dotenv()

DEFAULT_ELEC_MAP_BASE_URL = "https://api.electricitymaps.com/v3"


def _get_api_key() -> str:
    return os.environ.get("ELEC_MAP_API_KEY", "")


def _get_base_url() -> str:
    return os.environ.get("ELEC_MAP_BASE_URL", DEFAULT_ELEC_MAP_BASE_URL)


def _request_json(path: str, params: dict[str, Any]) -> dict[str, Any]:
    query = parse.urlencode(params)
    base_url = _get_base_url().rstrip("/")
    url = f"{base_url}/{path}?{query}"
    req = request.Request(
        url=url,
        method="GET",
        headers={"auth-token": _get_api_key()},
    )
    with request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _normalize_zone(zone: str) -> str:
    return zone.strip().upper()


def get_carbon_intensity(zone: str) -> dict[str, Any]:
    started = store.start()
    normalized_zone = _normalize_zone(zone)
    try:
        result = _request_json(
            "carbon-intensity/forecast",
            {"zone": normalized_zone},
        )
        store.finish(
            "get_carbon_intensity",
            started,
            "ok",
            {"zone": normalized_zone},
        )
        return result
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        store.finish(
            "get_carbon_intensity",
            started,
            "error",
            {"zone": normalized_zone, "error": str(exc)},
        )
        return {"error": str(exc), "zone": normalized_zone}


def get_carbon_intensity_forecast(
    zone: str,
    horizon_hours: int | None = None,
) -> dict[str, Any]:
    started = store.start()
    normalized_zone = _normalize_zone(zone)
    params: dict[str, Any] = {"zone": normalized_zone}
    safe_horizon: int | None = None
    if horizon_hours is not None:
        safe_horizon = min(max(int(horizon_hours), 1), 72)
        params["horizonHours"] = safe_horizon
    try:
        result = _request_json("carbon-intensity/forecast", params)
        store.finish(
            "get_carbon_intensity_forecast",
            started,
            "ok",
            {
                "zone": normalized_zone,
                "horizon_hours": safe_horizon,
            },
        )
        return result
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        store.finish(
            "get_carbon_intensity_forecast",
            started,
            "error",
            {
                "zone": normalized_zone,
                "horizon_hours": safe_horizon,
                "error": str(exc),
            },
        )
        return {"error": str(exc), "zone": normalized_zone}


def evaluate_best_usage_windows(
    forecast: list[dict[str, Any]],
    daytime_start_hour: int = 7,
    daytime_end_hour: int = 22,
) -> dict[str, Any]:
    if len(forecast) < 2:
        return {"error": "forecast must contain at least 2 points"}
    best_idx = min(
        range(len(forecast) - 1),
        key=lambda i: (
            forecast[i]["carbonIntensity"]
            + forecast[i + 1]["carbonIntensity"]
        ),
    )
    current_intensity = forecast[0]["carbonIntensity"]
    start_hour = forecast[best_idx]["datetime"][11:13]
    end_hour = forecast[best_idx + 1]["datetime"][11:13]
    best_intensity = (
        forecast[best_idx]["carbonIntensity"]
        + forecast[best_idx + 1]["carbonIntensity"]
    ) / 2
    result: dict[str, Any] = {
        "current": {
            "carbon_intensity_gCO2_per_kWh": current_intensity,
            "datetime": forecast[0]["datetime"],
        },
        "best_overall": {
            "start_hour": f"{start_hour}:00",
            "end_hour": f"{end_hour}:00",
            "carbon_intensity_gCO2_per_kWh": best_intensity,
            "savings_vs_now_percent": round(
                (1 - best_intensity / current_intensity) * 100,
                1,
            ),
        },
        "best_daytime": None,
        "is_best_during_daytime": (
            daytime_start_hour <= int(start_hour) < daytime_end_hour
        ),
    }
    if result["is_best_during_daytime"]:
        return result
    daytime_indices = [
        i
        for i in range(len(forecast) - 1)
        if daytime_start_hour <= int(forecast[i]["datetime"][11:13]) < daytime_end_hour
        and daytime_start_hour
        <= int(forecast[i + 1]["datetime"][11:13])
        < daytime_end_hour
    ]
    if not daytime_indices:
        return result
    best_day_idx = min(
        daytime_indices,
        key=lambda i: (
            forecast[i]["carbonIntensity"]
            + forecast[i + 1]["carbonIntensity"]
        ),
    )
    day_start_hour = forecast[best_day_idx]["datetime"][11:13]
    day_end_hour = forecast[best_day_idx + 1]["datetime"][11:13]
    day_intensity = (
        forecast[best_day_idx]["carbonIntensity"]
        + forecast[best_day_idx + 1]["carbonIntensity"]
    ) / 2
    result["best_daytime"] = {
        "start_hour": f"{day_start_hour}:00",
        "end_hour": f"{day_end_hour}:00",
        "carbon_intensity_gCO2_per_kWh": day_intensity,
        "savings_vs_now_percent": round(
            (1 - day_intensity / current_intensity) * 100,
            1,
        ),
    }
    return result


def get_best_usage_windows(
    zone: str,
    daytime_start_hour: int = 7,
    daytime_end_hour: int = 22,
) -> dict[str, Any]:
    started = store.start()
    forecast_data = get_carbon_intensity_forecast(zone=zone, horizon_hours=24)
    if "error" in forecast_data:
        store.finish(
            "get_best_usage_windows",
            started,
            "error",
            {
                "zone": zone,
                "error": forecast_data["error"],
            },
        )
        return forecast_data
    result = evaluate_best_usage_windows(
        forecast_data.get("forecast", []),
        daytime_start_hour=daytime_start_hour,
        daytime_end_hour=daytime_end_hour,
    )
    if "error" in result:
        store.finish(
            "get_best_usage_windows",
            started,
            "error",
            {
                "zone": zone,
                "error": result["error"],
            },
        )
        return result
    store.finish(
        "get_best_usage_windows",
        started,
        "ok",
        {"zone": _normalize_zone(zone)},
    )
    return result


def get_monitoring_snapshot() -> dict[str, Any]:
    started = store.start()
    result = store.metrics_snapshot()
    store.finish(
        "get_monitoring_snapshot",
        started,
        "ok",
        {"tools": len(result.get("tools", {}))},
    )
    return result


def get_recent_tool_traces(limit: int = 20) -> dict[str, Any]:
    started = store.start()
    traces = store.recent_traces(limit=limit)
    store.finish(
        "get_recent_tool_traces",
        started,
        "ok",
        {"returned": len(traces)},
    )
    return {"traces": traces}


def run_tool_self_test() -> dict[str, Any]:
    started = store.start()
    sample = [
        {"carbonIntensity": 300, "datetime": "2026-05-08T00:00:00.000Z"},
        {"carbonIntensity": 200, "datetime": "2026-05-08T01:00:00.000Z"},
        {"carbonIntensity": 150, "datetime": "2026-05-08T07:00:00.000Z"},
        {"carbonIntensity": 130, "datetime": "2026-05-08T08:00:00.000Z"},
    ]
    result = evaluate_best_usage_windows(sample)
    passed = result.get("best_overall", {}).get("start_hour") == "07:00"
    payload = {"passed": passed, "result": result}
    status = "ok" if passed else "error"
    store.finish(
        "run_tool_self_test",
        started,
        status,
        {"passed": passed},
    )
    return payload

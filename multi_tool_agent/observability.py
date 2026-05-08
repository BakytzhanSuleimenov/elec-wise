from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from statistics import mean
from threading import Lock
from time import perf_counter
from typing import Any


@dataclass
class TraceEvent:
    tool: str
    status: str
    duration_ms: float
    details: dict[str, Any]


class ObservabilityStore:
    def __init__(self, trace_limit: int = 200):
        self._lock = Lock()
        self._counters: dict[str, dict[str, int]] = defaultdict(lambda: {"ok": 0, "error": 0})
        self._latencies: dict[str, list[float]] = defaultdict(list)
        self._traces: deque[TraceEvent] = deque(maxlen=trace_limit)

    def start(self) -> float:
        return perf_counter()

    def finish(self, tool: str, started_at: float, status: str, details: dict[str, Any] | None = None) -> None:
        elapsed_ms = (perf_counter() - started_at) * 1000
        with self._lock:
            self._counters[tool][status] = self._counters[tool].get(status, 0) + 1
            self._latencies[tool].append(elapsed_ms)
            self._traces.append(TraceEvent(tool=tool, status=status, duration_ms=elapsed_ms, details=details or {}))

    def metrics_snapshot(self) -> dict[str, Any]:
        with self._lock:
            tool_stats: dict[str, Any] = {}
            for tool, status_counts in self._counters.items():
                latencies = self._latencies.get(tool, [])
                tool_stats[tool] = {
                    "calls_total": sum(status_counts.values()),
                    "ok_total": status_counts.get("ok", 0),
                    "error_total": status_counts.get("error", 0),
                    "avg_latency_ms": round(mean(latencies), 2) if latencies else 0.0,
                    "p95_latency_ms": round(sorted(latencies)[int(0.95 * (len(latencies) - 1))], 2) if latencies else 0.0,
                }
            return {"tools": tool_stats}

    def recent_traces(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            selected = list(self._traces)[-max(1, min(limit, len(self._traces))):]
            return [
                {
                    "tool": t.tool,
                    "status": t.status,
                    "duration_ms": round(t.duration_ms, 2),
                    "details": t.details,
                }
                for t in selected
            ]


store = ObservabilityStore()

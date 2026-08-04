"""In-process counters + fixed-bucket histograms (PRD §8.5)."""

from __future__ import annotations

import threading
from collections.abc import Mapping

_BUCKETS_MS = (5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000)


def _label_key(labels: Mapping[str, object]) -> str:
    if not labels:
        return ""
    parts = [f"{k}={labels[k]}" for k in sorted(labels)]
    return ",".join(parts)


class ProcessMetrics:
    """Thread-safe process metrics registry."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._enabled = True
        self._counters: dict[tuple[str, str], int] = {}
        self._histograms: dict[tuple[str, str], list[int]] = {}

    def reset(self, *, enabled: bool = True) -> None:
        with self._lock:
            self._enabled = enabled
            self._counters.clear()
            self._histograms.clear()

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._enabled = enabled

    def inc(self, name: str, **labels: object) -> None:
        if not self._enabled:
            return
        key = (name, _label_key(labels))
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + 1

    def observe_ms(self, name: str, value: float, **labels: object) -> None:
        if not self._enabled:
            return
        key = (name, _label_key(labels))
        with self._lock:
            buckets = self._histograms.setdefault(key, [0] * (len(_BUCKETS_MS) + 1))
            placed = False
            for i, edge in enumerate(_BUCKETS_MS):
                if value <= edge:
                    buckets[i] += 1
                    placed = True
                    break
            if not placed:
                buckets[-1] += 1

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            counters = {
                f"{name}|{lk}" if lk else name: count
                for (name, lk), count in self._counters.items()
            }
            histograms: dict[str, object] = {}
            for (name, lk), buckets in self._histograms.items():
                key = f"{name}|{lk}" if lk else name
                edges = list(_BUCKETS_MS) + ["inf"]
                histograms[key] = {str(edges[i]): buckets[i] for i in range(len(buckets))}
            return {"counters": counters, "histograms": histograms}


metrics = ProcessMetrics()

__all__ = ["ProcessMetrics", "metrics"]

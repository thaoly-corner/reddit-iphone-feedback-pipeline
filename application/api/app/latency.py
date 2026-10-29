"""In-memory latency ledger per route, used as runtime performance evidence."""
from __future__ import annotations

import statistics
import time
from collections import defaultdict, deque

_samples: dict[str, deque] = defaultdict(lambda: deque(maxlen=500))
_started = time.time()


def record(route: str, total_ms: float, db_ms: float, cache_hit: bool) -> None:
    _samples[route].append((total_ms, db_ms, cache_hit))


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, round(p / 100 * (len(s) - 1))))
    return round(s[k], 2)


def latency_report() -> dict:
    routes = []
    for route, dq in sorted(_samples.items()):
        totals = [t for t, _, _ in dq]
        dbs = [d for _, d, _ in dq]
        hits = sum(1 for _, _, h in dq if h)
        routes.append({
            "route": route, "n": len(dq), "mean_ms": round(statistics.fmean(totals), 2),
            "p50_ms": _pct(totals, 50), "p95_ms": _pct(totals, 95), "p99_ms": _pct(totals, 99),
            "max_ms": round(max(totals), 2), "db_mean_ms": round(statistics.fmean(dbs), 2) if dbs else 0.0,
            "cache_hit_rate_pct": round(hits / len(dq) * 100, 1),
        })
    all_totals = [t for dq in _samples.values() for t, _, _ in dq]
    return {
        "uptime_s": round(time.time() - _started), "requests": len(all_totals),
        "overall": {"p50_ms": _pct(all_totals, 50), "p95_ms": _pct(all_totals, 95), "p99_ms": _pct(all_totals, 99)},
        "routes": routes,
    }

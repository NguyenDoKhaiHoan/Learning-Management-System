"""Low-cardinality in-process metrics for health and hardening checks."""

from collections import Counter
from threading import Lock


class Metrics:
    def __init__(self):
        self._lock = Lock()
        self._requests: Counter[tuple[str, int]] = Counter()
        self._request_seconds: Counter[str] = Counter()

    def observe_http(self, route: str, status: int, duration_ms: float) -> None:
        route = route if route.startswith("/") else "unmatched"
        with self._lock:
            self._requests[(route, status)] += 1
            self._request_seconds[route] += duration_ms / 1000

    def prometheus(self) -> str:
        with self._lock:
            requests = dict(self._requests)
            durations = dict(self._request_seconds)
        lines = [
            "# HELP lms_http_requests_total HTTP requests by route and status.",
            "# TYPE lms_http_requests_total counter",
        ]
        for (route, status), count in sorted(requests.items()):
            lines.append(
                f'lms_http_requests_total{{route="{_label(route)}",status="{status}"}} {count}'
            )
        lines.extend(
            [
                "# HELP lms_http_request_duration_seconds_total Total request duration.",
                "# TYPE lms_http_request_duration_seconds_total counter",
            ]
        )
        for route, seconds in sorted(durations.items()):
            lines.append(
                f'lms_http_request_duration_seconds_total{{route="{_label(route)}"}} '
                f"{seconds:.6f}"
            )
        return "\n".join(lines) + "\n"


def _label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

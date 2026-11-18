"""Health check registry for ``GET /healthz``.

A health endpoint that always returns 200 is decoration. This registry runs the
real dependencies, separates *critical* checks (database, broker) from
*optional* ones (third-party API, cache warmup), and maps the result to an HTTP
status an orchestrator can act on.

A failed optional check degrades the report but keeps the pod in the load
balancer rotation; a failed critical check returns 503 so Kubernetes restarts it.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

Check = Callable[[], Any] | Callable[[], Awaitable[Any]]


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    critical: bool = True
    detail: str | None = None
    latency_ms: float = 0.0


@dataclass
class HealthReport:
    results: list[CheckResult] = field(default_factory=list)

    @property
    def status(self) -> str:
        if any(not result.ok and result.critical for result in self.results):
            return "failing"
        if any(not result.ok for result in self.results):
            return "degraded"
        return "ok"

    @property
    def http_status(self) -> int:
        return 503 if self.status == "failing" else 200

    @property
    def ok(self) -> bool:
        return self.http_status == 200

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "checks": [
                {
                    "name": result.name,
                    "ok": result.ok,
                    "critical": result.critical,
                    "detail": result.detail,
                    "latency_ms": round(result.latency_ms, 2),
                }
                for result in self.results
            ],
        }


class HealthRegistry:
    def __init__(self) -> None:
        self._checks: list[tuple[str, Check, bool]] = []

    def register(self, name: str, check: Check, critical: bool = True) -> None:
        self._checks.append((name, check, critical))

    def _evaluate(self, name: str, check: Check, critical: bool,
                  started: float, error: BaseException | None) -> CheckResult:
        latency = (time.perf_counter() - started) * 1000
        if error is None:
            return CheckResult(name, True, critical, None, latency)
        return CheckResult(name, False, critical, f"{type(error).__name__}: {error}", latency)

    def run(self) -> HealthReport:
        """Run synchronous checks. Awaitable checks are skipped."""
        results: list[CheckResult] = []
        for name, check, critical in self._checks:
            started = time.perf_counter()
            try:
                outcome = check()
            except Exception as exc:  # noqa: BLE001 - a failing check must not crash /healthz
                results.append(self._evaluate(name, check, critical, started, exc))
                continue
            if asyncio.iscoroutine(outcome):
                outcome.close()
                results.append(
                    CheckResult(name, False, critical, "coroutine check used with run()", 0.0)
                )
                continue
            results.append(self._evaluate(name, check, critical, started, None))
        return HealthReport(results)

    async def run_async(self, timeout: float = 5.0) -> HealthReport:
        """Run every check concurrently with a per-check timeout."""
        tasks = []
        for name, check, critical in self._checks:
            tasks.append(self._run_one(name, check, critical, timeout))
        return HealthReport(list(await asyncio.gather(*tasks)))

    async def _run_one(self, name: str, check: Check, critical: bool,
                       timeout: float) -> CheckResult:
        started = time.perf_counter()
        try:
            outcome = check()
            if asyncio.iscoroutine(outcome):
                await asyncio.wait_for(outcome, timeout=timeout)
            elif not callable(outcome):
                pass
        except asyncio.TimeoutError:
            return CheckResult(name, False, critical, f"timed out after {timeout}s",
                               (time.perf_counter() - started) * 1000)
        except Exception as exc:  # noqa: BLE001
            return self._evaluate(name, check, critical, started, exc)
        return self._evaluate(name, check, critical, started, None)

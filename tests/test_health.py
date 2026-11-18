import asyncio
import unittest

from patterns.health import HealthRegistry


class HealthSyncTests(unittest.TestCase):
    def setUp(self):
        self.registry = HealthRegistry()

    def test_all_green(self):
        self.registry.register("db", lambda: True)
        self.registry.register("redis", lambda: True)
        report = self.registry.run()
        self.assertEqual(report.status, "ok")
        self.assertEqual(report.http_status, 200)
        self.assertTrue(report.ok)

    def test_critical_failure_returns_503(self):
        self.registry.register("db", lambda: True)
        self.registry.register("broker", self._boom)
        report = self.registry.run()
        self.assertEqual(report.status, "failing")
        self.assertEqual(report.http_status, 503)
        self.assertFalse(report.ok)

    def test_optional_failure_degrades_but_stays_up(self):
        self.registry.register("db", lambda: True)
        self.registry.register("analytics", self._boom, critical=False)
        report = self.registry.run()
        self.assertEqual(report.status, "degraded")
        self.assertEqual(report.http_status, 200)

    def test_failure_detail_is_reported(self):
        self.registry.register("db", self._boom, critical=False)
        result = self.registry.run().results[0]
        self.assertFalse(result.ok)
        self.assertIn("ConnectionError", result.detail)

    def test_latency_is_measured(self):
        self.registry.register("db", lambda: True)
        self.assertGreaterEqual(self.registry.run().results[0].latency_ms, 0.0)

    def test_as_dict_shape(self):
        self.registry.register("db", lambda: True)
        payload = self.registry.run().as_dict()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["checks"][0]["name"], "db")
        self.assertIn("latency_ms", payload["checks"][0])

    def _boom(self):
        raise ConnectionError("connection refused")


class HealthAsyncTests(unittest.TestCase):
    def setUp(self):
        self.registry = HealthRegistry()

    def test_async_checks_run_concurrently(self):
        async def slow_ok():
            await asyncio.sleep(0.01)
            return True

        self.registry.register("db", slow_ok)
        self.registry.register("sync", lambda: True)

        report = asyncio.run(self.registry.run_async())
        self.assertEqual(report.status, "ok")
        self.assertEqual(len(report.results), 2)

    def test_async_timeout_is_failing(self):
        async def hangs():
            await asyncio.sleep(5)

        self.registry.register("db", hangs)
        report = asyncio.run(self.registry.run_async(timeout=0.01))
        self.assertEqual(report.http_status, 503)
        self.assertIn("timed out", report.results[0].detail)

    def test_sync_exception_in_async_run(self):
        def broken():
            raise TimeoutError("db pool exhausted")

        self.registry.register("db", broken)
        report = asyncio.run(self.registry.run_async())
        self.assertEqual(report.status, "failing")


if __name__ == "__main__":
    unittest.main()

import unittest

from patterns.circuit_breaker import CircuitBreaker, CircuitOpenError, State


class FakeClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class CircuitBreakerTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.breaker = CircuitBreaker(
            failure_threshold=2, recovery_timeout=30.0, clock=self.clock
        )

    def test_starts_closed_and_allows_calls(self):
        self.assertIs(self.breaker.state, State.CLOSED)
        self.assertTrue(self.breaker.allows())

    def test_opens_after_threshold(self):
        self.breaker.record_failure()
        self.assertIs(self.breaker.state, State.CLOSED)
        self.breaker.record_failure()
        self.assertIs(self.breaker.state, State.OPEN)
        self.assertFalse(self.breaker.allows())

    def test_open_short_circuits_without_calling_upstream(self):
        self.breaker.record_failure()
        self.breaker.record_failure()

        def upstream():
            raise AssertionError("must not be called")

        with self.assertRaises(CircuitOpenError):
            self.breaker.call(upstream)

    def test_half_open_after_recovery_window(self):
        self.breaker.record_failure()
        self.breaker.record_failure()
        self.clock.now += 29.9
        self.assertIs(self.breaker.state, State.OPEN)
        self.clock.now += 0.1
        self.assertIs(self.breaker.state, State.HALF_OPEN)

    def test_successful_probe_closes(self):
        self.breaker.record_failure()
        self.breaker.record_failure()
        self.clock.now += 31
        self.assertEqual(self.breaker.call(lambda: "probe"), "probe")
        self.assertIs(self.breaker.state, State.CLOSED)

    def test_failed_probe_reopens(self):
        self.breaker.record_failure()
        self.breaker.record_failure()
        self.clock.now += 31
        self.assertIs(self.breaker.state, State.HALF_OPEN)

        def broken():
            raise ConnectionError("still down")

        with self.assertRaises(ConnectionError):
            self.breaker.call(broken)
        self.assertIs(self.breaker.state, State.OPEN)

    def test_success_resets_failure_count(self):
        self.breaker.record_failure()
        self.breaker.record_success()
        self.breaker.record_failure()
        self.assertIs(self.breaker.state, State.CLOSED)


if __name__ == "__main__":
    unittest.main()

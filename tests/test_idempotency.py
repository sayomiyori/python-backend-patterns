import unittest

from patterns.idempotency import (
    IdempotencyConflict,
    InMemoryIdempotencyStore,
    run_once,
)


class FakeClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class RunOnceTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.store = InMemoryIdempotencyStore(clock=self.clock)
        self.calls = 0

    def charge(self):
        self.calls += 1
        return {"charged": True, "n": self.calls}

    def test_first_call_executes(self):
        value, replayed = run_once(self.store, "key-1", self.charge)
        self.assertFalse(replayed)
        self.assertEqual(self.calls, 1)
        self.assertEqual(value["n"], 1)

    def test_second_call_replays_stored_result(self):
        first, _ = run_once(self.store, "key-1", self.charge)
        second, replayed = run_once(self.store, "key-1", self.charge)
        self.assertTrue(replayed)
        self.assertEqual(first, second)
        self.assertEqual(self.calls, 1)

    def test_in_flight_key_conflicts(self):
        self.store.begin("key-1", ttl=60)
        with self.assertRaises(IdempotencyConflict):
            run_once(self.store, "key-1", self.charge)
        self.assertEqual(self.calls, 0)

    def test_failure_releases_the_key(self):
        def boom():
            raise RuntimeError("gateway timeout")

        with self.assertRaises(RuntimeError):
            run_once(self.store, "key-1", boom)

        value, replayed = run_once(self.store, "key-1", self.charge)
        self.assertFalse(replayed)
        self.assertEqual(self.calls, 1)

    def test_expired_key_allows_execution_again(self):
        run_once(self.store, "key-1", self.charge, ttl=10)
        self.clock.now += 11
        value, replayed = run_once(self.store, "key-1", self.charge, ttl=10)
        self.assertFalse(replayed)
        self.assertEqual(self.calls, 2)
        self.assertEqual(value["n"], 2)


if __name__ == "__main__":
    unittest.main()

import unittest

from patterns.ttl_cache import TTLCache, ttl_cache


class FakeClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class TTLCacheTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.cache = TTLCache(maxsize=2, ttl=10, clock=self.clock)

    def test_set_and_get(self):
        self.cache.set("a", 1)
        self.assertEqual(self.cache.get("a"), 1)
        self.assertEqual(self.cache.get("missing", "fallback"), "fallback")

    def test_expires_after_ttl(self):
        self.cache.set("a", 1)
        self.clock.now += 9.9
        self.assertIn("a", self.cache)
        self.clock.now += 0.2
        self.assertIsNone(self.cache.get("a"))
        self.assertEqual(len(self.cache), 0)

    def test_evicts_least_recently_used(self):
        self.cache.set("a", 1)
        self.cache.set("b", 2)
        self.cache.get("a")
        self.cache.set("c", 3)

        self.assertEqual(self.cache.get("a"), 1)
        self.assertIsNone(self.cache.get("b"))
        self.assertEqual(self.cache.get("c"), 3)

    def test_rejects_invalid_configuration(self):
        with self.assertRaises(ValueError):
            TTLCache(maxsize=0)
        with self.assertRaises(ValueError):
            TTLCache(ttl=0)


class TtlCacheDecoratorTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.calls = 0

        @ttl_cache(maxsize=4, ttl=5, clock=self.clock)
        def expensive(value):
            self.calls += 1
            return value * 2

        self.expensive = expensive

    def test_caches_result(self):
        self.assertEqual(self.expensive(3), 6)
        self.assertEqual(self.expensive(3), 6)
        self.assertEqual(self.calls, 1)

    def test_distinguishes_arguments(self):
        self.expensive(1)
        self.expensive(2)
        self.assertEqual(self.calls, 2)

    def test_recomputes_after_expiry(self):
        self.expensive(3)
        self.clock.now += 6
        self.expensive(3)
        self.assertEqual(self.calls, 2)

    def test_keyword_arguments_are_part_of_the_key(self):
        self.expensive(3)
        self.expensive(value=3)
        self.assertEqual(self.calls, 2)


if __name__ == "__main__":
    unittest.main()

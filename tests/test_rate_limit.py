import unittest

from patterns.rate_limit import TokenBucket


class FakeClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class TokenBucketTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.bucket = TokenBucket(
            capacity=2, refill_per_second=1.0, clock=self.clock
        )

    def test_starts_full(self):
        self.assertEqual(self.bucket.tokens, 2.0)

    def test_consumes_until_empty(self):
        self.assertTrue(self.bucket.try_acquire())
        self.assertTrue(self.bucket.try_acquire())
        self.assertFalse(self.bucket.try_acquire())

    def test_refills_over_time(self):
        self.bucket.try_acquire(2)
        self.assertFalse(self.bucket.try_acquire())
        self.clock.now += 1.0
        self.assertTrue(self.bucket.try_acquire())
        self.assertFalse(self.bucket.try_acquire())

    def test_never_exceeds_capacity(self):
        self.clock.now += 1000
        self.assertEqual(self.bucket.tokens, 2.0)

    def test_acquire_times_out_when_empty(self):
        self.bucket.try_acquire(2)
        self.assertFalse(self.bucket.acquire(timeout=0.02))

    def test_acquire_succeeds_after_refill(self):
        real_time_bucket = TokenBucket(capacity=1, refill_per_second=50.0)
        self.assertTrue(real_time_bucket.try_acquire())
        self.assertTrue(real_time_bucket.acquire(timeout=1.0, poll_interval=0.005))

    def test_rejects_invalid_configuration(self):
        with self.assertRaises(ValueError):
            TokenBucket(capacity=0, refill_per_second=1.0)


if __name__ == "__main__":
    unittest.main()

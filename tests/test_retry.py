import asyncio
import unittest

from patterns.retry import RetryConfig, retry, retry_async


class RetrySyncTests(unittest.TestCase):
    def test_retries_until_success(self):
        calls = []
        delays = []

        @retry(
            config=RetryConfig(attempts=3, base_delay=1.0, max_delay=10.0, jitter=False),
            sleep=delays.append,
        )
        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise RuntimeError("boom")
            return "ok"

        self.assertEqual(flaky(), "ok")
        self.assertEqual(len(calls), 3)
        self.assertEqual(delays, [1.0, 2.0])

    def test_reraises_last_error(self):
        calls = []

        @retry(config=RetryConfig(attempts=2, jitter=False), sleep=lambda _: None)
        def always_fails():
            calls.append(1)
            raise ValueError("nope")

        with self.assertRaises(ValueError):
            always_fails()
        self.assertEqual(len(calls), 2)

    def test_success_is_not_delayed(self):
        delays = []

        @retry(config=RetryConfig(attempts=5), sleep=delays.append)
        def fine():
            return 42

        self.assertEqual(fine(), 42)
        self.assertEqual(delays, [])

    def test_unlisted_exception_is_not_retried(self):
        calls = []

        @retry(exc_types=(ConnectionError,), config=RetryConfig(attempts=3), sleep=lambda _: None)
        def wrong_error():
            calls.append(1)
            raise KeyError("not retryable")

        with self.assertRaises(KeyError):
            wrong_error()
        self.assertEqual(len(calls), 1)

    def test_jitter_respects_ceiling(self):
        cfg = RetryConfig(attempts=6, base_delay=0.5, max_delay=2.0, jitter=True)
        for attempt in range(1, 7):
            ceiling = min(2.0, 0.5 * 2 ** (attempt - 1))
            for _ in range(50):
                self.assertGreaterEqual(cfg.delay_for(attempt), 0.0)
                self.assertLessEqual(cfg.delay_for(attempt), ceiling)


class RetryAsyncTests(unittest.TestCase):
    def test_async_retry_eventually_succeeds(self):
        attempts = []
        slept = []

        async def flaky():
            attempts.append(1)
            if len(attempts) < 3:
                raise TimeoutError("slow")
            return "done"

        async def fake_sleep(delay):
            slept.append(delay)

        wrapped = retry_async(
            config=RetryConfig(attempts=3, base_delay=0.1, jitter=False),
            sleep=fake_sleep,
        )(flaky)

        self.assertEqual(asyncio.run(wrapped()), "done")
        self.assertEqual(len(attempts), 3)
        self.assertEqual(len(slept), 2)

    def test_async_gives_up(self):
        async def always_fails():
            raise ConnectionError("down")

        async def fake_sleep(_):
            return None

        wrapped = retry_async(
            config=RetryConfig(attempts=2), sleep=fake_sleep
        )(always_fails)

        with self.assertRaises(ConnectionError):
            asyncio.run(wrapped())


if __name__ == "__main__":
    unittest.main()

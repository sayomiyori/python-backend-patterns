import asyncio
import unittest

from patterns.bounded_gather import bounded_gather, map_bounded


class BoundedGatherTests(unittest.TestCase):
    def test_results_keep_input_order(self):
        async def delayed(value, delay):
            await asyncio.sleep(delay)
            return value

        async def scenario():
            return await bounded_gather(
                [delayed(1, 0.02), delayed(2, 0.0), delayed(3, 0.01)], limit=2
            )

        self.assertEqual(asyncio.run(scenario()), [1, 2, 3])

    def test_concurrency_never_exceeds_the_limit(self):
        state = {"active": 0, "peak": 0}

        async def worker():
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
            await asyncio.sleep(0.005)
            state["active"] -= 1
            return "done"

        async def scenario():
            return await bounded_gather([worker() for _ in range(20)], limit=3)

        self.assertEqual(len(asyncio.run(scenario())), 20)
        self.assertLessEqual(state["peak"], 3)

    def test_exceptions_propagate_by_default(self):
        async def boom():
            raise ValueError("nope")

        async def ok():
            return "fine"

        async def scenario():
            return await bounded_gather([ok(), boom()], limit=2)

        with self.assertRaises(ValueError):
            asyncio.run(scenario())

    def test_return_exceptions_collects_errors(self):
        async def boom():
            raise ValueError("nope")

        async def ok():
            return "fine"

        async def scenario():
            return await bounded_gather([ok(), boom()], limit=2, return_exceptions=True)

        results = asyncio.run(scenario())
        self.assertEqual(results[0], "fine")
        self.assertIsInstance(results[1], ValueError)

    def test_map_bounded_applies_the_callable(self):
        async def double(value):
            await asyncio.sleep(0)
            return value * 2

        self.assertEqual(
            asyncio.run(map_bounded(double, range(5), limit=2)), [0, 2, 4, 6, 8]
        )

    def test_empty_input(self):
        self.assertEqual(asyncio.run(bounded_gather([], limit=4)), [])

    def test_rejects_non_positive_limit(self):
        async def scenario():
            return await bounded_gather([], limit=0)

        with self.assertRaises(ValueError):
            asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()

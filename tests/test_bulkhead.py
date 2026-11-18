import threading
import time
import unittest

from patterns.bulkhead import Bulkhead, BulkheadFull


class BulkheadTests(unittest.TestCase):
    def setUp(self):
        self.bulkhead = Bulkhead("payments", limit=2)

    def test_acquires_up_to_the_limit(self):
        self.assertTrue(self.bulkhead.acquire())
        self.assertTrue(self.bulkhead.acquire())
        self.assertFalse(self.bulkhead.acquire(timeout=0))
        self.assertEqual(self.bulkhead.stats()["rejected"], 1)

    def test_release_frees_a_slot(self):
        self.bulkhead.acquire()
        self.bulkhead.acquire()
        self.bulkhead.release()
        self.assertTrue(self.bulkhead.acquire(timeout=0))

    def test_context_manager_releases_on_exception(self):
        with self.bulkhead:
            self.assertEqual(self.bulkhead.stats()["active"], 1)
        self.assertEqual(self.bulkhead.stats()["active"], 0)

        with self.assertRaises(ValueError):
            with self.bulkhead:
                raise ValueError("handler failed")

        self.assertEqual(self.bulkhead.stats()["active"], 0)

    def test_raises_when_full(self):
        self.bulkhead.acquire()
        self.bulkhead.acquire()
        with self.assertRaises(BulkheadFull):
            with self.bulkhead:
                pass

    def test_waits_for_a_slot(self):
        self.bulkhead.acquire()
        self.bulkhead.acquire()

        def free_later():
            time.sleep(0.02)
            self.bulkhead.release()

        worker = threading.Thread(target=free_later)
        worker.start()
        self.assertTrue(self.bulkhead.acquire(timeout=1.0))
        worker.join()

    def test_stats_count_completed(self):
        with self.bulkhead:
            pass
        stats = self.bulkhead.stats()
        self.assertEqual(stats["completed"], 1)
        self.assertEqual(stats["active"], 0)

    def test_rejects_invalid_limit(self):
        with self.assertRaises(ValueError):
            Bulkhead("bad", limit=0)


if __name__ == "__main__":
    unittest.main()

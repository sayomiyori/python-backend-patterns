import unittest

from patterns.outbox import InMemoryOutbox


class FakeClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class OutboxTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.outbox = InMemoryOutbox(clock=self.clock)

    def test_new_records_are_pending(self):
        self.outbox.add("payments", {"id": 1})
        self.outbox.add("payments", {"id": 2})
        self.assertEqual(len(self.outbox.pending()), 2)
        self.assertEqual(len(self.outbox), 2)

    def test_drain_publishes_everything(self):
        self.outbox.add("payments", {"id": 1})
        self.outbox.add("payments", {"id": 2})
        seen = []

        published, failed = self.outbox.drain(seen.append)

        self.assertEqual((published, failed), (2, 0))
        self.assertEqual([r.payload["id"] for r in seen], [1, 2])
        self.assertEqual(self.outbox.pending(), [])

    def test_failed_publish_stays_pending(self):
        ok = self.outbox.add("payments", {"id": 1})
        bad = self.outbox.add("payments", {"id": 2})

        def publisher(record):
            if record.id == bad.id:
                raise ConnectionError("broker down")

        published, failed = self.outbox.drain(publisher)

        self.assertEqual((published, failed), (1, 1))
        pending = self.outbox.pending()
        self.assertEqual([r.id for r in pending], [bad.id])
        self.assertEqual(pending[0].attempts, 1)

    def test_republish_after_recovery(self):
        self.outbox.add("payments", {"id": 1})
        self.outbox.drain(lambda record: (_ for _ in ()).throw(ConnectionError()))
        self.assertEqual(len(self.outbox.pending()), 1)

        published, failed = self.outbox.drain(lambda record: None)

        self.assertEqual((published, failed), (1, 0))
        self.assertEqual(self.outbox.pending(), [])

    def test_limit_caps_the_batch(self):
        for index in range(5):
            self.outbox.add("payments", {"id": index})

        published, _ = self.outbox.drain(lambda record: None, limit=2)

        self.assertEqual(published, 2)
        self.assertEqual(len(self.outbox.pending()), 3)


if __name__ == "__main__":
    unittest.main()

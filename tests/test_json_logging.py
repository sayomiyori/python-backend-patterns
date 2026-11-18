import io
import json
import logging
import unittest

from patterns.json_logging import JsonFormatter, configure, new_request_id, request_id


class JsonLoggingTests(unittest.TestCase):
    def setUp(self):
        self.stream = io.StringIO()
        self.logger = logging.getLogger("test.json")
        self.logger.handlers.clear()
        self.logger.propagate = False
        self.logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(self.stream)
        handler.setFormatter(JsonFormatter(service="billing"))
        self.logger.addHandler(handler)

    def records(self):
        return [json.loads(line) for line in self.stream.getvalue().splitlines()]

    def test_emits_single_json_object(self):
        self.logger.info("charged")
        payload = self.records()[0]
        self.assertEqual(payload["message"], "charged")
        self.assertEqual(payload["level"], "INFO")
        self.assertEqual(payload["logger"], "test.json")
        self.assertEqual(payload["service"], "billing")
        self.assertIn("ts", payload)

    def test_request_id_is_attached(self):
        token = request_id.set("req-42")
        try:
            self.logger.warning("retrying")
        finally:
            request_id.reset(token)
        self.assertEqual(self.records()[0]["request_id"], "req-42")

    def test_request_id_absent_when_unset(self):
        token = request_id.set(None)
        try:
            self.logger.info("no id")
        finally:
            request_id.reset(token)
        self.assertNotIn("request_id", self.records()[0])

    def test_extra_fields_are_preserved(self):
        self.logger.info("paid", extra={"order_id": 7, "amount": 19.5})
        payload = self.records()[0]
        self.assertEqual(payload["order_id"], 7)
        self.assertEqual(payload["amount"], 19.5)

    def test_exception_is_serialised(self):
        try:
            raise ValueError("bad payload")
        except ValueError:
            self.logger.exception("failed")
        self.assertIn("ValueError: bad payload", self.records()[0]["exc"])

    def test_redaction_hook_runs(self):
        stream = io.StringIO()
        logger = logging.getLogger("test.redacted")
        logger.handlers.clear()
        logger.propagate = False
        handler = logging.StreamHandler(stream)
        handler.setFormatter(
            JsonFormatter(redact=lambda payload: {**payload, "message": "***"})
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        logger.info("password=hunter2")

        self.assertEqual(json.loads(stream.getvalue())["message"], "***")

    def test_new_request_id_is_short_and_unique(self):
        first = new_request_id()
        second = new_request_id()
        self.assertEqual(len(first), 12)
        self.assertNotEqual(first, second)

    def test_configure_is_idempotent(self):
        logger = logging.getLogger()
        before = len(logger.handlers)
        stream = io.StringIO()
        configure(stream=stream)
        configure(stream=stream)
        self.assertEqual(len(logger.handlers), before + 1)
        logger.handlers[:] = [
            h for h in logger.handlers if not getattr(h, "_json_backend_patterns", False)
        ]


if __name__ == "__main__":
    unittest.main()

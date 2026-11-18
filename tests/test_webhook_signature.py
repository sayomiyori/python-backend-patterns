import unittest

from patterns.webhook_signature import (
    compute_header,
    compute_signature,
    parse_header,
    verify_header,
)

SECRET = b"whsec_test_123"
BODY = b'{"event":"payment.succeeded","amount":1999}'


class SignatureTests(unittest.TestCase):
    def test_signature_is_stable_for_same_inputs(self):
        self.assertEqual(
            compute_signature(SECRET, BODY, 1700000000),
            compute_signature("whsec_test_123", BODY, 1700000000),
        )

    def test_signature_changes_with_body(self):
        self.assertNotEqual(
            compute_signature(SECRET, BODY, 1700000000),
            compute_signature(SECRET, BODY + b" ", 1700000000),
        )

    def test_signature_changes_with_timestamp(self):
        self.assertNotEqual(
            compute_signature(SECRET, BODY, 1700000000),
            compute_signature(SECRET, BODY, 1700000001),
        )

    def test_header_format(self):
        header = compute_header(SECRET, BODY, timestamp=1700000000)
        timestamp, signatures = parse_header(header)
        self.assertEqual(timestamp, 1700000000)
        self.assertEqual(len(signatures), 1)
        self.assertEqual(header, f"t=1700000000,v1={signatures[0]}")

    def test_parse_rejects_malformed_header(self):
        for header in ("", "v1=abc", "t=123", "t=abc,v1=def", "garbage"):
            with self.assertRaises(ValueError):
                parse_header(header)


class VerifyTests(unittest.TestCase):
    def setUp(self):
        self.now = 1700000000
        self.header = compute_header(SECRET, BODY, timestamp=self.now)

    def verify(self, **kwargs):
        params = {
            "secret": SECRET,
            "body": BODY,
            "header": self.header,
            "tolerance": 300,
            "now": lambda: self.now,
        }
        params.update(kwargs)
        return verify_header(**params)

    def test_accepts_valid_signature(self):
        self.assertTrue(self.verify())

    def test_rejects_tampered_body(self):
        self.assertFalse(self.verify(body=b'{"event":"payment.succeeded","amount":1}'))

    def test_rejects_wrong_secret(self):
        self.assertFalse(self.verify(secret=b"whsec_other"))

    def test_rejects_stale_timestamp(self):
        self.now += 301
        self.assertFalse(self.verify())

    def test_accepts_timestamp_inside_window(self):
        self.now += 299
        self.assertTrue(self.verify())

    def test_rejects_replayed_signature_with_tolerance_zero(self):
        self.now += 1
        self.assertFalse(self.verify(tolerance=0))

    def test_accepts_any_matching_signature_in_header(self):
        good = compute_signature(SECRET, BODY, self.now)
        self.assertTrue(self.verify(header=f"t={self.now},v1=deadbeef,v1={good}"))

    def test_rejects_malformed_header(self):
        self.assertFalse(self.verify(header="not-a-header"))


if __name__ == "__main__":
    unittest.main()

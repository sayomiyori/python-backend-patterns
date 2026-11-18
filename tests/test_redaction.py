import unittest

from patterns.redaction import MASK, mask, redact_mapping, redact_text


class RedactMappingTests(unittest.TestCase):
    def test_masks_sensitive_keys(self):
        payload = {"user": "alice", "password": "hunter2", "access_token": "abc"}
        cleaned = redact_mapping(payload)
        self.assertEqual(cleaned["user"], "alice")
        self.assertEqual(cleaned["password"], MASK)
        self.assertEqual(cleaned["access_token"], MASK)

    def test_masks_nested_structures(self):
        payload = {
            "order": {"id": 7, "payment": {"card_number": "4242424242424242"}},
            "items": [{"sku": "A-1", "api_key": "k"}],
        }
        cleaned = redact_mapping(payload)
        self.assertEqual(cleaned["order"]["id"], 7)
        self.assertEqual(cleaned["order"]["payment"]["card_number"], MASK)
        self.assertEqual(cleaned["items"][0]["sku"], "A-1")
        self.assertEqual(cleaned["items"][0]["api_key"], MASK)

    def test_preserves_scalars_and_lists_of_scalars(self):
        self.assertEqual(redact_mapping([1, "two", None]), [1, "two", None])
        self.assertEqual(redact_mapping("plain"), "plain")

    def test_case_insensitive_keys(self):
        self.assertEqual(redact_mapping({"API_KEY": "x"})["API_KEY"], MASK)
        self.assertEqual(redact_mapping({"Authorization": "x"})["Authorization"], MASK)

    def test_does_not_touch_similar_but_safe_keys(self):
        payload = {"username": "alice", "tokenizer": "bpe", "password_hint": "pet"}
        cleaned = redact_mapping(payload)
        self.assertEqual(cleaned["username"], "alice")
        self.assertEqual(cleaned["tokenizer"], "bpe")
        self.assertEqual(cleaned["password_hint"], MASK)


class RedactTextTests(unittest.TestCase):
    def test_masks_bearer_tokens(self):
        line = "GET /api Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6"
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6", redact_text(line))
        self.assertIn("Authorization:", redact_text(line))

    def test_masks_api_keys(self):
        self.assertNotIn("sk_live_abcdef123456", redact_text("key=sk_live_abcdef123456"))

    def test_masks_telegram_bot_token(self):
        token = "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"
        self.assertNotIn(token, redact_text(f"url=https://api.telegram.org/bot{token}"))

    def test_leaves_ordinary_text_alone(self):
        text = "user alice paid 19.99 USD for order 42"
        self.assertEqual(redact_text(text), text)


class MaskTests(unittest.TestCase):
    def test_short_values_are_fully_masked(self):
        self.assertEqual(mask("abc"), MASK)

    def test_long_values_keep_a_prefix(self):
        masked = mask("secret-value-123456")
        self.assertTrue(masked.startswith("secr"))
        self.assertTrue(masked.endswith(MASK))
        self.assertNotIn("123456", masked)


if __name__ == "__main__":
    unittest.main()

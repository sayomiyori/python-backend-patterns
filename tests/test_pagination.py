import unittest

from patterns.pagination import decode_cursor, encode_cursor, paginate


class CursorTests(unittest.TestCase):
    def test_round_trip(self):
        token = encode_cursor({"k": 42, "tenant": "acme"})
        self.assertEqual(decode_cursor(token), {"k": 42, "tenant": "acme"})

    def test_token_is_url_safe_and_unpadded(self):
        token = encode_cursor({"k": "../../etc/passwd"})
        self.assertNotIn("=", token)
        self.assertNotIn("+", token)
        self.assertNotIn("/", token)

    def test_garbage_raises_value_error(self):
        for bad in ("", "!!!not-base64!!!", encode_cursor({"k": 1})[:-3] + "\x00"):
            with self.assertRaises(ValueError):
                decode_cursor(bad)

    def test_valid_base64_of_non_object_is_rejected(self):
        import base64

        token = base64.urlsafe_b64encode(b"[1,2,3]").decode().rstrip("=")
        with self.assertRaises(ValueError):
            decode_cursor(token)


class PaginateTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{"id": index} for index in range(5)]

    def test_first_page(self):
        page = paginate(self.rows, key=lambda row: row["id"], limit=2)
        self.assertEqual([row["id"] for row in page.items], [0, 1])
        self.assertTrue(page.has_more)

    def test_walks_all_rows_without_duplicates(self):
        seen = []
        cursor = None
        for _ in range(10):
            page = paginate(self.rows, key=lambda row: row["id"], limit=2, after=cursor)
            seen.extend(row["id"] for row in page.items)
            cursor = page.next_cursor
            if cursor is None:
                break
        self.assertEqual(seen, [0, 1, 2, 3, 4])

    def test_last_page_has_no_cursor(self):
        page = paginate(self.rows, key=lambda row: row["id"], limit=10)
        self.assertEqual(len(page.items), 5)
        self.assertIsNone(page.next_cursor)

    def test_cursor_past_the_end_returns_empty_page(self):
        cursor = encode_cursor({"k": 99})
        page = paginate(self.rows, key=lambda row: row["id"], limit=2, after=cursor)
        self.assertEqual(page.items, [])
        self.assertFalse(page.has_more)

    def test_string_keys_are_supported(self):
        rows = [{"email": email} for email in ("a@x.io", "b@x.io", "c@x.io")]
        page = paginate(rows, key=lambda row: row["email"], limit=2)
        rest = paginate(
            rows, key=lambda row: row["email"], limit=2, after=page.next_cursor
        )
        self.assertEqual([row["email"] for row in rest.items], ["c@x.io"])

    def test_rejects_non_positive_limit(self):
        with self.assertRaises(ValueError):
            paginate(self.rows, key=lambda row: row["id"], limit=0)


if __name__ == "__main__":
    unittest.main()

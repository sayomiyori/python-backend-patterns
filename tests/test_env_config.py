import unittest

from patterns.env_config import ConfigError, Env


class EnvTests(unittest.TestCase):
    def make(self, **values):
        return Env(source={key: str(value) for key, value in values.items()})

    def test_string_default_and_required(self):
        env = self.make()
        self.assertIsNone(env.str("MISSING"))
        self.assertEqual(env.str("MISSING", default="fallback"), "fallback")
        self.assertIsNone(env.str("REQUIRED_KEY", required=True))
        with self.assertRaises(ConfigError) as ctx:
            env.validate()
        self.assertIn("REQUIRED_KEY is required", str(ctx.exception))

    def test_ints_are_parsed(self):
        env = self.make(PORT=8080, BIG="1_000_000")
        self.assertEqual(env.int("PORT"), 8080)
        self.assertEqual(env.int("BIG"), 1_000_000)
        self.assertIsNone(env.int("ABSENT"))

    def test_bad_int_is_collected_not_raised_immediately(self):
        env = self.make(PORT="eighty")
        self.assertEqual(env.int("PORT", default=80), 80)
        self.assertEqual(env.errors(), ["PORT must be an integer, got 'eighty'"])

    def test_float(self):
        env = self.make(RATIO="0.75")
        self.assertEqual(env.float("RATIO"), 0.75)
        env = self.make(RATIO="soon")
        self.assertIsNone(env.float("RATIO"))

    def test_bool_accepts_common_spellings(self):
        for raw in ("1", "true", "TRUE", "yes", "on", "y"):
            self.assertTrue(self.make(FLAG=raw).bool("FLAG"), raw)
        for raw in ("0", "false", "no", "off", "n"):
            self.assertFalse(self.make(FLAG=raw).bool("FLAG"), raw)

    def test_bool_rejects_garbage(self):
        env = self.make(FLAG="maybe")
        self.assertTrue(env.bool("FLAG", default=True))
        self.assertEqual(len(env.errors()), 1)

    def test_lists_are_split_and_trimmed(self):
        env = self.make(ALLOWED=" a , b ,, c ")
        self.assertEqual(env.list("ALLOWED"), ["a", "b", "c"])
        self.assertEqual(env.list("ABSENT", default=["x"]), ["x"])

    def test_blank_values_are_treated_as_missing(self):
        env = Env(source={"EMPTY": "   "})
        self.assertIsNone(env.str("EMPTY"))
        self.assertEqual(env.int("EMPTY", default=1), 1)
        self.assertEqual(env.errors(), [])

    def test_validate_reports_every_problem_at_once(self):
        env = self.make(PORT="abc", RATIO="xyz", FEATURE="sometimes")
        env.int("PORT")
        env.float("RATIO")
        env.bool("FEATURE")
        env.str("DATABASE_URL", required=True)
        with self.assertRaises(ConfigError) as ctx:
            env.validate()
        self.assertEqual(len(ctx.exception.errors), 4)

    def test_valid_configuration_passes(self):
        env = self.make(PORT=8000, FEATURE="true", DATABASE_URL="postgres://db/app")
        self.assertEqual(env.int("PORT"), 8000)
        self.assertTrue(env.bool("FEATURE"))
        self.assertEqual(env.str("DATABASE_URL", required=True), "postgres://db/app")
        env.validate()


if __name__ == "__main__":
    unittest.main()

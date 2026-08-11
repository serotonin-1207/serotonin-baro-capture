import unittest

from update_checker import semantic_version


class SemanticVersionTests(unittest.TestCase):
    def test_accepts_release_tags(self):
        self.assertEqual(semantic_version("v1.2.3"), (1, 2, 3))

    def test_accepts_legacy_single_number(self):
        self.assertEqual(semantic_version("V1"), (1, 0, 0))

    def test_orders_versions_numerically(self):
        self.assertGreater(semantic_version("v1.10.0"), semantic_version("v1.9.9"))

    def test_rejects_invalid_version(self):
        with self.assertRaises(ValueError):
            semantic_version("latest")


if __name__ == "__main__":
    unittest.main()

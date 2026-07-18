"""Tests for price book module."""

import unittest
from src.shared.price_book import round_price


class TestPriceBook(unittest.TestCase):
    def test_round_price_down(self):
        # 1002: remainder 2, <=5, rounds down
        result = round_price(1002, step=10)
        self.assertEqual(result, 1000)

    def test_round_price_up(self):
        # 1006: remainder 6, >5, rounds up
        result = round_price(1006, step=10)
        self.assertEqual(result, 1010)

    def test_round_price_none(self):
        result = round_price(None, step=10)
        self.assertIsNone(result)

    def test_round_price_no_step(self):
        result = round_price(1005.5, step=None)
        self.assertEqual(result, 1005.5)


if __name__ == "__main__":
    unittest.main()
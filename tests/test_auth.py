"""Tests for authentication module."""

import unittest
from unittest.mock import patch, MagicMock
from datetime import date

from src.shared.auth import load_cached_token, save_token_cache, get_kite_session


class TestAuth(unittest.TestCase):
    @patch("src.shared.auth.TOKEN_CACHE_FILE")
    def test_load_cached_token_not_exists(self, mock_file):
        mock_file.exists.return_value = False
        result = load_cached_token()
        self.assertIsNone(result)

    @patch("src.shared.auth.TOKEN_CACHE_FILE")
    def test_save_token_cache(self, mock_file):
        mock_file.open = MagicMock()
        # Test passes if no exception is raised
        save_token_cache("test_token")


if __name__ == "__main__":
    unittest.main()
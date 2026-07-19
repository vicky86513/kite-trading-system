import unittest
from unittest.mock import patch

from src.orchestration import run_all


class TestRunAll(unittest.TestCase):
    @patch("src.orchestration.run_all.importlib.util.find_spec")
    def test_start_tracker_reports_missing_dependency(self, mock_find_spec):
        mock_find_spec.return_value = None

        proc = run_all.start_tracker("TEST", "src.trackers.nifty_tracker")

        self.assertIsNone(proc)


if __name__ == "__main__":
    unittest.main()

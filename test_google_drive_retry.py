
import unittest
from unittest.mock import Mock, patch

from googleapiclient.errors import HttpError

from app.database.google_drive_backup import (
    execute_with_retry,
)


class TestGoogleDriveRetry(unittest.TestCase):

    @patch("app.database.google_drive_backup.time.sleep")
    def test_success_on_first_attempt(self, mock_sleep):

        request = Mock()
        request.execute.return_value = {
            "success": True
        }

        result = execute_with_retry(request)

        self.assertEqual(result, {"success": True})
        self.assertEqual(request.execute.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("app.database.google_drive_backup.time.sleep")
    def test_retry_after_temporary_timeout(self, mock_sleep):

        request = Mock()

        request.execute.side_effect = [
            TimeoutError("Temporary network failure"),
            {"success": True}
        ]

        result = execute_with_retry(request)

        self.assertEqual(result, {"success": True})
        self.assertEqual(request.execute.call_count, 2)

        mock_sleep.assert_called_once_with(2)

    @patch("app.database.google_drive_backup.time.sleep")
    def test_exponential_backoff(self, mock_sleep):

        request = Mock()

        request.execute.side_effect = [
            TimeoutError("Failure 1"),
            TimeoutError("Failure 2"),
            TimeoutError("Failure 3"),
            {"success": True}
        ]

        result = execute_with_retry(request)

        self.assertEqual(result, {"success": True})

        self.assertEqual(
            request.execute.call_count,
            4
        )

        self.assertEqual(
            [call.args[0] for call in mock_sleep.call_args_list],
            [2, 4, 8]
        )

    @patch("app.database.google_drive_backup.time.sleep")
    def test_stop_after_maximum_attempts(self, mock_sleep):

        request = Mock()

        request.execute.side_effect = TimeoutError(
            "Network unavailable"
        )

        with self.assertRaises(TimeoutError):

            execute_with_retry(request)

        self.assertEqual(
            request.execute.call_count,
            4
        )

        self.assertEqual(
            [call.args[0] for call in mock_sleep.call_args_list],
            [2, 4, 8]
        )

    @patch("app.database.google_drive_backup.time.sleep")
    def test_permanent_http_error_is_not_retried(self, mock_sleep):

        request = Mock()

        request.execute.side_effect = HttpError(
            resp=Mock(status=404),
            content=b"Not Found"
        )

        with self.assertRaises(HttpError):

            execute_with_retry(request)

        self.assertEqual(
            request.execute.call_count,
            1
        )

        mock_sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()

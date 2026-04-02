import sys
from unittest.mock import MagicMock

# Mock necessary modules
sys.modules['google_auth_oauthlib.flow'] = MagicMock()
sys.modules['google.auth.transport.requests'] = MagicMock()
sys.modules['googleapiclient.discovery'] = MagicMock()
sys.modules['googleapiclient.http'] = MagicMock()
sys.modules['logger'] = MagicMock()

import unittest
import time
from unittest.mock import patch

# Mock the YouTubeUploader class's __init__ to avoid _authenticate
from core.uploader_yt import YouTubeUploader

class TestYouTubeUploaderRetry(unittest.TestCase):
    def setUp(self):
        # We patch __init__ to do nothing
        with patch.object(YouTubeUploader, '__init__', return_value=None):
            self.uploader = YouTubeUploader()
            self.uploader.youtube = MagicMock()
            self.uploader.is_authenticated = True

    def test_pin_first_comment_retry(self):
        # Setup the mock for commentThreads().insert().execute()
        # We want it to fail twice and then succeed
        mock_execute = MagicMock()
        mock_execute.side_effect = [Exception("Transient Error"), Exception("Another Error"), {"id": "comment_id"}]

        mock_insert = MagicMock()
        mock_insert.execute = mock_execute

        self.uploader.youtube.commentThreads().insert.return_value = mock_insert

        # Patch time.sleep to avoid waiting during tests
        with patch('time.sleep') as mock_sleep:
            self.uploader._pin_first_comment("video_123", "Pesan CTA")

            # Verify that execute was called 3 times
            self.assertEqual(mock_execute.call_count, 3)
            # Verify that sleep was called 2 times (exponential backoff)
            self.assertEqual(mock_sleep.call_count, 2)
            mock_sleep.assert_any_call(2)
            mock_sleep.assert_any_call(4)

            # Check if the text formatting is correct (should have \n\n, not \\n\\n)
            call_args = self.uploader.youtube.commentThreads().insert.call_args
            body = call_args[1]['body']
            text = body['snippet']['topLevelComment']['snippet']['textOriginal']

            self.assertIn("\n\n", text)
            self.assertNotIn("\\n\\n", text)
            print("✅ Test Passed: Retry logic and formatting are correct.")

if __name__ == "__main__":
    unittest.main()

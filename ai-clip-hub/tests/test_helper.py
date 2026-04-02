import unittest
from unittest.mock import patch
import random
import sys
import os

# Add the parent directory to sys.path to import modules from ai-clip-hub
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.helper import get_random_user_agent, USER_AGENTS

class TestHelper(unittest.TestCase):
    def test_get_random_user_agent_returns_string(self):
        """Verify the return type is a string"""
        ua = get_random_user_agent()
        self.assertIsInstance(ua, str)

    def test_get_random_user_agent_in_list(self):
        """Verify the returned value is one of the predefined user agents"""
        ua = get_random_user_agent()
        self.assertIn(ua, USER_AGENTS)

    def test_get_random_user_agent_mock(self):
        """Verify it calls random.choice with the expected list"""
        with patch('random.choice') as mocked_choice:
            mocked_choice.return_value = "mocked_ua"
            ua = get_random_user_agent()
            mocked_choice.assert_called_once_with(USER_AGENTS)
            self.assertEqual(ua, "mocked_ua")

if __name__ == '__main__':
    unittest.main()

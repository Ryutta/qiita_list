import unittest
from unittest.mock import patch, MagicMock
from src.qiita_client import QiitaClient
import requests

class TestQiitaClient(unittest.TestCase):
    def setUp(self):
        self.client = QiitaClient(access_token="test_token")

    @patch('src.qiita_client.requests.get')
    def test_get_likes_success_first_try(self, mock_get):
        # Setup mock for first endpoint success
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": "item1"}]
        mock_get.return_value = mock_response

        # Call method
        likes = self.client.get_likes("user1")

        # Verify
        self.assertEqual(len(likes), 1)
        self.assertEqual(likes[0]['id'], "item1")

        # Verify it called the first endpoint
        args, kwargs = mock_get.call_args
        self.assertIn("/users/user1/likes", args[0])

    @patch('src.qiita_client.requests.get')
    def test_get_likes_fallback(self, mock_get):
        # Setup mock: first call returns 404, second call returns 200
        mock_response_404 = MagicMock()
        mock_response_404.status_code = 404

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = [{"id": "item2"}]

        # side_effect allows different return values for sequential calls
        mock_get.side_effect = [mock_response_404, mock_response_200]

        # Call method
        likes = self.client.get_likes("user1")

        # Verify
        self.assertEqual(len(likes), 1)
        self.assertEqual(likes[0]['id'], "item2")

        # Verify calls
        self.assertEqual(mock_get.call_count, 2)
        args_list = mock_get.call_args_list
        self.assertIn("/users/user1/likes", args_list[0][0][0])
        self.assertIn("/users/user1/likes/items", args_list[1][0][0])

    @patch('src.qiita_client.requests.get')
    def test_get_likes_all_fail(self, mock_get):
        # Setup mock: all calls return 404
        mock_response_404 = MagicMock()
        mock_response_404.status_code = 404
        mock_get.return_value = mock_response_404

        # Call method
        likes = self.client.get_likes("user1")

        # Verify
        self.assertEqual(len(likes), 0)
        # Should try all 3 endpoints
        self.assertEqual(mock_get.call_count, 3)

if __name__ == '__main__':
    unittest.main()

import unittest
from unittest.mock import patch, MagicMock
from src.qiita_client import QiitaClient
import requests
import json

class TestQiitaClient(unittest.TestCase):
    def setUp(self):
        self.client = QiitaClient(access_token="test_token")

    @patch('src.qiita_client.requests.get')
    def test_get_all_likes_api_success(self, mock_get):
        # Mock API response (success)
        resp1 = MagicMock()
        resp1.status_code = 200
        resp1.json.return_value = [{"id": "api_item_1", "title": "API Title 1"}]

        resp2 = MagicMock()
        resp2.status_code = 200
        resp2.json.return_value = [] # End of list

        mock_get.side_effect = [resp1, resp2]

        # Call method
        likes = self.client.get_all_likes("user1")

        # Verify
        self.assertEqual(len(likes), 1)
        self.assertEqual(likes[0]['id'], "api_item_1")
        # Verify it called API endpoint
        args_list = mock_get.call_args_list
        self.assertIn("/users/user1/likes", args_list[0][1]['url'] if 'url' in args_list[0][1] else args_list[0][0][0])

    @patch('src.qiita_client.requests.Session')
    @patch('src.qiita_client.requests.get')
    def test_get_all_likes_graphql_success(self, mock_get, mock_session_cls):
        # API v2 fails (404)
        mock_get.return_value.status_code = 404

        # Mock Session for GraphQL
        mock_session = mock_session_cls.return_value

        # Step 1: HTML Response
        resp_html = MagicMock()
        resp_html.status_code = 200
        # Mock data-config with JSON
        config_json = json.dumps({"settings": {"csrfToken": "test_token_123"}})
        resp_html.content = f'<div id="dataContainer" data-config=\'{config_json}\'></div>'.encode('utf-8')
        mock_session.get.return_value = resp_html

        # Step 2: GraphQL Response
        resp_gql = MagicMock()
        resp_gql.status_code = 200
        resp_gql.json.return_value = {
            "data": {
                "user": {
                    "paginatedArticleLikes": {
                        "items": [
                            {
                                "article": {
                                    "uuid": "gql_item_1",
                                    "title": "GraphQL Title 1",
                                    "linkUrl": "https://qiita.com/user/items/gql_item_1",
                                    "likesCount": 5,
                                    "publishedAt": "2024-01-01",
                                    "author": {"urlName": "author1"}
                                }
                            }
                        ],
                        "pageData": {
                            "isLastPage": True,
                            "totalPages": 1
                        }
                    }
                }
            }
        }
        mock_session.post.return_value = resp_gql

        # Call method
        likes = self.client.get_all_likes("user1")

        # Verify
        self.assertEqual(len(likes), 1)
        self.assertEqual(likes[0]['id'], "gql_item_1")
        self.assertEqual(likes[0]['title'], "GraphQL Title 1")

        # Verify GraphQL called with correct token
        mock_session.post.assert_called()
        args, kwargs = mock_session.post.call_args
        self.assertEqual(kwargs['headers']['X-CSRF-Token'], "test_token_123")

    @patch('src.qiita_client.requests.Session')
    @patch('src.qiita_client.requests.get')
    def test_get_all_likes_fallback_scraping(self, mock_get, mock_session_cls):
        # API v2 fails (404)
        resp_api = MagicMock()
        resp_api.status_code = 404

        # Scraping response (success)
        resp_scraping = MagicMock()
        resp_scraping.status_code = 200
        resp_scraping.content = b"""
        <html><body>
            <a href="/items/1234567890abcdef1234">Scrape Title 1</a>
        </body></html>
        """

        resp_scraping_end = MagicMock()
        resp_scraping_end.status_code = 200
        resp_scraping_end.content = b"<html><body></body></html>"

        mock_get.side_effect = [resp_api, resp_scraping, resp_scraping_end]

        # GraphQL fails (returns None)
        # Mock session to fail getting HTML or finding CSRF
        mock_session = mock_session_cls.return_value
        mock_session.get.return_value.status_code = 404 # Fail HTML fetch

        # Call method
        likes = self.client.get_all_likes("user1")

        # Verify
        self.assertEqual(len(likes), 1)
        self.assertEqual(likes[0]['id'], "1234567890abcdef1234")

        # Verify GraphQL attempt happened (session created)
        mock_session_cls.assert_called()

    @patch('src.qiita_client.requests.delete')
    def test_unstock_item_success(self, mock_delete):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_delete.return_value = mock_response

        result = self.client.unstock_item("12345")
        self.assertTrue(result)

    @patch('src.qiita_client.requests.delete')
    def test_unstock_item_fail(self, mock_delete):
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_delete.return_value = mock_response

        result = self.client.unstock_item("12345")
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()

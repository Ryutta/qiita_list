import os
import requests
import sys

class QiitaClient:
    BASE_URL = "https://qiita.com/api/v2"

    def __init__(self, access_token=None):
        self.access_token = access_token
        if not self.access_token:
            self.access_token = os.environ.get("QIITA_ACCESS_TOKEN")

        self.headers = {}
        if self.access_token:
            self.headers["Authorization"] = f"Bearer {self.access_token}"

    def get_stocks(self, user_id, page=1, per_page=100):
        url = f"{self.BASE_URL}/users/{user_id}/stocks"
        params = {"page": page, "per_page": per_page}
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def get_all_stocks(self, user_id):
        all_stocks = []
        page = 1
        while True:
            stocks = self.get_stocks(user_id, page=page)
            if not stocks:
                break
            all_stocks.extend(stocks)
            page += 1
        return all_stocks

    def get_likes(self, user_id, page=1, per_page=100):
        # NOTE: The standard endpoint for fetching likes seems to be missing or deprecated.
        # We try multiple potential endpoints.
        endpoints = [
            f"{self.BASE_URL}/users/{user_id}/likes",
            f"{self.BASE_URL}/users/{user_id}/likes/items",
            f"{self.BASE_URL}/users/{user_id}/liked_items"
        ]

        params = {"page": page, "per_page": per_page}

        for url in endpoints:
            try:
                response = requests.get(url, headers=self.headers, params=params)

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    print(f"Warning: Endpoint {url} returned 401 Unauthorized. Ensure your token has 'read_qiita' scope.", file=sys.stderr)
                elif response.status_code == 404:
                    print(f"Warning: Endpoint {url} not found (404).", file=sys.stderr)
                else:
                    response.raise_for_status()
            except requests.exceptions.RequestException as e:
                print(f"Error accessing {url}: {e}", file=sys.stderr)

        print(f"Warning: Could not fetch likes from any known endpoint for user {user_id}.", file=sys.stderr)
        return []

    def get_all_likes(self, user_id):
        all_likes = []
        page = 1
        while True:
            likes = self.get_likes(user_id, page=page)
            if not likes:
                break
            all_likes.extend(likes)
            page += 1
        return all_likes

    def get_authenticated_user(self):
        url = f"{self.BASE_URL}/authenticated_user"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

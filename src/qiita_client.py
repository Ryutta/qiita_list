import os
import requests
import sys
import re
from bs4 import BeautifulSoup

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
        if response.status_code == 404:
            return []
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

    def get_user_likes_via_scraping(self, user_id, page=1):
        url = f"https://qiita.com/{user_id}/likes?page={page}"
        # Use a browser-like User-Agent to avoid 502/403
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        try:
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                # If 404 or other error, assume end of list or user not found
                return []

            soup = BeautifulSoup(response.content, 'html.parser')

            # Look for item links: /username/items/item_id
            links = soup.find_all('a', href=re.compile(r'/items/[0-9a-f]{20}'))

            items = []
            seen_ids = set()

            # Use a dictionary to store items by ID to handle duplicates (empty vs filled title)
            items_dict = {}

            for link in links:
                href = link.get('href')
                match = re.search(r'/items/([0-9a-f]{20})', href)
                if match:
                    item_id = match.group(1)
                    title = link.get_text().strip()

                    if item_id not in items_dict:
                        if href.startswith("http"):
                            item_url = href
                        else:
                            item_url = f"https://qiita.com{href}"

                        items_dict[item_id] = {
                            'id': item_id,
                            'title': title, # Might be empty
                            'url': item_url,
                            'user': {'id': href.split('/')[1] if len(href.split('/')) > 1 else 'unknown'},
                            'tags': [], # Scraping doesn't easily give tags without more complex parsing
                            'likes_count': 0, # Unknown
                            'created_at': '', # Unknown
                        }
                    else:
                        # Update title if we have a better one
                        if title and not items_dict[item_id]['title']:
                            items_dict[item_id]['title'] = title

            # Filter out items with empty titles (unless that's all we have)
            # Generally valid items will have a title link.
            valid_items = [item for item in items_dict.values() if item['title']]
            return valid_items

        except Exception as e:
            print(f"Error scraping likes: {e}", file=sys.stderr)
            return []

    def get_all_likes(self, user_id):
        all_likes = []
        page = 1
        while True:
            # We use scraping because API endpoint is gone
            likes = self.get_user_likes_via_scraping(user_id, page=page)
            if not likes:
                break
            all_likes.extend(likes)
            page += 1
            # Safety break for scraping infinite loops
            if page > 50: # Arbitrary limit to prevent infinite run if detection fails
                break
        return all_likes

    def get_authenticated_user(self):
        url = f"{self.BASE_URL}/authenticated_user"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def unlike_item(self, item_id):
        # Try deleting "like"
        url = f"{self.BASE_URL}/items/{item_id}/like"
        try:
            response = requests.delete(url, headers=self.headers)
            if response.status_code == 204:
                return True
            # If 404 or other, maybe it's a reaction
        except requests.RequestException:
            pass

        # Try deleting "+1" reaction
        # API: DELETE /api/v2/items/:item_id/reactions/:reaction_name
        # Name is "+1"
        url = f"{self.BASE_URL}/items/{item_id}/reactions/+1"
        try:
            response = requests.delete(url, headers=self.headers)
            if response.status_code in [200, 204]:
                return True
        except requests.RequestException as e:
            print(f"Error unliking item {item_id}: {e}", file=sys.stderr)
            return False

        return False

    def unstock_item(self, item_id):
        url = f"{self.BASE_URL}/items/{item_id}/stock"
        try:
            response = requests.delete(url, headers=self.headers)
            if response.status_code == 204:
                return True
        except requests.RequestException as e:
            print(f"Error unstocking item {item_id}: {e}", file=sys.stderr)
        return False

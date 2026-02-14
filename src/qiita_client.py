import os
import requests
import sys
import re
import json
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

    def get_user_likes_via_api(self, user_id, page=1, per_page=100):
        url = f"{self.BASE_URL}/users/{user_id}/likes"
        params = {"page": page, "per_page": per_page}
        try:
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code == 200:
                return response.json()
        except requests.RequestException:
            pass
        return None

    def get_all_likes_via_graphql(self, user_id):
        # Create session to handle cookies/CSRF
        session = requests.Session()
        session.headers.update({
             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        })

        try:
            # Step 1: Get CSRF Token
            url_html = f"https://qiita.com/{user_id}/likes"
            resp_html = session.get(url_html)
            if resp_html.status_code != 200:
                return None
            
            soup = BeautifulSoup(resp_html.content, 'html.parser')
            data_container = soup.find('div', id='dataContainer')
            if not data_container:
                # If dataContainer is missing, maybe it's not a React page or user not found
                return None
            
            data_config_str = data_container.get('data-config')
            if not data_config_str:
                return None
            
            data_config = json.loads(data_config_str)
            csrf_token = data_config.get('settings', {}).get('csrfToken')
            if not csrf_token:
                return None
            
            # Step 2: Loop GraphQL
            all_items = []
            page = 1
            per_page = 20 # Standard page size for Qiita pagination via GraphQL
            
            url_graphql = "https://qiita.com/graphql"
            # Updated query to match verified structure
            query = """
            query GetUserPaginatedArticleLikes($urlName: String!, $page: Int!, $per: Int!) {
              user(urlName: $urlName) {
                paginatedArticleLikes(page: $page, per: $per) {
                  items {
                    createdAt
                    article {
                      title
                      linkUrl
                      uuid
                      likesCount
                      publishedAt
                      author {
                        urlName
                      }
                      tags {
                        name
                        urlName
                      }
                    }
                  }
                  pageData {
                    isLastPage
                    totalPages
                  }
                }
              }
            }
            """
            
            while True:
                payload = {
                    "operationName": "GetUserPaginatedArticleLikes",
                    "variables": {
                        "urlName": user_id,
                        "page": page,
                        "per": per_page
                    },
                    "query": query
                }
                
                gql_headers = {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrf_token
                }
                
                resp_gql = session.post(url_graphql, json=payload, headers=gql_headers)
                if resp_gql.status_code != 200:
                    break
                
                data = resp_gql.json()
                # Check for errors
                if 'errors' in data:
                    print(f"GraphQL errors: {data['errors']}", file=sys.stderr)
                    break
                    
                user_data = data.get('data', {}).get('user')
                if not user_data:
                    break
                    
                paginated_data = user_data.get('paginatedArticleLikes')
                if not paginated_data:
                    break
                    
                items = paginated_data.get('items', [])
                page_data = paginated_data.get('pageData', {})
                
                for item in items:
                    art = item.get('article')
                    if not art:
                        continue
                        
                    mapped_item = {
                        'id': art.get('uuid'), # Use UUID as ID
                        'title': art.get('title'),
                        'url': art.get('linkUrl'),
                        'user': {'id': art.get('author', {}).get('urlName')},
                        'likes_count': art.get('likesCount', 0),
                        'created_at': art.get('publishedAt', ''),
                        'is_like': True,
                    }
                    
                    tags = art.get('tags', [])
                    if tags:
                        mapped_item['tags'] = [{'name': t.get('name'), 'url_name': t.get('urlName')} for t in tags]
                    else:
                        mapped_item['tags'] = []
                    
                    all_items.append(mapped_item)
                
                if page_data.get('isLastPage', True):
                    break
                
                page += 1
                
            return all_items
            
        except Exception as e:
            print(f"Error fetching likes via GraphQL: {e}", file=sys.stderr)
            return None

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
            if not valid_items and response.status_code == 200:
                print(f"Warning: No likes found via scraping. This might be due to Qiita's page structure changes (CSR). Only stocks are available.", file=sys.stderr)
            return valid_items

        except Exception as e:
            print(f"Error scraping likes: {e}", file=sys.stderr)
            return []

    def get_all_likes(self, user_id):
        all_likes = []
        page = 1
        
        # 1. Try API v2 first
        api_worked = False
        while True:
            likes = self.get_user_likes_via_api(user_id, page=page)
            if likes is None:
                # API failed (404 or error), break loop
                break
            
            if not likes:
                # API returned empty list (end of pagination)
                api_worked = True
                break
                
            all_likes.extend(likes)
            page += 1
            api_worked = True # If we got items, API worked
            
        if api_worked:
            return all_likes

        # 2. Try GraphQL (Internal API)
        graphql_likes = self.get_all_likes_via_graphql(user_id)
        if graphql_likes is not None:
            return graphql_likes

        # 3. Fallback to scraping (likely to fail due to CSR, but kept as last resort)
        page = 1
        while True:
            likes = self.get_user_likes_via_scraping(user_id, page=page)
            if not likes:
                break
            all_likes.extend(likes)
            page += 1
            if page > 50: 
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
            else:
                print(f"Failed to unlike item {item_id}: {response.status_code} {response.text}", file=sys.stderr)
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
            else:
                print(f"Failed to unstock item {item_id}: {response.status_code} {response.text}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"Error unstocking item {item_id}: {e}", file=sys.stderr)
        return False

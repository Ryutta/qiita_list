import os
import sys
import argparse
from dotenv import load_dotenv
try:
    from qiita_client import QiitaClient
except ImportError:
    from .qiita_client import QiitaClient

def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="List and search Qiita likes and stocks.")
    parser.add_argument("user_id", nargs="?", help="Qiita User ID")
    parser.add_argument("--search", "-s", help="Search query (e.g. 'python')")
    args = parser.parse_args()

    token = os.getenv("QIITA_ACCESS_TOKEN")
    client = QiitaClient(access_token=token)

    user_id = args.user_id
    if not user_id:
        # Try to get authenticated user if token exists
        if token:
            try:
                user = client.get_authenticated_user()
                user_id = user['id']
                print(f"Logged in as: {user_id}")
            except Exception as e:
                print(f"Error getting authenticated user: {e}")
                return
        else:
            print("Please provide a user_id or set QIITA_ACCESS_TOKEN in .env")
            return

    print(f"Fetching stocks for {user_id}...")
    try:
        stocks = client.get_all_stocks(user_id)
        print(f"Found {len(stocks)} stocks.")
    except Exception as e:
        print(f"Error fetching stocks: {e}")
        stocks = []

    print(f"Fetching likes for {user_id}...")
    try:
        likes = client.get_all_likes(user_id)
        print(f"Found {len(likes)} likes.")
    except Exception as e:
        print(f"Error fetching likes: {e}")
        likes = []

    # Combine and deduplicate
    # Stocks and likes are lists of items (dicts).
    # Deduplicate by ID.
    all_items_dict = {}
    for item in stocks:
        all_items_dict[item['id']] = item
    for item in likes:
        all_items_dict[item['id']] = item

    all_items = list(all_items_dict.values())
    print(f"Total unique items: {len(all_items)}")

    if args.search:
        query = args.search.lower()
        results = search_items(all_items, query)
        print(f"Search results for '{query}':")
        for item in results:
            print(f"- {item['title']} ({item['url']})")
    else:
        # Interactive search loop
        print("\nEntering interactive search mode.")
        while True:
            try:
                query = input("\nEnter search query (or 'q' to quit): ").strip()
            except EOFError:
                break

            if query.lower() == 'q':
                break
            if not query:
                continue

            results = search_items(all_items, query)
            print(f"Found {len(results)} items:")
            for item in results:
                print(f"- {item['title']} ({item['url']})")

def search_items(items, query):
    query = query.lower()
    results = []
    for item in items:
        title_match = query in item.get('title', '').lower()
        tag_match = any(query in tag.get('name', '').lower() for tag in item.get('tags', []))
        if title_match or tag_match:
            results.append(item)
    return results

if __name__ == "__main__":
    main()

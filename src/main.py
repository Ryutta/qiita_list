import os
import sys
import argparse
import re
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import print as rprint

try:
    from qiita_client import QiitaClient
except ImportError:
    from .qiita_client import QiitaClient

console = Console()

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
                console.print(f"[green]Logged in as: {user_id}[/green]")
            except Exception as e:
                console.print(f"[red]Error getting authenticated user: {e}[/red]")
                return
        else:
            console.print("[yellow]Please provide a user_id or set QIITA_ACCESS_TOKEN in .env[/yellow]")
            return

    # Fetch Data
    all_items = fetch_data(client, user_id)

    current_items = all_items
    if args.search:
        current_items = search_items(all_items, args.search)
        display_results_table(current_items)
    else:
        # Interactive Mode
        console.print("\n[bold]Entering interactive mode.[/bold]")
        display_results_table(current_items)

        while True:
            try:
                prompt = "\n[bold cyan]Enter search query, item numbers (e.g. '1,3') to unlike/unstock, 'r' to reset, or 'q' to quit:[/bold cyan] "
                query = console.input(prompt).strip()
            except (EOFError, KeyboardInterrupt):
                break

            if query.lower() == 'q':
                break

            if not query:
                continue

            if query.lower() == 'r':
                current_items = all_items
                display_results_table(current_items)
                continue

            # Check if input is selection (numbers)
            if re.match(r'^[\d,\s]+$', query):
                indices = [int(x.strip()) for x in query.split(',') if x.strip().isdigit()]
                handle_selection(client, current_items, indices)
                # Refresh data after action? Maybe not full fetch, just remove from list.
                # For now, we remove from local list if action successful.
                # Re-display
                # update current_items by removing deleted ones?
                # Actually, better to just refetch or assume success and hide.
                # Let's remove from all_items and current_items.
                # But handle_selection needs to return deleted IDs.
                continue

            # Otherwise, treat as search
            current_items = search_items(all_items, query)
            display_results_table(current_items)

def fetch_data(client, user_id):
    console.print(f"Fetching stocks for {user_id}...")
    try:
        stocks = client.get_all_stocks(user_id)
        console.print(f"Found {len(stocks)} stocks.")
    except Exception as e:
        console.print(f"[red]Error fetching stocks: {e}[/red]")
        stocks = []

    console.print(f"Fetching likes for {user_id}...")
    try:
        likes = client.get_all_likes(user_id)
        console.print(f"Found {len(likes)} likes.")
    except Exception as e:
        console.print(f"[red]Error fetching likes: {e}[/red]")
        likes = []

    # Combine and deduplicate
    all_items_dict = {}
    for item in stocks:
        item['is_stock'] = True
        all_items_dict[item['id']] = item
    for item in likes:
        if item['id'] in all_items_dict:
             all_items_dict[item['id']]['is_like'] = True
        else:
             item['is_like'] = True
             all_items_dict[item['id']] = item

    all_items = list(all_items_dict.values())
    console.print(f"Total unique items: {len(all_items)}")
    return all_items

def search_items(items, query):
    query = query.lower()
    results = []
    for item in items:
        title_match = query in item.get('title', '').lower()
        tag_match = any(query in tag.get('name', '').lower() for tag in item.get('tags', []))
        if title_match or tag_match:
            results.append(item)
    return results

def display_results_table(items):
    table = Table(title=f"Found {len(items)} items")
    table.add_column("No.", style="cyan", no_wrap=True)
    table.add_column("Title", style="magenta")
    table.add_column("User", style="green")
    table.add_column("Type", style="yellow")
    # table.add_column("URL", style="blue") # Link is in Title

    for i, item in enumerate(items, 1):
        title = item.get('title', 'No Title')
        url = item.get('url', '')
        user = item.get('user', {}).get('id', 'unknown')

        # Format types (Like/Stock)
        types = []
        if item.get('is_like'): types.append("Like")
        if item.get('is_stock'): types.append("Stock")
        type_str = ", ".join(types)

        # Create clickable link
        display_title = f"[link={url}]{title}[/link]"

        table.add_row(str(i), display_title, user, type_str)

    console.print(table)

def handle_selection(client, items, indices):
    selected_items = []
    for idx in indices:
        if 1 <= idx <= len(items):
            selected_items.append(items[idx-1])

    if not selected_items:
        console.print("[yellow]No valid items selected.[/yellow]")
        return

    console.print(f"[bold]Selected {len(selected_items)} items:[/bold]")
    for item in selected_items:
        console.print(f"- {item.get('title')}")

    confirm = console.input("[bold red]Are you sure you want to unlike/unstock these items? (y/N):[/bold red] ")
    if confirm.lower() != 'y':
        console.print("Cancelled.")
        return

    for item in selected_items:
        item_id = item['id']
        success = False

        # Try unlike if it's a like
        if item.get('is_like'):
            if client.unlike_item(item_id):
                console.print(f"[green]Unliked: {item.get('title')}[/green]")
                item['is_like'] = False
                success = True
            else:
                console.print(f"[red]Failed to unlike: {item.get('title')}[/red]")

        # Try unstock if it's a stock (and user implies unstocking too?)
        # User said "unlike them", maybe implies removing from list.
        # If I unstock, it removes from list completely if it was also stocked.
        # I'll try unstock too if it is stocked.
        if item.get('is_stock'):
            if client.unstock_item(item_id):
                console.print(f"[green]Unstocked: {item.get('title')}[/green]")
                item['is_stock'] = False
                success = True
            else:
                 console.print(f"[red]Failed to unstock: {item.get('title')}[/red]")

        if not item.get('is_like') and not item.get('is_stock'):
            # Removed completely
            pass

if __name__ == "__main__":
    main()

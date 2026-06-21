#!/usr/bin/env python3
"""
Pure Python interactive wallet for Duino-Coin
Uses only standard library modules.
"""
import urllib.request
import urllib.parse
import urllib.error
import json
import sys

BASE_URL = "https://server.duinocoin.com"

def api_request(endpoint, params=None, method="GET", data=None):
    """Send a request to the Duino-Coin API and return the parsed JSON."""
    if params:
        query = urllib.parse.urlencode(params)
        url = f"{BASE_URL}/{endpoint}?{query}"
    else:
        url = f"{BASE_URL}/{endpoint}"

    headers = {"User-Agent": "DuinoCoinWallet/1.0"}
    req = urllib.request.Request(url, headers=headers, method=method)

    if data and method == "POST":
        data_bytes = urllib.parse.urlencode(data).encode()
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.data = data_bytes

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            content = response.read().decode()
            return json.loads(content)
    except urllib.error.URLError as e:
        return {"success": False, "error": f"Network error: {e.reason}"}
    except json.JSONDecodeError:
        return {"success": False, "error": "Invalid JSON response from server"}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {e}"}

def get_balance(username):
    """Get balance for a user."""
    result = api_request(f"balances/{username}")
    if result.get("success"):
        data = result.get("result", {})
        return data.get("balance")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
        return None

def get_user_transactions(username, limit=5):
    """Get recent transactions for a user."""
    result = api_request(f"user_transactions/{username}", params={"limit": limit})
    if result.get("success"):
        return result.get("result", [])
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
        return None

def get_miners(username=None):
    """Get miners. If username is provided, get user's miners, else all miners."""
    endpoint = f"miners/{username}" if username else "miners"
    result = api_request(endpoint)
    if result.get("success"):
        return result.get("result", [])
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
        return None

def send_transaction(username, password, recipient, amount, memo=""):
    """Send DUCO to a recipient."""
    params = {
        "username": username,
        "password": password,
        "recipient": recipient,
        "amount": amount,
        "memo": memo
    }
    result = api_request("transaction", params=params)
    if result.get("success"):
        return result.get("result", "Transaction successful")
    else:
        return f"Error: {result.get('error', 'Unknown error')}"

def get_statistics():
    """Get server statistics."""
    result = api_request("statistics")
    if result.get("success"):
        return result.get("result", {})
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
        return None

def display_balance(username):
    bal = get_balance(username)
    if bal is not None:
        print(f"Balance for {username}: {bal:.8f} DUCO")
    else:
        print("Could not retrieve balance.")

def display_transactions(username):
    txs = get_user_transactions(username)
    if txs is None:
        return
    if not txs:
        print("No transactions found.")
        return
    print(f"Recent transactions for {username}:")
    for tx in txs:
        print(f"  ID: {tx.get('id')} | {tx.get('datetime')} | "
              f"{tx.get('sender')} -> {tx.get('recipient')} | "
              f"Amount: {tx.get('amount')} DUCO | Memo: {tx.get('memo', 'None')}")

def display_my_miners(username):
    miners = get_miners(username)
    if miners is None:
        return
    if not miners:
        print("No miners found for this user.")
        return
    print(f"Miners for {username}:")
    for m in miners:
        print(f"  {m.get('identifier')}: {m.get('hashrate')} H/s, "
              f"accepted: {m.get('accepted')}, rejected: {m.get('rejected')}, "
              f"algorithm: {m.get('algorithm')}")

def display_all_miners():
    miners = get_miners()
    if miners is None:
        return
    if not miners:
        print("No miners found.")
        return
    print("All miners (first 20):")
    for m in miners[:20]:
        print(f"  {m.get('user')} - {m.get('identifier')}: {m.get('hashrate')} H/s")
    if len(miners) > 20:
        print("  ... and more")

def display_statistics():
    stats = get_statistics()
    if stats is None:
        return
    print("Server Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

def interactive_wallet():
    print("=== Duino-Coin Interactive Wallet ===")
    username = input("Enter your username: ").strip()
    if not username:
        print("Username cannot be empty.")
        return
    password = input("Enter your password: ").strip()
    # Note: password is not hidden per user's request (Không cần ẩn ô nhập mật khẩu)

    while True:
        print("\nOptions:")
        print("  1. Check balance")
        print("  2. View my transactions (last 5)")
        print("  3. View my miners")
        print("  4. Send DUCO")
        print("  5. View global statistics")
        print("  6. View all miners (first 20)")
        print("  7. Exit")
        choice = input("Select an option: ").strip()

        if choice == "1":
            display_balance(username)
        elif choice == "2":
            display_transactions(username)
        elif choice == "3":
            display_my_miners(username)
        elif choice == "4":
            recipient = input("Recipient username: ").strip()
            if not recipient:
                print("Recipient cannot be empty.")
                continue
            try:
                amount = float(input("Amount to send: ").strip())
                if amount <= 0:
                    print("Amount must be positive.")
                    continue
            except ValueError:
                print("Invalid amount.")
                continue
            memo = input("Memo (optional): ").strip()
            result = send_transaction(username, password, recipient, amount, memo)
            print(result)
        elif choice == "5":
            display_statistics()
        elif choice == "6":
            display_all_miners()
        elif choice == "7":
            print("Goodbye!")
            break
        else:
            print("Invalid option. Please try again.")

if __name__ == "__main__":
    try:
        interactive_wallet()
    except KeyboardInterrupt:
        print("\nExited by user.")
        sys.exit(0)

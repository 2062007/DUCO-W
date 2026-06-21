#!/usr/bin/env python3
"""
Duino-Coin Interactive Wallet
Pure Python, async, using aiohttp and pyaes.
"""

import asyncio
import aiohttp
import json
import hashlib
import os
import base64
import sys
import time
from datetime import datetime

# Third-party pure Python libraries
import pyaes
import colorama
from colorama import Fore, Style

# Constants
API_BASE = "http://server.duinocoin.com"
WALLET_FILE = "wallet.dat"
SALT_LEN = 16
IV_LEN = 16
KEY_LEN = 32  # AES-256


def derive_key(master_password: str, salt: bytes) -> bytes:
    """Derive a 32-byte AES key using SHA-256 of master_password + salt."""
    data = master_password.encode() + salt
    return hashlib.sha256(data).digest()


def encrypt_data(data: str, master_password: str) -> str:
    """Encrypt a string with AES-256-CBC. Returns base64(salt + iv + ciphertext)."""
    salt = os.urandom(SALT_LEN)
    iv = os.urandom(IV_LEN)
    key = derive_key(master_password, salt)

    # Pad data to AES block size (16 bytes)
    pad_len = 16 - (len(data) % 16)
    padded = data + chr(pad_len) * pad_len
    plaintext = padded.encode()

    aes = pyaes.AESModeOfOperationCBC(key, iv)
    ciphertext = aes.encrypt(plaintext)

    # Combine salt + iv + ciphertext and base64 encode
    combined = salt + iv + ciphertext
    return base64.b64encode(combined).decode()


def decrypt_data(encrypted_b64: str, master_password: str) -> str:
    """Decrypt data that was encrypted with encrypt_data()."""
    combined = base64.b64decode(encrypted_b64)
    salt = combined[:SALT_LEN]
    iv = combined[SALT_LEN:SALT_LEN + IV_LEN]
    ciphertext = combined[SALT_LEN + IV_LEN:]

    key = derive_key(master_password, salt)
    aes = pyaes.AESModeOfOperationCBC(key, iv)
    plaintext_padded = aes.decrypt(ciphertext)

    # Remove PKCS#7 padding
    pad_len = plaintext_padded[-1]
    plaintext = plaintext_padded[:-pad_len]
    return plaintext.decode()


class DuinoWallet:
    def __init__(self):
        self.username = None
        self.password = None  # plaintext, kept in memory after unlock
        self.session = None
        self.master_password = None  # only used during unlock/create

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    # ---------- Wallet file operations ----------
    async def load_wallet(self, master_password: str) -> bool:
        """Load and decrypt wallet file. Returns True on success."""
        if not os.path.exists(WALLET_FILE):
            return False
        try:
            with open(WALLET_FILE, "r") as f:
                data = json.load(f)
            encrypted = data.get("encrypted")
            if not encrypted:
                return False
            decrypted = decrypt_data(encrypted, master_password)
            parts = decrypted.split("\n", 1)
            if len(parts) != 2:
                return False
            self.username = parts[0].strip()
            self.password = parts[1].strip()
            self.master_password = master_password
            return True
        except Exception:
            return False

    async def save_wallet(self, master_password: str) -> None:
        """Encrypt and save wallet data."""
        if not self.username or not self.password:
            raise ValueError("Username and password must be set")
        plain = f"{self.username}\n{self.password}"
        encrypted = encrypt_data(plain, master_password)
        with open(WALLET_FILE, "w") as f:
            json.dump({"encrypted": encrypted}, f)

    async def create_wallet(self, username: str, password: str, master_password: str) -> None:
        """Create a new wallet file."""
        self.username = username
        self.password = password
        self.master_password = master_password
        await self.save_wallet(master_password)
        print(Fore.GREEN + f"Wallet created for {username}." + Style.RESET_ALL)

    # ---------- API helpers ----------
    async def _get(self, endpoint: str, params: dict = None) -> dict:
        """Perform a GET request and return JSON result."""
        url = f"{API_BASE}/{endpoint}"
        async with self.session.get(url, params=params) as resp:
            if resp.status != 200:
                raise Exception(f"HTTP {resp.status}: {await resp.text()}")
            data = await resp.json()
            if not data.get("success", False):
                raise Exception(f"API error: {data.get('error', 'Unknown error')}")
            return data.get("result", data)

    async def _post(self, endpoint: str, params: dict = None) -> dict:
        """Perform a POST request with parameters."""
        url = f"{API_BASE}/{endpoint}"
        # The API uses GET for most endpoints, but mining_key uses POST.
        # We'll use POST with params in the URL (since they are query string anyway)
        async with self.session.post(url, params=params) as resp:
            if resp.status != 200:
                raise Exception(f"HTTP {resp.status}: {await resp.text()}")
            data = await resp.json()
            if not data.get("success", False):
                raise Exception(f"API error: {data.get('error', 'Unknown error')}")
            return data.get("result", data)

    # ---------- API endpoints ----------
    async def get_balance(self) -> float:
        """Return user's balance."""
        result = await self._get(f"balances/{self.username}")
        return result["balance"]

    async def get_transactions(self, limit: int = 5) -> list:
        """Return recent transactions (up to limit)."""
        result = await self._get(f"user_transactions/{self.username}", {"limit": limit})
        return result  # list of transactions

    async def get_miners(self) -> list:
        """Return user's miners."""
        result = await self._get(f"miners/{self.username}")
        return result  # list of miners

    async def send_duco(self, recipient: str, amount: float, memo: str = "") -> dict:
        """Send DUCO to another user. Returns transaction info."""
        params = {
            "username": self.username,
            "password": self.password,
            "recipient": recipient,
            "amount": str(amount),
            "memo": memo
        }
        result = await self._get("transaction", params)
        return result

    async def get_shop_items(self) -> dict:
        """Return all shop items."""
        result = await self._get("shop_items")
        return result  # dict of items

    async def buy_shop_item(self, item_id: int) -> dict:
        """Buy a shop item."""
        params = {
            "password": self.password
        }
        result = await self._get(f"shop_buy/{self.username}", params)
        return result

    async def get_statistics(self) -> dict:
        """Return server statistics."""
        result = await self._get("statistics")
        return result

    async def set_mining_key(self, mining_key: str) -> dict:
        """Set or update the user's mining key."""
        # POST to /mining_key
        params = {
            "u": self.username,
            "k": mining_key,
            "password": self.password
        }
        result = await self._post("mining_key", params)
        return result

    async def check_mining_key(self, mining_key: str) -> bool:
        """Check if the given mining key is correct for the user."""
        params = {
            "u": self.username,
            "k": mining_key
        }
        result = await self._get("mining_key", params)
        return result.get("has_key", False)

    # ---------- Interactive menu ----------
    async def run(self):
        """Main interactive loop."""
        colorama.init(autoreset=True)

        # Unlock or create wallet
        if os.path.exists(WALLET_FILE):
            print(Fore.CYAN + "Duino-Coin Wallet" + Style.RESET_ALL)
            master = input("Enter master password: ")
            if not await self.load_wallet(master):
                print(Fore.RED + "Invalid master password or corrupted wallet." + Style.RESET_ALL)
                return
            print(Fore.GREEN + f"Welcome back, {self.username}!" + Style.RESET_ALL)
        else:
            print(Fore.CYAN + "No wallet found. Creating a new wallet." + Style.RESET_ALL)
            username = input("Duino-Coin username: ")
            password = input("Duino-Coin password: ")
            master = input("Set master password (for this wallet): ")
            await self.create_wallet(username, password, master)
            print(Fore.GREEN + "Wallet created successfully!" + Style.RESET_ALL)

        # Main menu
        while True:
            print("\n" + Fore.CYAN + "=== Main Menu ===" + Style.RESET_ALL)
            print("1. View balance")
            print("2. View recent transactions")
            print("3. View my miners")
            print("4. Send DUCO")
            print("5. View shop items")
            print("6. Buy shop item")
            print("7. View statistics")
            print("8. Set mining key")
            print("9. Exit")
            choice = input("Select option: ").strip()

            try:
                if choice == "1":
                    bal = await self.get_balance()
                    print(Fore.GREEN + f"Balance: {bal:.8f} DUCO" + Style.RESET_ALL)

                elif choice == "2":
                    limit = input("Number of transactions to show (default 5): ").strip()
                    limit = int(limit) if limit.isdigit() else 5
                    txs = await self.get_transactions(limit)
                    if not txs:
                        print("No transactions found.")
                    else:
                        for tx in txs:
                            print(f"{Fore.YELLOW}ID: {tx['id']} | {tx['datetime']}{Style.RESET_ALL}")
                            print(f"  {tx['sender']} -> {tx['recipient']} : {tx['amount']} DUCO")
                            print(f"  Memo: {tx.get('memo', 'None')}")
                            print()

                elif choice == "3":
                    miners = await self.get_miners()
                    if not miners:
                        print("No miners found.")
                    else:
                        for m in miners:
                            print(f"{Fore.YELLOW}Identifier: {m['identifier']}{Style.RESET_ALL}")
                            print(f"  Algorithm: {m['algorithm']}, Hashrate: {m['hashrate']} H/s")
                            print(f"  Accepted: {m['accepted']}, Rejected: {m['rejected']}")
                            print(f"  Software: {m['software']}")
                            print()

                elif choice == "4":
                    recipient = input("Recipient username: ").strip()
                    amount = input("Amount to send: ").strip()
                    try:
                        amount = float(amount)
                    except ValueError:
                        print(Fore.RED + "Invalid amount." + Style.RESET_ALL)
                        continue
                    memo = input("Memo (optional): ").strip()
                    try:
                        result = await self.send_duco(recipient, amount, memo)
                        print(Fore.GREEN + f"Transaction sent! ID: {result.get('id', 'N/A')}" + Style.RESET_ALL)
                    except Exception as e:
                        print(Fore.RED + f"Send failed: {e}" + Style.RESET_ALL)

                elif choice == "5":
                    items = await self.get_shop_items()
                    if not items:
                        print("No shop items available.")
                    else:
                        for idx, item in items.items():
                            print(f"{Fore.YELLOW}ID: {idx}{Style.RESET_ALL}")
                            print(f"  Name: {item['name']}")
                            print(f"  Price: {item['price']} DUCO")
                            print(f"  Description: {item['description']}")
                            print()

                elif choice == "6":
                    item_id = input("Enter item ID to buy: ").strip()
                    if not item_id.isdigit():
                        print(Fore.RED + "Invalid item ID." + Style.RESET_ALL)
                        continue
                    try:
                        result = await self.buy_shop_item(int(item_id))
                        print(Fore.GREEN + f"Purchase successful: {result}" + Style.RESET_ALL)
                    except Exception as e:
                        print(Fore.RED + f"Buy failed: {e}" + Style.RESET_ALL)

                elif choice == "7":
                    stats = await self.get_statistics()
                    # Pretty print some stats
                    print(Fore.CYAN + "Server Statistics:" + Style.RESET_ALL)
                    for key, value in stats.items():
                        if isinstance(value, (list, dict)):
                            continue  # skip complex fields
                        print(f"  {key}: {value}")
                    # Show top 10 if present
                    if "Top 10 richest miners" in stats:
                        print("  Top 10 richest miners:")
                        for line in stats["Top 10 richest miners"]:
                            print(f"    {line}")

                elif choice == "8":
                    mk = input("Enter new mining key (or leave blank to check current): ").strip()
                    if mk:
                        try:
                            result = await self.set_mining_key(mk)
                            print(Fore.GREEN + f"Mining key updated: {result}" + Style.RESET_ALL)
                        except Exception as e:
                            print(Fore.RED + f"Failed to set mining key: {e}" + Style.RESET_ALL)
                    else:
                        # Check current key (requires user to enter one to verify)
                        test_key = input("Enter the mining key to verify: ").strip()
                        try:
                            has = await self.check_mining_key(test_key)
                            if has:
                                print(Fore.GREEN + "Mining key is correct." + Style.RESET_ALL)
                            else:
                                print(Fore.RED + "Mining key is incorrect or not set." + Style.RESET_ALL)
                        except Exception as e:
                            print(Fore.RED + f"Check failed: {e}" + Style.RESET_ALL)

                elif choice == "9":
                    print("Goodbye!")
                    break

                else:
                    print(Fore.RED + "Invalid option." + Style.RESET_ALL)

            except Exception as e:
                print(Fore.RED + f"Error: {e}" + Style.RESET_ALL)


async def main():
    async with DuinoWallet() as wallet:
        await wallet.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExited.")

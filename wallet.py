#!/usr/bin/env python3
"""
Duino-Coin Interactive Wallet – Framed UI
Pure Python, async, using aiohttp and pyaes (BlockFeeder API).
Uses HTTPS and colorama for a polished terminal interface.
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

import pyaes
import colorama
from colorama import Fore, Style, init

# Constants
API_BASE = "https://server.duinocoin.com"
WALLET_FILE = "wallet.dat"
SALT_LEN = 16
IV_LEN = 16
KEY_LEN = 32  # AES-256


def derive_key(master_password: str, salt: bytes) -> bytes:
    """Derive a 32-byte AES key using SHA-256 of master_password + salt."""
    data = master_password.encode() + salt
    return hashlib.sha256(data).digest()


def encrypt_data(data: str, master_password: str) -> str:
    """
    Encrypt a string with AES-256-CBC using pyaes.Encrypter (PKCS#7 padding).
    Returns base64(salt + iv + ciphertext).
    """
    salt = os.urandom(SALT_LEN)
    iv = os.urandom(IV_LEN)
    key = derive_key(master_password, salt)

    mode = pyaes.AESModeOfOperationCBC(key, iv)
    encrypter = pyaes.Encrypter(mode)

    plaintext = data.encode('utf-8')
    ciphertext = encrypter.feed(plaintext)
    ciphertext += encrypter.feed()  # finalise with padding

    combined = salt + iv + ciphertext
    return base64.b64encode(combined).decode()


def decrypt_data(encrypted_b64: str, master_password: str) -> str:
    """Decrypt data encrypted with encrypt_data()."""
    combined = base64.b64decode(encrypted_b64)
    salt = combined[:SALT_LEN]
    iv = combined[SALT_LEN:SALT_LEN + IV_LEN]
    ciphertext = combined[SALT_LEN + IV_LEN:]

    key = derive_key(master_password, salt)
    mode = pyaes.AESModeOfOperationCBC(key, iv)
    decrypter = pyaes.Decrypter(mode)

    plaintext_padded = decrypter.feed(ciphertext)
    plaintext_padded += decrypter.feed()  # finalise (strips padding)

    return plaintext_padded.decode('utf-8')


def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_frame(title: str, content_lines: list, width: int = 60):
    """Print a framed box with a title and content lines."""
    border = Fore.CYAN + '+' + '-' * (width - 2) + '+' + Style.RESET_ALL
    print(border)
    # Title line
    title_line = f"| {Fore.YELLOW}{title}{Style.RESET_ALL}"
    print(title_line + ' ' * (width - len(title_line) - 1) + '|')
    print(Fore.CYAN + '|' + '-' * (width - 2) + '|' + Style.RESET_ALL)
    for line in content_lines:
        # Truncate if too long
        if len(line) > width - 4:
            line = line[:width - 7] + '...'
        print(f"| {line.ljust(width - 4)} |")
    print(border)


class DuinoWallet:
    def __init__(self):
        self.username = None
        self.password = None
        self.session = None
        self.master_password = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    # ---------- Wallet file operations ----------
    async def load_wallet(self, master_password: str) -> bool:
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
        except Exception as e:
            print(Fore.RED + f"Load error: {e}" + Style.RESET_ALL)
            return False

    async def save_wallet(self, master_password: str) -> None:
        if not self.username or not self.password:
            raise ValueError("Username and password must be set")
        plain = f"{self.username}\n{self.password}"
        encrypted = encrypt_data(plain, master_password)
        with open(WALLET_FILE, "w") as f:
            json.dump({"encrypted": encrypted}, f)

    async def create_wallet(self, username: str, password: str, master_password: str) -> None:
        self.username = username
        self.password = password
        self.master_password = master_password
        await self.save_wallet(master_password)
        print(Fore.GREEN + f"Wallet created for {username}." + Style.RESET_ALL)

    # ---------- API helpers ----------
    async def _request(self, method: str, endpoint: str, params: dict = None):
        """Unified request handler that works with JSON or plain text responses."""
        url = f"{API_BASE}/{endpoint}"
        async with self.session.request(method, url, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"HTTP {resp.status}: {text}")

            # Try to parse as JSON
            try:
                data = await resp.json()
            except aiohttp.ContentTypeError:
                # Not JSON – return the raw text
                text = await resp.text()
                return text

            # If JSON, check success flag
            if isinstance(data, dict) and not data.get("success", True):
                # Prefer 'message' over 'error' (some endpoints use 'message')
                error_msg = data.get("message") or data.get("error") or "Unknown error"
                # If still unknown, include the full response for debugging
                if error_msg == "Unknown error":
                    error_msg = f"Unknown error (full response: {data})"
                raise Exception(f"API error: {error_msg}")

            # Return the 'result' field if present, otherwise the whole data
            return data.get("result", data)

    async def _get(self, endpoint: str, params: dict = None):
        return await self._request("GET", endpoint, params)

    async def _post(self, endpoint: str, params: dict = None):
        return await self._request("POST", endpoint, params)

    # ---------- API endpoints ----------
    async def get_balance(self) -> float:
        result = await self._get(f"balances/{self.username}")
        if isinstance(result, dict):
            return result["balance"]
        return float(result)

    async def get_transactions(self, limit: int = 5) -> list:
        result = await self._get(f"user_transactions/{self.username}", {"limit": limit})
        if isinstance(result, list):
            return result
        return result

    async def get_miners(self) -> list:
        try:
            result = await self._get(f"miners/{self.username}")
            if isinstance(result, list):
                return result
            return []
        except Exception as e:
            # If the error message indicates no miners, return empty list silently
            if "No miners detected" in str(e):
                return []
            raise

    async def send_duco(self, recipient: str, amount: float, memo: str = ""):
        params = {
            "username": self.username,
            "password": self.password,
            "recipient": recipient,
            "amount": str(amount),
            "memo": memo
        }
        return await self._get("transaction", params)

    async def get_shop_items(self) -> dict:
        result = await self._get("shop_items")
        return result

    async def buy_shop_item(self, item_id: int) -> dict:
        params = {"password": self.password}
        result = await self._get(f"shop_buy/{self.username}", params)
        return result

    async def get_statistics(self) -> dict:
        result = await self._get("statistics")
        return result

    async def set_mining_key(self, mining_key: str) -> dict:
        params = {
            "u": self.username,
            "k": mining_key,
            "password": self.password
        }
        result = await self._post("mining_key", params)
        return result

    async def check_mining_key(self, mining_key: str) -> bool:
        params = {"u": self.username, "k": mining_key}
        result = await self._get("mining_key", params)
        return result.get("has_key", False)

    # ---------- Interactive menu ----------
    async def run(self):
        init(autoreset=True)

        # Unlock or create wallet
        if os.path.exists(WALLET_FILE):
            clear_screen()
            print(Fore.CYAN + "Duino-Coin Wallet" + Style.RESET_ALL)
            master = input("Enter master password: ")
            if not await self.load_wallet(master):
                print(Fore.RED + "Invalid master password or corrupted wallet." + Style.RESET_ALL)
                return
        else:
            clear_screen()
            print(Fore.CYAN + "No wallet found. Creating a new wallet." + Style.RESET_ALL)
            username = input("Duino-Coin username: ")
            password = input("Duino-Coin password: ")
            master = input("Set master password (for this wallet): ")
            await self.create_wallet(username, password, master)
            print(Fore.GREEN + "Wallet created successfully!" + Style.RESET_ALL)
            input("Press Enter to continue...")

        # Main loop
        while True:
            clear_screen()
            # Fetch balance for header
            try:
                bal = await self.get_balance()
                balance_str = f"{bal:.8f} DUCO"
            except:
                balance_str = "?"

            # Build header
            header = f"  {Fore.CYAN}Duino-Coin Wallet{Style.RESET_ALL}  |  {Fore.GREEN}{self.username}{Style.RESET_ALL}  |  Balance: {Fore.YELLOW}{balance_str}{Style.RESET_ALL}"

            # Menu options
            menu_lines = [
                "1. View balance",
                "2. View recent transactions",
                "3. View my miners",
                "4. Send DUCO",
                "5. View shop items",
                "6. Buy shop item",
                "7. View statistics",
                "8. Set mining key",
                "9. Exit"
            ]
            # Frame it with the header
            print_frame(header, menu_lines, width=70)
            choice = input(Fore.CYAN + "Select option: " + Style.RESET_ALL).strip()

            try:
                if choice == "1":
                    bal = await self.get_balance()
                    clear_screen()
                    print_frame("Balance", [f"{Fore.GREEN}{bal:.8f} DUCO{Style.RESET_ALL}"], width=50)
                    input("Press Enter to continue...")

                elif choice == "2":
                    limit = input("Number of transactions to show (default 5): ").strip()
                    limit = int(limit) if limit.isdigit() else 5
                    txs = await self.get_transactions(limit)
                    clear_screen()
                    if not txs:
                        print_frame("Recent Transactions", ["No transactions found."], width=60)
                    else:
                        lines = []
                        for tx in txs:
                            lines.append(f"{Fore.YELLOW}ID:{tx['id']}{Style.RESET_ALL}  {tx['datetime']}")
                            lines.append(f"  {tx['sender']} -> {tx['recipient']} : {Fore.GREEN}{tx['amount']} DUCO{Style.RESET_ALL}")
                            lines.append(f"  Memo: {tx.get('memo', 'None')}")
                            lines.append("")
                        print_frame("Recent Transactions", lines, width=70)
                    input("Press Enter to continue...")

                elif choice == "3":
                    clear_screen()
                    try:
                        miners = await self.get_miners()
                        if not miners:
                            print_frame("My Miners", ["No miners active."], width=50)
                        else:
                            lines = []
                            for m in miners:
                                lines.append(f"{Fore.YELLOW}Identifier: {m['identifier']}{Style.RESET_ALL}")
                                lines.append(f"  Algorithm: {m['algorithm']}, Hashrate: {Fore.CYAN}{m['hashrate']} H/s{Style.RESET_ALL}")
                                lines.append(f"  Accepted: {Fore.GREEN}{m['accepted']}{Style.RESET_ALL}, Rejected: {Fore.RED}{m['rejected']}{Style.RESET_ALL}")
                                lines.append(f"  Software: {m['software']}")
                                lines.append("")
                            print_frame("My Miners", lines, width=70)
                    except Exception as e:
                        print_frame("My Miners", [f"{Fore.RED}Could not fetch miners: {e}{Style.RESET_ALL}"], width=60)
                    input("Press Enter to continue...")

                elif choice == "4":
                    clear_screen()
                    print_frame("Send DUCO", ["Enter recipient and amount."], width=50)
                    recipient = input("Recipient username: ").strip()
                    amount = input("Amount to send: ").strip()
                    try:
                        amount = float(amount)
                    except ValueError:
                        print(Fore.RED + "Invalid amount." + Style.RESET_ALL)
                        input("Press Enter to continue...")
                        continue
                    memo = input("Memo (optional): ").strip()
                    try:
                        result = await self.send_duco(recipient, amount, memo)
                        if isinstance(result, dict):
                            tx_id = result.get('id', 'N/A')
                            msg = f"Transaction sent! ID: {Fore.GREEN}{tx_id}{Style.RESET_ALL}"
                        else:
                            msg = str(result)
                            if "Successfully transferred" in msg:
                                parts = msg.split(',')
                                if len(parts) >= 3:
                                    tx_hash = parts[-1].strip()
                                    msg = f"Transaction sent! Hash: {Fore.GREEN}{tx_hash}{Style.RESET_ALL}"
                                else:
                                    msg = Fore.GREEN + msg + Style.RESET_ALL
                            else:
                                msg = Fore.GREEN + msg + Style.RESET_ALL
                        clear_screen()
                        print_frame("Send DUCO", [msg], width=60)
                    except Exception as e:
                        clear_screen()
                        print_frame("Send DUCO", [f"{Fore.RED}Send failed: {e}{Style.RESET_ALL}"], width=60)
                    input("Press Enter to continue...")

                elif choice == "5":
                    clear_screen()
                    items = await self.get_shop_items()
                    if not items:
                        print_frame("Shop Items", ["No items available."], width=50)
                    else:
                        lines = []
                        for idx, item in items.items():
                            lines.append(f"{Fore.YELLOW}ID: {idx}{Style.RESET_ALL}")
                            lines.append(f"  Name: {Fore.CYAN}{item['name']}{Style.RESET_ALL}")
                            lines.append(f"  Price: {Fore.GREEN}{item['price']} DUCO{Style.RESET_ALL}")
                            lines.append(f"  {item['description']}")
                            lines.append("")
                        print_frame("Shop Items", lines, width=70)
                    input("Press Enter to continue...")

                elif choice == "6":
                    clear_screen()
                    print_frame("Buy Shop Item", ["Enter item ID to purchase."], width=50)
                    item_id = input("Enter item ID: ").strip()
                    if not item_id.isdigit():
                        print(Fore.RED + "Invalid item ID." + Style.RESET_ALL)
                        input("Press Enter to continue...")
                        continue
                    try:
                        result = await self.buy_shop_item(int(item_id))
                        if isinstance(result, dict):
                            msg = f"Purchase successful: {result}"
                        else:
                            msg = str(result)
                        clear_screen()
                        print_frame("Buy Shop Item", [Fore.GREEN + msg + Style.RESET_ALL], width=60)
                    except Exception as e:
                        clear_screen()
                        print_frame("Buy Shop Item", [f"{Fore.RED}Buy failed: {e}{Style.RESET_ALL}"], width=60)
                    input("Press Enter to continue...")

                elif choice == "7":
                    clear_screen()
                    try:
                        stats = await self.get_statistics()
                        lines = []
                        for key, value in stats.items():
                            if isinstance(value, (list, dict)):
                                continue
                            lines.append(f"{Fore.CYAN}{key}:{Style.RESET_ALL} {value}")
                        if "Top 10 richest miners" in stats:
                            lines.append("")
                            lines.append(f"{Fore.YELLOW}Top 10 richest miners:{Style.RESET_ALL}")
                            for line in stats["Top 10 richest miners"]:
                                lines.append(f"  {line}")
                        print_frame("Server Statistics", lines, width=70)
                    except Exception as e:
                        print_frame("Server Statistics", [f"{Fore.RED}Could not fetch statistics: {e}{Style.RESET_ALL}"], width=60)
                    input("Press Enter to continue...")

                elif choice == "8":
                    clear_screen()
                    print_frame("Mining Key", ["Enter new key or leave blank to check current."], width=60)
                    mk = input("New mining key (or blank to verify): ").strip()
                    if mk:
                        try:
                            result = await self.set_mining_key(mk)
                            msg = f"Mining key updated: {result}"
                            clear_screen()
                            print_frame("Mining Key", [Fore.GREEN + msg + Style.RESET_ALL], width=60)
                        except Exception as e:
                            clear_screen()
                            print_frame("Mining Key", [f"{Fore.RED}Failed to set mining key: {e}{Style.RESET_ALL}"], width=60)
                    else:
                        test_key = input("Enter the mining key to verify: ").strip()
                        try:
                            has = await self.check_mining_key(test_key)
                            if has:
                                msg = "Mining key is correct."
                            else:
                                msg = "Mining key is incorrect or not set."
                            clear_screen()
                            if has:
                                print_frame("Mining Key", [Fore.GREEN + msg + Style.RESET_ALL], width=60)
                            else:
                                print_frame("Mining Key", [Fore.RED + msg + Style.RESET_ALL], width=60)
                        except Exception as e:
                            clear_screen()
                            print_frame("Mining Key", [f"{Fore.RED}Check failed: {e}{Style.RESET_ALL}"], width=60)
                    input("Press Enter to continue...")

                elif choice == "9":
                    clear_screen()
                    print(Fore.CYAN + "Goodbye!" + Style.RESET_ALL)
                    break

                else:
                    print(Fore.RED + "Invalid option." + Style.RESET_ALL)
                    input("Press Enter to continue...")

            except Exception as e:
                clear_screen()
                print_frame("Error", [f"{Fore.RED}Unexpected error: {e}{Style.RESET_ALL}"], width=60)
                input("Press Enter to continue...")


async def main():
    async with DuinoWallet() as wallet:
        await wallet.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExited.")

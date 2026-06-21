#!/usr/bin/env python3
"""
Duino-Coin Interactive Wallet
Pure Python, async, using aiohttp and pyaes (BlockFeeder API).
Uses HTTPS for secure communication.
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
from colorama import Fore, Style

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

    # Create the CBC mode and the encrypter
    mode = pyaes.AESModeOfOperationCBC(key, iv)
    encrypter = pyaes.Encrypter(mode)

    # Feed the plaintext bytes (Encrypter buffers internally)
    plaintext = data.encode('utf-8')
    ciphertext = encrypter.feed(plaintext)

    # Finalise with padding (automatically adds PKCS#7 padding)
    ciphertext += encrypter.feed()

    # Combine salt + iv + ciphertext and base64 encode
    combined = salt + iv + ciphertext
    return base64.b64encode(combined).decode()


def decrypt_data(encrypted_b64: str, master_password: str) -> str:
    """
    Decrypt data that was encrypted with encrypt_data().
    Uses pyaes.Decrypter, which strips PKCS#7 padding automatically.
    """
    combined = base64.b64decode(encrypted_b64)
    salt = combined[:SALT_LEN]
    iv = combined[SALT_LEN:SALT_LEN + IV_LEN]
    ciphertext = combined[SALT_LEN + IV_LEN:]

    key = derive_key(master_password, salt)

    # Create the CBC mode and the decrypter
    mode = pyaes.AESModeOfOperationCBC(key, iv)
    decrypter = pyaes.Decrypter(mode)

    # Feed the ciphertext
    plaintext_padded = decrypter.feed(ciphertext)

    # Finalise (strips padding)
    plaintext_padded += decrypter.feed()

    return plaintext_padded.decode('utf-8')


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
    async def _get(self, endpoint: str, params: dict = None) -> dict:
        url = f"{API_BASE}/{endpoint}"
        async with self.session.get(url, params=params) as resp:
            if resp.status != 200:
                raise Exception(f"HTTP {resp.status}: {await resp.text()}")
            data = await resp.json()
            if not data.get("success", False):
                raise Exception(f"API error: {data.get('error', 'Unknown error')}")
            return data.get("result", data)

    async def _post(self, endpoint: str, params: dict = None) -> dict:
        url = f"{API_BASE}/{endpoint}"
        async with self.session.post(url, params=params) as resp:
            if resp.status != 200:
                raise Exception(f"HTTP {resp.status}: {await resp.text()}")
            data = await resp.json()
            if not data.get("success", False):
                raise Exception(f"API error: {data.get('error', 'Unknown error')}")
            return data.get("result", data)

    # ---------- API endpoints ----------
    async def get_balance(self) -> float:
        result = await self._get(f"balances/{self.username}")
        return result["balance"]

    async def get_transactions(self, limit: int = 5) -> list:
        result = await self._get(f"user_transactions/{self.username}", {"limit": limit})
        return result

    async def get_miners(self) -> list:
        result = await self._get(f"miners/{self.username}")
        return result

    async def send_duco(self, recipient: str, amount: float, memo: str = "") -> dict:
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
        colorama.init(autoreset=True)

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
                    print(Fore.CYAN + "Server Statistics:" + Style.RESET_ALL)
                    for key, value in stats.items():
                        if isinstance(value, (list, dict)):
                            continue
                        print(f"  {key}: {value}")
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

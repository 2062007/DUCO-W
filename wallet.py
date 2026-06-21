#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Duino-Coin Pure Python Wallet
Sử dụng thư viện chuẩn: urllib.request, json, argparse, os, sys
Không phụ thuộc vào bất kỳ gói C nào.
"""

import urllib.request
import urllib.parse
import json
import argparse
import os
import sys
from getpass import getpass

BASE_URL = "https://server.duinocoin.com"

class DucWallet:
    """Ví điện tử Duino-Coin"""

    def __init__(self, username=None, password=None):
        self.username = username
        self.password = password
        self.config_dir = os.path.expanduser("~/.duco-wallet")
        self.config_file = os.path.join(self.config_dir, "wallet.json")
        if username and password:
            self.save()

    def save(self):
        """Lưu thông tin username/password vào file cấu hình"""
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir, mode=0o700, exist_ok=True)
        data = {"username": self.username, "password": self.password}
        with open(self.config_file, "w") as f:
            json.dump(data, f)
        os.chmod(self.config_file, 0o600)

    @classmethod
    def load(cls):
        """Tải ví từ file cấu hình"""
        config_dir = os.path.expanduser("~/.duco-wallet")
        config_file = os.path.join(config_dir, "wallet.json")
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                data = json.load(f)
            return cls(data.get("username"), data.get("password"))
        return None

    def _api_request(self, endpoint, params=None, method="GET", data=None):
        """Thực hiện yêu cầu API và trả về dict kết quả"""
        if params:
            query = urllib.parse.urlencode(params)
            url = f"{BASE_URL}/{endpoint}?{query}"
        else:
            url = f"{BASE_URL}/{endpoint}"

        req = urllib.request.Request(url, method=method)
        if data:
            req.add_header("Content-Type", "application/json")
            req.data = json.dumps(data).encode("utf-8")

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                resp_data = response.read().decode("utf-8")
                return json.loads(resp_data)
        except urllib.error.URLError as e:
            return {"success": False, "error": f"Lỗi kết nối: {e.reason}"}
        except json.JSONDecodeError:
            return {"success": False, "error": "Phản hồi không hợp lệ từ máy chủ"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_balance(self):
        """Lấy số dư của ví"""
        if not self.username:
            return {"success": False, "error": "Chưa đăng nhập"}
        result = self._api_request(f"balances/{self.username}")
        if result.get("success"):
            return result["result"]
        return result

    def get_transactions(self, limit=5):
        """Lấy danh sách giao dịch gần đây"""
        if not self.username:
            return {"success": False, "error": "Chưa đăng nhập"}
        params = {"limit": limit}
        result = self._api_request(f"user_transactions/{self.username}", params)
        return result

    def get_miners(self):
        """Lấy danh sách miners của user"""
        if not self.username:
            return {"success": False, "error": "Chưa đăng nhập"}
        result = self._api_request(f"miners/{self.username}")
        return result

    def send(self, recipient, amount, memo=""):
        """Gửi DUCO đến recipient"""
        if not self.username or not self.password:
            return {"success": False, "error": "Chưa đăng nhập hoặc thiếu mật khẩu"}
        params = {
            "username": self.username,
            "password": self.password,
            "recipient": recipient,
            "amount": str(amount),
            "memo": memo
        }
        result = self._api_request("transaction", params)
        return result

    def get_info(self):
        """Lấy thông tin tổng hợp: balance, miners, transactions"""
        if not self.username:
            return {"success": False, "error": "Chưa đăng nhập"}
        result = self._api_request(f"users/{self.username}")
        return result

    def change_mining_key(self, new_key):
        """Thay đổi mining key (yêu cầu mật khẩu)"""
        if not self.username or not self.password:
            return {"success": False, "error": "Chưa đăng nhập hoặc thiếu mật khẩu"}
        params = {
            "u": self.username,
            "k": new_key,
            "password": self.password
        }
        result = self._api_request("mining_key", params, method="POST")
        return result

    def get_mining_key_status(self):
        """Kiểm tra xem user đã có mining key chưa"""
        if not self.username:
            return {"success": False, "error": "Chưa đăng nhập"}
        params = {"u": self.username, "k": ""}  # k rỗng để kiểm tra
        result = self._api_request("mining_key", params)
        return result


def main():
    parser = argparse.ArgumentParser(description="Duino-Coin Wallet CLI")
    subparsers = parser.add_subparsers(dest="command", help="Lệnh thực hiện")

    # Lệnh login
    login_parser = subparsers.add_parser("login", help="Đăng nhập và lưu thông tin")
    login_parser.add_argument("username", help="Tên đăng nhập")
    login_parser.add_argument("--password", help="Mật khẩu (nếu không cung cấp sẽ được hỏi)")

    # Lệnh balance
    balance_parser = subparsers.add_parser("balance", help="Xem số dư")

    # Lệnh send
    send_parser = subparsers.add_parser("send", help="Gửi DUCO")
    send_parser.add_argument("recipient", help="Người nhận")
    send_parser.add_argument("amount", type=float, help="Số lượng DUCO")
    send_parser.add_argument("--memo", default="", help="Ghi chú")

    # Lệnh transactions
    tx_parser = subparsers.add_parser("transactions", help="Xem lịch sử giao dịch")
    tx_parser.add_argument("--limit", type=int, default=5, help="Số lượng giao dịch (mặc định 5)")

    # Lệnh miners
    miners_parser = subparsers.add_parser("miners", help="Xem danh sách miners")

    # Lệnh info
    info_parser = subparsers.add_parser("info", help="Xem thông tin tổng hợp")

    # Lệnh miningkey
    mk_parser = subparsers.add_parser("miningkey", help="Quản lý mining key")
    mk_parser.add_argument("--set", help="Đặt mining key mới")
    mk_parser.add_argument("--check", action="store_true", help="Kiểm tra trạng thái")

    args = parser.parse_args()

    # Tải ví đã lưu
    wallet = DucWallet.load()

    # Nếu chưa có và không phải lệnh login, yêu cầu đăng nhập
    if not wallet and args.command != "login":
        print("❌ Chưa đăng nhập. Hãy chạy: python wallet.py login <username>")
        sys.exit(1)

    # Xử lý lệnh login
    if args.command == "login":
        username = args.username
        password = args.password or getpass("Nhập mật khẩu: ")
        wallet = DucWallet(username, password)
        print(f"✅ Đã lưu thông tin cho {username}")
        sys.exit(0)

    # Các lệnh khác cần có wallet
    if not wallet:
        print("❌ Không tìm thấy ví. Hãy đăng nhập trước.")
        sys.exit(1)

    # Xử lý lệnh
    if args.command == "balance":
        result = wallet.get_balance()
        if result.get("success") is False and "error" in result:
            print(f"❌ Lỗi: {result['error']}")
        else:
            print(f"💰 Số dư của {wallet.username}: {result.get('balance', 0):.8f} DUCO")

    elif args.command == "send":
        if not wallet.password:
            wallet.password = getpass("Nhập mật khẩu: ")
        result = wallet.send(args.recipient, args.amount, args.memo)
        if result.get("success"):
            print(f"✅ Đã gửi {args.amount} DUCO đến {args.recipient}")
            if "result" in result:
                print(result["result"])
        else:
            print(f"❌ Lỗi: {result.get('error', 'Không xác định')}")

    elif args.command == "transactions":
        result = wallet.get_transactions(args.limit)
        if result.get("success"):
            txs = result.get("result", [])
            if not txs:
                print("📭 Không có giao dịch nào.")
            else:
                print(f"📋 {len(txs)} giao dịch gần đây:")
                for tx in txs:
                    print(f"  {tx['datetime']} | {tx['sender']} -> {tx['recipient']} | {tx['amount']} DUCO | {tx['memo']}")
        else:
            print(f"❌ Lỗi: {result.get('error', 'Không xác định')}")

    elif args.command == "miners":
        result = wallet.get_miners()
        if result.get("success"):
            miners = result.get("result", [])
            if not miners:
                print("⛏️ Không có miner nào.")
            else:
                print(f"⛏️ {len(miners)} miner(s) đang hoạt động:")
                for m in miners:
                    print(f"  {m['identifier']} | Hashrate: {m['hashrate']} H/s | Diff: {m['diff']} | Accepted: {m['accepted']}")
        else:
            print(f"❌ Lỗi: {result.get('error', 'Không xác định')}")

    elif args.command == "info":
        result = wallet.get_info()
        if result.get("success"):
            data = result.get("result", {})
            bal = data.get("balance", {})
            print(f"👤 {wallet.username}")
            print(f"💰 Số dư: {bal.get('balance', 0):.8f} DUCO")
            print(f"⛏️ Số miners: {len(data.get('miners', []))}")
            print(f"📋 Số giao dịch gần đây: {len(data.get('transactions', []))}")
        else:
            print(f"❌ Lỗi: {result.get('error', 'Không xác định')}")

    elif args.command == "miningkey":
        if args.check:
            result = wallet.get_mining_key_status()
            if result.get("success"):
                has_key = result.get("has_key", False)
                print(f"🔑 Mining key: {'có' if has_key else 'không có'}")
            else:
                print(f"❌ Lỗi: {result.get('error', 'Không xác định')}")
        elif args.set:
            if not wallet.password:
                wallet.password = getpass("Nhập mật khẩu: ")
            result = wallet.change_mining_key(args.set)
            if result.get("success"):
                print("✅ Đã cập nhật mining key")
            else:
                print(f"❌ Lỗi: {result.get('error', 'Không xác định')}")
        else:
            print("⚠️ Vui lòng sử dụng --set <key> hoặc --check")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

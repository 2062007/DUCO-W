# DUCO-W — Duino‑Coin Interactive Wallet <img src="https://github.com/revoxhere/duino-coin/raw/master/Resources/duco.png" width="32" height="32" />

[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**A lightweight, secure, and fully interactive command‑line wallet for [Duino‑Coin](https://duinocoin.com).**  
Built with pure Python, async I/O, and end‑to‑end encryption – all you need is your terminal.

---

## ✨ Features

- **🔐 Secure storage** – your Duino‑Coin credentials are encrypted with AES‑256‑CBC (PKCS#7 padding) using a master password; the encryption key is derived via SHA‑256 + a random salt.
- **🌐 Async & fast** – built with `aiohttp` for non‑blocking API calls; all network requests are asynchronous.
- **📦 Zero external dependencies** – only three lightweight libraries (`aiohttp`, `pyaes`, `colorama`) – everything else is from the standard library.
- **🖥️ Beautiful terminal UI** – clean framed menus with colours; clears the screen for a distraction‑free experience.
- **💱 Full API coverage** – view balance, recent transactions, your miners, shop items, buy items, send DUCO, check statistics, and manage your mining key.
- **🔒 HTTPS** – all communication with the Duino‑Coin server is encrypted (server supports HTTPS).
- **📦 Portable** – wallet data is stored in a single `wallet.dat` file – just back it up.

---

## 📥 Installation

Clone the repository:

```bash
git clone https://github.com/2062007/DUCO-W.git
cd DUCO-W
```

Install the required dependencies (the script will also work without this step, but it's recommended):

```bash
pip install -r requirements.txt
```

The requirements.txt contains only:

```
aiohttp
pyaes
colorama
```

---

🚀 Usage

Run the wallet:

```bash
python3 wallet.py
```

First launch

· If no wallet file is found, you will be prompted to set up a new wallet:
  · Duino‑Coin username
  · Duino‑Coin password (the one you use for mining / web dashboard)
  · Master password – this is used to encrypt your wallet file locally. It is not sent anywhere and is never stored.

Subsequent launches

· Enter your master password to unlock the wallet.

Main menu

After unlocking, you'll see a framed menu with the following options:

```
1. View balance
2. View recent transactions
3. View my miners
4. Send DUCO
5. View shop items
6. Buy shop item
7. View statistics
8. Set mining key
9. Exit
```

Select the number and follow the prompts – every action is performed against the live Duino‑Coin API.

---

🛠️ Dependencies

All required libraries are pure‑Python and available on PyPI:

· aiohttp – for asynchronous HTTP requests.
· pyaes – pure‑Python AES implementation (no external C libraries).
· colorama – for cross‑platform coloured terminal output.

---

🔐 Security Model

· Your Duino‑Coin username and password are never stored in plain text.
· The master password is used to derive a 256‑bit AES key via SHA‑256 with a random salt.
· Encryption is performed with AES‑256‑CBC; pyaes.Encrypter handles PKCS#7 padding automatically.
· The wallet file (wallet.dat) contains only the base64‑encoded salt, IV, and ciphertext.
· All network communication uses HTTPS (https://server.duinocoin.com).

---

🌐 API Endpoints Used

The wallet leverages the official Duino‑Coin REST API. The following endpoints are implemented:

Endpoint Description
GET /balances/<username> Fetch user balance.
GET /user_transactions/<username>?limit=N Fetch last N transactions.
GET /miners/<username> Fetch active miners for the user.
GET /transaction?... Send DUCO (requires username, password, recipient, amount, memo).
GET /shop_items List all purchasable shop items.
GET /shop_buy/<username>?item=X&password=... Buy a shop item.
GET /statistics Fetch server statistics.
GET /mining_key?u=...&k=... Verify an existing mining key.
POST /mining_key?u=...&k=...&password=... Set a new mining key.

The wallet gracefully handles both JSON and plain‑text responses, and provides clear error messages for API failures.

---

📂 Files

· wallet.py – the main wallet script.
· requirements.txt – list of Python dependencies.
· wallet.dat – created automatically on first run; do not share this file.

---

🤝 Contributing

Contributions, issues, and feature requests are welcome!
Feel free to open a pull request or an issue on GitHub.

---

📄 License

This project is licensed under the MIT License – see the LICENSE file for details.

---

�Acknowledgements

· Duino‑Coin – for the awesome cryptocurrency and its open API.
· pyaes – pure‑Python AES implementation.
· aiohttp – async HTTP client/server framework.

---

Enjoy your Duino‑Coin journey!

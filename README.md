# Lucid Discord Multi-Account Giveaway Auto-Claimer

A high-performance Python script designed to monitor a specific Discord channel in real-time and instantly claim giveaway drops/codes across 2-3+ accounts concurrently.

---

## Features
- **Real-Time Discord Listener**: Connects to Discord WebSockets to intercept messages within **10-50 milliseconds**.
- **Multi-Account Concurrent Claiming**: Submits giveaway codes simultaneously across **2, 3, or more target accounts** using `asyncio.gather()`.
- **Regex Code Extractor**: Automatically parses plain text chat messages and Discord Rich Embeds for codes, claim keys, and drop URLs.
- **Connection Pooling**: Keeps persistent TCP/TLS connections open via `aiohttp` to ensure zero DNS/handshake latency during drop execution.

---

## Setup Instructions

### 1. Prerequisites
- Python 3.9 or higher installed on your machine.

### 2. Installation
Open your terminal and navigate to this folder:
```bash
cd /Users/yashjha/.gemini/antigravity/scratch/lucid_claimer
```

Create a virtual environment and install the required dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env` using your text editor and fill in your parameters:
- `DISCORD_TOKEN`: Your Discord account user token.
- `TARGET_CHANNEL_ID`: The ID of the Discord channel where drops are posted (Enable Developer Mode in Discord -> Right click channel -> Copy Channel ID).
- `ACCOUNT_TOKENS`: A comma-separated list of your trading account API tokens (e.g., `token_account1,token_account2,token_account3`).
- `REDEMPTION_API_URL`: The exact API URL used to redeem/claim codes (e.g., `https://api.lucidtrading.com/v1/giveaways/claim`).

---

## Running the Auto-Claimer

With your virtual environment activated, run:
```bash
python main.py
```

### Example Output
```text
[2026-08-07 22:58:30] INFO: Initialized MultiAccountClaimer with 3 accounts.
[2026-08-07 22:58:31] INFO: ✅ Discord Listener Connected as: User (ID: 9876543210)
[2026-08-07 22:58:31] INFO: 👀 Monitoring Target Channel ID: 123456789012345678
[2026-08-07 22:58:31] INFO: 👥 Configured Accounts to Claim: 3
[2026-08-07 23:01:05] INFO: 🔥 DROPPED CODE DETECTED: 'LUCID-2026-DROP' — Triggering claim for 3 accounts simultaneously!
[2026-08-07 23:01:05] INFO: ⚡ [Account #1] CLAIM SUCCESS! (42.1ms) Code: LUCID-2026-DROP
[2026-08-07 23:01:05] INFO: ⚡ [Account #2] CLAIM SUCCESS! (44.3ms) Code: LUCID-2026-DROP
[2026-08-07 23:01:05] INFO: ⚡ [Account #3] CLAIM SUCCESS! (46.8ms) Code: LUCID-2026-DROP
[2026-08-07 23:01:05] INFO: 🏁 Batch claim finished in 47.2ms for all accounts.
```

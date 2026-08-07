import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
# Multi-channel support: Comma-separated list of channel IDs to monitor
raw_channel_ids = os.getenv("TARGET_CHANNEL_ID", "1344026694691848274").strip()
TARGET_CHANNEL_IDS = [cid.strip() for cid in raw_channel_ids.split(",") if cid.strip()]
REDEMPTION_API_URL = os.getenv("REDEMPTION_API_URL", "https://dash.lucidtrading.com/api/rewards/redeem-secret").strip()
BROWSER_COOKIE = os.getenv("BROWSER_COOKIE", "").strip()

# Multi-account configuration
raw_account_tokens = os.getenv("ACCOUNT_TOKENS", "").strip()
ACCOUNT_TOKENS = [token.strip() for token in raw_account_tokens.split(",") if token.strip()]

def validate_config():
    errors = []
    if not DISCORD_TOKEN:
        errors.append("DISCORD_TOKEN is missing in .env")
    if not TARGET_CHANNEL_IDS:
        errors.append("TARGET_CHANNEL_ID is invalid or missing in .env")
    if not ACCOUNT_TOKENS:
        errors.append("ACCOUNT_TOKENS is empty in .env (add at least 1 account token)")
    return errors


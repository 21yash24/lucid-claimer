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

# Credentials for auto-login
raw_accounts = os.getenv("LUCID_ACCOUNTS", "").strip()
LUCID_ACCOUNTS = []
if raw_accounts:
    for acc in raw_accounts.split(","):
        if ":" in acc:
            parts = acc.split(":", 1)
            LUCID_ACCOUNTS.append((parts[0].strip(), parts[1].strip()))

LUCID_EMAIL = os.getenv("LUCID_EMAIL", "").strip()
LUCID_PASSWORD = os.getenv("LUCID_PASSWORD", "").strip()
if LUCID_EMAIL and LUCID_PASSWORD and not any(acc[0] == LUCID_EMAIL for acc in LUCID_ACCOUNTS):
    LUCID_ACCOUNTS.append((LUCID_EMAIL, LUCID_PASSWORD))

# Image scanning: author(s) whose image drops should be OCR'd for codes
# Supports multiple Discord usernames separated by commas.
raw_image_authors = os.getenv("IMAGE_AUTHORS", "leothetiger,tradorick").strip()
IMAGE_AUTHORS = [name.strip().lower() for name in raw_image_authors.split(",") if name.strip()]
IMAGE_DIR = os.getenv("IMAGE_DIR", "tmp_images").strip()

# How long an account stays skipped after receiving HTTP 429.
# A rate-limited account is NOT retried on subsequent codes during this window.
RATE_LIMIT_COOLDOWN = float(os.getenv("RATE_LIMIT_COOLDOWN", "60").strip())

# Maximum number of codes/variants placed into the claim queue for each drop.
# Kept deliberately small to reduce unnecessary requests.
MAX_CLAIM_ATTEMPTS = int(os.getenv("MAX_CLAIM_ATTEMPTS", "5").strip())

# Max OCR-correction variants per OCR-scanned code. Gemini is accurate, so the
# base extraction usually claims first try; this is just a small safety buffer.
MAX_OCR_VARIANTS = int(os.getenv("MAX_OCR_VARIANTS", "2").strip())

# Gemini Vision OCR (used when GEMINI_API_KEY is set — most accurate engine)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()

# X (Twitter) Scraper Settings
X_USERNAME = os.getenv("X_USERNAME", "").strip()
X_PASSWORD = os.getenv("X_PASSWORD", "").strip()
X_EMAIL = os.getenv("X_EMAIL", "").strip()
X_TARGET_USER = os.getenv("X_TARGET_USER", "cj_wawa").strip()
X_POLL_INTERVAL = float(os.getenv("X_POLL_INTERVAL", "12.0").strip())

# Game Cracker Settings
GUESS_DELAY = float(os.getenv("GUESS_DELAY", "3.1").strip())


def validate_config():
    errors = []
    if not DISCORD_TOKEN:
        errors.append("DISCORD_TOKEN is missing in .env")
    if not TARGET_CHANNEL_IDS:
        errors.append("TARGET_CHANNEL_ID is invalid or missing in .env")
    if not ACCOUNT_TOKENS and not LUCID_ACCOUNTS:
        errors.append("Either ACCOUNT_TOKENS or LUCID_ACCOUNTS credentials must be provided in .env")
    return errors

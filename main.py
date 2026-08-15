import os
import sys
import asyncio
import logging
import ssl
import certifi
import aiohttp
import random

# Fix for macOS Python SSL Certificate verification bug
ssl._create_default_https_context = ssl._create_unverified_context

_orig_tcp_init = aiohttp.TCPConnector.__init__
def _patched_tcp_init(self, *args, **kwargs):
    kwargs['ssl'] = False
    _orig_tcp_init(self, *args, **kwargs)
aiohttp.TCPConnector.__init__ = _patched_tcp_init

import discord
import config
from parser import parse_discord_message_all, extract_all_giveaway_codes, generate_code_variations
from claimer import MultiAccountClaimer
import ocr

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("LucidBot")

# Set up claimer instance with tokens and credentials
claimer = MultiAccountClaimer(
    config.REDEMPTION_API_URL,
    config.ACCOUNT_TOKENS,
    config.LUCID_ACCOUNTS
)

# Initialize discord.py-self client for user accounts
client = discord.Client()

# Set of already claimed codes to prevent duplicate claims
claimed_codes = set()
successful_claims = 0
MAX_CLAIMS = 1  # 1 successful claim target per 24 hours


def is_target_author(message) -> bool:
    """True if the message author matches one of the configured image-scan authors."""
    if not config.IMAGE_AUTHORS:
        return False
    author = message.author
    names = {
        getattr(author, "name", "").lower(),
        getattr(author, "display_name", "").lower(),
        getattr(author, "global_name", "").lower() or "",
    }
    return any(name for name in names if name and name in config.IMAGE_AUTHORS)


async def scan_image_codes(message) -> list:
    """Downloads image attachments from target authors and OCRs them for codes."""
    os.makedirs(config.IMAGE_DIR, exist_ok=True)
    found_codes = []
    for idx, attachment in enumerate(message.attachments):
        if not attachment.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")):
            logger.info(f"🖼️ Skipping non-image attachment: {attachment.filename}")
            continue

        img_path = os.path.join(config.IMAGE_DIR, f"ocr_{message.id}_{idx}.img")
        try:
            await attachment.save(img_path)
            logger.info(f"🔍 [OCR] Scanning image from {message.author}: {attachment.filename}")
            text = await ocr.ocr_image(img_path)
            image_codes = extract_all_giveaway_codes(text)
            logger.info(f"🔍 [OCR] Found {len(image_codes)} code(s) in image: {image_codes}")
            for code in image_codes:
                if code not in found_codes:
                    found_codes.append(code)
        except Exception as e:
            logger.error(f"⚠️ [OCR] Failed to scan {attachment.filename}: {e}")
        finally:
            if os.path.exists(img_path):
                os.remove(img_path)
    return found_codes


async def process_codes(codes: list, ocr_codes: list = None):
    """Shared claim flow: dedupe, print alert, then claim sequentially with safe pacing.
    OCR-scanned codes get correction variants (they may contain OCR misreads); plain
    text codes are claimed exactly as typed."""
    global successful_claims
    if successful_claims >= MAX_CLAIMS:
        return

    # Filter out already claimed codes
    new_codes = [c for c in codes if c not in claimed_codes]
    ocr_set = set(ocr_codes or [])
    if not new_codes:
        return

    # Trigger loud audible alert and print visually striking box
    print("\a\a")
    print("\n" + "🔥" * 25)
    print(f"🔥   SPOTTED NEW CODE(S) IN CHAT: {new_codes}   🔥")
    print("🔥" * 25 + "\n")

    # Build ordered claim queue. Priority: plain-text codes (exact) first, then
    # EVERY distinct OCR-extracted code (Gemini is accurate — the more real codes
    # we try, the better our hit chance), then OCR-correction variants only to
    # fill any leftover slots. Capped to limit rate-limit risk.
    text_codes = [c for c in new_codes if c not in ocr_set]
    ocr_codes = [c for c in new_codes if c in ocr_set]

    claim_queue = list(dict.fromkeys(text_codes + ocr_codes))
    random.shuffle(claim_queue)
    claim_queue = claim_queue[:config.MAX_CLAIM_ATTEMPTS]

    # Variants only if we have fewer real codes than the attempt cap
    if len(claim_queue) < config.MAX_CLAIM_ATTEMPTS:
        per_code_variants = []
        for code in ocr_codes:
            variants = []
            for variant in generate_code_variations(code):
                if variant not in claim_queue and variant not in variants:
                    variants.append(variant)
                if len(variants) >= config.MAX_OCR_VARIANTS:
                    break
            per_code_variants.append(variants)

        # Round-robin interleave
        idx = 0
        while len(claim_queue) < config.MAX_CLAIM_ATTEMPTS:
            added = False
            for variants in per_code_variants:
                if idx < len(variants) and variants[idx] not in claim_queue:
                    claim_queue.append(variants[idx])
                    added = True
                if len(claim_queue) >= config.MAX_CLAIM_ATTEMPTS:
                    break
            if not added:
                break
            idx += 1
    claim_queue = claim_queue[:config.MAX_CLAIM_ATTEMPTS]
    logger.info(f"🧬 Claim queue ({len(claim_queue)}): {claim_queue}")

    for pos, code in enumerate(claim_queue):
        if successful_claims >= MAX_CLAIMS:
            break

        if code in claimed_codes:
            continue
        claimed_codes.add(code)
        logger.info(f"🚀 [Queue {pos+1}/{len(claim_queue)}] Claiming: '{code}'")
        results = await claimer.claim_all_accounts(code)

        # Check if any claim succeeded
        for res in results:
            if isinstance(res, dict) and res.get("success"):
                successful_claims += 1
                logger.info(f"🎉 SUCCESSFUL CLAIM ({successful_claims}/{MAX_CLAIMS})!")
                if successful_claims >= MAX_CLAIMS:
                    logger.info("🏆 Target of 1 successful claim reached! Shutting down listener.")
                    await client.close()
                    return

        # Inter-code delay (2.5-3.0s) to stay under rate limits
        if pos < len(claim_queue) - 1 and successful_claims < MAX_CLAIMS:
            delay = random.uniform(2.5, 3.0)
            logger.info(f"⏳ Waiting {delay:.1f}s before next code...")
            await asyncio.sleep(delay)

@client.event
async def on_ready():
    logger.info(f"✅ Discord Listener Connected as: {client.user} (ID: {client.user.id})")
    logger.info(f"👀 Monitoring Target Channel IDs: {', '.join(config.TARGET_CHANNEL_IDS)}")
    logger.info(f"🛡️ Target: {MAX_CLAIMS} successful claim before auto-stop.")

@client.event
async def on_message(message):
    global successful_claims
    if successful_claims >= MAX_CLAIMS:
        return

    # Log incoming chat messages from designated target channel IDs
    if str(message.channel.id) in config.TARGET_CHANNEL_IDS:
        logger.info(f"💬 [Chat] {message.author}: {message.content[:80]}")

        # Convert embeds to list of dicts for parsing
        embeds_dict = [embed.to_dict() for embed in message.embeds] if message.embeds else []

        # Parse message content and embeds for giveaway drop codes
        codes = parse_discord_message_all(message.content, embeds_dict)
        ocr_codes = []

        # Scan image drops from configured authors (e.g. leothetiger)
        if message.attachments and is_target_author(message):
            image_codes = await scan_image_codes(message)
            ocr_codes = list(image_codes)
            for code in image_codes:
                if code not in codes:
                    codes.append(code)

        if codes:
            await process_codes(codes, ocr_codes=ocr_codes)


async def main():
    errors = config.validate_config()
    if errors:
        logger.error("Configuration errors found in .env:")
        for err in errors:
            logger.error(f" - {err}")
        sys.exit(1)

    # Initialize persistent HTTP session pool
    await claimer.initialize()

    try:
        logger.info("Starting Discord gateway listener...")
        await client.start(config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Stopping bot...")
    finally:
        await claimer.close()

async def test_fake_code():
    """Test claim flow with a fake code without Discord."""
    errors = config.validate_config()
    if errors:
        logger.error("Configuration errors found in .env:")
        for err in errors:
            logger.error(f" - {err}")
        return

    fake_code = "LBOX_TEST123456789"
    logger.info(f"🧪 TEST MODE: Claiming fake code '{fake_code}'")
    logger.info(f"📡 API: {config.REDEMPTION_API_URL}")
    logger.info(f"👥 Accounts: {len(config.ACCOUNT_TOKENS) + len(config.LUCID_ACCOUNTS)}")

    await claimer.initialize()
    results = await claimer.claim_all_accounts(fake_code)

    for res in results:
        if isinstance(res, dict):
            status = "✅ SUCCESS" if res.get("success") else "❌ FAILED"
            logger.info(f"Account #{res.get('account', '?')}: {status}")
            if res.get("error"):
                logger.info(f"  Error: {res['error']}")
            if res.get("response"):
                logger.info(f"  Response: {res['response']}")
        else:
            logger.error(f"Exception: {res}")
    await claimer.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test-fake":
        asyncio.run(test_fake_code())
    else:
        asyncio.run(main())

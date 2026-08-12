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
from parser import parse_discord_message_all
from claimer import MultiAccountClaimer

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

        if codes:
            # Filter out already claimed codes
            new_codes = [c for c in codes if c not in claimed_codes]
            if not new_codes:
                return

            # Trigger loud audible alert and print visually striking box
            print("\a\a")
            print("\n" + "🔥" * 25)
            print(f"🔥   SPOTTED NEW CODE(S) IN CHAT: {new_codes}   🔥")
            print("🔥" * 25 + "\n")

            # Aug 11 Structure: Process codes sequentially with safe pacing to prevent Cloudflare 429
            selected_codes = new_codes[:3]
            logger.info(f"🎲 Detected {len(new_codes)} new code(s). Selected {len(selected_codes)} to claim sequentially.")

            for idx, code in enumerate(selected_codes):
                if successful_claims >= MAX_CLAIMS:
                    break

                claimed_codes.add(code)
                logger.info(f"🚀 [Code {idx+1}/{len(selected_codes)}] Claiming: '{code}'")
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

                # Aug 11 Safe Delay (3.0-3.5s) between codes to prevent 429 rate limits
                if idx < len(selected_codes) - 1 and successful_claims < MAX_CLAIMS:
                    delay = random.uniform(3.0, 3.5)
                    logger.info(f"⏳ Waiting {delay:.1f}s before next code...")
                    await asyncio.sleep(delay)


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

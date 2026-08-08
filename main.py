import sys
import asyncio
import logging
import ssl
import certifi
import aiohttp

# Fix for macOS Python SSL Certificate verification bug
ssl._create_default_https_context = ssl._create_unverified_context

_orig_tcp_init = aiohttp.TCPConnector.__init__
def _patched_tcp_init(self, *args, **kwargs):
    kwargs['ssl'] = False
    _orig_tcp_init(self, *args, **kwargs)
aiohttp.TCPConnector.__init__ = _patched_tcp_init

import discord
import config
import random
from parser import parse_discord_message_all
from claimer import MultiAccountClaimer

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("LucidBot")

# Set up claimer instance
claimer = MultiAccountClaimer(config.REDEMPTION_API_URL, config.ACCOUNT_TOKENS)

# Initialize discord.py-self client for user accounts
client = discord.Client()

# Set of already claimed codes to prevent duplicate claims
claimed_codes = set()
successful_claims = 0
MAX_CLAIMS = 2  # Target 2 successful claims before auto-stopping

@client.event
async def on_ready():
    logger.info(f"✅ Discord Listener Connected as: {client.user} (ID: {client.user.id})")
    logger.info(f"👀 Monitoring Target Channel IDs: {', '.join(config.TARGET_CHANNEL_IDS)}")
    logger.info(f"🛡️ Target: {MAX_CLAIMS} successful claims before auto-stop.")

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

        # Parse message content and embeds for ALL giveaway drop codes
        codes = parse_discord_message_all(message.content, embeds_dict)

        if codes:
            # Randomly sample up to 10 codes maximum per drop to maintain pacing
            selected_codes = random.sample(codes, min(10, len(codes)))
            logger.info(f"🎲 Randomly selected {len(selected_codes)} code(s) out of {len(codes)} to attempt with 1.5s spacing.")

            for code in selected_codes:
                if code not in claimed_codes and successful_claims < MAX_CLAIMS:
                    claimed_codes.add(code)
                    results = await claimer.claim_all_accounts(code)
                    
                    # Check if any claim succeeded
                    for res in results:
                        if isinstance(res, dict) and res.get("success"):
                            successful_claims += 1
                            logger.info(f"🎉 SUCCESSFUL CLAIM ({successful_claims}/{MAX_CLAIMS})!")
                            if successful_claims >= MAX_CLAIMS:
                                logger.info("🏆 Target of 2 successful claims reached! Shutting down listener.")
                                await client.close()
                                return
                    
                    # Wait 1.5 seconds between attempts to maintain controlled request rate
                    await asyncio.sleep(1.5)






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

if __name__ == "__main__":
    asyncio.run(main())

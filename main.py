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

@client.event
async def on_ready():
    logger.info(f"✅ Discord Listener Connected as: {client.user} (ID: {client.user.id})")
    logger.info(f"👀 Monitoring Target Channel ID: {config.TARGET_CHANNEL_ID}")
    logger.info(f"👥 Configured Accounts to Claim: {len(config.ACCOUNT_TOKENS)}")

@client.event
async def on_message(message):
    # Log incoming chat messages from the target channel to the console
    if str(message.channel.id) == config.TARGET_CHANNEL_ID:
        logger.info(f"💬 [Chat] {message.author}: {message.content[:80]}")

        # Convert embeds to list of dicts for parsing
        embeds_dict = [embed.to_dict() for embed in message.embeds] if message.embeds else []

        # Parse message content and embeds for ALL giveaway drop codes
        codes = parse_discord_message_all(message.content, embeds_dict)

        for code in codes:
            if code not in claimed_codes:
                claimed_codes.add(code)
                # Execute instant multi-account claim concurrently for each code
                asyncio.create_task(claimer.claim_all_accounts(code))


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

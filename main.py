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
            # Filter out already claimed codes
            new_codes = [c for c in codes if c not in claimed_codes]
            if not new_codes:
                return

            # Limit to 5 codes max per message to avoid backend overload, and mark as claimed
            selected_codes = new_codes[:5]
            for c in selected_codes:
                claimed_codes.add(c)

            logger.info(f"⚡ Firing concurrent claims for {len(selected_codes)} code(s) in parallel: {selected_codes}")
            
            # Fire all codes in parallel
            tasks = [claimer.claim_all_accounts(code) for code in selected_codes]
            results_list = await asyncio.gather(*tasks, return_exceptions=True)

            # Analyze claim results
            for results in results_list:
                if isinstance(results, list):
                    for res in results:
                        if isinstance(res, dict) and res.get("success"):
                            successful_claims += 1
                            logger.info(f"🎉 SUCCESSFUL CLAIM ({successful_claims}/{MAX_CLAIMS})!")
                            if successful_claims >= MAX_CLAIMS:
                                logger.info("🏆 Target of 2 successful claims reached! Shutting down listener.")
                                await client.close()
                                return


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

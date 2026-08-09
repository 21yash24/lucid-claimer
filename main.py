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
from x_monitor import XMonitor

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

async def claim_code_callback(code: str):
    global successful_claims
    if successful_claims >= MAX_CLAIMS:
        return
    if code in claimed_codes:
        return
        
    claimed_codes.add(code)
    logger.info(f"⚡ [Dual Claim Mode] Spotted code: '{code}'. Triggering BOTH API Claim and Playwright Auto-Checkout concurrently...")
    
    # 1. Trigger Playwright Auto-Checkout as a background task
    try:
        from checkout_buyer import purchase_evaluation_account
        asyncio.create_task(purchase_evaluation_account(code))
    except Exception as e:
        logger.error(f"⚠️ Failed to spawn Playwright auto-checkout: {e}")
        
    # 2. Trigger the fast direct API Claim
    results = await claimer.claim_all_accounts(code)
    
    # Check if any claim succeeded
    for res in results:
        if isinstance(res, dict) and res.get("success"):
            successful_claims += 1
            logger.info(f"🎉 SUCCESSFUL API CLAIM ({successful_claims}/{MAX_CLAIMS})!")
            if successful_claims >= MAX_CLAIMS:
                logger.info("🏆 Target of 2 successful claims reached! Shutting down listener.")
                await client.close()
                return

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

            # Trigger loud audible alert and print visually striking box
            print("\a\a")
            print("\n" + "🔥" * 25)
            print(f"🔥   SPOTTED NEW CODE(S) IN CHAT: {new_codes}   🔥")
            print("🔥" * 25 + "\n")

            # Randomly select up to 3 codes maximum to attempt
            selected_codes = random.sample(new_codes, min(3, len(new_codes)))
            logger.info(f"🎲 Detected {len(new_codes)} new code(s). Randomly selected {len(selected_codes)} to claim sequentially.")

            for idx, code in enumerate(selected_codes):
                if successful_claims >= MAX_CLAIMS:
                    break

                claimed_codes.add(code)
                logger.info(f"⚡ [Dual Claim Mode] Attempting code '{code}' on API and Playwright...")
                
                # 1. Trigger Playwright Auto-Checkout as a background task
                try:
                    from checkout_buyer import purchase_evaluation_account
                    asyncio.create_task(purchase_evaluation_account(code))
                except Exception as e:
                    logger.error(f"⚠️ Failed to spawn Playwright auto-checkout: {e}")
                
                # 2. Trigger the direct API Claim
                results = await claimer.claim_all_accounts(code)

                # Check if any claim succeeded
                for res in results:
                    if isinstance(res, dict) and res.get("success"):
                        successful_claims += 1
                        logger.info(f"🎉 SUCCESSFUL API CLAIM ({successful_claims}/{MAX_CLAIMS})!")
                        if successful_claims >= MAX_CLAIMS:
                            logger.info("🏆 Target of 2 successful claims reached! Shutting down listener.")
                            await client.close()
                            return

                # Wait 2 to 3 seconds before trying the next code (if any remain)
                if idx < len(selected_codes) - 1 and successful_claims < MAX_CLAIMS:
                    delay = random.uniform(2.0, 3.0)
                    logger.info(f"⏳ Waiting {delay:.2f} seconds before attempting next code...")
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

    # Initialize and launch the X Monitor concurrently
    x_monitor = XMonitor(claim_code_callback)
    x_initialized = await x_monitor.initialize()
    if x_initialized:
        asyncio.create_task(x_monitor.poll_timeline())
        logger.info("🐦 X Monitor background loop started.")
    else:
        logger.warning("🐦 X Monitor not started (authentication failed or credentials/cookies missing).")

    try:
        logger.info("Starting Discord gateway listener...")
        await client.start(config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Stopping bot...")
    finally:
        await claimer.close()

if __name__ == "__main__":
    asyncio.run(main())

"""
snatch_newest_wawa_tweet.py
---------------------------
Explicit script to:
1. Fetch the absolute newest tweet from @cj_wawa (or @yashhjhaa for test).
2. If image attached, run Apple Vision OCR on the image.
3. Extract code.
4. Auto-paste code into open Chrome modal, click Apply Coupon, click PROCEED TO PAYMENT.
"""
import sys
import os
import asyncio
import logging
import aiohttp
import ssl

ssl._create_default_https_context = ssl._create_unverified_context
_orig_tcp_init = aiohttp.TCPConnector.__init__
def _patched_tcp_init(self, *args, **kwargs):
    kwargs['ssl'] = False
    _orig_tcp_init(self, *args, **kwargs)
aiohttp.TCPConnector.__init__ = _patched_tcp_init

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from x_monitor import XMonitor
from mac_150k_snatcher import paste_code_to_frontmost_chrome
from claimer import MultiAccountClaimer

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("NewestTweetSnatcher")

async def process_newest_tweet(username: str):
    logger.info(f"🔍 Fetching ABSOLUTE NEWEST tweet from @{username}...")
    mon = XMonitor(None)
    ok = await mon.initialize()
    if not ok:
        logger.error("❌ Failed to authenticate with X cookies!")
        return

    user = await mon.client.get_user_by_screen_name(username)
    tweets = await user.get_tweets('Tweets', count=1)
    if not tweets:
        logger.warning(f"⚠️ No tweets found for @{username}!")
        return

    newest_tweet = tweets[0]
    logger.info(f"📌 NEWEST TWEET ID: {newest_tweet.id}")
    logger.info(f"   Text: {newest_tweet.text}")

    connector = aiohttp.TCPConnector(ssl=False)
    codes = []
    async with aiohttp.ClientSession(connector=connector) as session:
        # 1. OCR Image attachments in newest tweet
        media = getattr(newest_tweet, "media", None) or getattr(newest_tweet, "extended_entities", {}).get("media", [])
        if media:
            logger.info(f"📸 Image attached to newest tweet! Downloading and running Apple Vision OCR...")
            image_codes = await mon.process_tweet_media(session, media)
            codes.extend(image_codes)

        # 2. Text codes in newest tweet
        text_codes = mon.ocr_solver.find_lucid_codes(newest_tweet.text)
        codes.extend(text_codes)

    # Remove duplicates
    codes = list(set(codes))
    logger.info(f"🎯 CODES EXTRACTED FROM NEWEST TWEET: {codes}")

    if not codes:
        logger.warning("⚠️ No coupon codes found in the newest tweet text or image!")
        return

    target_code = codes[0]
    logger.info(f"🚀 FIRING AUTO-CHECKOUT WITH CODE FROM NEWEST TWEET: '{target_code}'...")

    # Execute Chrome UI automation (paste → Apply Coupon → PROCEED TO PAYMENT)
    paste_code_to_frontmost_chrome(target_code)

    # Also fire background API checkout
    claimer = MultiAccountClaimer(config.REDEMPTION_API_URL, config.ACCOUNT_TOKENS, config.LUCID_ACCOUNTS)
    await claimer.initialize()
    await claimer.checkout_all_accounts(target_code, plan_id="150k")
    await claimer.close()

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "cj_wawa"
    asyncio.run(process_newest_tweet(target))

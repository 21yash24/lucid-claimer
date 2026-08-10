import asyncio
import aiohttp
import os
import re
import time
import logging
import ssl
import xml.etree.ElementTree as ET
from urllib.parse import unquote
from twikit import Client
import config
from ocr_solver import OcrSolver

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("XMonitor")

# Public Nitter RSS Mirrors for 0-rate-limit 2.0s fast polling
NITTER_MIRRORS = [
    "https://nitter.net",
    "https://nitter.cz",
    "https://nitter.privacydev.net",
]

# Hardcoded User IDs to eliminate get_user_by_screen_name API calls entirely
HARDCODED_USER_IDS = {
    "cj_wawa": "1580283393987649537",
    "yashhjhaa": "1939188836611014656",
}

class XMonitor:
    def __init__(self, claim_callback):
        self.client = Client('en-US')
        self.claim_callback = claim_callback
        self.ocr_solver = OcrSolver()
        self.seen_tweets = set()
        self.seen_rss_ids = set()
        self.cookies_path = os.path.join(os.path.dirname(__file__), "x_cookies.json")
        self.tmp_img_dir = os.path.join(os.path.dirname(__file__), "tmp_images")
        os.makedirs(self.tmp_img_dir, exist_ok=True)

    async def initialize(self):
        """
        Authenticates with X using cookies.json if it exists, or via username/password credentials.
        """
        if os.path.exists(self.cookies_path):
            try:
                self.client.load_cookies(self.cookies_path)
                logger.info("🔓 X authenticated successfully using loaded cookies.")
                return True
            except Exception as e:
                logger.warning(f"⚠️ Failed to load X cookies: {e}. Attempting login instead...")
        
        if config.X_USERNAME and config.X_PASSWORD:
            logger.info(f"🔄 Authenticating with X as: {config.X_USERNAME}...")
            try:
                await self.client.login(
                    auth_info_1=config.X_USERNAME,
                    auth_info_2=config.X_EMAIL,
                    password=config.X_PASSWORD
                )
                self.client.save_cookies(self.cookies_path)
                logger.info("🔑 X login successful! Saved cookies for future use.")
                return True
            except Exception as e:
                logger.error(f"❌ X credentials login failed: {e}")
                return False
        else:
            logger.warning("⚠️ No X credentials or cookies found.")
            return False

    async def download_image(self, session: aiohttp.ClientSession, url: str) -> str:
        """
        Downloads a tweet image locally to a temporary path.
        """
        filename = f"tweet_{int(time.time())}.jpg"
        filepath = os.path.join(self.tmp_img_dir, filename)
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
            async with session.get(url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    with open(filepath, 'wb') as f:
                        f.write(await resp.read())
                    return filepath
        except Exception as e:
            logger.error(f"⚠️ Error downloading image {url}: {e}")
        return ""

    async def process_tweet_media(self, session: aiohttp.ClientSession, media_list: list) -> list:
        """
        Downloads media, runs White-Only OCR color separation and extracts codes.
        """
        extracted_codes = []
        for media in media_list:
            media_url = getattr(media, "url", None)
            
            if isinstance(media, dict):
                media_url = media.get("media_url_https") or media.get("url")
            elif isinstance(media, str):
                media_url = media

            if not media_url:
                continue
                
            if not isinstance(media, (dict, str)) and hasattr(media, "download"):
                filename = f"tweet_{int(time.time())}.jpg"
                img_path = os.path.join(self.tmp_img_dir, filename)
                logger.info(f"📸 Image attachment detected: {media_url}. Downloading natively via Twikit...")
                try:
                    await media.download(img_path)
                except Exception as e:
                    logger.error(f"⚠️ Error using native twikit media download: {e}")
                    img_path = await self.download_image(session, media_url)
            else:
                logger.info(f"📸 Image attachment detected: {media_url}. Downloading via session fallback...")
                img_path = await self.download_image(session, media_url)

            if img_path:
                logger.info(f"👁️ Running 4-Pass Ensemble OCR solver on: {img_path}...")
                preprocessed_path = img_path.replace(".jpg", "_clean.jpg")
                text = self.ocr_solver.extract_text_from_image(img_path, preprocessed_path)
                codes = self.ocr_solver.find_lucid_codes(text)
                
                if codes:
                    logger.info(f"🎯 OCR found code(s) in image: {codes}")
                    extracted_codes.extend(codes)
        return extracted_codes

    # ────────────────────────────────────────────────────────
    # ZERO-RATE-LIMIT RSS MONITOR (2.0s polling interval)
    # ────────────────────────────────────────────────────────
    async def poll_rss_timeline(self):
        """
        Public RSS Feed Monitor (0 Rate Limits, 2.0s fast check).
        Polls Nitter RSS feeds continuously for target users without requiring Twitter API rate limits.
        """
        target_users_list = [u.strip() for u in config.X_TARGET_USER.split(",") if u.strip()]
        logger.info(f"⚡ [RSS Fast Engine] Polling zero-rate-limit feed for: {', '.join(target_users_list)} (interval: 2.0s)...")
        
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            is_first_check = True
            poll_count = 0
            while True:
                poll_count += 1
                for username in target_users_list:
                    success = False
                    for mirror in NITTER_MIRRORS:
                        rss_url = f"{mirror}/{username}/rss"
                        try:
                            headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
                            async with session.get(rss_url, headers=headers, timeout=3.0) as resp:
                                if resp.status != 200:
                                    continue
                                data = await resp.text()
                                root = ET.fromstring(data)
                                items = root.findall('.//item')
                                
                                if not items:
                                    continue

                                if is_first_check:
                                    for item in items:
                                        guid = item.find('guid')
                                        item_id = guid.text if guid is not None else item.find('link').text
                                        self.seen_rss_ids.add(item_id)
                                    success = True
                                    break

                                for item in reversed(items[:5]):
                                    guid = item.find('guid')
                                    item_id = guid.text if guid is not None else item.find('link').text
                                    if item_id in self.seen_rss_ids:
                                        continue

                                    self.seen_rss_ids.add(item_id)
                                    title = item.find('title').text or ''
                                    desc = item.find('description').text or ''

                                    print("\a\a\a")
                                    print("\n" + "⚡" * 25)
                                    print(f"🚨 FAST RSS: NEW TWEET FROM @{username}! 🚨")
                                    print(f"Content: {title}")
                                    print("⚡" * 25 + "\n")

                                    # Extract image URLs from RSS description
                                    raw_imgs = re.findall(r'<img[^>]+src=[\"\']([^\"\']+)[\"\']', desc)
                                    tw_imgs = []
                                    for img_src in raw_imgs:
                                        if 'media%2F' in img_src or 'media/' in img_src:
                                            media_id = unquote(img_src.split('media%2F')[-1] if 'media%2F' in img_src else img_src.split('media/')[-1])
                                            tw_url = f"https://pbs.twimg.com/media/{media_id}"
                                            tw_imgs.append(tw_url)
                                        elif 'pbs.twimg.com' in img_src:
                                            tw_imgs.append(img_src)

                                    if tw_imgs:
                                        logger.info(f"⚡ [RSS Engine] Download & OCR scanning image: {tw_imgs}")
                                        codes = await self.process_tweet_media(session, tw_imgs)
                                        codes = list(set(codes))
                                        if codes:
                                            logger.info(f"🚀 [RSS Engine] OCR found code(s) in @{username} tweet image: {codes}!")
                                            asyncio.create_task(self.claim_callback(codes, title))
                                success = True
                                break
                        except Exception as e:
                            logger.debug(f"RSS check error for {rss_url}: {e}")
                    
                    if poll_count % 10 == 0 and success:
                        logger.info(f"📡 [RSS Fast Engine] Active watch on @{username} (0 rate limits)...")

                is_first_check = False
                await asyncio.sleep(2.0)

    # ────────────────────────────────────────────────────────
    # STANDARD GRAPHQL TIMELINE MONITOR (Secondary Fallback)
    # ────────────────────────────────────────────────────────
    async def poll_timeline(self):
        """
        Main real-time timeline polling loop that monitors target users.
        Also launches the 2.0s fast zero-rate-limit RSS monitor in parallel.
        """
        target_users_list = [u.strip() for u in config.X_TARGET_USER.split(",") if u.strip()]
        logger.info(f"👀 Monitoring X users: {', '.join(target_users_list)} (interval: {config.X_POLL_INTERVAL}s)")
        
        # Launch 2.0s Fast RSS Monitor in parallel
        asyncio.create_task(self.poll_rss_timeline())

        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            is_first_check = True
            while True:
                try:
                    for username in target_users_list:
                        # Use hardcoded ID if available to prevent get_user_by_screen_name API calls entirely
                        user_id = HARDCODED_USER_IDS.get(username)
                        if user_id:
                            try:
                                tweets = await self.client.get_user_tweets(user_id, 'Tweets', count=5)
                            except Exception as req_err:
                                if "429" in str(req_err) or "limit" in str(req_err).lower():
                                    logger.debug(f"GraphQL 429 for {username} — RSS Engine active.")
                                    await asyncio.sleep(30)
                                    continue
                                else:
                                    tweets = None
                        else:
                            try:
                                user = await self.client.get_user_by_screen_name(username)
                                tweets = await user.get_tweets('Tweets', count=5)
                            except Exception:
                                tweets = None
                        
                        if not tweets:
                            continue
                            
                        if is_first_check:
                            for t in tweets:
                                self.seen_tweets.add(t.id)
                            continue

                        for tweet in reversed(tweets):
                            if tweet.id in self.seen_tweets:
                                continue

                            self.seen_tweets.add(tweet.id)
                                
                            print("\a\a\a")
                            print("\n" + "🐦" * 25)
                            print(f"🚨 NEW TWEET FROM @{username}! 🚨")
                            print(f"Content: {tweet.text}")
                            print("🐦" * 25 + "\n")
                            
                            media = getattr(tweet, "media", None) or getattr(tweet, "extended_entities", {}).get("media", [])
                            if not media:
                                logger.info(f"ℹ️  @{username} tweet has no image — skipping.")
                                continue

                            codes = await self.process_tweet_media(session, media)
                            codes = list(set(codes))

                            if codes:
                                logger.info(f"⚡ OCR found code(s) in @{username} tweet image: {codes}!")
                                asyncio.create_task(self.claim_callback(codes, tweet.text))
                            else:
                                logger.info(f"ℹ️  @{username} tweet image had no code — ignoring.")
                                    
                    is_first_check = False
                except Exception as e:
                    logger.debug(f"GraphQL poll status: {e}")
                    await asyncio.sleep(30)

                await asyncio.sleep(config.X_POLL_INTERVAL)

import asyncio
import aiohttp
import os
import re
import time
import logging
from twikit import Client
import config
from ocr_solver import OcrSolver

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("XMonitor")

class XMonitor:
    def __init__(self, claim_callback):
        self.client = Client('en-US')
        self.claim_callback = claim_callback
        self.ocr_solver = OcrSolver()
        self.seen_tweets = set()
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
                # Login using credentials
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
            logger.warning("⚠️ No X credentials or cookies found. Running in cookie extraction instruction mode.")
            return False

    async def download_image(self, session: aiohttp.ClientSession, url: str) -> str:
        """
        Downloads a tweet image locally to a temporary path.
        """
        filename = f"tweet_{int(time.time())}.jpg"
        filepath = os.path.join(self.tmp_img_dir, filename)
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    with open(filepath, 'wb') as f:
                        f.write(await resp.read())
                    return filepath
        except Exception as e:
            logger.error(f"⚠️ Error downloading image {url}: {e}")
        return ""

    async def process_tweet_media(self, session: aiohttp.ClientSession, media_list: list) -> list:
        """
        Downloads media, runs OCR scribble filtering and extracts codes.
        """
        extracted_codes = []
        for media in media_list:
            media_url = getattr(media, "url", None)
            media_type = getattr(media, "type", None)
            
            # Check if it's a dict (fallback for raw JSON objects)
            if isinstance(media, dict):
                media_url = media.get("media_url_https") or media.get("url")
                media_type = media.get("type")

            if not media_url or media_type != "photo":
                continue
                
            logger.info(f"📸 Image attachment detected: {media_url}. Downloading...")
            img_path = await self.download_image(session, media_url)
            if img_path:
                logger.info(f"👁️ Running OCR solver on: {img_path}...")
                preprocessed_path = img_path.replace(".jpg", "_clean.jpg")
                text = self.ocr_solver.extract_text_from_image(img_path, preprocessed_path)
                codes = self.ocr_solver.find_lucid_codes(text)
                
                # Cleanup downloaded temp files
                try:
                    os.remove(img_path)
                    if os.path.exists(preprocessed_path):
                        os.remove(preprocessed_path)
                except Exception:
                    pass
                    
                if codes:
                    logger.info(f"🎯 OCR found code(s) in image: {codes}")
                    extracted_codes.extend(codes)
        return extracted_codes

    async def poll_timeline(self):
        """
        Main real-time timeline polling loop that monitors the target users.
        """
        target_users_list = [u.strip() for u in config.X_TARGET_USER.split(",") if u.strip()]
        logger.info(f"👀 Monitoring X users: {', '.join(target_users_list)} (interval: {config.X_POLL_INTERVAL}s)")
        
        # We need a shared aiohttp ClientSession to download images efficiently
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            poll_count = 0
            user_objects = {}  # Cache username -> user object
            is_first_check = True
            while True:
                poll_count += 1
                if poll_count % 5 == 1:
                    logger.info(f"📡 [X Monitor] Polling {', '.join(target_users_list)} timelines (check #{poll_count})...")
                try:
                    for username in target_users_list:
                        # Get user profile once and cache it to cut API requests and prevent rate limits
                        if username not in user_objects:
                            user_objects[username] = await self.client.get_user_by_screen_name(username)
                        
                        user = user_objects[username]
                        tweets = await user.get_tweets('Tweets', count=5)
                        
                        if not tweets:
                            continue
                            
                        # Process from oldest to newest in the count sample
                        for tweet in reversed(tweets):
                            if tweet.id in self.seen_tweets:
                                continue
                                
                            self.seen_tweets.add(tweet.id)
                            
                            if is_first_check:
                                continue
                                
                            # Print large warning alert
                            print("\a\a\a")
                            print("\n" + "🐦" * 25)
                            print(f"🚨 NEW TWEET FROM @{username}! 🚨")
                            print(f"Content: {tweet.text}")
                            print("🐦" * 25 + "\n")
                            
                            # 1. Parse text directly for codes
                            codes = self.ocr_solver.find_lucid_codes(tweet.text)
                            
                            # 2. Check media attachments for codes (images with red scribbles)
                            media = getattr(tweet, "media", None) or getattr(tweet, "extended_entities", {}).get("media", [])
                            if media:
                                image_codes = await self.process_tweet_media(session, media)
                                codes.extend(image_codes)
                                
                            # Remove duplicates
                            codes = list(set(codes))
                            
                            if codes:
                                logger.info(f"⚡ Codes spotted in tweet from @{username}: {codes}. Dispatching claims...")
                                for code in codes:
                                    # Trigger redemption callback asynchronously
                                    asyncio.create_task(self.claim_callback(code))
                                    
                    is_first_check = False
                except Exception as e:
                    logger.error(f"⚠️ Error polling X timeline: {e}")
                    # If we get rate limited (429), back off for 300 seconds to reset rate limit window
                    if "429" in str(e) or "limit" in str(e).lower():
                        backoff_time = 300
                        logger.warning(f"⏳ Rate limit exceeded (429) detected. Sleeping for {backoff_time} seconds (5 minutes) to let Twitter reset your rate limit window...")
                        await asyncio.sleep(backoff_time)
                        continue
                    
                await asyncio.sleep(config.X_POLL_INTERVAL)

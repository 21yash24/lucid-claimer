import asyncio
import aiohttp
import time
import logging
import random
import string
import ssl
import certifi
from typing import List, Tuple, Set
import config

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("CrackSolver")

# SSL context for macOS
ssl_context = ssl.create_default_context(cafile=certifi.where())

# Candidate character set for 5-digit code (Digits 0-9 and Uppercase A-Z)
CHAR_SET = string.digits + string.ascii_uppercase  # '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'

def get_feedback(guess: str, secret: str) -> Tuple[int, int]:
    """
    Simulates Mastermind feedback for a guess against a secret:
    Returns (correct_spot, wrong_spot)
    """
    correct_spot = sum(1 for g, s in zip(guess, secret) if g == s)
    
    # Count frequency of characters for wrong_spot calculation
    guess_unmatched = [g for g, s in zip(guess, secret) if g != s]
    secret_unmatched = [s for g, s in zip(guess, secret) if g != s]
    
    wrong_spot = 0
    for char in guess_unmatched:
        if char in secret_unmatched:
            wrong_spot += 1
            secret_unmatched.remove(char)
            
    return correct_spot, wrong_spot

def filter_candidates(candidates: List[str], guess: str, correct_spot: int, wrong_spot: int) -> List[str]:
    """
    Filters candidate pool: Keeps only codes that would yield the exact same feedback.
    """
    filtered = []
    for cand in candidates:
        c_spot, w_spot = get_feedback(guess, cand)
        if c_spot == correct_spot and w_spot == wrong_spot:
            filtered.append(cand)
    return filtered

# Candidate API endpoints for Lucid Mobile App Giveaway feature
MOBILE_ENDPOINTS = [
    "https://dash.lucidtrading.com/api/rewards/guess",
    "https://dash.lucidtrading.com/api/giveaway/guess",
    "https://dash.lucidtrading.com/api/rewards/crack-code",
    "https://dash.lucidtrading.com/api/mobile/v1/giveaway/guess",
    "https://api.lucidtrading.com/v1/giveaway/guess"
]

class MastermindSolver:
    """
    Automated Mastermind Code Cracker for Lucid Trading 5-digit giveaway events.
    """
    def __init__(self, token: str, cookie: str, endpoint_url: str = None):
        self.token = token if token.startswith("Bearer ") else f"Bearer {token}"
        self.cookie = cookie
        self.api_url = endpoint_url or MOBILE_ENDPOINTS[0]
        self.headers = {
            "Authorization": self.token,
            "Content-Type": "application/json",
            "User-Agent": "LucidApp/90.0 (Android; Mobile)",
            "Origin": "https://dash.lucidtrading.com",
            "Referer": "https://dash.lucidtrading.com/",
            "Cookie": self.cookie
        }


    async def submit_guess(self, session: aiohttp.ClientSession, guess_code: str) -> dict:
        """
        Submits a 5-digit guess to Lucid's rewards endpoint.
        """
        payload = {"code": guess_code, "guess": guess_code}
        start_time = time.perf_counter()

        try:
            async with session.post(self.api_url, json=payload, headers=self.headers, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                data = await resp.json()
                logger.info(f"🎯 Guess '{guess_code}' -> HTTP {resp.status} ({elapsed_ms:.1f}ms): {data}")
                return data
        except Exception as e:
            logger.error(f"⚠️ Error submitting guess '{guess_code}': {e}")
            return {}

    async def solve(self, candidate_pool: List[str]):
        """
        Executes automated Mastermind guessing loop with 2.0s cooldown between attempts.
        """
        logger.info(f"🚀 Starting Mastermind Solver with {len(candidate_pool)} initial candidates...")
        connector = aiohttp.TCPConnector(limit=10, ssl=False)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            current_candidates = candidate_pool[:]
            attempts = 0

            # Initial first guess (e.g. "1EIOW" or random 5-character string)
            next_guess = "1EIOW" if "1EIOW" in current_candidates else random.choice(current_candidates)

            while current_candidates and attempts < 15:
                attempts += 1
                logger.info(f"👉 [Attempt #{attempts}] Submitting Guess: '{next_guess}' (Remaining Candidates: {len(current_candidates)})")
                
                res = await self.submit_guess(session, next_guess)
                
                # Check for success
                if res.get("success") or res.get("won") or res.get("status") == "claimed":
                    logger.info(f"🎉 WINNER! Code '{next_guess}' cracked the giveaway! Reward credited!")
                    return next_guess

                # Check feedback fields
                correct_spot = res.get("correct_spot", res.get("correctSpot"))
                wrong_spot = res.get("wrong_spot", res.get("wrongSpot"))

                if correct_spot is not None and wrong_spot is not None:
                    # Filter candidates in < 1ms
                    start_filter = time.perf_counter()
                    current_candidates = filter_candidates(current_candidates, next_guess, correct_spot, wrong_spot)
                    filter_ms = (time.perf_counter() - start_filter) * 1000
                    logger.info(f"⚡ Candidate pool pruned to {len(current_candidates)} in {filter_ms:.2f}ms (Feedback: {correct_spot} correct, {wrong_spot} wrong)")
                    
                    if not current_candidates:
                        logger.warning("No candidates match feedback! Code format might differ.")
                        break
                    
                    next_guess = current_candidates[0]
                else:
                    # If endpoint returns invalid or unknown format, pick next candidate
                    if next_guess in current_candidates:
                        current_candidates.remove(next_guess)
                    if current_candidates:
                        next_guess = random.choice(current_candidates)

                # 1.0 second delay between guesses for maximum speed
                await asyncio.sleep(1.0)


    async def check_event_status(self, session: aiohttp.ClientSession) -> Tuple[bool, dict]:
        """
        Polls the Lucid Mobile App '🎁 Giveaway' section status API.
        Returns (is_active, status_data)
        """
        # Strictly mobile app Giveaway section API endpoints (NOT web dashboard crate endpoints)
        status_urls = [
            "https://dash.lucidtrading.com/api/giveaway/status",
            "https://dash.lucidtrading.com/api/mobile/v1/giveaway/status",
            "https://api.lucidtrading.com/v1/giveaway/status"
        ]
        
        for url in status_urls:
            try:
                async with session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Check if a Crack the Code event is active or has spots left
                        is_active = bool(data.get("active") or data.get("spots_left", 0) > 0 or data.get("status") == "active")
                        return is_active, data
            except Exception:
                continue
        return False, {}


    async def watch_and_solve(self, candidate_pool: List[str]):
        """
        24/7 App Watcher: Monitors the Lucid App '🎁 Giveaway' section continuously.
        Only starts guessing when a new giveaway event goes live!
        """
        logger.info("👀 [Tool 2] Watching Lucid Mobile App '🎁 Giveaway' Section 24/7...")
        connector = aiohttp.TCPConnector(limit=10, ssl=False)

        async with aiohttp.ClientSession(connector=connector) as session:
            check_count = 0
            while True:
                check_count += 1
                is_active, status_data = await self.check_event_status(session)

                if is_active:
                    logger.info("🚨 NEW EVENT DROPPED IN LUCID APP '🎁 GIVEAWAY' SECTION! Launching Mastermind solver...")
                    won_code = await self.solve(candidate_pool)
                    if won_code:
                        logger.info("🎉 GIVEAWAY GAME WON & CLAIMED! Auto-stopping script to stay 100% safe & stealthy.")
                        return
                    logger.info("🏁 Event finished! Returning to 24/7 Giveaway section watcher...")

                else:
                    if check_count % 5 == 1:
                        logger.info("⏳ [Lucid App '🎁 Giveaway' Section] Status: Inactive / Event Ended. Watching for next drop...")
                
                # Poll status every 2 seconds
                await asyncio.sleep(2.0)

async def main():
    if not config.ACCOUNT_TOKENS:
        logger.error("ACCOUNT_TOKENS is missing in .env")
        return

    logger.info("Generating candidate 5-character combinations...")
    pool = [''.join(p) for p in [random.choices(CHAR_SET, k=5) for _ in range(5000)]]

    solver = MastermindSolver(
        token=config.ACCOUNT_TOKENS[0],
        cookie=config.BROWSER_COOKIE
    )
    await solver.watch_and_solve(pool)

if __name__ == "__main__":
    asyncio.run(main())


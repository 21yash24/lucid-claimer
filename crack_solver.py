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
    def __init__(self, token: str, cookie: str, email: str = None, password: str = None, endpoint_url: str = None):
        self.token = token if (token and token.startswith("Bearer ")) else f"Bearer {token}" if token else None
        self.cookie = cookie
        self.email = email
        self.password = password
        self.api_url = endpoint_url or MOBILE_ENDPOINTS[0]
        self.headers = {
            "Authorization": self.token or "",
            "Content-Type": "application/json",
            "User-Agent": "LucidApp/90.0 (Android; Mobile)",
            "Origin": "https://dash.lucidtrading.com",
            "Referer": "https://dash.lucidtrading.com/",
            "Cookie": self.cookie or ""
        }
        self.auth_error_logged = False


    async def refresh_token(self, session: aiohttp.ClientSession) -> bool:
        """
        Logs in programmatically via credentials to fetch a new JWT token.
        """
        if not self.email or not self.password:
            return False
            
        url = "https://dash.lucidtrading.com/api/mobile/login"
        payload = {
            "email": self.email,
            "password": self.password,
            "username": self.email
        }
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "LucidApp/90.0 (Android; Mobile)",
            "Accept": "application/json"
        }
        
        logger.info(f"🔄 Token expired or missing. Attempting login as {self.email}...")
        try:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    new_token = data.get("token")
                    if new_token:
                        self.token = f"Bearer {new_token}"
                        self.headers["Authorization"] = self.token
                        logger.info("🔑 Auto-login successful! Fresh token updated.")
                        self.auth_error_logged = False
                        return True
                logger.error(f"❌ Auto-login failed (HTTP {resp.status})")
        except Exception as e:
            logger.error(f"⚠️ Error during auto-login: {e}")
        return False


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

    def find_candidate_backtrack(self, history: List[Tuple[str, int, int]]) -> Optional[str]:
        # Pre-process history for rapid lookup
        h_processed = []
        for g, c, w in history:
            h_processed.append((list(g), c, w, g))
            
        chars = list(CHAR_SET)
        
        # Pre-shuffle character lists for each depth ONCE at the start
        # This prevents any list copying/shuffling inside recursion!
        depth_chars = []
        for _ in range(5):
            dc = chars[:]
            random.shuffle(dc)
            depth_chars.append(dc)
            
        candidate = [''] * 5
        used_chars = set()

        # Highly optimized validation
        def is_consistent_fast(cand_str: str) -> bool:
            for g_list, correct, wrong, _ in h_processed:
                c_spot = 0
                w_spot = 0
                g_unmatched = []
                c_unmatched = []
                
                for i in range(5):
                    if cand_str[i] == g_list[i]:
                        c_spot += 1
                    else:
                        g_unmatched.append(g_list[i])
                        c_unmatched.append(cand_str[i])
                
                if c_spot != correct:
                    return False
                    
                for char in g_unmatched:
                    if char in c_unmatched:
                        w_spot += 1
                        c_unmatched.remove(char)
                
                if w_spot != wrong:
                    return False
            return True

        def backtrack(depth: int) -> Optional[str]:
            if depth == 5:
                cand_str = "".join(candidate)
                if is_consistent_fast(cand_str):
                    return cand_str
                return None
            
            # Iterate over pre-shuffled list for this specific depth
            for c in depth_chars[depth]:
                if c in used_chars:
                    continue
                    
                candidate[depth] = c
                used_chars.add(c)
                
                possible = True
                remaining = 4 - depth
                
                for g_list, correct, wrong, _ in h_processed:
                    # 1. Matches in prefix
                    matches = 0
                    for i in range(depth + 1):
                        if candidate[i] == g_list[i]:
                            matches += 1
                            
                    # Upper bound match prune
                    if matches > correct:
                        possible = False
                        break
                    # Lower bound match prune (maximum possible matches < correct)
                    if matches + remaining < correct:
                        possible = False
                        break
                    
                    # 2. Overlap in prefix
                    overlap = 0
                    for i in range(depth + 1):
                        if candidate[i] in g_list:
                            overlap += 1
                            
                    # Upper bound overlap prune
                    if overlap > (correct + wrong):
                        possible = False
                        break
                    # Lower bound overlap prune (maximum possible overlap < correct + wrong)
                    if overlap + remaining < (correct + wrong):
                        possible = False
                        break
                
                if possible:
                    res = backtrack(depth + 1)
                    if res:
                        return res
                        
                used_chars.remove(c)
                
            return None
            
        return backtrack(0)

    async def solve(self) -> str:
        """
        Optimized prefix-pruned backtracking solver:
        Starts guessing randomly to gather constraints, then dynamically filters remaining search space.
        """
        logger.info("⚡ Solving Mastermind Giveaway Event...")
        connector = aiohttp.TCPConnector(limit=10, ssl=False)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            # Refresh token before starting solver if it doesn't exist
            if not self.token:
                await self.refresh_token(session)

            history = []
            
            # Start with a random initial guess
            next_guess = "".join(random.choices(CHAR_SET, k=5))
            
            for round_num in range(1, 15):
                logger.info(f"👉 [Round {round_num}] Submitting Guess: '{next_guess}'...")
                
                resp_data = await self.submit_guess(session, next_guess)
                
                if not resp_data:
                    # Retry in case of temporary network glitches
                    await asyncio.sleep(2)
                    continue
                
                # Check for win condition
                if resp_data.get("message") == "code_match" or resp_data.get("win") or resp_data.get("status") == "success":
                    logger.info(f"🏆 SUCCESS! Mastermind solved on round {round_num}. The correct code is '{next_guess}'!")
                    return next_guess
                
                # Retrieve spot feedback
                correct_spot = resp_data.get("correct") or resp_data.get("correctSpot") or resp_data.get("correct_spot")
                wrong_spot = resp_data.get("wrong") or resp_data.get("wrongSpot") or resp_data.get("wrong_spot")
                
                if correct_spot is None or wrong_spot is None:
                    # Check if event has ended or if we are out of spots
                    if resp_data.get("status") == "inactive" or "no spots" in str(resp_data).lower():
                        logger.warning("🚫 Event ended or no spots left. Stopping solver.")
                        return None
                    
                    logger.warning(f"❓ Unexpected response format (no match feedback): {resp_data}")
                    
                else:
                    logger.info(f"📊 Feedback: {correct_spot} correct spot, {wrong_spot} wrong spot.")
                    history.append((next_guess, correct_spot, wrong_spot))
                
                # Calculate next constraint-satisfying candidate using optimized backtracking
                start_filter = time.perf_counter()
                next_guess_candidate = self.find_candidate_backtrack(history)
                filter_ms = (time.perf_counter() - start_filter) * 1000
                
                if next_guess_candidate:
                    logger.info(f"⚡ Next guess generated in {filter_ms:.2f}ms: '{next_guess_candidate}' (satisfies {len(history)} historic rules)")
                    next_guess = next_guess_candidate
                else:
                    # Fallback to random if constraints collapsed
                    next_guess = "".join(random.choices(CHAR_SET, k=5))
                
                # 3.1 second delay between guesses to respect the 3-second server timeout
                await asyncio.sleep(3.1)
                
            return None


    async def check_event_status(self, session: aiohttp.ClientSession) -> Tuple[bool, dict]:
        """
        Polls the Lucid Mobile App '🎁 Giveaway' section status API.
        Returns (is_active, status_data)
        """
        status_urls = [
            "https://dash.lucidtrading.com/api/giveaway/status",
            "https://dash.lucidtrading.com/api/mobile/v1/giveaway/status",
            "https://api.lucidtrading.com/v1/giveaway/status"
        ]
        
        # If token doesn't exist, try logging in first
        if not self.token:
            await self.refresh_token(session)

        for url in status_urls:
            try:
                async with session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    if resp.status == 200:
                        self.auth_error_logged = False
                        data = await resp.json()
                        is_active = bool(data.get("active") or data.get("spots_left", 0) > 0 or data.get("status") == "active")
                        return is_active, data
                    elif resp.status == 204:
                        self.auth_error_logged = False
                        return False, {}
                    elif resp.status in (401, 403):
                        # Token expired, try refreshing
                        logger.warning(f"⚠️ Status check returned HTTP {resp.status}. Refreshing token...")
                        if await self.refresh_token(session):
                            # Retry request once with the new token
                            async with session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=3)) as retry_resp:
                                if retry_resp.status == 200:
                                    data = await retry_resp.json()
                                    is_active = bool(data.get("active") or data.get("spots_left", 0) > 0 or data.get("status") == "active")
                                    return is_active, data
                                elif retry_resp.status == 204:
                                    return False, {}
                        
                        if not self.auth_error_logged:
                            logger.error(f"❌ Authentication failure (HTTP {resp.status}) at {url}. Login credentials or cookie might be wrong!")
                            self.auth_error_logged = True
            except Exception:
                continue
        return False, {}


    async def watch_and_solve(self):
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
                    won_code = await self.solve()
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
    token = config.ACCOUNT_TOKENS[0] if config.ACCOUNT_TOKENS else None
    
    solver = MastermindSolver(
        token=token,
        cookie=config.BROWSER_COOKIE,
        email=config.LUCID_EMAIL,
        password=config.LUCID_PASSWORD
    )
    await solver.watch_and_solve()

if __name__ == "__main__":
    asyncio.run(main())

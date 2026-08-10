import asyncio
import aiohttp
import time
import logging
import random
import string
import ssl
import certifi
from typing import List, Tuple, Set, Optional
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

# ── Candidate endpoints ──────────────────────────────────────────────────────
# Status-check endpoints (GET) - CONFIRMED REAL: /api/events/active → {"status":"closed"/"active"}
STATUS_ENDPOINTS = [
    "https://dash.lucidtrading.com/api/events/active",    # ✅ CONFIRMED REAL
    "https://dash.lucidtrading.com/api/rewards/status",
    "https://dash.lucidtrading.com/api/giveaway/status",
    "https://dash.lucidtrading.com/api/rewards",
    "https://dash.lucidtrading.com/api/rewards/event",
    "https://dash.lucidtrading.com/api/giveaway",
    "https://dash.lucidtrading.com/api/giveaway/event",
    "https://dash.lucidtrading.com/api/mobile/giveaway/status",
    "https://dash.lucidtrading.com/api/mobile/v1/giveaway/status",
    "https://dash.lucidtrading.com/api/game/status",
    "https://dash.lucidtrading.com/api/mastermind/status",
]

# Guess submission endpoints (POST)
GUESS_ENDPOINTS = [
    "https://dash.lucidtrading.com/api/rewards/guess",
    "https://dash.lucidtrading.com/api/giveaway/guess",
    "https://dash.lucidtrading.com/api/rewards/crack-code",
    "https://dash.lucidtrading.com/api/mobile/giveaway/guess",
    "https://dash.lucidtrading.com/api/mobile/v1/giveaway/guess",
    "https://dash.lucidtrading.com/api/game/guess",
    "https://dash.lucidtrading.com/api/mastermind/guess",
]

# Legacy alias kept for compatibility
MOBILE_ENDPOINTS = GUESS_ENDPOINTS

class MastermindSolver:
    """
    Automated Mastermind Code Cracker for Lucid Trading 5-digit giveaway events.
    Auto-discovers working status + guess endpoints on first use.
    """
    def __init__(self, token: str, cookie: str, email: str = None, password: str = None, endpoint_url: str = None):
        self.token = token if (token and token.startswith("Bearer ")) else f"Bearer {token}" if token else None
        self.cookie = cookie
        self.email = email
        self.password = password
        # Will be auto-discovered; fallback to first candidate
        self.guess_url   = endpoint_url or GUESS_ENDPOINTS[0]
        self.status_url  = STATUS_ENDPOINTS[0]
        self.api_url     = self.guess_url  # legacy alias
        self.headers = {
            "Authorization": self.token or "",
            "Content-Type": "application/json",
            "User-Agent": "LucidApp/90.0 (Android; Mobile)",
            "Origin": "https://dash.lucidtrading.com",
            "Referer": "https://dash.lucidtrading.com/",
            "Cookie": self.cookie or ""
        }
        self.auth_error_logged   = False
        self._endpoints_probed   = False  # flag: auto-discovery done?


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


    async def _probe_endpoints(self, session: aiohttp.ClientSession):
        """
        One-time startup probe.
        - Always refreshes token first so probes use valid auth.
        - Only marks an endpoint as 'valid' if it returns non-401 / non-404 / non-405.
        - Status: /api/events/active is CONFIRMED real, so status probe is skipped.
        """
        # ── Always refresh token FIRST so all probes use valid auth ────────
        if not self.token:
            await self.refresh_token(session)
        else:
            # Re-validate: try a lightweight login to ensure token is fresh
            await self.refresh_token(session)

        logger.info("🔍 [EndpointProbe] Probing guess endpoints with fresh token...")
        test_payload = {"code": "AAAAA", "guess": "AAAAA"}

        # ── probe guess endpoints ─────────────────────────────────────────
        best_guess = None
        for url in GUESS_ENDPOINTS:
            try:
                async with session.post(url, json=test_payload, headers=self.headers,
                                        timeout=aiohttp.ClientTimeout(total=4)) as resp:
                    text = await resp.text()
                    logger.info(f"  [GUESS] {resp.status} {url}  body={text[:80]!r}")
                    # 401 = unauthorized (bad token or endpoint requires special app session)
                    # 404/405 = endpoint doesn't exist
                    # Anything else (200, 204, 400, 422, 429) = endpoint IS real
                    if resp.status not in (401, 403, 404, 405) and best_guess is None:
                        best_guess = url
            except Exception as e:
                logger.debug(f"  [GUESS] {url}: {e}")

        if best_guess:
            self.guess_url = best_guess
            self.api_url   = best_guess
            logger.info(f"✅ [EndpointProbe] Confirmed guess endpoint: {best_guess}")
        else:
            # All returned 401 — they exist but need fresh app session.
            # Keep default; submit_guess will retry with token refresh when event fires.
            logger.warning("⚠️ [EndpointProbe] All guess endpoints returned 401 (no live event). Will retry with fresh token when event fires.")

        # Status endpoint is CONFIRMED: /api/events/active → {"status":"closed/active"}
        self.status_url = "https://dash.lucidtrading.com/api/events/active"
        logger.info(f"✅ [EndpointProbe] Status endpoint confirmed: {self.status_url}")
        self._endpoints_probed = True


    async def submit_guess(self, session: aiohttp.ClientSession, guess_code: str) -> dict:
        """
        Submits a 5-digit guess. On 401, auto-refreshes token and retries.
        If the stored guess_url fails, tries every other endpoint as fallback.
        """
        payload = {"code": guess_code, "guess": guess_code}

        # Build attempt order: stored best first, then all others as fallback
        urls_to_try = [self.guess_url] + [u for u in GUESS_ENDPOINTS if u != self.guess_url]

        for url in urls_to_try:
            start_time = time.perf_counter()
            try:
                async with session.post(url, json=payload, headers=self.headers,
                                        timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    text = await resp.text()

                    # ── 401: token expired → refresh once and retry this URL ──
                    if resp.status in (401, 403):
                        logger.warning(f"🔐 [{url}] 401 on guess — refreshing token and retrying...")
                        refreshed = await self.refresh_token(session)
                        if refreshed:
                            async with session.post(url, json=payload, headers=self.headers,
                                                    timeout=aiohttp.ClientTimeout(total=5)) as r2:
                                elapsed_ms = (time.perf_counter() - start_time) * 1000
                                text = await r2.text()
                                resp = r2
                                logger.info(f"🔁 Retry after refresh: HTTP {resp.status} ({elapsed_ms:.1f}ms): {text[:150]!r}")
                                if resp.status in (401, 403):
                                    # This URL won't work, try next one
                                    continue
                        else:
                            continue

                    # ── 404/405: endpoint doesn't exist, try next ────────────
                    if resp.status in (404, 405):
                        continue

                    # ── Got a real response ──────────────────────────────────
                    logger.info(f"🎯 Guess '{guess_code}' → HTTP {resp.status} ({elapsed_ms:.1f}ms): {text[:200]!r}")
                    # Lock in this working URL for future guesses
                    if url != self.guess_url:
                        logger.info(f"🔀 Switching to working guess endpoint: {url}")
                        self.guess_url = url
                        self.api_url   = url
                    try:
                        return await resp.json(content_type=None) if text.strip() else {}
                    except Exception:
                        return {"_raw": text, "_status": resp.status}

            except Exception as e:
                logger.error(f"⚠️ Exception on guess '{guess_code}' [{url}]: {e}")
                continue

        logger.error(f"💀 All guess endpoints failed for '{guess_code}'. No valid response.")
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
        Optimized prefix-pruned backtracking solver.
        Starts guessing randomly to gather constraints, then filters remaining search space.
        """
        logger.info("⚡ Solving Mastermind Giveaway Event...")
        connector = aiohttp.TCPConnector(limit=10, ssl=False)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            if not self.token:
                await self.refresh_token(session)
            if not self._endpoints_probed:
                await self._probe_endpoints(session)

            history = []
            next_guess = "".join(random.choices(CHAR_SET, k=5))
            consecutive_empty = 0
            
            for round_num in range(1, 20):
                logger.info(f"👉 [Round {round_num}] Submitting Guess: '{next_guess}' to {self.guess_url}")
                
                resp_data = await self.submit_guess(session, next_guess)
                
                if not resp_data:
                    consecutive_empty += 1
                    if consecutive_empty >= 3:
                        logger.warning("🚫 3 consecutive empty responses — event may be inactive or endpoint wrong. Stopping.")
                        return None
                    await asyncio.sleep(2)
                    continue
                consecutive_empty = 0

                raw_str = str(resp_data).lower()

                # ── Win condition ─────────────────────────────────────────
                WIN_KEYS = ["code_match", "win", "winner", "success", "correct", "found"]
                if (any(resp_data.get(k) for k in ["win", "winner", "found"])
                        or resp_data.get("message") in ("code_match", "success")
                        or resp_data.get("status") in ("success", "win", "winner")):
                    logger.info(f"🏆 MASTERMIND SOLVED on round {round_num}! Code: '{next_guess}'")
                    return next_guess

                # ── Inactive / ended ──────────────────────────────────────
                DEAD_SIGNALS = ["inactive", "no spots", "ended", "over", "finished", "not active", "no event"]
                if any(sig in raw_str for sig in DEAD_SIGNALS):
                    logger.warning(f"🚫 Event inactive/ended: {resp_data}")
                    return None

                # ── Parse feedback ────────────────────────────────────────
                # Support many different key name conventions
                correct_spot = (
                    resp_data.get("correctSpot") or resp_data.get("correct_spot")
                    or resp_data.get("correct") or resp_data.get("bulls")
                    or resp_data.get("exactMatches") or resp_data.get("exact")
                )
                wrong_spot = (
                    resp_data.get("wrongSpot") or resp_data.get("wrong_spot")
                    or resp_data.get("wrong") or resp_data.get("cows")
                    or resp_data.get("partialMatches") or resp_data.get("partial")
                )

                # Try nested data key
                if correct_spot is None and isinstance(resp_data.get("data"), dict):
                    d = resp_data["data"]
                    correct_spot = d.get("correctSpot") or d.get("correct_spot") or d.get("correct") or d.get("bulls")
                    wrong_spot   = d.get("wrongSpot")   or d.get("wrong_spot")   or d.get("wrong")   or d.get("cows")

                if correct_spot is None or wrong_spot is None:
                    logger.warning(f"❓ No feedback fields in response: {resp_data} — cannot update constraints, trying fresh random guess")
                    next_guess = "".join(random.choices(CHAR_SET, k=5))
                    await asyncio.sleep(3.1)
                    continue

                correct_spot = int(correct_spot)
                wrong_spot   = int(wrong_spot)
                logger.info(f"📊 Feedback: {correct_spot} exact, {wrong_spot} partial")
                history.append((next_guess, correct_spot, wrong_spot))

                # Win check via feedback
                if correct_spot == 5:
                    logger.info(f"🏆 MASTERMIND SOLVED! Code: '{next_guess}'")
                    return next_guess

                # ── Generate next guess ───────────────────────────────────
                t0 = time.perf_counter()
                candidate = self.find_candidate_backtrack(history)
                logger.info(f"⚡ Next guess generated in {(time.perf_counter()-t0)*1000:.1f}ms: '{candidate}' (history depth={len(history)})")
                next_guess = candidate or "".join(random.choices(CHAR_SET, k=5))

                await asyncio.sleep(3.1)
                
            logger.warning("🔄 Max rounds reached without solving.")
            return None


    async def check_event_status(self, session: aiohttp.ClientSession) -> Tuple[bool, dict]:
        """
        Polls the Lucid giveaway status endpoint.
        Auto-discovers the working URL on first call.
        Returns (is_active, status_data)
        """
        if not self.token:
            await self.refresh_token(session)
        if not self._endpoints_probed:
            await self._probe_endpoints(session)

        # Build probe list: discovered best URL first, then all candidates
        urls_to_try = [self.status_url] + [u for u in STATUS_ENDPOINTS if u != self.status_url]

        for url in urls_to_try:
            try:
                async with session.get(url, headers=self.headers,
                                       timeout=aiohttp.ClientTimeout(total=4)) as resp:
                    text = await resp.text()

                    # ── Token expired ─────────────────────────────────────
                    if resp.status in (401, 403):
                        if not self.auth_error_logged:
                            logger.warning(f"⚠️ HTTP {resp.status} from {url} — refreshing token...")
                        if await self.refresh_token(session):
                            self.auth_error_logged = False
                            async with session.get(url, headers=self.headers,
                                                   timeout=aiohttp.ClientTimeout(total=4)) as r2:
                                text = await r2.text()
                                resp = r2
                        else:
                            if not self.auth_error_logged:
                                logger.error("❌ Token refresh failed. Check credentials.")
                                self.auth_error_logged = True
                            continue

                    # ── 404 / 405 = not a real endpoint ──────────────────
                    if resp.status in (404, 405):
                        continue

                    # ── Parse response ────────────────────────────────────
                    self.auth_error_logged = False
                    try:
                        data = await resp.json(content_type=None) if text.strip() else {}
                    except Exception:
                        data = {"_raw": text}

                    raw_str = str(data).lower()

                    # Positive active signals
                    ACTIVE_SIGNALS = ["active", "live", "open", "running", "spots"]
                    DEAD_SIGNALS   = ["inactive", "ended", "over", "finished", "not active", "no event", "closed"]

                    is_active = (
                        bool(data.get("active"))
                        or bool(data.get("isActive"))
                        or bool(data.get("is_active"))
                        or int(data.get("spots_left", 0) or data.get("spotsLeft", 0) or 0) > 0
                        or data.get("status") in ("active", "live", "open")
                        or any(s in raw_str for s in ACTIVE_SIGNALS)
                    )

                    if any(s in raw_str for s in DEAD_SIGNALS):
                        is_active = False

                    return is_active, data

            except Exception as e:
                logger.debug(f"Status check error ({url}): {e}")
                continue

        return False, {}


    async def watch_and_solve(self):
        """
        24/7 App Watcher: Monitors the Lucid Giveaway section continuously.
        Auto-discovers working endpoints at startup, then polls every 2s.
        Only starts guessing when a live event is detected!
        """
        logger.info("👀 [Mastermind Watcher] Starting 24/7 giveaway monitor...")
        connector = aiohttp.TCPConnector(limit=10, ssl=False)

        async with aiohttp.ClientSession(connector=connector) as session:
            # ── One-time startup: login + endpoint discovery ──────────────
            if not self.token:
                await self.refresh_token(session)
            await self._probe_endpoints(session)

            check_count = 0
            while True:
                check_count += 1
                is_active, status_data = await self.check_event_status(session)

                if is_active:
                    print("\a\a\a")
                    print("\n" + "🚨" * 25)
                    print("🚨   LUCID APP GIVEAWAY IS ACTIVE NOW!   🚨")
                    print("🚨" * 25 + "\n")
                    logger.info(f"🚨 LIVE GIVEAWAY EVENT DETECTED! Status data: {status_data}")
                    logger.info("🧠 Launching Mastermind solver...")
                    won_code = await self.solve()
                    if won_code:
                        logger.info(f"🎉 GIVEAWAY WON! Code: '{won_code}'. Stopping.")
                        return
                    logger.info("🏁 Event finished — returning to watcher...")
                else:
                    if check_count % 30 == 1:  # log every 60s (30 * 2s)
                        logger.info(f"⏳ [Giveaway Watcher] Inactive (check #{check_count}) — status: {status_data or 'no data'}")

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

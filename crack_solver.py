"""
crack_solver.py
---------------
Automated Mastermind Code Cracker for Lucid Trading 5-digit giveaway events.
1. Polls /api/events/active continuously in the background.
2. Extracts eventId when the event becomes active.
3. Automatically launches the Mastermind solver submitting guesses to /api/events/submit.
4. Uses a fast backtracking constraint-satisfaction solver supporting repeating alphanumeric characters.
"""

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

ssl_context = ssl.create_default_context(cafile=certifi.where())

# Candidate character set for 5-digit code (Digits 0-9 and Uppercase A-Z)
CHAR_SET = string.digits + string.ascii_uppercase  # '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'

def get_feedback(guess: str, secret: str) -> Tuple[int, int]:
    """
    Simulates Mastermind feedback for a guess against a secret:
    Returns (correct_spot, wrong_spot)
    """
    correct_spot = sum(1 for g, s in zip(guess, secret) if g == s)
    guess_unmatched = [g for g, s in zip(guess, secret) if g != s]
    secret_unmatched = [s for g, s in zip(guess, secret) if g != s]
    wrong_spot = 0
    for char in guess_unmatched:
        if char in secret_unmatched:
            wrong_spot += 1
            secret_unmatched.remove(char)
    return correct_spot, wrong_spot

# ── Candidate endpoints ──────────────────────────────────────────────────────
STATUS_ENDPOINTS = [
    "https://dash.lucidtrading.com/api/events/active",    # ✅ CONFIRMED REAL
    "https://dash.lucidtrading.com/api/rewards/status",
    "https://dash.lucidtrading.com/api/giveaway/status",
]

GUESS_ENDPOINTS = [
    "https://dash.lucidtrading.com/api/events/submit",    # ✅ CONFIRMED REAL
    "https://dash.lucidtrading.com/api/rewards/guess",
    "https://dash.lucidtrading.com/api/giveaway/guess",
]

class MastermindSolver:
    def __init__(self, token: str, cookie: str, email: str = None, password: str = None, endpoint_url: str = None, event_id: int = None):
        self.token = token if (token and token.startswith("Bearer ")) else f"Bearer {token}" if token else None
        self.cookie = cookie
        self.email = email
        self.password = password
        self.event_id = event_id or 0
        self.guess_url = endpoint_url or GUESS_ENDPOINTS[0]
        self.status_url = STATUS_ENDPOINTS[0]
        self.headers = {
            "Authorization": self.token or "",
            "Content-Type": "application/json",
            "User-Agent": "LucidApp/90.0 (Android; Mobile)",
            "Origin": "https://dash.lucidtrading.com",
            "Referer": "https://dash.lucidtrading.com/",
            "Cookie": self.cookie or ""
        }
        self.auth_error_logged = False
        self._endpoints_probed = False

    async def refresh_token(self, session: aiohttp.ClientSession) -> bool:
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
        try:
            logger.info(f"🔄 Token expired or missing. Attempting login as {self.email}...")
            async with session.post(url, json=payload, headers=headers, timeout=8) as resp:
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
        if not self.token:
            await self.refresh_token(session)
        else:
            await self.refresh_token(session)
        self.guess_url = GUESS_ENDPOINTS[0]
        self.status_url = STATUS_ENDPOINTS[0]
        self._endpoints_probed = True

    async def submit_guess(self, session: aiohttp.ClientSession, guess_code: str, event_id: int = None) -> dict:
        target_eid = event_id or self.event_id or 0
        payload = {"code": guess_code, "eventId": target_eid}
        urls_to_try = [self.guess_url] + [u for u in GUESS_ENDPOINTS if u != self.guess_url]

        for url in urls_to_try:
            start_time = time.perf_counter()
            try:
                async with session.post(url, json=payload, headers=self.headers, timeout=5) as resp:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    text = await resp.text()

                    if resp.status in (401, 403):
                        logger.warning(f"🔐 [{url}] 401 on guess — refreshing token...")
                        if await self.refresh_token(session):
                            # Re-build payload with new token if event_id changed
                            payload["eventId"] = self.event_id or target_eid
                            async with session.post(url, json=payload, headers=self.headers, timeout=5) as r2:
                                elapsed_ms = (time.perf_counter() - start_time) * 1000
                                text = await r2.text()
                                resp = r2
                                logger.info(f"🔁 Retry after refresh: HTTP {resp.status} ({elapsed_ms:.1f}ms): {text[:150]!r}")
                                if resp.status in (401, 403):
                                    continue
                        else:
                            continue

                    if resp.status in (404, 405):
                        continue

                    logger.info(f"🎯 Guess '{guess_code}' → HTTP {resp.status} ({elapsed_ms:.1f}ms): {text[:200]!r}")
                    if url != self.guess_url:
                        self.guess_url = url
                    try:
                        return await resp.json(content_type=None) if text.strip() else {}
                    except Exception:
                        return {"_raw": text, "_status": resp.status}
            except Exception as e:
                logger.error(f"⚠️ Exception on guess '{guess_code}' [{url}]: {e}")
                continue

        logger.error(f"💀 All guess endpoints failed for '{guess_code}'.")
        return {}

    def find_candidate_backtrack(self, history: List[Tuple[str, int, int]]) -> Optional[str]:
        h_processed = []
        for g, c, w in history:
            g_counts = {}
            for char in g:
                g_counts[char] = g_counts.get(char, 0) + 1
            h_processed.append((list(g), c, w, g, g_counts))
            
        chars = list(CHAR_SET)
        
        # Pre-shuffle character lists for each depth ONCE at the start
        depth_chars = []
        for _ in range(5):
            dc = chars[:]
            random.shuffle(dc)
            depth_chars.append(dc)
            
        candidate = [''] * 5

        # Highly optimized validation
        def is_consistent_fast(cand_str: str) -> bool:
            for g_list, correct, wrong, _, _ in h_processed:
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
            
            pref_counts = {}
            for i in range(depth):
                pref_counts[candidate[i]] = pref_counts.get(candidate[i], 0) + 1
                
            remaining = 4 - depth
            
            for c in depth_chars[depth]:
                candidate[depth] = c
                pref_counts[c] = pref_counts.get(c, 0) + 1
                
                possible = True
                for g_list, correct, wrong, _, g_counts in h_processed:
                    matches = 0
                    for i in range(depth + 1):
                        if candidate[i] == g_list[i]:
                            matches += 1
                            
                    if matches > correct:
                        possible = False
                        break
                    if matches + remaining < correct:
                        possible = False
                        break
                    
                    min_overlap = 0
                    for char, count in pref_counts.items():
                        if char in g_counts:
                            min_overlap += min(count, g_counts[char])
                            
                    if min_overlap > (correct + wrong):
                        possible = False
                        break
                    if min_overlap + remaining < (correct + wrong):
                        possible = False
                        break
                
                if possible:
                    res = backtrack(depth + 1)
                    if res:
                        return res
                        
                pref_counts[c] -= 1
                if pref_counts[c] == 0:
                    del pref_counts[c]
                    
            return None
            
        return backtrack(0)

    async def solve(self) -> str:
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
            
            # Fetch custom delay from settings
            delay = config.GUESS_DELAY or 0.5
            logger.info(f"⚙️ Configured guess interval delay: {delay:.2f}s")
            
            for round_num in range(1, 20):
                logger.info(f"👉 [Round {round_num}] Submitting Guess: '{next_guess}' to {self.guess_url}")
                
                resp_data = await self.submit_guess(session, next_guess, self.event_id)
                
                if not resp_data:
                    consecutive_empty += 1
                    if consecutive_empty >= 3:
                        logger.warning("🚫 3 consecutive empty responses — event may be inactive. Stopping.")
                        return None
                    await asyncio.sleep(2)
                    continue
                consecutive_empty = 0

                raw_str = str(resp_data).lower()

                # ── Win condition ─────────────────────────────────────────
                if (any(resp_data.get(k) for k in ["win", "winner", "found"])
                        or resp_data.get("message") in ("code_match", "success")
                        or resp_data.get("status") in ("success", "win", "winner")):
                    logger.info(f"🏆 MASTERMIND SOLVED on round {round_num}! Code: '{next_guess}'")
                    return next_guess

                # ── Inactive / ended ──────────────────────────────────────
                DEAD_SIGNALS = ["inactive", "no spots", "ended", "over", "finished", "not active", "no event", "event_closed"]
                if any(sig in raw_str for sig in DEAD_SIGNALS):
                    logger.warning(f"🚫 Event inactive/ended: {resp_data}")
                    return None

                # ── Parse feedback ────────────────────────────────────────
                correct_spot = None
                for key in ["correctSpot", "correct_spot", "correct", "exactMatches"]:
                    val = resp_data.get(key)
                    if val is not None:
                        correct_spot = val
                        break
                        
                wrong_spot = None
                for key in ["wrongSpot", "wrong_spot", "wrong", "partialMatches"]:
                    val = resp_data.get(key)
                    if val is not None:
                        wrong_spot = val
                        break

                if correct_spot is None and isinstance(resp_data.get("data"), dict):
                    d = resp_data["data"]
                    for key in ["correctSpot", "correct_spot", "correct"]:
                        val = d.get(key)
                        if val is not None:
                            correct_spot = val
                            break
                    for key in ["wrongSpot", "wrong_spot", "wrong"]:
                        val = d.get(key)
                        if val is not None:
                            wrong_spot = val
                            break

                if correct_spot is None or wrong_spot is None:
                    logger.warning(f"❓ No feedback fields in response: {resp_data} — cannot update constraints, trying fresh random guess")
                    next_guess = "".join(random.choices(CHAR_SET, k=5))
                    await asyncio.sleep(delay)
                    continue

                correct_spot = int(correct_spot)
                wrong_spot   = int(wrong_spot)
                logger.info(f"📊 Feedback: {correct_spot} exact, {wrong_spot} partial")
                history.append((next_guess, correct_spot, wrong_spot))

                if correct_spot == 5:
                    logger.info(f"🏆 MASTERMIND SOLVED! Code: '{next_guess}'")
                    return next_guess

                # ── Generate next guess ───────────────────────────────────
                t0 = time.perf_counter()
                candidate = self.find_candidate_backtrack(history)
                logger.info(f"⚡ Next guess generated in {(time.perf_counter()-t0)*1000:.1f}ms: '{candidate}' (history depth={len(history)})")
                next_guess = candidate or "".join(random.choices(CHAR_SET, k=5))

                await asyncio.sleep(delay)
                
            logger.warning("🔄 Max rounds reached without solving.")
            return None

    async def check_event_status(self, session: aiohttp.ClientSession) -> Tuple[bool, dict]:
        if not self.token:
            await self.refresh_token(session)
        if not self._endpoints_probed:
            await self._probe_endpoints(session)

        urls_to_try = [self.status_url] + [u for u in STATUS_ENDPOINTS if u != self.status_url]

        for url in urls_to_try:
            try:
                async with session.get(url, headers=self.headers, timeout=4) as resp:
                    text = await resp.text()

                    if resp.status in (401, 403):
                        if not self.auth_error_logged:
                            logger.warning(f"⚠️ HTTP {resp.status} from {url} — refreshing token...")
                        if await self.refresh_token(session):
                            self.auth_error_logged = False
                            async with session.get(url, headers=self.headers, timeout=4) as r2:
                                text = await r2.text()
                                resp = r2
                        else:
                            if not self.auth_error_logged:
                                logger.error("❌ Token refresh failed. Check credentials.")
                                self.auth_error_logged = True
                            continue

                    if resp.status in (404, 405):
                        continue

                    self.auth_error_logged = False
                    try:
                        data = await resp.json(content_type=None) if text.strip() else {}
                    except Exception:
                        data = {"_raw": text}

                    raw_str = str(data).lower()

                    ACTIVE_SIGNALS = ["active", "live", "open", "running"]
                    DEAD_SIGNALS   = ["inactive", "ended", "over", "finished", "not active", "no event", "closed"]

                    is_active = (
                        bool(data.get("active"))
                        or bool(data.get("isActive"))
                        or bool(data.get("is_active"))
                        or data.get("status") in ("active", "live", "open")
                        or any(s in raw_str for s in ACTIVE_SIGNALS)
                    )

                    if any(s in raw_str for s in DEAD_SIGNALS):
                        is_active = False

                    if is_active:
                        event_id = data.get("id") or data.get("eventId") or data.get("event_id") or data.get("event", {}).get("id")
                        if event_id:
                            self.event_id = int(event_id)
                            logger.info(f"📍 Extracted Event ID: {self.event_id}")

                    return is_active, data

            except Exception as e:
                logger.debug(f"Status check error ({url}): {e}")
                continue

        return False, {}

    async def watch_and_solve(self):
        logger.info("👀 [Mastermind Watcher] Starting 24/7 giveaway monitor...")
        connector = aiohttp.TCPConnector(limit=10, ssl=False)

        async with aiohttp.ClientSession(connector=connector) as session:
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
                    won_code = await self.solve()
                    if won_code:
                        logger.info(f"🎉 GIVEAWAY WON! Code: '{won_code}'.")
                    logger.info("🏁 Event finished — returning to watcher...")
                else:
                    if check_count % 30 == 1:
                        logger.info(f"⏳ [Giveaway Watcher] Inactive (check #{check_count}) — status: {status_data or 'no data'}")

                await asyncio.sleep(30.0)

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

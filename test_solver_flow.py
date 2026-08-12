"""
test_solver_flow.py
--------------------
Mocks active event status and mastermind feedback APIs to simulate a live 
giveaway round, proving that crack_solver.py works end-to-end.
"""

import asyncio
import logging
from unittest.mock import MagicMock, AsyncMock, patch

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

# Load solver module
import config
config.ACCOUNT_TOKENS = ["dummy_token"]
config.BROWSER_COOKIE = "dummy_cookie"
config.GUESS_DELAY = 0.01  # Speed up simulation delay to 10ms

from crack_solver import MastermindSolver

SECRET_CODE = "A3B9Z"

def get_mock_feedback(guess: str) -> dict:
    if guess == SECRET_CODE:
        return {"status": "win", "message": "code_match", "reward": "FREE_EVAL_50K"}
        
    correct_spot = sum(1 for g, s in zip(guess, SECRET_CODE) if g == s)
    guess_unmatched = [g for g, s in zip(guess, SECRET_CODE) if g != s]
    secret_unmatched = [s for g, s in zip(guess, SECRET_CODE) if g != s]
    wrong_spot = 0
    for char in guess_unmatched:
        if char in secret_unmatched:
            wrong_spot += 1
            secret_unmatched.remove(char)
            
    return {
        "correctSpot": correct_spot,
        "wrongSpot": wrong_spot,
        "status": "continue"
    }

class AsyncContextManagerMock:
    def __init__(self, return_value):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

async def run_simulation():
    solver = MastermindSolver(token="dummy_token", cookie="dummy_cookie", event_id=0)
    guess_count = 0

    # Mock response for GET (active status)
    mock_get_resp = MagicMock()
    mock_get_resp.status = 200
    mock_get_resp.text = AsyncMock(return_value='{"active": true, "id": 9999}')
    mock_get_resp.json = AsyncMock(return_value={"active": True, "id": 9999})

    # Intercept session.get to return our async context manager
    def mock_get(url, headers, timeout=None):
        return AsyncContextManagerMock(mock_get_resp)

    # Intercept session.post to return our async context manager with dynamic feedback
    def mock_post(url, json, headers, timeout=None):
        nonlocal guess_count
        guess_count += 1
        guess_code = json.get("code")
        
        # Calculate dynamic response
        resp_data = get_mock_feedback(guess_code)
        
        print(f"📡 API POST {url} | Payload: {json} | Guess #{guess_count}: '{guess_code}'")
        print(f"   ↳ Response: {resp_data}")
        
        mock_post_resp = MagicMock()
        mock_post_resp.status = 200
        mock_post_resp.text = AsyncMock(return_value=str(resp_data))
        mock_post_resp.json = AsyncMock(return_value=resp_data)
        return AsyncContextManagerMock(mock_post_resp)

    print("--- STARTING SOLVER SIMULATION ---")
    print(f"Secret Target Code: {SECRET_CODE}")
    print("----------------------------------\n")

    with patch("aiohttp.ClientSession.get", side_effect=mock_get), \
         patch("aiohttp.ClientSession.post", side_effect=mock_post):
        
        import aiohttp
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            # Step 1: Status Check
            is_active, data = await solver.check_event_status(session)
            print(f"\n📋 Event Status Check: Active={is_active}, Event ID={solver.event_id}")
            
            if is_active:
                print("\n🚀 Starting Mastermind Solver Loop...")
                won_code = await solver.solve()
                print(f"\n🏆 Solver Finished! Code Cracked: '{won_code}'")
                print(f"🎯 Total Guesses Submitted: {guess_count}")

if __name__ == "__main__":
    asyncio.run(run_simulation())

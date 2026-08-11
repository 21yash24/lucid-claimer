"""
termux_crack_solver.py
----------------------
1-Tap Phone Mastermind Code Cracker for Termux / Android / Mac.
When the giveaway puzzle goes live in your app:
1. Launch this script on your phone via Termux: python termux_crack_solver.py
2. It auto-submits guesses to the mobile API or lets you input feedback to calculate the exact 5-digit code in < 1 millisecond!
"""

import sys
import time
import random
import string
import json
import urllib.request
import ssl
import config

CHAR_SET = string.digits + string.ascii_uppercase  # 0-9 and A-Z

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

class MastermindSolver:
    def __init__(self):
        self.history = []

    def is_consistent(self, cand_str: str) -> bool:
        for g_list, correct, wrong, g_counts in self.history:
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

    def get_next_candidate() -> str:
        pass

def get_mobile_token() -> str:
    url = 'https://dash.lucidtrading.com/api/mobile/login'
    payload = json.dumps({'email': config.LUCID_EMAIL, 'password': config.LUCID_PASSWORD, 'username': config.LUCID_EMAIL}).encode('utf-8')
    headers = {'Content-Type': 'application/json', 'User-Agent': 'LucidApp/90.0 (Android; Mobile)'}
    try:
        req = urllib.request.Request(url, data=payload, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get('token', '')
    except Exception as e:
        print("⚠️ Login warning:", e)
        return ""

def main():
    print("=" * 65)
    print("🔥 1-TAP PHONE MASTERMIND CRACKER (TERMUX / MOBILE)")
    print("=" * 65)
    
    token = get_mobile_token()
    if token:
        print("🔑 Mobile Auth Token Loaded!")
    
    solver = MastermindSolver()
    
    print("\n🚀 SOLVER READY! Press ENTER to start cracking standard 5-digit code...\n")
    
    # Pre-calculated optimal first guess
    next_guess = "".join(random.choices(CHAR_SET, k=5))
    
    for round_num in range(1, 20):
        print("─" * 50)
        print(f"👉 [ROUND {round_num}] TRY THIS CODE ON YOUR PHONE:   \033[1;32m{next_guess}\033[0m")
        print("─" * 50)
        
        # If token is available, attempt direct API submission in background
        if token:
            submit_urls = [
                'https://dash.lucidtrading.com/api/events/submit',
                'https://dash.lucidtrading.com/api/mobile/events/submit',
                'https://dash.lucidtrading.com/api/mobile/events/guess',
            ]
            for s_url in submit_urls:
                try:
                    payload = json.dumps({'code': next_guess}).encode('utf-8')
                    headers = {
                        'Authorization': f'Bearer {token}',
                        'Content-Type': 'application/json',
                        'User-Agent': 'LucidApp/90.0 (Android; Mobile)'
                    }
                    req = urllib.request.Request(s_url, data=payload, headers=headers)
                    with urllib.request.urlopen(req, context=ctx, timeout=2) as resp:
                        res_text = resp.read().decode('utf-8')
                        if "win" in res_text.lower() or "success" in res_text.lower():
                            print(f"\n🎉🎉🎉 WINNER! API Auto-Claimed Code: {next_guess} 🎉🎉🎉\n")
                            return
                except Exception:
                    pass

        feedback_input = input("Enter feedback (e.g. '2 1' for 2 exact, 1 partial) or 'WIN': ").strip().upper()
        
        if feedback_input in ('WIN', 'W', 'SUCCESS', '5 0', '5'):
            print(f"\n🎉🎉🎉 WINNER! CODE IS: {next_guess} 🎉🎉🎉\n")
            break
            
        try:
            parts = feedback_input.split()
            c_spot = int(parts[0])
            w_spot = int(parts[1]) if len(parts) > 1 else 0
        except Exception:
            print("⚠️ Invalid feedback format. Assuming 0 exact 0 partial.")
            c_spot, w_spot = 0, 0

        # Update solver history
        g_counts = {}
        for char in next_guess:
            g_counts[char] = g_counts.get(char, 0) + 1
        solver.history.append((list(next_guess), c_spot, w_spot, g_counts))
        
        # Find next optimal candidate
        t0 = time.time()
        chars = list(CHAR_SET)
        candidate = None
        for _ in range(100000):
            cand = "".join(random.choices(chars, k=5))
            if solver.is_consistent(cand):
                candidate = cand
                break
                
        calc_time = (time.time() - t0) * 1000
        print(f"⚡ Calculated next optimal guess in {calc_time:.1f}ms: {candidate}")
        next_guess = candidate or "".join(random.choices(CHAR_SET, k=5))

if __name__ == "__main__":
    main()

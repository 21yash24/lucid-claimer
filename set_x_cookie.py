"""
set_x_cookie.py
---------------
Helper script to save X auth_token and ct0 into x_cookies.json
so Twikit connects instantly without login issues.
"""
import sys
import json
import os

def save_cookie(auth_token, ct0=""):
    cookies = {
        "auth_token": auth_token.strip(),
        "ct0": ct0.strip()
    }
    out_path = os.path.join(os.path.dirname(__file__), "x_cookies.json")
    with open(out_path, "w") as f:
        json.dump(cookies, f, indent=2)
    print(f"✅ Saved x_cookies.json with auth_token successfully!")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        token = sys.argv[1]
        ct0 = sys.argv[2] if len(sys.argv) > 2 else ""
        save_cookie(token, ct0)
    else:
        print("Usage: python3 set_x_cookie.py <AUTH_TOKEN> [CT0]")

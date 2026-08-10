import os

def main():
    discord_token = ""
    account_tokens = ""
    lucid_email = "yashjha2004@gmail.com"
    lucid_password = "Manjoo#1976"

    # 1. Read existing .env if it exists and extract tokens
    if os.path.exists(".env"):
        print("📖 Reading current .env file to preserve your tokens...")
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key == "DISCORD_TOKEN":
                        discord_token = val
                    elif key == "ACCOUNT_TOKENS":
                        account_tokens = val
                    elif key == "LUCID_EMAIL":
                        lucid_email = val
                    elif key == "LUCID_PASSWORD":
                        lucid_password = val

    # 2. Re-write the clean and correct .env file
    env_content = f"""DISCORD_TOKEN={discord_token}
TARGET_CHANNEL_ID=1344026694691848274
REDEMPTION_API_URL=https://dash.lucidtrading.com/api/rewards/redeem-secret

# Multi-account configuration
ACCOUNT_TOKENS={account_tokens}
LUCID_EMAIL={lucid_email}
LUCID_PASSWORD={lucid_password}

# X (Twitter) Scraper Settings
X_EMAIL=yjha974@gmail.com
X_PASSWORD=Nikita#2000
X_USERNAME=yjha974@gmail.com
X_TARGET_USER=cj_wawa,yashhjhaa
X_POLL_INTERVAL=12.0
"""

    with open(".env", "w") as f:
        f.write(env_content)
        
    print("✅ Successfully cleaned and rebuilt your .env file!")
    print(f"📡 Targets set to: cj_wawa, yashhjhaa")
    print(f"⏳ Poll interval set to: 12.0s")

if __name__ == "__main__":
    main()

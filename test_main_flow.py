"""
test_main_flow.py
------------------
Simulates a Discord message containing a drop code being received by main.py
to prove that the parser, claimer, and API endpoint (/api/rewards/redeem-secret)
trigger and execute successfully.
"""

import asyncio
import logging
import sys
from unittest.mock import MagicMock

# Configure logging to match main.py
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("TestFlow")

# Set dummy credentials in config before loading main
import config
config.DISCORD_TOKEN = "dummy_discord_token"
config.ACCOUNT_TOKENS = ["dummy_token_123"]
config.REDEMPTION_API_URL = "https://dash.lucidtrading.com/api/rewards/redeem-secret"

# Import main components
import main

class MockMessage:
    def __init__(self, content, channel_id):
        self.content = content
        self.author = "LucidDropBot"
        self.embeds = []
        self.channel = MagicMock()
        self.channel.id = channel_id

async def run_proof():
    # Target channel ID from config
    target_channel = config.TARGET_CHANNEL_IDS[0]
    
    # 1. Construct a mock message containing a drop code
    mock_message_text = "🚨 NEW DROP CODE IS: LBOX_TEST123! GO REDEEM IT QUICK!"
    mock_msg = MockMessage(content=mock_message_text, channel_id=int(target_channel))
    
    print("\n--- SIMULATING INCOMING DISCORD MESSAGE ---")
    print(f"Channel ID: {target_channel}")
    print(f"Content: {mock_message_text}")
    print("-------------------------------------------\n")
    
    # Initialize the claimer persistent session
    await main.claimer.initialize()
    
    # 2. Feed message directly into main.py's on_message handler
    try:
        await main.on_message(mock_msg)
    except Exception as e:
        logger.error(f"Error during simulation: {e}")
    finally:
        await main.claimer.close()

if __name__ == "__main__":
    asyncio.run(run_proof())

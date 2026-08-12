"""
test_woocommerce_checkout.py
----------------------------
Tests the new claimer.py WooCommerce checkout flow by making a live attempt
with a dummy coupon.
Verifies if:
1. Login token is accepted
2. Product is successfully added to cart (Step 1)
3. Coupon validation API responds correctly (Step 2)
"""

import asyncio
import sys
import logging

sys.path.insert(0, '.')
import config
from claimer import MultiAccountClaimer

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("TestWooCommerce")

async def main():
    # Instantiate claimer
    claimer = MultiAccountClaimer(
        config.REDEMPTION_API_URL,
        config.ACCOUNT_TOKENS,
        config.LUCID_ACCOUNTS
    )
    
    # Initialize connection pools
    await claimer.initialize()
    
    token = claimer.account_tokens[0]
    dummy_coupon = "soimwomed"
    plan_to_test = "50k"
    
    logger.info(f"🧪 Testing WooCommerce Checkout Flow...")
    logger.info(f"   Plan: {plan_to_test} | Coupon: {dummy_coupon}")
    
    # Run the checkout
    res = await claimer.checkout_single_account(
        account_index=0,
        token=token,
        code=dummy_coupon,
        plan_id=plan_to_test
    )
    
    logger.info(f"📊 Test Result: {res}")
    
    # Cleanup session
    await claimer.close()

if __name__ == "__main__":
    asyncio.run(main())

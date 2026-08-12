"""
parse_catalog.py
----------------
Loads plans_catalog.json, searches for 25K/50K/100K accounts and lists their keys.
"""

import json

def main():
    with open("plans_catalog.json", "r") as f:
        data = json.load(f)
        
    print(f"Total items in catalog: {len(data)}")
    if isinstance(data, list) and len(data) > 0:
        print("Keys of first item:", list(data[0].keys()))
        
        # Search for items matching 25k, 50k, 100k
        for idx, item in enumerate(data):
            # Print item representation
            item_str = str(item).lower()
            if "25k" in item_str or "50k" in item_str or "100k" in item_str:
                print(f"\n[{idx}] Match found:")
                # print nice json representation of only relevant keys
                clean_item = {k: v for k, v in item.items() if k in ["id", "productId", "name", "price", "title", "product_id", "woocommerceId", "woo_id", "woo_product_id", "wooProductId", "stripeId"]}
                if not clean_item:
                    clean_item = item
                print(json.dumps(clean_item, indent=2))

if __name__ == "__main__":
    main()

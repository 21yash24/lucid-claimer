import asyncio
import os
import sys
from twikit import Client

async def main():
    client = Client('en-US')
    cookies_path = "x_cookies.json"
    
    if os.path.exists(cookies_path):
        client.load_cookies(cookies_path)
        print("🔓 Cookies loaded.")
    else:
        print("❌ No cookies found in x_cookies.json!")
        return
        
    username = "yashhjhaa"  # Check last tweet from this user
    print(f"📡 Fetching last tweet from @{username}...")
    try:
        user = await client.get_user_by_screen_name(username)
        tweets = await user.get_tweets('Tweets', count=1)
        if not tweets:
            print("❌ No tweets found!")
            return
        
        tweet = tweets[0]
        media_list = getattr(tweet, "media", None) or getattr(tweet, "extended_entities", {}).get("media", [])
        if not media_list:
            print("❌ Last tweet has no media attachments!")
            return
            
        media = media_list[0]
        media_url = media.get("media_url_https") if isinstance(media, dict) else getattr(media, "media_url_https", None)
        print(f"📸 Found media: {media_url}")
        
        os.makedirs("tmp_images", exist_ok=True)
        img_path = "tmp_images/test_image.jpg"
        
        print("📥 Downloading image...")
        if not isinstance(media, dict) and hasattr(media, "download"):
            await media.download(img_path)
        else:
            # Fallback download using requests/urllib
            import urllib.request
            urllib.request.urlretrieve(media_url, img_path)
            
        print(f"✅ Downloaded to {img_path}!")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())

"""
extract_x_cookies.py
--------------------
Extracts X (twitter.com / x.com) auth cookies directly from Chrome's SQLite cookie database
and formats them for Twikit in x_cookies.json.
"""
import os
import shutil
import sqlite3
import json
import subprocess

def extract():
    src_db = os.path.expanduser('~/Library/Application Support/Google/Chrome/Default/Cookies')
    if not os.path.exists(src_db):
        print("❌ Chrome cookies DB not found.")
        return False

    tmp_db = os.path.join(os.path.dirname(__file__), "tmp_cookies.db")
    shutil.copyfile(src_db, tmp_db)

    conn = sqlite3.connect(tmp_db)
    cursor = conn.cursor()

    # Query x.com / twitter.com cookies
    cursor.execute("""
        SELECT host_key, name, encrypted_value, value 
        FROM cookies 
        WHERE host_key LIKE '%twitter.com%' OR host_key LIKE '%x.com%'
    """)

    rows = cursor.fetchall()
    print(f"Found {len(rows)} X/Twitter cookies in Chrome.")

    cookies_dict = {}

    # Try decrypting using macOS Keychain (Security tool)
    try:
        # Get Chrome Safe Storage key from Mac Keychain
        res = subprocess.run(
            ["security", "find-generic-password", "-w", "-s", "Chrome Safe Storage"],
            capture_output=True, text=True
        )
        safe_key = res.stdout.strip().encode('utf-8')
        if safe_key:
            import cryptography
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA1(),
                length=16,
                salt=b'saltysalt',
                iterations=1003
            )
            key = kdf.derive(safe_key)

            for host, name, enc_val, val in rows:
                if val:
                    cookies_dict[name] = val
                elif enc_val:
                    try:
                        # Chrome on Mac AES-CBC decryption (strip 'v10' prefix)
                        if enc_val.startswith(b'v10'):
                            enc_val = enc_val[3:]
                        iv = b' ' * 16
                        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
                        decryptor = cipher.decryptor()
                        decrypted = decryptor.update(enc_val) + decryptor.finalize()
                        # PKCS7 unpad
                        pad_len = decrypted[-1]
                        decrypted_val = decrypted[:-pad_len].decode('utf-8', errors='ignore')
                        cookies_dict[name] = decrypted_val
                    except Exception:
                        pass
    except Exception as e:
        print(f"Keychain decryption note: {e}")
        # Fallback to unencrypted values
        for host, name, enc_val, val in rows:
            if val:
                cookies_dict[name] = val

    conn.close()
    if os.path.exists(tmp_db):
        os.remove(tmp_db)

    print(f"Extracted cookie keys: {list(cookies_dict.keys())}")

    if "auth_token" in cookies_dict:
        out_path = os.path.join(os.path.dirname(__file__), "x_cookies.json")
        with open(out_path, "w") as f:
            json.dump(cookies_dict, f, indent=2)
        print(f"✅ Saved x_cookies.json with auth_token successfully!")
        return True
    else:
        print("⚠️ auth_token not found in Chrome cookies (make sure you are logged into x.com in Chrome).")
        return False

if __name__ == "__main__":
    extract()

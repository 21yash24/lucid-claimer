"""
test_mac_keystrokes.py
----------------------
Tests bringing Google Chrome to focus and pasting the coupon code
natively using macOS System Events.
"""

import subprocess
import time

def paste_code_to_frontmost_chrome(code: str):
    # 1. Put code in clipboard
    subprocess.run(['pbcopy'], input=code.encode('utf-8'))
    
    # 2. Activate Chrome and paste
    applescript = '''
    tell application "Google Chrome" to activate
    delay 0.1
    tell application "System Events"
        keystroke "v" using {command down}
        delay 0.1
        key code 36 -- Press Return/Enter
    end tell
    '''
    
    try:
        subprocess.run(['osascript', '-e', applescript])
        print(f"✅ Successfully pasted '{code}' into active Chrome window and pressed Enter!")
    except Exception as e:
        print(f"❌ Error pasting via System Events: {e}")

if __name__ == "__main__":
    paste_code_to_frontmost_chrome("LBOX_TEST_COUPON")

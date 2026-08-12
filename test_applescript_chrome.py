"""
test_applescript_chrome.py
--------------------------
Tests controlling Google Chrome via AppleScript to fill and submit
the coupon code input box in the active Chrome window.
"""

import subprocess

def fill_coupon_in_open_chrome(coupon_code: str):
    js_code = f"""
        (function() {{
            var filled = false;
            var inputs = document.querySelectorAll('input');
            for (var i = 0; i < inputs.length; i++) {{
                var p = (inputs[i].placeholder || '').toLowerCase();
                var n = (inputs[i].name || '').toLowerCase();
                if (p.includes('coupon') || p.includes('code') || n.includes('coupon')) {{
                    inputs[i].value = '{coupon_code}';
                    inputs[i].dispatchEvent(new Event('input', {{ bubbles: true }}));
                    inputs[i].dispatchEvent(new Event('change', {{ bubbles: true }}));
                    filled = true;
                    break;
                }}
            }}
            var btns = document.querySelectorAll('button');
            for (var j = 0; j < btns.length; j++) {{
                var txt = (btns[j].innerText || '').toLowerCase();
                if (txt.includes('apply')) {{
                    btns[j].click();
                    break;
                }}
            }}
            return filled ? 'SUCCESS' : 'NO_INPUT_FOUND';
        }})();
    """
    
    applescript = f'''
    tell application "Google Chrome"
        if (count of windows) > 0 then
            execute active tab of front window javascript "{js_code.replace('"', '\\"').replace('\n', ' ')}"
        end if
    end tell
    '''
    
    try:
        res = subprocess.run(['osascript', '-e', applescript], capture_output=True, text=True)
        print(f"AppleScript Output: {res.stdout.strip()}")
        print(f"AppleScript Error: {res.stderr.strip()}")
    except Exception as e:
        print(f"Error running AppleScript: {e}")

if __name__ == "__main__":
    fill_coupon_in_open_chrome("TEST1234")

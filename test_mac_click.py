"""
test_mac_click.py
-----------------
Tests native macOS CoreGraphics mouse clicking via ctypes with correct C signature.
"""
import ctypes
import time

# Load CoreGraphics
cg = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/ApplicationServices.framework/Frameworks/CoreGraphics.framework/CoreGraphics')

class CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

# Define function signatures
cg.CGEventCreateMouseEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, CGPoint, ctypes.c_uint32]
cg.CGEventCreateMouseEvent.restype = ctypes.c_void_p

cg.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
cg.CGEventPost.restype = None

def mac_click(x, y):
    pt = CGPoint(float(x), float(y))

    # kCGEventLeftMouseDown = 1, kCGEventLeftMouseUp = 2, kCGMouseButtonLeft = 0
    # kCGHIDEventTap = 0
    e_down = cg.CGEventCreateMouseEvent(None, 1, pt, 0)
    cg.CGEventPost(0, e_down)
    
    time.sleep(0.05)
    
    e_up = cg.CGEventCreateMouseEvent(None, 2, pt, 0)
    cg.CGEventPost(0, e_up)

    print(f"✅ Native CGEvent Clicked at display coords ({x}, {y})")

if __name__ == "__main__":
    mac_click(500, 300)

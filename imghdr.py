"""
Polyfill for standard library module `imghdr` which was removed in Python 3.13 (PEP 594).
Used by python-telegram-bot and image handling libraries.
"""
import sys

def what(file, h=None):
    if h is None:
        if isinstance(file, str):
            try:
                with open(file, 'rb') as f:
                    h = f.read(32)
            except Exception:
                return None
        elif isinstance(file, (bytes, bytearray)):
            h = file[:32]
        elif hasattr(file, 'read') and hasattr(file, 'tell') and hasattr(file, 'seek'):
            try:
                pos = file.tell()
                h = file.read(32)
                file.seek(pos)
            except Exception:
                return None
        else:
            return None

    if not h:
        return None

    if h.startswith(b'\xff\xd8'):
        return 'jpeg'
    if h.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if h.startswith(b'GIF87a') or h.startswith(b'GIF89a'):
        return 'gif'
    if h.startswith(b'RIFF') and h[8:12] == b'WEBP':
        return 'webp'
    if h.startswith(b'BM'):
        return 'bmp'
    if h.startswith(b'MM\x00*') or h.startswith(b'II*\x00'):
        return 'tiff'
    return None

# Register module into sys.modules if needed
sys.modules['imghdr'] = sys.modules[__name__]

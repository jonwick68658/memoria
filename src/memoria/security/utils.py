"""
Shared utility functions for security modules.
"""
import re
import base64
from typing import List, Dict, Any

def sanitize_input(text: str) -> str:
    """Basic input sanitization: remove HTML tags, normalize whitespace."""
    text = re.sub(r'<script.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'[ \t\n\r]+', ' ', text)
    return text.strip()

def decode_obfuscated(text: str) -> List[str]:
    """Decode potential obfuscated threats like base64 or rot13."""
    decoded = []
    try:
        # Base64 decode
        if re.match(r'^[A-Za-z0-9+/=]+$', text):
            decoded.append(base64.b64decode(text).decode('utf-8', errors='ignore'))
    except:
        pass
    # Rot13 (simple, add if needed)
    decoded.append(''.join(chr(ord(c) + 13) if c.isalpha() else c for c in text))
    return [d for d in decoded if d != text]

def is_threat_pattern(text: str, patterns: List[str], threshold: float = 0.5) -> float:
    """Simple pattern matching score for threats."""
    score = 0.0
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            score += 1.0 / len(patterns)
    return score if score >= threshold else 0.0
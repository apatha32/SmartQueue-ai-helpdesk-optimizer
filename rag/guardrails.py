import re
from typing import List

# Patterns that signal prompt injection attempts
_PATTERNS: List[re.Pattern] = [
    re.compile(
        r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|context)",
        re.IGNORECASE,
    ),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above|earlier)", re.IGNORECASE),
    re.compile(
        r"forget\s+(everything|all|your|the)\s+(you\s+know|previous|instructions?|training)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(override|bypass|escape)\s+(your\s+)?(system|safety|content)\s*(prompt|filter|policy|guidelines?)",
        re.IGNORECASE,
    ),
    re.compile(r"<\s*(system|instructions?)\s*>", re.IGNORECASE),
    re.compile(r"\[INST\]|\[\/INST\]|<\|im_start\|>|<\|im_end\|>"),
    re.compile(r"###\s*(system|instruction)\s*:", re.IGNORECASE),
    re.compile(
        r"you\s+are\s+now\s+(?!a\s+helpful|an?\s+AI\s+assistant)",
        re.IGNORECASE,
    ),
]


def check_injection(text: str) -> bool:
    """Return True if the text appears to contain a prompt injection attempt."""
    for pattern in _PATTERNS:
        if pattern.search(text):
            return True
    return False

"""PII Redaction and pseudonymization utilities.

Regex-based redaction of emails, national identity numbers, phone numbers, and explicitly introduced personal names.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Tuple

_EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
_IC = re.compile(r"(?<!\d)\d{6}-?\d{2}-?\d{4}(?!\d)")
_MY_MOBILE = re.compile(r"(?<![\w])(?:\+?60|0)\s?1\d(?:[\s\-]?\d){7,8}(?!\d)")
_LONG_DIGITS = re.compile(r"(?<!\d)\+?\d[\d\s\-()]{7,18}\d(?!\d)")
_PASSPORT = re.compile(r"(?<![A-Za-z0-9])[A-Z]\d{7,8}(?![A-Za-z0-9])")
_NOT_NAMES = frozenset(
    """interested looking planning thinking currently from in not a an the applying wondering asking writing here new
    still also just really very sorry glad happy confused worried currently student parent father mother""".split()
)
_INTRO = re.compile(r"\b(?:I am|I'm|this is|my name is|nama saya|saya)\s+([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,2})\b")
_RELATIVE_NAME = re.compile(
    r"(?i)\b(?:my (?:father|mother|dad|mum|son|daughter|brother|sister|child)(?:'s)? name(?: is)?|nama (?:ayah|ibu|anak)(?: saya)?)\s*:?\s+([A-Za-z'@\-]+(?:\s+[A-Za-z'@\-]+){0,2})"
)
_NAME = re.compile(r"(?i)\b(my name is|nama saya|nama\s*:|name\s*:)\s+([A-Za-z'@.\-]+(?:\s+[A-Za-z'@.\-]+){0,2})")


def salted_hash(value: str, salt: str) -> str:
    """Computes a salted SHA-256 hash surrogate for an identifier."""
    return hashlib.sha256(f"{salt}:{value}".encode("utf-8")).hexdigest()[:16]


def redact(text: str) -> Tuple[str, Counter]:
    """Replace direct identifiers with tokens. Names are only caught after explicit introductions (no NER)."""
    counts: Counter = Counter()

    def sub(pattern, token, s, min_digits=0):
        def repl(m):
            if min_digits and sum(c.isdigit() for c in m.group(0)) < min_digits:
                return m.group(0)
            counts[token] += 1
            return token

        return pattern.sub(repl, s)

    out = sub(_EMAIL, "[EMAIL]", text)
    out = sub(_IC, "[ID_NUMBER]", out)
    out = sub(_MY_MOBILE, "[PHONE]", out)
    out = sub(_LONG_DIGITS, "[PHONE]", out, min_digits=9)

    def name_repl(m):
        full = m.group(0)
        intro = m.group(1)
        name_part = full[len(intro) :] if full.startswith(intro) else m.group(len(m.groups()))
        first_token = name_part.strip().split()[0].lower() if name_part.strip() else ""
        if first_token in _NOT_NAMES:
            return full
        counts["[NAME]"] += 1
        return full.replace(name_part.strip(), "[NAME]")

    out = _NAME.sub(name_repl, out)
    out = _RELATIVE_NAME.sub(name_repl, out)
    out = _INTRO.sub(name_repl, out)
    return out, counts


def redact_text_only(text: str) -> str:
    """Convenience helper returning redacted text without counts."""
    clean, _ = redact(text)
    return clean

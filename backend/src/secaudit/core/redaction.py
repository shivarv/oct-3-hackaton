"""Redaction helpers. Every piece of evidence passes through here before it is logged or persisted."""

from __future__ import annotations

import hashlib
import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Credentials embedded in connection strings: scheme://user:pass@host
    (
        re.compile(r"(?P<scheme>[a-z][a-z0-9+.-]*://)[^:/@\s]+:[^@\s]+@", re.I),
        r"\g<scheme>***:***@",
    ),
    # JWTs
    (re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]+"), "<jwt:redacted>"),
    # Bearer / API keys
    (re.compile(r"(?i)(bearer\s+)[\w\-.~+/]+=*"), r"\1<redacted>"),
    (
        re.compile(r"(?i)((?:api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?)[^'\"\s,}]+"),
        r"\1<redacted>",
    ),
]

_PAN_CANDIDATE = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def luhn_valid(digits: str) -> bool:
    """Return True if ``digits`` (numeric characters only) passes the Luhn checksum."""
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def mask_pan(pan: str) -> str:
    """Mask a PAN to the PCI-permitted form: first 6 and last 4 digits visible."""
    digits = re.sub(r"\D", "", pan)
    return f"{digits[:6]}{'*' * (len(digits) - 10)}{digits[-4:]}"


def find_pans(text: str) -> list[str]:
    """Return the *masked* PANs found in ``text``. Full PANs are never returned."""
    found: list[str] = []
    for match in _PAN_CANDIDATE.finditer(text):
        digits = re.sub(r"\D", "", match.group())
        if 13 <= len(digits) <= 19 and luhn_valid(digits):
            found.append(mask_pan(digits))
    return found


def redact(text: str) -> str:
    """Remove secrets and card numbers from free text."""
    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)
    return _PAN_CANDIDATE.sub(
        lambda m: mask_pan(m.group()) if luhn_valid(re.sub(r"\D", "", m.group())) else m.group(),
        text,
    )


def fingerprint(secret: str) -> str:
    """Stable, non-reversible identifier for a secret (for example, a token) so it can be correlated safely."""
    return "sha256:" + hashlib.sha256(secret.encode()).hexdigest()[:16]

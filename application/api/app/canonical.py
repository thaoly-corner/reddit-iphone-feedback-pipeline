"""
Canonicalisation of entity labels produced by the Silver regex extractor.

The upstream extractor keeps the raw matched string (e.g. "iPhone 13Pro", "İphone 13",
"iPhone16 Promax") and also matches non-existent products ("iPhone 3 Pro", "iOS 24.5").
Until the Silver layer is re-run with a fixed extractor, the API folds variants together
here. When upstream is fixed every function below becomes an identity mapping.
"""
from __future__ import annotations

import re
import unicodedata

OTHER_MODEL = "Other / Unspecified"
OTHER_IOS = "iOS Unspecified"
NON_DEFECT = "Non-Defect / General Inquiry"

_VALID_NUMBERS = {4, 5, 6, 7, 8, 11, 12, 13, 14, 15, 16, 17}
_SUFFIX = {"promax": " Pro Max", "pro": " Pro", "plus": " Plus", "mini": " Mini", "air": " Air", None: ""}
_MODEL_RE = re.compile(r"iphone(\d{1,2}|xr|xs|x|se)(promax|pro|plus|mini|air)?")
_IOS_RE = re.compile(r"ios(\d{1,2})((?:\.\d+)*)(beta)?")
_VALID_IOS_MAJOR = {15, 16, 17, 18, 26, 27}


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", "", s.lower())


def canonical_model(raw: str | None) -> str:
    if not raw or raw == OTHER_MODEL:
        return OTHER_MODEL
    m = _MODEL_RE.fullmatch(_fold(raw))
    if not m:
        return OTHER_MODEL
    ident, suffix = m.group(1), m.group(2)
    if ident.isdigit():
        n = int(ident)
        if n not in _VALID_NUMBERS:
            return OTHER_MODEL
        base = f"iPhone {n}"
    else:
        base = f"iPhone {ident.upper()}"
    return base + _SUFFIX[suffix]


def model_generation(canon: str) -> str:
    """'iPhone 15 Pro Max' -> 'iPhone 15'; used to group a family."""
    m = re.match(r"(iPhone (?:\d+|XR|XS|X|SE))", canon)
    return m.group(1) if m else OTHER_MODEL


def canonical_ios(raw: str | None) -> str:
    if not raw or raw == OTHER_IOS:
        return OTHER_IOS
    m = _IOS_RE.fullmatch(_fold(raw))
    if not m:
        return OTHER_IOS
    major = int(m.group(1))
    if major not in _VALID_IOS_MAJOR:
        return OTHER_IOS
    minor = m.group(2) or ""
    beta = " Beta" if m.group(3) else ""
    return f"iOS {major}{minor}{beta}"


def ios_major(canon: str) -> str:
    m = re.match(r"iOS (\d+)", canon)
    return f"iOS {m.group(1)}" if m else OTHER_IOS


def model_sort_key(name: str) -> tuple:
    """Newest generation first, then base < Plus/Mini/Air < Pro < Pro Max."""
    if name == OTHER_MODEL:
        return (999, 0, name)
    m = re.match(r"iPhone (\d+|XR|XS|X|SE)(.*)", name)
    if not m:
        return (998, 0, name)
    ident, rest = m.groups()
    gen = int(ident) if ident.isdigit() else {"X": 10, "XR": 10, "XS": 10, "SE": 9}[ident]
    tier = {"": 0, " Mini": 1, " Plus": 1, " Air": 1, " Pro": 2, " Pro Max": 3}.get(rest, 4)
    return (-gen, tier, name)

"""Small text helpers: HTML stripping, tokenizing, TF-IDF-free cosine similarity."""
from __future__ import annotations

import math
import re
from collections import Counter

from bs4 import BeautifulSoup

_STOP = set("""
a an and are as at be by for from has have in is it its of on or that the to was were will with
you your we our us they their this these those who whom which what when where why how not no
all any can do does done if into more most other some such than then there very just also
about over under while within without across per via etc job role team work working company
""".split())

_TOKEN = re.compile(r"[a-z0-9][a-z0-9+#.\-]*[a-z0-9+#]|[a-z0-9]")


def html_to_text(html: str) -> str:
    if not html:
        return ""
    if "<" not in html:
        return html
    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)


def tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 1]


def cosine(a: str, b: str) -> float:
    """Cosine similarity of log-scaled term-frequency vectors (0..1)."""
    ca, cb = Counter(tokens(a)), Counter(tokens(b))
    if not ca or not cb:
        return 0.0
    wa = {t: 1 + math.log(n) for t, n in ca.items()}
    wb = {t: 1 + math.log(n) for t, n in cb.items()}
    dot = sum(wa[t] * wb[t] for t in wa.keys() & wb.keys())
    na = math.sqrt(sum(v * v for v in wa.values()))
    nb = math.sqrt(sum(v * v for v in wb.values()))
    return dot / (na * nb)


def phrase_in(phrase: str, text_lower: str) -> bool:
    """Whole-word/phrase match that tolerates symbols like c#, c++, .net."""
    p = re.escape(phrase.lower().strip())
    return re.search(rf"(?<![a-z0-9]){p}(?![a-z0-9])", text_lower) is not None

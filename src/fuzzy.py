"""Lax matching for the tree's search.

Every word of the query has to turn up somewhere in a tag's path (its
resource and folders count), but loosely: as part of a word ("cardio" finds
Cardiology), with a different ending ("developmental" finds Development), with
a typo ("devlopment", "pyschiatry"), or as a common abbreviation ("msk" finds
Musculoskeletal, "peds" Pediatrics, and back). Little words like "and" and
"of" are skipped. It errs towards more matches: a few extra rows are easier to
skip than a missing one is to notice.
"""

from __future__ import annotations

import re
from functools import lru_cache

_SPLIT = re.compile(r"[\s_:/\-(),.;]+")

STOPWORDS = frozenset({"a", "an", "and", "the", "of", "in", "on", "to", "for", "with", "or", "by"})

# Longest first; a stem keeps at least four letters.
_SUFFIXES = ("ations", "ation", "ments", "ment", "ities", "ity", "ically", "ical", "ally", "ies",
             "ing", "es", "al", "ed", "ic", "s", "y")

# Abbreviations that aren't just the start of the word (those already match).
ALIASES: dict[str, tuple[str, ...]] = {
    "msk": ("musculoskeletal",),
    "gi": ("gastrointestinal", "gastroenterolog"),
    "peds": ("pediatric", "paediatric"),
    "obgyn": ("obstetric", "gynecolog"),
    "ob": ("obstetric",),
    "gyn": ("gynecolog", "gynaecolog"),
    "heme": ("hematolog", "haematolog"),
    "onc": ("oncolog",),
    "cards": ("cardiolog", "cardiovascular", "cardiac"),
    "cv": ("cardiovascular",),
    "renal": ("nephrolog", "kidney"),
    "pulm": ("pulmonar", "pulmonolog", "respirat"),
    "ent": ("otolaryngolog",),
    "id": ("infectious",),
    "htn": ("hypertension",),
    "dm": ("diabetes",),
    "mi": ("infarction",),
    "biostats": ("biostatistic",),
    "epi": ("epidemiolog",),
    "derm": ("dermatolog", "skin"),
    "neuro": ("neurolog", "nervous"),
    "repro": ("reproduct",),
    "endo": ("endocrin",),
    "immuno": ("immunolog", "immune"),
    "micro": ("microbiolog",),
    "pharm": ("pharmacolog",),
    "biochem": ("biochemistr",),
    "path": ("patholog",),
    "psych": ("psychiatr", "psycholog"),
}


def tokens(key: str) -> list[str]:
    """The words of a tag path, without # and ^ markers."""
    return [t.lstrip("#^") for t in _SPLIT.split(key.lower()) if t.lstrip("#^")]


def query_words(text: str) -> list[str]:
    words = [w for w in tokens(text) if w]
    return [w for w in words if w not in STOPWORDS] or words


def stem(word: str) -> str | None:
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return None


def typos_allowed(word: str) -> int:
    return 0 if len(word) < 5 else 1 if len(word) < 9 else 2


def within(a: str, b: str, k: int) -> bool:
    """Levenshtein distance between a and b is at most k (with adjacent
    swaps counting as one, so "pyschiatry" is one off "psychiatry")."""
    if abs(len(a) - len(b)) > k:
        return False
    prev2: list[int] | None = None
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = a[i - 1] != b[j - 1]
            v = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if prev2 is not None and i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                v = min(v, prev2[j - 2] + 1)
            cur[j] = v
        if min(cur) > k:
            return False
        prev2, prev = prev, cur
    return prev[-1] <= k


def close(word: str, token: str) -> bool:
    """A typo of the token, or of how it starts (for a word still being typed)."""
    k = typos_allowed(word)
    if not k or len(token) < len(word) - k:
        return False
    # Typos rarely hit the first letter; checking it keeps this fast.
    if token[0] != word[0]:
        return False
    if within(word, token, k):
        return True
    n = len(word)
    return any(within(word, token[:m], k) for m in (n - 1, n, n + 1) if 0 < m < len(token))


def word_hits(word: str, vocabulary: frozenset[str]) -> frozenset[str]:
    """Every token in the vocabulary that the query word matches."""
    alts = {word, *ALIASES.get(word, ())}
    st = stem(word)
    exact = {abbr for abbr, longs in ALIASES.items()
             if any(word.startswith(e) or (len(word) >= 5 and e.startswith(word)) for e in longs)}
    hits = set()
    for t in vocabulary:
        if (any(a in t for a in alts)
                or (st is not None and st in t)
                or (len(t) >= 5 and t in word)
                or t in exact
                or close(word, t)):
            hits.add(t)
    return frozenset(hits)


class Vocabulary:
    """Tokens per tag, built once per tag index."""

    def __init__(self, keys) -> None:
        self.by_key: dict[str, frozenset[str]] = {k: frozenset(tokens(k)) for k in keys}
        self.words: frozenset[str] = frozenset().union(*self.by_key.values()) if self.by_key else frozenset()
        self._hits = lru_cache(maxsize=256)(lambda w: word_hits(w, self.words))

    def hits(self, word: str) -> frozenset[str]:
        return self._hits(word)


def vocabulary(index) -> Vocabulary:
    """The index's Vocabulary, made the first time it's searched."""
    vocab = getattr(index, "_vocabulary", None)
    if vocab is None:
        vocab = Vocabulary(index.names)
        index._vocabulary = vocab
    return vocab


class Query:
    def __init__(self, text: str, index) -> None:
        self.vocab = vocabulary(index)
        self.words = query_words(text)
        self.hits = [self.vocab.hits(w) for w in self.words]

    def matches(self, key: str) -> bool:
        have = self.vocab.by_key.get(key)
        if have is None:
            return False
        return all(not h.isdisjoint(have) for h in self.hits)

    def terms(self, shown: list[str]) -> list[str]:
        """What to highlight in the rows shown: the query's words, plus whole
        tokens matched some other way (a typo, another ending, an
        abbreviation), as long as they're in those rows."""
        seen: set[str] = set()
        for key in shown:
            seen |= self.vocab.by_key.get(key, frozenset())
        out = list(self.words)
        for word, hits in zip(self.words, self.hits):
            out += sorted(t for t in hits & seen if word not in t)
        return list(dict.fromkeys(out))

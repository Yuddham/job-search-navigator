import re
from collections import Counter

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "for", "to", "of",
    "in", "on", "at", "by", "with", "from", "as", "is", "are", "was", "were", "be",
    "been", "being", "this", "that", "these", "those", "it", "its", "we", "you",
    "your", "our", "will", "would", "should", "can", "could", "may", "might",
    "must", "shall", "into", "about", "over", "under", "than", "so", "not",
    "no", "yes", "have", "has", "had", "do", "does", "did", "their", "they",
    "them", "he", "she", "his", "her", "i", "us", "who", "which", "what",
    "responsibilities", "requirements", "requirement", "responsibility",
    "apply", "please", "job", "role", "position", "candidate", "candidates",
    "etc", "including", "include", "includes", "years", "year", "experience",
}

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+.#]*")


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug or "item"


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    tokens = [t.lower() for t in _TOKEN_RE.findall(text)]
    return [t for t in tokens if len(t) > 1 and t not in STOPWORDS]


def extract_bigrams(tokens: list[str]) -> list[str]:
    return [f"{a} {b}" for a, b in zip(tokens, tokens[1:])]


def keyword_frequencies(text: str, include_bigrams: bool = True) -> Counter:
    tokens = tokenize(text)
    counts = Counter(tokens)
    if include_bigrams:
        counts.update(extract_bigrams(tokens))
    return counts

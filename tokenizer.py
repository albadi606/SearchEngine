"""
Tokenizer
=========
Breaks raw text into searchable tokens (words).

Pipeline:
    Raw Text → Lowercase → Split → Remove stop words → Stem → Tokens

Improvements:
- Better stop word list (catches Wikipedia junk like "oldid", "talk")
- Improved stemmer (avoids ugly stems like "informa" or "includ")
- Preserves meaningful acronyms (AI, ML, TCP, etc.)
"""

import re
import logging
from collections import Counter
from typing import NamedTuple

logger = logging.getLogger(__name__)


# ─── Stop Words ──────────────────────────────────────────────────────
STOP_WORDS = frozenset({
    # Articles & determiners
    "a", "an", "the", "this", "that", "these", "those",
    # Pronouns
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves",
    "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself", "she", "her", "hers", "herself",
    "it", "its", "itself", "they", "them", "their", "theirs", "themselves",
    "what", "which", "who", "whom",
    # Prepositions
    "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "up", "about", "into", "through", "during", "before", "after",
    "above", "below", "between", "under", "over",
    # Conjunctions
    "and", "but", "or", "nor", "not", "so", "yet", "both", "either",
    "neither", "each", "every", "all", "any", "few", "more", "most",
    # Verbs (common)
    "is", "am", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "having", "do", "does", "did", "doing",
    "will", "would", "shall", "should", "may", "might", "must",
    "can", "could",
    # Other common
    "no", "than", "too", "very", "just", "also", "now", "here",
    "there", "when", "where", "why", "how", "if", "then", "else",
    "once", "only", "own", "same", "such", "because", "as", "until",
    "while", "some", "other", "many", "much", "even", "still",
    "new", "old", "one", "two", "first", "last", "used", "using",
    "make", "made", "like", "well", "get", "got", "set",
    # Wikipedia-specific noise
    "http", "https", "www", "com", "org", "html", "php", "asp",
    "wikipedia", "retrieved", "archived", "isbn", "doi", "cite",
    "ref", "edit", "external", "links", "references", "also",
    "see", "page", "article", "contents", "main", "talk",
    "portal", "category", "categories", "disambiguation",
    "redirect", "template", "templates", "special", "file",
    "upload", "view", "source", "history", "action",
    "oldid", "title", "help", "free", "encyclopedia",
    "jump", "navigation", "sidebar", "hide", "toggle",
    "move", "search", "tools", "personal", "namespace",
    "variant", "views", "read", "log", "contributions",
    "create", "account", "talk", "printable", "version",
    "permanent", "link", "cite", "wikidata", "item",
    "pdf", "download", "export", "print", "languages",
    "watchlist", "changes", "related", "upload", "special",
    "list", "need", "may", "use", "include", "including",
    "original", "since", "year", "years",
    # MDN/docs noise
    "mdn", "docs", "documentation", "note", "warning",
    "example", "examples", "syntax", "return", "value",
    "parameter", "parameters", "type", "method",
    # Common web/generic terms that pollute search
    "hidden", "display", "short", "different", "describe",
    "description", "section", "number", "follow", "general",
    "provide", "require", "support", "service", "available",
    "specific", "develop", "change", "update", "remove",
    "allow", "enable", "process", "access", "control",
    "manage", "result", "report", "document", "detail",
    "status", "format", "feature", "option", "select",
    "contain", "complete", "based", "called", "refer",
    "state", "group", "point", "order", "large", "small",
    "often", "found", "known", "given", "level", "place",
    "world", "part", "model", "check", "block",
    "added", "field", "entry", "store", "built",
    "common", "standard", "design", "several",
    "however", "another", "within", "without",
    "along", "among", "form", "work", "works",
    "single", "multi", "full",
})


class TokenizedResult(NamedTuple):
    tokens: list[str]
    token_count: int
    unique_count: int
    term_frequencies: dict
    token_positions: dict


# ─── Acronyms to preserve (don't filter or stem these) ──────────────
PRESERVE_TERMS = frozenset({
    "ai", "ml", "ip", "tcp", "udp", "dns", "ssl", "tls",
    "vpn", "ssh", "api", "sql", "cpu", "gpu", "ram", "rom",
    "css", "xml", "json", "url", "uri",
    "iot", "ddos", "xss", "csrf", "ids", "ips",
    "rsa", "aes", "sha", "md5", "oman",
})


class Tokenizer:
    """Converts raw text into searchable tokens."""

    def __init__(self, remove_stop_words: bool = True, use_stemming: bool = True):
        self.remove_stop_words = remove_stop_words
        self.use_stemming = use_stemming

    def tokenize(self, text: str) -> TokenizedResult:
        text = text.lower()
        raw_tokens = re.findall(r'[a-z0-9]+(?:-[a-z0-9]+)*', text)

        tokens = []
        token_positions = {}
        position = 0

        for raw_token in raw_tokens:
            # Keep meaningful acronyms even if short
            if raw_token in PRESERVE_TERMS:
                token = raw_token
            else:
                if len(raw_token) < 3:
                    continue
                if raw_token.isdigit() and len(raw_token) < 4:
                    continue
                if self.remove_stop_words and raw_token in STOP_WORDS:
                    continue

                if self.use_stemming:
                    token = self._stem(raw_token)
                else:
                    token = raw_token

                if len(token) < 3:
                    continue

            tokens.append(token)
            if token not in token_positions:
                token_positions[token] = []
            token_positions[token].append(position)
            position += 1

        term_frequencies = dict(Counter(tokens))

        return TokenizedResult(
            tokens=tokens,
            token_count=len(tokens),
            unique_count=len(term_frequencies),
            term_frequencies=term_frequencies,
            token_positions=token_positions,
        )

    def tokenize_query(self, query: str) -> list[str]:
        """Tokenize a search query (same pipeline as documents)."""
        result = self.tokenize(query)
        return result.tokens

    # ─── Improved Stemmer ────────────────────────────────────────

    def _stem(self, word: str) -> str:
        """
        Simplified stemming with better suffix handling.
        Avoids ugly stems like "informa" or "includ".
        """
        if len(word) <= 4:
            return word

        # Step 1: Plural forms
        if word.endswith("ies") and len(word) > 5:
            word = word[:-3] + "y"
        elif word.endswith("sses"):
            word = word[:-2]
        elif word.endswith("ves") and len(word) > 5:
            word = word[:-3] + "f"
        elif word.endswith("s") and not word.endswith(("ss", "us", "is")) and len(word) > 4:
            word = word[:-1]

        # Step 2: Past tense / progressive
        if word.endswith("ied") and len(word) > 5:
            word = word[:-3] + "y"
        elif word.endswith("ing") and len(word) > 6:
            stem = word[:-3]
            if len(stem) > 2 and stem[-1] == stem[-2] and stem[-1] not in "lsz":
                word = stem[:-1]
            else:
                word = stem
        elif word.endswith("ed") and len(word) > 5:
            stem = word[:-2]
            if len(stem) > 2 and stem[-1] == stem[-2] and stem[-1] not in "lsz":
                word = stem[:-1]
            else:
                word = stem

        # Step 3: Common suffixes (only if result stays long enough)
        if word.endswith("ation") and len(word) > 7:
            word = word[:-5] + "ate"
        elif word.endswith("ional") and len(word) > 7:
            word = word[:-2]
        elif word.endswith("tion") and len(word) > 7:
            word = word[:-4]
        elif word.endswith("sion") and len(word) > 7:
            word = word[:-4]
        elif word.endswith("ly") and len(word) > 5:
            word = word[:-2]
        elif word.endswith("er") and len(word) > 5 and not word.endswith(("ber", "ter", "der", "ver", "ger", "ner", "per")):
            word = word[:-2]

        return word


def tokenize(text: str) -> TokenizedResult:
    return Tokenizer().tokenize(text)


if __name__ == "__main__":
    t = Tokenizer()
    test_words = [
        "information", "including", "original", "computer",
        "searching", "cybersecurity", "running", "machines",
        "learning", "network", "security", "attacks",
    ]
    print("Stemming tests:")
    for word in test_words:
        result = t._stem(word)
        print(f"  {word:<20} → {result}")
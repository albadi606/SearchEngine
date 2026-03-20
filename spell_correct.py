"""
Spell Corrector & Autocomplete (Norvig Algorithm)
===================================================
Based on Peter Norvig's spell corrector: https://norvig.com/spell-correct.html

Key insight — instead of comparing the misspelled word against every word
in the vocabulary (slow), we:
1. Generate ALL possible 1-edit variations of the misspelled word (~500)
2. Check which of those variations exist in our vocabulary (instant lookup)
3. Pick the one with the highest document frequency

This is O(word_length * alphabet_size) instead of O(vocabulary_size).
For a 10-char word: ~500 lookups vs 10,000+ Levenshtein calculations.

Speed: ~2ms instead of ~2000ms. That's 1000x faster.
"""

import sqlite3
import logging
from typing import Optional

logger = logging.getLogger(__name__)

ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


class SpellCorrector:
    """
    Fast spelling correction using Norvig's edit-distance algorithm.
    
    Instead of checking every vocabulary word (O(n) × O(m²)),
    generates all possible edits and checks if they exist (O(1) per check).
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._vocab: set[str] = set()          # All known terms (for O(1) lookup)
        self._word_freq: dict[str, int] = {}   # term → document frequency
        self._loaded = False

    def _ensure_loaded(self):
        if not self._loaded:
            self.load_vocabulary()

    def load_vocabulary(self):
        """Load all indexed terms into a set for O(1) membership testing."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                """SELECT token, COUNT(DISTINCT page_id) as doc_freq
                   FROM inverted_index
                   GROUP BY token
                   HAVING doc_freq >= 2"""
            )

            self._vocab = set()
            self._word_freq = {}

            for row in cursor:
                token, freq = row[0], row[1]
                self._vocab.add(token)
                self._word_freq[token] = freq

            conn.close()
            self._loaded = True
            logger.info(f"Spell corrector loaded {len(self._vocab)} terms")
        except Exception as e:
            logger.warning(f"Failed to load spell vocabulary: {e}")
            self._loaded = True

    def correct(self, query: str) -> Optional[str]:
        """
        Suggest a corrected version of the query.
        Returns None if query looks correct.
        
        Example:
            correct("machne lerning") → "machine learning"
            correct("cybersecurity") → None (already correct)
        """
        self._ensure_loaded()

        if not self._vocab:
            return None

        words = query.lower().split()
        corrected_words = []
        any_corrected = False

        for word in words:
            if len(word) < 3:
                corrected_words.append(word)
                continue

            # Word already in vocabulary — no correction needed
            if word in self._vocab:
                corrected_words.append(word)
                continue

            # Find best correction using Norvig's algorithm
            best = self._find_correction(word)
            if best and best != word:
                corrected_words.append(best)
                any_corrected = True
            else:
                corrected_words.append(word)

        if any_corrected:
            return " ".join(corrected_words)
        return None

    def _find_correction(self, word: str) -> Optional[str]:
        """
        Find the best correction for a misspelled word.
        
        Priority:
        1. Edit distance 1 candidates (prefer these — closer match)
        2. Edit distance 2 candidates (only if no distance-1 match)
        
        Among candidates at the same distance, pick the one that
        appears in the most documents (higher frequency = more likely correct).
        """
        # Try edit distance 1 first
        candidates_1 = self._known(self._edits1(word))
        if candidates_1:
            return max(candidates_1, key=lambda w: self._word_freq.get(w, 0))

        # Try edit distance 2 (edits of edits)
        candidates_2 = self._known(self._edits2(word))
        if candidates_2:
            return max(candidates_2, key=lambda w: self._word_freq.get(w, 0))

        return None

    def _known(self, words: set[str]) -> set[str]:
        """Filter a set of words to only those that exist in our vocabulary."""
        return words & self._vocab

    def _edits1(self, word: str) -> set[str]:
        """
        Generate ALL strings that are 1 edit away from the word.
        
        Four types of edits:
        - Deletes:    "machne" → "achne", "mchne", "mahne", "macne", "mache", "machn"
        - Transposes: "machne" → "amchne", "mcahne", "mahcne", "macnhe", "machen"
        - Replaces:   "machne" → "aachne", "bachne", ... (each position × 36 chars)
        - Inserts:    "machne" → "amachne", "bmachne", ... (each gap × 36 chars)
        
        For a 6-letter word: ~6+5+216+252 = ~479 candidates
        Each checked against vocabulary in O(1). Total: ~479 O(1) lookups.
        """
        splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]

        deletes    = {L + R[1:]         for L, R in splits if R}
        transposes = {L + R[1] + R[0] + R[2:] for L, R in splits if len(R) > 1}
        replaces   = {L + c + R[1:]     for L, R in splits if R for c in ALPHABET}
        inserts    = {L + c + R         for L, R in splits     for c in ALPHABET}

        return deletes | transposes | replaces | inserts

    def _edits2(self, word: str) -> set[str]:
        """
        Generate all strings that are 2 edits away.
        
        Optimization: for long words (>8 chars), skip edits2 entirely —
        edit distance 1 is almost always sufficient, and edits2 generates
        ~250,000 candidates which is slower in pure Python.
        """
        if len(word) > 8:
            return set()
        return {e2 for e1 in self._edits1(word) for e2 in self._edits1(e1)}


class Autocomplete:
    """Provides real-time search suggestions as the user types."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def suggest(self, prefix: str, limit: int = 7) -> list[dict]:
        prefix = prefix.lower().strip()
        if len(prefix) < 2:
            return []

        conn = sqlite3.connect(self.db_path)

        words = prefix.split()
        if len(words) > 1:
            last_word = words[-1]
            prefix_base = " ".join(words[:-1])
        else:
            last_word = prefix
            prefix_base = ""

        cursor = conn.execute(
            """SELECT token, COUNT(DISTINCT page_id) as doc_count
               FROM inverted_index
               WHERE token LIKE ? || '%'
               GROUP BY token
               HAVING doc_count >= 2
               ORDER BY doc_count DESC
               LIMIT ?""",
            (last_word, limit),
        )

        suggestions = []
        for row in cursor:
            full_suggestion = f"{prefix_base} {row[0]}" if prefix_base else row[0]
            suggestions.append({"term": full_suggestion, "doc_count": row[1]})

        conn.close()
        return suggestions

    def get_popular_searches(self, limit: int = 10) -> list[dict]:
        """
        Get meaningful popular search terms.
        Filters out stemmed junk, short terms, and web noise.
        """
        junk = {
            "index", "hidden", "article", "descrip", "short", "informate",
            "system", "different", "displai", "content", "section",
            "number", "follow", "general", "return", "function",
            "class", "defin", "provid", "requir", "support",
            "servic", "avail", "specif", "develop", "design",
            "chang", "updat", "creat", "remov", "allow",
            "enabl", "applic", "proces", "access", "control",
            "manag", "config", "result", "report", "document",
            "detail", "status", "format", "featur", "option",
            "select", "contain", "complet", "describ", "relat",
            "based", "called", "refer", "state", "group",
            "point", "order", "large", "small", "often",
            "found", "known", "given", "level", "place",
            "world", "parti", "model", "check", "block",
            "added", "field", "exist", "count", "valid",
            "local", "entry", "valu", "store", "built",
        }

        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            """SELECT token, COUNT(DISTINCT page_id) as doc_count
               FROM inverted_index
               WHERE LENGTH(token) >= 5
               GROUP BY token
               ORDER BY doc_count DESC
               LIMIT 150""",
        )

        results = []
        for row in cursor:
            term = row[0]
            if term in junk:
                continue
            if term.isdigit():
                continue
            if term.endswith(("nct", "mpl", "rmat", "ript", "ipt")):
                continue
            results.append({"term": term, "doc_count": row[1]})
            if len(results) >= limit:
                break

        conn.close()
        return results


# ─── Demo ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Show how fast edit generation is
    import time

    word = "machne"
    sc = SpellCorrector.__new__(SpellCorrector)

    start = time.time()
    edits = sc._edits1(word)
    elapsed = (time.time() - start) * 1000

    print(f"Word: '{word}'")
    print(f"Edit distance 1: {len(edits)} candidates generated in {elapsed:.1f}ms")
    print(f"Sample edits: {list(edits)[:10]}")
    print()
    print("Compare: checking 10,000 words with Levenshtein = ~2000ms")
    print(f"         generating {len(edits)} edits + set lookup = ~{elapsed:.1f}ms")
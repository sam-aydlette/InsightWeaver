"""
Labelling a coverage gap: which words the unrouted observations are about.

Split out of :mod:`src.routing.gaps` on 2026-08-31 (backlog task 015) to keep
both files inside the repository's 200-300 line rule. The seam is real:
everything here is a pure function of text and knows nothing about
observations, watches, clusters or the database.

**Why this exists at all.** Near-duplicate clustering catches one story carried
by six outlets. It cannot catch a subject covered by forty *different* stories
over a month, no two of which are near-duplicates -- and that is the shape a
missing sensor usually has. Document frequency over salient words catches it.
Frequency is counted once per document, so one verbose article cannot invent a
theme.

This is a label, not a topic model. It is deliberately the crudest thing that
makes the unrouted set readable, because the decision it feeds -- "is there a
watch missing here?" -- is a human one (backlog task 021), and a cleverer
grouping would mostly be harder to argue with.
"""

from __future__ import annotations

import re
from collections import Counter

__all__ = ["MAX_GAP_TERMS", "gap_terms"]

_WORD = re.compile(r"[0-9A-Za-z][0-9A-Za-z'-]*")

# Words that carry no subject. Deliberately short: the length floor below
# already removes most function words, and a long hand-tuned stoplist is a place
# to accidentally suppress a real subject. Anything not here is reported, and
# whoever reads the file can see the noise for what it is.
_STOPWORDS = frozenset(
    [
        "about",
        "after",
        "again",
        "against",
        "also",
        "among",
        "another",
        "because",
        "been",
        "before",
        "being",
        "between",
        "both",
        "cannot",
        "could",
        "does",
        "doing",
        "done",
        "down",
        "during",
        "each",
        "either",
        "else",
        "even",
        "ever",
        "every",
        "from",
        "further",
        "had",
        "has",
        "have",
        "having",
        "here",
        "how",
        "however",
        "into",
        "itself",
        "just",
        "like",
        "made",
        "make",
        "many",
        "may",
        "might",
        "more",
        "most",
        "much",
        "must",
        "never",
        "new",
        "news",
        "now",
        "only",
        "other",
        "others",
        "our",
        "out",
        "over",
        "own",
        "report",
        "reports",
        "said",
        "same",
        "say",
        "says",
        "see",
        "seen",
        "should",
        "since",
        "some",
        "such",
        "than",
        "that",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "time",
        "today",
        "too",
        "under",
        "until",
        "upon",
        "used",
        "using",
        "very",
        "want",
        "was",
        "way",
        "well",
        "were",
        "what",
        "when",
        "where",
        "which",
        "while",
        "who",
        "whom",
        "why",
        "will",
        "with",
        "within",
        "without",
        "would",
        "year",
        "years",
        "your",
    ]
)

# Four, because "NIST", "CISA", "OMB"... -- three-letter acronyms are the
# shortest thing that can name a subject, and a three-letter floor drags in
# every remaining function word. The stoplist absorbs the four-letter ones that
# survive. A subject named only by a three-letter acronym will show up in the
# near-duplicate clusters instead; it is not lost, only unlabelled.
_MIN_TERM_LENGTH = 4

# How many gap terms to write. The tail is a long list of hapaxes; it is not
# information, it is the corpus.
MAX_GAP_TERMS = 50


def _salient(text: str) -> set[str]:
    """The subject-bearing words of one text, deduplicated within the document."""
    return {
        word
        for token in _WORD.findall(text.lower())
        if len(word := token.strip("'-")) >= _MIN_TERM_LENGTH and word not in _STOPWORDS
    }


def gap_terms(texts: list[str], limit: int = MAX_GAP_TERMS) -> list[tuple[str, int]]:
    """
    Salient words by document frequency, most common first.

    Ties break alphabetically so the report is a deterministic function of the
    corpus rather than of dict insertion order.
    """
    counts: Counter[str] = Counter()
    for text in texts:
        counts.update(_salient(text))
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]

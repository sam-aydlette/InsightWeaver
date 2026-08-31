"""
Near-duplicate detection by MinHash over word shingles.

**What this is for.** Two feeds carry the same wire story with a different
byline, a different photo credit and a different "appeared first on" footer.
Their content hashes differ -- correctly, because the bytes differ -- so
content-addressing cannot group them. Something has to, or the same event is
adjudicated three times and counts as three pieces of evidence for a Watch.
That is the failure this module exists to prevent.

**Why MinHash and not the existing similarity code.**
``src/processors/deduplicator.py`` compares articles pairwise with a word-set
Jaccard computed from scratch on every comparison, inside a time window, at
query time. It is not wrong, but nothing about it is storable: there is no
per-article artefact you can keep and compare later, so the grouping cannot be
recomputed identically after the fact. A MinHash signature *is* that artefact.
It is a fixed-width function of the text alone, written once beside the
observation, and the similarity of two observations is then a comparison of two
short integer vectors -- so a grouping computed today and a grouping computed
after a replay agree by construction.

**The parameters are format, not preference.**
:data:`PERMUTATIONS` and :data:`SHINGLE_SIZE` determine what a stored signature
*means*. Change either and every signature already written becomes
incomparable with every signature written afterwards, silently -- the vectors
are still the same width, the numbers are still numbers, and the similarities
are just wrong. So they are module constants with this warning attached, not
configuration. The *threshold* is the tunable one, because it is applied at
comparison time and changing it re-groups the same stored signatures
consistently; it lives in ``settings.near_duplicate_threshold``.

The permutation coefficients are derived from BLAKE2b of the permutation index
rather than from ``random.Random(seed)``. Both are deterministic today, but only
one of them is deterministic because of a documented property of a hash function
rather than a documented property of an implementation's PRNG.

Added 2026-08-31 for backlog task 014.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence

from .base import normalize_for_hash

__all__ = [
    "PERMUTATIONS",
    "SHINGLE_SIZE",
    "group_near_duplicates",
    "shingles",
    "signature",
    "similarity",
]

# Words per shingle. Five is long enough that two documents sharing a stock
# phrase ("the department said in a statement") do not look related on that
# alone, and short enough that a rewritten sentence in an otherwise identical
# document still leaves most shingles intact.
SHINGLE_SIZE = 5

# Signature width. 128 puts the standard error of the Jaccard estimate near
# 1/sqrt(128) ~= 0.09, which is far below the margin between the two cases this
# has to separate (see tests/sources/test_minhash.py: a real near-duplicate pair
# lands around 0.9, a real distinct pair around 0.0).
PERMUTATIONS = 128

# 2**61 - 1, a Mersenne prime: the modulus for the (a*x + b) mod p permutations.
_MODULUS = (1 << 61) - 1


def _coefficients(index: int) -> tuple[int, int]:
    """The (a, b) pair for permutation ``index``, derived from its number."""
    digest = hashlib.blake2b(f"insightweaver/minhash/{index}".encode(), digest_size=16).digest()
    a = int.from_bytes(digest[:8], "big") % (_MODULUS - 1) + 1
    b = int.from_bytes(digest[8:], "big") % _MODULUS
    return a, b


_COEFFICIENTS: tuple[tuple[int, int], ...] = tuple(_coefficients(i) for i in range(PERMUTATIONS))


def shingles(text: str) -> set[int]:
    """
    The hashed word-shingles of ``text``.

    Normalization is :func:`src.sources.base.normalize_for_hash` -- the same
    function the content hash uses -- so "the same text" means one thing in this
    repository rather than two.

    A document shorter than :data:`SHINGLE_SIZE` words yields one shingle for
    the whole document rather than none, so that short items are comparable with
    each other instead of silently matching nothing.
    """
    words = normalize_for_hash(text).split()
    if not words:
        return set()
    if len(words) <= SHINGLE_SIZE:
        grams = [" ".join(words)]
    else:
        grams = [
            " ".join(words[i : i + SHINGLE_SIZE]) for i in range(len(words) - SHINGLE_SIZE + 1)
        ]
    return {
        int.from_bytes(hashlib.blake2b(g.encode("utf-8"), digest_size=8).digest(), "big")
        for g in grams
    }


def signature(text: str) -> tuple[int, ...]:
    """
    The MinHash signature of ``text``: :data:`PERMUTATIONS` integers.

    Empty text has an empty signature rather than a signature of sentinels.
    An empty signature is 0.0-similar to everything including another empty one,
    which is the honest answer -- two items we know nothing about are not
    evidence of the same event.
    """
    hashed = shingles(text)
    if not hashed:
        return ()
    return tuple(min((a * h + b) % _MODULUS for h in hashed) for a, b in _COEFFICIENTS)


def similarity(left: Sequence[int], right: Sequence[int]) -> float:
    """
    Estimated Jaccard similarity of two signatures: the fraction that agree.

    Signatures of different non-zero widths are a programming error, not a
    similarity of zero -- it means signatures written under two different
    :data:`PERMUTATIONS` values are being compared, which is the silent
    corruption the module docstring warns about, so it raises.
    """
    if not left or not right:
        return 0.0
    if len(left) != len(right):
        raise ValueError(
            f"cannot compare MinHash signatures of width {len(left)} and {len(right)}: "
            f"they were computed under different PERMUTATIONS settings and their "
            f"similarity would be meaningless"
        )
    return sum(1 for a, b in zip(left, right, strict=True) if a == b) / len(left)


def group_near_duplicates(
    signatures: Mapping[str, Sequence[int]],
    threshold: float,
) -> list[list[str]]:
    """
    Group keys whose signatures are at least ``threshold`` similar.

    Returns every group, including singletons, sorted by key and then by first
    key, so the output is a deterministic function of the input -- a grouping
    that depended on dict order would break the replay guarantee it supports.

    Transitive by union-find: if A is near B and B is near C then all three land
    in one group even if A and C fall just under the threshold. That is the
    behaviour wanted for a wire story picked up in a chain of rewrites.

    Pairwise, so O(n^2) comparisons. That is deliberate at this size -- a
    day of ingestion is a few hundred observations and the comparison is 128
    integer equalities. An LSH index is the answer if this is ever pointed at
    the whole corpus, and it would change the grouping only by making it
    approximate.
    """
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(f"near-duplicate threshold must be in [0, 1], got {threshold}")

    keys = sorted(signatures)
    parent = {key: key for key in keys}

    def find(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(a: str, b: str) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[max(root_a, root_b)] = min(root_a, root_b)

    for i, left in enumerate(keys):
        for right in keys[i + 1 :]:
            if similarity(signatures[left], signatures[right]) >= threshold:
                union(left, right)

    groups: dict[str, list[str]] = {}
    for key in keys:
        groups.setdefault(find(key), []).append(key)
    return sorted((sorted(members) for members in groups.values()), key=lambda g: g[0])

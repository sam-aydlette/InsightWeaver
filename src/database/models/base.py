"""
The declarative base and the exceptions the guards raise.

Split out of the single ``models.py`` on 2026-09-22 (backlog task 030) when
that file passed 480 lines; one module per table family, nothing about any
table changed.
"""

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class ObservationIsImmutable(RuntimeError):
    """
    Raised when anything tries to change a stored observation.

    Not a warning and not a silently-ignored write. An observation is
    content-addressed, so its hash is a claim that the payload beside it is the
    payload that produced the hash. A single successful UPDATE turns every
    replay run afterwards into a comparison against a corpus that no longer
    matches its own identities, and nothing would say so.
    """


class LedgerIsAppendOnly(RuntimeError):
    """
    Raised when anything tries to change or delete a belief ledger row.

    Belief history is the calibration record the system exists to accumulate;
    a row that can be edited is a history that can be rewritten. Added
    2026-09-22 (backlog task 030).
    """

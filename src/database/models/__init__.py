"""
Database models, one module per table family (split 2026-09-22, backlog task 030,
when the single file passed 480 lines; nothing about any table changed):

* ``sources``: the feeds we read (``rss_feeds``) and the legacy ``articles``.
* ``observations``: the content-addressed corpus and the ``evidence`` derived
  from it.
* ``watches``: the operator's pre-registered claims and their belief ledger
  (``watch_beliefs``).
* ``monitor``: Tier 1's ``routes`` and Tier 2's ``adjudications`` ledger.

Everything else was deleted by backlog task 012 along with the briefing product
that owned it -- syntheses, context snapshots, provenance, topic clusters,
narrative frames, questions, predictions, decisions and beats. The tables are
dropped by ``src.database.migrations.drop_briefing_tables``; the models are
removed here so that ``Base.metadata.create_all()`` cannot quietly recreate a
concept the rewrite removed.

``watches`` is the first table of the rewrite, added 2026-08-31 by backlog task
013. Its CHECK constraints are not decoration -- see the class docstring.

``observations`` and ``evidence`` are the second and third, added 2026-08-31 by
backlog task 014.

**The rule for ``articles`` versus ``observations``, decided by task 014 and
written here because this is the file both of them live in.** They coexist, with
one direction of authority and one writer:

* ``articles`` is the *legacy ingestion table*. It holds the 55,249 rows written
  before the rewrite and it stays the row shape the pre-rewrite code reads. It
  is not deleted and not migrated.
* ``observations`` is *authoritative for everything the rewrite builds*. A tier
  added from task 014 onwards reads ``observations`` and never ``articles``.
* Exactly one code path writes an observation:
  ``src.sources.observation.store_observation``, called from
  ``src.sources.store.store_items``, which is the store path every adapter in
  ``src/sources/`` already goes through. Each new article gets an observation in
  the same transaction, and ``observations.article_id`` links the two.
* The 55,249 pre-existing rows have no observation, and neither does anything
  the legacy ``src/rss/fetcher.py`` path writes directly. That is a known,
  bounded gap, not an ambiguity: the content hash is a pure function of columns
  those rows already carry, so a backfill is mechanical and is deliberately left
  to its own task rather than run inside this one.

The one thing that was not acceptable was two corpora with no stated rule. The
rule is: **new tiers read observations; articles is the pre-rewrite archive.**

``routes`` is Tier 1's output, added 2026-09-22 by backlog task 028: which
observations are candidates for which watch. It is derived and rebuildable,
which is why it may be deleted by ``route --rebuild`` and ``evidence`` may not
be deleted by anything but ``replay --commit``.

``adjudications`` is Tier 2's run ledger, added 2026-09-22 by backlog task 029:
every pair the model was asked about, whatever it answered, with the tokens it
cost. ``evidence`` keeps holding the verdicts; the ledger is why a pair is not
asked twice and where a failed call is recorded rather than retried.

``watch_beliefs`` is the belief ledger, added 2026-09-22 by backlog task 030,
append-only and written only from the watch file at sync and by the operator;
the same task gave ``watches`` its lifecycle columns (retired, resolved) so a
watch is never deleted once history hangs off it.

``briefs`` records each brief rendered, added 2026-09-22 by backlog task 031;
the next brief's default window starts where the last one before today ended.
"""

from .base import Base, LedgerIsAppendOnly, ObservationIsImmutable
from .monitor import Adjudication, BriefRun, Route
from .observations import Evidence, Observation
from .sources import Article, RSSFeed
from .watches import Watch, WatchBelief

__all__ = [
    "Adjudication",
    "Article",
    "Base",
    "BriefRun",
    "Evidence",
    "LedgerIsAppendOnly",
    "Observation",
    "ObservationIsImmutable",
    "RSSFeed",
    "Route",
    "Watch",
    "WatchBelief",
]

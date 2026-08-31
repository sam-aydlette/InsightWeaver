# Make Observations immutable and content-addressed, and Evidence derived, so the corpus can be replayed against a changed prompt and the diff inspected.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
SIZE: medium
ACCEPTANCE: `make check` passes, plus: an `observations` table stores normalized adapter output keyed by content hash, with the raw payload retained verbatim and never mutated after write; a write attempting to change a stored observation **fails loudly** rather than updating; adapters in `src/sources/` emit Observations through one path; near-duplicate detection by MinHash groups items that differ only in boilerplate, with the threshold recorded in config and a test showing two real near-duplicates grouping and two distinct items not; an `evidence` table links (observation, watch) with direction and magnitude, and every row records the prompt version that produced it; `insightweaver replay --prompt-version X` rebuilds Evidence from Observations alone and **prints a diff against the stored Evidence without writing**, with `--commit` required to persist; and a test proves replay is deterministic given the same prompt version.
OUT OF SCOPE: The adjudication prompt itself and its content -- this task builds the replay harness, task 016 writes what runs inside it. Routing. State transitions. Deleting or migrating the 55,249 existing `articles` rows; decide whether Observations supersede, wrap, or coexist with that table and record the reasoning, but do not perform a destructive migration in this task. Any change to `SOURCES.md`'s recorded-basis rule.
LANDMINES: **This invariant is the one that makes a stochastic component testable, and it is worthless if replay is not byte-reproducible.** A prompt version that is not recorded per row, or an adapter that normalizes with a timestamp in the payload, silently breaks it -- and it breaks in the direction of looking fine. **`src/sources/base.py` already has `content_hash()` and `ARTICLE_FIELDS`** from task 005; extend that seam rather than introducing a second hashing scheme. **The `articles` table is 55,249 rows and is what every existing query reads**; a parallel `observations` table that only new adapters write leaves the system with two corpora and no rule for which is authoritative. State the rule in the PR. Content-addressing means the hash **is** the identity: an adapter that includes a fetch timestamp or a session ID in the hashed payload will store the same article repeatedly and the dedup will look broken when the hashing is what is wrong. Test that first. `main` is protected -- open a PR.
---
Written 2026-08-31.

Invariant 3 is the one that makes the LLM tier reviewable. Everything downstream of adjudication is
deterministic and unit-testable; adjudication itself is not, and the only way to test it is to hold
the inputs fixed and inspect what a prompt change does to the outputs. That requires Observations
to be immutable and Evidence to be a pure function of (Observations, prompt version).

**Why `--commit` is required rather than default.** A replay that writes by default makes the
before-state unrecoverable at exactly the moment you wanted to compare against it. Printing the
diff and requiring an explicit commit costs one flag and preserves the thing the invariant exists
to provide.

**The open question this task must answer, not assume.** The repository has 55,249 `articles` rows
written by the RSS path and the Federal Register adapter. Observations may supersede that table,
wrap it, or run alongside it during a transition. Each has a real cost -- superseding means a
migration of 55k rows, wrapping means two shapes for one concept, coexisting means a rule nobody
will remember in six months. The implementer picks and writes down why; what is not acceptable is
two corpora with no stated rule, because the audit found exactly that pattern already exists in
this repository between `migrations/` and `src/database/migrations/`.

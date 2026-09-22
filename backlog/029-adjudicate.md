# Adjudicate routed pairs with one structured model call each, recording every outcome including failure, and make replay read what adjudication read.
REPO: InsightWeaver
STATUS: DONE              # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
SIZE: medium
PLAN: docs/PLAN.md (section 4; section 5, task 029; supersedes backlog/016 as rescoped)
ACCEPTANCE: `make check` passes, plus: a `ClaudeAdjudicator` registered under prompt version `claude-v1` implements the existing `Adjudicator` protocol and is the **only** module that constructs a `ClaudeClient`, asserted against the tree; its response is requested as structured output (`output_config.format`, a JSON schema derived from a pydantic verdict model) and validated on receipt; a response that fails validation, a refusal, or an API error is recorded in an `adjudications` row with `outcome = 'failed'` and the error text, **never retried and never coerced into a verdict**, tested with a stub that returns malformed JSON; every routed pair the model is asked about gets exactly one `adjudications` row per prompt version (`evidence`, `none` or `failed`), so `insightweaver adjudicate` run twice sends nothing the second time; each row carries the audit id and the input and output tokens, and the command prints the run's totals; `adjudicate --dry-run` prints the exact system and user text for the first N pairs and a character-based estimate labelled as an estimate, without constructing a client; `rebuild` in `src/evidence/replay.py` iterates **routed pairs** rather than the full observation x watch product, and the replay stubs route their fixture corpus through the real router so the existing replay tests keep their meaning; and the observation text sent is capped, with the cap and whether it applied recorded in the audit entry.
OUT OF SCOPE: Belief updates from evidence (none, by decision of 2026-09-22). The brief. Batching, prompt caching, or a second prompt version; get one-call-per-pair right first. Any use of `parse_claude_json`. Cost in dollars: tokens are recorded; a price table goes stale silently and the operator can multiply.
LANDMINES: **A retry that produces a different answer to the same input is what breaks replay**, so a failed call is recorded and left. **Replay against a stochastic adjudicator is not expected to be empty.** The harness's `commit` refuses when the same version disagrees with its own stored rows; for `claude-v1` that refusal is the measurement of prompt stability, not a bug, and the task file for the first replay must say what rate was observed. **The adjudicator must see only what Tier 1 routed.** The protocol passes a watch list; `adjudicate` passes the routed subset per observation and `rebuild` must do the same, or a replay silently costs more and judges pairs adjudication never saw. **`_response_text` raises on refusal and on a missing text block**; catch those at the adjudicator boundary and record them as failures, do not let one refusal abort the run. **Structured output is a request parameter, not a parsing convention** (task 016's landmine); a schema in the prompt text is not the same thing. **The SDK is 1.x**: `output_config` is a named parameter and `messages.parse` exists; do not put the schema in `extra_body`. `main` is protected -- open a PR.
---
Written 2026-09-22.

## The verdict schema

```python
class AdjudicationVerdict(BaseModel):
    is_evidence: bool
    direction: Literal["supports", "contradicts"] | None   # required when is_evidence
    magnitude: float = Field(ge=0.0, le=1.0)                # strength of bearing, not a probability
    satisfies_clause: int | None                             # index into the watch's trigger clauses
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str                                           # one or two sentences, citing the text
```

A verdict with `is_evidence=false` writes an `adjudications` row with `outcome='none'` and no
`evidence` row. A verdict with `is_evidence=true` and no direction is a validation failure.

**As built (2026-09-22):** `direction` is the three-valued enum `supports | contradicts | none` and
`satisfies_clause` is an integer with `-1` for no clause, instead of the nullable fields above. The
structured-output grammar takes a flat enum and an integer; a nullable union would need `anyOf`,
and the flat form keeps the schema the SDK sends identical to the one a reader sees here. The
validator enforces the same rule the nullable form would have. The schema is derived from the
pydantic model at import (`api_schema`), with the range keywords the grammar rejects removed and
their ranges kept in the field descriptions; pydantic enforces the ranges on receipt. The ledger
also keeps `confidence`, `satisfies_clause` and the rationale for every validated verdict, since
`evidence` holds only evidence.

## The prompt, in outline

System: the role (judge one observation against one pre-registered claim), the rules that survive
from the deleted `ANALYSIS_RULES.md` for a single judgement (label what the text says, not what it
implies; default to the weaker reading; do not recommend; do not infer beyond the text; a claim
the observation does not address is not evidence), and the schema semantics above.

User: the watch's claim, its `so_what`, its trigger clauses with indices; then the observation's
source name, published date, title and text (capped).

The prompt is a module constant beside the adjudicator with its version string; changing the text
without changing the version is the mislabelled-corpus failure task 014 was built to prevent, so a
test hashes the prompt constant and pins the hash to the version.

## What the adversarial review found, and what was done

Four independent reviewers read the uncommitted change against this file. Fixed before commit:

- **A missing keychain entry was recorded as a permanent failure on every pending pair**, with no
  call made, and the command exited 0. The client is now built before the first pair and outside
  the recording path; a missing key raises with nothing written. The same rule covers a request
  the API rejects (400, 401, 403, 404): `ModelCallFailed.misconfigured` aborts the run at the pair
  it hit, earlier answers kept.
- **An interrupted run lost every answer it had paid for**: rows were flushed, never committed.
  Each pair commits as it is answered; the pair in flight under Ctrl-C is re-asked, and the
  module docstring says so.
- **The hand-written schema carried `minimum`/`maximum`**, which the grammar rejects, and could
  drift from the model. It is derived from the model with those keywords stripped.
- **A refusal or API error wrote a ledger row with no audit id and zero tokens** although the
  audit log had both. The client's failure is typed and carries them.
- **`max_tokens` of 2000 capped thinking and answer together**; a reply cut off there was recorded
  as a JSON error. It is 16000 now and a `max_tokens` stop is recorded as what it is.
- **Adjudication and replay read different pair sets** (one filtered by expiry, one did not).
  Expiry is Tier 1's gate at routing time; both tiers now read exactly the routed pairs.
- **`adjudicate` after `replay --commit` crashed** on the evidence unique constraint; a pair with
  committed evidence now counts as answered. **`replay` over an unrouted corpus** read as "no
  evidence" and would have deleted the version's rows with `--commit`; it now refuses and names
  the fix. `replay --limit` counts routed observations, so a bounded model replay judges something.
- The truncation test was a tautology; it now checks the sent body. `--limit 0` is refused.
  `satisfies_clause` beyond the watch's clauses is a validation failure. The prompt's stake heading
  was reworded to state the record rather than frame urgency. Docstrings that still cited task 016
  were corrected.

Recorded, not changed: the SDK resends an identical request up to twice on a 429 or 5xx, below the
never-retried rule, and the audit log records the request once. The replay path aborts at the
first failed pair by design (it has no ledger). The tree-grep gate for "only the adjudicator
constructs a client" matches the literal token and is a guard against habit, not an adversary.
`src/database/models.py` is 480 lines and is split in task 030. Live acceptance of the derived
schema is unverified from this machine: the first real run is the test, and if the API rejects the
schema the run stops at the first pair with the API's message and nothing recorded.

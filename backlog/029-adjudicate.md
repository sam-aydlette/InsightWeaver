# Adjudicate routed pairs with one structured model call each, recording every outcome including failure, and make replay read what adjudication read.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
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

# Adjudicate routed (observation, watch) pairs in the single LLM tier, with structured output and a versioned prompt.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
SIZE: medium
ACCEPTANCE: `make check` passes, plus: one prompt, versioned and stored with every Evidence row it produces, runs only on pairs Tier 1 routed; output is structured and validated -- is-evidence, direction, magnitude, satisfies-which-trigger, confidence -- and a response failing validation is **recorded as a failed adjudication rather than silently dropped or retried into a different answer**; the tier is the only place in the codebase that constructs a model request, proved by a test asserting no other module imports the client; `insightweaver adjudicate --dry-run` prints what would be sent and its token estimate without calling; replay from task 014 reproduces Evidence for a given prompt version; and per-run token and cost are recorded, because the repository currently has **no token accounting at all** and a cost-controlled architecture that cannot measure its own cost is asserting the property, not holding it.
OUT OF SCOPE: Belief updates, trigger firing, hysteresis, state transitions -- adjudication reports what an observation *is*, and task 017 decides what it *does*. Batching or Bedrock migration; get the semantics right at one-call-per-pair first and optimise once volume is known. Prompt tuning beyond a first version that passes replay. Multiple prompts or a prompt per watch type.
LANDMINES: **The model has been retired underneath this repository once already.** `claude-sonnet-4-20250514` reached end of life on 2026-06-15 and every synthesis failed for ten weeks while the CLI printed a duration and exited 0, because the exception was caught and logged. Any adjudication path must make an API failure loud at the tier boundary. **The response shape changed too**: `content[0].text` was correct when the model did not think and returns a `ThinkingBlock` now; `src/context/claude_client.py` selects text blocks by type and raises on a refusal -- reuse it, do not reimplement the extraction. **Do not add fallbacks**; `CLAUDE.md` forbids concealing problems behind them, and an adjudication that silently degrades to a default verdict is the worst possible instance -- it writes wrong Evidence that the state machine then acts on. Structured output is a request parameter, not a parsing convention. `main` is protected -- open a PR.
---
Written 2026-08-31.

Invariant 4 puts exactly one stochastic component in the system. That is what makes the other four
tiers unit-testable, and it means this tier's contract has to be narrow enough to validate: a
verdict object, not prose.

**Why a failed adjudication is recorded rather than retried.** A retry that produces a different
answer to the same input breaks task 014's replay determinism, which is the only mechanism for
reviewing a prompt change. Record the failure, leave the pair unadjudicated, and let it be visible.

**Why token accounting lands here.** The audit found the repository has none. Every cost claim in
this architecture -- "Tier 1 is the cost control", "the model must never see the bulk of the
corpus" -- is currently unfalsifiable. This is the tier where a number can be attached.

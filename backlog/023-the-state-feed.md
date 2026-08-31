# A password-protected feed showing current state of every live watch, so email carries transitions and the feed carries state.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
SIZE: medium
ACCEPTANCE: `make check` passes, plus: the weekly Lambda writes a JSON state snapshot to S3 containing every live watch with its claim, current belief, date and direction of last change, the decision it serves, days to expiry, staleness state, and its last three evidence items; a static page renders one card per watch behind HTTP Basic auth that **fails closed** -- no credential configured returns 503, never open -- reusing the corrected pattern from `silk-reeling-mirror` PR #5; the page has **no scroll beyond the card list, no counts, no badges, no history stream, and no infinite anything**; a week in which nothing changed renders every card reading "no change since <date>" and that is a complete and correct view; belief can be adjusted and a watch resolved from the page, writing back through the same path the CLI uses; and the page renders correctly with zero live watches rather than erroring.
OUT OF SCOPE: Any content the feed shows that the email does not. This is the constraint that keeps it from becoming a place to browse, and browsing is the addictive property. No article text beyond the evidence items already attached to a watch. No search, no archive, no "explore", no related-watch suggestions. No engagement metrics of any kind -- not view counts, not streaks, not "3 new since your last visit". No LLM call in the render path. No server: a JSON file and a static page, nothing to compromise beyond the bucket. No mobile app.
LANDMINES: **Every feature that makes this more engaging moves it back toward being a briefing, which is the product being replaced.** The pressure will not arrive as "let's make it addictive"; it will arrive as "it would be useful to also see...". The acceptance criterion "shows nothing the email does not" is the line, and it is written that way so a proposed addition has to justify itself against the email first. **Auth must fail closed and this is not theoretical**: the same middleware pattern shipped fail-open in `silk-reeling-mirror` and served the whole app when an env var was missing. **The snapshot contains Position-derived data** -- decisions, deadlines, beliefs -- which is more sensitive than anything currently on samaydlette.com. The S3 object must not be public-read, and the bucket must not be the site's public bucket. `main` is protected -- open a PR.
---
Written 2026-08-31.

## Why this is not scope creep

Email is good at transitions and bad at state. *"Belief on FedRAMP 20x moved to 0.62"* is an email.
*"What do I currently believe across nine watches, and which are stale?"* is not -- answering that
from an inbox means reconstructing state from a sequence of deltas, which is the wrong tool.

**Email carries transitions. The feed carries state.** Each does one job.

## What makes it non-addictive is structural, not restraint

- **Bounded.** N watches, one card each. There is no scroll. Nine cards read is *done*, and done is
  a real state that a social feed deliberately never has.
- **State, not stream.** Cards update in place. There is no accumulating history to graze.
- **Boring when nothing happened**, the same discipline as the weekly receipt.
- **Nothing appears because it is new.** Things appear because a watch was registered on them.
- **No numbers except belief**, which the operator sets themselves.

## The highest-value interaction

Adjusting belief and resolving from the page. That is the calibration loop with the friction
removed -- and friction is the reason the existing ledger holds 33 predictions and zero verdicts.
A card with the claim, the date it last moved, and two buttons is a materially lower bar than
remembering a CLI command.

# Make silence distinguishable from breakage: staleness alerts, a dead-man's switch off the mail path, and a weekly receipt.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
SIZE: medium
ACCEPTANCE: `make check` passes, plus: a Watch routing zero Observations for `staleness_alert_days` fires its own Alert naming the watch and the decision it serves; a **heartbeat and DLQ-depth alarm reach the operator through a channel that is not SES**, so a notification-path failure is reported by a path that did not fail -- the channel is named in the PR and its failure mode stated; a weekly receipt is emitted on a fixed schedule stating watches live, alerts fired, alerts suppressed **and why**, calibration by domain, and sources that contributed nothing; the receipt is emitted **even when every count is zero**, because that is precisely when it carries information; and a test drives a fully-silent week and asserts the receipt still goes out with its zeros intact.
OUT OF SCOPE: Making the receipt interesting. It is a liveness proof and an audit surface, and every feature that makes it engaging moves it back toward being a briefing -- which is the product being replaced. No summarization, no highlights, no LLM call anywhere in the receipt path. Alert grouping or silencing UI. Adapter retry policy beyond what the DLQ requires.
LANDMINES: **The brief names this as the requirement most likely to be quietly dropped under schedule pressure, and it is right, because nothing breaks when it is missing.** A system with no staleness alerting works perfectly on every test and fails only by saying nothing while the operator assumes it is watching. **Sequence this alongside task 017, not after it.** The moment hysteresis exists, silence becomes ambiguous; shipping the state machine without this is the window where the failure is live. **The dead-man's switch must not route through SES.** If SES is misconfigured, suspended, or the domain's DKIM breaks, an SES-delivered "SES is broken" alert is an empty inbox -- which is indistinguishable from a quiet week, which is the exact ambiguity this task exists to remove. **The receipt must stay dull on purpose** and this will be the hardest instruction in the plan to follow, because a boring weekly email is the thing everyone wants to improve. `main` is protected -- open a PR.
---
Written 2026-08-31.

## Why this is not the last task

The natural instinct is to build the pipeline and then add observability. Invariant 5 makes that
wrong: in a silence-default system, the observability *is* part of the output contract. "I am blind
here" is frequently the most valuable thing the system produces, and it is only producible if the
staleness path exists at the same time as the path that produces silence.

The repository has a direct precedent. Task 005 shipped a source-adapter layer with a silent-zero
watchdog because a deploy `notify` job had previously reported success through twelve consecutive
failed nights. Then in task 009 five feeds were configured, CI went green, and the corpus stayed
empty of all of them -- caught only because task 010's coverage command happened to exist by then.
Both were the same failure: a component that succeeded at doing nothing. This task is the general
form of the fix.

## The receipt's four sections and why each is there

- **Watches live** -- proves the config loaded.
- **Alerts fired, and suppressed with reasons** -- proves the state machine ran, and makes
  hysteresis auditable. A week with 40 suppressions is tuning information; a week with zero
  suppressions and zero alerts might be silence or might be a dead router.
- **Calibration by domain** -- the only place the system's own accuracy is visible.
- **Sources that contributed nothing** -- the coverage gap, from the opposite direction to the
  staleness alert. A source ingesting steadily and never routing is a feed that costs money and
  earns nothing.

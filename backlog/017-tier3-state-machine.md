# Apply Evidence to Watches deterministically, with hysteresis and debouncing, so one story across twelve outlets produces one transition.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
SIZE: large
ACCEPTANCE: `make check` passes, plus: belief updates and trigger evaluation are deterministic with **no LLM call**, proved the same way as Tier 1; hysteresis requires N independent sources or one source on a per-watch pre-declared authoritative list, and `N` is per-watch configuration, not a global constant; a debounce window collapses the same story arriving from many outlets into **one** transition, with a test driving twelve near-duplicate observations through and asserting exactly one Alert; a belief drift of 0.35 to 0.41 produces **no** Alert, asserted directly as the brief specifies; an Alert is created only on a state transition, never on evidence arrival; transitions are append-only and a Watch's belief history is reconstructable; and a test asserts that replaying the same Evidence twice produces the same transitions and no duplicate Alerts.
OUT OF SCOPE: Sending anything -- Alerts are created here and delivered by task 019. Silencing or grouping UI. Resolution scoring; that is task 021. Auto-adjusting hysteresis from observed alert volume, which would let the system tune away its own noise complaint. Belief models more elaborate than what the acceptance requires -- no Bayesian update framework unless a specific watch demonstrably needs one, and if one does, park and say so.
LANDMINES: **This is the task where the rewrite's whole property lives or dies, and every failure mode here is silent.** Hysteresis too weak floods; too strong means the system never fires and looks identical to a broken pipeline -- which is why task 018 must land alongside, not after. **"N independent sources" needs a definition of independent that survives contact with reality**: three outlets syndicating one wire story are not three sources, and the near-duplicate grouping from task 014 is what makes the distinction available -- if it is not wired in here, "independent" degrades to "distinct feed URL" and the debounce is defeated by exactly the case it exists for. **The state machine must be a pure function of (prior state, evidence) or the append-only history is not reconstructable.** Reading current belief from a mutable column and writing back in place will pass tests and lose the audit trail. `main` is protected -- open a PR.
---
Written 2026-08-31. **The largest and most load-bearing task in this plan.**

Everything before this tier decides what the system knows. This tier decides what it says, and it
is the only place where the difference between a monitoring system and a firehose is enforced.

**Why hysteresis is per-watch.** A global N would force one threshold across a Federal Register
publication trigger, where a single authoritative source is sufficient, and a market-sentiment
trigger, where three sources is barely a signal. Watches carry their own; the schema from task 013
already has the shape for it.

**On the belief model.** The brief specifies belief as a float and gives one transition example.
Nothing in the acceptance requires a principled update rule, and the temptation here is to build a
Bayesian framework because the data model suggests one. Resist it until a watch exists that needs
it. The 33 predictions in the ledger are a standing demonstration of what happens when machinery is
built ahead of a use for it: 25 of them cannot be graded and none ever was.

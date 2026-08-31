# Reconciliation: which product is this?

Written 2026-08-31, at the start of the monitoring re-architecture.

## The contradiction

`README.md` describes a briefing generator: situations, frame analysis, three synthesis passes, a
document you read each morning. `CLAUDE.md`'s North Star describes a persistent commitment graph
where *"the brief is the update event; the graph is the artifact."*

Both are checked in. Both are honest descriptions of something. They are not descriptions of the
same thing, and the disagreement is not cosmetic -- it decides what the selection function selects
against. A briefing selects the most notable items from the corpus. A monitoring system selects
state transitions on pre-registered watches. The first scales with news volume, the second with the
number of live watches, and no amount of better synthesis converts one into the other.

**`CLAUDE.md` is closer to correct and the re-architecture resolves in its favour.** The graph is
the artifact; the notification is the update event. The briefing framing goes to `archive/`.

## The stale claim, and it is now stale twice over

`CLAUDE.md` was corrected on 2026-08-26 to say input arrives through the adapter layer in
`src/sources/` rather than RSS alone. That correction is accurate. What is now stale is the
sentence around it describing the pipeline's purpose -- clustering, frames and synthesis are
described as being *"unaware adapters exist"*, which was the right seam for a briefing generator
and is the wrong description of a system whose downstream is a state machine.

`README.md` is stale more broadly. It opens on narrative framing and dominant-narrative analysis,
which is a coherent thesis about news consumption and is not what the system will do.

## What the docs should say after the rewrite

**`README.md`** -- lead with the monitoring claim and its measurable property: notification volume
tracks live watches, not news volume. State the invariants. Keep the `Current state` section added
on 2026-08-27, which already carries known limitations honestly and should carry the rewrite's
status the same way. Delete the frame-analysis thesis; it belongs to the archived product.

**`CLAUDE.md`** -- keep the North Star's commitment-graph framing, which survives intact. Replace
the pipeline description with the five tiers and the four invariants that constrain them. Keep the
unattended-work rules unchanged; they are product-independent and have earned their place.

**`docs/CONCEPTS.md`** -- currently 11 sections describing Questions, Predictions, Decisions,
Frames, Meta-fractures, Beats, Institutional activity and how a daily brief flows through the
graph. Sections describing the briefing flow are archived. Whether Beats, Questions and
Institutional activity survive as concepts depends on Q5 in `backlog/022`, which is parked.

## One thing worth saying plainly

The old product was not wrong because it was badly built. It has 1,006 tests, a real gate, and
several genuinely careful pieces of engineering -- the offline render path, the coverage probes,
the person-tracking boundary. It was wrong because a document of constant length emitted on a fixed
schedule cannot carry information about whether anything happened. That is a property of the shape,
not of the implementation quality, which is exactly why better synthesis was never going to fix it.

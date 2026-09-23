---
name: onboard
description: Interview the operator for the decisions they are carrying and the claims they want watched, transcribe the answers into position.yaml and watches.yaml in the private directory, validate them, and run `insightweaver watch sync`. Use on first setup, when a decision is added or closed, or when the operator asks to review the Position.
allowed-tools: Read, Write, Bash(insightweaver:*), Bash(ls:*), Bash(cat:*), Bash(diff:*), Bash(mkdir:*), Bash(python:*)
---

# Onboard

You are transcribing, not authoring. Every decision, deadline, stake, claim, belief, trigger
word, expiry and staleness window in the files you write is something the operator said in this
conversation and heard read back. If an answer is missing, ask; if it is vague, ask for the
concrete form; never fill a field yourself. This is invariant 6 of `docs/CONCEPTS.md`, the system
never authors its own watches, applied to the one place where it is easiest to break: a drafting
interview is one helpful suggestion away from being a generator.

The files are private. They name real decisions and real deadlines. They live outside the
repository at `POSITION_PATH` and `WATCHES_PATH` (default `~/.config/insightweaver/`), ideally
under git in the operator's private repo, because a review's value is the diff. This
repository's `.gitignore` refuses `position.yaml` and `watches.yaml` at the root and under
`config/`. Do not write them anywhere under the checkout.

## 1. Find what exists

```bash
insightweaver watch list
ls -la ~/.config/insightweaver/ 2>/dev/null
echo "POSITION_PATH=$POSITION_PATH WATCHES_PATH=$WATCHES_PATH"
```

If a Position exists, read it and start from it: show each decision and ask whether it is still
live, closed, or changed. If none exists, say so and start the interview. Read
`config/position.example.yaml` and `config/watches.example.yaml` once for the exact field names
and the trigger rules; the loaders reject any field that is missing or malformed, and default
nothing.

## 2. Decisions

A decision is something the operator will do or not do by a date. Ask, one at a time, and stop
when the operator says there are no more:

1. What is the decision? (`name`: one sentence they could act on.)
2. By when? (`deadline`: a date. A decision with no date is an interest, and the loader refuses
   it; do not invent one and do not accept "soon".)
3. What is at stake if it goes the wrong way? (`stake`: their words, one or two sentences.)
4. A short key for it (`key`: a slug such as `renew-authorization`; propose one built from
   their words and let them confirm).

Read the list back. Then set `reviewed` to today's date and `version: 1`. If the file
runs past two pages the loader warns; that is drift from stakes into interests, so ask which
decisions are really dated before writing more.

## 3. Watches

For each decision, ask: what would you want to know before that date that would change what you
do? Each answer that is a claim about the world becomes one watch. Ask the fields in this order
and write down the answers verbatim:

1. `claim`: the thing that is or is not true, phrased so that afterwards they could say which.
   If the answer is a topic ("FedRAMP changes"), ask for the claim inside it.
2. `belief`: their probability now, 0.0 to 1.0. Do not suggest a number.
3. `so_what.because`: what changes for the decision if the claim resolves.
4. `triggers`: the words, names and sources that would appear in a document that bears on the
   claim. Explain the rule once: a trigger is a list of clauses; within a clause every populated
   field must match and any listed value will do; across clauses any one firing is enough;
   `terms` and `entities` match whole words, an all-caps term matches case-sensitively, `sources`
   must equal a registered source name exactly (case aside): the `name` fields in
   `config/feeds/*.json`, or `Federal Register - Documents API`. The loader does not check
   source names, so check them yourself against those files before writing; a misspelt name is
   a clause that never fires and no command will say so. Ask for the actual words. A trigger
   that cannot be compiled never fires, so do not accept a sentence.
5. `expires`: when the question stops mattering, usually on or before the decision's deadline.
6. `staleness_alert_days`: after how many days of nothing routed the silence should be reported.

A watch serves exactly one decision (`so_what.decision` is that decision's key). Give each an
`id` slug built from the claim and confirmed by the operator.

## 4. Write, validate, sync

Write both files with the exact structure of the example files. If a file already exists, show
`diff` against the new content and ask before replacing it. Then:

```bash
insightweaver watch sync
insightweaver watch list
```

`watch sync` validates both files together and refuses the whole set if any field is missing or
malformed (it does not check source names; see step 3); fix what it names and run it again. Do not work around a refusal by changing what the operator said
without asking them. When it succeeds, tell the operator what was added, updated or retired, and
that `insightweaver run` is the morning command.

## What this skill does not do

It does not rank decisions, suggest beliefs, propose claims the operator did not state, or write
a watch for a decision the operator did not connect it to. It does not run `ingest`, `route` or
`adjudicate`. It does not touch the database except through `watch sync`.

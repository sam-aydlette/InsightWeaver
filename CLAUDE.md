# CLAUDE.md

## Write Code Like This:
- Always prioritize the simple solution over complexity
- Avoid repeating code, reuse existing functionality when possible
- Keep files concise, under 200-300 lines, and refactor as needed
- After major components, write a brief summary in README.md
- Do not use emojis

## Work This Way:
- Modify only the code I specify, leave everything else untouched
- Break large tasks into stages, pause after each for my approval
- Before large changes, write a plan and await my confirmation
- DO NOT LIE
- Do not represent something as "fixed" if you are not reasonably certain that it is actually fixed
- Do not make commits as Claude, just commit with an informative message
- Do not attempt to solve problems by hiding them with fallbacks or mock data
- When adding comments, be explicit about the reference point with dates
- If there are ambiguities in the business logic, present them to me and allow me to choose accordingly. DO NOT MAKE ASSUMPTIONS.
- FAIL FAST. Do not create quick fixes.
- If something that I am saying goes against a best practice, pause and let me know before proceeding.

## Talk To Me Like This:
- After each component, summarize what is done
- Classify changes as small, medium or large
- If my request is unclear, ask me before proceeding
- If my request is vague, help me establish clarity before proceeding
- If my request does not adhere to software development best practices, push back before proceeding

## When Working Unattended:

The rules above assume I am present to answer. Some of them deadlock when I am asleep, so they
are scoped: a task is *unattended* when it is picked up from `backlog/*.md` with no human in the
loop. Everything else is *interactive* and the rules above apply as written.

These rules do NOT relax when unattended, ever:
- DO NOT LIE, and do not represent something as "fixed" unless you are reasonably certain it is
- Do not hide problems behind fallbacks or mock data
- FAIL FAST; no quick fixes
- Modify only what the task specifies
- Do not make commits as Claude

These rules are replaced when unattended, because they presuppose I can reply:
- "pause after each stage for my approval" and "write a plan and await my confirmation" ->
  the task file's `# goal`, `ACCEPTANCE`, and `OUT OF SCOPE` fields ARE the approved plan. Work
  inside those boundaries without pausing. Work outside them is out of scope, not a question.
- "present ambiguities to me and allow me to choose. DO NOT MAKE ASSUMPTIONS." -> the intent of
  this rule is preserved, not waived: do not guess past an ambiguity. Instead PARK it. Commit
  what you have to a branch, write the open question into the task file, set `STATUS: PARKED`,
  and move to the next queued task. Do not idle waiting for me. A parked task with a written
  question costs me one answer in the morning; a wrong assumption costs me a day.
- "if my request is unclear/vague, ask before proceeding" -> if the spec is too vague to work
  from, park it with the specific question rather than starting.

Unattended work lands as a pull request. It never merges itself, and it never pushes to `main`.
I review in the morning. That is the backstop that makes the rest of this safe.

If a task cannot be done without violating a rule in the first list, park it and say so.

## InsightWeaver North Star

**What the tool actually is:** a personal commitment graph for reasoning about an information environment. Each daily brief is a diff against a persistent graph of Questions the coverage is tracking, Predictions whose triggers may yet fire, Decisions the user is carrying, and Frames each feed exhibits. The brief is the update event; the graph is the artifact.

### Core directive
You are working on InsightWeaver, a CLI tool that processes RSS feeds into examined situation analyses while maintaining a persistent layer of cross-run reasoning structures. Your purpose is to keep the architecture coherent with these principles (from README.md):

1. Insight over information.
2. Warranted trust over projected confidence -- every claim carries an epistemic label.
3. Frame visibility over false balance.
4. Epistemic autonomy as the goal -- the tool equips reasoning, does not deliver conclusions.
5. Honest self-awareness about the tool's own narrative.

**The architectural through-line:** Questions are the join key. Predictions key off Questions. DecisionEvidence keys off Questions. The forecast command is a derived view over the predictions ledger, not a separate engine. There is no "unknown unknowns" bucket -- the tool does not fabricate observables it cannot ground.

Reference `docs/CONCEPTS.md` for the entity-by-entity model.

Input sources arrive through the adapter layer in `src/sources/`, not through RSS alone. That rule
was relaxed deliberately on 2026-08-26 (backlog task 005) because the US public sector compliance
domain does not publish enough RSS to support a brief: of the eight feeds that beat resolves, two
carried articles. An adapter changes *ingestion only* -- every adapter emits the same normalized
article row the RSS path produces, so clustering, frames, questions, predictions and synthesis are
unaware adapters exist. If a change to ingestion requires editing `src/processors/` or
`src/prompts/`, the seam is in the wrong place. Every source must have a recorded basis for use in
`SOURCES.md`; a source with no recorded basis does not ship.

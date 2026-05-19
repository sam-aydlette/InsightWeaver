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

Reference `docs/CONCEPTS.md` for the entity-by-entity model. RSS is the only input source.

# Split brief rendering into one document model plus terminal, HTML, and email renderers, so the same brief can be delivered three ways.
REPO: InsightWeaver
STATUS: QUEUED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
ACCEPTANCE: `make check` passes, plus: a new `src/render/` package exposes a `BriefDocument` model and three renderers; `insightweaver brief` output is **byte-identical** to before this change (capture it first and diff, do not eyeball it); `insightweaver brief --format html` writes a self-contained HTML file that opens correctly with no network fetches; `insightweaver brief --format email` sends via the existing SMTP env vars; and new tests cover each renderer against a fixture `BriefDocument` without invoking the pipeline.
OUT OF SCOPE: Any change to what the brief *says* — this is a pure refactor of how it is emitted, and the terminal output must not drift by a single character. Changing the pipeline, the graph, the prompts, or any processor. Adding new content sections (entity mentions, standing questions) — those are separate queued tasks that build on this one. Changing the database schema. Styling beyond a readable single-file HTML page; no CSS framework, no web fonts, no external assets. Retry/queue logic for email delivery — a failed send should report clearly and exit non-zero, not build an outbox.
LANDMINES: The terminal output is the regression risk and it is not covered by a golden test today — capture `insightweaver brief > /tmp/before.txt` on a fixed database *before* touching anything, and diff against it at the end. Rendering is currently entangled with synthesis: `src/prompts/synthesis.py` and `src/context/` both do formatting work, so the seam is not obvious and finding it honestly is most of this task. The `.env` already carries `SMTP_SERVER`, `SMTP_PORT`, `EMAIL_USERNAME`, `EMAIL_PASSWORD`, `FROM_EMAIL`, `RECIPIENT_EMAIL` — email was anticipated and never built, so check whether dead code exists before writing new. **Never echo `EMAIL_PASSWORD` or `ANTHROPIC_API_KEY` into logs or output.** `.env` is gitignored; keep it that way. Local `main` is 11 commits ahead of `origin`; do not push.
---
This is step 1 of five for the US Public Sector Compliance beat, and it is deliberately first
because it is the only one that is a pure refactor: no new inputs, no new schema, nothing
speculative. It de-risks everything after it by proving the pipeline and the presentation are
separable, and it delivers standalone value immediately — email and HTML for the brief that
already exists.

Target shape:

```
src/render/
  document.py    BriefDocument: sections, situations, questions, predictions, meta-fractures
  terminal.py    TerminalRenderer  (must reproduce today's output exactly)
  html.py        HTMLRenderer      (self-contained, no external assets)
  email.py       EmailRenderer     (wraps HTMLRenderer, sends via SMTP)
```

The pipeline builds a `BriefDocument`; the CLI picks a renderer. That is the whole change.

Do the terminal renderer first and get it byte-identical before writing the other two. If the
seam turns out to be genuinely tangled — if synthesis is emitting formatted strings rather than
structured data — say so and park it rather than half-extracting it. A partial split is worse
than none, because it leaves two places that format.

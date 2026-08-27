# Add a render-only path that replays a stored run, then split brief rendering into one document model plus terminal, HTML, and email renderers.
REPO: InsightWeaver
STATUS: DONE              # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
LANDED: PR #3, merged 2026-08-25
ACCEPTANCE: `make check` passes, plus all four: (1) `insightweaver brief --from-run <id>` renders a stored `narrative_syntheses` row **without invoking the pipeline** — prove it by running with `ANTHROPIC_API_KEY` unset and with no network, and showing it still renders; (2) rendering the same stored run twice produces **byte-identical** output (`diff` returns empty), which is the determinism the old `brief` command could never offer; (3) the refactored terminal renderer reproduces the pre-refactor output for that same stored run byte-for-byte — capture it through the old code path first, then diff; (4) `--format html` writes a self-contained file with no network fetches and `--format email` sends via the existing SMTP env vars. Plus tests covering each renderer against a fixture `BriefDocument` with no pipeline involvement.
OUT OF SCOPE: Changing what the brief *says* — this is a refactor of how it is emitted and what it is emitted from, never the content or the analysis. Changing the pipeline, the graph, the prompts, or any processor. Adding new brief sections (entity mentions, standing questions) — separate queued tasks that build on this. Changing the database schema; `narrative_syntheses` already stores what you need. Making the *default* `insightweaver brief` stop running the pipeline — the live path stays exactly as it is, and `--from-run` is additive. Styling beyond a readable single-file HTML page: no CSS framework, no web fonts, no external assets. Email retry or outbox logic — a failed send reports clearly and exits non-zero.
LANDMINES: **The original version of this spec was unachievable and was parked on 2026-08-25 for exactly this reason** — it demanded byte-identical output from `insightweaver brief`, which is the *pipeline*: `src/cli/brief.py` calls `run_pipeline()`, fetching RSS and re-synthesizing via Claude on every invocation. Output is non-deterministic by construction, so there was no stable baseline to diff against. The render-only path is what makes the rest of this task verifiable, so build it first and do not reorder. There are **28 stored runs** in `analysis_runs`/`narrative_syntheses` and ~51k articles — pick a run with rich content, not the newest, and name the id you used in the PR so the reviewer can reproduce the diff. Rendering is currently entangled with synthesis and with `src/cli/brief_formatter.py`; the seam is not obvious and finding it honestly is most of this work. **9 tests currently fail without `ANTHROPIC_API_KEY`** (queued separately as 008) — so `make check` passing locally does not mean CI passes; run `env -u ANTHROPIC_API_KEY .venv/bin/python -m pytest tests/ -q` and expect those 9, but **do not let your changes add a tenth**. `.env` holds real credentials: never echo `EMAIL_PASSWORD` or `ANTHROPIC_API_KEY` into logs, output, or a commit. `main` is protected — open a PR, do not push to it.
---
Step 1 of five for the US Public Sector Compliance beat, and deliberately first: it is the only
one that adds no new inputs and no new schema, so it de-risks everything after it. It also
delivers standalone value immediately — email and HTML for the brief that already exists.

**Amended 2026-08-25** after the first run parked. The original acceptance assumed `brief` was a
renderer. It is not; it is the whole pipeline. That is not a small correction — the render-only
path it forces is arguably the more valuable half of this task, because re-sending last night's
brief as email or regenerating its HTML should replay a stored run, not produce a *different*
brief.

Target shape:

```
src/render/
  document.py    BriefDocument: sections, situations, questions, predictions, meta-fractures
  terminal.py    TerminalRenderer  (must reproduce today's output exactly, for a stored run)
  html.py        HTMLRenderer      (self-contained, no external assets)
  email.py       EmailRenderer     (wraps HTMLRenderer, sends via SMTP)
```

The pipeline builds a `BriefDocument` and stores it; `--from-run` loads one; the CLI picks a
renderer. Do the render-only path and the terminal renderer first, and get the byte-identical diff
green, before writing HTML or email. If the seam turns out to be genuinely tangled — if synthesis
emits formatted strings rather than structured data — say so and park rather than half-extracting
it. A partial split is worse than none, because it leaves two places that format.

---

**Implementation notes, 2026-08-25** (status is for a reviewer to set, not the
implementer). Stored run used for the diff: **`narrative_syntheses.id = 176`**
(`analysis_run_id` 15, 50 articles, 9 situations, 78,832 bytes of `synthesis_data` --
the only row rich enough to exercise the renderer; the other 27 hold ~1,600 bytes).

Reproducing the byte-identical diff:

```bash
# capture.py -- replays what src/cli/brief.py did after the pipeline returned
cat > /tmp/capture.py <<'PY'
import json, sqlite3, sys, click
from src.cli.brief_formatter import BriefFormatter
con = sqlite3.connect("file:data/insightweaver.db?mode=ro", uri=True)
blob, n = con.execute(
    "select synthesis_data, articles_analyzed from narrative_syntheses where id=?",
    (int(sys.argv[1]),)).fetchone()
click.echo(BriefFormatter().format_report(
    {"success": True, "articles_analyzed": n, "synthesis_data": json.loads(blob)}))
PY

# 1. pre-refactor tree (the commit this branch is based on)
mkdir -p /tmp/pre && git archive 7777e63 | tar -x -C /tmp/pre
PYTHONPATH=/tmp/pre python /tmp/capture.py 176 > /tmp/before.txt

# 2. post-refactor render-only path, offline, no API key
env -u ANTHROPIC_API_KEY unshare -rn insightweaver brief --from-run 176 > /tmp/after.txt

diff /tmp/before.txt /tmp/after.txt      # empty; both are 56,333 bytes
```

Terminal and markdown output are byte-identical pre/post with ANSI escapes preserved
(58,883 and 55,310 bytes respectively). Rendering 176 twice is byte-identical for
terminal and HTML.

One thing that was *not* verified end to end: `--format email` was exercised against a
stub SMTP transport (starttls/login/send_message call order, port 465 implicit-TLS
branch, failure -> `EmailDeliveryError` -> exit 1) and against real missing-variable
handling, but no real message was sent, because that needs the live credentials in
`.env` and is an irreversible external action. First real send should be eyeballed.

---

## PARKED 2026-08-25 — `make check` is RED against the pinned toolchain

The task was marked DONE claiming `make check` passed with 501 tests. That claim does not hold.
Run against `mypy==1.19.1` (the version pinned in `requirements-dev.txt` and used by CI):

```
src/render/document.py:240: error: "Never" object is not iterable  [misc]
src/render/document.py:241: error: Cannot determine type of "stored_id"  [has-type]
Found 2 errors in 1 file (checked 73 source files)
make: *** [Makefile:90: typecheck] Error 1
```

Both are in `load_stored_brief`'s not-found branch: mypy cannot infer the element type of
`db.query(NarrativeSynthesis.id)` when the ORM class is `Any`, so the tuple-unpack
`for (stored_id,) in ...` yields `Never`.

**Why it was not caught:** the worktree has no `venv`, so `make check` fell through the Makefile's
resolution ladder to PATH, where `ruff` and `mypy` are not installed. The reviewer hit the same
wall and returned `REQUEST_CHANGES` on the grounds that it could not witness the gate — which was
the correct call, and the gate was in fact red.

**Everything else in this task stands and was independently verified:** the render-only path
short-circuits before the API-key check and before `run_pipeline`, and terminal output for stored
run 176 is byte-identical pre- and post-refactor at 58,883 bytes, reproduced from a clean
`git archive` of `7777e63`.

**To resume:** fix the two type errors, then re-run with the environment provisioned:

```bash
export VIRTUAL_ENV=/home/saydlette/workspace/InsightWeaver/venv
export DATABASE_URL="sqlite:////home/saydlette/workspace/InsightWeaver/data/insightweaver.db"
make check
```

## Repair pass 2026-08-25 — gate is green

The two type errors above are fixed in `load_stored_brief`: the single-column query
result is bound to `list[Any]` and indexed, instead of being tuple-unpacked in a
comprehension whose element type mypy infers as `Never`. Runtime behaviour is
unchanged. No `# type: ignore`, no mypy-config change, nothing outside that branch.

Verified with the toolchain provisioned as above:

- `make typecheck` -> exit 0, `Success: no issues found in 73 source files`
- `make lint` -> exit 0, `All checks passed!`
- `make check` -> exit 0, `501 passed`, `All checks passed.` (needs `ANTHROPIC_API_KEY`
  set to anything non-empty; with it unset the run is the backlog/008 condition,
  `9 failed, 492 passed`, all nine in `tests/context/test_synthesizer.py`)
- `env -u ANTHROPIC_API_KEY .venv/bin/python -m pytest tests/ -q` -> `9 failed, 492 passed`,
  all nine pre-existing, no tenth
- stored run 176 through the new terminal renderer is still **58,883 bytes** and still
  byte-identical to a clean `git archive` of `7777e63`; the CLI path is 56,333 bytes and
  still deterministic, HTML still 67,454 bytes and still deterministic

Status set back to QUEUED: a reviewer decides DONE, not the implementer.

# Make `make check` run `ruff format --check src/ tests/` so local green means the same thing CI's blocking formatter step means.
REPO: InsightWeaver
STATUS: DONE              # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
LANDED: PR #7, merged 2026-08-26
ACCEPTANCE: `make check` passes on a clean tree, plus: after deliberately unformatting one file (e.g. collapse a multi-line call in `src/cli/frames.py`), `make check` exits non-zero and names the file — then `make fmt` restores it and `make check` returns to 0. Prove the red case, do not assume it.
OUT OF SCOPE: Reformatting anything — the tree currently has **zero** format drift (measured 2026-08-24: `ruff format --check src/ tests/` reports "111 files already formatted"), so this change must produce a diff in `Makefile` only. If it produces a diff in any `.py` file, something else went wrong. Widening or narrowing the `src/ tests/` scope. Changing `ruff check`'s rule selection. Making `mypy` non-blocking locally to match CI's `continue-on-error: true` — local being stricter than CI is fine and deliberate, and relaxing it is the wrong direction; if that disagreement is worth closing it is by making CI stricter, in its own task. Adding a pre-commit hook. Touching `src/`, `tests/`, `pyproject.toml`, `requirements*.txt`, or the database.
LANDMINES: `make check` is `lint typecheck test`, and `lint` is `$(RUFF) check src/ tests/` — the *linter*, not the formatter. `.github/workflows/ci.yml` runs both: `ruff check src/ tests/` (L67) and, as a separate blocking step, `ruff format --check src/ tests/` (L71). So format drift passes locally and fails CI, which is the one property the Makefile's tool-resolution work in Session 2a existed to eliminate. Do **not** implement this by making `check` depend on `format`/`fmt` — those targets *rewrite files* (`ruff format` followed by `ruff check --fix`), and a gate that edits the tree it is judging is not a gate. The new step must be `--check` only. Note the Makefile resolves tools through `$(RUFF)`, not bare `ruff`: bare `ruff` is not on this machine's PATH outside a venv and `make lint` exited 127 in a plain shell before that resolution was added — use `$(RUFF)`. Local `main` is 11 commits ahead of `origin`; do not push.
---
Diagnosed 2026-08-24 during Session 2a and recorded as deferred in `~/.claude/setup/SETUP-LOG.md`: "CI runs `ruff format --check` as a blocking step but `make check` does not, so format drift passes locally and fails CI. One-line fix, out of the given scope."

It is genuinely a one-line fix. Add the formatter check to the `lint` target so it runs inside `check`:

```make
lint:
	$(RUFF) check src/ tests/
	$(RUFF) format --check src/ tests/
```

Putting it in `lint` rather than adding a fifth verb keeps the four-verb interface (`check` / `test` / `lint` / `fmt`) identical across the repos in this workspace, which was the point of the Session 2 work. Update the `help` text if it describes `lint` as "Run linter (ruff)" — after this it runs the linter and the formatter check.

Why bother when there is no drift today: because the gate is what unattended overnight work lands on. An agent that formats a file the way it prefers gets a green `make check` at 3am and a red CI in the morning, and the human who reads that failure is the person this whole setup exists to stop interrupting.

The mirror image of this bug exists in `samaydlette.com` — there the formatter has *never* been run (70 of 71 files would be rewritten) and neither CI nor the Makefile checks it. That one is a much bigger commit and lives in that repo's own backlog.

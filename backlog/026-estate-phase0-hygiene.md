# Estate Phase 0: keychain credentials, an audited model client, secret scanning, and the plan's decisions recorded.
REPO: InsightWeaver
STATUS: IN_PROGRESS       # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
SIZE: small
PLAN: docs/ESTATE_PLAN.md (section 5, Phase 0)
ACCEPTANCE: `make check` passes, plus: the Anthropic key is read from the OS keychain through `keyring` at the moment a model client is constructed, never at import and never from `.env`, with **no environment fallback** -- a test sets `ANTHROPIC_API_KEY` in the environment, leaves the keychain empty, and asserts the client refuses; `estate auth set|status|clear` exist and `status` never prints a value; **every outbound model request is written to a local JSON-lines audit log before it is sent** and its usage after, with a test that stubs the SDK to fail and asserts the request line exists with an error line and no response line; the client returns token usage rather than discarding it; the model is chosen by role (`triage` -> `settings.llm_triage_model`, `synthesis` -> `settings.llm_synthesis_model`) and no `src/` module outside the client constructs a request, asserted against the tree; a secret scanner runs in pre-commit and in a CI job that **can fail**; the `anthropic` pin is raised to 1.x so `output_config` is a named parameter; `.gitignore` refuses the audit log, an `estate/` directory at the root and OAuth artefacts; and the decisions of 2026-09-22 are recorded in `docs/ESTATE_PLAN.md`, `backlog/022`, and the superseded task files.
OUT OF SCOPE: The grid, any sensor, any brief section, the `grid` trigger axis, `watch_beliefs`, and `estate` commands other than `auth` -- each is its own Phase 1 task. Structured output in the client (Phase 1d, task 016). Rewriting `README.md` / `GETTING_STARTED.md` / `docs/CONCEPTS.md` (Phase 1c). Deleting the dead top-level `migrations/` directory. Moving the database file out of the checkout.
LANDMINES: **A fallback is a second place a secret lives.** The obvious convenience is "read the keychain, else the environment", and it is exactly the thing this task exists to remove; the test that sets the env var and asserts refusal is there to make the convenience fail loudly if someone adds it. **The audit log must be written before the send, not after**, or a process that dies mid-call leaves no record that a payload left the machine. **`parse_claude_json` returns `{}` on failure**; it is a silent default and Tier 2 must not use it -- noted in `src/llm/__init__.py` rather than deleted, because deleting it is not this task's call. **`safety check || true` cannot fail the build** and never could; the secrets step is the first thing in that job that can. **The requirements files are compiled artefacts**; regenerate them with `pip-compile`, do not hand-edit the pins. `main` is protected -- open a PR.
---
Written 2026-09-22, the day the plan was approved.

## Why this is its own PR

Every later phase builds on three properties this one establishes: secrets have one home, model
calls have one door and it is logged, and a leaked key cannot be committed. None of them is
interesting on its own and each is the kind of thing that gets folded into a feature PR and then
half-done. Landing them first, small and reviewable, means Phase 1a starts from a tree where the
rules are already enforced rather than promised.

## What changed in the tree, and why each

| change | reason |
|---|---|
| `src/estate/credentials.py`, `src/estate/cli.py` | the keychain path and the one command that writes to it |
| `src/llm/audit.py` | the log; request before send, response or error after |
| `src/llm/claude_client.py` rewritten | key from keychain, role-chosen model, `output_config`, usage returned, dead briefing-era methods removed |
| `src/config/settings.py` | `anthropic_api_key` removed; `llm_audit_dir`, two model settings, `keyring_service` added |
| `pyproject.toml`, `requirements*.txt` | `anthropic>=1.7,<2`, `keyring`, `pydantic` explicit, `detect-secrets`, `types-PyYAML`, the `estate` script |
| `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `.secrets.baseline` | scanning that can fail |
| `.gitignore`, `.env.example` | the audit log and an `estate/` directory refused; the key line gone |
| `backlog/015, 016, 018, 019, 020, 022, 023` | rescoped, rewritten for a laptop, or superseded, each with a dated note |
| `docs/RECONCILIATION.md`, `CLAUDE.md` | the estate plan is now the plan; the North Star paragraph names nodes, not questions |

## On `types-PyYAML`

`make typecheck` failed in a fresh virtualenv on 2026-09-22 with "Library stubs not installed for
yaml" because the stubs were only ever installed by the pre-commit mypy hook's
`additional_dependencies`. A gate that passes in one environment and fails in another is the
pattern the Makefile's tool-resolution note already corrected once; the stubs are a dev dependency
now.

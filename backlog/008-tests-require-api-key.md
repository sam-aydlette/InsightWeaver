# Make the synthesizer tests run without an ANTHROPIC_API_KEY, so CI is green and `make check` means what CI means.
REPO: InsightWeaver
STATUS: DONE              # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
LANDED: PR #4, merged 2026-08-26
ACCEPTANCE: `make check` passes, plus: `env -u ANTHROPIC_API_KEY .venv/bin/python -m pytest tests/ -q` passes with **zero** failures (this is the real acceptance — it reproduces CI's environment locally, and it currently fails 9 tests); CI on `main` goes green; and the two `Test (Python 3.11)` / `Test (Python 3.12)` contexts are restored to the required set in branch protection once it does.
OUT OF SCOPE: Adding `ANTHROPIC_API_KEY` as a CI secret — that would make CI green by letting it make **real, billed API calls** on every push, which is the wrong fix twice over. Changing what the synthesizer does. Deleting or permanently skipping the nine tests — they cover citation maps, token estimation, profile hashing, and the two-pass synthesis path, all of which are worth testing. Rewriting the tests to test less than they do now. Touching `src/` beyond whatever minimal seam is needed to inject a fake client.
LANDMINES: **This is the exact local-green/CI-red gap Session 2 existed to close, and it survived that session unnoticed** — `make check` passes on this machine only because `.env` supplies a real key, so the gate has been lying about CI parity. Whatever the fix, verify it by unsetting the variable, not by trusting `make check`. The nine failures come from the 11 staged commits (`stage 0` … `stage A cleanup`) that lived locally for five months and were pushed 2026-08-25; CI had not run on them since 2026-03-31, so this is drift being surfaced, not newly introduced. Do not "fix" it by making the key optional at import time and letting the synthesizer construct with a null client — that moves a loud failure to a quiet one and would reach production. `ValueError: ANTHROPIC_API_KEY not configured` is raised at client construction; the seam is dependency injection or a fixture that patches the client, not defensive defaulting. **Never print the key, and never commit it.**
---
Found 2026-08-25 immediately after pushing `main` and enabling branch protection. The two Test
contexts were temporarily removed from the required set so PRs are not wedged; restoring them is
part of this task's acceptance, not a follow-up.

The nine failures, all `ValueError: ANTHROPIC_API_KEY not configured`:

```
tests/context/test_synthesizer.py::TestSynthesizerConfiguration::test_topic_filters_are_applied_to_curation
tests/context/test_synthesizer.py::TestCitationMap::test_builds_citation_map_from_articles
tests/context/test_synthesizer.py::TestEstimateTokens::test_estimate_tokens_basic
tests/context/test_synthesizer.py::TestEstimateTokens::test_estimate_tokens_empty_context
tests/context/test_synthesizer.py::TestHashProfile::test_hash_profile_consistent
tests/context/test_synthesizer.py::TestHashProfile::test_hash_profile_different_for_different_profiles
tests/context/test_synthesizer.py::TestHashProfile::test_hash_profile_none_returns_none
tests/context/test_synthesizer.py::TestSynthesizeNoArticles::test_returns_no_articles_status
tests/context/test_synthesizer.py::TestSynthesizeTwoPass::test_clusters_articles_then_synthesizes
```

Note what they are: token estimation, profile hashing, and citation-map construction are **pure
functions that should never have needed a client at all**. The fix is probably to stop constructing
the synthesizer (and therefore the client) in those tests' setup, rather than to mock anything.
The two that genuinely exercise synthesis need an injected fake.

Once green, restore the required contexts:

```bash
gh api -X PUT repos/sam-aydlette/InsightWeaver/branches/main/protection --input - <<'JSON'
{"required_status_checks":{"strict":false,"contexts":["Test (Python 3.11)","Test (Python 3.12)","Lint","Type Check","Security Check"]},
 "enforce_admins":true,
 "required_pull_request_reviews":{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":0},
 "restrictions":null,"allow_force_pushes":false,"allow_deletions":false,
 "required_conversation_resolution":false,"required_linear_history":false,
 "block_creations":false,"lock_branch":false,"allow_fork_syncing":false}
JSON
```

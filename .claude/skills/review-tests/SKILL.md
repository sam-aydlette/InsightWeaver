---
name: review-tests
description: Review test code for behavior-focused testing, decoupling from implementation, and InsightWeaver patterns. Use when reviewing tests, writing new tests, or checking test quality.
allowed-tools: Read, Grep, Glob, Bash(pytest:*), Bash(python -m pytest:*)
---

# Test Review Skill

Review tests to ensure they describe behaviors, not implementations.

## Core Principles

**Tests should answer: "What does it do?" not "How does it work?"**

### Good Test Characteristics

1. **Describes behavior, not methods**
   - Test name: `test_a_second_run_asks_nothing` (behavior: idempotency)
   - Not: `test_pending_pairs_calls_query_filter` (implementation)

2. **Can actually fail**
   - A test earns its place only if a plausible bug turns it red.
   - `tests/routing/test_regression.py` plants exactly 20 whole-word matches
     among 1000 observations and 100 look-alikes, then asserts on the
     identity of the routed set, not just a count -- a routing predicate
     that is too loose bills real model calls, so the test is pinned with a
     number and was verified to fail (61 routed) when the word-boundary
     anchors were emptied out.
   - `tests/brief/test_select.py` inserts rows out of the order the brief
     must print them (`test_clusters_and_citations_are_ordered_by_date_before_hash`
     even gives the earlier observation the *larger* hash in both pairs), so
     a missing or wrong `ORDER BY` fails the test instead of passing by
     accident.

3. **No tautologies**
   - Don't assert that a mock returned what you told it to return.
   - Assert on what the code under test *did* with that input: what it
     wrote, what it computed, what it left alone.
   - `tests/position/test_ledger.py::test_only_sync_and_the_two_commands_write_belief_or_resolution`
     is the extreme version of this: instead of trusting that every call
     site remembers to go through `record_belief`/`resolve_watch`, it scans
     every file under `src/` for the patterns that would write to the
     ledger and asserts the only matches are the three allowed writers, by
     name.

4. **Mocks only at the boundary**
   - Mock the external boundary (the model API, the network), never an
     internal method of the unit under test.
   - `tests/evidence/test_adjudicate.py`'s `FakeClient` stands in for the
     Claude API client itself -- the one seam that would otherwise cost
     money and require a key -- and returns scripted `ModelResponse` or
     raises a scripted `ModelCallFailed`. Everything downstream (routing,
     the adjudicator, the ledger writes) is the real code.
   - `tests/sources/test_runner.py`'s `FakeAdapter` plays the same role for
     a source: it returns a scripted list of items, an empty list, or
     raises `SourceUnavailable`, and the runner, the silence watchdog and
     the database writes are all real.
   - `tests/brief/test_end_to_end.py` goes one boundary further: it patches
     `get_db` to yield one shared test session and patches the HTTP layer
     under each adapter, then runs the real CLI commands (`watch sync`,
     `ingest`, `route`, `adjudicate`, `brief`) end to end and compares the
     rendered bytes against a committed golden file.

## Red Flags

- Test names that mirror method or function names exactly
- Assertions that only check a mock's call count (`mock.assert_called_once()`
  with nothing about what it produced)
- Tests that would still pass if the feature were deleted
- A test that asserts a value it just told a stub to return
- Mocking an internal function of the module under test rather than the
  true external boundary (an LLM client, the network, the database engine)
- A clock read from the wall in a test that asserts on dates or ordering
  (see `frozen_clock` in `tests/brief/test_end_to_end.py`, which replaces
  the `datetime` class `src.utils.utcnow` reads)

## Review Checklist

When reviewing a test, ask:

- [ ] Does the test name describe a behavior or outcome, not a method call?
- [ ] Is there a concrete bug that would turn this test red? (If you can't
      name one, the test may be a tautology.)
- [ ] Are assertions on outcomes -- what got written, computed, or
      rendered -- rather than on call patterns?
- [ ] Is mocking limited to a true external boundary (model client,
      network, wall clock), with everything else real?
- [ ] Would this test survive a refactor that kept behavior the same but
      changed internals (renamed a private function, changed a return
      type)?
- [ ] If the test is about ordering or a threshold, is it exercised with
      data that would expose a wrong sort or an off-by-one (both sides of
      the boundary, not just one)?

## Questions to Ask

1. "If I renamed a private function, would this test break?"
2. "What real defect would this test catch?"
3. "Am I testing the contract (what the caller observes) or the internals?"
4. "Is every mock here standing in for the network, the model, or the
   clock -- or did I mock something inside the unit under test?"

## Example Transformation

**Before (tautological, mock-verification only):**
```python
def test_run_calls_the_client():
    client = FakeClient(_verdict())
    run(corpus, ClaudeAdjudicator(client))
    assert client.calls == 1
```

**After (behavior-focused, from `tests/evidence/test_adjudicate.py`):**
```python
def test_every_pair_gets_a_ledger_row_and_evidence_gets_an_evidence_row(self, corpus):
    client = FakeClient(_verdict(), _verdict(is_evidence=False, direction="none"))

    result = run(corpus, ClaudeAdjudicator(client))

    assert (result.asked, result.evidence, result.none, result.failed) == (2, 1, 1, 0)
    ledger = corpus.query(Adjudication).order_by(Adjudication.watch_id).all()
    assert [(a.watch_id, a.outcome, a.audit_id) for a in ledger] == [
        ("conmon-scope-expands", "evidence", "audit-1"),
        ("hiring-market-tightens", "none", "audit-2"),
    ]
```

See `examples.md` for the full good/bad contrast pairs drawn from the
current suite.

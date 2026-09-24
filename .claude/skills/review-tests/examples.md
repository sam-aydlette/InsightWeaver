# Test Examples from InsightWeaver

Excerpts are trimmed to the lines the point needs; `# ...` marks lines left out.

## Good Examples (Behavior-Focused, Can Fail, Boundary-Mocked)

### From tests/evidence/test_adjudicate.py

```python
def test_a_second_run_asks_nothing(self, corpus):
    client = FakeClient(_verdict(), _verdict())
    run(corpus, ClaudeAdjudicator(client))

    second = run(corpus, ClaudeAdjudicator(client))

    assert second.asked == 0
    assert client.calls == 2
    # ...
```

**Why good:** `FakeClient` replaces the one true boundary in this path --
the Claude API -- and nothing else; routing, the adjudicator and the
database writes are all real. The name states the behavior (never-retried),
and the assertion checks both the observable count and the mechanism that
would leak a retry (`client.calls == 2`, not 4).

### From tests/routing/test_regression.py

```python
def test_exactly_the_planted_whole_word_matches_route(test_session):
    # ... the two builders that plant the corpus
    report = route(test_session, since=SINCE, today=TODAY)

    # ...
    assert report.routed == 20
    routed_hashes = {h for (h,) in test_session.query(Route.observation_hash)}
    assert routed_hashes == planted_hashes
```

**Why good:** pinned with a number, not "some routed" -- the file's
docstring records that this test was verified to fail (61 routed) when the
word-boundary anchors in `entity_matcher.py` were emptied. It checks
identity (`routed_hashes == planted_hashes`), not just count, so a router
that matched the wrong 20 items still fails. The look-alike corpus plants
`PRECISA` and `COMBAT` in capitals because task 010 found a boundary test
that passed for the wrong reason (case-sensitivity, not the anchors).

### From tests/brief/test_select.py

```python
def test_clusters_and_citations_are_ordered_by_date_before_hash(self, test_session):
    # The earlier observation has the LARGER hash in both pairs, so an
    # order by hash alone gets both wrong.
    later_small = _obs(test_session, "aa", source.id, "later", None, datetime(2026, 9, 16), [7]*10)
    earlier_big = _obs(test_session, "zz", source.id, "earlier", None, datetime(2026, 9, 15), [7]*10)
    ...
    assert [c[0].title for c in moved.clusters] == ["earlier", "single"]
```

**Why good:** rows are inserted with hashes running opposite to the
correct date order, so a missing or wrong `ORDER BY` fails loudly instead
of passing by coincidence. Elsewhere in the file,
`test_the_review_banner_turns_on_the_day_after_the_threshold` exercises
both sides of a threshold, which is what catches an off-by-one.

### From tests/brief/test_end_to_end.py

```python
class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.replace(tzinfo=UTC) if tz is not None else NOW

@pytest.fixture
def frozen_clock(monkeypatch):
    monkeypatch.setattr("src.utils.datetime", _FrozenDatetime)
    return NOW
```

**Why good:** the clock is a boundary like any other -- every column
default and the belief ledger read `src.utils.utcnow`, so it is frozen here.
Everything else patched is a boundary too: the HTTP layer under each adapter,
the model client behind the adjudicator, the two private file loaders, and
each command's `get_db`, pointed at one test session. Nothing inside the
pipeline is mocked. The real CLI commands (`watch sync`, `ingest`, `route`, `adjudicate`,
`brief`) then run end to end against a real session, compared byte-for-byte
with a committed golden file -- catching regressions no single unit test
would see.

### From tests/position/test_ledger.py

```python
def test_only_sync_and_the_two_commands_write_belief_or_resolution():
    patterns = [re.compile(r"\brecord_belief\("), re.compile(r"\bresolve_watch\("), ...]
    allowed = {root / "position" / "ledger.py", root / "position" / "watches.py",
               root / "cli" / "watch.py"}
    offenders = [str(p.relative_to(root)) for p in sorted(root.rglob("*.py"))
                 if p not in allowed and any(pat.search(p.read_text()) for pat in patterns)]
    assert offenders == []
```

**Why good:** instead of trusting every future call site to remember "only
the ledger writes belief", it scans the tree for anything that could
construct a ledger row or assign a resolution column and names the
offending file if one appears -- catching a bypass, not just documenting
the rule.

### From tests/sources/test_runner.py

```python
async def test_source_unavailable_is_an_error_not_an_empty_run(self, db_factory, caplog):
    adapter = FakeAdapter(SourceUnavailable("Fake Source", "HTTP 503"))

    result = await run_adapter(adapter, SINCE, db_factory=db_factory)

    assert result.success is False
    assert result.fetched == 0
```

**Why good:** `FakeAdapter` mocks only the source boundary (`fetch`), which
can return items, return nothing, or raise. This test and its neighbor
`test_zero_after_some_is_loud` distinguish two failure classes that look
alike from outside (zero items): unreachable is loud on a first run, quiet
is loud only once a source has history to contradict.

---

## Bad Examples (Tautological, Implementation-Coupled, or Untrustworthy)

### Testing a Mock's Own Return Value

```python
# BAD: asserts the stub returned what it was told to return
client = FakeClient(_verdict())
response = client.analyze("system", "user")
assert response.text == _verdict()
```

**Problems:** no code under test runs; this is a tautology about the
fixture, not a behavior of `run()`. No plausible bug would ever turn it
red.

**Better:** assert on what `run()` does with that verdict, as in
`test_every_pair_gets_a_ledger_row_and_evidence_gets_an_evidence_row`
above.

### Asserting Only a Count

```python
# BAD: passes even if the wrong 20 items routed
def test_some_items_route(test_session):
    report = route(test_session, since=SINCE, today=TODAY)
    assert report.routed == 20
```

**Problems:** drops the identity check, so a router that matched 20 wrong
items (look-alikes instead of the planted whole words) still passes.

**Better:** compare the routed set by hash against the known-planted set.

### Mocking Past the Boundary

```python
# BAD: mocks a method internal to the unit under test, not the true boundary
with patch("src.sources.runner.store_items") as mock_store:
    await run_adapter(FakeAdapter([item("a")]), SINCE, db_factory=db_factory)
    mock_store.assert_called_once()
```

**Problems:** `store_items` is internal to the module under test; the
assertion verifies a call happened, not that a row exists.

**Better:** mock only the adapter's `fetch` and assert on `RSSFeed`/
`Article` rows through the real `db_factory` session, as the real tests do.

### A Clock Read from the Wall

```python
# BAD: uses the real clock in a test that asserts on dates
def test_watch_is_live_today():
    watch = Watch(id="w", expires=date.today() + timedelta(days=1), ...)
    assert live_clause(date.today())
```

**Problems:** nothing pins the scenario; the test's meaning drifts with
the date it happens to run on.

**Better:** pass an explicit `TODAY = date(2026, 9, 1)`, as
`tests/position/test_ledger.py` does throughout, or freeze `src.utils`'s
clock for a full command run as `test_end_to_end.py` does.

---

## Refactoring Litmus Test

Ask yourself: **If I refactor the implementation without changing behavior, do tests break?**

| Refactoring | Good Test | Bad Test |
|-------------|-----------|----------|
| Rename a private helper | Still passes | Breaks |
| Change an internal data structure, same output | Still passes | Breaks |
| Split one module into two, same CLI/API behavior | Still passes | Breaks |
| Change an algorithm, same routed/adjudicated result | Still passes | May break |
| Introduce the exact bug the test exists to catch | Fails | Still passes |

If your tests break on a pure refactor, or stay green through the bug they
were written for, they are testing implementation, not behavior.

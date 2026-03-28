# Test Examples from InsightWeaver

## Good Examples (Behavior-Focused)

### From test_synthesizer.py

```python
class TestSynthesizeWithTrustVerificationCitationMap:
    """Integration tests for citation_map handling in trust-verified synthesis"""

    @pytest.mark.asyncio
    async def test_citation_map_overrides_claude_response(self, ...):
        """Our citation map should override any citation_map Claude returns"""
        # Arrange: Setup with KNOWN correct data
        test_articles = [{"id": 99, "title": "Correct Title", ...}]
        mock_curator.return_value = {"articles": test_articles}

        # Claude returns WRONG data (simulating the bug)
        mock_client.return_value = json.dumps({
            "metadata": {"citation_map": {"1": {"title": "WRONG Title"}}}
        })

        # Act
        result = await synthesizer.synthesize_with_trust_verification()

        # Assert: Our data wins (the behavior we care about)
        citation_map = result["synthesis_data"]["metadata"]["citation_map"]
        assert citation_map["1"]["title"] == "Correct Title"  # Not "WRONG Title"
```

**Why this is good:**
- Test name describes the behavior: "citation_map_overrides_claude_response"
- Tests a real scenario: Claude returning incorrect data
- Asserts on the outcome users care about: correct citation titles
- Does not assert on internal method calls

### From test_trust_pipeline.py

```python
async def test_biased_response_detected(self, trust_pipeline):
    """Test detection of bias in response"""
    # Arrange
    trust_pipeline.client.analyze = AsyncMock(
        return_value="This revolutionary technology will change everything!"
    )
    trust_pipeline.bias_analyzer.analyze = AsyncMock(
        return_value=BiasAnalysis(
            loaded_terms=[LoadedTerm("revolutionary", "dramatic", "innovative")]
        )
    )

    # Act
    result = await trust_pipeline.run_full_pipeline(
        user_query="Tell me about tech", verify_response=True
    )

    # Assert: Bias was detected (the behavior)
    assert result["analysis"]["bias"]["total_issues"] > 0
```

**Why this is good:**
- Tests the user-visible outcome: "bias detected"
- Does not care HOW bias was detected internally
- Meaningful assertion on what matters

---

## Bad Examples (Implementation-Coupled)

### Testing Method Signatures

```python
# BAD: Tests implementation detail (return type)
def test_build_synthesis_task_with_citations_returns_tuple():
    result = synthesizer._build_synthesis_task_with_citations(articles, 2)
    assert isinstance(result, tuple)
    assert len(result) == 2
```

**Problems:**
- Name mirrors method name exactly
- Tests private method directly
- Asserts on structure, not behavior
- Would break if we changed return type but kept behavior

**Better:**
```python
# GOOD: Test the behavior enabled by this method
def test_synthesis_output_contains_accurate_citation_references():
    result = await synthesizer.synthesize_with_trust_verification()
    # Assert on what the citation_map enables
    assert result["synthesis_data"]["metadata"]["citation_map"]
```

### Excessive Mock Verification

```python
# BAD: Tests plumbing, not behavior
async def test_synthesize_calls_curator_then_client():
    await synthesizer.synthesize()

    mock_curator.curate_for_narrative_synthesis.assert_called_once()
    mock_client.analyze_with_context.assert_called_once()
    # What did it produce? Who knows!
```

**Problems:**
- Only verifies calls happened
- Says nothing about the outcome
- Would pass even if result is garbage

**Better:**
```python
# GOOD: Test the outcome
async def test_synthesize_produces_structured_brief():
    result = await synthesizer.synthesize()

    assert result["status"] == "success"
    assert "synthesis_data" in result
    assert result["synthesis_data"]["bottom_line"]
```

### Testing Exception Flow

```python
# BAD: Tests exception propagation (implementation)
async def test_api_error_raises_exception():
    mock_client.analyze.side_effect = APIError("fail")

    with pytest.raises(APIError):
        await synthesizer.synthesize()
```

**Problems:**
- Tests how errors flow, not what happens
- Couples test to exception type

**Better:**
```python
# GOOD: Tests error handling behavior
async def test_api_failure_returns_error_status():
    mock_client.analyze.side_effect = Exception("API Error")

    result = await synthesizer.synthesize()

    assert result["status"] == "error"
    assert "error" in result
```

---

## Refactoring Litmus Test

Ask yourself: **If I refactor the implementation without changing behavior, do tests break?**

| Refactoring | Good Test | Bad Test |
|-------------|-----------|----------|
| Rename private method | Still passes | Breaks |
| Change return type of internal | Still passes | Breaks |
| Split class into two | Still passes | Breaks |
| Change algorithm (same output) | Still passes | May break |

If your tests break on pure refactoring, they're testing implementation, not behavior.

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
   - Test name: `test_citation_map_overrides_claude_response` (behavior)
   - Not: `test_build_synthesis_task_with_citations_returns_tuple` (implementation)

2. **Decoupled from implementation details**
   - Test the contract, not the internals
   - If refactoring breaks tests but not behavior, tests are too coupled

3. **Follows Arrange-Act-Assert structure**
   ```python
   # Arrange: Set up preconditions
   articles = [{"id": 1, "title": "Test"}]

   # Act: Execute the behavior
   result = await synthesizer.synthesize()

   # Assert: Verify outcomes
   assert result["status"] == "success"
   ```

4. **Tests at boundaries, not internals**
   - Public API boundaries
   - Integration points (database, external APIs)
   - Error boundaries

5. **Meaningful assertions**
   - Assert on outcomes users care about
   - Not: `assert mock.called` (verifies plumbing)
   - Yes: `assert result["citation_map"]["1"]["title"] == "Expected Title"` (verifies value)

## Red Flags

- Test names that mirror method names exactly
- Assertions that only check mock call counts
- Tests that break when implementation changes but behavior doesn't
- Heavy use of `mock.assert_called_with()` on internal methods
- Tests that require knowing private method signatures
- Excessive mocking of the unit under test

## InsightWeaver-Specific Patterns

### Async Tests
```python
@pytest.mark.asyncio
async def test_synthesis_produces_valid_output(self, mock_curator, mock_client):
    # Arrange
    mock_curator.curate.return_value = {"articles": sample_articles}
    mock_client.analyze.return_value = valid_response_json

    # Act
    result = await synthesizer.synthesize_with_trust_verification()

    # Assert on behavior
    assert result["status"] == "success"
    assert "citation_map" in result["synthesis_data"]["metadata"]
```

### Mocking External Services
Mock at the boundary (Claude API, database), not internal methods:
```python
# Good: Mock the external boundary
mock_client.analyze_with_context = AsyncMock(return_value=response)

# Bad: Mock internal helper methods
mock_synthesizer._parse_synthesis_response = MagicMock()
```

### Testing Error Handling
Test that errors produce correct outcomes, not that specific exceptions flow:
```python
# Good: Behavior when API fails
async def test_synthesis_handles_api_failure_gracefully():
    mock_client.analyze.side_effect = Exception("API Error")
    result = await synthesizer.synthesize()
    assert result["status"] == "error"  # Behavior

# Bad: Testing exception plumbing
async def test_api_exception_propagates():
    mock_client.analyze.side_effect = APIError()
    with pytest.raises(APIError):  # Implementation detail
        await synthesizer.synthesize()
```

## Review Checklist

When reviewing tests, ask:

- [ ] Does the test name describe a behavior or outcome?
- [ ] Would this test break if I refactored without changing behavior?
- [ ] Am I testing what users/callers care about?
- [ ] Are assertions on outcomes rather than call patterns?
- [ ] Is mocking limited to true external boundaries?
- [ ] Can I understand what the code does just from reading tests?

## Questions to Ask

1. "If I renamed a private method, would this test break?"
2. "Does this test tell me what the feature does?"
3. "Am I testing the contract or the implementation?"
4. "Would a user of this code care about what I'm asserting?"

## Example Transformation

**Before (implementation-coupled):**
```python
def test_build_synthesis_task_with_citations_returns_tuple():
    result = synthesizer._build_synthesis_task_with_citations(articles, 2)
    assert isinstance(result, tuple)
    assert len(result) == 2
```

**After (behavior-focused):**
```python
def test_synthesis_includes_citation_map_matching_input_articles():
    """Citation map in output should reference the exact articles provided"""
    articles = [{"id": 1, "title": "Article One", "source": "Source A"}]

    result = await synthesizer.synthesize_with_trust_verification()

    citation_map = result["synthesis_data"]["metadata"]["citation_map"]
    assert citation_map["1"]["title"] == "Article One"
    assert citation_map["1"]["source"] == "Source A"
```

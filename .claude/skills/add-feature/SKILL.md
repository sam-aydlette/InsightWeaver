---
name: add-feature
description: Guide feature implementation following InsightWeaver principles. Use when adding new functionality, implementing user requests, or extending existing features.
allowed-tools: Read, Grep, Glob, Edit, Write, Bash(pytest:*), Bash(python -m pytest:*), Bash(git:*)
---

# Add Feature Skill

Implement features with minimal complexity and maximum clarity.

## Before Writing Code

### 1. Clarify Requirements
If the request is vague or has multiple interpretations:
- **Ask** - Don't assume business logic
- **Present options** - "This could mean X or Y. Which do you want?"
- **Scope it** - What's explicitly in/out?

### 2. Find Existing Patterns
```bash
# How is similar functionality implemented?
grep -r "similar_pattern" src/

# What's the structure of related modules?
ls -la src/related_module/
```

### 3. Plan Simply
- What's the **minimum** change needed?
- Can this extend existing code rather than add new files?
- Will this require changes in multiple places? (red flag for over-engineering)

## Implementation Rules

### Do
```python
# Use existing patterns
async def new_feature():
    # Follow established async patterns
    result = await existing_service.do_thing()
    return result

# Fail explicitly
if not valid:
    raise ValueError(f"Invalid input: {input}")

# Keep functions focused
def calculate_score(items):
    """One job: calculate score."""
    return sum(item.value for item in items)
```

### Don't
```python
# Don't add "flexibility" that wasn't requested
def process(data, format="json", validate=True, cache=False, retry=3):
    # Too many options for a simple feature

# Don't create abstractions for one use case
class AbstractProcessor(ABC):
    # Only one implementation? Just write the code.

# Don't add defensive code for impossible cases
if data is None:  # Can this actually be None here?
    data = []      # If not, don't handle it
```

## InsightWeaver Patterns

### Async Operations
```python
async def fetch_and_process():
    data = await collector.fetch()  # Await external calls
    return process(data)            # Sync processing is fine
```

### Claude API Integration
```python
# Always handle markdown-wrapped JSON
response = await client.analyze(prompt)
# Parser handles: ```json {...} ``` and raw JSON
data = parse_claude_response(response)
```

### Database Operations
```python
from src.database.connection import get_db

with get_db() as session:
    result = session.query(Model).filter(...).first()
    # Session auto-commits on success, rolls back on error
```

### Error Handling
```python
# Log with context, don't swallow
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"Operation failed for {context}: {e}")
    raise  # Or return meaningful error, never pass silently
```

## After Implementation

### 1. Write Behavior Tests
```python
# Test what it does, not how
async def test_feature_produces_expected_output():
    result = await new_feature(valid_input)
    assert result["status"] == "success"
    assert "expected_field" in result
```

### 2. Verify Simplicity
- Can you explain the change in one sentence?
- Would you be comfortable maintaining this in 6 months?
- Is there any code you added "just in case"? Remove it.

### 3. Check Integration
```bash
# Run related tests
pytest tests/module/ -v

# Run full check before committing
make check
```

## Size Guide

| Change Size | Expectation |
|-------------|-------------|
| Small | Single file, < 50 lines |
| Medium | 2-3 files, < 200 lines |
| Large | Pause and discuss approach first |

If a "simple feature" is turning into a large change, stop and reassess.

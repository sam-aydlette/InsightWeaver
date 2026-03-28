---
name: review-code
description: Review code changes for InsightWeaver patterns, simplicity, and correctness. Use when reviewing PRs, checking code quality, or before committing changes.
allowed-tools: Read, Grep, Glob, Bash(git diff:*), Bash(git log:*), Bash(git show:*)
---

# Code Review Skill

Review code against InsightWeaver standards. Prioritize correctness and simplicity.

## Core Principles (from CLAUDE.md)

1. **Simple over complex** - Is there a simpler way?
2. **Fail fast** - No quick fixes or hidden fallbacks
3. **No assumptions** - Business logic ambiguities should be clarified, not guessed
4. **No over-engineering** - Only build what's needed now

## Review Checklist

### Correctness
- [ ] Does it do what was requested? Nothing more?
- [ ] Are edge cases handled or explicitly out of scope?
- [ ] No silent failures or swallowed exceptions?

### Simplicity
- [ ] Could this be done with less code?
- [ ] Any premature abstractions? (helpers for one-time operations)
- [ ] Any "just in case" code that isn't needed?

### InsightWeaver Patterns
- [ ] Async functions use `async/await` properly
- [ ] Claude API responses are parsed defensively (JSON may be wrapped in markdown)
- [ ] Database operations use context managers (`with get_db() as session`)
- [ ] Errors logged with context, not swallowed

### Security
- [ ] No hardcoded secrets or API keys
- [ ] User input validated at boundaries
- [ ] No command injection vectors

## Red Flags

**Stop and question if you see:**

```python
# Over-engineering
class AbstractFactoryBuilder:  # For a one-time operation

# Hidden failures
except Exception:
    pass  # Swallowed error

# Quick fix
if data is None:
    data = {}  # Masking a real bug

# Assumption
# Assuming user wants X format
result = format_as_json(data)  # Why not ask?

# Backwards compatibility hack
old_field = new_field  # Just delete the old code
```

## Questions to Ask

1. "What's the simplest version of this that works?"
2. "If this fails, will we know why?"
3. "Is this solving a real problem or a hypothetical one?"
4. "Would a new contributor understand this?"

## When Reviewing Changes

```bash
# See what changed
git diff --stat

# Review specific file
git diff path/to/file.py

# Check recent context
git log --oneline -10
```

Focus on:
- **New code**: Does it follow patterns?
- **Changed code**: Is the change minimal and focused?
- **Deleted code**: Good! Less is more.

## Approve When

- Code does what was asked
- No obvious bugs or security issues
- Complexity is justified
- Tests cover the behavior (not implementation)

# Contributing to InsightWeaver

Thank you for your interest in contributing to InsightWeaver! This guide will help you get started.

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)

## Development Setup

### Prerequisites

- Python 3.11 or higher
- pip and virtualenv
- Git

### Initial Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/insightweaver.git
   cd insightweaver
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies**
   ```bash
   make install-dev
   # Or manually:
   pip install -r requirements-dev.txt
   pip install -e .
   pre-commit install
   ```

   This installs the package in editable mode (`-e`) so you can test CLI changes immediately.

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

5. **Set up database**
   ```bash
   make db-migrate
   ```

6. **Run tests to verify setup**
   ```bash
   make test
   ```

## Project Structure

```
insightweaver/
├── src/                      # Source code
│   ├── cli/                  # Command-line interface
│   ├── collectors/           # RSS feed collectors
│   ├── context/              # Context and narrative synthesis
│   ├── trust/                # Trust verification system
│   ├── forecast/             # Forecasting engine
│   ├── database/             # Database models and migrations
│   └── utils/                # Utility functions
├── tests/                    # Automated test suite (pytest)
│   ├── conftest.py           # Shared test fixtures
│   └── trust/                # Trust module tests
├── scripts/                  # Manual test scripts and utilities
│   ├── test_collectors.py   # Manual collector testing
│   ├── test_semantic_memory.py  # Manual memory testing
│   └── scheduled_report.py  # Scheduled task runner
├── config/                   # Configuration files
└── docs/                     # Documentation

```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Your Changes

Follow the [Code Standards](#code-standards) below when writing code.

### 3. Run Quality Checks

Before committing, run all checks:

```bash
make check  # Runs lint + typecheck + test
```

Or run individually:
```bash
make lint       # Run linter
make format     # Auto-format code
make typecheck  # Run type checker
make test       # Run tests
```

### 4. Commit Your Changes

Pre-commit hooks will automatically run on each commit:

```bash
git add .
git commit -m "feat: add new feature"
```

Use conventional commit messages:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Test changes
- `refactor:` Code refactoring
- `chore:` Maintenance tasks

### 5. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub.

## Code Standards

### Python Style

- Follow PEP 8
- Use type hints for function signatures
- Maximum line length: 100 characters
- Use ruff for linting and formatting

### Code Organization

- Keep functions focused and single-purpose
- Avoid files longer than 300 lines
- Reuse existing functionality
- Add docstrings to all public functions and classes

### Naming Conventions

- **Functions/Variables**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private members**: `_leading_underscore`

### Example

```python
from typing import Optional

class FactVerifier:
    """Verifies claims against authoritative sources."""

    def verify_claim(
        self,
        claim: str,
        sources: Optional[list[str]] = None
    ) -> dict:
        """
        Verify a factual claim.

        Args:
            claim: The claim to verify
            sources: Optional list of authoritative sources

        Returns:
            Dictionary containing verification result
        """
        # Implementation
        pass
```

## Testing

### Writing Tests

- Place tests in `tests/` directory
- Use `test_*.py` naming convention
- Follow AAA pattern: Arrange, Act, Assert
- Use fixtures from `conftest.py` for common setup
- Mock external dependencies (API calls, file I/O)

### Test Example

```python
import pytest
from src.trust.fact_verifier import FactVerifier

class TestFactVerifier:
    """Test fact verification functionality."""

    @pytest.mark.asyncio
    async def test_verify_simple_claim(self, fact_verifier):
        """Test verification of a simple factual claim."""
        # Arrange
        claim = "Paris is the capital of France"

        # Act
        result = await fact_verifier.verify_claim(claim)

        # Assert
        assert result["verdict"] == "VERIFIED"
        assert result["confidence"] > 0.9
```

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make coverage

# Run specific test file
pytest tests/trust/test_fact_verifier.py -v

# Run specific test
pytest tests/trust/test_fact_verifier.py::TestFactVerifier::test_verify_simple_claim -v
```

### Coverage Requirements

- Aim for 85%+ overall coverage
- New features should have 90%+ coverage
- Critical components (trust, verification) should have 95%+ coverage

### Manual Testing Scripts

Manual test scripts belong in `scripts/` directory, NOT in `tests/`:

- **tests/**: Automated unit/integration tests using pytest
- **scripts/**: Manual testing scripts, utilities, and one-off tasks

Example manual test script:
```python
#!/usr/bin/env python3
"""Manual test script for feature X"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.your_module import YourClass

def main():
    # Manual testing logic
    pass

if __name__ == "__main__":
    main()
```

## Database Migrations

InsightWeaver uses a custom migration system located in `src/database/migrations/`.

### Running Migrations

```bash
# Apply migrations
make db-migrate

# Rollback migrations
make db-migrate-down

# Reset database (WARNING: deletes all data)
make db-reset
```

### Creating Migrations

Migrations are Python modules in `src/database/migrations/` with `upgrade()` and `downgrade()` functions:

```python
"""
Migration: Add New Tables
Description of what this migration does
"""
from src.database.connection import engine
from src.database.models import YourModel

def upgrade():
    """Apply migration"""
    YourModel.__table__.create(engine, checkfirst=True)
    print("✓ your_table created")

def downgrade():
    """Rollback migration"""
    YourModel.__table__.drop(engine, checkfirst=True)
    print("✓ your_table dropped")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "down":
        downgrade()
    else:
        upgrade()
```

## Documentation

### Code Documentation

- Add docstrings to all public functions and classes
- Use Google-style docstrings
- Include parameter types and return types
- Provide usage examples for complex functions

### Project Documentation

- Update README.md for user-facing changes
- Update this CONTRIBUTING.md for development workflow changes
- Add comments for complex logic (explain "why", not "what")

## Pull Request Process

### Before Submitting

1. **Ensure all checks pass**
   ```bash
   make check
   ```

2. **Update tests**
   - Add tests for new features
   - Update tests for modified behavior
   - Ensure coverage doesn't decrease

3. **Update documentation**
   - Update docstrings
   - Update README if needed
   - Add comments for complex logic

4. **Clean commit history**
   - Squash fixup commits if needed
   - Use meaningful commit messages

### PR Guidelines

1. **Title**: Use conventional commit format
   ```
   feat: add claim verification timeout
   fix: resolve race condition in parallel fetcher
   ```

2. **Description**: Include
   - Summary of changes
   - Motivation and context
   - Testing performed
   - Breaking changes (if any)

3. **Size**: Keep PRs focused
   - Prefer smaller, focused PRs over large ones
   - One feature/fix per PR
   - Large refactors should be discussed first

### Review Process

1. Automated CI checks must pass
2. At least one maintainer approval required
3. Address review feedback promptly
4. Squash and merge when approved

## Getting Help

- **Questions**: Open a GitHub Discussion
- **Bugs**: Open a GitHub Issue
- **Features**: Open a GitHub Issue with proposal

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on the code, not the person
- Help others learn and grow

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to InsightWeaver!

# Context Modules

Context modules provide domain-specific background knowledge to Claude without consuming article tokens. This allows richer, more informed analysis by giving Claude reference context that doesn't change frequently.

## Directory Structure

```
context_modules/
├── core/                    # Core system configuration
│   └── (reserved for future use)
├── domain_knowledge/        # Professional domain background
│   ├── cybersecurity_context.json
│   ├── local_governance_context.json
│   └── economic_indicators_context.json
├── historical/              # Historical patterns and memory
│   └── (auto-generated)
└── supplemental/            # Additional reference data
    └── (calendar events, metrics, etc.)
```

## Module Structure

Each module is a JSON file with this structure:

```json
{
  "module_name": "unique_identifier",
  "description": "What this module provides",
  "version": "1.0",
  "priority": "high|medium|low",
  "content_sections": {
    "section_name": {
      "description": "Section purpose",
      "content": [
        "Bullet point 1",
        "Bullet point 2"
      ]
    }
  },
  "key_metrics_baselines": {
    "category": {
      "metric": "value"
    }
  },
  "reference_links": {
    "Link Name": "URL"
  },
  "last_updated": "YYYY-MM-DD",
  "token_estimate": 500
}
```

## Module Types

### Domain Knowledge
**Purpose:** Background context for professional domains
**Examples:** Cybersecurity frameworks, local government structure, economic indicators
**Token Budget:** 10,000-15,000 tokens total
**Priority:** High - always included

### Historical
**Purpose:** Patterns from past analyses
**Examples:** Synthesis summaries, identified trends over time
**Token Budget:** 10,000-15,000 tokens
**Priority:** Medium - included when relevant

### Supplemental
**Purpose:** Timely reference data
**Examples:** Upcoming events, calendar deadlines, current metrics
**Token Budget:** 15,000-20,000 tokens
**Priority:** Medium - context-dependent

## Priority Levels

- **High:** Always included, critical background knowledge
- **Medium:** Included if token budget allows
- **Low:** Included only if significant budget headroom

## Token Estimates

Each module should estimate its token cost. Rough guideline:
- 1 token ≈ 4 characters
- 250 tokens ≈ 1 paragraph
- 500 tokens ≈ 1/2 page
- 1000 tokens ≈ 1 page

## Usage in Code

```python
from src.context.module_loader import ContextModuleLoader

# Load all modules
loader = ContextModuleLoader()
modules_by_type = loader.load_all_modules()

# Get domain knowledge modules
domain_modules = modules_by_type['domain_knowledge']

# Format for Claude context
context_str = loader.format_for_claude_context(
    domain_modules,
    max_tokens=15000
)
```

## Creating New Modules

1. Create JSON file in appropriate subdirectory
2. Follow the structure above
3. Estimate token count (length / 4)
4. Set appropriate priority
5. Test with `python -m src.context.module_loader` (future CLI)

## Maintenance

- **Update frequency:** Domain knowledge: quarterly, Supplemental: weekly/daily
- **Review:** Check accuracy every 3-6 months
- **Token optimization:** Keep modules concise, bullet points preferred
- **Versioning:** Increment version number when making significant changes

## Best Practices

1. **Be specific:** "Fairfax County budget: $5.08B" not "County has large budget"
2. **Use bullets:** Easier for Claude to parse
3. **Include baselines:** Reference points for comparison
4. **Cite sources:** Add reference_links for credibility
5. **Estimate accurately:** Helps token budget management
6. **Prioritize ruthlessly:** Not everything needs to be high priority

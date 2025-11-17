# Configuration Guide: Where to Put What

## Two Main Configuration Files

### 1. `config/user_profile.json` - YOUR IDENTITY
**Edit frequency:** 1-2 times per year (when major life changes happen)

**Contains:**
- Geographic scope (where you live, areas of interest)
- Professional domains (your industry, job role, skills)
- Civic interests (policy areas you care about)
- Content preferences (what to include/exclude)
- Feed preferences (what sources to pull)

**Edit this when:**
- ✓ You move to a new city/state
- ✓ You change careers or industries
- ✓ Your civic interests shift significantly
- ✓ You want to exclude/include new content types

**Example:**
```json
{
  "geographic_context": {
    "primary_location": {
      "city": "Fairfax",
      "state": "Virginia"
    }
  },
  "professional_context": {
    "job_role": "Cybersecurity Engineer",
    "professional_domains": ["cybersecurity", "AI/ML"]
  }
}
```

---

### 2. `config/context_modules/core/decision_context.json` - YOUR ACTIVE DECISIONS
**Edit frequency:** Monthly (as decisions come and go)

**Contains:**
- Active decisions you're making RIGHT NOW
- Timeline for each decision
- What signals are relevant to each decision
- Decision criteria (what you're optimizing for)

**Edit this when:**
- ✓ You start a job search
- ✓ You're timing a major purchase (house, car)
- ✓ You're monitoring something time-sensitive
- ✓ You complete a decision (remove it!)
- ✓ Decision criteria change (salary target, timeline shift)

**Example:**
```json
{
  "active_decisions": [
    {
      "decision_id": "career_2025_q4",
      "decision": "Career advancement - evaluating opportunities",
      "timeline": "Next 3-6 months",
      "relevant_signals": [
        "job market trends",
        "salary trends",
        "clearance processing times"
      ],
      "decision_criteria": [
        "Compensation: target $200k+",
        "Work-life balance: remote preferred"
      ]
    }
  ]
}
```

---

## Quick Decision: Which File?

**Ask yourself:** "Will this change in the next 3-6 months?"

- **YES** → Put it in `decision_context.json`
  - Examples: Job search, house purchase, school choice

- **NO** → Put it in `user_profile.json`
  - Examples: Your profession, where you live, civic interests

---

## Common Scenarios

### Scenario: Starting a job search
**Action:** Add to `decision_context.json`
```json
{
  "decision_id": "job_search_2025",
  "decision": "Looking for senior cybersecurity role",
  "timeline": "Next 6 months",
  "relevant_signals": [
    "hiring trends",
    "salary benchmarks",
    "skills in demand"
  ]
}
```

### Scenario: Job search complete, got hired
**Action:** Remove from `decision_context.json`
- Delete the entire `job_search_2025` decision block

### Scenario: Moved from DC to Richmond
**Action:** Update `user_profile.json`
```json
{
  "geographic_context": {
    "primary_location": {
      "city": "Richmond",  // Changed
      "state": "Virginia"
    }
  }
}
```
**Also update:** `decision_context.json` if your active decisions changed due to the move

### Scenario: Changed from "exclude sports" to "include soccer"
**Action:** Update `user_profile.json`
```json
{
  "content_preferences": {
    "excluded_topics": [
      "celebrity news",
      "entertainment gossip"
    ]
    // Removed "sports" from excluded list
  }
}
```

---

## How InsightWeaver Uses These Files

### User Profile → Feed Selection
Your `user_profile.json` controls **which RSS feeds** are loaded:
- Geographic interests → pulls local/regional feeds
- Professional domains → pulls industry-specific feeds
- Excluded topics → filters out unwanted content

### Decision Context → Analysis Focus
Your `decision_context.json` tells Claude **what to pay attention to**:
- "This mortgage rate change affects your housing decision"
- "Clearance processing delays impact your job search timeline"
- "FCPS policy change relevant to your school monitoring"

---

## Pro Tips

1. **Don't delete decisions, archive them**
   - Add `"status": "completed"` or `"status": "on_hold"`
   - Helpful to see past decision patterns

2. **Be specific in decision criteria**
   - BAD: "Good salary"
   - GOOD: "Compensation: target $200k+ range"

3. **Update timelines regularly**
   - If "Next 3 months" was set 6 months ago, update it!

4. **Use watching_topics for fuzzy monitoring**
   - Not a hard decision, but want to stay aware
   - Example: "AI regulation (affects career trajectory)"

5. **Review monthly**
   - First Monday of each month: review `decision_context.json`
   - Remove completed decisions
   - Update timelines
   - Add new decisions

---

## File Locations Reference

```
config/
├── user_profile.json              # YOUR IDENTITY (edit yearly)
├── user_profile.example.json      # Template/backup
└── context_modules/
    └── core/
        ├── decision_context.json         # YOUR DECISIONS (edit monthly)
        └── decision_context.example.json # Template/backup
```

---

## Questions?

**"Should I put X in user_profile or decision_context?"**
→ Ask: "Will this be true a year from now?"
- YES → user_profile.json
- NO → decision_context.json

**"I have too many decisions, should I add them all?"**
→ Focus on top 3-5 most time-sensitive decisions
→ Use "watching_topics" for general monitoring

**"Can I have multiple decision_context files?"**
→ Not currently, but you can use decision_id to organize
→ Example: `career_2025_q4`, `housing_2025`, `education_ongoing`

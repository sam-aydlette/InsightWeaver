# Civic Engagement Intelligence Implementation

## Overview
This document describes the Civic Engagement Intelligence Package implementation for InsightWeaver, which enhances the system's ability to collect, prioritize, and synthesize civic content relevant to local government, elections, zoning, legislation, and civic participation in Northern Virginia.

## Implementation Status
**Completed**: Week 1-2 (Local Data Collection + Civic Context Module)
**Date**: 2025-11-18
**Next Phase**: Civic Analysis Enhancements (Week 2-3)

## RSS Feed Collection

### Feed Sources (14 Validated Feeds)
Located in: `config/feeds/domains/civic_engagement.json`

**High-Priority Feeds (Relevance Score 0.90+)**:
- Fairfax County Public Schools News (0.96) - School board meetings, policy changes, budget
- Virginia Mercury (0.95) - State legislation, General Assembly, policy analysis
- Inside Nova (0.94) - Investigative local government coverage, zoning applications
- FFXnow (0.92) - Breaking Fairfax County news, development, meetings
- Greater Greater Washington (0.91) - Housing policy, transportation, land use, zoning

**Regional Coverage**:
- Washington Post Local (DC/MD/VA)
- ARLnow (Arlington)
- ALXnow (Alexandria)
- Potomac Local (Prince William/Stafford)
- Prince William Living
- What's Up Woodbridge
- WTOP Virginia
- DCist
- The Zebra (Arlington)

### Performance Metrics
- **Feeds Configured**: 14
- **Articles Per Fetch**: ~40
- **Active Publishing Feeds**: 4 (others validated but lower frequency)
- **Geographic Coverage**: Fairfax, Arlington, Alexandria, Prince William, Loudoun
- **Content Types**: Local news, school board, state legislation, zoning, development, elections

### Feed Selection Strategy
**Challenge**: Fairfax County government RSS feeds are blocked (403 Forbidden) by bot protection.

**Solution**: Rely on local news outlets that cover government activities:
- News outlets are designed for programmatic consumption
- Comprehensive coverage of all civic topics (meetings, bills, zoning, elections)
- Avoids legal/technical issues with scraping government websites
- Provides context and analysis beyond raw government data

## Civic Context Module

### Location
`config/context_modules/domain_knowledge/civic_engagement_context.json`

### Purpose
Provides Claude with civic engagement background knowledge to recognize and prioritize civic content during analysis and synthesis.

### Content Sections
1. **Local Governance Structure**: Key decision-making bodies (Board of Supervisors, School Board, Planning Commission)
2. **Electoral Districts**: Voting districts and representation structure
3. **Key Civic Issues**: Ongoing issues (school funding, housing, transportation, development, taxes)
4. **Civic Participation Touchpoints**: How residents engage with government
5. **High-Priority Signals**: Events indicating important civic developments
6. **Regional Context**: Northern Virginia regional governance (NVRC, MWCOG, WMATA)
7. **State Legislative Impact**: How Virginia General Assembly affects local governance

### Civic Keywords
**High Priority**: Board of Supervisors, School Board, Planning Commission, public hearing, zoning application, rezoning, election, General Assembly, legislation, ordinance

**Medium Priority**: supervisor, school boundary, FCPS, transportation project, affordable housing, Metro, public comment

**Contextual**: neighborhood association, civic association, parent-teacher, commission appointment

### Integration
- Automatically loaded by existing `ContextModuleLoader`
- Priority level: HIGH
- Estimated token usage: 1,200 tokens
- No code changes required (uses existing infrastructure)

## How Civic Content is Recognized

### 1. Feed Matching (Collection Phase)
- Feeds tagged with `domain_tags: ["civic_engagement"]`
- Geographic tags match user profile location (northern_virginia, fairfax)
- Specialty tags (school_board, zoning, legislation) boost relevance score
- Matched feeds automatically included in collection cycle

### 2. Context-Aware Analysis (Analysis Phase)
- Civic context module loaded before Claude API calls
- High-priority civic keywords boost article importance
- Governance structure knowledge helps identify key decision-makers
- Civic participation touchpoints highlight actionable opportunities

### 3. Prioritization (Curation Phase)
- Articles matching civic keywords scored higher
- Content about high-priority signals (zoning applications, meeting agendas, ordinances) prioritized
- Regional vs. local scope affects relevance to user

## Current Performance
- **Data Collection**: 40 civic articles per fetch cycle
- **Content Quality**: Mix of breaking news, investigative reporting, and policy analysis
- **Geographic Relevance**: Strong Fairfax County focus with regional Northern Virginia coverage
- **Topic Coverage**: School board, zoning, state legislation, elections, local government meetings

## Civic Analysis Enhancements - COMPLETED

### Week 2-3 Goals ✅
1. Enhanced fact extraction to capture civic-specific facts:
   - Added `civic_event` fact type (90-day retention)
   - Added `policy_position` fact type (180-day retention)
   - Updated extraction prompt to specifically request civic facts
   - Enhanced historical context to prioritize civic events

2. Updated synthesis prompts to recognize civic content patterns:
   - Added civic engagement opportunities to Local analysis section
   - Enhanced Priority Events section to explicitly request civic events with dates
   - Added government decisions to analysis requirements

3. Civic articles now properly prioritized through enhanced perspective

### Week 3-4: Civic Dashboard in Email Reports - COMPLETED

**Email Template Enhancement:**
- Added dedicated "Civic Engagement Opportunities" section to email reports
- Blue-highlighted section appears after Bottom Line, before Trends
- Filters Priority Events for civic keywords (meeting, hearing, board, election, zoning, etc.)
- Shows civic events in clean card format with:
  - Event name and date
  - Why it matters
  - How to participate section
- Only appears when civic events are detected

**Files Modified:**
- `src/newsletter/templates.py`:
  - Added `.civic-section` CSS styles (blue theme)
  - Added `_render_civic_engagement()` method
  - Integrated into main template flow

## Security Considerations
- No web scraping (avoids legal issues)
- Only public RSS feeds designed for consumption
- User profile and context modules excluded from version control (`.gitignore`)
- No API keys required for civic feeds

## References
- Feed configuration: `config/feeds/domains/civic_engagement.json`
- Context module: `config/context_modules/domain_knowledge/civic_engagement_context.json`
- Health monitoring: Civic feeds tracked in system health metrics
- Original plan: `docs/civic_engagement_plan.md`

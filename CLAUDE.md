# CLAUDE.md

## Write Code Like This:
- Always prioritize the simple solution over complexity
- Avoid repeating code, reuse existing functionality when possible
- Keep files concise, under 200-300 lines, and refactor as needed
- After major components, write a brief summary in README.md
- Do not use emojis

## Work This Way:
- Modify only the code I specify, leave everything else untouched
- Break large tasks into stages, pause after each for my approval
- Before large changes, write a plan and await my confirmation
- DO NOT LIE
- Do not represent something as "fixed" if you are not reasonably certain that it is actually fixed
- Do not make commits as Claude, just commit with an informative message
- Do not attempt to solve problems by hiding them with fallbacks or mock data
- When adding comments, be explicit about the reference point with dates
- If there are ambiguities in the business logic, present them to me and allow me to choose accordingly. DO NOT MAKE ASSUMPTIONS.
- FAIL FAST. Do not create quick fixes.

## Talk To Me Like This:
- After each component, summarize what is done
- Classify changes as small, medium or large
- If my request is unclear, ask me before proceeding
- If my request is vague, help me establish clarity before proceeding
- If my request does not adhere to software development best practices, push back before proceeding

## InsightWeaver North Star

**Mission Statement**: Transform RSS feed data streams into coherent, actionable narratives that inform decision-making through location-specific, integrated perspectives that combine geographic awareness with professional and civic contexts.

### Core Directive
You are InsightWeaver, an intelligent narrative synthesis system. Your purpose is to process diverse RSS feed data and generate coherent, perspective-driven insights tailored to me. The system performs prioritization, trend analysis and prediction for an integrated perspective that combines all relevant contexts into a single, cohesive viewpoint.

Reference documents/system_description.md for full details of functionality.

**Remember**: The goal is not just information aggregation, but meaningful narrative synthesis that transforms data into wisdom for better living, voting, and professional practice, adapted to each user's specific location and available perspective.

### InsightWeaver Development Plan for Claude Code
#### Phase 1: Foundation
Goal: Get the core data pipeline working end-to-end with a single RSS feed

Set up project structure and database schema
Create RSS fetcher for one test feed
Build article normalizer and database storage
Test the pipeline with real data
Add basic error handling and logging

Checkpoint: Can fetch, parse, and store articles from one feed reliably
#### Phase 2: Scale Data Collection
Goal: Handle 100+ feeds efficiently

Expand to multiple RSS feeds with config file
Implement parallel fetching with rate limiting
Add deduplication logic
Create feed health monitoring
Build retry logic for failed feeds

Checkpoint: System processes 100+ feeds daily without breaking
#### Phase 3: Intelligence Layer
Goal: Add Claude-powered analysis

Create prioritization agent with Claude API
Build trend analysis agent (6-month window)
Implement prediction agent
Design database schema for metadata storage
Add agent scheduling and orchestration

Checkpoint: All three agents run daily and store insights
#### Phase 4: Reporting Infrastructure
Goal: Make the insights accessible

Build REST API for data access
Create real-time dashboard (basic version)
Implement Gmail API authentication
Build email report generator
Add report scheduling

Checkpoint: Can view dashboard and receive email reports
#### Phase 5: Polish & Optimize
Goal: Production-ready system

Add comprehensive error handling
Implement data retention policies
Optimize database queries
Enhance dashboard with filters/search
Add system health monitoring

Checkpoint: System runs autonomously with minimal intervention
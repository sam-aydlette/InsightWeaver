# Deep Context Enhancement: Comprehensive Implementation Plan

**Document Version**: 1.0
**Created**: 2025-01-17
**Status**: Planning
**Estimated Duration**: 6-8 weeks
**Token Budget Impact**: +5k tokens (81k/200k total)

---

## Executive Summary

This plan implements three integrated systems to achieve deeper, more meaningful synthesis:
1. **Semantic Memory** - Historical context from persistent facts
2. **Perception Pipeline** - Relationship extraction and pattern detection
3. **Reflection Loop** - Self-critique for analytical depth

**Core Principle**: These systems work together as an integrated memory-perception-reasoning cycle, not isolated features.

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Implementation Phases](#implementation-phases)
3. [Milestone Definitions](#milestone-definitions)
4. [Testing Strategy](#testing-strategy)
5. [Success Metrics](#success-metrics)
6. [Technical Specifications](#technical-specifications)
7. [Validation Criteria](#validation-criteria)
8. [Rollback Strategy](#rollback-strategy)
9. [Documentation Standards](#documentation-standards)

---

## System Architecture

### Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    ARTICLE COLLECTION                        │
│                    (Existing Pipeline)                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              PERCEPTION PIPELINE (NEW)                       │
│  Extract: Entities, Relationships, Events, Patterns         │
│  Store: EntityRelationships table                           │
│  Output: relationship_graph, cross_article_patterns         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              SEMANTIC MEMORY (NEW)                           │
│  Retrieve: Historical facts relevant to current articles    │
│  Output: historical_context (last 90 days of facts)         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              CONTEXT CURATOR (ENHANCED)                      │
│  Combine: Articles + History + Relationships + Patterns     │
│  Output: enhanced_context                                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              SYNTHESIS WITH REFLECTION (NEW)                 │
│  Step 1: Initial synthesis using enhanced_context           │
│  Step 2: Self-critique (depth evaluation)                   │
│  Step 3: Refinement (if depth_score < 8)                    │
│  Output: refined_synthesis + reflection_metadata            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              FACT EXTRACTION (NEW)                           │
│  Extract structured facts from synthesis output             │
│  Store: MemoryFacts table for future retrievals             │
│  Creates feedback loop for next synthesis                   │
└─────────────────────────────────────────────────────────────┘
```

### Component Dependencies

```
Phase 1 (Reflection) → Independent, can deploy immediately
Phase 2 (Memory)     → Depends on Reflection (extracts facts from refined synthesis)
Phase 3 (Perception) → Independent, but synergizes with Memory
Integration          → Requires all three phases complete
```

---

## Implementation Phases

### Phase 1: Reflection Loop (Week 1-2)

**Objective**: Enable self-critique and refinement for deeper analysis

**Deliverables**:
- `src/context/reflection_engine.py` - Reflection logic
- Enhanced `src/context/synthesizer.py` - Integrate reflection loop
- Configuration flag: `enable_reflection` in settings
- Reflection metadata stored in `NarrativeSynthesis.synthesis_data`

**Success Criteria**:
- Initial synthesis generates normally
- Reflection produces depth_score (0-10) and specific improvement areas
- Refined synthesis demonstrates measurably deeper analysis (see Testing Strategy)
- Process completes within 3-5 minutes (2min initial + 1-3min refinement)

**API Call Budget**:
- Initial synthesis: 1 call (~50k tokens input, 5k tokens output)
- Reflection: 1 call (~6k tokens input, 1k tokens output)
- Refinement: 1 call (~52k tokens input, 5k tokens output)
- **Total: 3 calls per synthesis** (vs 1 currently)

---

### Phase 2: Semantic Memory (Week 3-4)

**Objective**: Build persistent fact storage and historical context retrieval

**Deliverables**:
- Database migration: Add `MemoryFacts` table
- `src/context/semantic_memory.py` - Fact extraction and retrieval
- Enhanced `src/context/curator.py` - Integrate historical context
- CLI tool: `python main.py --memory-stats` to view fact database

**Success Criteria**:
- Facts extracted from each synthesis (5-10 facts per synthesis)
- Historical context retrieved based on current article topics
- Synthesis demonstrates temporal awareness ("compared to 3 months ago...")
- Fact database grows over time (target: 100+ facts after 10 syntheses)

**Database Schema**:
```sql
CREATE TABLE memory_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_type VARCHAR(50),        -- 'metric', 'trend', 'relationship', 'decision'
    subject VARCHAR(200),          -- 'Fairfax County unemployment'
    predicate VARCHAR(100),        -- 'rate'
    object TEXT,                   -- '2.3%'
    temporal_context VARCHAR(50),  -- '2025-01-15' or 'Q4 2024'
    confidence FLOAT,              -- 0.0-1.0
    source_synthesis_id INTEGER,   -- FK to narrative_synthesis.id
    created_at DATETIME,
    expires_at DATETIME,           -- NULL for evergreen facts
    metadata JSON,                 -- Additional context
    FOREIGN KEY (source_synthesis_id) REFERENCES narrative_synthesis(id)
);

CREATE INDEX idx_memory_facts_subject ON memory_facts(subject);
CREATE INDEX idx_memory_facts_temporal ON memory_facts(temporal_context);
```

---

### Phase 3: Perception Pipeline (Week 5-6)

**Objective**: Extract entities, relationships, and cross-article patterns

**Deliverables**:
- Database migration: Add `EntityRelationships` table
- `src/processors/perception_pipeline.py` - Entity/relationship extraction
- Enhanced `src/pipeline/orchestrator.py` - Run perception before synthesis
- Relationship graph builder and pattern detector

**Success Criteria**:
- Entities extracted from articles (people, orgs, locations, events)
- Relationships identified (entity-relationship-entity triples)
- Cross-article patterns detected (entity appears in 3+ articles)
- Synthesis uses relationship graph to identify non-obvious connections

**Database Schema**:
```sql
CREATE TABLE entity_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_1 VARCHAR(200),
    entity_2 VARCHAR(200),
    relationship_type VARCHAR(100),  -- 'opposed', 'sponsored', 'collaborated_with'
    confidence FLOAT,
    source_article_ids TEXT,         -- JSON array of article IDs
    first_observed DATETIME,
    last_observed DATETIME,
    occurrence_count INTEGER DEFAULT 1,
    metadata JSON
);

CREATE INDEX idx_entity_rel_e1 ON entity_relationships(entity_1);
CREATE INDEX idx_entity_rel_e2 ON entity_relationships(entity_2);
CREATE INDEX idx_entity_rel_type ON entity_relationships(relationship_type);
```

---

### Phase 4: Integration & Optimization (Week 7-8)

**Objective**: Integrate all systems, optimize performance, validate end-to-end

**Deliverables**:
- Full integration in `src/context/curator.py`
- Performance optimization (caching, batching, parallel processing)
- Comprehensive testing suite
- Documentation and user guide

**Success Criteria**:
- All three systems work together seamlessly
- End-to-end pipeline completes in <10 minutes (maintain current SLA)
- Token usage stays within budget (81k/200k)
- Synthesis quality demonstrably improved (see Success Metrics)

---

## Milestone Definitions

### M1: Reflection Loop Functional (End of Week 2)

**Acceptance Criteria**:
- [ ] `ReflectionEngine` class implemented with `evaluate_depth()` method
- [ ] `ContextSynthesizer.synthesize_with_reflection()` works end-to-end
- [ ] Configuration flag `enable_reflection` toggles feature on/off
- [ ] Reflection metadata stored in database
- [ ] Unit tests pass (see Testing Strategy)
- [ ] Manual test: Run synthesis with/without reflection, verify output quality difference

**Validation Test**:
```bash
# Test 1: Baseline synthesis
python main.py --synthesize --no-reflection --output baseline.json

# Test 2: Reflection-enhanced synthesis
python main.py --synthesize --reflection --output enhanced.json

# Expected: enhanced.json shows deeper causal analysis, historical comparisons
```

**Deliverables Checklist**:
- [ ] Code: `src/context/reflection_engine.py`
- [ ] Code: Updated `src/context/synthesizer.py`
- [ ] Config: `enable_reflection` flag in `config/settings.py`
- [ ] Tests: `tests/test_reflection_engine.py`
- [ ] Documentation: `docs/reflection_loop.md`

---

### M2: Semantic Memory Operational (End of Week 4)

**Acceptance Criteria**:
- [ ] `MemoryFacts` table created and populated
- [ ] `SemanticMemory` class extracts facts from synthesis
- [ ] Historical context retrieval works (finds relevant facts for current articles)
- [ ] Context curator integrates historical context
- [ ] Fact database contains 10+ facts after 2 synthesis runs
- [ ] Synthesis demonstrates temporal awareness

**Validation Test**:
```bash
# Test 1: Run initial synthesis (seed facts)
python main.py --synthesize --output run1.json

# Test 2: Check fact extraction
python main.py --memory-stats
# Expected: 5-10 facts extracted

# Test 3: Run second synthesis (should reference run1 facts)
python main.py --synthesize --output run2.json
# Expected: run2.json contains phrases like "compared to last week" or "continuing the trend from..."

# Test 4: Query facts
python main.py --query-memory --subject "unemployment"
# Expected: Returns relevant unemployment facts with timestamps
```

**Deliverables Checklist**:
- [ ] Database: Migration script for `MemoryFacts` table
- [ ] Code: `src/context/semantic_memory.py`
- [ ] Code: Updated `src/context/curator.py`
- [ ] CLI: `--memory-stats` and `--query-memory` commands
- [ ] Tests: `tests/test_semantic_memory.py`
- [ ] Documentation: `docs/semantic_memory.md`

---

### M3: Perception Pipeline Active (End of Week 6)

**Acceptance Criteria**:
- [ ] `EntityRelationships` table created and populated
- [ ] `PerceptionPipeline` class extracts entities and relationships from articles
- [ ] Relationship graph builder aggregates across articles
- [ ] Cross-article pattern detector identifies connections
- [ ] Synthesis uses relationship graph in analysis
- [ ] At least 10 relationships detected in typical article batch

**Validation Test**:
```bash
# Test 1: Run perception pipeline on article batch
python main.py --run-perception --input articles.json --output perception_results.json

# Test 2: View relationship graph
python main.py --show-relationships --format graph
# Expected: Visual or text representation of entity relationships

# Test 3: Run full synthesis with perception
python main.py --synthesize --with-perception --output synthesis.json
# Expected: Synthesis mentions cross-article patterns like "Entity X appears in 3 articles, connecting topics Y and Z"

# Test 4: Query relationships
python main.py --query-relationships --entity "Senator Smith"
# Expected: Returns all relationships involving Senator Smith
```

**Deliverables Checklist**:
- [ ] Database: Migration script for `EntityRelationships` table
- [ ] Code: `src/processors/perception_pipeline.py`
- [ ] Code: Updated `src/pipeline/orchestrator.py`
- [ ] CLI: `--run-perception`, `--show-relationships` commands
- [ ] Tests: `tests/test_perception_pipeline.py`
- [ ] Documentation: `docs/perception_pipeline.md`

---

### M4: Full Integration Complete (End of Week 8)

**Acceptance Criteria**:
- [ ] All three systems work together in single pipeline run
- [ ] Performance within SLA (<10 min end-to-end)
- [ ] Token usage within budget (81k/200k)
- [ ] Comprehensive test suite passes
- [ ] User documentation complete
- [ ] Rollback procedure documented and tested

**Validation Test**:
```bash
# Test 1: Full integrated pipeline
python main.py --full-analysis --with-reflection --with-memory --with-perception

# Test 2: Performance benchmark
python main.py --benchmark --iterations 3
# Expected: Average time <10 minutes, token usage <85k

# Test 3: Quality comparison (side-by-side)
python main.py --compare-modes --baseline vs --enhanced
# Expected: Report showing depth improvements

# Test 4: Rollback test
python main.py --disable-enhancements --verify
# Expected: System reverts to baseline behavior without errors
```

**Deliverables Checklist**:
- [ ] Code: All integration complete
- [ ] Tests: End-to-end test suite
- [ ] Documentation: User guide (`docs/USER_GUIDE.md`)
- [ ] Documentation: Developer guide (`docs/DEVELOPER_GUIDE.md`)
- [ ] Documentation: API reference (`docs/API_REFERENCE.md`)
- [ ] Performance: Benchmark results document

---

## Testing Strategy

### Unit Testing

**File**: `tests/test_reflection_engine.py`
```python
def test_evaluate_depth():
    """Test depth scoring accuracy"""
    # Shallow synthesis: "Prices went up. Jobs increased."
    shallow = "Housing prices increased 8%. Employment rose 2%."
    score = reflection_engine.evaluate_depth(shallow)
    assert score < 5, "Shallow synthesis should score low"

    # Deep synthesis: causal chains, historical context, implications
    deep = """Housing prices increased 8%, accelerating the 6-month upward trend
    and exceeding historical growth rates by 3 percentage points. This appears
    causally linked to federal workforce expansion, as employment rose 2% primarily
    in government sectors. Second-order implication: school budgets may face
    pressure as property tax assessment cycles lag market prices."""
    score = reflection_engine.evaluate_depth(deep)
    assert score >= 8, "Deep synthesis should score high"

def test_identify_shallow_areas():
    """Test identification of specific shallow areas"""
    synthesis = "Housing prices increased. This is significant for the local economy."
    result = reflection_engine.identify_shallow_areas(synthesis)

    assert len(result['shallow_areas']) > 0
    assert any('causal' in area['issue'].lower() for area in result['shallow_areas'])
    # Should identify missing causal explanation
```

**File**: `tests/test_semantic_memory.py`
```python
def test_fact_extraction():
    """Test fact extraction from synthesis"""
    synthesis = {
        'narrative': "Fairfax County unemployment rate decreased to 2.3% in January 2025."
    }
    facts = semantic_memory.extract_facts(synthesis)

    assert len(facts) > 0
    assert any(
        f.subject == "Fairfax County unemployment" and
        f.predicate == "rate" and
        f.object == "2.3%" and
        f.temporal_context == "January 2025"
        for f in facts
    )

def test_historical_context_retrieval():
    """Test retrieval of relevant historical facts"""
    # Seed database with facts
    seed_fact(subject="Fairfax unemployment", object="2.8%", temporal="December 2024")
    seed_fact(subject="Arlington unemployment", object="2.5%", temporal="December 2024")

    # Query with current articles about Fairfax employment
    articles = [create_article(content="Fairfax employment trends...")]
    facts = semantic_memory.retrieve_relevant_facts(articles)

    assert len(facts) > 0
    assert any("Fairfax unemployment" in f.subject for f in facts)
    # Should prioritize Fairfax over Arlington based on relevance
```

**File**: `tests/test_perception_pipeline.py`
```python
def test_entity_extraction():
    """Test entity extraction from article"""
    article = create_article(
        content="Senator Smith opposed Bill H.R. 1234, which was sponsored by Rep. Jones."
    )
    result = perception_pipeline.extract_entities_and_relationships(article)

    assert 'Senator Smith' in result['entities']
    assert 'Bill H.R. 1234' in result['entities']
    assert 'Rep. Jones' in result['entities']

def test_relationship_extraction():
    """Test relationship extraction"""
    article = create_article(
        content="Senator Smith opposed Bill H.R. 1234, which was sponsored by Rep. Jones."
    )
    result = perception_pipeline.extract_entities_and_relationships(article)

    assert any(
        r['entity1'] == 'Senator Smith' and
        r['relationship'] == 'opposed' and
        r['entity2'] == 'Bill H.R. 1234'
        for r in result['relationships']
    )

def test_cross_article_pattern_detection():
    """Test pattern detection across multiple articles"""
    articles = [
        create_article(content="Senator Smith criticized federal telework policy..."),
        create_article(content="GSA announces office space reduction, per Senator Smith's recommendations..."),
        create_article(content="Commercial real estate concerns raised in Senate hearing, led by Senator Smith...")
    ]

    graph = perception_pipeline.build_relationship_graph(articles)
    patterns = perception_pipeline.identify_cross_article_patterns(graph)

    assert len(patterns) > 0
    assert any('Senator Smith' in pattern for pattern in patterns)
    # Should detect Senator Smith as central figure connecting multiple articles
```

### Integration Testing

**File**: `tests/test_integration.py`
```python
def test_full_pipeline_with_enhancements():
    """Test complete pipeline with all enhancements"""
    # Setup: Seed memory with historical facts
    setup_memory_facts()

    # Run full pipeline
    result = orchestrator.run_full_analysis(
        enable_reflection=True,
        enable_memory=True,
        enable_perception=True
    )

    # Verify all components contributed
    assert result['synthesis']['reflection']['refinement_applied'] == True
    assert len(result['synthesis']['historical_context']) > 0
    assert len(result['synthesis']['relationship_insights']) > 0

    # Verify output quality
    assert result['synthesis']['reflection']['final_depth_score'] >= 8

    # Verify performance
    assert result['processing_time'] < 600  # 10 minutes

def test_graceful_degradation():
    """Test system works when enhancements fail"""
    # Simulate memory database unavailable
    semantic_memory.disconnect()

    result = orchestrator.run_full_analysis(
        enable_reflection=True,
        enable_memory=True,  # Will fail gracefully
        enable_perception=True
    )

    # Should complete without historical context
    assert result['status'] == 'completed_with_warnings'
    assert 'memory_unavailable' in result['warnings']
    assert result['synthesis'] is not None  # Still produces synthesis
```

### Manual Quality Testing

**Test Protocol**: Compare baseline vs enhanced synthesis on same article batch

**Evaluation Dimensions**:
1. **Causal Depth**: Does synthesis explain WHY things are happening?
2. **Historical Awareness**: Does synthesis reference past trends/context?
3. **Cross-Article Connections**: Does synthesis identify patterns across articles?
4. **Prediction Specificity**: Are predictions concrete with reasoning chains?
5. **Implication Exploration**: Are second-order effects discussed?

**Scoring Rubric** (0-10 for each dimension):
- 0-3: Not present
- 4-6: Mentioned but superficial
- 7-8: Good depth, specific details
- 9-10: Exceptional insight, actionable analysis

**Test Cases**:
```json
{
  "test_case_1": {
    "articles": "20 articles about local housing market, county budget, school funding",
    "baseline_expected": "Surface reporting: prices up, budget tight, schools need funds",
    "enhanced_expected": "Causal chain: housing prices → property tax lag → budget pressure → school funding gap. Historical: exceeds 3-year trend. Connection: 5 articles all trace back to federal policy shift."
  },
  "test_case_2": {
    "articles": "15 articles about cybersecurity jobs, federal contracts, local tech companies",
    "baseline_expected": "Jobs up, contracts awarded, companies hiring",
    "enhanced_expected": "Pattern: Company X won contract (Article 1), hired 50 employees (Article 2), CEO testified (Article 3) - coordinated expansion. Historical: reverses 6-month decline. Prediction: Q2 hiring surge based on contract timelines."
  }
}
```

---

## Success Metrics

### Quantitative Metrics

**M1: Processing Performance**
- Target: End-to-end pipeline completes in <10 minutes
- Measurement: Track `AnalysisRun.processing_time_seconds` in database
- Baseline: Current average ~6 minutes
- Enhanced: Target <10 minutes (allowing +4 min for enhancements)

**M2: Token Efficiency**
- Target: Stay within 85k tokens per synthesis (42% of 200k budget)
- Measurement: Track `AnalysisRun.context_token_count` in database
- Baseline: Current average ~76k tokens
- Enhanced: Target <85k tokens

**M3: Memory Growth**
- Target: 5-10 facts extracted per synthesis
- Measurement: Count rows in `MemoryFacts` table per synthesis
- Milestone: 100+ facts after 10 synthesis runs
- Validation: Facts remain relevant (used in subsequent syntheses)

**M4: Relationship Detection**
- Target: 10-20 relationships per article batch
- Measurement: Count rows in `EntityRelationships` per batch
- Validation: Relationships contribute to synthesis insights

**M5: Reflection Effectiveness**
- Target: 70% of syntheses score <8 initially, improve to 8+ after refinement
- Measurement: `reflection.initial_depth_score` vs `reflection.final_depth_score`
- Success: Average improvement of +2 points per refinement

### Qualitative Metrics

**Q1: Causal Depth Score**
- Evaluation: Manual review of 10 syntheses
- Rubric: 0-10 scale (see Manual Quality Testing)
- Target: Average score 8+ across dimensions
- Baseline: Estimate current average ~5-6

**Q2: User Satisfaction**
- Survey question: "Do intelligence briefs provide deeper insights than before?"
- Scale: 1-5 (strongly disagree to strongly agree)
- Target: Average 4+
- Method: Self-report after 2 weeks using enhanced system

**Q3: Actionability**
- Question: "How often do insights lead to concrete decisions/actions?"
- Scale: Never / Rarely / Sometimes / Often / Always
- Target: "Often" or "Always"
- Baseline: Establish after 10 enhanced syntheses

### Tracking Dashboard

**CLI Command**: `python main.py --metrics-dashboard`

**Output**:
```
================================
Deep Context Enhancement Metrics
================================

Performance:
  Average Processing Time: 8.2 min (target: <10 min) ✓
  Average Token Usage: 82k (target: <85k) ✓

Memory System:
  Total Facts Stored: 127
  Facts per Synthesis: 8.5 (target: 5-10) ✓
  Fact Retrieval Rate: 85% (facts used in subsequent syntheses)

Perception System:
  Avg Relationships per Batch: 15.3 (target: 10-20) ✓
  Avg Entities per Article: 6.2
  Cross-Article Patterns Detected: 42

Reflection System:
  Avg Initial Depth Score: 5.8
  Avg Final Depth Score: 8.4 (improvement: +2.6) ✓
  Refinement Rate: 73% (syntheses needing refinement)

Quality (Manual Review, n=10):
  Causal Depth: 8.2/10 ✓
  Historical Awareness: 7.9/10
  Cross-Article Connections: 8.5/10 ✓
  Prediction Specificity: 7.6/10
  Implication Exploration: 8.1/10 ✓

Overall System Health: EXCELLENT
```

---

## Technical Specifications

### API Interfaces

**ReflectionEngine**
```python
class ReflectionEngine:
    """Evaluates synthesis depth and suggests improvements"""

    async def evaluate_depth(
        self,
        synthesis: str,
        context: dict
    ) -> ReflectionResult:
        """
        Evaluate synthesis for analytical depth

        Args:
            synthesis: The narrative synthesis text
            context: Original context used for synthesis

        Returns:
            ReflectionResult with depth_score, shallow_areas, recommendations
        """

    async def generate_refinement_prompt(
        self,
        synthesis: str,
        reflection: ReflectionResult
    ) -> str:
        """
        Generate prompt for synthesis refinement

        Args:
            synthesis: Original synthesis
            reflection: Evaluation results

        Returns:
            Prompt string for refinement pass
        """

@dataclass
class ReflectionResult:
    depth_score: float  # 0-10
    shallow_areas: List[ShallowArea]
    missing_connections: List[str]
    recommendations: List[str]
    evaluation_metadata: dict

@dataclass
class ShallowArea:
    topic: str
    issue: str
    deeper_question: str
```

**SemanticMemory**
```python
class SemanticMemory:
    """Persistent fact storage and retrieval"""

    async def extract_facts(
        self,
        synthesis: dict,
        source_synthesis_id: int
    ) -> List[MemoryFact]:
        """
        Extract structured facts from synthesis

        Args:
            synthesis: Synthesis output dictionary
            source_synthesis_id: Database ID for source tracking

        Returns:
            List of MemoryFact objects ready for storage
        """

    async def retrieve_relevant_facts(
        self,
        articles: List[Article],
        max_facts: int = 20
    ) -> List[MemoryFact]:
        """
        Retrieve facts relevant to current article set

        Args:
            articles: Current articles being analyzed
            max_facts: Maximum facts to retrieve

        Returns:
            List of relevant MemoryFact objects, prioritized by relevance
        """

    def build_historical_context(
        self,
        facts: List[MemoryFact]
    ) -> str:
        """
        Format facts as context string for synthesis

        Args:
            facts: Retrieved memory facts

        Returns:
            Formatted context string (target: ~2-3k tokens)
        """

@dataclass
class MemoryFact:
    fact_type: str  # 'metric', 'trend', 'relationship', 'decision'
    subject: str
    predicate: str
    object: str
    temporal_context: str
    confidence: float
    source_synthesis_id: int
    metadata: dict
```

**PerceptionPipeline**
```python
class PerceptionPipeline:
    """Extract entities, relationships, and patterns from articles"""

    async def extract_entities_and_relationships(
        self,
        article: Article
    ) -> PerceptionResult:
        """
        Extract structured information from article

        Args:
            article: Article object with content

        Returns:
            PerceptionResult with entities, relationships, events
        """

    async def build_relationship_graph(
        self,
        articles: List[Article]
    ) -> RelationshipGraph:
        """
        Aggregate relationships across articles into graph

        Args:
            articles: List of articles to analyze

        Returns:
            RelationshipGraph with nodes (entities) and edges (relationships)
        """

    def identify_cross_article_patterns(
        self,
        graph: RelationshipGraph
    ) -> List[Pattern]:
        """
        Detect patterns connecting multiple articles

        Args:
            graph: Relationship graph from articles

        Returns:
            List of detected patterns with descriptions
        """

@dataclass
class PerceptionResult:
    entities: List[Entity]
    relationships: List[Relationship]
    events: List[Event]
    metadata: dict

@dataclass
class Entity:
    name: str
    type: str  # 'person', 'organization', 'location', 'event', 'policy'
    mentions: int
    confidence: float

@dataclass
class Relationship:
    entity1: str
    relationship_type: str
    entity2: str
    confidence: float
    source_article_ids: List[int]

@dataclass
class Pattern:
    pattern_type: str  # 'recurring_entity', 'coordinated_action', 'causal_chain'
    description: str
    entities_involved: List[str]
    articles_involved: List[int]
    confidence: float
```

### Configuration Schema

**File**: `config/settings.py`
```python
class DeepContextConfig:
    """Configuration for deep context enhancements"""

    # Feature flags
    enable_reflection: bool = True
    enable_semantic_memory: bool = True
    enable_perception: bool = True

    # Reflection settings
    reflection_depth_threshold: float = 8.0  # Don't refine if score >= this
    reflection_max_iterations: int = 1  # Maximum refinement passes

    # Memory settings
    memory_retention_days: int = 90  # How long to keep facts
    memory_max_facts_per_retrieval: int = 20
    memory_relevance_threshold: float = 0.6  # Minimum relevance to include fact

    # Perception settings
    perception_confidence_threshold: float = 0.7  # Minimum confidence for relationships
    perception_min_occurrences: int = 2  # Minimum mentions to consider pattern

    # Performance limits
    max_processing_time_minutes: int = 10
    max_token_budget: int = 85000
```

### Database Indexes

**Performance-critical indexes**:
```sql
-- Memory lookups by subject
CREATE INDEX idx_memory_facts_subject ON memory_facts(subject);
CREATE INDEX idx_memory_facts_temporal ON memory_facts(temporal_context);

-- Relationship queries
CREATE INDEX idx_entity_rel_e1 ON entity_relationships(entity_1);
CREATE INDEX idx_entity_rel_e2 ON entity_relationships(entity_2);
CREATE INDEX idx_entity_rel_type ON entity_relationships(relationship_type);

-- Composite index for temporal + relevance queries
CREATE INDEX idx_memory_facts_composite ON memory_facts(temporal_context, confidence);
```

### Token Budget Allocation

**Total Budget**: 200,000 tokens

**Allocation**:
- Articles (existing): 50,000 tokens
- User profile (existing): 3,000 tokens
- Decision context (existing): 2,000 tokens
- Historical context (new): 3,000 tokens
- Relationship graph (new): 2,000 tokens
- Cross-article patterns (new): 1,000 tokens
- System prompts (existing): 5,000 tokens
- **Subtotal input**: 66,000 tokens
- **Synthesis output**: 5,000 tokens
- **Reflection pass**: 10,000 tokens (input + output)
- **Total per synthesis**: ~81,000 tokens (40% of budget)

**Buffer**: 119,000 tokens remaining for future enhancements

---

## Validation Criteria

### Phase 1 Validation (Reflection)

**Criterion 1.1**: Reflection produces structured output
```bash
# Test command
python main.py --synthesize --reflection --debug

# Expected output structure in logs
{
  "reflection": {
    "depth_score": 6.5,
    "shallow_areas": [
      {
        "topic": "housing trends",
        "issue": "no causal explanation",
        "deeper_question": "Why are prices rising - demand, supply, or policy?"
      }
    ],
    "recommendations": ["Explore causal chain", "Add historical comparison"]
  }
}
```

**Criterion 1.2**: Refinement improves synthesis
```bash
# Compare before/after refinement
python main.py --compare-synthesis --baseline initial --enhanced refined

# Expected: Refined version contains:
# - Explicit causal chains ("X because Y, leading to Z")
# - Historical comparisons ("compared to...", "exceeds trend...")
# - Second-order implications ("This suggests...", "Long-term effect...")
```

**Criterion 1.3**: Performance within bounds
```bash
# Benchmark reflection overhead
python main.py --benchmark --reflection --iterations 5

# Expected:
# - Average total time: 3-5 minutes (vs 2min baseline)
# - Token usage: +10-15k tokens
# - Success rate: 100% (no failures)
```

### Phase 2 Validation (Semantic Memory)

**Criterion 2.1**: Facts extracted correctly
```bash
# Run synthesis and inspect facts
python main.py --synthesize
python main.py --query-memory --limit 10

# Expected output format
Facts extracted from synthesis (2025-01-17):
1. [metric] Fairfax County unemployment | rate | 2.3% | Jan 2025 | confidence: 0.95
2. [trend] Housing prices | direction | upward | Q4 2024-Q1 2025 | confidence: 0.88
3. [decision] County Board | voted | budget increase 12% | 2025-02-15 | confidence: 0.92

# Validation: Facts are specific, temporal, and have confidence scores
```

**Criterion 2.2**: Historical context retrieval works
```bash
# Seed facts, then query
python main.py --seed-facts --file test_facts.json
python main.py --query-memory --subject "unemployment"

# Expected: Returns facts matching subject, sorted by relevance and recency
```

**Criterion 2.3**: Synthesis uses historical context
```bash
# Run synthesis with memory enabled
python main.py --synthesize --with-memory --output enhanced.json

# Expected: Synthesis contains phrases like:
# - "compared to 3 months ago when unemployment was 2.8%"
# - "continuing the trend from Q4 2024"
# - "historically, this level indicates..."

# Validation: grep for temporal keywords
cat enhanced.json | jq '.narrative' | grep -i "compared\|previously\|historically\|trend"
```

### Phase 3 Validation (Perception)

**Criterion 3.1**: Entities extracted from articles
```bash
# Run perception on article batch
python main.py --run-perception --input articles.json --output perception.json

# Expected output structure
{
  "articles_processed": 20,
  "entities_found": 87,
  "relationships_found": 34,
  "patterns_detected": 5
}

# Validation: Inspect sample entities
cat perception.json | jq '.entities[0:5]'
# Expected: Proper entity names, types, confidence scores
```

**Criterion 3.2**: Relationships identified
```bash
# Query relationships after perception
python main.py --query-relationships --entity "Senator Smith"

# Expected output
Relationships involving "Senator Smith":
1. Senator Smith | opposed | Bill H.R. 1234 | confidence: 0.91 | articles: [12, 15, 18]
2. Senator Smith | collaborated_with | Rep. Jones | confidence: 0.83 | articles: [15, 22]
3. Senator Smith | sponsored | Amendment 45 | confidence: 0.95 | articles: [12]

# Validation: Relationships have proper structure and article references
```

**Criterion 3.3**: Cross-article patterns detected
```bash
# Run pattern detection
python main.py --detect-patterns --articles articles.json

# Expected output
Patterns detected:
1. [recurring_entity] Senator Smith appears in 5 articles, connecting federal policy (3), local impact (2)
2. [causal_chain] Policy A (Article 12) → Implementation B (Article 15) → Local effect C (Article 18)
3. [coordinated_action] Company X expands (Article 5), hires staff (Article 9), CEO testifies (Article 14)

# Validation: Patterns identify non-obvious connections
```

**Criterion 3.4**: Synthesis uses relationship insights
```bash
# Run full synthesis with perception
python main.py --synthesize --with-perception --output enhanced.json

# Expected: Synthesis contains phrases like:
# - "These articles connect through Entity X"
# - "A pattern emerges across 4 articles"
# - "Entity A's relationship with Entity B explains..."

# Validation: grep for pattern keywords
cat enhanced.json | jq '.narrative' | grep -i "pattern\|connection\|relationship\|across.*articles"
```

### Integration Validation

**Criterion I.1**: All systems work together
```bash
# Run full integrated pipeline
python main.py --full-analysis --all-enhancements

# Expected: Completes without errors, produces synthesis using all three systems
# Verify in output:
cat output.json | jq '.metadata'
# Expected:
{
  "reflection_applied": true,
  "historical_facts_used": 12,
  "relationships_considered": 34,
  "patterns_detected": 5,
  "depth_score_initial": 6.2,
  "depth_score_final": 8.5
}
```

**Criterion I.2**: Performance SLA met
```bash
# Benchmark integrated pipeline
python main.py --benchmark --all-enhancements --iterations 3

# Expected results:
Run 1: 9.2 minutes, 82k tokens
Run 2: 8.8 minutes, 79k tokens
Run 3: 9.5 minutes, 84k tokens
Average: 9.2 minutes, 82k tokens

# Validation: Average <10 minutes, <85k tokens
```

**Criterion I.3**: Quality improvement measurable
```bash
# Compare baseline vs enhanced on same articles
python main.py --quality-comparison --articles articles.json

# Runs synthesis twice (baseline vs enhanced), compares outputs
# Expected: Enhanced scores higher on all quality dimensions (see Success Metrics)
```

---

## Rollback Strategy

### Rollback Triggers

**Trigger R1**: Performance degradation
- If average processing time >12 minutes for 5 consecutive runs
- Action: Disable least critical component (perception → memory → reflection)

**Trigger R2**: Quality regression
- If manual quality scores drop below baseline
- Action: Investigate root cause, potentially rollback specific component

**Trigger R3**: Critical bug
- If synthesis fails >20% of runs
- Action: Immediate rollback to previous stable version

### Rollback Procedures

**Procedure 1: Feature Flag Disable**
```bash
# Disable specific enhancement
python main.py --config enable_reflection=false

# Or disable all enhancements
python main.py --config enable_deep_context=false

# System reverts to baseline behavior immediately
```

**Procedure 2: Database Rollback**
```bash
# If new tables cause issues
python main.py --migrate --rollback --target <migration_id>

# Removes MemoryFacts and EntityRelationships tables
# Existing tables (articles, syntheses) unaffected
```

**Procedure 3: Code Rollback**
```bash
# Revert to pre-enhancement commit
git checkout <baseline_commit_hash>
python main.py --verify

# Or use tagged release
git checkout tags/v1.0-baseline
```

**Procedure 4: Partial Rollback**
```bash
# Keep database tables but disable processing
# Allows gradual debugging without data loss

# config/settings.py
enable_reflection = False  # Disable reflection only
enable_semantic_memory = False
enable_perception = False

# Data remains in database for analysis
```

### Rollback Testing

**Test RB-1**: Feature flag disable works
```bash
python main.py --config enable_deep_context=false --synthesize
# Expected: Completes using baseline logic, no errors
```

**Test RB-2**: Database rollback preserves data
```bash
# Backup before rollback
python main.py --backup-db --output backup.db

# Rollback
python main.py --migrate --rollback --target baseline

# Verify articles/syntheses intact
python main.py --verify-db
# Expected: Core tables unchanged, new tables removed
```

**Test RB-3**: Code rollback restores baseline
```bash
git checkout <baseline_commit>
python main.py --test
# Expected: All baseline tests pass
```

---

## Documentation Standards

### Code Documentation

**Docstring Template**:
```python
def method_name(param1: type, param2: type) -> return_type:
    """
    Brief description (one line)

    Detailed explanation of what this method does, including:
    - Key behavior
    - Side effects
    - Performance considerations

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ExceptionType: When and why this exception is raised

    Example:
        >>> result = method_name("value1", "value2")
        >>> print(result)
        expected_output
    """
```

**Inline Comments**:
```python
# Use comments to explain WHY, not WHAT
# Good: "Cache facts to avoid repeated DB queries during synthesis"
# Bad: "Store facts in cache"

# Document non-obvious decisions
# Example: "Use 90-day retention to balance memory size vs context depth"

# Flag future improvements
# TODO(priority): Implement parallel fact extraction for better performance
```

### API Documentation

**File**: `docs/API_REFERENCE.md`

**Structure**:
```markdown
# API Reference

## ReflectionEngine

### evaluate_depth(synthesis: str, context: dict) -> ReflectionResult

**Purpose**: Evaluates synthesis for analytical depth

**Parameters**:
- `synthesis` (str): The narrative synthesis text to evaluate
- `context` (dict): Original context used for synthesis

**Returns**: `ReflectionResult` object containing:
- `depth_score` (float): Score from 0-10
- `shallow_areas` (List[ShallowArea]): Specific areas needing improvement
- `recommendations` (List[str]): Actionable improvement suggestions

**Example**:
```python
reflection = await engine.evaluate_depth(
    synthesis="Housing prices increased...",
    context={"articles": [...], ...}
)
print(f"Depth score: {reflection.depth_score}")
```

**Performance**: ~5-10 seconds, ~6k tokens
```

### User Documentation

**File**: `docs/USER_GUIDE.md`

**Contents**:
1. What's New: Deep Context Enhancements
2. How It Works: Plain English explanation
3. Configuration Guide: Enabling/disabling features
4. Expected Changes: What users will notice
5. Troubleshooting: Common issues and solutions
6. FAQ: Frequently asked questions

**Tone**: Non-technical, user-focused

### Developer Documentation

**File**: `docs/DEVELOPER_GUIDE.md`

**Contents**:
1. Architecture Overview
2. Component Interactions
3. Adding New Features: Extension points
4. Testing Guidelines
5. Performance Tuning
6. Debugging Techniques

**Tone**: Technical, implementation-focused

---

## Risk Assessment

### High Priority Risks

**Risk H1: Token Budget Exceeded**
- Probability: Medium
- Impact: High (synthesis fails or gets truncated)
- Mitigation: Implement strict token counting, automatic context pruning
- Contingency: Disable least critical component to reduce tokens

**Risk H2: Performance Degradation**
- Probability: Medium
- Impact: High (>10 min processing time unacceptable)
- Mitigation: Parallel processing where possible, optimize DB queries
- Contingency: Feature flag disable for slowest component

**Risk H3: Quality Does Not Improve**
- Probability: Low-Medium
- Impact: Medium (enhancement effort wasted)
- Mitigation: Extensive testing during development, A/B comparison
- Contingency: Rollback to baseline, iterate on design

### Medium Priority Risks

**Risk M1: Database Size Growth**
- Probability: High (intentional accumulation)
- Impact: Medium (storage concerns, query slowdown)
- Mitigation: 90-day retention policy, periodic archival
- Contingency: Compress old facts, move to cold storage

**Risk M2: Fact Extraction Errors**
- Probability: Medium (LLM hallucination)
- Impact: Medium (incorrect facts poison future syntheses)
- Mitigation: Confidence thresholds, cross-validation, expiry dates
- Contingency: Manual fact review tools, purge low-confidence facts

**Risk M3: Relationship False Positives**
- Probability: Medium
- Impact: Low-Medium (misleading connections)
- Mitigation: Confidence thresholds, occurrence minimums
- Contingency: User feedback mechanism to flag incorrect relationships

### Low Priority Risks

**Risk L1: Configuration Complexity**
- Probability: Medium
- Impact: Low (user confusion)
- Mitigation: Sensible defaults, clear documentation
- Contingency: Simplified configuration mode

**Risk L2: Over-Reflection**
- Probability: Low
- Impact: Low (slightly slower, more tokens)
- Mitigation: Depth threshold prevents unnecessary refinement
- Contingency: Tune threshold based on performance data

---

## Appendix A: Example Outputs

### Baseline Synthesis (Before Enhancements)

```json
{
  "priority_insights": [
    "Housing prices in Fairfax County increased 8% this quarter.",
    "Unemployment rate decreased to 2.3%.",
    "County Board to vote on budget increase of 12%."
  ],
  "trends": [
    "Housing market shows upward trend",
    "Employment market remains strong"
  ],
  "predictions": [
    "Budget vote likely to pass based on past voting patterns"
  ],
  "events": [
    "County Board meeting on February 15, 2025"
  ]
}
```

### Enhanced Synthesis (After All Enhancements)

```json
{
  "priority_insights": [
    "Housing prices increased 8% this quarter, significantly accelerating the 6-month upward trend (historical: previous quarters averaged 2-3% growth). This appears causally linked to federal workforce expansion, as government employment rose 2% while private sector remained flat. Second-order implication: School budget pressures will intensify as property tax assessment cycles lag market prices by 6-12 months.",

    "Unemployment decreased to 2.3%, reversing the 3-month uptick to 2.8% in December 2024 (semantic memory). Pattern analysis reveals this coincides with three major federal contractors (mentioned across 4 articles) announcing expansions, suggesting the improvement is concentrated in federal-adjacent sectors rather than broad economic strength.",

    "County Board's proposed 12% budget increase reflects property tax revenue projections, but three board members (relationship analysis) who previously voted against increases >10% now indicate support. The shift appears linked to constituent pressure documented in 5 town hall articles (cross-article pattern), suggesting political calculus has changed."
  ],

  "causal_chains": [
    "Federal telework policy reversal → Increased office occupancy → Local housing demand → Price acceleration → Tax base growth (12-month lag) → County budget capacity increase"
  ],

  "trends_with_context": [
    {
      "trend": "Housing market acceleration",
      "historical_comparison": "Current 8% quarterly growth exceeds 5-year average of 3%, placing it in 95th percentile",
      "causal_factors": ["Federal workforce expansion", "Office space occupancy increase", "Tight supply (new construction permits down 15% YoY)"],
      "sustainability": "Likely to moderate by Q3 2025 as supply adjusts and federal hiring normalizes"
    }
  ],

  "predictions_with_reasoning": [
    {
      "prediction": "County budget vote will pass 8-2 (vs previous prediction of uncertain outcome)",
      "reasoning_chain": "Three previously opposed board members (Smith, Jones, Lee) now indicate support based on town hall feedback → Likely votes: 5 reliable yes + 3 fence-sitters now yes + 2 reliable no = 8-2",
      "confidence": 0.87,
      "key_uncertainty": "Fiscal impact statement due February 10 could reveal unexpected revenue shortfall"
    }
  ],

  "relationship_insights": [
    "Senator Smith's opposition to federal telework policy (3 articles) connects to GSA office space decision (2 articles) and local commercial real estate concerns (4 articles). This represents a coordinated policy push affecting local housing market dynamics through increased office occupancy."
  ],

  "reflection_metadata": {
    "initial_depth_score": 5.8,
    "final_depth_score": 8.6,
    "refinement_areas_addressed": [
      "Added causal explanation for housing price increase",
      "Connected cross-article pattern for County Board voting shift",
      "Explored second-order implications for school budgets"
    ]
  }
}
```

---

## Appendix B: CLI Command Reference

### Core Analysis Commands

```bash
# Run full analysis with all enhancements
python main.py --full-analysis --all-enhancements

# Run with specific enhancements
python main.py --synthesize --reflection --memory --perception

# Run baseline (no enhancements)
python main.py --synthesize --baseline

# Interactive mode (preview before sending)
python main.py --synthesize --interactive
```

### Memory Management

```bash
# View memory statistics
python main.py --memory-stats

# Query facts by subject
python main.py --query-memory --subject "unemployment"

# View all facts from last 30 days
python main.py --query-memory --days 30

# Purge low-confidence facts
python main.py --purge-memory --confidence-below 0.5

# Export facts to JSON
python main.py --export-memory --output facts.json
```

### Relationship Analysis

```bash
# Run perception pipeline on articles
python main.py --run-perception --articles articles.json

# View relationships for entity
python main.py --query-relationships --entity "Senator Smith"

# Show relationship graph (text format)
python main.py --show-relationships --format text

# Detect cross-article patterns
python main.py --detect-patterns --articles articles.json
```

### Testing & Validation

```bash
# Benchmark performance
python main.py --benchmark --iterations 5

# Compare baseline vs enhanced
python main.py --compare-modes --articles articles.json

# Quality evaluation
python main.py --evaluate-quality --synthesis synthesis.json

# Run full test suite
python main.py --test --verbose
```

### Debugging

```bash
# Enable debug logging
python main.py --synthesize --debug --log-level DEBUG

# Trace specific synthesis run
python main.py --trace <correlation_id>

# Verify database integrity
python main.py --verify-db

# Show token usage breakdown
python main.py --token-analysis --synthesis synthesis.json
```

### Configuration

```bash
# Show current configuration
python main.py --show-config

# Set configuration value
python main.py --config enable_reflection=true

# Reset to defaults
python main.py --config-reset

# Disable all enhancements
python main.py --config enable_deep_context=false
```

---

## Appendix C: Troubleshooting Guide

### Issue: Synthesis Takes Too Long (>10 minutes)

**Symptoms**: Pipeline exceeds 10-minute SLA

**Diagnosis**:
```bash
python main.py --trace <run_id> --show-timings
# Shows time breakdown by stage
```

**Solutions**:
1. Check if perception pipeline is bottleneck → Consider batching article processing
2. Check if reflection is timing out → Lower depth threshold to reduce refinement frequency
3. Check database query performance → Run `ANALYZE` command, rebuild indexes
4. Temporarily disable slowest component:
   ```bash
   python main.py --config enable_perception=false
   ```

### Issue: Token Budget Exceeded

**Symptoms**: Synthesis fails with "context too long" error

**Diagnosis**:
```bash
python main.py --token-analysis --synthesis <run_id>
# Shows token usage by component
```

**Solutions**:
1. Reduce historical fact count: `--config memory_max_facts_per_retrieval=10`
2. Simplify relationship graph: `--config perception_confidence_threshold=0.8`
3. Compress article content (summarize less relevant articles)
4. Verify no token leaks (debug logging showing unexpected large prompts)

### Issue: Memory Facts Not Being Retrieved

**Symptoms**: Synthesis doesn't reference historical context

**Diagnosis**:
```bash
# Check fact extraction
python main.py --query-memory --limit 50

# Check relevance matching
python main.py --debug-memory --articles articles.json
```

**Solutions**:
1. Verify facts were extracted: Check `MemoryFacts` table
2. Lower relevance threshold: `--config memory_relevance_threshold=0.5`
3. Check fact expiry dates: Some facts may have expired
4. Verify subject matching: Ensure article topics align with stored fact subjects

### Issue: Relationships Not Detected

**Symptoms**: Perception pipeline finds few/no relationships

**Diagnosis**:
```bash
python main.py --run-perception --articles articles.json --debug
# Shows entity extraction and relationship identification process
```

**Solutions**:
1. Lower confidence threshold: `--config perception_confidence_threshold=0.6`
2. Check article content quality: Ensure articles have substantive text
3. Verify LLM prompts: Review perception prompts for clarity
4. Test with known relationship: Manually verify an article that should contain obvious relationships

### Issue: Reflection Not Improving Depth

**Symptoms**: Final depth score not significantly higher than initial

**Diagnosis**:
```bash
# Review reflection results
python main.py --show-reflection --synthesis <run_id>
```

**Solutions**:
1. Review shallow areas identified: Are they specific enough?
2. Check refinement prompt: Ensure it guides toward depth
3. Verify depth scoring rubric: May need calibration
4. Consider if articles lack depth to begin with (garbage in, garbage out)

### Issue: Database Growing Too Large

**Symptoms**: Database file size >1GB, queries slowing

**Diagnosis**:
```bash
# Check table sizes
python main.py --db-stats
```

**Solutions**:
1. Run retention cleanup: `python main.py --cleanup-old-facts --days 90`
2. Archive old data: `python main.py --archive --before 2024-01-01`
3. Vacuum database: `python main.py --vacuum-db`
4. Review indexes: Ensure efficient queries

---

**End of Document**

This plan will be maintained as a living document throughout implementation. All changes to architecture, milestones, or success criteria will be documented with version updates and change log entries.

**Next Steps**: Review plan, confirm approach, begin Phase 1 implementation (Reflection Loop).

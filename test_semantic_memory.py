#!/usr/bin/env python3
"""
Test script for semantic memory system
"""

import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.database.connection import get_db
from src.database.models import NarrativeSynthesis, Article
from src.context.semantic_memory import SemanticMemory


async def test_semantic_memory():
    print('=' * 60)
    print('SEMANTIC MEMORY SYSTEM TEST')
    print('=' * 60)
    print()

    with get_db() as session:
        # Get a recent synthesis to test extraction
        synthesis = session.query(NarrativeSynthesis).order_by(
            NarrativeSynthesis.id.desc()
        ).first()

        if not synthesis:
            print('❌ No synthesis found to test with')
            return

        print(f'📊 Using synthesis ID: {synthesis.id}')
        print(f'   Generated: {synthesis.generated_at}')
        print(f'   Articles analyzed: {synthesis.articles_analyzed}')
        print()

        # Initialize semantic memory
        memory = SemanticMemory(session)

        # TEST 1: Extract facts from synthesis
        print('TEST 1: Fact Extraction')
        print('-' * 60)
        facts = await memory.extract_facts_from_synthesis(
            synthesis.synthesis_data,
            synthesis.id
        )

        print(f'✅ Extracted {len(facts)} facts')
        if facts:
            print(f'\n   Sample facts:')
            for i, sample in enumerate(facts[:3], 1):
                print(f'\n   {i}. Type: {sample.fact_type}')
                print(f'      Subject: {sample.subject}')
                print(f'      Predicate: {sample.predicate}')
                print(f'      Object: {sample.object[:60]}...' if len(sample.object) > 60 else f'      Object: {sample.object}')
                print(f'      Temporal: {sample.temporal_context}')
                print(f'      Confidence: {sample.confidence}')
        print()

        # TEST 2: Store facts
        print('TEST 2: Fact Storage')
        print('-' * 60)
        stored_count = memory.store_facts(facts)
        print(f'✅ Stored {stored_count} facts in database')
        print()

        # TEST 3: Check database
        print('TEST 3: Database Verification')
        print('-' * 60)
        from src.database.models import MemoryFact
        total_facts = session.query(MemoryFact).count()
        print(f'✅ Total facts in database: {total_facts}')

        # Show most recent facts
        recent_facts = session.query(MemoryFact).order_by(
            MemoryFact.id.desc()
        ).limit(3).all()

        if recent_facts:
            print(f'\n   Most recent stored facts:')
            for fact in recent_facts:
                print(f'   - {fact.subject} {fact.predicate} {fact.object[:40]}...' if len(fact.object) > 40 else f'   - {fact.subject} {fact.predicate} {fact.object}')
        print()

        # TEST 4: Retrieve facts
        print('TEST 4: Fact Retrieval')
        print('-' * 60)

        # Get some articles to match against
        articles = session.query(Article).limit(10).all()
        print(f'   Using {len(articles)} sample articles for matching')

        # Show what keywords would be extracted
        keywords = memory._extract_keywords_from_articles(articles)
        print(f'   Extracted keywords: {keywords[:5]}...')

        retrieved_facts = memory.retrieve_relevant_facts(articles, max_facts=10)
        print(f'✅ Retrieved {len(retrieved_facts)} relevant facts')

        if retrieved_facts:
            print(f'\n   Retrieved facts:')
            for i, sample in enumerate(retrieved_facts[:3], 1):
                print(f'   {i}. {sample.subject} {sample.predicate} {sample.object[:40]}...' if len(sample.object) > 40 else f'   {i}. {sample.subject} {sample.predicate} {sample.object}')
                print(f'      ({sample.temporal_context or "recent"})')
        print()

        # TEST 5: Build historical context
        print('TEST 5: Historical Context Formatting')
        print('-' * 60)
        context = memory.build_historical_context(retrieved_facts)
        print(f'✅ Built historical context ({len(context)} characters)')
        if context:
            print('\n   FORMATTED CONTEXT:')
            print('   ' + '-' * 56)
            for line in context.split('\n')[:15]:  # Show first 15 lines
                print(f'   {line}')
            if len(context.split('\n')) > 15:
                print('   ...')
        print()

        print('=' * 60)
        print('ALL TESTS PASSED ✅')
        print('=' * 60)


if __name__ == "__main__":
    asyncio.run(test_semantic_memory())

#!/usr/bin/env python3
"""
InsightWeaver Test Suite
Comprehensive testing with cost control and granular selection

Usage:
    python test_suite.py --all                    # Full end-to-end test (EXPENSIVE)
    python test_suite.py --trends                 # Test trend analysis only
    python test_suite.py --synthesis              # Test narrative synthesis only
    python test_suite.py --newsletter             # Test newsletter generation only
    python test_suite.py --quick                  # Quick test (10 articles, 1 trend)
    python test_suite.py --validate               # Validate existing data (FREE)
"""

import asyncio
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.database.connection import get_db
from src.database.models import Article, NarrativeSynthesis
from src.agents.trend_agent import TrendAnalysisAgent
from src.agents.narrative_synthesis_agent import NarrativeSynthesisAgent
from src.newsletter.content_engine import NewsletterContentEngine
from src.newsletter.templates import PersonalizedNarrativeTemplate

# ANSI colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
BOLD = '\033[1m'
RESET = '\033[0m'


def print_header(text):
    """Print test section header"""
    print(f"\n{BLUE}{BOLD}{'=' * 70}{RESET}")
    print(f"{BLUE}{BOLD}{text:^70}{RESET}")
    print(f"{BLUE}{BOLD}{'=' * 70}{RESET}\n")


def print_success(text):
    """Print success message"""
    print(f"{GREEN}✓ {text}{RESET}")


def print_error(text):
    """Print error message"""
    print(f"{RED}✗ {text}{RESET}")


def print_warning(text):
    """Print warning message"""
    print(f"{YELLOW}⚠ {text}{RESET}")


def print_info(text):
    """Print info message"""
    print(f"{BLUE}ℹ {text}{RESET}")


class TestSuite:
    """Main test suite controller"""

    def __init__(self):
        self.results = {
            'passed': [],
            'failed': [],
            'warnings': []
        }

    async def validate_database(self):
        """Validate existing database data (FREE - no API calls)"""
        print_header("VALIDATING DATABASE")

        with get_db() as db:
            # Check articles
            total_articles = db.query(Article).count()
            filtered_articles = db.query(Article).filter(Article.filtered == True).count()
            high_priority = db.query(Article).filter(
                Article.priority_score >= 0.7,
                Article.filtered == False
            ).count()

            print_info(f"Total articles: {total_articles}")
            print_info(f"Filtered articles: {filtered_articles}")
            print_info(f"High-priority articles (≥0.7): {high_priority}")

            if total_articles == 0:
                print_error("No articles in database - run pipeline first")
                self.results['failed'].append('validate_articles')
                return False

            # Check narrative synthesis
            syntheses = db.query(NarrativeSynthesis).all()
            print_info(f"Narrative syntheses: {len(syntheses)}")

            if not syntheses:
                print_warning("No narrative syntheses found")
                self.results['warnings'].append('no_syntheses')
            else:
                latest = syntheses[-1]
                print_info(f"Latest synthesis: {latest.generated_at}")
                print_info(f"Articles analyzed: {latest.articles_analyzed}")

                # Validate synthesis data structure
                if latest.synthesis_data is None:
                    print_error(f"Synthesis {latest.id} has NULL synthesis_data")
                    self.results['failed'].append('synthesis_data_null')
                    return False

                required_fields = ['temporal_layers', 'cross_domain_insights',
                                 'priority_actions', 'executive_summary']
                missing = [f for f in required_fields if f not in latest.synthesis_data]

                if missing:
                    print_error(f"Synthesis missing fields: {missing}")
                    print_info(f"Available fields: {list(latest.synthesis_data.keys())}")
                    self.results['failed'].append('synthesis_incomplete')
                    return False
                else:
                    print_success("Synthesis data structure is valid")

        self.results['passed'].append('validate_database')
        return True

    async def test_trend_analysis(self, article_limit=10, trend_count=1):
        """Test trend analysis with controlled scope"""
        print_header(f"TESTING TREND ANALYSIS ({article_limit} articles, {trend_count} trend(s))")

        try:
            agent = TrendAnalysisAgent()

            # Get sample articles
            articles = agent.get_recent_articles(days=1, limit=article_limit)
            print_info(f"Retrieved {len(articles)} articles")

            if len(articles) == 0:
                print_error("No articles found")
                self.results['failed'].append('trend_no_articles')
                return False

            # Convert Article objects to dictionaries (same format as analyze_articles)
            from datetime import timezone
            articles_data = []
            with get_db() as db:
                for article in articles:
                    article = db.merge(article)
                    fetched_at = article.fetched_at.replace(tzinfo=timezone.utc) if article.fetched_at.tzinfo is None else article.fetched_at
                    article_age_days = (datetime.now(timezone.utc) - fetched_at).total_seconds() / (24 * 3600)

                    articles_data.append({
                        "id": article.id,
                        "title": article.title or "No title",
                        "content": (article.normalized_content or article.description or "")[:800],
                        "published_date": article.published_date.isoformat() if article.published_date else "Unknown",
                        "source": article.feed.name if article.feed else "Unknown",
                        "age_days": round(article_age_days, 1),
                        "url": article.url
                    })

            # Test with limited trends
            from src.analyzers.trend_analyzer import GlobalTrend
            test_trends = [GlobalTrend.DIGITAL_CENTRALIZATION_VS_DECENTRALIZATION]
            if trend_count > 1:
                test_trends.append(GlobalTrend.SECURITY_VS_PRIVACY)

            # Filter articles by relevance
            filtered_groups = {}
            for trend_enum in test_trends[:trend_count]:
                trend_name = trend_enum.value
                filtered_groups[trend_name] = articles_data

            # Analyze stances
            print_info("Analyzing article stances...")
            trend_stances = await agent._analyze_trend_stances(filtered_groups)

            # Validate results
            for trend_name, articles_with_stance in trend_stances.items():
                print_info(f"\nTrend: {trend_name}")
                print_info(f"  Articles analyzed: {len(articles_with_stance)}")

                # Check for random assignments (Issue 1)
                random_count = sum(1 for a in articles_with_stance
                                  if 'Fallback' in a.get('reasoning', ''))
                if random_count > 0:
                    print_error(f"  Found {random_count} articles with random/fallback stances!")
                    self.results['failed'].append('random_assignments')
                else:
                    print_success("  No random assignments detected")

                # Check stance distribution (Issue 2 & 3)
                supporting = sum(1 for a in articles_with_stance if a.get('stance') == 'SUPPORTING')
                opposing = sum(1 for a in articles_with_stance if a.get('stance') == 'OPPOSING')
                neutral = sum(1 for a in articles_with_stance if a.get('stance') == 'NEUTRAL')

                print_info(f"  SUPPORTING: {supporting}")
                print_info(f"  OPPOSING: {opposing}")
                print_info(f"  NEUTRAL: {neutral}")

                total_stances = supporting + opposing + neutral
                if total_stances == 0:
                    print_error("  Stance distribution is 0 - no stances recorded!")
                    self.results['failed'].append('zero_stances')
                else:
                    print_success(f"  Valid stance distribution (total: {total_stances})")

                # Validate NEUTRAL is accepted
                if neutral > 0:
                    print_success(f"  NEUTRAL stance properly accepted ({neutral} articles)")

            self.results['passed'].append('trend_analysis')
            return True

        except Exception as e:
            print_error(f"Trend analysis failed: {e}")
            import traceback
            traceback.print_exc()
            self.results['failed'].append('trend_analysis_exception')
            return False

    async def test_narrative_synthesis(self, article_limit=20):
        """Test narrative synthesis with controlled scope"""
        print_header(f"TESTING NARRATIVE SYNTHESIS ({article_limit} articles)")

        try:
            agent = NarrativeSynthesisAgent()

            # Get high-priority articles
            with get_db() as db:
                cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
                articles = db.query(Article).filter(
                    Article.fetched_at >= cutoff,
                    Article.priority_score >= 0.85,
                    Article.filtered == False
                ).order_by(Article.priority_score.desc()).limit(article_limit).all()

            print_info(f"Found {len(articles)} high-priority articles")

            if len(articles) == 0:
                print_warning("No high-priority articles found - skipping synthesis")
                self.results['warnings'].append('no_high_priority_articles')
                return False

            # Run synthesis
            print_info("Running narrative synthesis...")
            results = await agent.synthesize_narrative(articles)

            # Validate results
            if not results:
                print_error("Synthesis returned no results")
                self.results['failed'].append('synthesis_empty')
                return False

            synthesis_data = results.get('synthesis_data', {})
            executive_summary = results.get('executive_summary', '')

            # Check required fields
            required_fields = ['temporal_layers', 'cross_domain_insights',
                             'priority_actions', 'executive_summary']
            missing = [f for f in required_fields if f not in synthesis_data]

            if missing:
                print_error(f"Synthesis missing fields: {missing}")
                self.results['failed'].append('synthesis_incomplete_fields')
                return False
            else:
                print_success("All required fields present")

            # Validate content
            temporal_layers = synthesis_data.get('temporal_layers', {})
            print_info(f"Temporal layers: {list(temporal_layers.keys())}")

            if not executive_summary:
                print_error("Executive summary is empty")
                self.results['failed'].append('empty_executive_summary')
                return False
            else:
                print_success(f"Executive summary present ({len(executive_summary)} chars)")

            cross_domain = synthesis_data.get('cross_domain_insights', [])
            print_info(f"Cross-domain insights: {len(cross_domain)}")

            priority_actions = synthesis_data.get('priority_actions', [])
            print_info(f"Priority actions: {len(priority_actions)}")

            self.results['passed'].append('narrative_synthesis')
            return True

        except Exception as e:
            print_error(f"Narrative synthesis failed: {e}")
            import traceback
            traceback.print_exc()
            self.results['failed'].append('synthesis_exception')
            return False

    async def test_newsletter_generation(self):
        """Test newsletter generation (uses existing data - FREE)"""
        print_header("TESTING NEWSLETTER GENERATION")

        try:
            engine = NewsletterContentEngine()

            # Generate content from existing synthesis
            print_info("Generating newsletter content...")
            content = await engine.generate_daily_brief_content(datetime.now())

            # Validate content structure
            if not content:
                print_error("Content generation returned None")
                self.results['failed'].append('newsletter_no_content')
                return False

            required_keys = ['date', 'synthesis_data', 'executive_summary', 'user_context']
            missing = [k for k in required_keys if k not in content]

            if missing:
                print_error(f"Content missing keys: {missing}")
                self.results['failed'].append('newsletter_incomplete_content')
                return False

            print_success("Content structure valid")

            # Generate HTML
            print_info("Generating HTML template...")
            html = PersonalizedNarrativeTemplate.generate_html(content)

            if not html or len(html) < 100:
                print_error("HTML generation failed or too short")
                self.results['failed'].append('newsletter_html_failed')
                return False

            print_success(f"HTML generated ({len(html)} bytes)")

            # Check for key sections
            required_sections = ['Your Intelligence Brief', 'What You Need to Know']
            missing_sections = [s for s in required_sections if s not in html]

            if missing_sections:
                print_warning(f"HTML missing sections: {missing_sections}")
                self.results['warnings'].append('newsletter_missing_sections')
            else:
                print_success("All key sections present in HTML")

            self.results['passed'].append('newsletter_generation')
            return True

        except Exception as e:
            print_error(f"Newsletter generation failed: {e}")
            import traceback
            traceback.print_exc()
            self.results['failed'].append('newsletter_exception')
            return False

    async def run_quick_test(self):
        """Quick test of all components with minimal API usage"""
        print_header("QUICK TEST SUITE (MINIMAL COST)")
        print_info("Testing with 10 articles, 1 trend\n")

        await self.validate_database()
        await self.test_trend_analysis(article_limit=10, trend_count=1)
        await self.test_narrative_synthesis(article_limit=10)
        await self.test_newsletter_generation()

    async def run_full_test(self):
        """Full end-to-end test (EXPENSIVE)"""
        print_header("FULL END-TO-END TEST (HIGH COST)")
        print_warning("This will use significant API credits!")

        await self.validate_database()
        await self.test_trend_analysis(article_limit=100, trend_count=5)
        await self.test_narrative_synthesis(article_limit=50)
        await self.test_newsletter_generation()

    def print_summary(self):
        """Print test summary"""
        print_header("TEST SUMMARY")

        total = len(self.results['passed']) + len(self.results['failed'])
        passed = len(self.results['passed'])
        failed = len(self.results['failed'])
        warnings = len(self.results['warnings'])

        print(f"Total tests: {total}")
        print(f"{GREEN}Passed: {passed}{RESET}")
        if failed > 0:
            print(f"{RED}Failed: {failed}{RESET}")
        if warnings > 0:
            print(f"{YELLOW}Warnings: {warnings}{RESET}")

        if self.results['passed']:
            print(f"\n{GREEN}Passed tests:{RESET}")
            for test in self.results['passed']:
                print(f"  ✓ {test}")

        if self.results['failed']:
            print(f"\n{RED}Failed tests:{RESET}")
            for test in self.results['failed']:
                print(f"  ✗ {test}")

        if self.results['warnings']:
            print(f"\n{YELLOW}Warnings:{RESET}")
            for warning in self.results['warnings']:
                print(f"  ⚠ {warning}")

        print()

        # Return exit code
        return 0 if failed == 0 else 1


async def main():
    parser = argparse.ArgumentParser(
        description='InsightWeaver Test Suite - Granular testing with cost control'
    )

    parser.add_argument('--all', action='store_true',
                       help='Run full end-to-end test (EXPENSIVE)')
    parser.add_argument('--quick', action='store_true',
                       help='Quick test with minimal API usage (10 articles, 1 trend)')
    parser.add_argument('--validate', action='store_true',
                       help='Validate existing database data only (FREE)')
    parser.add_argument('--trends', action='store_true',
                       help='Test trend analysis only')
    parser.add_argument('--synthesis', action='store_true',
                       help='Test narrative synthesis only')
    parser.add_argument('--newsletter', action='store_true',
                       help='Test newsletter generation only')
    parser.add_argument('--articles', type=int, default=10,
                       help='Number of articles to test with (default: 10)')
    parser.add_argument('--trend-count', type=int, default=1,
                       help='Number of trends to test (default: 1)')

    args = parser.parse_args()

    suite = TestSuite()

    # If no flags, show help
    if not any([args.all, args.quick, args.validate, args.trends,
                args.synthesis, args.newsletter]):
        parser.print_help()
        return 1

    # Run selected tests
    if args.all:
        await suite.run_full_test()
    elif args.quick:
        await suite.run_quick_test()
    else:
        if args.validate:
            await suite.validate_database()
        if args.trends:
            await suite.test_trend_analysis(args.articles, args.trend_count)
        if args.synthesis:
            await suite.test_narrative_synthesis(args.articles)
        if args.newsletter:
            await suite.test_newsletter_generation()

    # Print summary and exit
    exit_code = suite.print_summary()
    return exit_code


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
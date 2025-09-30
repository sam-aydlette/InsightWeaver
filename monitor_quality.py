#!/usr/bin/env python3
"""
Data Quality Monitor for InsightWeaver
Checks for data integrity issues without running pipeline

Usage:
    python monitor_quality.py
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).parent))

from src.database.connection import get_db
from src.database.models import Article, NarrativeSynthesis, AnalysisRun

# ANSI colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
BOLD = '\033[1m'
RESET = '\033[0m'


def print_section(title):
    print(f"\n{BLUE}{BOLD}═══ {title} ═══{RESET}")


def check_issue(condition, pass_msg, fail_msg):
    """Check a condition and print colored result"""
    if condition:
        print(f"{GREEN}✓{RESET} {pass_msg}")
        return True
    else:
        print(f"{RED}✗{RESET} {fail_msg}")
        return False


def monitor():
    """Run all quality checks"""
    issues_found = []

    with get_db() as db:
        print_section("Issue 1: Random Stance Assignments")

        # Check for fallback/random assignments in recent articles
        recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        articles_with_metadata = db.query(Article).filter(
            Article.fetched_at >= recent_cutoff,
            Article.priority_metadata.isnot(None)
        ).all()

        fallback_count = 0
        random_count = 0

        for article in articles_with_metadata:
            metadata = article.priority_metadata or {}
            reasoning = str(metadata.get('reasoning', ''))

            if 'Fallback' in reasoning:
                fallback_count += 1
            if 'randomly' in reasoning.lower() or 'alternate' in reasoning.lower():
                random_count += 1

        if not check_issue(
            fallback_count == 0 and random_count == 0,
            f"No random assignments detected ({len(articles_with_metadata)} articles checked)",
            f"Found {fallback_count} fallback + {random_count} random assignments"
        ):
            issues_found.append("Random stance assignments detected")
            # Show examples
            for article in articles_with_metadata[:3]:
                metadata = article.priority_metadata or {}
                reasoning = str(metadata.get('reasoning', ''))
                if 'Fallback' in reasoning or 'randomly' in reasoning.lower():
                    print(f"  Example: Article {article.id}: {reasoning[:80]}")

        print_section("Issue 2 & 3: NEUTRAL Stance & Distribution")

        # Check for NEUTRAL stances in trend metadata
        articles_with_trends = db.query(Article).filter(
            Article.fetched_at >= recent_cutoff,
            Article.priority_metadata.isnot(None)
        ).all()

        supporting = 0
        opposing = 0
        neutral = 0

        for article in articles_with_trends:
            metadata = article.priority_metadata or {}
            trends = metadata.get('trends', {})

            for trend_data in trends.values():
                stance = trend_data.get('stance', '')
                if stance == 'SUPPORTING':
                    supporting += 1
                elif stance == 'OPPOSING':
                    opposing += 1
                elif stance == 'NEUTRAL':
                    neutral += 1

        total_stances = supporting + opposing + neutral

        if total_stances > 0:
            print(f"{BLUE}ℹ{RESET} Stance distribution:")
            print(f"    SUPPORTING: {supporting} ({supporting/total_stances*100:.1f}%)")
            print(f"    OPPOSING: {opposing} ({opposing/total_stances*100:.1f}%)")
            print(f"    NEUTRAL: {neutral} ({neutral/total_stances*100:.1f}%)")

            check_issue(
                neutral > 0,
                "NEUTRAL stance is being used",
                "No NEUTRAL stances found (should exist for some articles)"
            )

            check_issue(
                total_stances > 0,
                f"Stance distribution active ({total_stances} total stances)",
                "Stance distribution is 0 - no trends recorded"
            )
        else:
            if not check_issue(
                False,
                "N/A",
                "No stance data found - trends may not be running"
            ):
                issues_found.append("Zero stance distribution")

        print_section("Issue 4: Narrative Synthesis Integrity")

        syntheses = db.query(NarrativeSynthesis).order_by(
            NarrativeSynthesis.generated_at.desc()
        ).limit(5).all()

        if len(syntheses) == 0:
            if not check_issue(
                False,
                "N/A",
                "No narrative syntheses found in database"
            ):
                issues_found.append("No syntheses")
        else:
            print(f"{BLUE}ℹ{RESET} Found {len(syntheses)} recent syntheses")

            for synthesis in syntheses:
                print(f"\n  Synthesis {synthesis.id} ({synthesis.generated_at}):")

                # Check for NULL synthesis_data
                if synthesis.synthesis_data is None:
                    if not check_issue(
                        False,
                        "N/A",
                        f"    synthesis_data is NULL"
                    ):
                        issues_found.append(f"Synthesis {synthesis.id} NULL data")
                    continue

                # Check for required fields
                required_fields = ['temporal_layers', 'cross_domain_insights',
                                 'priority_actions', 'executive_summary']
                missing = [f for f in required_fields if f not in synthesis.synthesis_data]

                if missing:
                    if not check_issue(
                        False,
                        "N/A",
                        f"    Missing fields: {missing}"
                    ):
                        issues_found.append(f"Synthesis {synthesis.id} incomplete")
                else:
                    check_issue(
                        True,
                        f"    All required fields present",
                        "N/A"
                    )

                # Check executive summary
                if not synthesis.executive_summary:
                    if not check_issue(
                        False,
                        "N/A",
                        f"    Executive summary is empty"
                    ):
                        issues_found.append(f"Synthesis {synthesis.id} empty summary")

        print_section("Pipeline Health")

        # Check recent analysis runs
        recent_runs = db.query(AnalysisRun).order_by(
            AnalysisRun.created_at.desc()
        ).limit(5).all()

        if recent_runs:
            print(f"{BLUE}ℹ{RESET} Last 5 analysis runs:")
            for run in recent_runs:
                status_color = GREEN if run.status == 'completed' else RED
                print(f"  {status_color}{run.run_type:20s}{RESET} "
                      f"{run.created_at.strftime('%Y-%m-%d %H:%M')} "
                      f"- {run.status} ({run.articles_processed} articles)")
        else:
            print(f"{YELLOW}⚠{RESET} No analysis runs found")

        # Summary
        print_section("SUMMARY")

        if issues_found:
            print(f"\n{RED}{BOLD}Issues Found ({len(issues_found)}):{RESET}")
            for issue in issues_found:
                print(f"  • {issue}")
            print(f"\n{RED}Action Required: Investigate and fix issues above{RESET}\n")
            return 1
        else:
            print(f"\n{GREEN}{BOLD}✓ No data quality issues detected{RESET}\n")
            return 0


if __name__ == '__main__':
    exit_code = monitor()
    sys.exit(exit_code)
"""
Trust Command - AI Response Verification
Provides trust-verified Claude queries with transparency
"""
import asyncio
import click
from pathlib import Path
from ..config.settings import settings
from ..trust.trust_pipeline import TrustPipeline
from ..trust.trust_report import TrustReportFormatter


@click.command()
@click.argument('query', required=False)
@click.option('--no-verify', is_flag=True, help='Skip verification (just get trust-enhanced response)')
@click.option('--verify-facts-only', is_flag=True, help='Only verify factual claims (Stage 2B+)')
@click.option('--check-bias-only', is_flag=True, help='Only check bias/framing (Stage 2C+)')
@click.option('--check-tone-only', is_flag=True, help='Only check tone/intimacy (Stage 2D+)')
@click.option('--export', type=click.Path(), help='Export detailed report to file')
@click.option('--format', type=click.Choice(['json', 'text']), default='text', help='Export format (default: text)')
@click.option('--verbose', is_flag=True, help='Show detailed analysis')
def trust_command(query, no_verify, verify_facts_only, check_bias_only, check_tone_only, export, format, verbose):
    """
    Trust-verified Claude queries

    Provides AI responses with:
    1. Fact verification
    2. Bias/framing analysis
    3. Tone/intimacy checking

    If QUERY is not provided, enters interactive mode.

    Examples:
        insightweaver trust "What is quantum computing?"
        insightweaver trust "Explain AI safety" --verbose
        insightweaver trust "Market analysis" --export report.txt
        insightweaver trust --no-verify "Quick question"
    """
    # Check for API key
    if not settings.anthropic_api_key:
        click.echo("❌ Error: ANTHROPIC_API_KEY not configured", err=True)
        click.echo("Add ANTHROPIC_API_KEY to your .env file", err=True)
        raise click.Abort()

    # Interactive mode if no query provided
    if not query:
        click.echo("\n" + "=" * 70)
        click.echo("InsightWeaver Trust Mode")
        click.echo("=" * 70)
        click.echo("\nQuery Claude with trust verification enabled.")
        click.echo("Responses are analyzed for fact accuracy, bias, and tone.\n")

        try:
            query = click.prompt("Enter your query", type=str)
        except (click.Abort, KeyboardInterrupt):
            click.echo("\n\nExiting trust mode.")
            return

    # Determine verification flags
    if verify_facts_only or check_bias_only or check_tone_only:
        # Specific verification requested
        verify_facts = verify_facts_only
        check_bias = check_bias_only
        check_intimacy = check_tone_only
    else:
        # Default: all verifications (unless --no-verify)
        verify_facts = not no_verify
        check_bias = not no_verify
        check_intimacy = not no_verify

    # Run the trust pipeline
    asyncio.run(_run_trust_pipeline(
        query=query,
        verify_response=not no_verify,
        verify_facts=verify_facts,
        check_bias=check_bias,
        check_intimacy=check_intimacy,
        export_path=export,
        export_format=format,
        verbose=verbose
    ))


async def _run_trust_pipeline(
    query: str,
    verify_response: bool,
    verify_facts: bool,
    check_bias: bool,
    check_intimacy: bool,
    export_path: str,
    export_format: str,
    verbose: bool
):
    """
    Execute trust pipeline asynchronously

    Args:
        query: User's query
        verify_response: Whether to verify the response
        verify_facts: Whether to verify facts
        check_bias: Whether to check bias
        check_intimacy: Whether to check intimacy
        export_path: Path to export report (None = no export)
        export_format: Export format (json or text)
        verbose: Whether to show detailed output
    """
    formatter = TrustReportFormatter()

    # Initialize pipeline
    click.echo("\n🔍 Querying Claude with trust constraints...")
    pipeline = TrustPipeline()

    try:
        # Run full pipeline
        result = await pipeline.run_full_pipeline(
            user_query=query,
            verify_response=verify_response,
            verify_facts=verify_facts,
            check_bias=check_bias,
            check_intimacy=check_intimacy,
            temperature=1.0
        )

        # Display response
        click.echo(formatter.format_response_display(result["response"]))

        # Display analysis (if verification was run)
        if verify_response:
            click.echo("\n🔍 Analyzing response...")

            if "analysis" in result:
                # Show analysis
                if verbose:
                    click.echo(formatter.format_trust_analysis(result["analysis"]))
                else:
                    click.echo(formatter.format_compact_summary(result["analysis"]))
            else:
                click.echo("\n⚠️  Analysis not available")

        else:
            click.echo("\n✓ Response generated (verification skipped)")

        # Export if requested
        if export_path:
            export_content = None

            if export_format == 'json':
                export_content = formatter.export_to_json(result)
            else:  # text
                export_content = formatter.export_to_text(result)

            # Write to file
            with open(export_path, 'w', encoding='utf-8') as f:
                f.write(export_content)

            click.echo(f"\n💾 Report exported to: {export_path}")

    except Exception as e:
        click.echo(f"\n❌ Error: {e}", err=True)
        raise click.Abort()

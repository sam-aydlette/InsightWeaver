"""
Web Tools Helper
Provides async wrappers for web fetching functionality using httpx + BeautifulSoup
"""

import logging

import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify as md

logger = logging.getLogger(__name__)


async def web_fetch(url: str, prompt: str, timeout: int = 30) -> str:
    """
    Fetch content from URL and process with AI

    Fetches HTML content, converts to clean text, then uses Claude to answer
    the specific question about the content.

    Args:
        url: URL to fetch
        prompt: Prompt/question for processing the content
        timeout: Request timeout in seconds (default: 30)

    Returns:
        Processed/analyzed content from the URL

    Raises:
        Exception: If fetch fails or processing errors
    """
    from ..context.claude_client import ClaudeClient

    try:
        # Fetch URL content
        logger.info(f"Fetching URL: {url}")

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(
                url,
                headers={
                    "User-Agent": "InsightWeaver/1.0 (Fact Verification Bot)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            )
            response.raise_for_status()
            html_content = response.text

        logger.info(f"Successfully fetched {len(html_content)} bytes from {url}")

        # Parse HTML and extract text
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()

        # Convert to markdown for better structure preservation
        # This helps maintain headings, lists, etc.
        try:
            markdown_content = md(str(soup), heading_style="ATX")
        except Exception:
            # Fallback to plain text if markdown conversion fails
            markdown_content = soup.get_text(separator="\n", strip=True)

        # Clean up excessive whitespace
        lines = [line.strip() for line in markdown_content.split("\n") if line.strip()]
        clean_content = "\n".join(lines)

        # Truncate if too long (keep first 50000 chars to stay within token limits)
        # 50k characters is ~12.5k tokens, well within Claude's 200k token context window
        if len(clean_content) > 50000:
            clean_content = clean_content[:50000] + "\n\n[Content truncated for length...]"

        logger.info(f"Extracted {len(clean_content)} characters of clean text")

        # Use Claude to analyze the content and answer the prompt
        claude_client = ClaudeClient()

        analysis_prompt = f"""You are analyzing content from an authoritative web source.

SOURCE URL: {url}

CONTENT FROM SOURCE:
{clean_content}

TASK: {prompt}

Provide a factual, precise answer based ONLY on the content above. If the content doesn't contain the information needed to answer, state that clearly."""

        result = await claude_client.analyze(
            system_prompt="You are a web content analyzer. Extract specific factual information from provided web content accurately.",
            user_message=analysis_prompt,
            temperature=0.0,
        )

        logger.info(f"Successfully processed content from {url}")
        return result

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching {url}: {e.response.status_code}")
        raise Exception(f"Failed to fetch {url}: HTTP {e.response.status_code}")

    except httpx.TimeoutException:
        logger.error(f"Timeout fetching {url}")
        raise Exception(f"Timeout while fetching {url}")

    except httpx.RequestError as e:
        logger.error(f"Request error fetching {url}: {e}")
        raise Exception(f"Network error fetching {url}: {str(e)}")

    except Exception as e:
        logger.error(f"Web fetch failed for {url}: {e}")
        raise Exception(f"Failed to process content from {url}: {str(e)}")

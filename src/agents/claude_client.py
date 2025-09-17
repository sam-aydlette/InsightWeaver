"""
Claude API Client
Handles communication with Anthropic's Claude API
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
import json
import httpx
from datetime import datetime

from src.config.settings import settings

logger = logging.getLogger(__name__)

class ClaudeClient:
    """Client for interacting with Claude API"""

    def __init__(self):
        self.api_key = settings.anthropic_api_key
        self.api_url = "https://api.anthropic.com/v1/messages"
        self.model = "claude-3-5-sonnet-20241022"
        self.max_tokens = 4096

        if not self.api_key:
            raise ValueError("Anthropic API key not configured. Please set ANTHROPIC_API_KEY environment variable.")

    async def send_message(self,
                          system_prompt: str,
                          user_prompt: str,
                          temperature: float = 0.1) -> str:
        """
        Send a message to Claude API and return the response
        """
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }

        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    json=payload
                )

                if response.status_code != 200:
                    error_msg = f"Claude API error {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)

                result = response.json()

                if "content" not in result or not result["content"]:
                    raise Exception("Empty response from Claude API")

                # Extract the text content from the response
                content = result["content"][0]["text"] if result["content"] else ""

                logger.debug(f"Claude API response received: {len(content)} characters")
                return content

        except httpx.TimeoutException:
            error_msg = "Claude API request timed out"
            logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            logger.error(f"Claude API request failed: {e}")
            raise

    async def analyze_batch(self,
                           system_prompt: str,
                           articles_data: List[Dict[str, Any]],
                           batch_size: int = 10) -> List[Dict[str, Any]]:
        """
        Analyze a batch of articles with rate limiting
        """
        results = []

        for i in range(0, len(articles_data), batch_size):
            batch = articles_data[i:i + batch_size]

            # Create user prompt for this batch
            user_prompt = self._create_batch_prompt(batch)

            try:
                response = await self.send_message(system_prompt, user_prompt)
                batch_results = self._parse_batch_response(response, batch)
                results.extend(batch_results)

                # Rate limiting - wait between batches
                if i + batch_size < len(articles_data):
                    await asyncio.sleep(1.0)

            except Exception as e:
                logger.error(f"Failed to analyze batch {i//batch_size + 1}: {e}")
                # Add default results for failed batch
                for article in batch:
                    results.append({
                        "article_id": article["id"],
                        "priority_score": 0.5,
                        "error": str(e)
                    })

        return results

    def _create_batch_prompt(self, articles: List[Dict[str, Any]]) -> str:
        """Create a prompt for a batch of articles"""
        articles_text = ""
        for i, article in enumerate(articles, 1):
            articles_text += f"Article {i} (ID: {article['id']}):\n"
            articles_text += f"Title: {article['title']}\n"
            articles_text += f"Published: {article['published_date']}\n"
            articles_text += f"Source: {article['source']}\n"
            articles_text += f"Content: {article['content'][:1000]}...\n\n"

        return f"Please analyze these {len(articles)} articles:\n\n{articles_text}"

    def _parse_batch_response(self, response: str, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse Claude's response for a batch of articles"""
        results = []

        try:
            # Try to parse as JSON first
            if response.strip().startswith('[') or response.strip().startswith('{'):
                parsed = json.loads(response)
                if isinstance(parsed, list):
                    return parsed
                elif isinstance(parsed, dict) and "results" in parsed:
                    return parsed["results"]

            # If not JSON, try to extract structured data
            lines = response.split('\n')
            current_result = {}

            for line in lines:
                line = line.strip()
                if line.startswith('Article ID:') or line.startswith('ID:'):
                    if current_result:
                        results.append(current_result)
                    current_result = {"article_id": self._extract_id(line)}
                elif line.startswith('Priority Score:') or line.startswith('Score:'):
                    current_result["priority_score"] = self._extract_score(line)
                elif line.startswith('Reasoning:') or line.startswith('Rationale:'):
                    current_result["reasoning"] = line.split(':', 1)[1].strip()

            if current_result:
                results.append(current_result)

        except Exception as e:
            logger.warning(f"Failed to parse Claude response, using defaults: {e}")

        # Ensure we have results for all articles
        for article in articles:
            if not any(r.get("article_id") == article["id"] for r in results):
                results.append({
                    "article_id": article["id"],
                    "priority_score": 0.5,
                    "reasoning": "Failed to parse response"
                })

        return results[:len(articles)]  # Ensure we don't return more than input

    def _extract_id(self, line: str) -> int:
        """Extract article ID from a line"""
        import re
        match = re.search(r'\d+', line)
        return int(match.group()) if match else 0

    def _extract_score(self, line: str) -> float:
        """Extract priority score from a line"""
        import re
        match = re.search(r'[\d.]+', line)
        return float(match.group()) if match else 0.5
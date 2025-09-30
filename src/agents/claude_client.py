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

    def __init__(self, model="claude-sonnet-4-20250514"):
        self.api_key = settings.anthropic_api_key
        self.api_url = "https://api.anthropic.com/v1/messages"
        self.model = model
        self.max_tokens = 4096

        if not self.api_key:
            raise ValueError("Anthropic API key not configured. Please set ANTHROPIC_API_KEY environment variable.")

    async def send_message(self,
                          system_prompt: str,
                          user_prompt: str,
                          temperature: float = 0.1,
                          timeout: float = 60.0) -> str:
        """
        Send a message to Claude API and return the response

        Args:
            system_prompt: System instructions for Claude
            user_prompt: User message/query
            temperature: Sampling temperature (0.0-1.0)
            timeout: Request timeout in seconds (default 60s)
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
            async with httpx.AsyncClient(timeout=timeout) as client:
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
                    logger.error(f"Empty content in API response. Full response keys: {result.keys()}")
                    raise Exception("Empty response from Claude API")

                # Extract the text content from the response
                content_array = result.get("content", [])
                logger.debug(f"Content array length: {len(content_array)}")

                # Concatenate all text blocks (Claude may return multiple content blocks)
                content = ""
                for block in content_array:
                    if isinstance(block, dict) and block.get("type") == "text":
                        content += block.get("text", "")

                if not content:
                    logger.error(f"No text content extracted from response")
                    logger.error(f"Content array: {content_array}")

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

    async def analyze_trend_batch(self,
                                 system_prompt: str,
                                 articles_data: List[Dict[str, Any]],
                                 batch_size: int = 10) -> List[Dict[str, Any]]:
        """
        Analyze a batch of articles for trend stance with custom parsing
        """
        results = []

        for i in range(0, len(articles_data), batch_size):
            batch = articles_data[i:i + batch_size]

            # Create user prompt for this batch (trend-specific)
            user_prompt = self._create_trend_batch_prompt(batch)

            try:
                response = await self.send_message(system_prompt, user_prompt)

                # Validate response structure BEFORE parsing
                batch_num = i//batch_size + 1
                logger.info(f"Batch {batch_num}: Received response ({len(response)} chars)")

                # Check for basic JSON structure
                if not response.strip().startswith('{'):
                    logger.warning(f"Batch {batch_num}: Response doesn't start with {{ - may have prefix text")
                    logger.warning(f"Batch {batch_num}: Response starts with: '{response[:100]}'")

                if not response.strip().endswith('}'):
                    logger.warning(f"Batch {batch_num}: Response doesn't end with }} - likely truncated")
                    logger.warning(f"Batch {batch_num}: Response ends with: '{response[-100:]}'")

                # Check for required structure
                if '"article_analysis"' not in response:
                    logger.error(f"Batch {batch_num}: Missing 'article_analysis' key in response")
                    logger.error(f"Batch {batch_num}: Full response: {response}")

                # Additional debug for problematic batches
                if len(response) > 4000:  # Long responses are more likely to be truncated
                    logger.warning(f"Batch {batch_num}: Response is long ({len(response)} chars) - truncation risk")

                batch_results = self._parse_trend_response(response, batch)
                results.extend(batch_results)

                # Rate limiting - wait between batches
                if i + batch_size < len(articles_data):
                    await asyncio.sleep(1.0)

            except Exception as e:
                logger.error(f"Failed to analyze trend batch {i//batch_size + 1}: {e}")
                # Fail explicitly during development
                raise ValueError(f"Failed to analyze batch {i//batch_size + 1}: {e}")

        return results

    def _parse_json_with_repair(self, json_str: str) -> dict:
        """Robust JSON parser with multiple GenAI-specific repair strategies"""
        import json
        import re

        logger.info(f"Attempting JSON parse of {len(json_str)} character response")

        # First attempt: Parse as-is
        try:
            result = json.loads(json_str)
            logger.info("✓ JSON parsed successfully on first attempt")
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"Initial JSON parse failed: {e}, attempting GenAI repairs...")

        # GENAI REPAIR LAYER 1: Handle common Claude prefixes/suffixes
        repaired = json_str.strip()
        try:
            # Remove common Claude commentary prefixes
            prefixes_to_remove = [
                r'^.*?Here is the JSON.*?:\s*',
                r'^.*?Here\'s the JSON.*?:\s*',
                r'^.*?JSON analysis.*?:\s*',
                r'^.*?Here are the results.*?:\s*',
                r'^.*?Analysis results.*?:\s*',
                r'^.*?Based on.*?:\s*',
                r'^[^{]*'  # Remove everything before first {
            ]

            for prefix_pattern in prefixes_to_remove:
                repaired = re.sub(prefix_pattern, '', repaired, flags=re.IGNORECASE | re.DOTALL, count=1)
                if repaired.startswith('{'):
                    break

            # Remove markdown code blocks
            if '```json' in repaired:
                repaired = re.sub(r'```json\s*', '', repaired)
                repaired = re.sub(r'```\s*$', '', repaired)
            elif '```' in repaired:
                repaired = re.sub(r'```\s*', '', repaired, count=1)
                repaired = re.sub(r'```\s*$', '', repaired)

            result = json.loads(repaired)
            logger.info("✓ JSON parsed after removing Claude prefixes")
            return result
        except json.JSONDecodeError:
            pass

        # GENAI REPAIR LAYER 2: Fix missing commas (most common GenAI issue)
        try:
            # Fix missing commas between objects in arrays
            repaired = re.sub(r'}\s*{', '},{', repaired)
            # Fix missing commas between object properties
            repaired = re.sub(r'"\s*"([^"]+)"\s*:', r'", "\1":', repaired)
            # Fix missing commas after values before new keys
            repaired = re.sub(r'(["\d\]]})\s*"([^"]+)"\s*:', r'\1, "\2":', repaired)

            result = json.loads(repaired)
            logger.info("✓ JSON parsed after fixing missing commas")
            return result
        except json.JSONDecodeError:
            pass

        # GENAI REPAIR LAYER 3: Handle truncation and incomplete responses
        try:
            # If response appears truncated, try to complete it
            if not repaired.rstrip().endswith('}'):
                logger.warning("Response appears truncated, attempting to complete...")

                # Count unclosed brackets
                open_braces = repaired.count('{')
                close_braces = repaired.count('}')
                open_brackets = repaired.count('[')
                close_brackets = repaired.count(']')

                # Try to find the last complete article entry
                last_complete_match = re.search(r'.*"reasoning"\s*:\s*"[^"]*"}\s*(?:,\s*)?', repaired, re.DOTALL)
                if last_complete_match:
                    # Truncate to last complete entry and close properly
                    repaired = last_complete_match.group(0).rstrip().rstrip(',')
                    repaired += ']}'
                else:
                    # Close any incomplete entry and structure
                    if repaired.rstrip().endswith('"'):
                        repaired += '"}'
                    elif repaired.rstrip().endswith(','):
                        repaired = repaired.rstrip().rstrip(',')

                    # Close arrays and objects
                    if open_brackets > close_brackets:
                        repaired += ']' * (open_brackets - close_brackets)
                    if open_braces > close_braces:
                        repaired += '}' * (open_braces - close_braces)

                result = json.loads(repaired)
                logger.info("✓ JSON parsed after truncation repair")
                return result
        except json.JSONDecodeError:
            pass

        # GENAI REPAIR LAYER 4: Fix trailing commas and quote issues
        try:
            # Remove trailing commas
            repaired = re.sub(r',(\s*[}\]])', r'\1', repaired)
            # Fix single quotes (Claude sometimes uses them)
            repaired = re.sub(r"'([^']*)'", r'"\1"', repaired)
            # Fix unquoted keys
            repaired = re.sub(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'"\1":', repaired)

            result = json.loads(repaired)
            logger.info("✓ JSON parsed after fixing trailing commas and quotes")
            return result
        except json.JSONDecodeError:
            pass

        # GENAI REPAIR LAYER 5: Aggressive parsing - extract what we can
        try:
            logger.warning("Attempting aggressive parsing with regex extraction...")

            # Try to extract the article_analysis array content
            analysis_match = re.search(r'"article_analysis"\s*:\s*\[(.*?)\]', repaired, re.DOTALL)
            if analysis_match:
                array_content = analysis_match.group(1)

                # Split by likely article boundaries and parse each
                articles = []
                # Look for article_id patterns to split
                article_parts = re.split(r'(?="article_id")', array_content)

                for part in article_parts:
                    if not part.strip():
                        continue

                    # Try to extract data from this part
                    article_id_match = re.search(r'"article_id"\s*:\s*"([^"]+)"', part)
                    stance_match = re.search(r'"stance"\s*:\s*"([^"]+)"', part)
                    confidence_match = re.search(r'"confidence"\s*:\s*([0-9.]+)', part)
                    reasoning_match = re.search(r'"reasoning"\s*:\s*"([^"]*)"', part)

                    if article_id_match:
                        article = {
                            "article_id": article_id_match.group(1),
                            "stance": stance_match.group(1) if stance_match else "OPPOSING",
                            "confidence": float(confidence_match.group(1)) if confidence_match else 0.5,
                            "reasoning": reasoning_match.group(1) if reasoning_match else "Extracted from malformed JSON"
                        }
                        articles.append(article)

                if articles:
                    result = {"article_analysis": articles}
                    logger.info(f"✓ Aggressive parsing recovered {len(articles)} articles")
                    return result
        except Exception as e:
            logger.warning(f"Aggressive parsing failed: {e}")

        # FINAL FALLBACK: Create minimal response with extracted IDs
        try:
            logger.warning("All parsing attempts failed, creating minimal fallback response...")

            # Extract any article IDs we can find
            id_pattern = r'"?article_id"?\s*:\s*"?([^",\s}]+)"?'
            article_ids = re.findall(id_pattern, json_str, re.IGNORECASE)

            # Also try to extract from article lists in prompt
            if not article_ids:
                # Look for "Article X (ID: Y)" patterns from the prompt
                prompt_id_pattern = r'Article\s+\d+\s*\(ID:\s*([^)]+)\)'
                article_ids = re.findall(prompt_id_pattern, json_str)

            # DO NOT CREATE FAKE DATA - removed fallback mechanism that invented stances
            pass

        except Exception as fallback_error:
            logger.error(f"Even fallback extraction failed: {fallback_error}")

        # Absolute failure - log everything and raise
        logger.error("=" * 80)
        logger.error("COMPLETE JSON PARSING FAILURE")
        logger.error("=" * 80)
        logger.error(f"Original response length: {len(json_str)} characters")
        logger.error(f"Final repaired attempt: {repaired[:500]}...")
        logger.error("=" * 80)

        raise ValueError(f"All JSON repair strategies failed - GenAI response is completely unparseable")

    def _create_trend_batch_prompt(self, articles: List[Dict[str, Any]]) -> str:
        """Create a prompt for trend analysis of a batch of articles"""
        articles_text = ""
        for i, article in enumerate(articles, 1):
            articles_text += f"Article {i} (ID: {article['id']}):\n"
            articles_text += f"Title: {article['title'][:80]}\n"
            content = article.get('content', '')
            if content:
                # Reduced content to prevent truncation
                articles_text += f"Content: {content[:200]}\n\n"
            else:
                articles_text += "\n"

        return f"Analyze these {len(articles)} articles:\n\n{articles_text}"

    def _parse_trend_response(self, response: str, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse trend analysis response from Claude with robust handling"""
        try:
            import json
            import re

            # Step 1: Remove any text before the JSON starts
            # Look for common prefixes Claude might add
            json_start_patterns = [
                r'Here is the JSON.*?:\s*\n',
                r'Here\'s the JSON.*?:\s*\n',
                r'JSON analysis.*?:\s*\n',
                r'Analysis result.*?:\s*\n',
                r'^[^{]*'  # Remove everything before first {
            ]

            response_cleaned = response.strip()
            for pattern in json_start_patterns:
                response_cleaned = re.sub(pattern, '', response_cleaned, flags=re.IGNORECASE | re.DOTALL, count=1)
                if response_cleaned.startswith('{'):
                    break

            # Step 2: Remove markdown code blocks
            if "```json" in response_cleaned:
                response_cleaned = re.sub(r'```json\s*', '', response_cleaned)
                response_cleaned = re.sub(r'```\s*$', '', response_cleaned)
            elif "```" in response_cleaned:
                response_cleaned = re.sub(r'```\s*', '', response_cleaned)

            # Step 3: Handle truncated JSON by attempting to fix common issues
            response_cleaned = response_cleaned.strip()

            # If response appears truncated (doesn't end with }), try to close it
            if response_cleaned and not response_cleaned.rstrip().endswith('}'):
                # Count opening and closing braces
                open_braces = response_cleaned.count('{')
                close_braces = response_cleaned.count('}')

                # Add missing closing braces
                if open_braces > close_braces:
                    # First, try to close any incomplete JSON objects
                    # Look for the last complete item and truncate there
                    last_complete = response_cleaned.rfind('},')
                    if last_complete > 0:
                        response_cleaned = response_cleaned[:last_complete + 1]
                        # Now close the structure properly
                        response_cleaned += ']' if '"article_analysis"' in response_cleaned else ''
                        response_cleaned += '}' * (open_braces - close_braces - 1)
                    else:
                        # If we can't find a complete item, close everything
                        response_cleaned += '"}' if response_cleaned.rstrip().endswith('"') else '"}'
                        response_cleaned += ']' if '[' in response_cleaned and ']' not in response_cleaned else ''
                        response_cleaned += '}' * max(0, open_braces - close_braces - 1)

            # Step 4: Parse the cleaned JSON with repair attempts
            response_data = self._parse_json_with_repair(response_cleaned)

            # Step 5: Extract article analysis
            if "article_analysis" in response_data:
                analysis_list = response_data["article_analysis"]

                # Validate and clean each item
                cleaned_results = []
                for item in analysis_list:
                    if isinstance(item, dict) and "article_id" in item:
                        # Ensure required fields with defaults
                        cleaned_item = {
                            "article_id": item.get("article_id"),
                            "stance": item.get("stance", "NEUTRAL"),
                            "confidence": float(item.get("confidence", 0.5)),
                            "reasoning": item.get("reasoning", "")[:500]  # Truncate long reasoning
                        }
                        cleaned_results.append(cleaned_item)

                logger.info(f"Successfully parsed {len(cleaned_results)} trend analyses")
                return cleaned_results
            else:
                logger.warning(f"No article_analysis in response structure")
                return []

        except json.JSONDecodeError as e:
            # During development, log the FULL response to debug malformed JSON
            logger.error(f"JSON parse failed: {e}")
            logger.error(f"FULL RAW RESPONSE causing parse failure:")
            logger.error(f"{'='*80}")
            logger.error(response)
            logger.error(f"{'='*80}")
            logger.error(f"Response length: {len(response)} characters")
            logger.error(f"Response ends with: '{response[-50:]}'")

            # Also log the cleaned version that failed
            logger.error(f"CLEANED JSON that failed to parse:")
            logger.error(f"{'='*80}")
            logger.error(json_str)
            logger.error(f"{'='*80}")

            raise ValueError(f"Failed to parse Claude response as JSON: {e}")
        except Exception as e:
            logger.error(f"Error parsing trend response: {e}")
            logger.error(f"Response was: {response[:500]}")
            raise

    def _fallback_regex_extraction(self, response: str, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fallback method to extract data using regex when JSON parsing fails"""
        import re

        results = []

        # Pattern to match individual article entries (NEUTRAL is optional for backward compatibility)
        pattern = r'"article_id"\s*:\s*"([^"]+)"[^}]*?"stance"\s*:\s*"(SUPPORTING|OPPOSING|NEUTRAL?)"[^}]*?"confidence"\s*:\s*([\d.]+)'

        matches = re.finditer(pattern, response, re.DOTALL)

        for match in matches:
            article_id = match.group(1)
            stance = match.group(2)
            confidence = float(match.group(3))

            # Try to extract reasoning if present
            reasoning_pattern = rf'"article_id"\s*:\s*"{article_id}"[^}}]*?"reasoning"\s*:\s*"([^"]*)"'
            reasoning_match = re.search(reasoning_pattern, response)
            reasoning = reasoning_match.group(1) if reasoning_match else ""

            results.append({
                "article_id": article_id,
                "stance": stance,
                "confidence": confidence,
                "reasoning": reasoning[:500]
            })

        if results:
            logger.info(f"Regex extraction recovered {len(results)} analyses")
        else:
            # DO NOT CREATE FAKE DATA - fail instead
            logger.error("Regex extraction failed - cannot recover trend analysis")
            logger.error(f"Response was: {response[:1000]}")
            raise ValueError("Failed to parse trend analysis response via both JSON and regex")

        return results

    def _create_batch_prompt(self, articles: List[Dict[str, Any]]) -> str:
        """Create a prompt for a batch of articles"""
        articles_text = ""
        for i, article in enumerate(articles, 1):
            articles_text += f"Article {i} (ID: {article['id']}):\n"
            articles_text += f"Title: {article['title'][:100]}\n"  # Limit title length
            articles_text += f"Age: {article.get('age_hours', 0):.1f}h\n"  # More relevant than published date
            # Only include summary if content exists (screening stage has empty content)
            content = article.get('content', '')
            if content:
                articles_text += f"Summary: {content[:300]}\n\n"
            else:
                articles_text += "\n"  # Just add spacing for screening stage

        return f"Analyze these {len(articles)} articles and return JSON with priority scores:\n\n{articles_text}"

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

    async def analyze_for_summary(self, prompt: str, model: str = "claude-3-haiku-20240307") -> Dict[str, Any]:
        """
        Generate executive summaries using Claude API
        Uses Haiku model for cost efficiency
        """
        system_prompt = """You are an intelligence analyst specializing in generating executive summaries for Northern Virginia government and technology professionals. Your summaries should be concise, actionable, and focused on decision-making implications."""

        try:
            # Use Haiku model for cost-effective summary generation
            original_model = self.model
            self.model = model

            response = await self.send_message(system_prompt, prompt, temperature=0.2)

            # Restore original model
            self.model = original_model

            # Clean up response
            summary_text = response.strip()

            # Remove any prefixes or commentary from Claude
            prefixes_to_remove = [
                "Here is the executive summary:",
                "Executive summary:",
                "Summary:",
                "Based on the analysis:",
            ]

            for prefix in prefixes_to_remove:
                if summary_text.lower().startswith(prefix.lower()):
                    summary_text = summary_text[len(prefix):].strip()

            return {
                "summary": summary_text,
                "success": True
            }

        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return {
                "summary": "Unable to generate executive summary due to API error.",
                "success": False,
                "error": str(e)
            }
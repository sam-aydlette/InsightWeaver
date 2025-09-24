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
        """Parse JSON with multiple repair attempts for common Claude errors"""
        import json
        import re

        # First attempt: Parse as-is
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"Initial JSON parse failed: {e}, attempting repairs...")

        # Repair attempt 1: Fix missing commas between objects
        try:
            # Pattern: }{  ->  },{
            repaired = re.sub(r'}\s*{', '},{', json_str)
            # Pattern: }"  ->  },"  (when followed by another object)
            repaired = re.sub(r'}"(\s*{)', r'}",\1', repaired)
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

        # Repair attempt 2: Fix missing commas between array elements
        try:
            # Pattern: "}  "article_id" -> "},  "article_id"
            repaired = re.sub(r'"}(\s*"article_id")', r'}",\1', json_str)
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

        # Repair attempt 2b: Fix missing commas between object properties
        try:
            # Pattern: "value"  "key": -> "value",  "key":
            repaired = re.sub(r'"(\s*"[^"]+"\s*:)', r'",\1', json_str)
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

        # Repair attempt 3: Fix trailing comma issues
        try:
            # Remove trailing commas before closing brackets
            repaired = re.sub(r',(\s*[}\]])', r'\1', json_str)
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

        # Repair attempt 4: Add missing quotes around unquoted keys/values
        try:
            # Fix unquoted keys: article_id: -> "article_id":
            repaired = re.sub(r'([a-zA-Z_]+):', r'"\1":', json_str)
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

        # Repair attempt 5: Try to extract valid JSON substring
        try:
            # Find the largest valid JSON substring
            for i in range(len(json_str), 0, -1):
                try:
                    subset = json_str[:i]
                    # Try to close any unclosed structures
                    if subset.count('{') > subset.count('}'):
                        subset += '}' * (subset.count('{') - subset.count('}'))
                    if subset.count('[') > subset.count(']'):
                        subset += ']' * (subset.count('[') - subset.count(']'))
                    return json.loads(subset)
                except json.JSONDecodeError:
                    continue
        except:
            pass

        # Final fallback: Extract article IDs and create minimal valid response
        try:
            import re
            logger.warning("All JSON repairs failed, attempting fallback extraction...")

            # Extract article IDs from the text
            id_pattern = r'"article_id"\s*:\s*"([^"]+)"'
            article_ids = re.findall(id_pattern, json_str)

            if article_ids:
                # Create minimal valid JSON response
                fallback_response = {
                    "article_analysis": []
                }

                for article_id in article_ids:
                    fallback_response["article_analysis"].append({
                        "article_id": article_id,
                        "stance": "OPPOSING",  # Default to opposing for balanced results
                        "confidence": 0.1,
                        "reasoning": "Fallback extraction due to JSON parse failure"
                    })

                logger.warning(f"Fallback extraction successful: created response for {len(article_ids)} articles")
                return fallback_response

        except Exception as fallback_error:
            logger.error(f"Even fallback extraction failed: {fallback_error}")

        # If absolutely everything fails, raise the original error with context
        logger.error(f"All JSON repair attempts failed. Original string (first 1000 chars): {json_str[:1000]}")
        raise ValueError(f"Unable to parse JSON even after all repair attempts")

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
            # Last resort: assign 50/50 supporting/opposing when parsing fails
            logger.warning("Regex extraction failed, returning balanced stances as fallback")
            import random
            for i, article in enumerate(articles):
                # Alternate between supporting and opposing for balance
                stance = "SUPPORTING" if i % 2 == 0 else "OPPOSING"
                results.append({
                    "article_id": article.get("id", "unknown"),
                    "stance": stance,
                    "confidence": 0.1,  # Low confidence since it's a fallback
                    "reasoning": "Fallback stance due to parse error"
                })

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
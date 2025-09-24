"""
Local Sentiment Analysis
Uses spaCy for lightweight sentiment scoring and categorization
"""

import logging
from typing import Dict, List, Tuple, Optional
from enum import Enum
import spacy
from textblob import TextBlob

logger = logging.getLogger(__name__)

class SentimentCategory(Enum):
    """Granular categories for precise article classification"""
    # Government & Policy
    FEDERAL_POLICY = "federal_policy"           # Federal government decisions, legislation
    STATE_LOCAL_POLICY = "state_local_policy"   # State/local government, Virginia-specific
    DEFENSE_SECURITY = "defense_security"       # Military, national security, defense contracts
    REGULATORY = "regulatory"                   # New regulations, compliance, legal changes

    # Technology & Innovation
    AI_ML = "ai_ml"                            # Artificial intelligence, machine learning
    CYBERSECURITY = "cybersecurity"            # Security threats, breaches, protection
    GOV_TECH = "gov_tech"                      # Government technology, digital transformation
    TECH_INFRASTRUCTURE = "tech_infrastructure" # Cloud, data centers, networks

    # Crisis & Threats
    SECURITY_THREAT = "security_threat"         # Active threats, attacks, vulnerabilities
    ECONOMIC_DISRUPTION = "economic_disruption" # Market crashes, economic instability
    SYSTEM_FAILURE = "system_failure"          # Outages, technical failures
    NATURAL_DISASTER = "natural_disaster"      # Weather, emergencies, disasters

    # Business & Economy
    NOVA_ECONOMY = "nova_economy"              # Northern Virginia specific business
    FEDERAL_CONTRACTING = "federal_contracting" # Government contracts, procurement
    INVESTMENT_FUNDING = "investment_funding"   # Funding, acquisitions, investments
    MARKET_CHANGES = "market_changes"          # Industry trends, market shifts

    # General Information
    BACKGROUND_INFO = "background_info"        # General news, background context

class SentimentAnalyzer:
    """Lightweight sentiment analysis for article pre-filtering"""

    def __init__(self):
        self.nlp = None
        self._load_model()

        # Keywords for granular category detection
        self.category_keywords = {
            # Government & Policy
            SentimentCategory.FEDERAL_POLICY: [
                'congress', 'senate', 'house', 'biden', 'trump', 'federal government',
                'white house', 'executive order', 'legislation', 'bill', 'federal budget',
                'appropriations', 'homeland security', 'dhs', 'federal agency'
            ],
            SentimentCategory.STATE_LOCAL_POLICY: [
                'virginia', 'va', 'maryland', 'md', 'dc', 'richmond', 'alexandria',
                'fairfax', 'loudoun', 'prince william', 'arlington', 'governor youngkin',
                'northam', 'mcauliffe', 'virginia general assembly', 'county board'
            ],
            SentimentCategory.DEFENSE_SECURITY: [
                'pentagon', 'defense', 'military', 'navy', 'army', 'air force', 'dod',
                'national security', 'clearance', 'classified', 'defense contractor',
                'lockheed martin', 'northrop grumman', 'boeing', 'raytheon', 'general dynamics'
            ],
            SentimentCategory.REGULATORY: [
                'fcc', 'fda', 'epa', 'sec', 'ftc', 'regulation', 'compliance', 'enforcement',
                'ruling', 'decision', 'guidance', 'policy update', 'legal requirement'
            ],

            # Technology & Innovation
            SentimentCategory.AI_ML: [
                'artificial intelligence', 'ai', 'machine learning', 'ml', 'deep learning',
                'neural network', 'chatgpt', 'openai', 'claude', 'anthropic', 'llm',
                'generative ai', 'computer vision', 'natural language processing'
            ],
            SentimentCategory.CYBERSECURITY: [
                'cybersecurity', 'hack', 'breach', 'malware', 'ransomware', 'phishing',
                'vulnerability', 'zero day', 'cisa', 'nist', 'security clearance',
                'cyber attack', 'data breach', 'incident response', 'threat intelligence'
            ],
            SentimentCategory.GOV_TECH: [
                'government technology', 'digital transformation', 'modernization',
                'gsa', 'fedramp', 'government cloud', 'civic tech', 'digital services',
                'usds', '18f', 'government software', 'public sector technology'
            ],
            SentimentCategory.TECH_INFRASTRUCTURE: [
                'cloud computing', 'aws', 'azure', 'google cloud', 'data center',
                'infrastructure', 'network', 'bandwidth', 'fiber', 'internet', 'broadband'
            ],

            # Crisis & Threats
            SentimentCategory.SECURITY_THREAT: [
                'attack', 'threat', 'terrorism', 'espionage', 'foreign interference',
                'china', 'russia', 'north korea', 'iran', 'state actor', 'apt',
                'critical infrastructure', 'supply chain attack'
            ],
            SentimentCategory.ECONOMIC_DISRUPTION: [
                'recession', 'inflation', 'market crash', 'economic crisis', 'unemployment',
                'financial crisis', 'bank failure', 'economic downturn', 'gdp decline'
            ],
            SentimentCategory.SYSTEM_FAILURE: [
                'outage', 'failure', 'down', 'offline', 'system failure', 'technical issues',
                'service disruption', 'network failure', 'power outage', 'infrastructure failure'
            ],
            SentimentCategory.NATURAL_DISASTER: [
                'hurricane', 'tornado', 'earthquake', 'flood', 'wildfire', 'storm',
                'emergency', 'disaster', 'evacuation', 'fema', 'natural disaster'
            ],

            # Business & Economy
            SentimentCategory.NOVA_ECONOMY: [
                'northern virginia', 'nova', 'tysons', 'reston', 'herndon', 'mclean',
                'crystal city', 'rosslyn', 'ballston', 'clarendon', 'arlington',
                'dulles corridor', 'technology corridor', 'beltway'
            ],
            SentimentCategory.FEDERAL_CONTRACTING: [
                'federal contract', 'government contract', 'procurement', 'rfp', 'gsa contract',
                'idiq', 'prime contractor', 'subcontractor', 'acquisition', 'award',
                'contract vehicle', 'small business', 'set aside', 'oasis'
            ],
            SentimentCategory.INVESTMENT_FUNDING: [
                'funding', 'investment', 'venture capital', 'vc', 'acquisition', 'merger',
                'ipo', 'valuation', 'round', 'series a', 'series b', 'startup funding'
            ],
            SentimentCategory.MARKET_CHANGES: [
                'market trend', 'industry shift', 'disruption', 'innovation', 'competition',
                'market share', 'growth', 'decline', 'transformation', 'pivot'
            ]
        }

    def _load_model(self):
        """Load spaCy model for text processing"""
        try:
            # Try to load English model
            self.nlp = spacy.load("en_core_web_sm")
            logger.info("Loaded spaCy en_core_web_sm model")
        except OSError:
            logger.warning("spaCy en_core_web_sm not found, using basic tokenization")
            self.nlp = None

    def analyze_sentiment(self, title: str, content: str = "") -> Dict[str, float]:
        """
        Analyze sentiment of article title and content
        Returns polarity (-1 to 1) and subjectivity (0 to 1)
        """
        # Combine title and content, prioritizing title
        text = f"{title}. {content[:200]}" if content else title

        if not text:
            return {"polarity": 0.0, "subjectivity": 0.0, "confidence": 0.0}

        try:
            # Use TextBlob for simple sentiment analysis
            blob = TextBlob(text)

            # Weight title sentiment more heavily
            title_blob = TextBlob(title) if title else TextBlob("")
            title_weight = 0.7
            content_weight = 0.3

            if title and content:
                polarity = (title_blob.sentiment.polarity * title_weight +
                           blob.sentiment.polarity * content_weight)
                subjectivity = (title_blob.sentiment.subjectivity * title_weight +
                               blob.sentiment.subjectivity * content_weight)
            else:
                polarity = blob.sentiment.polarity
                subjectivity = blob.sentiment.subjectivity

            # Calculate confidence based on text length and subjectivity
            confidence = min(1.0, len(text) / 100.0) * (1.0 - abs(subjectivity - 0.5))

            return {
                "polarity": round(polarity, 3),
                "subjectivity": round(subjectivity, 3),
                "confidence": round(confidence, 3)
            }

        except Exception as e:
            logger.warning(f"Sentiment analysis failed: {e}")
            return {"polarity": 0.0, "subjectivity": 0.0, "confidence": 0.0}

    def categorize_article(self, title: str, content: str = "") -> SentimentCategory:
        """
        Categorize article using granular keyword matching with smart fallbacks
        """
        text = f"{title} {content}".lower()
        sentiment = self.analyze_sentiment(title, content)

        # Check for specific category keywords with weighted scoring
        category_scores = {}
        for category, keywords in self.category_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in text:
                    # Weight title matches higher than content matches
                    if keyword in title.lower():
                        score += 2
                    else:
                        score += 1

            if score > 0:
                category_scores[category] = score

        # If we found strong category matches, use the highest scoring one
        if category_scores:
            max_score = max(category_scores.values())
            # Only use keyword matching if we have a reasonably strong signal
            if max_score >= 2:
                return max(category_scores, key=category_scores.get)

        # Fallback: Use sentiment analysis for ambiguous articles
        polarity = sentiment["polarity"]

        # Smart fallbacks based on sentiment and common patterns
        if polarity < -0.4:
            # Negative sentiment - check for crisis indicators
            crisis_words = ['attack', 'failure', 'breach', 'threat', 'emergency', 'crisis']
            if any(word in text for word in crisis_words):
                return SentimentCategory.SECURITY_THREAT
            else:
                return SentimentCategory.ECONOMIC_DISRUPTION

        elif polarity > 0.4:
            # Positive sentiment - check for opportunity indicators
            business_words = ['funding', 'investment', 'growth', 'expansion', 'success']
            if any(word in text for word in business_words):
                return SentimentCategory.INVESTMENT_FUNDING
            else:
                return SentimentCategory.MARKET_CHANGES

        else:
            # Neutral sentiment - general background information
            return SentimentCategory.BACKGROUND_INFO

    def group_articles_by_sentiment(self, articles_data: List[Dict]) -> Dict[SentimentCategory, List[Dict]]:
        """
        Group articles by sentiment category and rank within each group
        """
        groups = {category: [] for category in SentimentCategory}

        for article in articles_data:
            title = article.get("title", "")
            content = article.get("content", "")

            # Analyze sentiment
            sentiment = self.analyze_sentiment(title, content)
            category = self.categorize_article(title, content)

            # Add sentiment data to article
            article_with_sentiment = {
                **article,
                "sentiment": sentiment,
                "category": category.value,
                "local_priority_score": self._calculate_local_priority(article, sentiment, category)
            }

            groups[category].append(article_with_sentiment)

        # Sort each group by local priority score
        for category in groups:
            groups[category].sort(key=lambda x: x["local_priority_score"], reverse=True)

        return groups

    def _calculate_local_priority(self, article: Dict, sentiment: Dict, category: SentimentCategory) -> float:
        """
        Calculate local priority score based on sentiment and metadata
        """
        base_score = 0.5

        # Age factor (newer is better, but not too new to be unverified)
        age_hours = article.get("age_hours", 24)
        if age_hours <= 1:
            age_factor = 0.8  # Very new, might be unverified
        elif age_hours <= 6:
            age_factor = 1.0  # Sweet spot
        elif age_hours <= 24:
            age_factor = 0.9  # Recent
        else:
            age_factor = 0.7  # Older

        # Sentiment factors
        polarity_abs = abs(sentiment["polarity"])
        confidence = sentiment["confidence"]

        # Category bonuses based on relevance to Northern Virginia government/tech professional
        category_bonus = {
            # Highest priority - immediate professional impact
            SentimentCategory.DEFENSE_SECURITY: 0.25,       # Defense contracts are huge in NoVA
            SentimentCategory.FEDERAL_CONTRACTING: 0.25,    # Core business relevance
            SentimentCategory.CYBERSECURITY: 0.25,          # Critical security concerns
            SentimentCategory.NOVA_ECONOMY: 0.25,           # Local economic impact

            # High priority - significant relevance
            SentimentCategory.FEDERAL_POLICY: 0.20,         # Federal government decisions
            SentimentCategory.GOV_TECH: 0.20,               # Government technology
            SentimentCategory.SECURITY_THREAT: 0.20,        # Security threats
            SentimentCategory.STATE_LOCAL_POLICY: 0.20,     # Local Virginia policy

            # Medium priority - professional interest
            SentimentCategory.AI_ML: 0.15,                  # AI/ML developments
            SentimentCategory.REGULATORY: 0.15,             # Regulatory changes
            SentimentCategory.TECH_INFRASTRUCTURE: 0.15,    # Infrastructure changes
            SentimentCategory.SYSTEM_FAILURE: 0.15,         # System reliability

            # Lower priority - general awareness
            SentimentCategory.INVESTMENT_FUNDING: 0.10,     # Business developments
            SentimentCategory.MARKET_CHANGES: 0.10,         # Market trends
            SentimentCategory.ECONOMIC_DISRUPTION: 0.10,    # Economic impact
            SentimentCategory.NATURAL_DISASTER: 0.05,       # Emergency preparedness

            # Baseline - background information
            SentimentCategory.BACKGROUND_INFO: 0.0          # General news
        }.get(category, 0.0)

        # Source reliability (if available)
        source = article.get("source", "").lower()
        source_bonus = 0.0
        reliable_sources = ["reuters", "associated press", "wall street journal", "washington post",
                           "new york times", "bloomberg", "techcrunch", "government", "federal"]
        if any(reliable in source for reliable in reliable_sources):
            source_bonus = 0.1

        # Calculate final score
        score = (base_score +
                (polarity_abs * 0.3) +     # Strong sentiment gets attention
                (confidence * 0.2) +       # Confident analysis
                category_bonus +           # Category importance
                source_bonus) * age_factor  # Adjust for timing

        return min(1.0, max(0.0, score))

    def get_top_articles_per_category(self, groups: Dict[SentimentCategory, List[Dict]],
                                    top_n: int = 3) -> Dict[str, List[Dict]]:
        """
        Get top N articles from each sentiment category
        """
        result = {}

        for category, articles in groups.items():
            if articles:  # Only include categories that have articles
                top_articles = articles[:top_n]
                result[category.value] = top_articles
                logger.info(f"Selected top {len(top_articles)} articles from {category.value} category")

        return result
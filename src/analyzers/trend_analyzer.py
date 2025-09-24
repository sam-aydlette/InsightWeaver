"""
Local Trend Analysis
Uses spaCy for lightweight trend categorization and keyword matching
"""

import logging
from typing import Dict, List, Tuple, Optional
from enum import Enum
import spacy
import re

logger = logging.getLogger(__name__)

class GlobalTrend(Enum):
    """15 major global trends to track"""

    # Economic & Governance Trends
    PRIVATIZATION_VS_REGULATION = "privatization_vs_regulation"
    ECONOMIC_GROWTH_VS_STAGNATION = "economic_growth_vs_stagnation"
    DEBT_EXPANSION_VS_FISCAL_RESTRAINT = "debt_expansion_vs_fiscal_restraint"
    FORMAL_VS_INFORMAL_ECONOMY = "formal_vs_informal_economy"

    # Geopolitical & Security Trends
    GEOPOLITICAL_FRAGMENTATION_VS_COOPERATION = "geopolitical_fragmentation_vs_cooperation"
    SECURITY_VS_PRIVACY = "security_vs_privacy"
    SCIENTIFIC_OPENNESS_VS_COMPETITION = "scientific_openness_vs_competition"

    # Technology & Society Trends
    DIGITAL_CENTRALIZATION_VS_DECENTRALIZATION = "digital_centralization_vs_decentralization"
    AUTOMATION_VS_HUMAN_LABOR = "automation_vs_human_labor"
    URBANIZATION_VS_DISTRIBUTED_LIVING = "urbanization_vs_distributed_living"
    CULTURAL_HOMOGENIZATION_VS_LOCALIZATION = "cultural_homogenization_vs_localization"

    # Demographic & Environmental Trends
    DEMOGRAPHIC_TRANSITION = "demographic_transition"
    ENERGY_TRANSITION = "energy_transition"
    CLIMATE_ACTION_VS_ECONOMIC_PRIORITIES = "climate_action_vs_economic_priorities"
    SOCIAL_COHESION_VS_POLARIZATION = "social_cohesion_vs_polarization"

class TrendAnalyzer:
    """Lightweight trend analysis for article pre-filtering and categorization"""

    def __init__(self):
        self.nlp = None
        self._load_model()

        # Comprehensive trend keyword dictionaries for local categorization
        self.trend_keywords = {
            GlobalTrend.PRIVATIZATION_VS_REGULATION: [
                # Privatization side
                'privatization', 'privatise', 'privatize', 'deregulation', 'deregulate',
                'market solutions', 'private sector', 'outsourcing', 'outsource',
                'public-private partnership', 'ppp', 'competitive bidding', 'free market',
                'economic liberalization', 'private ownership', 'market-driven',
                'competitive market', 'private enterprise', 'market competition',
                # Regulation side
                'government regulation', 'regulate', 'regulatory oversight', 'state intervention',
                'public sector', 'nationalization', 'nationalise', 'nationalize',
                'government control', 'public ownership', 'state-owned', 'state ownership',
                'regulatory framework', 'government oversight', 'public administration',
                'state control', 'regulatory compliance', 'government agency'
            ],

            GlobalTrend.GEOPOLITICAL_FRAGMENTATION_VS_COOPERATION: [
                # Fragmentation side
                'trade war', 'economic war', 'sanctions', 'tariffs', 'bilateral agreement',
                'regional bloc', 'economic nationalism', 'protectionism', 'protectionist',
                'decoupling', 'economic decoupling', 'unilateral', 'isolationism',
                'national sovereignty', 'national interest', 'america first', 'china first',
                'economic rivalry', 'strategic competition', 'bloc formation',
                # Cooperation side
                'multilateral', 'international cooperation', 'global governance',
                'united nations', 'un', 'international agreement', 'collective action',
                'global partnership', 'international alliance', 'consensus building',
                'diplomatic cooperation', 'international collaboration', 'global coordination',
                'multilateral institution', 'international treaty', 'global framework'
            ],

            GlobalTrend.ECONOMIC_GROWTH_VS_STAGNATION: [
                # Growth side
                'gdp growth', 'economic expansion', 'economic boom', 'productivity gains',
                'innovation boom', 'job creation', 'employment growth', 'investment boom',
                'economic recovery', 'bull market', 'market rally', 'business optimism',
                'economic dynamism', 'robust growth', 'strong economy', 'economic acceleration',
                'rising wages', 'wage growth', 'business confidence', 'economic momentum',
                # Stagnation side
                'recession', 'economic slowdown', 'economic contraction', 'stagnant wages',
                'unemployment', 'job losses', 'inflation', 'stagflation', 'economic crisis',
                'bear market', 'market decline', 'productivity decline', 'economic pessimism',
                'economic stagnation', 'slow growth', 'weak economy', 'economic uncertainty',
                'business pessimism', 'economic headwinds', 'declining productivity'
            ],

            GlobalTrend.DIGITAL_CENTRALIZATION_VS_DECENTRALIZATION: [
                # Centralization side
                'big tech', 'tech giants', 'gafa', 'platform monopoly', 'digital monopoly',
                'data concentration', 'algorithmic control', 'platform dominance',
                'tech oligopoly', 'centralized platform', 'gatekeeper', 'walled garden',
                'platform lock-in', 'digital dominance', 'tech concentration',
                'centralized control', 'platform power', 'digital gatekeeping',
                # Decentralization side
                'blockchain', 'cryptocurrency', 'crypto', 'bitcoin', 'ethereum',
                'decentralized', 'distributed system', 'peer-to-peer', 'p2p',
                'open source', 'data sovereignty', 'digital rights', 'self-sovereign',
                'web3', 'defi', 'dao', 'distributed ledger', 'decentralized finance',
                'digital sovereignty', 'open protocol', 'federated', 'distributed network'
            ],

            GlobalTrend.DEMOGRAPHIC_TRANSITION: [
                # Aging side
                'aging population', 'ageing population', 'demographic cliff', 'pension crisis',
                'elder care', 'elderly care', 'healthcare costs', 'workforce shortage',
                'retirement crisis', 'dependency ratio', 'longevity', 'senior care',
                'demographic decline', 'population decline', 'birth rate decline',
                'fertility decline', 'aging workforce', 'pension burden',
                # Youth side
                'youth bulge', 'young population', 'demographic dividend', 'youth unemployment',
                'education expansion', 'digital natives', 'emerging workforce',
                'population growth', 'birth rate', 'fertility rate', 'young workers',
                'youth employment', 'demographic growth', 'population boom'
            ],

            GlobalTrend.ENERGY_TRANSITION: [
                # Renewable side
                'renewable energy', 'clean energy', 'solar power', 'solar energy',
                'wind energy', 'wind power', 'green energy', 'green transition',
                'carbon neutral', 'net zero', 'electric vehicles', 'ev', 'battery',
                'energy storage', 'clean tech', 'cleantech', 'decarbonization',
                'renewable power', 'sustainable energy', 'green power', 'clean electricity',
                'energy efficiency', 'carbon reduction', 'emissions reduction',
                # Fossil fuel side
                'oil', 'petroleum', 'natural gas', 'lng', 'coal', 'fossil fuel',
                'carbon emissions', 'drilling', 'oil drilling', 'pipeline', 'refinery',
                'energy security', 'hydrocarbon', 'crude oil', 'gas pipeline',
                'oil production', 'gas production', 'fossil energy', 'conventional energy'
            ],

            GlobalTrend.URBANIZATION_VS_DISTRIBUTED_LIVING: [
                # Urbanization side
                'megacity', 'urban growth', 'city expansion', 'metropolitan area',
                'urban development', 'city planning', 'urban density', 'smart city',
                'urban infrastructure', 'urban population', 'city growth', 'metropolitan',
                'urban center', 'downtown', 'city center', 'urban living',
                'urban concentration', 'metropolitan growth', 'city development',
                # Distributed side
                'remote work', 'work from home', 'wfh', 'telecommuting', 'telework',
                'rural revival', 'small town', 'geographic dispersion', 'distributed workforce',
                'location independence', 'digital nomad', 'rural development',
                'suburban growth', 'small city', 'rural living', 'countryside',
                'distributed living', 'remote workforce', 'flexible work', 'hybrid work'
            ],

            GlobalTrend.AUTOMATION_VS_HUMAN_LABOR: [
                # Automation side
                'artificial intelligence', 'ai', 'machine learning', 'ml', 'robotics',
                'automation', 'robot', 'algorithmic decision', 'autonomous system',
                'digital transformation', 'process automation', 'ai adoption',
                'robotic process automation', 'rpa', 'automated system', 'smart automation',
                'intelligent automation', 'cognitive automation', 'ai-powered',
                # Human labor side
                'job protection', 'human workforce', 'employment protection', 'labor rights',
                'worker rights', 'skill development', 'human skills', 'human creativity',
                'human judgment', 'worker retraining', 'reskilling', 'upskilling',
                'labor unions', 'trade unions', 'job creation', 'human employment',
                'worker protection', 'employment security', 'human capital'
            ],

            GlobalTrend.CULTURAL_HOMOGENIZATION_VS_LOCALIZATION: [
                # Homogenization side
                'global culture', 'globalization', 'english dominance', 'cultural convergence',
                'universal values', 'standardization', 'global brands', 'multinational',
                'cultural imperialism', 'westernization', 'americanization', 'global media',
                'international culture', 'worldwide culture', 'global entertainment',
                'cultural globalization', 'uniform culture', 'mass culture',
                # Localization side
                'cultural preservation', 'indigenous rights', 'local culture', 'local content',
                'cultural protectionism', 'linguistic diversity', 'local traditions',
                'cultural sovereignty', 'regional identity', 'cultural revival',
                'local identity', 'traditional culture', 'cultural heritage',
                'indigenous culture', 'local language', 'cultural diversity', 'local customs'
            ],

            GlobalTrend.SECURITY_VS_PRIVACY: [
                # Security side
                'surveillance', 'national security', 'homeland security', 'data collection',
                'monitoring', 'intelligence gathering', 'security measures', 'law enforcement',
                'threat detection', 'biometric', 'facial recognition', 'security camera',
                'government surveillance', 'mass surveillance', 'security screening',
                'intelligence agency', 'security apparatus', 'surveillance state',
                # Privacy side
                'privacy rights', 'data protection', 'privacy law', 'encryption',
                'anonymity', 'digital rights', 'privacy legislation', 'data sovereignty',
                'personal data', 'privacy tools', 'digital freedom', 'civil liberties',
                'privacy advocacy', 'data privacy', 'digital privacy', 'privacy protection',
                'privacy-preserving', 'privacy technology', 'anonymous', 'private'
            ],

            GlobalTrend.DEBT_EXPANSION_VS_FISCAL_RESTRAINT: [
                # Debt expansion side
                'national debt', 'government debt', 'fiscal stimulus', 'deficit spending',
                'quantitative easing', 'qe', 'debt ceiling', 'borrowing', 'government borrowing',
                'monetary expansion', 'debt crisis', 'leveraging', 'fiscal expansion',
                'government spending', 'public spending', 'deficit', 'debt financing',
                'stimulus package', 'bailout', 'financial assistance',
                # Fiscal restraint side
                'austerity', 'fiscal discipline', 'debt reduction', 'deficit reduction',
                'balanced budget', 'spending cuts', 'fiscal responsibility', 'budget cuts',
                'monetary tightening', 'fiscal consolidation', 'debt ceiling', 'fiscal prudence',
                'budget discipline', 'expenditure control', 'fiscal conservatism',
                'government restraint', 'spending restraint', 'fiscal austerity'
            ],

            GlobalTrend.CLIMATE_ACTION_VS_ECONOMIC_PRIORITIES: [
                # Climate action side
                'climate action', 'climate policy', 'carbon reduction', 'emissions reduction',
                'environmental regulation', 'green investment', 'climate finance',
                'climate adaptation', 'carbon pricing', 'carbon tax', 'environmental protection',
                'climate commitment', 'green deal', 'paris agreement', 'climate target',
                'net zero', 'carbon neutral', 'climate emergency', 'climate crisis',
                # Economic priorities side
                'economic competitiveness', 'business competitiveness', 'industrial growth',
                'economic development', 'development needs', 'economic cost', 'compliance cost',
                'business concerns', 'growth priorities', 'economic impact', 'cost-benefit',
                'economic burden', 'regulatory burden', 'business impact', 'economic growth',
                'job creation', 'industrial development', 'economic activity'
            ],

            GlobalTrend.SCIENTIFIC_OPENNESS_VS_COMPETITION: [
                # Openness side
                'international collaboration', 'scientific collaboration', 'open science',
                'research cooperation', 'scientific exchange', 'knowledge sharing',
                'global research', 'academic collaboration', 'scientific diplomacy',
                'research partnership', 'international research', 'collaborative research',
                'open data', 'open access', 'scientific cooperation', 'research sharing',
                # Competition side
                'technology export controls', 'tech export controls', 'scientific decoupling',
                'research restrictions', 'ip protection', 'intellectual property',
                'technology competition', 'tech competition', 'strategic technology',
                'tech rivalry', 'innovation competition', 'tech sovereignty',
                'research security', 'technology transfer', 'scientific competition',
                'research rivalry', 'academic espionage', 'technology race'
            ],

            GlobalTrend.SOCIAL_COHESION_VS_POLARIZATION: [
                # Cohesion side
                'social unity', 'social cohesion', 'institutional trust', 'political center',
                'shared values', 'social solidarity', 'consensus building', 'bipartisan',
                'civic engagement', 'community building', 'social capital', 'national unity',
                'social harmony', 'political consensus', 'cross-party', 'moderate',
                'centrist', 'unity', 'cooperation', 'collaboration', 'compromise',
                # Polarization side
                'political polarization', 'polarization', 'identity politics', 'echo chamber',
                'extremism', 'political extremism', 'social fragmentation', 'tribal politics',
                'divisiveness', 'partisan divide', 'political tribalism', 'us vs them',
                'political division', 'social division', 'political conflict', 'partisanship',
                'radical', 'extreme', 'divided', 'fragmented', 'polarized'
            ],

            GlobalTrend.FORMAL_VS_INFORMAL_ECONOMY: [
                # Formal side
                'traditional employment', 'full-time employment', 'regulated market',
                'formal sector', 'institutional finance', 'traditional banking',
                'regulated industry', 'established business', 'formal contracts',
                'regulated economy', 'traditional finance', 'conventional banking',
                'formal business', 'traditional employer', 'standard employment',
                'regulated financial', 'institutional banking', 'formal employment',
                # Informal side
                'gig economy', 'gig work', 'platform work', 'freelance', 'contractor',
                'shadow banking', 'alternative finance', 'digital markets', 'unregulated',
                'informal sector', 'cryptocurrency', 'crypto', 'peer-to-peer lending',
                'p2p lending', 'fintech', 'digital currency', 'alternative payment',
                'platform economy', 'sharing economy', 'on-demand work', 'flexible work'
            ]
        }

    def _load_model(self):
        """Load spaCy model for text processing"""
        try:
            self.nlp = spacy.load("en_core_web_sm")
            logger.info("Loaded spaCy en_core_web_sm model for trend analysis")
        except OSError:
            logger.warning("spaCy en_core_web_sm not found, using basic text processing for trends")
            self.nlp = None

    def categorize_article_by_trends(self, title: str, content: str = "") -> Dict[str, float]:
        """
        Categorize article by trend relevance and return relevance scores

        Returns:
            Dict mapping trend names to relevance scores (0.0-1.0)
        """
        text = f"{title} {content}".lower()
        trend_scores = {}

        for trend, keywords in self.trend_keywords.items():
            score = 0.0
            keyword_matches = 0
            total_weight = 0

            for keyword in keywords:
                if keyword in text:
                    # Weight title matches higher than content matches
                    if keyword in title.lower():
                        weight = 2.0
                    else:
                        weight = 1.0

                    # Count occurrences for stronger signals
                    occurrences = text.count(keyword)
                    score += weight * occurrences
                    keyword_matches += 1
                    total_weight += weight

            # Normalize score and add diversity bonus
            if keyword_matches > 0:
                normalized_score = min(1.0, score / max(len(keywords) * 0.1, 1))

                # Bonus for multiple keyword matches (indicates strong relevance)
                diversity_bonus = min(0.3, keyword_matches / len(keywords))
                final_score = min(1.0, normalized_score + diversity_bonus)

                trend_scores[trend.value] = round(final_score, 3)

        return trend_scores

    def filter_articles_by_trends(self, articles_data: List[Dict],
                                 min_relevance: float = 0.1,
                                 max_per_trend: int = 50) -> Dict[str, List[Dict]]:
        """
        Filter and group articles by trend relevance

        Args:
            articles_data: List of article dictionaries
            min_relevance: Minimum relevance score to include article
            max_per_trend: Maximum articles per trend to send to API

        Returns:
            Dict mapping trend names to lists of relevant articles
        """
        trend_groups = {}

        for article in articles_data:
            title = article.get("title", "")
            content = article.get("content", "")

            # Get trend relevance scores
            trend_scores = self.categorize_article_by_trends(title, content)

            # Add article to relevant trend groups
            for trend_name, score in trend_scores.items():
                if score >= min_relevance:
                    if trend_name not in trend_groups:
                        trend_groups[trend_name] = []

                    # Add relevance score to article data
                    article_with_score = {
                        **article,
                        "trend_relevance_score": score,
                        "trend_category": trend_name
                    }
                    trend_groups[trend_name].append(article_with_score)

        # Sort and limit articles per trend
        for trend_name in trend_groups:
            # Sort by relevance score (highest first)
            trend_groups[trend_name].sort(
                key=lambda x: x["trend_relevance_score"],
                reverse=True
            )

            # Limit to max_per_trend most relevant articles
            trend_groups[trend_name] = trend_groups[trend_name][:max_per_trend]

        logger.info(f"Filtered articles into {len(trend_groups)} trend categories")
        for trend_name, articles in trend_groups.items():
            logger.info(f"  {trend_name}: {len(articles)} articles")

        return trend_groups

    def get_trend_statistics(self, trend_groups: Dict[str, List[Dict]]) -> Dict[str, any]:
        """
        Generate statistics about trend categorization
        """
        total_articles = sum(len(articles) for articles in trend_groups.values())
        total_categorized = len([article for articles in trend_groups.values() for article in articles])

        trend_stats = {}
        for trend_name, articles in trend_groups.items():
            if articles:
                scores = [article["trend_relevance_score"] for article in articles]
                trend_stats[trend_name] = {
                    "article_count": len(articles),
                    "avg_relevance": round(sum(scores) / len(scores), 3),
                    "max_relevance": round(max(scores), 3),
                    "top_article": articles[0]["title"][:60] + "..." if articles else ""
                }

        return {
            "total_trend_groups": len(trend_groups),
            "total_articles_categorized": total_categorized,
            "avg_articles_per_trend": round(total_categorized / len(trend_groups), 1) if trend_groups else 0,
            "trend_statistics": trend_stats
        }

    def categorize_articles_by_trends(self, articles_data: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Categorize multiple articles by trends and group them
        """
        # Use the existing filter_articles_by_trends method with correct parameters
        return self.filter_articles_by_trends(articles_data, min_relevance=0.1, max_per_trend=100)

    def get_trend_info(self, trend_name: str) -> Optional[Dict[str, str]]:
        """
        Get descriptive information about a trend
        """
        trend_descriptions = {
            "privatization_vs_regulation": {
                "description": "Privatization vs. Government Regulation - Market solutions vs. state intervention",
                "side_a": "privatization",
                "side_b": "regulation"
            },
            "geopolitical_fragmentation_vs_cooperation": {
                "description": "Geopolitical Fragmentation vs. Global Cooperation - Regional blocs vs. multilateral institutions",
                "side_a": "fragmentation",
                "side_b": "cooperation"
            },
            "economic_growth_vs_stagnation": {
                "description": "Economic Growth vs. Stagnation - GDP growth vs. recession risk",
                "side_a": "growth",
                "side_b": "stagnation"
            },
            "digital_centralization_vs_decentralization": {
                "description": "Digital Centralization vs. Decentralization - Tech monopolies vs. distributed systems",
                "side_a": "centralization",
                "side_b": "decentralization"
            },
            "demographic_transition": {
                "description": "Demographic Transition - Aging populations vs. youth bulges",
                "side_a": "aging",
                "side_b": "youth"
            },
            "energy_transition": {
                "description": "Energy Transition - Renewables vs. fossil fuels",
                "side_a": "renewables",
                "side_b": "fossil_fuels"
            },
            "urbanization_vs_distributed_living": {
                "description": "Urbanization vs. Distributed Living - Megacities vs. remote work dispersion",
                "side_a": "urbanization",
                "side_b": "distributed_living"
            },
            "automation_vs_human_labor": {
                "description": "Automation vs. Human Labor - AI/robotics vs. human employment",
                "side_a": "automation",
                "side_b": "human_labor"
            },
            "cultural_homogenization_vs_localization": {
                "description": "Cultural Homogenization vs. Localization - Global culture vs. local identity",
                "side_a": "homogenization",
                "side_b": "localization"
            },
            "security_vs_privacy": {
                "description": "Security vs. Privacy - Surveillance expansion vs. privacy rights",
                "side_a": "security",
                "side_b": "privacy"
            },
            "debt_expansion_vs_fiscal_restraint": {
                "description": "Debt Expansion vs. Fiscal Restraint - Spending vs. austerity",
                "side_a": "debt_expansion",
                "side_b": "fiscal_restraint"
            },
            "climate_action_vs_economic_priorities": {
                "description": "Climate Action vs. Economic Priorities - Environmental protection vs. economic growth",
                "side_a": "climate_action",
                "side_b": "economic_priorities"
            },
            "scientific_openness_vs_competition": {
                "description": "Scientific Openness vs. Strategic Competition - Research collaboration vs. tech rivalry",
                "side_a": "openness",
                "side_b": "competition"
            },
            "social_cohesion_vs_polarization": {
                "description": "Social Cohesion vs. Polarization - Unity vs. political division",
                "side_a": "cohesion",
                "side_b": "polarization"
            },
            "formal_vs_informal_economy": {
                "description": "Formal vs. Informal Economy - Traditional employment vs. gig work",
                "side_a": "formal",
                "side_b": "informal"
            }
        }

        return trend_descriptions.get(trend_name)
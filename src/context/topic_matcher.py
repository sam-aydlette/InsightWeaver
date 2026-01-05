"""
Topic Matcher - Article filtering by topic and geographic scope
Uses keyword matching and metadata to filter articles without AI inference
"""
import logging

from src.database.models import Article
from src.utils.profile_loader import UserProfile

logger = logging.getLogger(__name__)

# Topic keyword dictionaries with broad interpretation
TOPIC_KEYWORDS = {
    'cybersecurity': {
        'core': [
            'cybersecurity', 'cyber security', 'infosec', 'information security',
            'cyber', 'security breach', 'data security', 'network security'
        ],
        'threats': [
            'ransomware', 'malware', 'phishing', 'breach', 'hack', 'hacker',
            'zero day', 'zero-day', 'vulnerability', 'exploit', 'attack',
            'threat actor', 'backdoor', 'trojan', 'spyware', 'botnet',
            'ddos', 'denial of service', 'sql injection', 'xss'
        ],
        'tech': [
            'firewall', 'encryption', 'authentication', 'access control',
            'vpn', 'ids', 'intrusion detection', 'penetration test',
            'security patch', 'security update', 'mfa', 'multi-factor'
        ],
        'policy': [
            'cyber policy', 'data privacy', 'surveillance', 'CISA',
            'cybersecurity framework', 'nist', 'compliance', 'gdpr',
            'hipaa', 'data protection', 'privacy law'
        ],
        'industry': [
            'supply chain security', 'critical infrastructure',
            'industrial control', 'scada', 'ot security',
            'third-party risk', 'vendor security'
        ],
        'geopolitical': [
            'cyber warfare', 'state-sponsored', 'espionage',
            'nation-state', 'apt', 'advanced persistent threat',
            'cyber attack', 'cyber espionage'
        ],
        'entities': [
            'crowdstrike', 'palo alto', 'mandiant', 'cisa', 'nsa',
            'cisco', 'fortinet', 'microsoft security', 'google security',
            'amazon security', 'cloudflare'
        ]
    },
    'ai/ml': {
        'core': [
            'artificial intelligence', 'ai', 'machine learning', 'ml',
            'deep learning', 'neural network', 'ai model', 'ai system'
        ],
        'tech': [
            'llm', 'large language model', 'gpt', 'transformer',
            'generative ai', 'computer vision', 'nlp', 'natural language',
            'reinforcement learning', 'supervised learning', 'unsupervised learning',
            'training data', 'ai training', 'inference'
        ],
        'policy': [
            'ai regulation', 'ai safety', 'ai ethics', 'ai governance',
            'ai bias', 'algorithmic fairness', 'responsible ai',
            'ai transparency', 'explainable ai'
        ],
        'entities': [
            'openai', 'anthropic', 'google ai', 'microsoft ai',
            'deepmind', 'meta ai', 'nvidia', 'hugging face'
        ]
    },
    'software development': {
        'core': [
            'software development', 'programming', 'coding', 'developer',
            'software engineer', 'devops', 'agile', 'scrum'
        ],
        'tech': [
            'git', 'github', 'ci/cd', 'docker', 'kubernetes',
            'api', 'microservices', 'cloud native', 'serverless',
            'react', 'python', 'javascript', 'java', 'go'
        ],
        'tools': [
            'ide', 'visual studio', 'vscode', 'intellij',
            'jenkins', 'gitlab', 'jira', 'slack'
        ]
    },
    'cloud computing': {
        'core': [
            'cloud computing', 'cloud', 'saas', 'paas', 'iaas',
            'cloud services', 'cloud platform'
        ],
        'providers': [
            'aws', 'amazon web services', 'azure', 'microsoft azure',
            'gcp', 'google cloud', 'ibm cloud', 'oracle cloud'
        ],
        'tech': [
            's3', 'ec2', 'lambda', 'cloud storage', 'cloud database',
            'cloud security', 'cloud migration', 'multi-cloud', 'hybrid cloud'
        ]
    },
    'technology policy': {
        'core': [
            'technology policy', 'tech policy', 'tech regulation',
            'digital policy', 'internet policy'
        ],
        'topics': [
            'net neutrality', 'data privacy', 'antitrust', 'section 230',
            'content moderation', 'platform regulation', 'digital markets',
            'competition policy', 'tech monopoly'
        ],
        'entities': [
            'ftc', 'fcc', 'doj', 'eu commission', 'congress'
        ]
    },
    'privacy': {
        'core': [
            'privacy', 'data privacy', 'personal data', 'user data',
            'privacy rights', 'data protection'
        ],
        'topics': [
            'gdpr', 'ccpa', 'surveillance', 'tracking', 'cookies',
            'consent', 'data collection', 'privacy policy',
            'encryption', 'anonymization'
        ]
    },
    'education': {
        'core': [
            'education', 'school', 'university', 'college', 'student',
            'teacher', 'classroom', 'learning'
        ],
        'topics': [
            'education policy', 'curriculum', 'standardized test',
            'school funding', 'education budget', 'school board',
            'online learning', 'edtech', 'student loan'
        ]
    },
    'transportation': {
        'core': [
            'transportation', 'transit', 'commute', 'traffic',
            'infrastructure', 'public transport'
        ],
        'topics': [
            'metro', 'subway', 'bus', 'train', 'highway', 'road',
            'ev', 'electric vehicle', 'autonomous vehicle', 'self-driving'
        ]
    },
    'housing': {
        'core': [
            'housing', 'real estate', 'property', 'home', 'apartment',
            'rent', 'mortgage', 'housing market'
        ],
        'topics': [
            'affordable housing', 'housing crisis', 'zoning',
            'development', 'construction', 'homeowner', 'renter',
            'eviction', 'housing policy'
        ]
    }
}


class TopicMatcher:
    """
    Matches articles to topics using metadata and keyword expansion
    Provides both topic filtering and geographic scope filtering
    """

    def __init__(self):
        self.topic_keywords = TOPIC_KEYWORDS

    def matches_topic(self, article: Article, topic: str) -> tuple[bool, float]:
        """
        Check if article matches topic using metadata and weighted scoring

        Args:
            article: Article to check
            topic: Topic name (e.g., 'cybersecurity', 'ai/ml')

        Returns:
            (matches: bool, score: float) - Whether article matches and confidence score
        """
        score = 0.0

        # Get keywords for this topic
        keywords = self.topic_keywords.get(topic, {})
        if not keywords:
            logger.warning(f"Unknown topic: {topic}")
            return False, 0.0

        # Combine searchable text (title is most important, then description)
        text = ""
        if article.title:
            text += article.title.lower() + " "
        if article.description:
            text += article.description.lower() + " "

        # Add first 500 chars of content if available
        if article.normalized_content:
            text += article.normalized_content[:500].lower()

        # Category weights (how strongly each keyword category signals relevance)
        category_weights = {
            'core': 3.0,        # Core terms are strongest signal
            'threats': 2.0,     # Specific threats/technologies
            'policy': 2.0,      # Policy/governance terms
            'geopolitical': 2.0,
            'tech': 1.5,
            'industry': 1.5,
            'topics': 1.5,
            'tools': 1.0,
            'providers': 1.0,
            'entities': 1.0     # Mentioned companies/orgs
        }

        # Score based on keyword matches
        for category, terms in keywords.items():
            weight = category_weights.get(category, 1.0)
            matches = sum(1 for term in terms if term in text)
            score += matches * weight

        # Entity matching (strong signal if relevant entities mentioned)
        if article.entities and 'entities' in keywords:
            entity_keywords = keywords['entities']
            for entity in article.entities:
                if any(kw in entity.lower() for kw in entity_keywords):
                    score += 3.0  # High confidence for entity match

        # Feed category matching
        if article.feed and article.feed.category:
            category_lower = article.feed.category.lower()

            # Check if topic or core keywords in feed category
            if topic in category_lower:
                score += 2.0
            elif 'core' in keywords:
                core_keywords = keywords['core']
                if any(kw in category_lower for kw in core_keywords):
                    score += 2.0

        # Decision threshold: require minimum score
        threshold = 3.0
        matches = score >= threshold

        if matches:
            logger.debug(
                f"Article '{article.title[:50]}...' matched topic '{topic}' "
                f"with score {score:.1f}"
            )

        return matches, score

    def matches_scope(
        self,
        article: Article,
        scope: str,
        user_location: dict
    ) -> bool:
        """
        Check if article matches geographic scope

        Args:
            article: Article to check
            scope: Geographic scope ('local', 'state', 'national', 'global')
            user_location: User's location dict (city, state, region)

        Returns:
            bool - Whether article matches scope
        """
        # Combine searchable text
        text = ""
        if article.title:
            text += article.title.lower() + " "
        if article.description:
            text += article.description.lower()

        if scope == 'local':
            # Extract user location details
            city = user_location.get('city', '').lower()
            region = user_location.get('region', '').lower()

            # Check for direct mentions
            if city and city in text:
                return True
            if region and region in text:
                return True

            # Check entities for location matches
            if article.entities:
                for entity in article.entities:
                    entity_lower = entity.lower()
                    if (city and city in entity_lower) or (region and region in entity_lower):
                        return True

            # Check feed category for 'local'
            if article.feed and article.feed.category:
                if 'local' in article.feed.category.lower():
                    return True

            return False

        elif scope == 'state':
            state = user_location.get('state', '').lower()

            # State name in text
            if state and state in text:
                return True

            # State in feed category
            if article.feed and article.feed.category:
                cat = article.feed.category.lower()
                if state in cat or 'state' in cat or 'regional' in cat:
                    return True

            return False

        elif scope == 'national':
            national_keywords = [
                'federal', 'congress', 'senate', 'house of representatives',
                'washington', 'white house', 'national', 'u.s.', 'usa',
                'president', 'supreme court', 'fbi', 'cia', 'dhs', 'nationwide'
            ]

            # Check for national keywords
            if any(kw in text for kw in national_keywords):
                return True

            # Check feed category
            if article.feed and article.feed.category:
                cat = article.feed.category.lower()
                if any(kw in cat for kw in ['national', 'federal', 'us', 'usa']):
                    return True

            return False

        elif scope == 'global':
            # Global is more permissive - includes international news
            global_keywords = [
                'international', 'global', 'worldwide', 'world',
                'europe', 'asia', 'africa', 'united nations', 'nato',
                'g7', 'g20', 'china', 'russia', 'india'
            ]

            if any(kw in text for kw in global_keywords):
                return True

            if article.feed and article.feed.category:
                cat = article.feed.category.lower()
                if any(kw in cat for kw in ['global', 'international', 'world']):
                    return True

            return False

        # Unknown scope = no filtering
        logger.warning(f"Unknown scope: {scope}")
        return True

    def filter_articles(
        self,
        articles: list[Article],
        topic_filters: dict,
        user_profile: UserProfile
    ) -> list[Article]:
        """
        Apply topic and scope filters to article list

        Args:
            articles: List of Article objects to filter
            topic_filters: Dict with 'topics' and/or 'scopes' keys
            user_profile: UserProfile for location/context

        Returns:
            Filtered list of articles sorted by relevance score
        """
        filtered = articles.copy()
        filter_stats = {
            'input_count': len(articles),
            'topics': topic_filters.get('topics', []),
            'scopes': topic_filters.get('scopes', [])
        }

        # Apply topic filters (OR logic within topics)
        topics = topic_filters.get('topics', [])
        if topics:
            topic_matches = []
            for article in filtered:
                for topic in topics:
                    matches, score = self.matches_topic(article, topic)
                    if matches:
                        topic_matches.append((article, score))
                        break  # Article matches at least one topic

            # Sort by score (descending) to prioritize best matches
            topic_matches.sort(key=lambda x: x[1], reverse=True)
            filtered = [article for article, score in topic_matches]

            filter_stats['after_topic_filter'] = len(filtered)

        # Apply scope filters (OR logic within scopes)
        scopes = topic_filters.get('scopes', [])
        if scopes:
            user_location = user_profile.get_primary_location()
            scope_matches = []

            for article in filtered:
                for scope in scopes:
                    if self.matches_scope(article, scope, user_location):
                        scope_matches.append(article)
                        break  # Article matches at least one scope

            filtered = scope_matches
            filter_stats['after_scope_filter'] = len(filtered)

        filter_stats['output_count'] = len(filtered)

        logger.info(
            f"TopicMatcher: {filter_stats['output_count']}/{filter_stats['input_count']} "
            f"articles matched filters {topic_filters}"
        )

        return filtered

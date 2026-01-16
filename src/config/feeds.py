"""
RSS Feed Configuration for InsightWeaver
Curated list of 112 reliable, accurate RSS feeds organized by category
Focus: Northern Virginia residents with government, technology, and local news emphasis
Last Updated: September 2025
"""

RSS_FEEDS = {
    # Government & Political (Verified Working)
    "government": [
        {
            "name": "Supreme Court Blog",
            "url": "https://www.scotusblog.com/feed/",
            "category": "judicial",
            "description": "Supreme Court decisions and analysis",
        },
        {
            "name": "Congress.gov - House Floor Updates",
            "url": "https://www.congress.gov/rss/house-floor-today.xml",
            "category": "legislative",
            "description": "House of Representatives floor activity",
        },
        {
            "name": "Congress.gov - Senate Floor Updates",
            "url": "https://www.congress.gov/rss/senate-floor-today.xml",
            "category": "legislative",
            "description": "Senate floor activity",
        },
        {
            "name": "Federal Register - Public Inspection",
            "url": "https://www.federalregister.gov/documents/feeds/public-inspection.xml",
            "category": "federal_government",
            "description": "Documents on public inspection at the Office of the Federal Register",
        },
        {
            "name": "Federal Reserve Press Releases",
            "url": "https://www.federalreserve.gov/feeds/press_all.xml",
            "category": "monetary_policy",
            "description": "Federal Reserve announcements and monetary policy",
        },
        {
            "name": "SEC Press Releases",
            "url": "https://www.sec.gov/news/pressreleases.rss",
            "category": "financial_regulation",
            "description": "SEC enforcement and regulatory actions",
        },
        {
            "name": "USAGov Blog",
            "url": "https://blog.usa.gov/feed",
            "category": "federal_government",
            "description": "Official guide to government information and services",
        },
    ],
    # Virginia State & Local (Verified Working)
    "virginia": [
        {
            "name": "Virginia Mercury",
            "url": "https://www.virginiamercury.com/feed/",
            "category": "state_news",
            "description": "Virginia government and policy news",
        },
        {
            "name": "Supreme Court of Virginia Opinions",
            "url": "https://www.vacourts.gov/static/rss/rss_scv_opinions.xml",
            "category": "state_judicial",
            "description": "Virginia Supreme Court opinions",
        },
        {
            "name": "Virginia Court of Appeals Published Opinions",
            "url": "https://www.vacourts.gov/static/rss/rss_cav_p_opinions.xml",
            "category": "state_judicial",
            "description": "Virginia Court of Appeals published opinions",
        },
        {
            "name": "WAVY Virginia Politics",
            "url": "https://www.wavy.com/news/politics/virginia-politics/feed/",
            "category": "state_politics",
            "description": "Hampton Roads political coverage",
        },
        {
            "name": "Blue Virginia",
            "url": "https://bluevirginia.us/feed",
            "category": "state_politics",
            "description": "Progressive Virginia politics blog",
        },
        {
            "name": "Bacon's Rebellion",
            "url": "https://baconsrebellion.com/feed/",
            "category": "state_politics",
            "description": "Non-aligned Virginia politics and policy analysis",
        },
        {
            "name": "Cardinal News",
            "url": "https://cardinalnews.org/feed/",
            "category": "regional_news",
            "description": "Southwest Virginia news coverage",
        },
        {
            "name": "ARLnow",
            "url": "https://www.arlnow.com/feed/",
            "category": "local_news",
            "description": "Arlington County news and events",
        },
        {
            "name": "National Weather Service - Virginia",
            "url": "https://alerts.weather.gov/cap/va.php?x=0",
            "category": "weather_alerts",
            "description": "Virginia weather alerts and warnings",
        },
        {
            "name": "Arlington County RSS",
            "url": "https://www.arlingtonva.us/Government/News/RSS",
            "category": "local_government",
            "description": "Arlington County government news",
        },
        {
            "name": "Alexandria City RSS",
            "url": "https://www.alexandriava.gov/news/rss.xml",
            "category": "local_government",
            "description": "Alexandria city government news",
        },
        {
            "name": "Loudoun County RSS",
            "url": "https://www.loudoun.gov/rss.xml",
            "category": "local_government",
            "description": "Loudoun County government news",
        },
        {
            "name": "Prince William County RSS",
            "url": "https://www.pwcva.gov/news/rss.xml",
            "category": "local_government",
            "description": "Prince William County government news",
        },
        {
            "name": "DC Council RSS",
            "url": "https://dccouncil.us/feed/",
            "category": "dc_metro",
            "description": "DC Council legislative activity",
        },
    ],
    # Transportation (DC Metro Area)
    "transportation": [
        {
            "name": "WMATA Service Alerts",
            "url": "https://www.wmata.com/rider-tools/service-alerts/rss.cfm",
            "category": "transit",
            "description": "Washington Metro service alerts and updates",
        },
        {
            "name": "Virginia Railway Express",
            "url": "https://www.vre.org/news/rss.xml",
            "category": "transit",
            "description": "VRE commuter rail news and updates",
        },
        {
            "name": "VDOT Northern Virginia",
            "url": "https://www.virginiadot.org/news/northern_virginia_rss.xml",
            "category": "transportation_infrastructure",
            "description": "Northern Virginia transportation projects",
        },
    ],
    # National & International News (Verified Working)
    "news": [
        {
            "name": "NPR News",
            "url": "https://feeds.npr.org/1001/rss.xml",
            "category": "general_news",
            "description": "NPR national and international news",
        },
        {
            "name": "NPR Politics",
            "url": "https://feeds.npr.org/1014/rss.xml",
            "category": "politics",
            "description": "NPR political coverage",
        },
        {
            "name": "BBC World News",
            "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
            "category": "world_news",
            "description": "BBC international news coverage",
        },
        {
            "name": "BBC US & Canada",
            "url": "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml",
            "category": "us_news",
            "description": "BBC coverage of US and Canadian news",
        },
        {
            "name": "The Guardian US",
            "url": "https://www.theguardian.com/us-news/rss",
            "category": "us_news",
            "description": "Guardian US news coverage",
        },
        {
            "name": "The Guardian World",
            "url": "https://www.theguardian.com/world/rss",
            "category": "world_news",
            "description": "Guardian international news",
        },
        {
            "name": "The Hill",
            "url": "https://thehill.com/feed/",
            "category": "politics",
            "description": "Congressional and political news",
        },
        {
            "name": "Al Jazeera",
            "url": "https://www.aljazeera.com/xml/rss/all.xml",
            "category": "world_news",
            "description": "International news with Middle East focus",
        },
        {
            "name": "Deutsche Welle",
            "url": "https://rss.dw.com/rdf/rss-en-all",
            "category": "world_news",
            "description": "German international broadcaster",
        },
        {
            "name": "CNN Top Stories",
            "url": "http://rss.cnn.com/rss/edition.rss",
            "category": "general_news",
            "description": "CNN breaking news and top stories",
        },
        {
            "name": "ABC News Top Stories",
            "url": "https://feeds.abcnews.com/abcnews/topstories",
            "category": "general_news",
            "description": "ABC News headlines",
        },
        {
            "name": "CBS News Top Stories",
            "url": "https://www.cbsnews.com/latest/rss/main",
            "category": "general_news",
            "description": "CBS News latest stories",
        },
        {
            "name": "NBC News Top Stories",
            "url": "https://feeds.nbcnews.com/feeds/topstories",
            "category": "general_news",
            "description": "NBC News top headlines",
        },
        {
            "name": "Fox News Latest",
            "url": "https://moxie.foxnews.com/google-publisher/latest.xml",
            "category": "general_news",
            "description": "Fox News latest headlines",
        },
        {
            "name": "USA Today",
            "url": "http://rssfeeds.usatoday.com/usatoday-NewsTopStories",
            "category": "general_news",
            "description": "USA Today top news",
        },
        {
            "name": "Washington Post Politics",
            "url": "https://feeds.washingtonpost.com/rss/politics",
            "category": "politics",
            "description": "Washington Post political coverage",
        },
        {
            "name": "New York Times Homepage",
            "url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
            "category": "general_news",
            "description": "New York Times front page stories",
        },
    ],
    # Cybersecurity & Technology (Working Alternatives)
    "cybersecurity": [
        {
            "name": "Krebs on Security",
            "url": "https://krebsonsecurity.com/feed/",
            "category": "security_news",
            "description": "Cybersecurity news and investigation",
        },
        {
            "name": "Schneier on Security",
            "url": "https://www.schneier.com/feed/",
            "category": "security_analysis",
            "description": "Security analysis and commentary",
        },
        {
            "name": "The Hacker News",
            "url": "https://feeds.feedburner.com/TheHackersNews",
            "category": "security_news",
            "description": "Latest cybersecurity news and alerts",
        },
        {
            "name": "Dark Reading",
            "url": "https://www.darkreading.com/rss.xml",
            "category": "security_news",
            "description": "Enterprise security news",
        },
        {
            "name": "Bleeping Computer",
            "url": "https://www.bleepingcomputer.com/feed/",
            "category": "security_news",
            "description": "Security and technology news",
        },
        {
            "name": "SANS Internet Storm Center",
            "url": "https://isc.sans.edu/rssfeed.xml",
            "category": "security_alerts",
            "description": "Daily security diary and alerts",
        },
        {
            "name": "CSO Online",
            "url": "https://www.csoonline.com/feed/",
            "category": "security_news",
            "description": "Security and risk management",
        },
        {
            "name": "Graham Cluley",
            "url": "https://grahamcluley.com/feed/",
            "category": "security_analysis",
            "description": "Security news and opinion",
        },
        {
            "name": "Threatpost",
            "url": "https://threatpost.com/feed/",
            "category": "security_news",
            "description": "Information security news",
        },
        {
            "name": "SecurityWeek",
            "url": "https://www.securityweek.com/feed",
            "category": "security_news",
            "description": "Cybersecurity news and analysis",
        },
    ],
    # Technology & Innovation (Verified Working)
    "technology": [
        {
            "name": "TechCrunch",
            "url": "https://techcrunch.com/feed/",
            "category": "tech_news",
            "description": "Technology news and startup coverage",
        },
        {
            "name": "Ars Technica",
            "url": "https://feeds.arstechnica.com/arstechnica/index",
            "category": "tech_analysis",
            "description": "Technology news and analysis",
        },
        {
            "name": "The Verge",
            "url": "https://www.theverge.com/rss/index.xml",
            "category": "tech_news",
            "description": "Technology, science, art, and culture",
        },
        {
            "name": "Wired",
            "url": "https://www.wired.com/feed/rss",
            "category": "tech_culture",
            "description": "Technology and its impact on culture",
        },
        {
            "name": "MIT Technology Review",
            "url": "https://www.technologyreview.com/feed/",
            "category": "tech_research",
            "description": "Emerging technology insights",
        },
        {
            "name": "Mashable",
            "url": "https://mashable.com/feeds/rss/all",
            "category": "tech_culture",
            "description": "Digital culture and tech news",
        },
        {
            "name": "Engadget",
            "url": "https://www.engadget.com/rss.xml",
            "category": "tech_gadgets",
            "description": "Technology and gadget news",
        },
        {
            "name": "ZDNet",
            "url": "https://www.zdnet.com/news/rss.xml",
            "category": "tech_enterprise",
            "description": "Business technology news",
        },
        {
            "name": "Slashdot",
            "url": "http://rss.slashdot.org/Slashdot/slashdotMain",
            "category": "tech_community",
            "description": "News for nerds, stuff that matters",
        },
    ],
    # Economic & Financial (Working Feeds)
    "economic": [
        {
            "name": "Federal Reserve Press Releases",
            "url": "https://www.federalreserve.gov/feeds/press_all.xml",
            "category": "monetary_policy",
            "description": "Federal Reserve announcements",
        },
        {
            "name": "SEC Press Releases",
            "url": "https://www.sec.gov/news/pressreleases.rss",
            "category": "financial_regulation",
            "description": "SEC enforcement and regulatory actions",
        },
        {
            "name": "Bloomberg Markets",
            "url": "https://feeds.bloomberg.com/markets/news.rss",
            "category": "financial_markets",
            "description": "Financial markets news",
        },
        {
            "name": "MarketWatch Top Stories",
            "url": "https://feeds.marketwatch.com/marketwatch/topstories/",
            "category": "financial_news",
            "description": "Stock market and financial news",
        },
        {
            "name": "Financial Times",
            "url": "https://www.ft.com/?format=rss&edition=international",
            "category": "global_finance",
            "description": "Global financial news",
        },
        {
            "name": "CNBC Top News",
            "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
            "category": "business_news",
            "description": "CNBC top business news",
        },
        {
            "name": "Wall Street Journal Markets",
            "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
            "category": "financial_markets",
            "description": "WSJ market coverage",
        },
        {
            "name": "Yahoo Finance",
            "url": "https://finance.yahoo.com/news/rssindex",
            "category": "financial_news",
            "description": "Yahoo Finance top stories",
        },
        {
            "name": "Washington Business Journal",
            "url": "https://www.bizjournals.com/washington/feeds/latest.xml",
            "category": "regional_business",
            "description": "DC area business news",
        },
        {
            "name": "Northern Virginia Chamber",
            "url": "https://www.nvchamber.org/feed/",
            "category": "regional_business",
            "description": "Northern Virginia business community",
        },
        {
            "name": "DC Chamber of Commerce",
            "url": "https://www.dcchamber.org/feed/",
            "category": "regional_business",
            "description": "DC business community news",
        },
    ],
    # Environmental & Science (Verified Working)
    "environmental": [
        {
            "name": "NASA Breaking News",
            "url": "https://www.nasa.gov/rss/dyn/breaking_news.rss",
            "category": "space_science",
            "description": "NASA space and science news",
        },
        {
            "name": "Nature News",
            "url": "https://www.nature.com/nature.rss",
            "category": "scientific_research",
            "description": "Scientific research and discoveries",
        },
        {
            "name": "Science Magazine",
            "url": "https://www.science.org/rss/news_current.xml",
            "category": "scientific_research",
            "description": "Science news and research",
        },
        {
            "name": "National Weather Service Alerts - Virginia",
            "url": "https://alerts.weather.gov/cap/va.php?x=0",
            "category": "weather_alerts",
            "description": "Virginia weather alerts and warnings",
        },
        {
            "name": "Scientific American",
            "url": "http://rss.sciam.com/ScientificAmerican-Global",
            "category": "popular_science",
            "description": "Science news and analysis",
        },
        {
            "name": "Live Science",
            "url": "https://www.livescience.com/feeds/all",
            "category": "popular_science",
            "description": "Science news and discoveries",
        },
        {
            "name": "Phys.org",
            "url": "https://phys.org/rss-feed/",
            "category": "physics_news",
            "description": "Physics and technology news",
        },
    ],
    # International Organizations (Working Alternatives)
    "international": [
        {
            "name": "United Nations News",
            "url": "https://news.un.org/feed/subscribe/en/news/all/rss.xml",
            "category": "international_organizations",
            "description": "UN news and updates",
        },
        {
            "name": "IMF News",
            "url": "https://www.imf.org/en/News/RSS",
            "category": "international_finance",
            "description": "International Monetary Fund news",
        },
        {
            "name": "European Union News",
            "url": "https://www.consilium.europa.eu/en/press/rss/",
            "category": "european_union",
            "description": "EU Council press releases",
        },
    ],
    # Defense & Military (Working Feeds)
    "defense": [
        {
            "name": "Department of Defense",
            "url": "https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?max=10&ContentType=1&Site=945",
            "category": "military_news",
            "description": "DoD news releases",
        },
        {
            "name": "Army News",
            "url": "https://www.army.mil/rss/233/",
            "category": "military_branch",
            "description": "US Army news",
        },
        {
            "name": "Navy News",
            "url": "https://www.navy.mil/DesktopModules/ArticleCS/RSS.ashx?ContentType=1&Site=1&max=10",
            "category": "military_branch",
            "description": "US Navy news",
        },
        {
            "name": "Air Force News",
            "url": "https://www.af.mil/DesktopModules/ArticleCS/RSS.ashx?ContentType=1&Site=1&max=20",
            "category": "military_branch",
            "description": "US Air Force news",
        },
        {
            "name": "Military.com News",
            "url": "https://www.military.com/rss/",
            "category": "military_news",
            "description": "Military news and benefits information",
        },
        {
            "name": "Defense One",
            "url": "https://www.defenseone.com/rss/technology/",
            "category": "defense_technology",
            "description": "Defense technology and innovation news",
        },
        {
            "name": "C4ISRNET",
            "url": "https://www.c4isrnet.com/arc/outboundfeeds/rss/",
            "category": "defense_technology",
            "description": "Command, control, communications, computers intelligence, surveillance and reconnaissance",
        },
        {
            "name": "Breaking Defense",
            "url": "https://breakingdefense.com/feed/",
            "category": "defense_analysis",
            "description": "Defense industry analysis and breaking news",
        },
    ],
    # Federal Contractors & Technology
    "federal_contractors": [
        {
            "name": "Federal News Network",
            "url": "https://federalnewsnetwork.com/feed/",
            "category": "federal_contracting",
            "description": "Federal government news and contracting",
        },
        {
            "name": "Washington Technology",
            "url": "https://washingtontechnology.com/rss/all.aspx",
            "category": "government_technology",
            "description": "Government technology and IT contracting",
        },
        {
            "name": "FCW Federal Computer Week",
            "url": "https://fcw.com/rss-feeds/all.aspx",
            "category": "government_technology",
            "description": "Federal IT and technology news",
        },
        {
            "name": "FTC Press Releases",
            "url": "https://www.ftc.gov/news-events/press-releases/rss",
            "category": "federal_regulation",
            "description": "Federal Trade Commission press releases",
        },
        {
            "name": "FCC Daily Digest",
            "url": "https://www.fcc.gov/news-events/headlines/rss",
            "category": "telecommunications_regulation",
            "description": "Federal Communications Commission news",
        },
    ],
    # Science & Research
    "science": [
        {
            "name": "NIH News",
            "url": "https://www.nih.gov/news-events/news-releases/rss",
            "category": "medical_research",
            "description": "National Institutes of Health research news",
        },
        {
            "name": "NSF News",
            "url": "https://www.nsf.gov/news/news_feeds.jsp",
            "category": "scientific_research",
            "description": "National Science Foundation research updates",
        },
        {
            "name": "Smithsonian Magazine",
            "url": "https://www.smithsonianmag.com/rss/latest_articles/",
            "category": "science_culture",
            "description": "Science, history, and culture from Smithsonian",
        },
    ],
    # Legal & Regulatory
    "legal": [
        {
            "name": "Legal Times",
            "url": "https://www.law.com/legaltimes/rss/",
            "category": "legal_news",
            "description": "DC legal community news",
        }
    ],
    # Health & Public Health (Working Alternatives)
    "health": [
        {
            "name": "CDC Newsroom",
            "url": "https://tools.cdc.gov/api/v2/resources/media/316422.rss",
            "category": "public_health",
            "description": "CDC health alerts and updates",
        },
        {
            "name": "FDA News Releases",
            "url": "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml",
            "category": "food_drug_safety",
            "description": "FDA regulatory news",
        },
        {
            "name": "WebMD Health News",
            "url": "https://www.webmd.com/rss/health-news.xml",
            "category": "health_news",
            "description": "Consumer health news",
        },
        {
            "name": "MedPage Today",
            "url": "https://www.medpagetoday.com/rss/headlines.xml",
            "category": "medical_news",
            "description": "Medical news for healthcare professionals",
        },
        {
            "name": "New England Journal of Medicine",
            "url": "https://www.nejm.org/action/showFeed?jc=nejm&type=etoc&feed=rss",
            "category": "medical_journals",
            "description": "Medical research and reviews",
        },
    ],
    # Education & Research (Working Alternatives)
    "education": [
        {
            "name": "Chronicle of Higher Education",
            "url": "https://www.chronicle.com/feed",
            "category": "higher_education",
            "description": "Higher education news",
        },
        {
            "name": "Inside Higher Ed",
            "url": "https://www.insidehighered.com/rss/feed",
            "category": "higher_education",
            "description": "College and university news",
        },
        {
            "name": "EdWeek",
            "url": "https://www.edweek.org/feed/",
            "category": "k12_education",
            "description": "K-12 education news",
        },
        {
            "name": "THE Campus",
            "url": "https://www.timeshighereducation.com/campus/feed",
            "category": "higher_education",
            "description": "Times Higher Education campus news",
        },
    ],
    # Additional News Sources (Aggregators and Alternatives)
    "news_alternatives": [
        {
            "name": "Google News - US",
            "url": "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
            "category": "aggregator",
            "description": "Google News aggregator for US news",
        },
        {
            "name": "Google News - Virginia",
            "url": "https://news.google.com/rss/search?q=Virginia&hl=en-US&gl=US&ceid=US:en",
            "category": "virginia_aggregator",
            "description": "Google News aggregator for Virginia news",
        },
        {
            "name": "Reddit - Politics",
            "url": "https://www.reddit.com/r/politics/.rss",
            "category": "social_news",
            "description": "Political discussions from Reddit",
        },
        {
            "name": "Reddit - News",
            "url": "https://www.reddit.com/r/news/.rss",
            "category": "social_news",
            "description": "News discussions from Reddit",
        },
        {
            "name": "Hacker News",
            "url": "https://news.ycombinator.com/rss",
            "category": "tech_community",
            "description": "Hacker News front page",
        },
    ],
}


def get_all_feeds():
    """Return all feeds as a flat list with metadata"""
    all_feeds = []
    for category_group, feeds in RSS_FEEDS.items():
        for feed in feeds:
            feed_config = feed.copy()
            feed_config["category_group"] = category_group
            all_feeds.append(feed_config)
    return all_feeds


def get_feeds_by_category_group(category_group: str):
    """Get feeds filtered by category group"""
    return RSS_FEEDS.get(category_group, [])


def get_feed_count():
    """Get total number of configured feeds"""
    return len(get_all_feeds())


def get_feeds_by_category(category: str):
    """Get feeds filtered by specific category"""
    matching_feeds = []
    for category_group, feeds in RSS_FEEDS.items():
        for feed in feeds:
            if feed["category"] == category:
                feed_config = feed.copy()
                feed_config["category_group"] = category_group
                matching_feeds.append(feed_config)
    return matching_feeds


def get_category_list():
    """Get unique list of all categories"""
    categories = set()
    for feeds in RSS_FEEDS.values():
        for feed in feeds:
            categories.add(feed["category"])
    return sorted(categories)


def validate_feeds():
    """Validate feed structure and return any issues"""
    issues = []
    required_fields = ["name", "url", "category", "description"]

    for category_group, feeds in RSS_FEEDS.items():
        for i, feed in enumerate(feeds):
            for field in required_fields:
                if field not in feed:
                    issues.append(f"{category_group}[{i}]: Missing required field '{field}'")
                elif not feed[field]:
                    issues.append(f"{category_group}[{i}]: Empty value for field '{field}'")

            # Check for duplicate URLs
            all_urls = [f["url"] for f in get_all_feeds()]
            if all_urls.count(feed["url"]) > 1:
                issues.append(f"{category_group}[{i}]: Duplicate URL found: {feed['url']}")

    return issues


# Print summary when module is run directly
if __name__ == "__main__":
    print("RSS Feed Configuration Summary:")
    print(f"Total feeds configured: {get_feed_count()}")
    print("\nFeeds by category group:")
    for category_group in RSS_FEEDS:
        count = len(RSS_FEEDS[category_group])
        print(f"  {category_group}: {count} feeds")

    print(f"\nTotal unique categories: {len(get_category_list())}")

    # Validate configuration
    issues = validate_feeds()
    if issues:
        print("\nConfiguration issues found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\nConfiguration validated successfully!")

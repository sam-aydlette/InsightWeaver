#!/usr/bin/env python3
"""
InsightWeaver - An app that curates information from a wide range of reputable sources 
and creates custom daily reporting for me on events and trends that I care about.
"""

import feedparser
import sqlite3
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import hashlib
import os
from dotenv import load_dotenv
import anthropic

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# RSS Feed Sources - all pre-vetted reputable sources
RSS_FEEDS = {
    # Western/US Perspective
    "Reuters": "https://feeds.reuters.com/reuters/worldNews",
    "AP International": "https://feeds.apnews.com/rss/apf-intlnews",
    "BBC World": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "Foreign Policy": "https://foreignpolicy.com/feed/",
    "The Economist World": "https://www.economist.com/international/rss.xml",
    
    # Non-Western Perspectives
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "SCMP": "https://www.scmp.com/rss/91/feed",
    "Deutsche Welle": "https://rss.dw.com/rss/en-world",
    
    # Cybersecurity
    "Krebs Security": "https://krebsonsecurity.com/feed/",
}

class InsightAnalyzer:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
    
    def analyze_articles(self, articles):
        """Generate strategic insights from collected articles"""
        if not articles or not os.getenv('ANTHROPIC_API_KEY'):
            return self.get_default_analysis(articles)
        
        try:
            # Prepare article summaries for analysis
            article_text = self.prepare_articles_for_analysis(articles[:20])  # Analyze top 20
            
            # Get strategic analysis
            analysis_response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                messages=[{
                    "role": "user",
                    "content": f"""Analyze these news articles and provide strategic insights in two main sections:

{article_text}

**SECTION 1: STRATEGIC RISK ASSESSMENT**
Provide a holistic risk assessment across these geographic levels:

**GLOBAL**: Major worldwide risks, systemic threats, international stability
**UNITED STATES**: National-level risks, domestic policy impacts, economic vulnerabilities  
**NORTHERN VIRGINIA**: Regional risks affecting DC metro area, government contracting, tech corridor
**INDIVIDUAL**: Specific risks for a cybersecurity engineer in American tech industry with family (job market, security clearances, industry trends, family safety considerations)

For each level:
- **Key Facts:** Current risk factors based on articles
- **Strategic Implications:** Analysis of impact and significance
- **Forward Look:** Risk trajectory and mitigation strategies

**SECTION 2: THEMATIC ANALYSIS**
Provide narrative updates for themes with significant developments:

**WAR AND PEACE**: Military conflicts, diplomatic tensions, defense developments, peace processes
**ECONOMICS**: Markets, trade, sanctions, economic policy, financial systems  
**CYBERSECURITY**: Cyber attacks, data breaches, tech security, digital warfare
**SOCIAL AND POLITICAL**: Elections, governance, civil unrest, policy changes
**SCIENCE AND TECHNOLOGY**: Innovation, research breakthroughs, tech policy
**OUTSIDE THE BOX TRENDS**: Unexpected patterns, emerging issues, unconventional developments

For each theme:
- **Key Facts:** Start with verified information from articles
- **Strategic Implications:** Analysis of broader meaning
- **Forward Look:** Reasonable predictions (clearly labeled as analysis)

Skip themes with no significant developments. Be concise and actionable."""
                }]
            )
            
            return {
                'analysis': analysis_response.content[0].text,
                'article_count': len(articles),
                'sources_analyzed': len(set(a[2] for a in articles)),
                'has_ai_analysis': True
            }
            
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return self.get_default_analysis(articles)
    
    def prepare_articles_for_analysis(self, articles):
        """Prepare article text for AI analysis"""
        text_blocks = []
        for i, article in enumerate(articles):
            title, url, source, content, created_at = article
            text_blocks.append(f"{i+1}. [{source}] {title}\n{content[:200]}...\n")
        return "\n".join(text_blocks)
    
    def get_default_analysis(self, articles):
        """Fallback analysis when AI is not available"""
        sources = set(a[2] for a in articles)
        
        # Simple categorization
        cyber_articles = [a for a in articles if 'cyber' in a[0].lower() or 'security' in a[0].lower()]
        
        return {
            'analysis': f"""**SECTION 1: STRATEGIC RISK ASSESSMENT**

**GLOBAL**
**Key Facts:** Major worldwide risks identified from news sources.
**Strategic Implications:** Global tensions remain elevated.
**Forward Look:** Monitor international developments.

**UNITED STATES**
**Key Facts:** Domestic policy impacts observed.
**Strategic Implications:** National security considerations.
**Forward Look:** Track policy changes.

**NORTHERN VIRGINIA**
**Key Facts:** Regional tech corridor activities.
**Strategic Implications:** Government contracting impacts.
**Forward Look:** Watch defense spending trends.

**INDIVIDUAL (Cybersecurity Engineer)**
**Key Facts:** Industry trends affecting professionals.
**Strategic Implications:** Job market considerations.
**Forward Look:** Monitor clearance requirements.

**SECTION 2: THEMATIC ANALYSIS**

**ECONOMICS**
**Key Facts:** Market developments noted.
**Strategic Implications:** Economic indicators mixed.
**Forward Look:** Watch inflation trends.

**WAR AND PEACE**
**Key Facts:** Diplomatic tensions ongoing.
**Strategic Implications:** Regional conflicts persist.
**Forward Look:** Monitor escalation risks.

**CYBERSECURITY**
**Key Facts:** {len(cyber_articles)} security incidents reported.
**Strategic Implications:** Threat landscape evolving.
**Forward Look:** Enhance security posture.

**SCIENCE AND TECHNOLOGY**
**Key Facts:** Innovation developments tracked.
**Strategic Implications:** Technology adoption accelerating.
**Forward Look:** Monitor regulatory changes.

**SOCIAL AND POLITICAL**
**Key Facts:** Political developments observed.
**Strategic Implications:** Policy shifts expected.
**Forward Look:** Track election impacts.

**OUTSIDE THE BOX TRENDS**
**Key Facts:** Emerging patterns identified.
**Strategic Implications:** Unexpected developments noted.
**Forward Look:** Watch for anomalous events.""",
            'article_count': len(articles),
            'sources_analyzed': len(sources),
            'has_ai_analysis': False
        }

class IntelligenceBriefing:
    def __init__(self, db_path="briefing.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                source TEXT NOT NULL,
                content TEXT,
                pub_date TEXT,
                content_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_content_hash(self, title, content):
        """Generate hash for deduplication"""
        combined = f"{title}{content}".lower()
        return hashlib.md5(combined.encode()).hexdigest()
    
    def collect_articles(self):
        """Collect articles from all RSS feeds"""
        logger.info("Starting article collection from RSS feeds")
        articles = []
        
        for source_name, feed_url in RSS_FEEDS.items():
            try:
                logger.info(f"Fetching from {source_name}")
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries[:10]:
                    content = getattr(entry, 'summary', getattr(entry, 'description', ''))
                    content_hash = self.get_content_hash(entry.title, content)
                    
                    article = {
                        'title': entry.title,
                        'url': entry.link,
                        'source': source_name,
                        'content': content,
                        'pub_date': getattr(entry, 'published', ''),
                        'content_hash': content_hash
                    }
                    articles.append(article)
                    
            except Exception as e:
                logger.error(f"Error fetching from {source_name}: {e}")
        
        self.store_articles(articles)
        return articles
    
    def store_articles(self, articles):
        """Store articles in database, avoiding duplicates"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        current_time = datetime.now().isoformat()
        
        for article in articles:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO articles 
                    (title, url, source, content, pub_date, content_hash, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    article['title'],
                    article['url'],
                    article['source'],
                    article['content'],
                    article['pub_date'],
                    article['content_hash'],
                    current_time
                ))
            except Exception as e:
                logger.error(f"Error storing article: {e}")
        
        conn.commit()
        conn.close()
    
    def get_recent_articles(self, hours=24):
        """Get articles from the last N hours"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        cursor.execute('''
            SELECT title, url, source, content, created_at
            FROM articles 
            WHERE created_at > ?
            ORDER BY created_at DESC
        ''', (since,))
        
        articles = cursor.fetchall()
        conn.close()
        return articles
    
    def format_analysis_html(self, analysis_text):
        """Format AI analysis with theme sections and proper styling"""
        if not analysis_text:
            return analysis_text
        
        
        # Replace section headers with styled sections
        sections = {
            '**SECTION 1: STRATEGIC RISK ASSESSMENT**': 'STRATEGIC RISK ASSESSMENT',
            '**SECTION 2: THEMATIC ANALYSIS**': 'THEMATIC ANALYSIS'
        }
        
        # Replace geographic risk levels
        risk_levels = {
            '**GLOBAL**': 'GLOBAL',
            '**UNITED STATES**': 'UNITED STATES',
            '**NORTHERN VIRGINIA**': 'NORTHERN VIRGINIA',
            '**INDIVIDUAL**': 'INDIVIDUAL',
            '**INDIVIDUAL (Cybersecurity Engineer)**': 'INDIVIDUAL (CYBERSECURITY ENGINEER)'
        }
        
        # Replace theme headers (including variations Claude might return)
        themes = {
            '**WAR AND PEACE**': 'WAR AND PEACE',
            '**ECONOMICS**': 'ECONOMICS', 
            '**CYBERSECURITY**': 'CYBERSECURITY',
            '**SOCIAL AND POLITICAL**': 'SOCIAL AND POLITICAL',
            '**SCIENCE AND TECHNOLOGY**': 'SCIENCE AND TECHNOLOGY',
            '**OUTSIDE THE BOX TRENDS**': 'OUTSIDE THE BOX TRENDS',
            '**OUT OF THE BOX TRENDS**': 'OUTSIDE THE BOX TRENDS'
        }
        
        # Replace subsection headers with enhanced styling
        subsections = {
            '**Key Facts:**': '<div class="subsection-header" role="heading" aria-level="4">Key Facts</div>',
            '**Strategic Implications:**': '<div class="subsection-header" role="heading" aria-level="4">Strategic Implications</div>',
            '**Forward Look:**': '<div class="subsection-header forward-look" role="heading" aria-level="4">Forward Look</div>'
        }
        
        formatted = analysis_text
        
        # First, convert newlines to proper HTML structure
        paragraphs = formatted.split('\n\n')
        formatted = ''.join(f'<p class="content-text">{p.replace(chr(10), " ")}</p>' for p in paragraphs if p.strip())
        
        # Apply all replacements with inline styles for email compatibility AFTER paragraph conversion
        header_inline_style = 'font-family: Georgia, Times New Roman, serif; font-size: 20px; font-weight: 700; color: #000000; margin-bottom: 25px; margin-top: 35px; text-transform: uppercase; letter-spacing: 1px; padding-bottom: 8px; border-bottom: 2px solid #e0e0e0;'
        
        for marker, replacement in {**sections, **risk_levels, **themes}.items():
            if marker in formatted:
                section_class = "risk-section" if marker in risk_levels else "theme-section"
                styled_replacement = f'</p></div><div class="{section_class}"><div class="theme-header" style="{header_inline_style}" role="heading" aria-level="3">{replacement}</div><p class="content-text">'
                formatted = formatted.replace(marker, styled_replacement)
        
        # Apply subsection styling
        for marker, replacement in subsections.items():
            formatted = formatted.replace(marker, replacement)
        
        # Remove any remaining hashtag markdown headers completely
        import re
        formatted = re.sub(r'#+\s*', '', formatted)
        
        # Catch any remaining unformatted theme headers that weren't in our dictionary
        header_pattern = r'\*\*([A-Z\s&()]+)\*\*'
        def replace_remaining_headers(match):
            header_text = match.group(1).strip()
            return f'</p></div><div class="theme-section"><div class="theme-header" style="{header_inline_style}" role="heading" aria-level="3">{header_text}</div><p class="content-text">'
        
        formatted = re.sub(header_pattern, replace_remaining_headers, formatted)
        
        # Convert markdown-style bold to HTML with proper semantics
        formatted = formatted.replace('**', '<strong>').replace('**', '</strong>')
        
        # Add opening div if we have sections
        if '<div class="theme-section">' in formatted:
            formatted = '<div class="theme-section"><p class="content-text">' + formatted + '</p></div>'
        
        return formatted
    
    def generate_briefing_html(self, articles, analysis=None):
        """Generate HTML briefing with AI insights"""
        
        # Generate AI analysis if not provided
        if analysis is None:
            analyzer = InsightAnalyzer()
            analysis = analyzer.analyze_articles(articles)
        
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Strategic Intelligence Brief - {datetime.now().strftime('%B %d, %Y')}</title>
            <style>
                /* Clean newspaper-style design */
                * {{ 
                    margin: 0; 
                    padding: 0; 
                    box-sizing: border-box; 
                }}
                
                body {{ 
                    font-family: 'Times New Roman', 'Georgia', 'Baskerville', serif;
                    line-height: 1.8;
                    color: #1a1a1a;
                    background: #f8f8f8;
                    font-size: 18px;
                    -webkit-font-smoothing: antialiased;
                    -moz-osx-font-smoothing: grayscale;
                }}
                
                .container {{
                    max-width: 800px;
                    margin: 0 auto;
                    background: #ffffff;
                    box-shadow: 0 0 20px rgba(0, 0, 0, 0.08);
                }}
                
                .header {{
                    background: #f5f5f5;
                    color: #2a2a2a;
                    padding: 60px 50px;
                    text-align: center;
                    border-bottom: 4px solid #1a1a1a;
                }}
                
                .header h1 {{
                    font-family: 'Georgia', 'Times New Roman', serif;
                    font-size: 36px;
                    font-weight: 700;
                    margin-bottom: 12px;
                    letter-spacing: 0.02em;
                    text-transform: uppercase;
                    color: #1a1a1a;
                }}
                
                .header-meta {{
                    font-size: 16px;
                    color: #404040;
                    font-weight: 400;
                    font-style: italic;
                }}
                
                .content {{
                    padding: 50px;
                }}
                
                .section {{
                    margin-bottom: 60px;
                }}
                
                .section-title {{
                    font-family: 'Georgia', 'Times New Roman', serif;
                    font-size: 28px;
                    font-weight: 700;
                    color: #000000;
                    margin-bottom: 30px;
                    letter-spacing: 0.01em;
                    text-transform: uppercase;
                    border-bottom: 3px solid #1a1a1a;
                    padding-bottom: 15px;
                }}
                
                .analysis-container {{
                    background: #fafafa;
                    padding: 40px;
                    border: 2px solid #e0e0e0;
                    margin-bottom: 30px;
                }}
                
                .theme-section {{
                    background: #ffffff;
                    border: 1px solid #d0d0d0;
                    padding: 30px;
                    margin-bottom: 25px;
                }}
                
                .risk-section {{
                    background: #ffffff;
                    border: 1px solid #d0d0d0;
                    padding: 30px;
                    margin-bottom: 25px;
                }}
                
                .theme-header {{
                    font-family: 'Georgia', 'Times New Roman', serif;
                    font-size: 20px;
                    font-weight: 700;
                    color: #000000 !important;
                    margin-bottom: 25px;
                    margin-top: 35px;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    padding-bottom: 8px;
                    border-bottom: 2px solid #e0e0e0;
                }}
                
                .subsection-header {{
                    font-family: 'Georgia', 'Times New Roman', serif;
                    font-size: 16px;
                    font-weight: 700;
                    color: #000000;
                    margin: 25px 0 15px 0;
                    text-transform: uppercase;
                    letter-spacing: 0.8px;
                }}
                
                .content-text {{
                    font-family: 'Times New Roman', 'Georgia', 'Baskerville', serif;
                    color: #2a2a2a;
                    line-height: 1.9;
                    margin-bottom: 20px;
                    font-size: 18px;
                    font-weight: 400;
                }}
                
                .content-text:last-child {{
                    margin-bottom: 0;
                }}
                
                /* Override any inherited styling for text following subsection headers */
                .subsection-header + .content-text {{
                    font-family: 'Times New Roman', 'Georgia', 'Baskerville', serif;
                    color: #2a2a2a;
                    font-size: 18px;
                    font-weight: 400;
                    text-transform: none;
                    letter-spacing: normal;
                }}
                
                .article {{
                    background: #ffffff;
                    border: 1px solid #d0d0d0;
                    padding: 25px;
                    margin-bottom: 20px;
                }}
                
                .article h3 {{
                    margin-bottom: 10px;
                }}
                
                .article h3 a {{
                    color: #000000;
                    text-decoration: none;
                    font-size: 18px;
                    font-weight: 700;
                    line-height: 1.6;
                    font-family: 'Georgia', 'Times New Roman', serif;
                }}
                
                .article h3 a:hover {{
                    text-decoration: underline;
                }}
                
                .source {{
                    font-size: 14px;
                    font-weight: 600;
                    color: #666666;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    margin-bottom: 10px;
                    font-family: 'Arial', sans-serif;
                }}
                
                .article p {{
                    color: #404040;
                    line-height: 1.7;
                    font-size: 17px;
                }}
                
                .footer {{
                    background: #f0f0f0;
                    padding: 30px 50px;
                    border-top: 2px solid #d0d0d0;
                    text-align: center;
                }}
                
                .footer p {{
                    color: #666666;
                    font-size: 14px;
                    margin-bottom: 6px;
                    font-style: italic;
                }}
                
                .ai-badge {{
                    display: inline-block;
                    background: #1a1a1a;
                    color: #ffffff;
                    padding: 6px 16px;
                    font-size: 12px;
                    font-weight: 600;
                    letter-spacing: 0.5px;
                    text-transform: uppercase;
                    font-family: 'Arial', sans-serif;
                }}
                
                strong {{
                    color: #000000;
                    font-weight: 700;
                }}
                
                h1, h2, h3 {{
                    font-family: 'Georgia', 'Times New Roman', serif;
                    color: #000000;
                    font-weight: 700;
                    margin-bottom: 15px;
                }}
                
                h1 {{ font-size: 24px; }}
                h2 {{ font-size: 22px; }}
                h3 {{ font-size: 20px; }}
                
                /* Accessibility */
                @media (prefers-reduced-motion: reduce) {{
                    * {{ 
                        transition: none !important;
                    }}
                }}
                
                @media (max-width: 768px) {{
                    .container {{ margin: 0 20px; }}
                    .header {{ padding: 40px 30px; }}
                    .content {{ padding: 30px; }}
                    .header h1 {{ font-size: 28px; }}
                    .section-title {{ font-size: 24px; }}
                    body {{ font-size: 16px; }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <header class="header">
                    <h1>Strategic Intelligence Brief</h1>
                    <div class="header-meta">
                        <p>{datetime.now().strftime('%B %d, %Y')}</p>
                        <p>{analysis['article_count']} articles from {analysis['sources_analyzed']} sources 
                        {'• AI-Enhanced Analysis' if analysis['has_ai_analysis'] else '• Basic Analysis'}</p>
                    </div>
                </header>
                
                <div class="content">
                    <section class="section" aria-labelledby="strategic-assessment">
                        <h2 class="section-title" id="strategic-assessment">Strategic Assessment</h2>
                        <div class="analysis-container" role="region" aria-label="Strategic analysis content">
                            {self.format_analysis_html(analysis['analysis']) if analysis['has_ai_analysis'] else f'<div class="content-text">{analysis["analysis"]}</div>'}
                        </div>
                    </section>
                    
                    <section class="section" aria-labelledby="source-intelligence">
                        <h2 class="section-title" id="source-intelligence">Source Intelligence</h2>
        """
        
        for article in articles[:12]:  # Show fewer articles since we have analysis now
            title, url, source, content, created_at = article
            html += f"""
                <article class="article" role="article">
                    <h3><a href="{url}" target="_blank" rel="noopener noreferrer" aria-label="Read full article: {title}">{title}</a></h3>
                    <p class="source" aria-label="Source: {source}">{source}</p>
                    <p>{content[:250]}...</p>
                </article>
            """
        
        html += f"""
                    </section>
                </div>
                
                <footer class="footer">
                    <p><em>Generated by InsightWeaver</em></p>
                    {f'<p class="ai-badge">Strategic analysis powered by Claude AI</p>' if analysis['has_ai_analysis'] else ''}
                </footer>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def send_email(self, html_content, recipient_email, smtp_config):
        """Send briefing via email"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Daily Insights - {datetime.now().strftime('%B %d, %Y')}"
            msg['From'] = smtp_config['from_email']
            msg['To'] = recipient_email
            
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            with smtplib.SMTP(smtp_config['smtp_server'], smtp_config['smtp_port']) as server:
                server.starttls()
                server.login(smtp_config['username'], smtp_config['password'])
                server.send_message(msg)
            
            logger.info(f"Briefing sent successfully to {recipient_email}")
            
        except Exception as e:
            logger.error(f"Error sending email: {e}")

    def run_daily_briefing(self):
        """Main function to run daily briefing"""
        logger.info("Starting daily insights")
        
        # Collect articles
        self.collect_articles()
        
        # Get recent articles
        articles = self.get_recent_articles(hours=24)
        
        if not articles:
            logger.info("No new articles found")
            return
        
        # Generate AI analysis
        logger.info("Generating strategic analysis")
        analyzer = InsightAnalyzer()
        analysis = analyzer.analyze_articles(articles)
        
        if analysis['has_ai_analysis']:
            logger.info("AI-enhanced analysis completed")
        else:
            logger.info("Using basic analysis (AI not configured)")
        
        # Generate briefing with analysis
        html_content = self.generate_briefing_html(articles, analysis)
        
        # Save briefing locally
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"briefing_{timestamp}.html"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"Briefing saved as {filename}")
        
        # Email configuration (set via environment variables)
        smtp_config = {
            'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            'smtp_port': int(os.getenv('SMTP_PORT', '587')),
            'username': os.getenv('EMAIL_USERNAME'),
            'password': os.getenv('EMAIL_PASSWORD'),
            'from_email': os.getenv('FROM_EMAIL')
        }
        
        recipient = os.getenv('RECIPIENT_EMAIL')
        
        if all(smtp_config.values()) and recipient:
            self.send_email(html_content, recipient, smtp_config)
        else:
            logger.info("Email configuration incomplete. Briefing saved locally only.")
        
        return filename

if __name__ == "__main__":
    briefing = IntelligenceBriefing()
    briefing.run_daily_briefing()
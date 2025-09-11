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
    "Foreign Affairs": "https://www.foreignaffairs.com/rss.xml",
    "CFR": "https://feeds.cfr.org/publication/global",
    "CSIS": "https://www.csis.org/analysis.xml",
    "The Economist World": "https://www.economist.com/international/rss.xml",
    "Chatham House": "https://www.chathamhouse.org/rss/publications",
    "Carnegie Endowment": "https://carnegieendowment.org/rss/publications",
    "International Crisis Group": "https://www.crisisgroup.org/rss/publications",
    
    # Non-Western Perspectives  
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "SCMP": "https://www.scmp.com/rss/91/feed",
    "The Hindu International": "https://www.thehindu.com/news/international/feeder/default.rss",
    "Deutsche Welle": "https://rss.dw.com/rss/en-world",
    "France24": "https://www.france24.com/en/rss",
    "Americas Quarterly": "https://www.americasquarterly.org/fullfeed/",
    "Council on Hemispheric Affairs": "https://www.coha.org/feed/",
    "AllAfrica": "https://allafrica.com/tools/headlines/rdf/africa/headlines.rdf",
    "ISS Africa": "https://issafrica.org/rss.xml",
    "The Diplomat": "https://thediplomat.com/feed/",
    "East Asia Forum": "https://www.eastasiaforum.org/feed/",
    "Arab News": "https://www.arabnews.com/rss.xml",
    "Haaretz English": "https://www.haaretz.com/cmlink/1.628752",
    
    # Cybersecurity
    "Krebs Security": "https://krebsonsecurity.com/feed/",
    "Hacker News": "https://feeds.feedburner.com/hn/frontpage",
    "Threatpost": "https://threatpost.com/feed/",
    "Bellingcat": "https://www.bellingcat.com/feed/",
    "CISA Alerts": "https://www.cisa.gov/cybersecurity-advisories/rss.xml",
    "CISA News": "https://www.cisa.gov/news/rss.xml",
    
    # Defense/Military
    "Defense News": "https://www.defensenews.com/arc/outboundfeeds/rss/category/global/?outputType=xml",
    "Military.com": "https://www.military.com/rss/news",
    "Jane's Defence": "https://www.janes.com/feeds/all-content",
    "CSBA": "https://csbaonline.org/rss.xml",
    
    # Alternative Analysis
    "Carnegie Moscow": "https://carnegie.ru/publications/?lang=en&fa=rss",
    "PONARS Eurasia": "https://www.ponarseurasia.org/rss/",
    "Quincy Institute": "https://quincyinst.org/feed/",
    "CNAS": "https://www.cnas.org/rss/publications",
    
    # Institutional
    "UN News": "https://news.un.org/feed/subscribe/en/news/all/rss.xml",
    "World Bank": "https://www.worldbank.org/en/news/rss",
    
    # Economic Intelligence
    "Financial Times World": "https://www.ft.com/world?format=rss",

    # DevOps
    "DevOps.com": "https://devops.com/feed/",
    "The New Stack.io": "https://thenewstack.io/devops/feed",
    "Azure DevOps Blog": "https://devblogs.microsoft.com/devops/feed/",
    "InfoWorld": "https://www.infoworld.com/devops/feed/",
    "Rapid7": "https://www.rapid7.com/blog/tag/devops/rss",
    "HackerNews": "http://thehackernews.com/feeds/posts/default"
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
                    "content": f"""Analyze these news articles and provide strategic insights in three main categories:

{article_text}

Generate a comprehensive intelligence analysis with proper HTML formatting. Use the following structure exactly:

**FORMATTING REQUIREMENTS:**
- Use proper HTML headers: `<h2>` for main sections, `<h3>` for subsections
- Use `<p>` tags for paragraphs
- Use `<strong>` for emphasis on key points
- Use `<em>` for analytical assessments and predictions
- Ensure proper spacing between sections with `<br>` tags
- Use `<ul>` and `<li>` for any bullet points

**ANALYSIS STRUCTURE:**
For each category below, provide two substantive sections with proper HTML formatting:

```html
<h2>GLOBAL ANALYSIS</h2>
<h3>Narrative</h3>
<p>[1-2 paragraphs of meaningful analysis based on current events, connecting multiple sources and identifying patterns. Focus on strategic implications rather than just summarizing news. Highlight <strong>key developments</strong> that signal broader trends.]</p>

<h3>Forward Look</h3>
<p><em>ASSESSMENT:</em> [1-2 paragraphs of trajectory analysis and strategic implications. Clearly label predictions as analytical projections. Identify potential flashpoints, escalation risks, and decision points in the next 30-90 days.]</p>

<h2>LOCAL ANALYSIS</h2>
<h3>Narrative</h3>
<p>[Focus specifically on Northern Virginia and DC metro area developments, including government contracting impacts, federal and state policy effects on the region, local government decisions, environmental considerations, and public schools. Connect local developments to broader national trends.]</p>

<h3>Forward Look</h3>
<p><em>ASSESSMENT:</em> [Regional trajectory analysis with focus on how federal policy changes, contracting cycles, and economic trends will impact the local area. Include implications for professionals in the cybersecurity and government contracting sectors.]</p>

<h2>CYBERSECURITY ANALYSIS</h2>
<h3>Narrative</h3>
<p>[Examine cyber threats, data breaches, digital warfare, and technology security developments. Analyze cybersecurity policy developments (particularly FedRAMP, GovRAMP, TXRAMP, CMMC) and industry-specific trends. Connect cyber incidents to geopolitical context and nation-state activities.]</p>

<h3>Forward Look</h3>
<p><em>ASSESSMENT:</em> [Strategic implications for cybersecurity professionals. Identify emerging threat vectors, policy changes that will affect compliance requirements, and industry trends that will shape career opportunities and business decisions.]</p>


<h2>MY STUFF</h2>
<h3>Narrative</h3>
<p>[Focus specifically on Chippewa Valley of Wisconsin and the area developments, including government contracting impacts, federal and state policy effects on the region, local government decisions, environmental considerations, and public schools. Connect local developments to broader national trends.]</p>

<h3>Forward Look</h3>
<p><em>ASSESSMENT:</em> [Regional trajectory analysis with focus on how federal policy changes, contracting cycles, and economic trends will impact the local area. Include implications for professionals in the cybersecurity and government contracting sectors.]</p>

<h2>DevOps</h2>
<h3>Narrative</h3>
<p>[Focus specifically on DevOps job market and jobs market overall. Here in the Chippewa Valley of Wisconsin and how it impacts remote work.t. Connect the developments to broader national trends.]</p>

<h3>Forward Look</h3>
<p><em>ASSESSMENT:</em> [Regional trajectory analysis with focus on and economic trends will impact the local area. Include implications for professionals in the devops and sysadmin sectors.]</p>
```

**ANALYSIS QUALITY STANDARDS:**
- Base all analysis strictly on factual information from the provided articles
- Connect dots between seemingly separate events to identify patterns
- Provide strategic context that explains WHY events matter, not just WHAT happened
- When making forward-looking assessments, use phrases like "Assessment indicates..." or "Analysis suggests..." 
- Include confidence levels when appropriate ("High confidence," "Moderate confidence," "Low confidence")
- Cite specific sources when referencing particular claims
- Avoid speculation beyond what the evidence supports
- Each narrative section should synthesize information across multiple sources
- Forward Look sections should identify specific indicators to monitor and decision points ahead

**SUBSTANTIVE REQUIREMENTS:**
- Each section should be 150-250 words of meaningful analysis
- Focus on implications for decision-makers rather than just description
- Identify second and third-order effects of developments
- Connect local, national, and international trends where relevant
- Provide actionable intelligence that helps readers understand strategic implications"""
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
            'analysis': "AI content is unavailable.",
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
        
        # Handle simple fallback messages
        if analysis_text == "AI content is unavailable.":
            return f'<div class="content-text">{analysis_text}</div>'
        
        
        # Replace analysis category headers with enhanced styling
        categories = {
            '**GLOBAL ANALYSIS**': '<div class="category-header" role="heading" aria-level="3">GLOBAL ANALYSIS</div>',
            '**LOCAL ANALYSIS**': '<div class="category-header" role="heading" aria-level="3">LOCAL ANALYSIS</div>',
            '**CYBERSECURITY ANALYSIS**': '<div class="category-header" role="heading" aria-level="3">CYBERSECURITY ANALYSIS</div>'
        }
        
        # Replace subsection headers with enhanced styling
        subsections = {
            '**Narrative:**': '<div class="subsection-header" role="heading" aria-level="4">Narrative</div>',
            '**Forward Look:**': '<div class="subsection-header forward-look" role="heading" aria-level="4">Forward Look</div>'
        }
        
        formatted = analysis_text
        
        # First, convert newlines to proper HTML structure
        paragraphs = formatted.split('\n\n')
        formatted = ''.join(f'<p class="content-text">{p.replace(chr(10), " ")}</p>' for p in paragraphs if p.strip())
        
        # Apply all replacements with enhanced inline styles for email compatibility AFTER paragraph conversion
        header_inline_style = 'font-family: Georgia, Times New Roman, serif; font-size: 22px; font-weight: 700; color: #1a1a1a; margin-bottom: 30px; margin-top: 40px; text-transform: uppercase; letter-spacing: 1.5px; padding: 12px 0; border-bottom: 3px solid #000000; background: linear-gradient(135deg, #f8f8f8 0%, #e8e8e8 100%); text-align: center; border-radius: 4px;'
        
        for marker, replacement in categories.items():
            if marker in formatted:
                styled_replacement = f'</p></div><div class="analysis-section">{replacement}<p class="content-text">'
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
        if '<div class="analysis-section">' in formatted:
            formatted = '<div class="analysis-section"><p class="content-text">' + formatted + '</p></div>'
        
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
            <title>InsightWeaver - {datetime.now().strftime('%B %d, %Y')}</title>
            <style>
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
                
                .analysis-section {{
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
                
                .category-header {{
                    font-family: 'Georgia', 'Times New Roman', serif;
                    font-size: 22px;
                    font-weight: 700;
                    color: #1a1a1a;
                    margin: 40px 0 30px 0;
                    text-transform: uppercase;
                    letter-spacing: 1.5px;
                    padding: 12px 0;
                    border-bottom: 3px solid #000000;
                    background: linear-gradient(135deg, #f8f8f8 0%, #e8e8e8 100%);
                    text-align: center;
                    border-radius: 4px;
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
                    line-height: 1.8;
                    margin-bottom: 18px;
                    font-size: 18px;
                    font-weight: 400;
                }}
                
                .content-text:last-child {{
                    margin-bottom: 0;
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
                    font-family: 'Times New Roman', 'Georgia', 'Baskerville', serif;
                    color: #2a2a2a;
                    line-height: 1.8;
                    font-size: 18px;
                    font-weight: 400;
                    margin-bottom: 18px;
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
                    <h1>InsightWeaver</h1>
                    <div class="header-meta">
                        <p>{datetime.now().strftime('%B %d, %Y')}</p>
                        <p>{analysis['article_count']} articles from {analysis['sources_analyzed']} sources 
                        {'• AI-Enhanced Analysis' if analysis['has_ai_analysis'] else 'No Analysis Generated'}</p>
                    </div>
                </header>
                
                <div class="content">
                    <section class="section" aria-labelledby="strategic-assessment">
                        <h2 class="section-title" id="strategic-assessment">Key Insights of the Day</h2>
                        <div class="analysis-container" role="region" aria-label="Strategic analysis content">
                            {self.format_analysis_html(analysis['analysis'])}
                        </div>
                    </section>
                    
        """
        
        
        html += f"""
                    </section>
                </div>
                
                <footer class="footer">
                    <p><em>Generated by InsightWeaver and Claude AI</em></p>
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
            msg['Subject'] = f"Daily Insights by InsightWeaver- {datetime.now().strftime('%B %d, %Y')}"
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

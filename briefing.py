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
        
        for article in articles:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO articles 
                    (title, url, source, content, pub_date, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    article['title'],
                    article['url'],
                    article['source'],
                    article['content'],
                    article['pub_date'],
                    article['content_hash']
                ))
            except Exception as e:
                logger.error(f"Error storing article: {e}")
        
        conn.commit()
        conn.close()
    
    def get_recent_articles(self, hours=24):
        """Get articles from the last N hours"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since = datetime.now() - timedelta(hours=hours)
        cursor.execute('''
            SELECT title, url, source, content, created_at
            FROM articles 
            WHERE created_at > ?
            ORDER BY created_at DESC
        ''', (since,))
        
        articles = cursor.fetchall()
        conn.close()
        return articles
    
    def generate_briefing_html(self, articles):
        """Generate HTML briefing"""
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; }}
                .header {{ background-color: #2c3e50; color: white; padding: 20px; }}
                .section {{ margin: 20px 0; }}
                .article {{ border-left: 3px solid #3498db; padding-left: 15px; margin: 15px 0; }}
                .source {{ font-weight: bold; color: #7f8c8d; }}
                .summary {{ background-color: #ecf0f1; padding: 15px; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Daily Intelligence Briefing</h1>
                <p>{datetime.now().strftime('%B %d, %Y')}</p>
            </div>
            
            <div class="section">
                <h2>Executive Summary</h2>
                <div class="summary">
                    <p>Today's briefing covers {len(articles)} developments from {len(set(a[2] for a in articles))} sources.</p>
                </div>
            </div>
            
            <div class="section">
                <h2>Key Developments</h2>
        """
        
        for article in articles[:15]:
            title, url, source, content, created_at = article
            html += f"""
                <div class="article">
                    <h3><a href="{url}" target="_blank">{title}</a></h3>
                    <p class="source">{source}</p>
                    <p>{content[:300]}...</p>
                </div>
            """
        
        html += """
            </div>
            
            <div class="section">
                <p><em>Generated by InsightWeaver</em></p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def send_email(self, html_content, recipient_email, smtp_config):
        """Send briefing via email"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Daily Intelligence Briefing - {datetime.now().strftime('%B %d, %Y')}"
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
        logger.info("Starting daily intelligence briefing")
        
        # Collect articles
        self.collect_articles()
        
        # Get recent articles
        articles = self.get_recent_articles(hours=24)
        
        if not articles:
            logger.info("No new articles found")
            return
        
        # Generate briefing
        html_content = self.generate_briefing_html(articles)
        
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
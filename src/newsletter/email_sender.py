"""
Email System for InsightWeaver Newsletter
Handles Gmail API integration and email delivery
"""

import smtplib
import ssl
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, Any, Optional, List
import os
from pathlib import Path

from .templates import PersonalizedNarrativeTemplate


class EmailSender:
    """Handles email delivery for InsightWeaver newsletters"""

    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.email_username = os.getenv('EMAIL_USERNAME')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.from_email = os.getenv('FROM_EMAIL')

        if not all([self.email_username, self.email_password, self.from_email]):
            print("⚠️ Email credentials not configured. Newsletter will be saved locally only.")
            self.email_enabled = False
        else:
            self.email_enabled = True

    async def send_daily_brief(self, content_data: Dict[str, Any], recipient_email: str) -> bool:
        """Send daily intelligence brief via email"""
        print(f"📧 Preparing daily brief for {recipient_email}")

        try:
            # Generate email content using PersonalizedNarrativeTemplate
            html_content = PersonalizedNarrativeTemplate.generate_html(content_data)

            # Simple text version (extract bottom line summary)
            synthesis = content_data.get('synthesis_data', {})
            bottom_line = synthesis.get('bottom_line', {})
            text_content = bottom_line.get('summary', 'Please view the HTML version for full formatting.')

            # Format subject based on report type
            if 'date' in content_data:
                subject = f"InsightWeaver Daily Brief - {content_data['date'].strftime('%B %d, %Y')}"
            else:
                date_range = f"{content_data['start_date'].strftime('%b %d')} - {content_data['end_date'].strftime('%b %d, %Y')}"
                subject = f"InsightWeaver Intelligence Report - {date_range}"

            # Send email
            success = await self._send_email(
                recipient_email=recipient_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )

            if success:
                print(f"✅ Daily brief sent successfully to {recipient_email}")
            else:
                # Save locally as fallback
                self._save_newsletter_locally(content_data, "daily", html_content)

            return success

        except Exception as e:
            print(f"❌ Failed to send daily brief: {e}")
            self._save_newsletter_locally(content_data, "daily", PersonalizedNarrativeTemplate.generate_html(content_data))
            return False

    async def send_weekly_trends(self, content_data: Dict[str, Any], recipient_email: str) -> bool:
        """Send weekly trend analysis via email"""
        print(f"📈 Preparing weekly trends for {recipient_email}")

        try:
            # Generate email content using PersonalizedNarrativeTemplate
            html_content = PersonalizedNarrativeTemplate.generate_html(content_data)

            date_range = f"{content_data['start_date'].strftime('%B %d')} - {content_data['end_date'].strftime('%B %d, %Y')}"
            subject = f"InsightWeaver Weekly Trends - {date_range}"

            # Simple text version
            synthesis = content_data.get('synthesis_data', {})
            text_content = f"Weekly trend analysis: {date_range}\n\n{synthesis.get('executive_summary', 'Please view the HTML version for full formatting.')}"

            # Send email
            success = await self._send_email(
                recipient_email=recipient_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )

            if success:
                print(f"✅ Weekly trends sent successfully to {recipient_email}")
            else:
                # Save locally as fallback
                self._save_newsletter_locally(content_data, "weekly", html_content)

            return success

        except Exception as e:
            print(f"❌ Failed to send weekly trends: {e}")
            self._save_newsletter_locally(content_data, "weekly", PersonalizedNarrativeTemplate.generate_html(content_data))
            return False

    async def _send_email(self, recipient_email: str, subject: str,
                         html_content: str, text_content: str) -> bool:
        """Send email using SMTP"""
        if not self.email_enabled:
            print("📧 Email not configured, saving locally instead")
            return False

        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.from_email
            message["To"] = recipient_email

            # Add text and HTML parts
            text_part = MIMEText(text_content, "plain")
            html_part = MIMEText(html_content, "html")

            message.attach(text_part)
            message.attach(html_part)

            # Send email
            context = ssl.create_default_context()

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.email_username, self.email_password)
                server.sendmail(self.from_email, recipient_email, message.as_string())

            return True

        except smtplib.SMTPAuthenticationError:
            print("❌ SMTP authentication failed. Check email credentials.")
            return False
        except smtplib.SMTPException as e:
            print(f"❌ SMTP error: {e}")
            return False
        except Exception as e:
            print(f"❌ Email sending failed: {e}")
            return False

    def _save_newsletter_locally(self, content_data: Dict[str, Any], newsletter_type: str, html_content: str):
        """Save newsletter to local file as fallback"""
        try:
            # Create newsletters directory
            newsletters_dir = Path("data/newsletters")
            newsletters_dir.mkdir(parents=True, exist_ok=True)

            if newsletter_type == "daily":
                date_str = content_data['date'].strftime('%Y-%m-%d')
                filename = f"daily_brief_{date_str}.html"
            else:
                start_str = content_data['start_date'].strftime('%Y-%m-%d')
                end_str = content_data['end_date'].strftime('%Y-%m-%d')
                filename = f"weekly_trends_{start_str}_to_{end_str}.html"

            filepath = newsletters_dir / filename

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)

            print(f"💾 Newsletter saved locally: {filepath}")

        except Exception as e:
            print(f"❌ Failed to save newsletter locally: {e}")

    async def send_test_email(self, recipient_email: str) -> bool:
        """Send test email to verify configuration"""
        if not self.email_enabled:
            print("❌ Email not configured")
            return False

        try:
            test_content = """
            <h2>InsightWeaver Email Test</h2>
            <p>This is a test message from your InsightWeaver system.</p>
            <p>Email configuration is working correctly!</p>
            <hr>
            <small>Generated at {}</small>
            """.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

            success = await self._send_email(
                recipient_email=recipient_email,
                subject="InsightWeaver Email Test",
                html_content=test_content,
                text_content="InsightWeaver email test - configuration working!"
            )

            if success:
                print(f"✅ Test email sent successfully to {recipient_email}")
            else:
                print(f"❌ Test email failed")

            return success

        except Exception as e:
            print(f"❌ Test email error: {e}")
            return False


class NewsletterScheduler:
    """Handles scheduling and delivery of newsletters"""

    def __init__(self, email_sender: Optional[EmailSender] = None):
        self.email_sender = email_sender or EmailSender()
        self.default_recipient = os.getenv('RECIPIENT_EMAIL')

    async def send_daily_briefing(self, date: Optional[datetime] = None,
                                recipient: Optional[str] = None) -> bool:
        """Send daily briefing for specified date"""
        from .content_engine import NewsletterContentEngine

        if date is None:
            date = datetime.now()

        recipient = recipient or self.default_recipient
        if not recipient:
            print("❌ No recipient email configured")
            return False

        print(f"📊 Generating daily briefing for {date.strftime('%Y-%m-%d')}")

        try:
            # Generate content
            content_engine = NewsletterContentEngine()
            content_data = await content_engine.generate_daily_brief_content(date)

            # Send email
            success = await self.email_sender.send_daily_brief(content_data, recipient)
            return success

        except Exception as e:
            print(f"❌ Daily briefing failed: {e}")
            return False

    async def send_weekly_analysis(self, end_date: Optional[datetime] = None,
                                 recipient: Optional[str] = None) -> bool:
        """Send weekly trend analysis"""
        from .content_engine import NewsletterContentEngine

        if end_date is None:
            end_date = datetime.now()

        recipient = recipient or self.default_recipient
        if not recipient:
            print("❌ No recipient email configured")
            return False

        print(f"📈 Generating weekly analysis ending {end_date.strftime('%Y-%m-%d')}")

        try:
            # Generate content
            content_engine = NewsletterContentEngine()
            content_data = await content_engine.generate_weekly_trend_content(end_date)

            # Send email
            success = await self.email_sender.send_weekly_trends(content_data, recipient)
            return success

        except Exception as e:
            print(f"❌ Weekly analysis failed: {e}")
            return False

    async def test_email_system(self) -> bool:
        """Test the email system configuration"""
        recipient = self.default_recipient
        if not recipient:
            print("❌ No recipient email configured for testing")
            return False

        return await self.email_sender.send_test_email(recipient)

    def get_email_status(self) -> Dict[str, Any]:
        """Get status of email configuration"""
        return {
            "email_enabled": self.email_sender.email_enabled,
            "smtp_server": self.email_sender.smtp_server,
            "smtp_port": self.email_sender.smtp_port,
            "from_email": self.email_sender.from_email,
            "default_recipient": self.default_recipient,
            "credentials_configured": bool(self.email_sender.email_username and self.email_sender.email_password)
        }
"""
Newsletter System for InsightWeaver
Main orchestrator for intelligence briefing generation and delivery
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path

from .content_engine import NewsletterContentEngine
from .email_sender import NewsletterScheduler
from .templates import DailyBriefTemplate


class NewsletterSystem:
    """Main newsletter system orchestrator"""

    def __init__(self):
        self.content_engine = NewsletterContentEngine()
        self.scheduler = NewsletterScheduler()

    async def generate_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        hours: Optional[int] = None,
        save_local: bool = True,
        send_email: bool = False
    ) -> Dict[str, Any]:
        """
        Generate intelligence report for any time period

        Args:
            start_date: Start of analysis window
            end_date: End of analysis window (defaults to now)
            hours: Look back N hours from end_date (alternative to start_date)
            save_local: Save HTML to data/newsletters/
            send_email: Send via email

        Returns:
            Report generation results
        """
        # Generate content
        content_data = await self.content_engine.generate_intelligence_report(
            start_date=start_date,
            end_date=end_date,
            hours=hours
        )

        results = {
            "success": True,
            "start_date": content_data['start_date'],
            "end_date": content_data['end_date'],
            "duration_hours": content_data['duration_hours'],
            "report_type": content_data['report_type'],
            "articles_analyzed": content_data['articles_analyzed'],
            "synthesis_id": content_data.get('synthesis_id'),
            "processing_time": content_data.get('processing_time'),
            "local_saved": False,
            "email_sent": False
        }

        try:
            # Render template
            html_content = DailyBriefTemplate.generate_html(content_data)

            # Save locally if requested
            if save_local:
                local_path = self._save_report_local(content_data, html_content)
                results["local_saved"] = True
                results["local_path"] = str(local_path)
                print(f"💾 Report saved: {local_path}")

            # Send email if requested
            if send_email:
                recipient = self.scheduler.default_recipient
                if recipient and self.scheduler.email_sender.email_enabled:
                    email_success = await self.scheduler.email_sender.send_daily_brief(
                        content_data, recipient
                    )
                    results["email_sent"] = email_success
                    if email_success:
                        print(f"📧 Report emailed to {recipient}")
                else:
                    print("⚠️ Email not configured - report saved locally only")
                    results["email_sent"] = False

            return results

        except Exception as e:
            print(f"❌ Report generation failed: {e}")
            results["success"] = False
            results["error"] = str(e)
            return results

    def _save_report_local(self, content_data: Dict[str, Any], html_content: str) -> Path:
        """Save report with descriptive filename"""
        newsletters_dir = Path("data/newsletters")
        newsletters_dir.mkdir(parents=True, exist_ok=True)

        start = content_data['start_date'].strftime('%Y-%m-%d')
        end = content_data['end_date'].strftime('%Y-%m-%d')
        report_type = content_data['report_type']

        filename = f"intel_report_{report_type}_{start}_to_{end}.html"
        filepath = newsletters_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return filepath

    async def test_system(self) -> Dict[str, Any]:
        """Test the newsletter system components"""
        print("🧪 Testing newsletter system...")

        test_results = {
            "content_engine": False,
            "email_system": False,
            "template_rendering": False,
            "overall_status": "FAILED"
        }

        try:
            # Test content engine with recent data
            print("📊 Testing content engine...")
            end_date = datetime.now()
            start_date = end_date - timedelta(hours=24)
            content_data = await self.content_engine.generate_intelligence_report(
                start_date=start_date,
                end_date=end_date
            )

            if content_data and "executive_summary" in content_data:
                test_results["content_engine"] = True
                print("✅ Content engine: OK")
            else:
                print("❌ Content engine: No data or generation failed")

            # Test template rendering
            print("🎨 Testing template rendering...")
            if content_data:
                html_output = DailyBriefTemplate.generate_html(content_data)
                if html_output and len(html_output) > 1000:
                    test_results["template_rendering"] = True
                    print("✅ Template rendering: OK")
                else:
                    print("❌ Template rendering: Output too short or failed")

            # Test email system
            print("📧 Testing email system...")
            email_status = self.scheduler.get_email_status()

            if email_status["email_enabled"] and email_status["credentials_configured"]:
                # Try to send test email
                email_success = await self.scheduler.test_email_system()
                test_results["email_system"] = email_success
                if email_success:
                    print("✅ Email system: OK")
                else:
                    print("❌ Email system: Test email failed")
            else:
                print("⚠️ Email system: Not configured (will save locally)")
                test_results["email_system"] = "not_configured"

            # Overall status
            core_systems = [test_results["content_engine"], test_results["template_rendering"]]
            if all(core_systems):
                if test_results["email_system"] == True:
                    test_results["overall_status"] = "FULLY_OPERATIONAL"
                else:
                    test_results["overall_status"] = "OPERATIONAL_LOCAL_ONLY"
            else:
                test_results["overall_status"] = "FAILED"

            print(f"\n📋 Newsletter System Status: {test_results['overall_status']}")
            return test_results

        except Exception as e:
            print(f"❌ System test failed: {e}")
            test_results["error"] = str(e)
            return test_results

    async def preview_report(self, start_date: Optional[datetime] = None,
                            end_date: Optional[datetime] = None, hours: Optional[int] = None) -> str:
        """
        Generate preview of intelligence report (HTML content only)

        Args:
            start_date: Start of analysis window
            end_date: End of analysis window
            hours: Look back N hours (alternative to start_date)

        Returns:
            HTML content string
        """
        content_data = await self.content_engine.generate_intelligence_report(
            start_date=start_date,
            end_date=end_date,
            hours=hours
        )
        return DailyBriefTemplate.generate_html(content_data)

    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status"""
        email_status = self.scheduler.get_email_status()

        return {
            "system_version": "Phase 4 - Intelligence Newsletter System",
            "content_engine": "Operational",
            "template_system": "Operational",
            "email_system": {
                "enabled": email_status["email_enabled"],
                "configured": email_status["credentials_configured"],
                "smtp_server": email_status["smtp_server"],
                "default_recipient": email_status["default_recipient"]
            },
            "local_storage": {
                "enabled": True,
                "directory": "data/newsletters/"
            },
            "capabilities": [
                "Intelligence reports for any time window",
                "Narrative synthesis from RSS feeds",
                "Executive summary generation",
                "Multi-format output (HTML/Text)",
                "Email delivery with SMTP",
                "Local file storage",
                "System testing and validation"
            ]
        }


async def main():
    """Main function for testing newsletter system"""
    system = NewsletterSystem()

    print("🚀 InsightWeaver Newsletter System")
    print("=" * 50)

    # Test system
    await system.test_system()

    print("\n" + "=" * 50)
    print("📊 System Status:")
    status = system.get_system_status()
    for key, value in status.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for subkey, subvalue in value.items():
                print(f"    {subkey}: {subvalue}")
        elif isinstance(value, list):
            print(f"  {key}:")
            for item in value:
                print(f"    • {item}")
        else:
            print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
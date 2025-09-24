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
from .templates import DailyBriefTemplate, WeeklyTrendTemplate


class NewsletterSystem:
    """Main newsletter system orchestrator"""

    def __init__(self):
        self.content_engine = NewsletterContentEngine()
        self.scheduler = NewsletterScheduler()

    async def generate_daily_brief(self, date: Optional[datetime] = None,
                                 save_local: bool = True, send_email: bool = True) -> Dict[str, Any]:
        """Generate and optionally send daily intelligence brief"""
        if date is None:
            date = datetime.now()

        print(f"🚀 Starting daily brief generation for {date.strftime('%Y-%m-%d')}")

        try:
            # Generate content
            content_data = await self.content_engine.generate_daily_brief_content(date)

            results = {
                "success": True,
                "date": date,
                "content_generated": True,
                "email_sent": False,
                "local_saved": False,
                "article_count": content_data.get("article_count", 0),
                "priority_count": len(content_data.get("priority_articles", [])),
                "trend_count": len(content_data.get("trends", [])),
                "processing_time": content_data.get("processing_time", "N/A")
            }

            # Save locally if requested
            if save_local:
                html_content = DailyBriefTemplate.generate_html(content_data)
                local_path = self._save_daily_brief_local(content_data, html_content)
                results["local_saved"] = True
                results["local_path"] = str(local_path)
                print(f"💾 Daily brief saved locally: {local_path}")

            # Send email if requested
            if send_email:
                email_success = await self.scheduler.send_daily_briefing(date)
                results["email_sent"] = email_success

            return results

        except Exception as e:
            print(f"❌ Daily brief generation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "date": date
            }

    async def generate_weekly_analysis(self, end_date: Optional[datetime] = None,
                                     save_local: bool = True, send_email: bool = True) -> Dict[str, Any]:
        """Generate and optionally send weekly trend analysis"""
        if end_date is None:
            end_date = datetime.now()

        start_date = end_date - timedelta(days=7)
        print(f"📈 Starting weekly analysis: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

        try:
            # Generate content
            content_data = await self.content_engine.generate_weekly_trend_content(end_date)

            results = {
                "success": True,
                "start_date": start_date,
                "end_date": end_date,
                "content_generated": True,
                "email_sent": False,
                "local_saved": False,
                "total_articles": content_data.get("total_articles", 0),
                "trend_count": len(content_data.get("trends", [])),
                "processing_time": content_data.get("processing_time", "N/A")
            }

            # Save locally if requested
            if save_local:
                html_content = WeeklyTrendTemplate.generate_html(content_data)
                local_path = self._save_weekly_analysis_local(content_data, html_content)
                results["local_saved"] = True
                results["local_path"] = str(local_path)
                print(f"💾 Weekly analysis saved locally: {local_path}")

            # Send email if requested
            if send_email:
                email_success = await self.scheduler.send_weekly_analysis(end_date)
                results["email_sent"] = email_success

            return results

        except Exception as e:
            print(f"❌ Weekly analysis generation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "start_date": start_date,
                "end_date": end_date
            }

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
            test_date = datetime.now() - timedelta(days=1)  # Yesterday's data
            content_data = await self.content_engine.generate_daily_brief_content(test_date)

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

    def _save_daily_brief_local(self, content_data: Dict[str, Any], html_content: str) -> Path:
        """Save daily brief to local file"""
        newsletters_dir = Path("data/newsletters")
        newsletters_dir.mkdir(parents=True, exist_ok=True)

        date_str = content_data['date'].strftime('%Y-%m-%d')
        filename = f"daily_brief_{date_str}.html"
        filepath = newsletters_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return filepath

    def _save_weekly_analysis_local(self, content_data: Dict[str, Any], html_content: str) -> Path:
        """Save weekly analysis to local file"""
        newsletters_dir = Path("data/newsletters")
        newsletters_dir.mkdir(parents=True, exist_ok=True)

        start_str = content_data['start_date'].strftime('%Y-%m-%d')
        end_str = content_data['end_date'].strftime('%Y-%m-%d')
        filename = f"weekly_analysis_{start_str}_to_{end_str}.html"
        filepath = newsletters_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return filepath

    async def preview_daily_brief(self, date: Optional[datetime] = None) -> str:
        """Generate preview of daily brief (HTML content only)"""
        if date is None:
            date = datetime.now()

        content_data = await self.content_engine.generate_daily_brief_content(date)
        return DailyBriefTemplate.generate_html(content_data)

    async def preview_weekly_analysis(self, end_date: Optional[datetime] = None) -> str:
        """Generate preview of weekly analysis (HTML content only)"""
        if end_date is None:
            end_date = datetime.now()

        content_data = await self.content_engine.generate_weekly_trend_content(end_date)
        return WeeklyTrendTemplate.generate_html(content_data)

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
                "Daily intelligence briefings",
                "Weekly trend analysis",
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
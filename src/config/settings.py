import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    # Database
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/insightweaver.db")

    # Email
    smtp_server: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    email_username: str = os.getenv("EMAIL_USERNAME", "")
    email_password: str = os.getenv("EMAIL_PASSWORD", "")
    from_email: str = os.getenv("FROM_EMAIL", "")
    recipient_email: str = os.getenv("RECIPIENT_EMAIL", "")

    # API Keys
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Application
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Performance Optimizations
    enable_smart_rss_fetch: bool = os.getenv("ENABLE_SMART_RSS_FETCH", "True").lower() == "true"
    smart_rss_fetch_threshold_minutes: int = int(
        os.getenv("SMART_RSS_FETCH_THRESHOLD_MINUTES", "60")
    )

    # Data Retention Policies (in days)
    retention_articles_days: int = int(os.getenv("RETENTION_ARTICLES_DAYS", "90"))
    retention_syntheses_days: int = int(os.getenv("RETENTION_SYNTHESES_DAYS", "180"))
    retention_feed_health_days: int = int(os.getenv("RETENTION_FEED_HEALTH_DAYS", "30"))

    # Scheduling
    daily_report_enabled: bool = os.getenv("DAILY_REPORT_ENABLED", "True").lower() == "true"
    daily_report_hours: int = int(os.getenv("DAILY_REPORT_HOURS", "24"))
    auto_cleanup_enabled: bool = os.getenv("AUTO_CLEANUP_ENABLED", "True").lower() == "true"

    # Paths
    project_root: Path = Path(__file__).parent.parent.parent
    data_dir: Path = project_root / "data"
    logs_dir: Path = project_root / "src" / "logs"

    # Reports directories
    reports_dir: Path = project_root / "reports"
    briefings_dir: Path = reports_dir / "briefings"
    forecasts_dir: Path = reports_dir / "forecasts"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)
        self.reports_dir.mkdir(exist_ok=True)
        self.briefings_dir.mkdir(exist_ok=True)
        self.forecasts_dir.mkdir(exist_ok=True)


settings = Settings()

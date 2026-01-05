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

    # Deep Context Enhancements
    enable_reflection: bool = os.getenv("ENABLE_REFLECTION", "True").lower() == "true"
    reflection_depth_threshold: float = float(os.getenv("REFLECTION_DEPTH_THRESHOLD", "8.0"))
    enable_semantic_memory: bool = os.getenv("ENABLE_SEMANTIC_MEMORY", "False").lower() == "true"  # Phase 2
    enable_perception: bool = os.getenv("ENABLE_PERCEPTION", "False").lower() == "true"  # Phase 3

    # Performance Optimizations
    enable_smart_rss_fetch: bool = os.getenv("ENABLE_SMART_RSS_FETCH", "True").lower() == "true"
    smart_rss_fetch_threshold_minutes: int = int(os.getenv("SMART_RSS_FETCH_THRESHOLD_MINUTES", "60"))
    enable_trust_verification: bool = os.getenv("ENABLE_TRUST_VERIFICATION", "True").lower() == "true"

    # Data Retention Policies (in days)
    retention_articles_days: int = int(os.getenv("RETENTION_ARTICLES_DAYS", "90"))
    retention_syntheses_days: int = int(os.getenv("RETENTION_SYNTHESES_DAYS", "180"))
    retention_feed_health_days: int = int(os.getenv("RETENTION_FEED_HEALTH_DAYS", "30"))
    # Note: Semantic facts use type-based expiration (60-365 days)

    # Scheduling
    daily_report_enabled: bool = os.getenv("DAILY_REPORT_ENABLED", "True").lower() == "true"
    daily_report_hours: int = int(os.getenv("DAILY_REPORT_HOURS", "24"))  # Look back window
    auto_cleanup_enabled: bool = os.getenv("AUTO_CLEANUP_ENABLED", "True").lower() == "true"

    # Paths
    project_root: Path = Path(__file__).parent.parent.parent
    data_dir: Path = project_root / "data"
    logs_dir: Path = project_root / "src" / "logs"

    class Config:
        env_file = ".env"
        case_sensitive = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create necessary directories
        self.data_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)

settings = Settings()

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/insightweaver.db")

    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")

    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    enable_smart_rss_fetch: bool = os.getenv("ENABLE_SMART_RSS_FETCH", "True").lower() == "true"
    smart_rss_fetch_threshold_minutes: int = int(
        os.getenv("SMART_RSS_FETCH_THRESHOLD_MINUTES", "60")
    )

    project_root: Path = Path(__file__).parent.parent.parent
    data_dir: Path = project_root / "data"
    logs_dir: Path = project_root / "src" / "logs"

    # forecasts_dir is consumed by src/forecast/formatter.py and lives until Stage 8
    # deletes the forecast subsystem.
    reports_dir: Path = project_root / "reports"
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
        self.forecasts_dir.mkdir(exist_ok=True)


settings = Settings()

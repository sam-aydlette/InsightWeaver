import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

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
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

    # How similar two observations' MinHash signatures must be before they are
    # treated as the same item published twice. 0.7 was chosen against measured
    # values rather than picked: on the two real corpus pairs in
    # tests/sources/fixtures/near_duplicates.json, a genuine near-duplicate (the
    # same press release carried by two Prince William feeds, differing only in
    # byline and footer) scores 0.89, and the hardest distinct pair -- two
    # different articles from the same publisher about the same county clerk's
    # wedding events -- scores 0.016. 0.7 sits in the middle of that gap with
    # room on both sides for text this suite has not seen.
    #
    # This is the *only* near-duplicate parameter that belongs in config. The
    # signature width and shingle size are format, not preference; changing them
    # silently invalidates every signature already stored, which is why they are
    # constants in src/sources/minhash.py. (2026-08-31, backlog task 014.)
    near_duplicate_threshold: float = float(os.getenv("NEAR_DUPLICATE_THRESHOLD", "0.7"))

    project_root: Path = Path(__file__).parent.parent.parent
    data_dir: Path = project_root / "data"
    logs_dir: Path = project_root / "src" / "logs"

    # Position and the watch set are hand-authored and live in the operator's
    # *private* repository -- they name real decisions, deadlines and exposures
    # and this repo is public. The defaults deliberately point outside any
    # checkout so that a missing configuration cannot resolve to a file in the
    # tree. This repo carries config/position.example.yaml and
    # config/watches.example.yaml, and .gitignore refuses the real ones.
    # (2026-08-31, backlog task 013.)
    position_path: Path = Path(
        os.getenv("POSITION_PATH", "~/.config/insightweaver/position.yaml")
    ).expanduser()
    watches_path: Path = Path(
        os.getenv("WATCHES_PATH", "~/.config/insightweaver/watches.yaml")
    ).expanduser()

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)


settings = Settings()

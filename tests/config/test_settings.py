"""
Tests for Settings configuration
"""



class TestSettingsDefaults:
    """Tests for default setting values"""

    def test_database_url_default(self, monkeypatch):
        """Default database URL should be SQLite"""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        # Force reimport to get fresh settings
        import importlib

        import src.config.settings as settings_module

        importlib.reload(settings_module)

        assert "sqlite" in settings_module.settings.database_url

    def test_smtp_defaults(self, monkeypatch):
        """SMTP should have reasonable defaults"""
        monkeypatch.delenv("SMTP_SERVER", raising=False)
        monkeypatch.delenv("SMTP_PORT", raising=False)

        import importlib

        import src.config.settings as settings_module

        importlib.reload(settings_module)

        assert settings_module.settings.smtp_server == "smtp.gmail.com"
        assert settings_module.settings.smtp_port == 587

    def test_debug_default_false(self, monkeypatch):
        """Debug should default to False"""
        monkeypatch.delenv("DEBUG", raising=False)

        import importlib

        import src.config.settings as settings_module

        importlib.reload(settings_module)

        assert settings_module.settings.debug is False

    def test_log_level_default(self, monkeypatch):
        """Log level should default to INFO"""
        monkeypatch.delenv("LOG_LEVEL", raising=False)

        import importlib

        import src.config.settings as settings_module

        importlib.reload(settings_module)

        assert settings_module.settings.log_level == "INFO"


class TestBooleanParsing:
    """Tests for boolean environment variable parsing"""

    def test_debug_true_string(self, monkeypatch):
        """DEBUG=true should parse as True"""
        monkeypatch.setenv("DEBUG", "true")

        import importlib

        import src.config.settings as settings_module

        importlib.reload(settings_module)

        assert settings_module.settings.debug is True

    def test_debug_True_string(self, monkeypatch):
        """DEBUG=True should parse as True"""
        monkeypatch.setenv("DEBUG", "True")

        import importlib

        import src.config.settings as settings_module

        importlib.reload(settings_module)

        assert settings_module.settings.debug is True

    def test_debug_false_string(self, monkeypatch):
        """DEBUG=false should parse as False"""
        monkeypatch.setenv("DEBUG", "false")

        import importlib

        import src.config.settings as settings_module

        importlib.reload(settings_module)

        assert settings_module.settings.debug is False

    def test_debug_FALSE_string(self, monkeypatch):
        """DEBUG=FALSE should parse as False (case insensitive)"""
        monkeypatch.setenv("DEBUG", "FALSE")

        import importlib

        import src.config.settings as settings_module

        importlib.reload(settings_module)

        assert settings_module.settings.debug is False

    def test_enable_reflection_default_true(self, monkeypatch):
        """ENABLE_REFLECTION should default to True"""
        monkeypatch.delenv("ENABLE_REFLECTION", raising=False)

        import importlib

        import src.config.settings as settings_module

        importlib.reload(settings_module)

        assert settings_module.settings.enable_reflection is True

    def test_enable_semantic_memory_can_be_toggled(self, monkeypatch):
        """ENABLE_SEMANTIC_MEMORY should be configurable via env var"""
        monkeypatch.setenv("ENABLE_SEMANTIC_MEMORY", "false")

        import importlib

        import src.config.settings as settings_module

        importlib.reload(settings_module)

        assert settings_module.settings.enable_semantic_memory is False

        # Test enabling it
        monkeypatch.setenv("ENABLE_SEMANTIC_MEMORY", "true")
        importlib.reload(settings_module)
        assert settings_module.settings.enable_semantic_memory is True


class TestNumericParsing:
    """Tests for numeric environment variable parsing"""

    def test_smtp_port_parsing(self, monkeypatch):
        """SMTP_PORT should parse as integer"""
        monkeypatch.setenv("SMTP_PORT", "465")

        import importlib

        import src.config.settings as settings_module

        importlib.reload(settings_module)

        assert settings_module.settings.smtp_port == 465
        assert isinstance(settings_module.settings.smtp_port, int)

    def test_retention_days_parsing(self, monkeypatch):
        """Retention days should parse as integers"""
        monkeypatch.setenv("RETENTION_ARTICLES_DAYS", "30")
        monkeypatch.setenv("RETENTION_SYNTHESES_DAYS", "60")

        import importlib

        import src.config.settings as settings_module

        importlib.reload(settings_module)

        assert settings_module.settings.retention_articles_days == 30
        assert settings_module.settings.retention_syntheses_days == 60


class TestPathConfiguration:
    """Tests for path configuration"""

    def test_project_root_exists(self):
        """Project root path should exist"""
        from src.config.settings import settings

        assert settings.project_root.exists()

    def test_data_dir_path(self):
        """Data directory path should be relative to project root"""
        from src.config.settings import settings

        assert settings.data_dir == settings.project_root / "data"

    def test_reports_dir_structure(self):
        """Reports directories should be properly structured"""
        from src.config.settings import settings

        assert settings.reports_dir == settings.project_root / "reports"
        assert settings.briefings_dir == settings.reports_dir / "briefings"
        assert settings.forecasts_dir == settings.reports_dir / "forecasts"
        assert settings.trust_reports_dir == settings.reports_dir / "trust"


class TestDirectoryCreation:
    """Tests for automatic directory creation"""

    def test_data_dir_created(self, tmp_path, monkeypatch):
        """Settings should create data directory"""
        # This is tested implicitly by the existence tests
        # Settings.__init__ creates directories
        from src.config.settings import settings

        assert settings.data_dir.exists()

    def test_logs_dir_created(self):
        """Settings should create logs directory"""
        from src.config.settings import settings

        assert settings.logs_dir.exists()

    def test_reports_dirs_created(self):
        """Settings should create reports directories"""
        from src.config.settings import settings

        assert settings.reports_dir.exists()
        assert settings.briefings_dir.exists()
        assert settings.forecasts_dir.exists()
        assert settings.trust_reports_dir.exists()


class TestFeatureFlags:
    """Tests for feature flag configuration"""

    def test_smart_rss_fetch_default(self, monkeypatch):
        """Smart RSS fetch should default to enabled"""
        monkeypatch.delenv("ENABLE_SMART_RSS_FETCH", raising=False)

        import importlib

        import src.config.settings as settings_module

        importlib.reload(settings_module)

        assert settings_module.settings.enable_smart_rss_fetch is True

    def test_trust_verification_default(self, monkeypatch):
        """Trust verification should default to enabled"""
        monkeypatch.delenv("ENABLE_TRUST_VERIFICATION", raising=False)

        import importlib

        import src.config.settings as settings_module

        importlib.reload(settings_module)

        assert settings_module.settings.enable_trust_verification is True

    def test_daily_report_default(self, monkeypatch):
        """Daily report should default to enabled"""
        monkeypatch.delenv("DAILY_REPORT_ENABLED", raising=False)

        import importlib

        import src.config.settings as settings_module

        importlib.reload(settings_module)

        assert settings_module.settings.daily_report_enabled is True

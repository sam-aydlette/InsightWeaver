"""
Tests for Settings configuration
"""


class TestSettingsDefaults:
    """Tests for default setting values"""

    def test_database_url_default(self, monkeypatch):
        """Default database URL should be SQLite"""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        import importlib

        import src.config.settings as settings_module

        importlib.reload(settings_module)

        assert "sqlite" in settings_module.settings.database_url

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


class TestDirectoryCreation:
    """Tests for automatic directory creation"""

    def test_data_dir_created(self):
        """Settings should create data directory"""
        from src.config.settings import settings

        assert settings.data_dir.exists()

    def test_logs_dir_created(self):
        """Settings should create logs directory"""
        from src.config.settings import settings

        assert settings.logs_dir.exists()


class TestFeatureFlags:
    """Tests for feature flag configuration"""

    def test_smart_rss_fetch_default(self, monkeypatch):
        """Smart RSS fetch should default to enabled"""
        monkeypatch.delenv("ENABLE_SMART_RSS_FETCH", raising=False)

        import importlib

        import src.config.settings as settings_module

        importlib.reload(settings_module)

        assert settings_module.settings.enable_smart_rss_fetch is True

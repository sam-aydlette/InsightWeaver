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

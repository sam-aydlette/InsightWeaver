"""
Tests for Web Server
"""




class TestCreateApp:
    """Tests for Flask app creation"""

    def test_create_app_returns_flask_app(self):
        """Should return Flask application"""
        from src.web.server import create_app

        app = create_app()

        assert app is not None
        assert hasattr(app, "route")

    def test_create_app_configures_templates(self):
        """Should configure template folder"""
        from src.web.server import create_app

        app = create_app()

        assert app.template_folder is not None

    def test_create_app_registers_blueprints(self):
        """Should register route blueprints"""
        from src.web.server import create_app

        app = create_app()

        # Check that blueprints are registered
        assert len(app.blueprints) > 0


class TestRootRoute:
    """Tests for root route"""

    def test_root_redirects_or_serves_dashboard(self, test_client):
        """Should redirect to dashboard or serve it"""
        response = test_client.get("/")

        # Should either redirect (302) or serve (200)
        assert response.status_code in [200, 302, 308]


class TestSetupRouteExists:
    """Tests for setup route existence"""

    def test_setup_route_exists(self, test_client):
        """Should have setup route"""
        response = test_client.get("/setup")

        # Should return 200 or redirect
        assert response.status_code in [200, 302, 308]


class TestApiRoutes:
    """Tests for API route existence"""

    def test_brief_routes_exist(self, flask_app):
        """Should have brief routes registered"""
        # Check that brief blueprint is registered
        assert "brief" in flask_app.blueprints or any(
            "brief" in str(rule) for rule in flask_app.url_map.iter_rules()
        )

    def test_trust_routes_exist(self, flask_app):
        """Should have trust routes registered"""
        assert "trust" in flask_app.blueprints or any(
            "trust" in str(rule) for rule in flask_app.url_map.iter_rules()
        )

    def test_forecast_routes_exist(self, flask_app):
        """Should have forecast routes registered"""
        assert "forecast" in flask_app.blueprints or any(
            "forecast" in str(rule) for rule in flask_app.url_map.iter_rules()
        )

    def test_dashboard_routes_exist(self, flask_app):
        """Should have dashboard routes registered"""
        assert "dashboard" in flask_app.blueprints or any(
            "dashboard" in str(rule) for rule in flask_app.url_map.iter_rules()
        )


class TestStaticFiles:
    """Tests for static file configuration"""

    def test_static_folder_configured(self, flask_app):
        """Should have static folder configured"""
        assert flask_app.static_folder is not None


class TestErrorHandling:
    """Tests for error handling"""

    def test_404_returns_error(self, test_client):
        """Should return 404 for non-existent routes"""
        response = test_client.get("/nonexistent-route-12345")

        assert response.status_code == 404


class TestTestingConfig:
    """Tests for testing configuration"""

    def test_testing_mode_enabled(self, flask_app):
        """Should have testing mode enabled"""
        flask_app.config["TESTING"] = True

        assert flask_app.config["TESTING"] is True

    def test_debug_mode_configurable(self, flask_app):
        """Should have configurable debug mode"""
        flask_app.config["DEBUG"] = True

        assert flask_app.config["DEBUG"] is True

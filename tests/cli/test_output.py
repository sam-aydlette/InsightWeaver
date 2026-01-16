"""
Tests for CLI Output Management
"""

import logging
import sys

from src.cli.output import (
    OutputManager,
    get_output_manager,
    is_debug_mode,
    set_debug_mode,
)


class TestOutputManagerInit:
    """Tests for OutputManager initialization"""

    def test_init_debug_false(self):
        """Should initialize with debug=False by default"""
        manager = OutputManager()

        assert manager.debug is False

    def test_init_debug_true(self):
        """Should accept debug=True"""
        manager = OutputManager(debug=True)

        assert manager.debug is True


class TestSuppressOutput:
    """Tests for output suppression context manager"""

    def test_suppress_output_hides_stdout(self):
        """Should suppress stdout when not in debug mode"""
        manager = OutputManager(debug=False)

        original_stdout = sys.stdout

        with manager.suppress_output():
            print("This should not appear")
            # stdout should be redirected
            assert sys.stdout is not original_stdout

        # After context, stdout should be restored
        assert sys.stdout is original_stdout

    def test_suppress_output_hides_stderr(self):
        """Should suppress stderr when not in debug mode"""
        manager = OutputManager(debug=False)

        original_stderr = sys.stderr

        with manager.suppress_output():
            print("Error message", file=sys.stderr)
            # stderr should be redirected
            assert sys.stderr is not original_stderr

        # After context, stderr should be restored
        assert sys.stderr is original_stderr

    def test_suppress_output_allows_output_in_debug_mode(self, capsys):
        """Should allow output when in debug mode"""
        manager = OutputManager(debug=True)

        with manager.suppress_output():
            print("Debug message")

        captured = capsys.readouterr()
        assert "Debug message" in captured.out

    def test_suppress_output_restores_on_exception(self):
        """Should restore streams even if exception occurs"""
        manager = OutputManager(debug=False)
        original_stdout = sys.stdout
        original_stderr = sys.stderr

        try:
            with manager.suppress_output():
                raise ValueError("Test exception")
        except ValueError:
            pass

        assert sys.stdout is original_stdout
        assert sys.stderr is original_stderr


class TestConfigureLogging:
    """Tests for logging configuration"""

    def test_configure_logging_debug_mode(self):
        """Should set DEBUG level in debug mode"""
        manager = OutputManager(debug=True)

        manager.configure_logging()

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_configure_logging_non_debug_mode(self):
        """Should set CRITICAL level in non-debug mode"""
        manager = OutputManager(debug=False)

        manager.configure_logging()

        root_logger = logging.getLogger()
        assert root_logger.level == logging.CRITICAL

    def test_configure_logging_custom_level(self):
        """Should accept custom logging level"""
        manager = OutputManager(debug=True)

        manager.configure_logging(level=logging.WARNING)

        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING


class TestManagerPrint:
    """Tests for manager print method"""

    def test_print_outputs_message(self, capsys):
        """Should print message to stdout"""
        manager = OutputManager(debug=False)

        manager.print("Test message")

        captured = capsys.readouterr()
        assert "Test message" in captured.out


class TestGetOutputManager:
    """Tests for global output manager getter"""

    def test_get_output_manager_returns_instance(self):
        """Should return OutputManager instance"""
        manager = get_output_manager()

        assert isinstance(manager, OutputManager)

    def test_get_output_manager_singleton(self):
        """Should return same instance on multiple calls"""
        # Reset global state first
        set_debug_mode(False)

        manager1 = get_output_manager()
        manager2 = get_output_manager()

        assert manager1 is manager2


class TestSetDebugMode:
    """Tests for setting debug mode globally"""

    def test_set_debug_mode_true(self):
        """Should set debug mode to True"""
        set_debug_mode(True)

        assert is_debug_mode() is True

    def test_set_debug_mode_false(self):
        """Should set debug mode to False"""
        set_debug_mode(False)

        assert is_debug_mode() is False

    def test_set_debug_mode_configures_logging(self):
        """Should configure logging when setting debug mode"""
        set_debug_mode(True)

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG


class TestIsDebugMode:
    """Tests for debug mode checker"""

    def test_is_debug_mode_returns_bool(self):
        """Should return boolean"""
        set_debug_mode(False)

        result = is_debug_mode()

        assert isinstance(result, bool)

    def test_is_debug_mode_reflects_current_state(self):
        """Should reflect current debug state"""
        set_debug_mode(True)
        assert is_debug_mode() is True

        set_debug_mode(False)
        assert is_debug_mode() is False

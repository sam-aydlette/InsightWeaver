"""
Output management for CLI commands
Handles output suppression and debug mode
"""

import logging
import sys
from contextlib import contextmanager
from io import StringIO


class OutputManager:
    """Manages output suppression for CLI commands"""

    def __init__(self, debug=False):
        self.debug = debug
        self._original_stdout = None
        self._original_stderr = None
        self._stdout_buffer = None
        self._stderr_buffer = None

    @contextmanager
    def suppress_output(self):
        """
        Context manager to suppress stdout/stderr output

        Usage:
            with output_manager.suppress_output():
                print("This won't show unless in debug mode")
        """
        if self.debug:
            yield
            return

        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        self._stdout_buffer = StringIO()
        self._stderr_buffer = StringIO()

        sys.stdout = self._stdout_buffer
        sys.stderr = self._stderr_buffer

        try:
            yield
        finally:
            sys.stdout = self._original_stdout
            sys.stderr = self._original_stderr

    def configure_logging(self, level=None):
        """
        Configure logging based on debug mode

        Args:
            level: Logging level (default: DEBUG if debug=True, CRITICAL otherwise)
        """
        if level is None:
            level = logging.DEBUG if self.debug else logging.CRITICAL

        # Remove all existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Configure with new level
        if self.debug:
            # In debug mode, show all logs
            logging.basicConfig(
                level=level,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                force=True,
            )
        else:
            # In non-debug mode, suppress all logs by using CRITICAL level
            # (higher than ERROR, so errors won't show either)
            logging.basicConfig(
                level=logging.CRITICAL,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                force=True,
            )

    def print(self, message):
        """Print message (always shown, even in non-debug mode)"""
        print(message)


# Global output manager instance
_output_manager = None


def get_output_manager():
    """Get the global output manager instance"""
    global _output_manager
    if _output_manager is None:
        _output_manager = OutputManager(debug=False)
    return _output_manager


def set_debug_mode(debug):
    """Set debug mode globally"""
    global _output_manager
    _output_manager = OutputManager(debug=debug)
    _output_manager.configure_logging()


def is_debug_mode():
    """Check if debug mode is enabled"""
    return get_output_manager().debug

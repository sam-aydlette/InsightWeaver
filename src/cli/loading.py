"""
Loading indicator utility for CLI commands
Provides animated "Executing..." display with dots
"""
import sys
import threading
import time
from contextlib import contextmanager


class LoadingIndicator:
    """Animated loading indicator with dots"""

    def __init__(self, message="Executing"):
        self.message = message
        self.is_running = False
        self.thread = None

    def _animate(self):
        """Animation loop - dots appear one by one, then disappear and repeat"""
        dots = 0
        while self.is_running:
            # Create the dot display (0 dots, 1 dot, 2 dots, 3 dots, then back to 0)
            dot_display = '.' * dots
            # Pad with spaces to ensure consistent width (3 spaces for max 3 dots)
            padding = ' ' * (3 - dots)
            sys.stdout.write(f"\r{self.message}{dot_display}{padding}")
            sys.stdout.flush()

            # Cycle through 0, 1, 2, 3 dots
            dots = (dots + 1) % 4
            time.sleep(0.4)

        # Clear the line when done
        sys.stdout.write("\r" + " " * (len(self.message) + 3) + "\r")
        sys.stdout.flush()

    def start(self):
        """Start the loading animation"""
        self.is_running = True
        self.thread = threading.Thread(target=self._animate, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the loading animation"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=1)


@contextmanager
def loading(message="Executing", debug=False):
    """
    Context manager for showing loading indicator

    Args:
        message: Message to display (default: "Executing")
        debug: If True, skip loading indicator

    Usage:
        with loading("Processing data"):
            # do work
            pass
    """
    if debug:
        yield
        return

    indicator = LoadingIndicator(message)
    indicator.start()
    try:
        yield
    finally:
        indicator.stop()

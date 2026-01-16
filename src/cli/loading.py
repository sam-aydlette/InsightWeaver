"""
Loading indicator utility for CLI commands
Provides animated "Executing..." display with dots
"""

import sys
import threading
import time
from contextlib import contextmanager

# ANSI escape codes for bright green (hacker aesthetic)
GREEN = "\033[92m"
RESET = "\033[0m"


class LoadingIndicator:
    """Animated loading indicator with dots"""

    def __init__(self, message="Executing"):
        self.message = message
        self.is_running = False
        self.thread = None

    def _animate(self):
        """Animation loop - spinner cycles continuously"""
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        idx = 0
        while self.is_running:
            frame = frames[idx % len(frames)]
            # Write to __stderr__ which is the original stderr before any redirection
            # This prevents the output manager from suppressing the spinner
            sys.__stderr__.write(f"\r{GREEN}{frame}{RESET} {self.message}... ")
            sys.__stderr__.flush()

            idx += 1
            time.sleep(0.1)

        # Clear the line when done
        sys.__stderr__.write("\r" + " " * (len(self.message) + 10) + "\r")
        sys.__stderr__.flush()

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

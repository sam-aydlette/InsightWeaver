"""
Performance Profiler for InsightWeaver
Thread-safe timing instrumentation for identifying bottlenecks
"""

import threading
import time
from contextlib import contextmanager
from datetime import datetime


class PerformanceProfiler:
    """Thread-safe performance profiler for timing operations"""

    def __init__(self):
        self._operations: list[dict] = []
        self._lock = threading.Lock()
        self._start_time = None

    @contextmanager
    def profile(self, operation_name: str, **metadata):
        """Context manager for timing operations"""
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            with self._lock:
                self._operations.append(
                    {
                        "operation": operation_name,
                        "duration": duration,
                        "timestamp": datetime.now(),
                        "metadata": metadata,
                    }
                )

    def start_session(self):
        """Start timing session"""
        self._start_time = time.perf_counter()

    def get_summary(self) -> dict:
        """Get performance summary"""
        if not self._operations:
            return {}

        total_time = time.perf_counter() - self._start_time if self._start_time else 0

        # Group by operation name
        grouped = {}
        for op in self._operations:
            name = op["operation"]
            if name not in grouped:
                grouped[name] = []
            grouped[name].append(op["duration"])

        # Calculate stats
        summary = []
        for name, durations in grouped.items():
            summary.append(
                {
                    "operation": name,
                    "count": len(durations),
                    "total": sum(durations),
                    "avg": sum(durations) / len(durations),
                    "min": min(durations),
                    "max": max(durations),
                    "pct": (sum(durations) / total_time * 100) if total_time > 0 else 0,
                }
            )

        # Sort by total time
        summary.sort(key=lambda x: x["total"], reverse=True)

        return {
            "total_time": total_time,
            "total_operations": len(self._operations),
            "breakdown": summary,
        }

    def print_summary(self):
        """Print formatted summary"""
        summary = self.get_summary()

        if not summary:
            print("\nNo profiling data collected")
            return

        print("\n" + "=" * 80)
        print("PERFORMANCE PROFILE")
        print("=" * 80)
        print(f"Total Time: {summary['total_time']:.2f}s")
        print(f"Total Operations: {summary['total_operations']}")
        print()
        print(f"{'Operation':<40} {'Count':>6} {'Total':>10} {'Avg':>10} {'%':>6}")
        print("-" * 80)

        for item in summary["breakdown"]:
            print(
                f"{item['operation']:<40} {item['count']:>6} "
                f"{item['total']:>9.2f}s {item['avg']:>9.2f}s {item['pct']:>5.1f}%"
            )

    def reset(self):
        """Reset profiler state"""
        with self._lock:
            self._operations.clear()
            self._start_time = None


# Global profiler instance
_profiler = PerformanceProfiler()


def get_profiler():
    """Get the global profiler instance"""
    return _profiler


@contextmanager
def profile(operation: str, **metadata):
    """Convenience function for profiling"""
    with _profiler.profile(operation, **metadata):
        yield

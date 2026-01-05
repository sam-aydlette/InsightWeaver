"""
Error Handling Utilities for InsightWeaver

Provides:
- Custom exception hierarchy
- Retry decorator with exponential backoff
- Graceful degradation patterns
- Error context tracking
"""

import asyncio
import functools
import time
from typing import Any, Callable, TypeVar, cast

from .logging import get_logger

logger = get_logger(__name__)

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])


# ============================================================================
# Custom Exception Hierarchy
# ============================================================================


class InsightWeaverError(Exception):
    """Base exception for all InsightWeaver errors"""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}


class APIError(InsightWeaverError):
    """Base class for API-related errors"""

    pass


class ClaudeAPIError(APIError):
    """Error when communicating with Claude API"""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        context: dict[str, Any] | None = None
    ):
        super().__init__(message, context)
        self.status_code = status_code


class RateLimitError(APIError):
    """API rate limit exceeded"""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
        context: dict[str, Any] | None = None
    ):
        super().__init__(message, context)
        self.retry_after = retry_after


class AuthenticationError(APIError):
    """API authentication failed"""

    pass


class DataError(InsightWeaverError):
    """Base class for data-related errors"""

    pass


class ValidationError(DataError):
    """Data validation failed"""

    pass


class ParsingError(DataError):
    """Failed to parse data"""

    pass


class DatabaseError(InsightWeaverError):
    """Database operation failed"""

    pass


class ConfigurationError(InsightWeaverError):
    """Configuration is invalid or missing"""

    pass


class TimeoutError(InsightWeaverError):
    """Operation timed out"""

    pass


# ============================================================================
# Retry Decorator with Exponential Backoff
# ============================================================================


def retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    on_retry: Callable[[Exception, int], None] | None = None,
) -> Callable[[F], F]:
    """
    Decorator to retry a function with exponential backoff

    Args:
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        exceptions: Tuple of exception types to retry on
        on_retry: Optional callback function called on each retry

    Example:
        @retry(max_attempts=3, initial_delay=1.0, exceptions=(ClaudeAPIError,))
        async def call_claude_api():
            ...

        @retry(max_attempts=5, exceptions=(RateLimitError, TimeoutError))
        def fetch_data():
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts",
                            extra_fields={
                                "function": func.__name__,
                                "attempts": max_attempts,
                                "error": str(e),
                            },
                            exc_info=True,
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(initial_delay * (exponential_base ** (attempt - 1)), max_delay)

                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt}/{max_attempts}), "
                        f"retrying in {delay:.2f}s",
                        extra_fields={
                            "function": func.__name__,
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                            "delay": delay,
                            "error": str(e),
                        },
                    )

                    if on_retry:
                        on_retry(e, attempt)

                    await asyncio.sleep(delay)

            # This should never be reached, but type checker needs it
            raise last_exception if last_exception else Exception("Unexpected retry error")

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts",
                            extra_fields={
                                "function": func.__name__,
                                "attempts": max_attempts,
                                "error": str(e),
                            },
                            exc_info=True,
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(initial_delay * (exponential_base ** (attempt - 1)), max_delay)

                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt}/{max_attempts}), "
                        f"retrying in {delay:.2f}s",
                        extra_fields={
                            "function": func.__name__,
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                            "delay": delay,
                            "error": str(e),
                        },
                    )

                    if on_retry:
                        on_retry(e, attempt)

                    time.sleep(delay)

            # This should never be reached, but type checker needs it
            raise last_exception if last_exception else Exception("Unexpected retry error")

        # Return appropriate wrapper based on whether function is async
        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        else:
            return cast(F, sync_wrapper)

    return decorator


# ============================================================================
# Graceful Degradation Patterns
# ============================================================================


def with_fallback(fallback_value: Any = None, log_errors: bool = True) -> Callable[[F], F]:
    """
    Decorator to provide fallback value on error (graceful degradation)

    Args:
        fallback_value: Value to return if function raises an exception
        log_errors: Whether to log errors when falling back

    Example:
        @with_fallback(fallback_value=[])
        def get_items():
            # If this fails, returns []
            ...

        @with_fallback(fallback_value=None)
        async def fetch_optional_data():
            # If this fails, returns None
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    logger.warning(
                        f"{func.__name__} failed, using fallback value",
                        extra_fields={
                            "function": func.__name__,
                            "fallback_value": fallback_value,
                            "error": str(e),
                        },
                        exc_info=True,
                    )
                return fallback_value

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    logger.warning(
                        f"{func.__name__} failed, using fallback value",
                        extra_fields={
                            "function": func.__name__,
                            "fallback_value": fallback_value,
                            "error": str(e),
                        },
                        exc_info=True,
                    )
                return fallback_value

        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        else:
            return cast(F, sync_wrapper)

    return decorator


def timeout(seconds: float) -> Callable[[F], F]:
    """
    Decorator to add timeout to async functions

    Args:
        seconds: Timeout duration in seconds

    Example:
        @timeout(30.0)
        async def slow_operation():
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                logger.error(
                    f"{func.__name__} timed out after {seconds}s",
                    extra_fields={"function": func.__name__, "timeout_seconds": seconds},
                )
                raise TimeoutError(
                    f"{func.__name__} timed out after {seconds}s",
                    context={"timeout_seconds": seconds},
                )

        if not asyncio.iscoroutinefunction(func):
            raise TypeError(f"@timeout can only be applied to async functions, {func.__name__} is sync")

        return cast(F, wrapper)

    return decorator


# ============================================================================
# Error Context Manager
# ============================================================================


class ErrorContext:
    """
    Context manager for adding structured error context

    Example:
        with ErrorContext("processing_user", user_id=123):
            process_user(user_id)
    """

    def __init__(self, operation: str, **context: Any):
        self.operation = operation
        self.context = context
        self.start_time: float | None = None

    def __enter__(self) -> "ErrorContext":
        self.start_time = time.time()
        logger.debug(
            f"Starting {self.operation}",
            extra_fields={"operation": self.operation, **self.context},
        )
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any) -> bool:
        duration = time.time() - (self.start_time or time.time())

        if exc_type is None:
            logger.debug(
                f"Completed {self.operation}",
                extra_fields={
                    "operation": self.operation,
                    "duration_seconds": duration,
                    **self.context,
                },
            )
        else:
            logger.error(
                f"Failed {self.operation}",
                extra_fields={
                    "operation": self.operation,
                    "duration_seconds": duration,
                    "error": str(exc_val),
                    **self.context,
                },
                exc_info=True,
            )

        return False  # Don't suppress exceptions

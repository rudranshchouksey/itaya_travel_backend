import asyncio
import logging
import random
from functools import wraps
from typing import Any, Callable, TypeVar

from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TransientRetryError(Exception):
    """Exception raised when a transient error occurs that should be retried."""
    pass


def with_backoff(
    max_attempts: int = settings.RETRY_MAX_ATTEMPTS,
    initial_delay: float = settings.RETRY_INITIAL_DELAY_SECONDS,
    max_delay: float = settings.RETRY_MAX_DELAY_SECONDS,
    backoff_multiplier: float = settings.RETRY_BACKOFF_MULTIPLIER,
    retryable_exceptions: tuple[type[Exception], ...] = (TransientRetryError,),
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator that retries an async function with exponential backoff and jitter.

    Args:
        max_attempts: Maximum number of attempts before failing.
        initial_delay: Initial delay in seconds before the first retry.
        max_delay: Maximum delay in seconds between retries.
        backoff_multiplier: Multiplier for the delay after each retry.
        retryable_exceptions: Tuple of exception classes that should trigger a retry.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 1
            delay = initial_delay

            while True:
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    if attempt >= max_attempts:
                        logger.error(
                            f"Max retries ({max_attempts}) reached for {func.__name__}. Last error: {e}"
                        )
                        raise

                    # Add jitter: random between 50% and 100% of the calculated delay
                    jitter = random.uniform(0.5, 1.0)
                    sleep_time = delay * jitter

                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} for {func.__name__} failed with {type(e).__name__}: {e}. "
                        f"Retrying in {sleep_time:.2f}s..."
                    )

                    await asyncio.sleep(sleep_time)

                    attempt += 1
                    delay = min(delay * backoff_multiplier, max_delay)
                except Exception as e:
                    # Non-retryable exception
                    logger.error(f"Non-retryable error in {func.__name__}: {e}")
                    raise

        return wrapper

    return decorator

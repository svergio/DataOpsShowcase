from __future__ import annotations

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter


def with_backoff(max_attempts: int = 5):
    return retry(
        reraise=True,
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential_jitter(initial=0.5, max=20.0),
        retry=retry_if_exception_type(Exception),
    )

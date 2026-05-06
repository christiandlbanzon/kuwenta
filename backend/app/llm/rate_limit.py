"""Async token-bucket rate limiter.

Used to respect free-tier limits (e.g. Gemini 15 req/min). Process-local — fine for
a single backend instance; would need Redis-backed bucket if we ever scale to multiple workers.
"""

import asyncio
import time


class TokenBucket:
    def __init__(self, rate_per_minute: int) -> None:
        if rate_per_minute <= 0:
            raise ValueError("rate_per_minute must be positive")
        self.capacity: float = float(rate_per_minute)
        self.tokens: float = float(rate_per_minute)
        self.refill_per_second: float = rate_per_minute / 60.0
        self.last_refill: float = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, n: int = 1) -> None:
        """Block until `n` tokens are available, then consume them."""
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self.last_refill
                self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_second)
                self.last_refill = now
                if self.tokens >= n:
                    self.tokens -= n
                    return
                deficit = n - self.tokens
                wait_for = deficit / self.refill_per_second
            await asyncio.sleep(wait_for)

import asyncio
import time

from app.llm.rate_limit import TokenBucket


async def test_bucket_allows_capacity_burst() -> None:
    bucket = TokenBucket(rate_per_minute=60)
    start = time.monotonic()
    for _ in range(5):
        await bucket.acquire()
    elapsed = time.monotonic() - start
    assert elapsed < 0.1  # burst should be near-instant


async def test_bucket_throttles_when_drained() -> None:
    # 60/min => 1 token/sec refill; drain capacity then time the next acquire
    bucket = TokenBucket(rate_per_minute=60)
    for _ in range(60):
        await bucket.acquire()
    start = time.monotonic()
    await bucket.acquire()
    elapsed = time.monotonic() - start
    # Should wait roughly 1 second; allow generous slack on slow CI
    assert 0.5 < elapsed < 2.0


async def test_bucket_concurrent_acquires_serialize() -> None:
    bucket = TokenBucket(rate_per_minute=120)  # 2/sec
    # 4 simultaneous acquires after capacity = 4 tokens; should be instant
    await asyncio.gather(*(bucket.acquire() for _ in range(4)))

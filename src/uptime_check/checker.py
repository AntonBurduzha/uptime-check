import asyncio
import time
from collections.abc import Sequence

import httpx

from uptime_check.models import Result, Target

RETRY_DELAY_S = 0.5
ATTEMPTS = 2


def elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000


def failure(url: str, started: float, exc: Exception) -> Result:
    return Result(
        url=url,
        ok=False,
        status=None,
        ms=elapsed_ms(started),
        error=type(exc).__name__,
    )


async def check_one(client: httpx.AsyncClient, target: Target, timeout_s: float) -> Result:
    url = str(target.url)
    for attempt in range(1, ATTEMPTS + 1):
        started = time.perf_counter()
        try:
            async with asyncio.timeout(timeout_s):
                response = await client.get(url)

        except (TimeoutError, httpx.TransportError) as exc:
            if attempt == ATTEMPTS:
                return failure(url, started, exc)
            await asyncio.sleep(RETRY_DELAY_S)
        except httpx.RequestError as exc:
            return failure(url, started, exc)
        else:
            return Result(
                url=url,
                ok=response.status_code < 400,
                status=response.status_code,
                ms=elapsed_ms(started),
                error=None,
            )
    raise AssertionError("unreachable")


async def check_all(
    targets: Sequence[Target],
    concurrency: int,
    timeout_s: float,
) -> list[Result]:
    limit = asyncio.Semaphore(concurrency)

    async def guarded_check(client: httpx.AsyncClient, target: Target) -> Result:
        async with limit:
            return await check_one(client, target, timeout_s)

    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout_s) as client:
        return await asyncio.gather(*(guarded_check(client, target) for target in targets))

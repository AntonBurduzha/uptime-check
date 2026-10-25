import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest
import respx

from uptime_check import checker
from uptime_check.checker import check_all, check_one
from uptime_check.models import Target

UP_URL = "https://up.test/health"
DOWN_URL = "https://down.test/health"
FLAKY_URL = "https://flaky.test/health"


def make_target(url: str) -> Target:
    return Target.model_validate({"url": url})


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(checker, "RETRY_DELAY_S", 0.0)


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as c:
        yield c


async def test_200_is_up(respx_mock: respx.MockRouter, client: httpx.AsyncClient) -> None:
    route = respx_mock.get(UP_URL).mock(return_value=httpx.Response(200))
    result = await check_one(client, make_target(UP_URL), timeout_s=5.0)
    assert result.ok is True
    assert result.status == 200
    assert result.error is None
    assert route.call_count == 1


async def test_503_is_down_without_retry(
    respx_mock: respx.MockRouter,
    client: httpx.AsyncClient,
) -> None:
    route = respx_mock.get(DOWN_URL).mock(return_value=httpx.Response(503))
    result = await check_one(client, make_target(DOWN_URL), timeout_s=5.0)
    assert result.ok is False
    assert result.status == 503
    assert result.error is None
    assert route.call_count == 1


async def test_timeout_then_200_is_up_after_retry(
    respx_mock: respx.MockRouter,
    client: httpx.AsyncClient,
) -> None:
    route = respx_mock.get(FLAKY_URL).mock(
        side_effect=[httpx.ConnectTimeout("connect timed out"), httpx.Response(200)],
    )
    result = await check_one(client, make_target(FLAKY_URL), timeout_s=5.0)
    assert result.ok is True
    assert result.status == 200
    assert route.call_count == 2


async def test_two_timeouts_is_down_with_error(
    respx_mock: respx.MockRouter,
    client: httpx.AsyncClient,
) -> None:
    route = respx_mock.get(FLAKY_URL).mock(
        side_effect=[
            httpx.ConnectTimeout("connect timed out"),
            httpx.ConnectTimeout("connect timed out"),
        ],
    )
    result = await check_one(client, make_target(FLAKY_URL), timeout_s=5.0)
    assert result.ok is False
    assert result.status is None
    assert result.error == "ConnectTimeout"
    assert route.call_count == 2


@pytest.mark.slow
async def test_slow_answer_hits_the_time_limit(
    respx_mock: respx.MockRouter,
    client: httpx.AsyncClient,
) -> None:
    attempts = 0

    async def too_slow(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        await asyncio.sleep(1.0)
        return httpx.Response(200)

    respx_mock.get(UP_URL).mock(side_effect=too_slow)
    result = await check_one(client, make_target(UP_URL), timeout_s=0.5)
    assert result.ok is False
    assert result.status is None
    assert result.error == "TimeoutError"
    assert attempts == 2


async def test_check_all_keeps_input_order(respx_mock: respx.MockRouter) -> None:
    delays = {"/0": 0.1, "/1": 0.05}

    async def delayed(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(delays.get(request.url.path, 0.0))
        return httpx.Response(200)

    respx_mock.get(host="order.test").mock(side_effect=delayed)
    urls = [f"https://order.test/{i}" for i in range(3)]
    results = await check_all([make_target(u) for u in urls], concurrency=3, timeout_s=5.0)
    assert [r.url for r in results] == urls


async def test_check_all_respects_concurrency_limit(respx_mock: respx.MockRouter) -> None:
    in_flight = 0
    peak = 0

    async def slow_ok(_: httpx.Request) -> httpx.Response:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.1)
        in_flight -= 1
        return httpx.Response(200)

    respx_mock.get(host="slow.test").mock(side_effect=slow_ok)
    targets = [make_target(f"https://slow.test/{i}") for i in range(10)]
    results = await check_all(targets, concurrency=3, timeout_s=5.0)
    assert peak == 3
    assert len(results) == 10
    assert all(r.ok for r in results)

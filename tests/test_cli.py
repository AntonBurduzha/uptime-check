from pathlib import Path

import httpx
import pytest
import respx

from uptime_check.cli import main

UP_URL = "https://up.test/health"
DOWN_URL = "https://down.test/health"


def write_urls(tmp_path: Path, *lines: str) -> Path:
    path = tmp_path / "urls.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_all_up_exits_0(
    tmp_path: Path,
    respx_mock: respx.MockRouter,
    capsys: pytest.CaptureFixture[str],
) -> None:
    other_url = "https://also-up.test/health"
    respx_mock.get(UP_URL).mock(return_value=httpx.Response(200))
    respx_mock.get(other_url).mock(return_value=httpx.Response(200))
    path = write_urls(tmp_path, UP_URL, other_url)

    code = main([str(path)])

    assert code == 0
    assert capsys.readouterr().out.splitlines()[-1] == "2 up, 0 down"


def test_one_down_exits_1(
    tmp_path: Path,
    respx_mock: respx.MockRouter,
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx_mock.get(UP_URL).mock(return_value=httpx.Response(200))
    respx_mock.get(DOWN_URL).mock(return_value=httpx.Response(503))
    path = write_urls(tmp_path, UP_URL, DOWN_URL)

    code = main([str(path)])

    lines = capsys.readouterr().out.splitlines()
    assert code == 1
    assert lines[0] == "STATUS       MS  URL"
    assert lines[1].startswith("200 ")
    assert lines[1].endswith(UP_URL)
    assert lines[2].startswith("503 ")
    assert lines[2].endswith(DOWN_URL)
    assert lines[-1] == "1 up, 1 down"


def test_unreadable_file_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main([str(tmp_path / "missing.txt")])

    captured = capsys.readouterr()
    assert code == 2
    assert "cannot read" in captured.err
    assert captured.out == ""


def test_skips_invalid_lines(
    tmp_path: Path,
    respx_mock: respx.MockRouter,
    capsys: pytest.CaptureFixture[str],
) -> None:
    route = respx_mock.get(UP_URL).mock(return_value=httpx.Response(200))
    path = write_urls(tmp_path, "not a url", UP_URL)

    code = main([str(path)])

    captured = capsys.readouterr()
    assert code == 0
    assert "skipped line 1: 'not a url'" in captured.err
    assert captured.out.splitlines()[-1] == "1 up, 0 down"


def test_zero_concurrency_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["urls.txt", "--concurrency", "0"])

    assert exc_info.value.code == 2
    assert "must be at least 1" in capsys.readouterr().err

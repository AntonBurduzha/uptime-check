import argparse

# asyncio.run(): create the event loop, run one coroutine to the end, close the loop.
import asyncio

# sys.stderr: the standard error stream, a file object; print(..., file=sys.stderr) writes to it.
import sys

# Iterator: the type of a generator. Sequence: a read-only list-like parameter type.
from collections.abc import Iterator, Sequence

# Path: an object for a file path that can also read and write the file (.read_text()).
from pathlib import Path

# ValidationError: raised by Pydantic when input doesn't fit the model; .errors() lists problems.
from pydantic import ValidationError

from uptime_check.checker import check_all
from uptime_check.models import Result, Target

EXIT_ALL_UP = 0
EXIT_SOME_DOWN = 1
EXIT_CANNOT_READ = 2


class UrlFileError(Exception):
    """The URL file could not be read."""


def read_file(path: Path) -> str:
    try:
        return path.read_text()
    except (OSError, UnicodeDecodeError) as exc:
        raise UrlFileError(f"cannot read {path!s}: {exc}") from exc


def iter_candidates(text: str) -> Iterator[tuple[int, str]]:
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        yield number, line


def parse_targets(text: str) -> tuple[list[Target], list[str]]:
    targets: list[Target] = []
    problems: list[str] = []
    for number, line in iter_candidates(text):
        try:
            targets.append(Target.model_validate({"url": line}))
        except ValidationError as exc:
            reason = exc.errors()[0]["msg"]
            problems.append(f"skipped line {number}: {line!r}: {reason}")
    return targets, problems


def format_table(results: Sequence[Result]) -> str:
    lines = [f"{'STATUS':<6}  {'MS':>7}  URL"]
    for result in results:
        status = "ERR" if result.status is None else str(result.status)
        note = "" if result.error is None else f"  ({result.error})"
        lines.append(f"{status:<6}  {result.ms:>7.0f}  {result.url}{note}")

    up = sum(1 for result in results if result.ok)
    lines.append(f"{up} up, {len(results) - up} down")
    return "\n".join(lines)


def positive_int(value: str) -> int:
    int_value = int(value)
    if int_value < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1: {value!r}")
    return int_value


def positive_float(value: str) -> float:
    float_value = float(value)
    if not float_value > 0:
        raise argparse.ArgumentTypeError(f"must be above 0: {value!r}")
    return float_value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uptime_check", description="Check that every URL in a file is responds."
    )
    parser.add_argument("file", type=Path, help="text file with one URL per line")
    parser.add_argument(
        "-c",
        "--concurrency",
        type=positive_int,
        default=10,
        help="max requests in flight (default: 10)",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=positive_float,
        default=5.0,
        help="time limit per attempt (default: 5.0)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path: Path = args.file
    try:
        text = read_file(path)
    except UrlFileError as exc:
        print(f"uptime-check: {exc}", file=sys.stderr)
        return EXIT_CANNOT_READ

    targets, problems = parse_targets(text)
    for problem in problems:
        print(problem, file=sys.stderr)
    results = asyncio.run(
        check_all(targets, concurrency=args.concurrency, timeout_s=args.timeout),
    )
    print(format_table(results))
    return EXIT_ALL_UP if all(result.ok for result in results) else EXIT_SOME_DOWN


if __name__ == "__main__":
    sys.exit(main())

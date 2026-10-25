# uptime-check

A small CLI tool that checks that every URL in a text file responds.
Requests run concurrently, each with a timeout, and the results are printed as a table.

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)

## Install

```sh
git clone https://github.com/AntonBurduzha/uptime-check.git
cd uptime-check
uv sync
```

## Usage

```sh
uv run uptime-check FILE [-c CONCURRENCY] [-t TIMEOUT]
```

`FILE` is a text file with one URL per line. Lines that are not valid `http`/`https` URLs
are reported on stderr and skipped.

| Option | Default | Meaning |
| --- | --- | --- |
| `-c`, `--concurrency` | `10` | Max requests in flight at once (at least 1) |
| `-t`, `--timeout` | `5.0` | Time limit per attempt, in seconds (above 0) |

### Example

Using the bundled `urls.txt`:

```console
$ uv run uptime-check urls.txt
skipped line 5: 'not a url': Input should be a valid URL, relative URL without a base
STATUS       MS  URL
200          71  https://example.com/
200        1112  https://www.python.org/
503         575  https://httpbin.org/status/503
ERR        5003  https://httpbin.org/delay/10  (TimeoutError)
2 up, 2 down
```

- `STATUS` is the HTTP status code, or `ERR` if no response came back (the error type is shown in brackets).
- `MS` is how long the last attempt took, in milliseconds.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | All URLs are up |
| `1` | At least one URL is down |
| `2` | The URL file could not be read |

This makes it easy to use in scripts or cron jobs:

```sh
uv run uptime-check urls.txt || echo "something is down"
```

## Project layout

```
src/uptime_check/
  cli.py       # argument parsing, reading the file, printing the table, exit codes
  checker.py   # concurrent HTTP checks with timeout and retry
  models.py    # Target (validated URL) and Result
tests/
  test_checker.py
  test_cli.py
urls.txt       # sample URL list
```

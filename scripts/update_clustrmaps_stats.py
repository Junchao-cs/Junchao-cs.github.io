#!/usr/bin/env python3

from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


PROFILE_URL = "https://clustrmaps.com/site/1c96n"
PROFILE_FETCH_URLS = [
    PROFILE_URL,
    "https://www.clustrmaps.com/site/1c96n",
    "http://clustrmaps.com/site/1c96n",
]
ROOT_PATH = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT_PATH / "data" / "clustrmaps-stats.json"
INDEX_PATH = ROOT_PATH / "index.html"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/135.0.0.0 Safari/537.36"
)


def fetch_text_with_curl(url: str) -> str:
    print(f"Fetching ClustrMaps with curl: {url}", file=sys.stderr)
    result = subprocess.run(
        [
            "curl",
            "--fail",
            "--ipv4",
            "--http1.1",
            "--tlsv1.2",
            "--location",
            "--silent",
            "--show-error",
            "--max-time",
            "30",
            "--retry",
            "3",
            "--retry-delay",
            "5",
            "--user-agent",
            USER_AGENT,
            "--header",
            "Accept-Language: en-US,en;q=0.9",
            url,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def fetch_text_with_urllib(url: str) -> str:
    print(f"Fetching ClustrMaps with urllib: {url}", file=sys.stderr)
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "ignore")


def fetch_text(url: str) -> str:
    try:
        return fetch_text_with_curl(url)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"curl fetch failed: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError):
            stderr = (error.stderr or "").strip()
            if stderr:
                print(stderr, file=sys.stderr)
        try:
            return fetch_text_with_urllib(url)
        except (OSError, URLError) as urllib_error:
            raise RuntimeError(
                "Could not fetch ClustrMaps stats from "
                f"{url}. ClustrMaps may be unreachable from this runner."
            ) from urllib_error


def extract(pattern: str, text: str, field_name: str) -> str:
    match = re.search(pattern, text, re.S)
    if not match:
        raise RuntimeError(f"Could not find {field_name} in {PROFILE_URL}")
    return match.group(1).strip()


def parse_stats(html: str, source_url: str) -> tuple[int, int, str]:
    total_pageviews = int(
        extract(
            r'class="pvTV total-pageviews odometer" data-value="(\d+)"',
            html,
            f"total pageviews from {source_url}",
        )
    )
    total_visits = int(
        extract(
            r'<strong data-count="(\d+)">\d+</strong>\s*total visits for:',
            html,
            f"total visits from {source_url}",
        )
    )
    since = extract(
        r'class="text-nowrap pvTT">Since ([^<]+)</span>',
        html,
        f"start date from {source_url}",
    )
    return total_pageviews, total_visits, since


def fetch_and_parse_stats() -> tuple[int, int, str]:
    errors = []
    for source_url in PROFILE_FETCH_URLS:
        try:
            return parse_stats(fetch_text(source_url), source_url)
        except Exception as error:
            errors.append(f"{source_url}: {error}")
            print(f"Failed to read ClustrMaps stats from {source_url}: {error}", file=sys.stderr)
    raise RuntimeError(
        "Could not read ClustrMaps stats from any known endpoint:\n"
        + "\n".join(errors)
    )


def replace_first(pattern: str, replacement: str, text: str, field_name: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"Could not update {field_name} in {INDEX_PATH}")
    return updated


def update_index_fallback(total_pageviews: int, since: str) -> None:
    html = INDEX_PATH.read_text(encoding="utf-8")
    html = replace_first(
        r'(<span class="visitor-stats-value" id="clustrmaps-total-pageviews">)[^<]*(</span>)',
        rf"\g<1>{total_pageviews:,}\2",
        html,
        "total pageviews fallback",
    )
    html = replace_first(
        r'(<span class="visitor-stats-meta" id="clustrmaps-total-since">)[^<]*(</span>)',
        rf"\g<1>Since {since}\2",
        html,
        "start date fallback",
    )
    INDEX_PATH.write_text(html, encoding="utf-8")


def main() -> None:
    total_pageviews, total_visits, since = fetch_and_parse_stats()

    payload = {
        "profileUrl": PROFILE_URL,
        "totalPageviews": total_pageviews,
        "totalVisits": total_visits,
        "since": since,
        "updatedAt": dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    update_index_fallback(total_pageviews, since)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen


PROFILE_URL = "https://clustrmaps.com/site/1c96n"
ROOT_PATH = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT_PATH / "data" / "clustrmaps-stats.json"
INDEX_PATH = ROOT_PATH / "index.html"


def fetch_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/135.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "ignore")


def extract(pattern: str, text: str, field_name: str) -> str:
    match = re.search(pattern, text, re.S)
    if not match:
        raise RuntimeError(f"Could not find {field_name} in {PROFILE_URL}")
    return match.group(1).strip()


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
    html = fetch_text(PROFILE_URL)

    total_pageviews = int(
        extract(
            r'class="pvTV total-pageviews odometer" data-value="(\d+)"',
            html,
            "total pageviews",
        )
    )
    total_visits = int(
        extract(
            r'<strong data-count="(\d+)">\d+</strong>\s*total visits for:',
            html,
            "total visits",
        )
    )
    since = extract(
        r'class="text-nowrap pvTT">Since ([^<]+)</span>',
        html,
        "start date",
    )

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

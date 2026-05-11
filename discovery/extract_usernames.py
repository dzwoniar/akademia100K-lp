"""Extract unique usernames from an Apify hashtag-scraper JSON dump.

Used between step 1 (hashtag scrape) and step 3 (profile scrape) of the
discovery pipeline — feed the output into the profile scraper's input list.

Usage:
    python -m discovery.extract_usernames --platform ig --in posts.json
    python -m discovery.extract_usernames --platform tt --in videos.json [--as-urls]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def extract_ig(items: list[dict]) -> list[str]:
    seen: set[str] = set()
    for it in items:
        u = (it.get("ownerUsername") or "").strip()
        if u:
            seen.add(u)
    return sorted(seen)


def extract_tt(items: list[dict]) -> list[str]:
    seen: set[str] = set()
    for it in items:
        author = it.get("authorMeta") or {}
        u = (author.get("name") or author.get("uniqueId") or "").strip()
        if u:
            seen.add(u)
    return sorted(seen)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--platform", choices=("ig", "tt"), required=True)
    ap.add_argument("--in", dest="src", type=Path, required=True)
    ap.add_argument("--as-urls", action="store_true", help="emit profile URLs instead of bare handles")
    args = ap.parse_args()

    with args.src.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and "items" in data:
        data = data["items"]

    handles = extract_ig(data) if args.platform == "ig" else extract_tt(data)

    if args.as_urls:
        prefix = "https://www.instagram.com/" if args.platform == "ig" else "https://www.tiktok.com/@"
        suffix = "/" if args.platform == "ig" else ""
        for h in handles:
            print(f"{prefix}{h}{suffix}")
    else:
        for h in handles:
            print(h)
    print(f"# {len(handles)} unique handles", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

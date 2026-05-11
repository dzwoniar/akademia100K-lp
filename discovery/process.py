"""Discovery PL Creators v1 — dedup + filter + export.

Reads Apify JSON exports (hashtag scraper + profile scraper) for IG and TT,
applies the PRD §4 filters, writes one XLSX per platform.

Usage:
    python -m discovery.process \\
        --ig-hashtag-posts ig_hashtag.json \\
        --ig-profiles ig_profiles.json \\
        --tt-hashtag-posts tt_hashtag.json \\
        --tt-profiles tt_profiles.json \\
        --out-dir ./out

Each --*-* flag is optional; the script processes whichever platform has both
inputs supplied.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from openpyxl import Workbook

from .config import (
    BIO_BLACKLIST_SUBSTRINGS,
    FOLLOWERS_MAX,
    FOLLOWERS_MIN,
    IG_HASHTAGS,
    MAX_ROWS_PER_PLATFORM,
    MIN_REELS_30D,
    PL_DIACRITICS,
    PL_STOPWORDS,
    PL_STOPWORDS_HITS_REQUIRED,
    TT_HASHTAGS,
    WINDOW_DAYS,
)

log = logging.getLogger("discovery")

XLSX_COLUMNS = [
    "Data scrape",
    "Nick wyświetlany",
    "Handle",
    "Link do profilu",
    "Platforma",
    "Followers",
    "Following",
    "Reels/Videos w 30d",
    "Bio (raw)",
    "Link do top postu",
    "Link do najnowszej rolki",
    "Avg views (ost. rolki)",
    "Writing Score (1–5)",
    "Hunger Score (1–5)",
    "Professionalism (1–5)",
    "Ocena końcowa (Z/Ż/C)",
    "Status",
    "Notatki",
]


@dataclass
class CreatorRow:
    handle: str
    display_name: str
    platform: str  # "IG" or "TT"
    followers: int
    following: int
    bio: str
    is_verified: bool
    reels_30d: int
    top_post_url: str
    latest_reel_url: str
    avg_views: float | None
    profile_url: str
    discovered_via_pl_hashtag: bool = False
    captions_blob: str = ""  # joined captions/texts from recent videos for PL detection
    reject_reasons: list[str] = field(default_factory=list)


# ---------- parsing ----------

def _load_json(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and "items" in data:
        data = data["items"]
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected list of items, got {type(data).__name__}")
    return data


def build_ig_hashtag_map(posts: list[dict]) -> dict[str, set[str]]:
    """username -> set of hashtags it was discovered through."""
    out: dict[str, set[str]] = defaultdict(set)
    seed = {h.lower() for h in IG_HASHTAGS}
    for post in posts:
        user = (post.get("ownerUsername") or "").strip().lower()
        if not user:
            continue
        # Apify IG hashtag scraper item includes the searched hashtag in one of
        # several keys depending on version. Fall back to caption parsing.
        hashtags: set[str] = set()
        for key in ("hashtag", "searchHashtag", "searchQuery"):
            v = post.get(key)
            if isinstance(v, str):
                hashtags.add(v.lstrip("#").lower())
        for tag in post.get("hashtags") or []:
            if isinstance(tag, str):
                hashtags.add(tag.lstrip("#").lower())
        caption = post.get("caption") or ""
        for token in caption.split():
            if token.startswith("#"):
                hashtags.add(token[1:].lower().rstrip(",.!?:;"))
        if hashtags & seed:
            out[user] |= hashtags & seed
    return out


def build_tt_hashtag_map(videos: list[dict]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    seed = {h.lower() for h in TT_HASHTAGS}
    for vid in videos:
        author = (vid.get("authorMeta") or {}).get("name") or vid.get("authorMeta", {}).get("uniqueId") or ""
        author = author.strip().lower()
        if not author:
            continue
        hashtags: set[str] = set()
        # clockworks/tiktok-scraper records the exact seed that pulled the
        # video in via `searchHashtag` — most reliable PL-trust signal.
        sh = vid.get("searchHashtag")
        if isinstance(sh, dict):
            sh = sh.get("name") or sh.get("hashtag")
        if isinstance(sh, str):
            hashtags.add(sh.lstrip("#").lower())
        inp = vid.get("input")
        if isinstance(inp, str):
            hashtags.add(inp.lstrip("#").lower())
        for tag in vid.get("hashtags") or []:
            name = tag.get("name") if isinstance(tag, dict) else tag
            if isinstance(name, str):
                hashtags.add(name.lstrip("#").lower())
        text = vid.get("text") or ""
        for token in text.split():
            if token.startswith("#"):
                hashtags.add(token[1:].lower().rstrip(",.!?:;"))
        if hashtags & seed:
            out[author] |= hashtags & seed
    return out


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # heuristic: ms vs s
        ts = value / 1000 if value > 1e12 else value
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def parse_ig_profile(profile: dict, pl_hashtag_users: dict[str, set[str]]) -> CreatorRow | None:
    handle = (profile.get("username") or "").strip()
    if not handle:
        return None
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=WINDOW_DAYS)

    posts = profile.get("latestPosts") or profile.get("posts") or []
    reels: list[dict] = []
    for p in posts:
        ptype = (p.get("type") or "").lower()
        product = (p.get("productType") or "").lower()
        if ptype == "video" or product in {"clips", "reel"}:
            ts = _parse_ts(p.get("timestamp") or p.get("takenAtTimestamp"))
            if ts and ts >= cutoff:
                reels.append({**p, "_ts": ts})

    if reels:
        top = max(reels, key=lambda r: r.get("videoViewCount") or r.get("videoPlayCount") or r.get("likesCount") or 0)
        latest = max(reels, key=lambda r: r["_ts"])
        views = [r.get("videoViewCount") or r.get("videoPlayCount") for r in reels]
        views = [v for v in views if isinstance(v, (int, float))]
        avg_views: float | None = sum(views) / len(views) if views else None
        top_url = top.get("url") or f"https://www.instagram.com/p/{top.get('shortCode', '')}/"
        latest_url = latest.get("url") or f"https://www.instagram.com/p/{latest.get('shortCode', '')}/"
    else:
        top_url = latest_url = ""
        avg_views = None

    return CreatorRow(
        handle=handle,
        display_name=profile.get("fullName") or handle,
        platform="IG",
        followers=int(profile.get("followersCount") or 0),
        following=int(profile.get("followsCount") or 0),
        bio=profile.get("biography") or "",
        is_verified=bool(profile.get("verified") or profile.get("isVerified")),
        reels_30d=len(reels),
        top_post_url=top_url,
        latest_reel_url=latest_url,
        avg_views=avg_views,
        profile_url=f"https://www.instagram.com/{handle}/",
        discovered_via_pl_hashtag=handle.lower() in pl_hashtag_users,
    )


def aggregate_tt_per_video(items: list[dict]) -> list[dict]:
    """clockworks/tiktok-scraper returns one item per video even when run
    against profile usernames. Group by author into pseudo-profile dicts so
    parse_tt_profile can consume them."""
    by_author: dict[str, dict] = {}
    for it in items:
        author = it.get("authorMeta") or {}
        name = (author.get("name") or author.get("uniqueId") or "").strip().lower()
        if not name:
            continue
        entry = by_author.get(name)
        if entry is None:
            entry = {"authorMeta": author, "posts": []}
            by_author[name] = entry
        entry["posts"].append(it)
    return list(by_author.values())


def parse_tt_profile(profile: dict, pl_hashtag_users: dict[str, set[str]]) -> CreatorRow | None:
    # Apify TT profile scraper nests author info under various keys depending on actor
    author = profile.get("authorMeta") or profile.get("user") or profile
    handle = (author.get("name") or author.get("uniqueId") or profile.get("username") or "").strip()
    if not handle:
        return None
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=WINDOW_DAYS)

    posts = profile.get("posts") or profile.get("videos") or profile.get("latestPosts") or []
    recent: list[dict] = []
    for p in posts:
        ts = _parse_ts(p.get("createTime") or p.get("createTimeISO") or p.get("timestamp"))
        if ts and ts >= cutoff:
            recent.append({**p, "_ts": ts})

    # Captions blob — aggregate text from ALL fetched videos (not just recent)
    # so we have language signal even for less-active creators.
    captions_blob = " ".join((p.get("text") or "") for p in posts)[:8000]

    if recent:
        top = max(recent, key=lambda r: r.get("playCount") or r.get("views") or 0)
        latest = max(recent, key=lambda r: r["_ts"])
        views = [r.get("playCount") or r.get("views") for r in recent]
        views = [v for v in views if isinstance(v, (int, float))]
        avg_views: float | None = sum(views) / len(views) if views else None
        top_url = top.get("webVideoUrl") or top.get("url") or ""
        latest_url = latest.get("webVideoUrl") or latest.get("url") or ""
    else:
        top_url = latest_url = ""
        avg_views = None

    followers = author.get("fans") or author.get("followerCount") or profile.get("fans") or 0
    following = author.get("following") or author.get("followingCount") or profile.get("following") or 0
    bio = author.get("signature") or profile.get("signature") or profile.get("bio") or ""
    verified = bool(author.get("verified") or profile.get("verified"))
    nickname = author.get("nickName") or author.get("nickname") or handle

    return CreatorRow(
        handle=handle,
        display_name=nickname,
        platform="TT",
        followers=int(followers),
        following=int(following),
        bio=bio,
        is_verified=verified,
        reels_30d=len(recent),
        top_post_url=top_url,
        latest_reel_url=latest_url,
        avg_views=avg_views,
        profile_url=f"https://www.tiktok.com/@{handle}",
        discovered_via_pl_hashtag=handle.lower() in pl_hashtag_users,
        captions_blob=captions_blob,
    )


# ---------- filters ----------

def looks_polish(bio: str) -> bool:
    if not bio:
        return False
    if any(ch in PL_DIACRITICS for ch in bio):
        return True
    tokens = {t.strip(".,!?:;()[]\"'").lower() for t in bio.split()}
    return len(tokens & PL_STOPWORDS) >= PL_STOPWORDS_HITS_REQUIRED


def bio_has_blacklist(bio: str) -> bool:
    low = (bio or "").lower()
    return any(needle in low for needle in BIO_BLACKLIST_SUBSTRINGS)


def apply_filters(row: CreatorRow) -> bool:
    """Mutates row.reject_reasons; returns True if row passes."""
    if not (FOLLOWERS_MIN <= row.followers <= FOLLOWERS_MAX):
        row.reject_reasons.append(f"followers={row.followers}")
    if row.reels_30d < MIN_REELS_30D:
        row.reject_reasons.append(f"reels_30d={row.reels_30d}")
    # PL detection — bio is the strongest signal. For TT the bio is often empty
    # or in English; fall back to video captions where the creator's actual
    # content language shows up. IG falls back to PL-hashtag discovery (their
    # captions aren't enriched by the profile scraper).
    pl_signal = looks_polish(row.bio) or looks_polish(row.captions_blob)
    if row.platform == "IG":
        pl_signal = pl_signal or row.discovered_via_pl_hashtag
    if not pl_signal:
        row.reject_reasons.append("not_pl")
    if row.is_verified:
        row.reject_reasons.append("verified")
    if bio_has_blacklist(row.bio):
        row.reject_reasons.append("bio_blacklist")
    return not row.reject_reasons


# ---------- export ----------

def write_xlsx(rows: list[CreatorRow], path: Path, scrape_date: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "discovery"
    ws.append(XLSX_COLUMNS)
    for r in rows:
        ws.append([
            scrape_date,
            r.display_name,
            r.handle,
            r.profile_url,
            r.platform,
            r.followers,
            r.following,
            r.reels_30d,
            r.bio,
            r.top_post_url,
            r.latest_reel_url,
            round(r.avg_views) if r.avg_views is not None else "",
            "",  # writing
            "",  # hunger
            "",  # professionalism
            "",  # ocena
            "nowy",
            "",  # notatki
        ])
    wb.save(path)


# ---------- pipeline ----------

def process_platform(
    platform: str,
    hashtag_posts: list[dict],
    profiles: list[dict],
    parse_profile,
    build_hashtag_map,
) -> tuple[list[CreatorRow], list[CreatorRow]]:
    pl_users = build_hashtag_map(hashtag_posts)
    log.info("%s: %d posts -> %d users on PL hashtags", platform, len(hashtag_posts), len(pl_users))

    seen: set[str] = set()
    rows: list[CreatorRow] = []
    for p in profiles:
        row = parse_profile(p, pl_users)
        if row is None:
            continue
        key = row.handle.lower()
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)

    log.info("%s: %d unique profiles parsed", platform, len(rows))

    passed: list[CreatorRow] = []
    rejected: list[CreatorRow] = []
    for r in rows:
        (passed if apply_filters(r) else rejected).append(r)

    passed.sort(key=lambda r: r.reels_30d, reverse=True)
    if len(passed) > MAX_ROWS_PER_PLATFORM:
        log.info("%s: capping %d -> %d", platform, len(passed), MAX_ROWS_PER_PLATFORM)
        passed = passed[:MAX_ROWS_PER_PLATFORM]
    return passed, rejected


def main(argv: Iterable[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ig-hashtag-posts", type=Path)
    ap.add_argument("--ig-profiles", type=Path)
    ap.add_argument("--tt-hashtag-posts", type=Path)
    ap.add_argument("--tt-profiles", type=Path)
    ap.add_argument("--out-dir", type=Path, default=Path("./out"))
    args = ap.parse_args(list(argv) if argv is not None else None)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    summary: list[str] = []

    if args.ig_hashtag_posts and args.ig_profiles:
        passed, rejected = process_platform(
            "IG",
            _load_json(args.ig_hashtag_posts),
            _load_json(args.ig_profiles),
            parse_ig_profile,
            build_ig_hashtag_map,
        )
        out = args.out_dir / f"discovery_ig_v1_{today}.xlsx"
        write_xlsx(passed, out, today)
        summary.append(f"IG: {len(passed)} passed / {len(rejected)} rejected -> {out}")
    elif args.ig_hashtag_posts or args.ig_profiles:
        log.warning("IG: need both --ig-hashtag-posts and --ig-profiles, skipping")

    if args.tt_hashtag_posts and args.tt_profiles:
        tt_profile_items = _load_json(args.tt_profiles)
        if tt_profile_items and "posts" not in tt_profile_items[0] and "videos" not in tt_profile_items[0]:
            log.info("TT: detected per-video shape, aggregating by author")
            tt_profile_items = aggregate_tt_per_video(tt_profile_items)
        passed, rejected = process_platform(
            "TT",
            _load_json(args.tt_hashtag_posts),
            tt_profile_items,
            parse_tt_profile,
            build_tt_hashtag_map,
        )
        out = args.out_dir / f"discovery_tt_v1_{today}.xlsx"
        write_xlsx(passed, out, today)
        summary.append(f"TT: {len(passed)} passed / {len(rejected)} rejected -> {out}")
    elif args.tt_hashtag_posts or args.tt_profiles:
        log.warning("TT: need both --tt-hashtag-posts and --tt-profiles, skipping")

    if not summary:
        log.error("nothing to process; pass at least one platform's pair of inputs")
        return 2
    for line in summary:
        log.info(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())

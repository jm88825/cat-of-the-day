#!/usr/bin/env python3
"""Cat of the Day picker (Python 3.9+, standard library only).

Finds today's most viral cat post on Reddit and writes:
  data/latest.json   - today's pick
  data/archive.json  - newest first, last 60 days (one entry per date)

Source order (first one that yields usable posts wins):
  1. Reddit JSON listing on www.reddit.com, old.reddit.com, api.reddit.com
     (has real upvote scores; ranked by score)
  2. Reddit Atom/RSS feed (.rss) on www.reddit.com / old.reddit.com
     (no score in the feed; Reddit's own "top of the day" order is used as the
     ranking and `score` is written as null — never guessed)

Alternative: record a pick chosen elsewhere (e.g. an X post) with
  python3 pick_cat.py --from-json pick.json

Nothing is ever fabricated: if every source fails the script exits non-zero and
leaves the existing data files untouched.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SUBREDDITS = ["cats", "catpictures", "catvideos", "Catswithjobs",
              "CatsAreAssholes", "catsstandingup", "aww"]
# Subreddits whose posts must mention a cat in the title to count.
TITLE_FILTERED = {"aww"}
CAT_WORDS = re.compile(r"\b(cats?|kittens?|kitty|kitties|kitten's|cat's)\b", re.I)

USER_AGENT = os.environ.get(
    "CATOTD_USER_AGENT",
    "cat-of-the-day/1.0 (daily cat picker; +https://github.com/catoftheday)")
ARCHIVE_DAYS = 60
TIMEOUT = 20

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_DIR = os.path.join(HERE, "data")

ATOM = "{http://www.w3.org/2005/Atom}"
MEDIA = "{http://search.yahoo.com/mrss/}"


def log(msg: str) -> None:
    print(f"[pick_cat] {msg}", file=sys.stderr)


def today_et() -> str:
    """Date in America/New_York (the app's 'day'); falls back to UTC."""
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:  # tzdata missing
        return dt.datetime.now(dt.timezone.utc).date().isoformat()


def http_get(url: str, *, max_bytes: int | None = None,
             headers: dict | None = None,
             retries: int = 0) -> tuple[int, str, bytes]:
    h = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                body = r.read(max_bytes) if max_bytes else r.read()
                return r.status, r.geturl(), body
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                try:
                    wait = min(int(e.headers.get("Retry-After", "")), 60)
                except ValueError:
                    wait = 15 * (attempt + 1)
                log(f"HTTP 429 (rate limited) on {url[:70]}... retrying in {wait}s")
                time.sleep(wait)
                continue
            return e.code, url, e.read(2000) if hasattr(e, "read") else b""
    return 0, url, b""


# --------------------------------------------------------------------------
# Media helpers
# --------------------------------------------------------------------------

def image_size(data: bytes) -> tuple[int, int] | None:
    """Parse width/height from the first bytes of a PNG/GIF/JPEG/WebP."""
    try:
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            w, h = struct.unpack(">II", data[16:24])
            return w, h
        if data[:6] in (b"GIF87a", b"GIF89a"):
            w, h = struct.unpack("<HH", data[6:10])
            return w, h
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            chunk = data[12:16]
            if chunk == b"VP8X":
                w = int.from_bytes(data[24:27], "little") + 1
                h = int.from_bytes(data[27:30], "little") + 1
                return w, h
            if chunk == b"VP8 ":
                w, h = struct.unpack("<HH", data[26:30])
                return w & 0x3FFF, h & 0x3FFF
            if chunk == b"VP8L":
                b = data[21:25]
                w = 1 + (((b[1] & 0x3F) << 8) | b[0])
                h = 1 + (((b[3] & 0xF) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))
                return w, h
        if data[:2] == b"\xff\xd8":
            i = 2
            while i < len(data) - 9:
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                    i += 2
                    continue
                seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                              0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    h, w = struct.unpack(">HH", data[i + 5:i + 9])
                    return w, h
                i += 2 + seg_len
    except Exception:
        pass
    return None


def probe_image(url: str) -> dict:
    """Confirm an image URL is reachable and read its dimensions."""
    status, _, body = http_get(url, max_bytes=256 * 1024,
                               headers={"Range": "bytes=0-262143"})
    if status not in (200, 206):
        return {"ok": False}
    size = image_size(body)
    out = {"ok": True}
    if size:
        out["width"], out["height"] = size
    return out


def vreddit_info(vid_url: str) -> dict | None:
    """Resolve a v.redd.it link to a direct MP4 via its DASH manifest.

    The JSON API exposes `fallback_url`; the manifest lists the same
    progressive MP4 renditions (DASH_720.mp4 / CMAF_720.mp4). These files are
    video-only — Reddit serves audio as a separate track — so `hasAudio`
    tells the app whether the DASH manifest (Android can play it) has sound.
    """
    m = re.match(r"https?://v\.redd\.it/([A-Za-z0-9]+)", vid_url)
    if not m:
        return None
    base = f"https://v.redd.it/{m.group(1)}"
    status, _, body = http_get(base + "/DASHPlaylist.mpd")
    if status != 200:
        return None
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return None
    ns = {"d": "urn:mpeg:dash:schema:mpd:2011"}
    best = None
    has_audio = False
    for aset in root.iter("{urn:mpeg:dash:schema:mpd:2011}AdaptationSet"):
        ctype = aset.get("contentType", "")
        for rep in aset.findall("d:Representation", ns):
            mime = rep.get("mimeType", aset.get("mimeType", ""))
            if ctype == "audio" or mime.startswith("audio"):
                has_audio = True
                continue
            h = int(rep.get("height", 0) or 0)
            w = int(rep.get("width", 0) or 0)
            url_el = rep.find("d:BaseURL", ns)
            if url_el is None or not url_el.text:
                continue
            # Prefer the largest rendition up to 1080p (phone-friendly).
            if min(w, h) <= 1080 and (best is None or h * w > best[0] * best[1]):
                best = (w, h, url_el.text.strip())
    if not best:
        return None
    w, h, name = best
    return {
        "mediaUrl": f"{base}/{name}",
        "dashUrl": f"{base}/DASHPlaylist.mpd",
        "hasAudio": has_audio,
        "width": w,
        "height": h,
    }


def classify_media(url: str, reddit_video: dict | None = None,
                   preview_img: str | None = None) -> dict | None:
    """Return media fields for image/gif/video URLs we support, else None."""
    if not url:
        return None
    url = html.unescape(url)
    p = urllib.parse.urlparse(url)
    host = p.netloc.lower()
    path = p.path.lower()

    if host == "v.redd.it":
        info = None
        if reddit_video and reddit_video.get("fallback_url"):
            info = {
                "mediaUrl": reddit_video["fallback_url"],
                "dashUrl": reddit_video.get("dash_url"),
                "hasAudio": None,  # unknown from JSON alone; checked below
                "width": reddit_video.get("width"),
                "height": reddit_video.get("height"),
            }
            mpd = vreddit_info(url)
            if mpd:
                info["hasAudio"] = mpd["hasAudio"]
                info["dashUrl"] = info["dashUrl"] or mpd["dashUrl"]
        else:
            info = vreddit_info(url)
        if not info:
            return None
        info["mediaType"] = "video"
        return info

    if host == "i.redd.it" or host.endswith("imgur.com"):
        if host.endswith("imgur.com"):
            if path.endswith((".gifv", ".mp4")):
                mp4 = re.sub(r"\.(gifv|mp4)$", ".mp4", url.split("?")[0])
                mp4 = mp4.replace("://imgur.com", "://i.imgur.com")
                st, _, _ = http_get(mp4, max_bytes=1024,
                                    headers={"Range": "bytes=0-1023"})
                if st not in (200, 206):
                    return None
                return {"mediaType": "video", "mediaUrl": mp4, "hasAudio": None}
            if not re.search(r"\.(jpe?g|png|gif|webp)$", path):
                # imgur.com/abc (single image page) -> try the direct file
                if "/a/" in path or "/gallery/" in path:
                    return None
                url = f"https://i.imgur.com{p.path}.jpg"
                path = url.lower()
        if not re.search(r"\.(jpe?g|png|gif|webp)$", urllib.parse.urlparse(url).path.lower()):
            return None
        probe = probe_image(url)
        if not probe["ok"]:
            return None
        out = {"mediaType": "gif" if path.endswith(".gif") else "image",
               "mediaUrl": url}
        if "width" in probe:
            out["width"], out["height"] = probe["width"], probe["height"]
        return out
    return None


def is_cat_post(subreddit: str, title: str) -> bool:
    if subreddit.lower() in {s.lower() for s in TITLE_FILTERED}:
        return bool(CAT_WORDS.search(title or ""))
    return True


# --------------------------------------------------------------------------
# Source 1: Reddit JSON
# --------------------------------------------------------------------------

def fetch_reddit_json(period: str = "day") -> tuple[list[dict], str] | None:
    multi = "+".join(SUBREDDITS)
    urls = [
        f"https://www.reddit.com/r/{multi}/top.json?t={period}&limit=100&raw_json=1",
        f"https://old.reddit.com/r/{multi}/top.json?t={period}&limit=100&raw_json=1",
        f"https://api.reddit.com/r/{multi}/top?t={period}&limit=100&raw_json=1",
    ]
    for url in urls:
        try:
            status, final, body = http_get(url)
        except Exception as e:
            log(f"JSON {url} -> error {e}")
            continue
        if status != 200 or "/login" in final:
            log(f"JSON {url} -> HTTP {status} ({final[:60]})")
            continue
        try:
            data = json.loads(body)
            children = data["data"]["children"]
        except Exception:
            log(f"JSON {url} -> not a listing (blocked page?)")
            continue
        posts = []
        for c in children:
            d = c.get("data", {})
            if d.get("over_18") or d.get("stickied"):
                continue
            posts.append({
                "id": d.get("id"),
                "title": d.get("title", ""),
                "subreddit": d.get("subreddit", ""),
                "author": d.get("author", ""),
                "score": d.get("score"),
                "permalink": "https://www.reddit.com" + d.get("permalink", ""),
                "url": d.get("url_overridden_by_dest") or d.get("url", ""),
                "reddit_video": ((d.get("secure_media") or d.get("media") or {})
                                 .get("reddit_video")),
                "thumbnail": _json_thumb(d),
                "created_utc": d.get("created_utc"),
                "is_gallery": bool(d.get("is_gallery")),
            })
        log(f"JSON {url} -> {len(posts)} SFW posts")
        return posts, "reddit-json"
    return None


def _json_thumb(d: dict) -> str | None:
    try:
        res = d["preview"]["images"][0]["resolutions"]
        pick = next((r for r in res if r.get("width", 0) >= 320), res[-1])
        return pick["url"]
    except Exception:
        t = d.get("thumbnail")
        return t if t and t.startswith("http") else None


# --------------------------------------------------------------------------
# Source 2: Reddit RSS / Atom
# --------------------------------------------------------------------------

def fetch_reddit_rss(period: str = "day") -> tuple[list[dict], str] | None:
    multi = "+".join(SUBREDDITS)
    urls = [
        f"https://www.reddit.com/r/{multi}/top/.rss?t={period}&limit=100",
        f"https://old.reddit.com/r/{multi}/top/.rss?t={period}&limit=100",
    ]
    for url in urls:
        try:
            status, final, body = http_get(url, retries=2)
        except Exception as e:
            log(f"RSS {url} -> error {e}")
            continue
        if status != 200 or "/login" in final:
            log(f"RSS {url} -> HTTP {status} ({final[:60]})")
            continue
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            log(f"RSS {url} -> not XML (blocked page?)")
            continue
        posts = []
        for rank, e in enumerate(root.findall(f"{ATOM}entry"), start=1):
            content = html.unescape(e.findtext(f"{ATOM}content") or "")
            title = html.unescape(e.findtext(f"{ATOM}title") or "")
            cat = e.find(f"{ATOM}category")
            sub = cat.get("term") if cat is not None else ""
            author = (e.findtext(f"{ATOM}author/{ATOM}name") or "").replace("/u/", "")
            link_el = e.find(f"{ATOM}link")
            permalink = link_el.get("href") if link_el is not None else ""
            m = re.search(r'<a href="([^"]+)">\[link\]</a>', content)
            thumb_el = e.find(f"{MEDIA}thumbnail")
            thumb = thumb_el.get("url") if thumb_el is not None else None
            # The feed has no over_18 flag; Reddit marks NSFW thumbnails.
            nsfw = ("nsfw" in (thumb or "").lower()
                    or re.search(r"\bnsfw\b", title, re.I) is not None)
            if nsfw:
                continue
            posts.append({
                "id": (e.findtext(f"{ATOM}id") or "").replace("t3_", ""),
                "title": title,
                "subreddit": sub,
                "author": author,
                "score": None,          # not exposed by the feed
                "rank": rank,           # Reddit's top-of-day order
                "permalink": permalink,
                "url": m.group(1) if m else "",
                "reddit_video": None,
                "thumbnail": html.unescape(thumb) if thumb else None,
                "published": e.findtext(f"{ATOM}published"),
                "is_gallery": "/gallery/" in (m.group(1) if m else ""),
            })
        log(f"RSS {url} -> {len(posts)} entries")
        if posts:
            return posts, "reddit-rss"
    return None


# --------------------------------------------------------------------------
# Picking
# --------------------------------------------------------------------------

def choose(posts: list[dict], source: str, exclude: set[str]) -> dict | None:
    if source == "reddit-json":
        ordered = sorted(posts, key=lambda p: p.get("score") or 0, reverse=True)
    else:
        ordered = sorted(posts, key=lambda p: p.get("rank", 10 ** 6))
    for p in ordered:
        if p["permalink"] in exclude:
            continue
        if p.get("is_gallery"):
            continue
        if not is_cat_post(p["subreddit"], p["title"]):
            continue
        media = classify_media(p["url"], p.get("reddit_video"))
        if not media:
            continue
        pick = {
            "title": p["title"],
            "subreddit": p["subreddit"],
            "author": p["author"],
            "score": p.get("score"),
            "permalink": p["permalink"],
            "mediaType": media["mediaType"],
            "mediaUrl": media["mediaUrl"],
            "width": media.get("width"),
            "height": media.get("height"),
            "thumbnail": p.get("thumbnail"),
        }
        if media["mediaType"] == "video":
            pick["dashUrl"] = media.get("dashUrl")
            pick["hasAudio"] = media.get("hasAudio")
            pick["mp4HasAudio"] = False if "redd.it" in media["mediaUrl"] else None
        if source == "reddit-rss":
            pick["rank"] = p.get("rank")
        return pick
    return None


def load_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: str, obj) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def save(pick: dict, data_dir: str) -> None:
    os.makedirs(data_dir, exist_ok=True)
    archive_path = os.path.join(data_dir, "archive.json")
    archive = load_json(archive_path, {"days": []})
    days = [d for d in archive.get("days", []) if d.get("date") != pick["date"]]
    days.insert(0, pick)
    days.sort(key=lambda d: d["date"], reverse=True)
    cutoff = (dt.date.fromisoformat(pick["date"])
              - dt.timedelta(days=ARCHIVE_DAYS - 1)).isoformat()
    days = [d for d in days if d["date"] >= cutoff][:ARCHIVE_DAYS]
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    write_json(os.path.join(data_dir, "latest.json"), pick)
    write_json(archive_path, {"updatedAt": now, "days": days})
    log(f"wrote {data_dir}/latest.json and archive.json ({len(days)} days)")


REQUIRED_IMPORT = ["title", "author", "permalink", "mediaType", "mediaUrl"]


def import_pick(path: str, date: str) -> dict:
    """Import a manually chosen pick (e.g. an X post) from a JSON file."""
    raw = load_json(path, None)
    if not isinstance(raw, dict):
        raise SystemExit(f"{path}: expected a JSON object")
    missing = [k for k in REQUIRED_IMPORT if not raw.get(k)]
    if missing:
        raise SystemExit(f"{path}: missing required fields: {', '.join(missing)}")
    if raw["mediaType"] not in ("image", "gif", "video"):
        raise SystemExit(f"{path}: mediaType must be image, gif or video")
    for k in ("permalink", "mediaUrl"):
        if not str(raw[k]).startswith("https://"):
            raise SystemExit(f"{path}: {k} must be an https:// URL")
    source = raw.get("source") or ("x" if re.search(r"//(x|twitter)\.com/", raw["permalink"]) else "manual")
    pick = {
        "date": raw.get("date") or date,
        "title": raw["title"],
        "subreddit": raw.get("subreddit"),   # null for non-Reddit posts
        "author": str(raw["author"]).lstrip("@").replace("u/", "", 1),
        "score": raw.get("score"),           # e.g. likes on X; null if unknown
        "scoreLabel": raw.get("scoreLabel") or ("likes" if source == "x" else "upvotes"),
        "permalink": raw["permalink"],
        "mediaType": raw["mediaType"],
        "mediaUrl": raw["mediaUrl"],
        "width": raw.get("width"),
        "height": raw.get("height"),
        "thumbnail": raw.get("thumbnail"),
        "source": source,
        "pickedAt": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
    }
    return pick


def post_date_et(p: dict) -> str | None:
    """Calendar date (America/New_York) a post was published."""
    try:
        if p.get("created_utc"):
            t = dt.datetime.fromtimestamp(float(p["created_utc"]), dt.timezone.utc)
        elif p.get("published"):
            t = dt.datetime.fromisoformat(p["published"])
        else:
            return None
        try:
            from zoneinfo import ZoneInfo
            t = t.astimezone(ZoneInfo("America/New_York"))
        except Exception:
            pass
        return t.date().isoformat()
    except Exception:
        return None


def backfill(days: int, data_dir: str, today: str) -> int:
    """Fill empty past dates with the top post *published* on that date.

    Uses Reddit's top-of-week / top-of-month listing, so the ranking reflects
    scores as of now, not as of that day. Entries are marked "backfilled": true.
    """
    period = "week" if days <= 7 else "month"
    archive = load_json(os.path.join(data_dir, "archive.json"), {"days": []})
    have = {d["date"] for d in archive.get("days", [])}
    used = {d.get("permalink") for d in archive.get("days", [])}
    start = dt.date.fromisoformat(today)
    wanted = [(start - dt.timedelta(days=i)).isoformat() for i in range(1, days + 1)]
    wanted = [d for d in wanted if d not in have]
    if not wanted:
        log("backfill: nothing to do")
        return 0
    got = fetch_reddit_json(period) or fetch_reddit_rss(period)
    if not got:
        log("backfill: no data source worked")
        return 2
    posts, source = got
    by_date: dict[str, list[dict]] = {}
    for p in posts:
        d = post_date_et(p)
        if d in wanted:
            by_date.setdefault(d, []).append(p)
    added = []
    for d in wanted:
        cands = by_date.get(d, [])
        if source == "reddit-rss":  # keep listing order as the per-day rank
            for i, c in enumerate(sorted(cands, key=lambda c: c["rank"]), start=1):
                c["rank"] = i
        pick = choose(cands, source, used)
        if not pick:
            log(f"backfill: no usable post published on {d}")
            continue
        used.add(pick["permalink"])
        added.append({"date": d, **pick, "source": source, "scoreLabel": "upvotes",
                      "backfilled": True,
                      "pickedAt": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()})
    if not added:
        return 2
    days_list = archive.get("days", []) + added
    days_list.sort(key=lambda x: x["date"], reverse=True)
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    write_json(os.path.join(data_dir, "archive.json"),
               {"updatedAt": now, "days": days_list[:ARCHIVE_DAYS]})
    for a in added:
        log(f"backfill: {a['date']} -> r/{a['subreddit']} \"{a['title'][:50]}\" ({a['mediaType']})")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    ap.add_argument("--date", default=None, help="override date (YYYY-MM-DD, default: today in ET)")
    ap.add_argument("--from-json", metavar="PICK_JSON",
                    help="record this pick (e.g. an X post) instead of querying Reddit")
    ap.add_argument("--backfill", type=int, metavar="N",
                    help="also fill up to N empty past days (max 30) from Reddit's top-of-week/month")
    ap.add_argument("--dry-run", action="store_true", help="print pick, do not write files")
    ap.add_argument("--force", action="store_true",
                    help="re-pick even if today already has a pick")
    args = ap.parse_args(argv)
    date = args.date or today_et()

    if args.from_json:
        pick = import_pick(args.from_json, date)
        print(json.dumps(pick, indent=2, ensure_ascii=False))
        if not args.dry_run:
            save(pick, args.data_dir)
        return 0

    latest = load_json(os.path.join(args.data_dir, "latest.json"), {})
    if latest.get("date") == date and latest.get("source") in ("x", "manual") and not args.force:
        log(f"{date} already has a manual pick; keeping it (use --force to override)")
        return 0

    archive = load_json(os.path.join(args.data_dir, "archive.json"), {"days": []})
    # Don't repeat a post that already won a previous day.
    exclude = {d.get("permalink") for d in archive.get("days", []) if d.get("date") != date}

    if args.backfill:
        return backfill(min(args.backfill, 30), args.data_dir, date)

    errors = []
    for fetch in (fetch_reddit_json, fetch_reddit_rss):
        try:
            got = fetch()
        except Exception as e:  # network problems etc.
            errors.append(f"{fetch.__name__}: {e}")
            continue
        if not got:
            errors.append(f"{fetch.__name__}: no usable response")
            continue
        posts, source = got
        pick = choose(posts, source, exclude)
        if not pick:
            errors.append(f"{source}: no post with supported media")
            continue
        pick = {"date": date, **pick, "source": source,
                "scoreLabel": "upvotes",
                "pickedAt": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()}
        print(json.dumps(pick, indent=2, ensure_ascii=False))
        if not args.dry_run:
            save(pick, args.data_dir)
        return 0

    log("FAILED: no data source worked. Existing data left untouched.")
    for e in errors:
        log("  " + e)
    return 2


if __name__ == "__main__":
    sys.exit(main())

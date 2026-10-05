#!/usr/bin/env python3
"""Cat of the Day picker (Python 3.9+, standard library only).

Picks a random "hidden gem" cat post from a broad pool of Reddit cat
subreddits (today's top ~100, skipping the top 3 already-famous posts) and writes:
  data/latest.json   - today's pick
  data/archive.json  - newest first, last 60 days (one entry per date)

Source order (first one that yields usable posts wins):
  1. Reddit JSON listing on www.reddit.com, old.reddit.com, api.reddit.com
     (has real upvote scores; ranked by score)
  2. Reddit Atom/RSS feed (.rss) on www.reddit.com / old.reddit.com
     (no score in the feed; Reddit's own "top of the day" order is used as the
     ranking and `score` is written as null — never guessed)

Alternative: record a pick chosen elsewhere (e.g. an X post) with
  python3 pick_cat.py --from-json pick.json        (see X_PICK.md)
Add/replace the short blurb on today's entry with
  python3 pick_cat.py --set-blurb "Two sentences about the cat."

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
import shutil
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import random
import xml.etree.ElementTree as ET

# One multireddit RSS request covers all of these (checked 2026-10-02: every
# one resolves; small subs only contribute a few posts per day).
SUBREDDITS = ["cats", "catpictures", "catvideos", "Catswithjobs",
              "CatsAreAssholes", "catsstandingup", "aww", "StartledCats",
              "catbellies", "SupermodelCats", "catsareliquid", "blackcats",
              "IllegallySmolCats", "Catloaf", "CatsInSinks", "TuxedoCats",
              "OneOrangeBraincell"]
# Subreddits whose posts must mention a cat in the title to count.
TITLE_FILTERED = {"aww"}
CAT_WORDS = re.compile(r"\b(cats?|kittens?|kitty|kitties|kitten's|cat's)\b", re.I)

# Random "hidden gem" selection (see choose_random()).
SKIP_TOP = 3          # the top N of the day are the already-discovered ones
POOL_SIZE = 60        # consider at most this many ranked candidates after the skip
SAME_SUB_PENALTY = 0.15   # weight multiplier for yesterday's subreddit (only
                          # matters when fewer than 3 posts from other subs exist)
MAX_MEDIA_TRIES = 15  # media probes per run (each costs an HTTP request or two)

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


def hls_audio(base: str) -> tuple[str | None, bool]:
    """Return (hlsUrl, has_audio) for a v.redd.it video, checking the master playlist.

    The HLS master lists separate audio renditions (EXT-X-MEDIA TYPE=AUDIO) and
    mp4a codecs when the clip has sound. ExoPlayer (Android) and AVPlayer (iOS)
    both play it with audio.
    """
    url = f"{base}/HLSPlaylist.m3u8"
    status, _, body = http_get(url, retries=1)
    text = body.decode("utf-8", "replace") if body else ""
    if status != 200 or not text.startswith("#EXTM3U"):
        return None, False
    has_audio = ("TYPE=AUDIO" in text) or ("mp4a" in text)
    return url, has_audio


QUIET_MEAN_DB = -45.0  # below this the track is practically inaudible on a phone


def audio_loudness(url: str, seconds: int = 30) -> tuple[float | None, float | None]:
    """Optional: mean/max volume (dB) of the first audio track via ffmpeg.

    Only runs if ffmpeg is installed; returns (None, None) otherwise.
    """
    if not shutil.which("ffmpeg"):
        return None, None
    try:
        r = subprocess.run(
            ["ffmpeg", "-nostats", "-hide_banner", "-user_agent", USER_AGENT, "-i", url,
             "-map", "0:a:0", "-t", str(seconds), "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True, timeout=90)
    except Exception as e:
        log(f"ffmpeg loudness check failed: {e}")
        return None, None
    mean = re.search(r"mean_volume: (-?[\d.]+) dB", r.stderr)
    peak = re.search(r"max_volume: (-?[\d.]+) dB", r.stderr)
    return (float(mean.group(1)) if mean else None, float(peak.group(1)) if peak else None)


def vreddit_info(vid_url: str) -> dict | None:
    """Resolve a v.redd.it link to playable sources.

    - mediaUrl: progressive MP4 (the JSON API's `fallback_url` / CMAF_720.mp4).
      **Video-only**: Reddit keeps audio in a separate track, so this file is
      always silent. It's used as the last fallback and for the web build.
    - hlsUrl:   HLSPlaylist.m3u8 (video + audio). The app prefers it on native.
    - dashUrl:  DASHPlaylist.mpd (video + audio). Android-only fallback.
    - hasAudio: True only if a stream we store actually lists an audio track.
    """
    m = re.match(r"https?://v\.redd\.it/([A-Za-z0-9]+)", vid_url)
    if not m:
        return None
    base = f"https://v.redd.it/{m.group(1)}"
    status, _, body = http_get(base + "/DASHPlaylist.mpd", retries=1)
    best = None
    dash_audio = False
    dash_url = None
    if status == 200:
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            root = None
        if root is not None:
            dash_url = f"{base}/DASHPlaylist.mpd"
            ns = {"d": "urn:mpeg:dash:schema:mpd:2011"}
            for aset in root.iter("{urn:mpeg:dash:schema:mpd:2011}AdaptationSet"):
                ctype = aset.get("contentType", "")
                for rep in aset.findall("d:Representation", ns):
                    mime = rep.get("mimeType", aset.get("mimeType", ""))
                    if ctype == "audio" or mime.startswith("audio"):
                        dash_audio = True
                        continue
                    h = int(rep.get("height", 0) or 0)
                    w = int(rep.get("width", 0) or 0)
                    url_el = rep.find("d:BaseURL", ns)
                    if url_el is None or not url_el.text:
                        continue
                    # Prefer the largest rendition up to 1080p (phone-friendly).
                    if min(w, h) <= 1080 and (best is None or h * w > best[0] * best[1]):
                        best = (w, h, url_el.text.strip())
    hls_url, hls_has_audio = hls_audio(base)
    if not best and not hls_url:
        return None
    out = {
        "hlsUrl": hls_url,
        "dashUrl": dash_url,
        "hasAudio": bool(hls_has_audio or dash_audio),
        "hlsHasAudio": hls_has_audio if hls_url else None,
        "dashHasAudio": dash_audio if dash_url else None,
        "mp4HasAudio": False,
    }
    audio_src = hls_url if hls_has_audio else (dash_url if dash_audio else None)
    if audio_src:
        mean_db, max_db = audio_loudness(audio_src)
        out["audioMeanDb"], out["audioMaxDb"] = mean_db, max_db
        out["audioQuiet"] = None if mean_db is None else mean_db < QUIET_MEAN_DB
    if best:
        w, h, name = best
        out.update({"mediaUrl": f"{base}/{name}", "width": w, "height": h})
    else:
        out["mediaUrl"] = hls_url
    return out


VIDEO_KEYS = ("hlsUrl", "dashUrl", "hasAudio", "hlsHasAudio", "dashHasAudio", "mp4HasAudio",
              "audioMeanDb", "audioMaxDb", "audioQuiet")


def refresh_video_sources(days: list[dict], only_missing: bool = True) -> int:
    """Add hlsUrl/dashUrl/hasAudio to stored v.redd.it entries (derived from the id)."""
    changed = 0
    for d in days:
        if d.get("mediaType") != "video":
            continue
        src = d.get("mediaUrl") or ""
        if "v.redd.it/" not in src:
            continue
        if only_missing and "hlsUrl" in d and d.get("hlsUrl"):
            continue
        info = vreddit_info(src)
        if not info:
            log(f"refresh: {d.get('date')} {src} -> no manifests reachable")
            continue
        for k in VIDEO_KEYS:
            if k in info:
                d[k] = info[k]
        changed += 1
        log(f"refresh: {d.get('date')} hls={'yes' if info.get('hlsUrl') else 'no'} "
            f"dash={'yes' if info.get('dashUrl') else 'no'} hasAudio={info.get('hasAudio')} "
            f"meanDb={info.get('audioMeanDb')} quiet={info.get('audioQuiet')}")
    return changed


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
        info = vreddit_info(url)
        if info is None and reddit_video and reddit_video.get("fallback_url"):
            info = {"mediaUrl": reddit_video["fallback_url"],
                    "hlsUrl": reddit_video.get("hls_url"),
                    "dashUrl": reddit_video.get("dash_url"),
                    "hasAudio": None, "mp4HasAudio": False}
        if not info:
            return None
        if reddit_video:
            info["width"] = info.get("width") or reddit_video.get("width")
            info["height"] = info.get("height") or reddit_video.get("height")
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
                return {"mediaType": "video", "mediaUrl": mp4, "hasAudio": None, "mp4HasAudio": None}
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

def reddit_id(url: str | None) -> str | None:
    m = re.search(r"/comments/([a-z0-9]+)", url or "", re.I)
    return m.group(1).lower() if m else None


def ranked(posts: list[dict], source: str) -> list[dict]:
    """Posts in Reddit's own top-of-day order, with 1-based `rank` set."""
    if source == "reddit-json":
        ordered = sorted(posts, key=lambda p: p.get("score") or 0, reverse=True)
        for i, p in enumerate(ordered, start=1):
            p.setdefault("rank", i)
        return ordered
    return sorted(posts, key=lambda p: p.get("rank", 10 ** 6))


def is_excluded(p: dict, exclude: set[str]) -> bool:
    return p["permalink"] in exclude or (reddit_id(p["permalink"]) or p.get("id")) in exclude


def build_pick(p: dict, media: dict, source: str) -> dict:
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
        for k in VIDEO_KEYS:
            if k in media:
                pick[k] = media[k]
    if source == "reddit-rss" or p.get("rank"):
        pick["rank"] = p.get("rank")
    return pick


def eligible(p: dict, exclude: set[str]) -> bool:
    return (not is_excluded(p, exclude) and not p.get("is_gallery")
            and is_cat_post(p["subreddit"], p["title"]))


def choose(posts: list[dict], source: str, exclude: set[str]) -> dict | None:
    """Deterministic: the highest-ranked usable post (used by --backfill / --top)."""
    for p in ranked(posts, source):
        if not eligible(p, exclude):
            continue
        media = classify_media(p["url"], p.get("reddit_video"))
        if media:
            return build_pick(p, media, source)
    return None


def candidate_weights(pool: list[dict], avoid_sub: str | None) -> list[float]:
    """Weight = mild preference for higher rank x boost for less common subs
    x penalty for yesterday's subreddit.

    - rank: 1/sqrt(position in pool) -> #4 is ~4x likelier than #60, not 60x.
    - subreddit balance: r/cats often fills a third of the list; dividing by
      sqrt(posts from that sub) gives small subs a real chance.
    - yesterday's subreddit is normally filtered out before this (see
      choose_random); the penalty only applies on thin days.
    """
    counts: dict[str, int] = {}
    for p in pool:
        counts[p["subreddit"].lower()] = counts.get(p["subreddit"].lower(), 0) + 1
    out = []
    for i, p in enumerate(pool, start=1):
        w = 1.0 / (i ** 0.5)
        w /= counts[p["subreddit"].lower()] ** 0.5
        if avoid_sub and p["subreddit"].lower() == avoid_sub.lower():
            w *= SAME_SUB_PENALTY
        out.append(w)
    return out


def choose_random(posts: list[dict], source: str, exclude: set[str],
                  rng: random.Random, avoid_sub: str | None = None,
                  skip_top: int = SKIP_TOP) -> dict | None:
    """A weighted-random "hidden gem": skip the day's top `skip_top`, then draw
    from the next POOL_SIZE eligible posts until one has usable media."""
    ordered = [p for p in ranked(posts, source) if not p.get("is_gallery")]
    pool = [p for p in ordered[skip_top:] if eligible(p, exclude)][:POOL_SIZE]
    if not pool:  # tiny day: fall back to the top ones rather than nothing
        pool = [p for p in ordered if eligible(p, exclude)][:POOL_SIZE]
    # Variety: never yesterday's subreddit when anything else is available.
    if avoid_sub:
        others = [p for p in pool if p["subreddit"].lower() != avoid_sub.lower()]
        if len(others) >= 3:
            pool = others
    log(f"random pool: {len(pool)} candidates (skipped top {skip_top}; "
        f"avoiding r/{avoid_sub or '-'}); subs: "
        + ", ".join(sorted({p['subreddit'] for p in pool})))
    tries = 0
    while pool and tries < MAX_MEDIA_TRIES:
        weights = candidate_weights(pool, avoid_sub)
        idx = rng.choices(range(len(pool)), weights=weights, k=1)[0]
        p = pool.pop(idx)
        tries += 1
        media = classify_media(p["url"], p.get("reddit_video"))
        if not media:
            log(f"  #{p.get('rank')} r/{p['subreddit']} skipped (no usable media)")
            continue
        log(f"  picked #{p.get('rank')} r/{p['subreddit']} after {tries} tries")
        return build_pick(p, media, source)
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
    # Older entries saved before hlsUrl existed get their audio-capable URLs now.
    refresh_video_sources([d for d in days if d["date"] != pick["date"]])
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    write_json(os.path.join(data_dir, "latest.json"), pick)
    write_json(archive_path, {"updatedAt": now, "days": days})
    log(f"wrote {data_dir}/latest.json and archive.json ({len(days)} days)")


BLURB_MAX = 300
X_STATUS = re.compile(r"^https://(?:x|twitter)\.com/([A-Za-z0-9_]{1,15})/status/(\d+)")
X_MEDIA_HOSTS = ("pbs.twimg.com", "video.twimg.com")
X_MAX_BITRATE = 2_500_000  # phone-friendly: best MP4 at or under ~2.5 Mbps


def clean_blurb(text) -> str | None:
    if text is None:
        return None
    t = re.sub(r"\s+", " ", str(text)).strip()
    if not t:
        return None
    if len(t) > BLURB_MAX:
        raise SystemExit(f"blurb is {len(t)} chars; keep it to 1-2 sentences (max {BLURB_MAX})")
    return t


def best_x_variant(variants: list[dict]) -> dict | None:
    """Highest-bitrate MP4 at or under X_MAX_BITRATE (else the lowest MP4)."""
    mp4s = [v for v in variants or [] if v.get("content_type") == "video/mp4" and v.get("url")]
    if not mp4s:
        return None
    under = [v for v in mp4s if (v.get("bit_rate") or 0) <= X_MAX_BITRATE]
    if under:
        return max(under, key=lambda v: v.get("bit_rate") or 0)
    return min(mp4s, key=lambda v: v.get("bit_rate") or 0)


def x_media_fields(m: dict) -> dict:
    """Turn an X API v2 media object (from includes.media) into our media fields."""
    kind = m.get("type")
    out: dict = {"width": m.get("width"), "height": m.get("height")}
    if kind == "photo":
        url = m.get("url")
        out.update({"mediaType": "image", "mediaUrl": url,
                    # small (~680px) rendition for archive rows / placeholders
                    "thumbnail": f"{url}?name=small" if url and "?" not in url else None})
        return out
    if kind in ("video", "animated_gif"):
        v = best_x_variant(m.get("variants") or [])
        if not v:
            raise SystemExit("X media has no MP4 variant")
        hls = next((x["url"] for x in m.get("variants") or []
                    if x.get("content_type") == "application/x-mpegURL"), None)
        out.update({"mediaType": "video", "mediaUrl": v["url"],
                    "thumbnail": m.get("preview_image_url"),
                    "bitRate": v.get("bit_rate")})
        if kind == "animated_gif":   # X GIFs are silent MP4s
            out.update({"hasAudio": False, "mp4HasAudio": False, "xGif": True})
        elif hls:
            out["hlsUrl"] = hls
        return out
    raise SystemExit(f"unsupported X media type: {kind}")


def probe_audio_ffprobe(url: str) -> bool | None:
    """True/False if ffprobe can tell whether the file/stream has audio, else None."""
    if not shutil.which("ffprobe"):
        return None
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
                            "-of", "csv=p=0", url], capture_output=True, text=True, timeout=45)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    return "audio" in r.stdout.split()


def x_video_audio(pick: dict) -> None:
    """Fill hasAudio / mp4HasAudio / hlsHasAudio for an X video (MP4s carry audio)."""
    if pick.get("mediaType") != "video" or pick.get("xGif"):
        return
    if pick.get("mp4HasAudio") is None:
        a = probe_audio_ffprobe(pick["mediaUrl"])
        pick["mp4HasAudio"] = True if a is None else a   # X video MP4s normally have AAC audio
    if pick.get("hlsUrl"):
        st, _, body = http_get(pick["hlsUrl"], retries=1)
        text = body.decode("utf-8", "replace") if body else ""
        if st == 200 and text.startswith("#EXTM3U"):
            pick["hlsHasAudio"] = ("TYPE=AUDIO" in text) or ("mp4a" in text)
        else:
            log(f"X HLS playlist not reachable (HTTP {st}); dropping hlsUrl")
            pick["hlsUrl"] = None
            pick["hlsHasAudio"] = None
    pick["hasAudio"] = bool(pick.get("mp4HasAudio") or pick.get("hlsHasAudio"))
    src = pick["mediaUrl"] if pick.get("mp4HasAudio") else pick.get("hlsUrl")
    if pick["hasAudio"] and src:
        mean_db, max_db = audio_loudness(src)
        pick["audioMeanDb"], pick["audioMaxDb"] = mean_db, max_db
        pick["audioQuiet"] = None if mean_db is None else mean_db < QUIET_MEAN_DB


def import_pick(path: str, date: str, data_dir: str | None = None) -> dict:
    """Import a manually chosen pick from a JSON file (see X_PICK.md).

    X picks: {"source": "x", "postUrl", "authorHandle", "authorName", "likes",
              "text", "title"?, "blurb", and either "xMedia" (the media object
              copied verbatim from the X API response) or "mediaType" + "mediaUrl"
              (+ "thumbnail"/"posterUrl", "hlsUrl", "width", "height")}
    Other picks need: title, author, permalink, mediaType, mediaUrl.
    The legacy fields the shipped app reads (author, permalink, score,
    scoreLabel, subreddit, thumbnail) are always filled in, so older app builds
    still render X days correctly.
    """
    raw = load_json(path, None)
    if not isinstance(raw, dict):
        raise SystemExit(f"{path}: expected a JSON object")
    post_url = raw.get("postUrl") or raw.get("permalink") or ""
    is_x = raw.get("source") == "x" or bool(X_STATUS.match(post_url))
    pick: dict = {"date": raw.get("date") or date}
    if is_x:
        m = X_STATUS.match(post_url)
        if not m:
            raise SystemExit(f"{path}: postUrl must look like https://x.com/<handle>/status/<id>")
        post_url = f"https://x.com/{m.group(1)}/status/{m.group(2)}"
        handle = str(raw.get("authorHandle") or raw.get("author") or m.group(1)).lstrip("@")
        media = x_media_fields(raw["xMedia"]) if raw.get("xMedia") else {
            k: raw.get(k) for k in ("mediaType", "mediaUrl", "width", "height", "hlsUrl",
                                    "hasAudio", "mp4HasAudio")}
        media.setdefault("thumbnail", None)
        if raw.get("thumbnail") or raw.get("posterUrl"):
            media["thumbnail"] = raw.get("posterUrl") or raw.get("thumbnail")
        text = re.sub(r"\s*https://t\.co/\w+", "", str(raw.get("text") or "")).strip()
        title = (raw.get("title") or "").strip()
        if not title:
            first = re.split(r"(?<=[.!?])\s|\n", text, maxsplit=1)[0].strip() if text else ""
            title = first if len(first) <= 110 else first[:107].rstrip() + "…"
        if not title:
            raise SystemExit(f"{path}: X pick needs a title or text")
        likes = raw.get("likes", raw.get("score"))
        if likes is not None and not isinstance(likes, int):
            raise SystemExit(f"{path}: likes must be an integer")
        pick.update({
            "title": title,
            "subreddit": None,
            "author": handle,                  # legacy credit field
            "authorHandle": handle,
            "authorName": raw.get("authorName"),
            "score": likes,                    # legacy popularity field
            "scoreLabel": "likes",
            "likes": likes,
            "permalink": post_url,             # legacy link field
            "postUrl": post_url,
            "postId": m.group(2),
            "text": text or None,
            **{k: v for k, v in media.items() if v is not None or k in ("width", "height", "thumbnail")},
            "source": "x",
        })
        for k in ("mediaUrl", "thumbnail", "hlsUrl"):
            u = pick.get(k)
            if u and urllib.parse.urlparse(u).netloc not in X_MEDIA_HOSTS:
                raise SystemExit(f"{path}: {k} must be on {' or '.join(X_MEDIA_HOSTS)} (got {u})")
    else:
        missing = [k for k in ["title", "author", "permalink", "mediaType", "mediaUrl"] if not raw.get(k)]
        if missing:
            raise SystemExit(f"{path}: missing required fields: {', '.join(missing)}")
        source = raw.get("source") or "manual"
        pick.update({
            "title": raw["title"],
            "subreddit": raw.get("subreddit"),
            "author": str(raw["author"]).lstrip("@").replace("u/", "", 1),
            "score": raw.get("score"),
            "scoreLabel": raw.get("scoreLabel") or "upvotes",
            "permalink": raw["permalink"],
            "mediaType": raw["mediaType"],
            "mediaUrl": raw["mediaUrl"],
            "width": raw.get("width"),
            "height": raw.get("height"),
            "thumbnail": raw.get("thumbnail"),
            "source": source,
        })
    if pick.get("mediaType") not in ("image", "gif", "video"):
        raise SystemExit(f"{path}: mediaType must be image, gif or video")
    for k in ("permalink", "mediaUrl"):
        if not str(pick.get(k) or "").startswith("https://"):
            raise SystemExit(f"{path}: {k} must be an https:// URL")
    if pick["mediaType"] in ("image", "gif"):
        probe = probe_image(pick["mediaUrl"])
        if not probe["ok"]:
            raise SystemExit(f"{path}: mediaUrl is not reachable: {pick['mediaUrl']}")
        if not pick.get("width") and "width" in probe:
            pick["width"], pick["height"] = probe["width"], probe["height"]
    elif is_x:
        st, _, _ = http_get(pick["mediaUrl"], max_bytes=1024, headers={"Range": "bytes=0-1023"})
        if st not in (200, 206):
            raise SystemExit(f"{path}: video mediaUrl not reachable (HTTP {st})")
        x_video_audio(pick)
    blurb = clean_blurb(raw.get("blurb"))
    if blurb:
        pick["blurb"] = blurb
    if data_dir:  # never re-use a post that already had its day
        archive = load_json(os.path.join(data_dir, "archive.json"), {"days": []})
        for d in archive.get("days", []):
            if d.get("date") != pick["date"] and pick["permalink"] in (d.get("permalink"), d.get("postUrl")):
                raise SystemExit(f"{path}: this post was already the cat of {d['date']}")
    pick.pop("xGif", None)
    pick["pickedAt"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    return pick


def set_blurb(text: str, date: str, data_dir: str, dry_run: bool = False) -> int:
    """Add/replace the blurb on `date`'s entry in latest.json + archive.json."""
    blurb = clean_blurb(text)
    archive_path = os.path.join(data_dir, "archive.json")
    latest_path = os.path.join(data_dir, "latest.json")
    archive = load_json(archive_path, {"days": []})
    latest = load_json(latest_path, {})
    entry = next((d for d in archive.get("days", []) if d.get("date") == date), None)
    if entry is None:
        log(f"set-blurb: no entry for {date} in archive.json")
        return 2
    if blurb:
        entry["blurb"] = blurb
    else:
        entry.pop("blurb", None)
    if latest.get("date") == date:
        if blurb:
            latest["blurb"] = blurb
        else:
            latest.pop("blurb", None)
    print(json.dumps(entry, indent=2, ensure_ascii=False))
    if not dry_run:
        write_json(archive_path, archive)
        if latest.get("date") == date:
            write_json(latest_path, latest)
        log(f"set-blurb: {'updated' if blurb else 'removed'} blurb for {date}")
    return 0


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
        added.append({"date": d, **pick, "source": "reddit",
                      "fetchedVia": source.replace("reddit-", ""), "scoreLabel": "upvotes",
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
    ap.add_argument("--set-blurb", metavar="TEXT",
                    help="add/replace the 1-2 sentence blurb on today's (or --date's) entry and exit; "
                         "pass an empty string to remove it")
    ap.add_argument("--top", action="store_true",
                    help="pick the #1 usable post (old behaviour) instead of a random hidden gem")
    ap.add_argument("--seed", default=None,
                    help="random seed (default: the date, so re-runs on the same day agree)")
    ap.add_argument("--backfill", type=int, metavar="N",
                    help="also fill up to N empty past days (max 30) from Reddit's top-of-week/month")
    ap.add_argument("--refresh-media", action="store_true",
                    help="re-derive hlsUrl/dashUrl/hasAudio for every stored v.redd.it video and exit")
    ap.add_argument("--dry-run", action="store_true", help="print pick, do not write files")
    ap.add_argument("--force", action="store_true",
                    help="re-pick even if today already has a pick")
    args = ap.parse_args(argv)
    date = args.date or today_et()

    if args.refresh_media:
        archive_path = os.path.join(args.data_dir, "archive.json")
        archive = load_json(archive_path, {"days": []})
        n = refresh_video_sources(archive.get("days", []), only_missing=False)
        latest_path = os.path.join(args.data_dir, "latest.json")
        latest = load_json(latest_path, {})
        match = next((d for d in archive.get("days", []) if d.get("date") == latest.get("date")), None)
        if not args.dry_run:
            write_json(archive_path, archive)
            if match:
                write_json(latest_path, match)
        log(f"refresh-media: updated {n} video entries")
        return 0

    if args.set_blurb is not None:
        return set_blurb(args.set_blurb, date, args.data_dir, args.dry_run)

    if args.from_json:
        pick = import_pick(args.from_json, date, args.data_dir)
        print(json.dumps(pick, indent=2, ensure_ascii=False))
        if not args.dry_run:
            save(pick, args.data_dir)
        return 0

    latest = load_json(os.path.join(args.data_dir, "latest.json"), {})
    if latest.get("date") == date and not args.force and (
            latest.get("source") not in (None, "reddit", "reddit-rss", "reddit-json")
            or latest.get("blurb")):  # a curated (blurbed) Reddit pick also stays
        log(f"{date} already has a curated pick; keeping it (use --force to override)")
        return 0

    archive = load_json(os.path.join(args.data_dir, "archive.json"), {"days": []})
    past = [d for d in archive.get("days", []) if d.get("date") != date]
    # Don't repeat a post that already won a previous day (by permalink or Reddit id).
    exclude = {d.get("permalink") for d in past} | {reddit_id(d.get("permalink")) for d in past}
    exclude.discard(None)
    yesterday = (dt.date.fromisoformat(date) - dt.timedelta(days=1)).isoformat()
    avoid_sub = next((d.get("subreddit") for d in past if d.get("date") == yesterday), None)
    rng = random.Random(args.seed or f"catotd-{date}")

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
        if args.top:
            pick = choose(posts, source, exclude)
        else:
            pick = choose_random(posts, source, exclude, rng, avoid_sub)
        if not pick:
            errors.append(f"{source}: no post with supported media")
            continue
        pick = {"date": date, **pick, "source": "reddit",
                "fetchedVia": source.replace("reddit-", ""),
                "selection": "top" if args.top else "random",
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

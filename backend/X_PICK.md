# Daily X pick (for the Cat of the Day routine)

The GitHub Action (`.github/workflows/daily-cat.yml`, ~9:07 AM ET) always picks a
random Reddit "hidden gem" first. The daily routine runs **after** it (9:30 AM ET
or later) and either:

- **X day:** replaces today's entry with a quirky/heartwarming cat post from X, or
- **Reddit day:** keeps the Reddit pick and just adds a short blurb.

Aim for a mix (roughly every other day on X, never more than 2 X days in a row
and never 3 Reddit days in a row). Check the archive to see what recent days used:
`python3 -c "import json;[print(d['date'],d.get('source'),d.get('subreddit')) for d in json.load(open('backend/data/archive.json'))['days'][:7]]"`

Repo: `/workspace/cat-of-the-day` (GitHub `jm88825/cat-of-the-day`). Always start with
`git pull --rebase origin main` because the bot commits data every morning.

## 1. Search X (one call, keep it cheap)

MCP server `user-X`, tool **`search_posts_all`** (there is no `search_posts_recent`
on this connector). Arguments that worked on 2026-10-02:

```json
{
  "query": "(cat OR kitten OR kitty) (has:images OR has:videos) -is:retweet -is:reply -is:quote -is:nullcast lang:en -giveaway -sale -shop -nft -crypto -adopt",
  "max_results": 12,
  "sort_order": "relevancy",
  "start_time": "<now minus ~48h, ISO 8601 UTC, e.g. 2026-09-30T23:00:00Z>",
  "expansions": "attachments.media_keys,author_id",
  "media.fields": "type,url,preview_image_url,variants,width,height,duration_ms,alt_text",
  "post.fields": "created_at,public_metrics,possibly_sensitive,lang,attachments",
  "user.fields": "username,name,verified"
}
```

Facts learned from the test run:

- **`min_faves:` is NOT available** on this API tier ("Operator is not available in
  current product"); the request fails (no charge). Filter on
  `public_metrics.like_count` yourself.
- Cost: 12 posts = **$0.06** (≈ $0.005/post; the user expansion added nothing
  measurable). Check with `get_usage_credits` (free) before/after. Keep
  `max_results` ≤ 20 (≤ $0.10/day).
- With that query, relevancy results were mostly hashtag spam and promo accounts
  with 0–2 likes. Add **`-has:hashtags`** to the query next time (every spam post
  had hashtags; the good one had none) and consider `("my cat" OR "my kitten" OR
  "our cat" OR kitten OR kitty)` as the keyword group. If a search turns up nothing
  usable, make it a Reddit day instead of paying for more searches.
- Each post has a `url` field (`https://x.com/<handle>/status/<id>`) and its media
  are in `includes.media` (match `attachments.media_keys[0]` to `media_key`);
  the author is in `includes.users` (match `author_id` to `id`).

## 2. Choose a post

Must:
- Clearly a real cat/kitten in the media (download and **look at it**: photo
  `url` + `?name=small`, or the video's `preview_image_url`).
- `possibly_sensitive: false`, safe for work, no injury/gore/death, not sad.
- Not an ad, shop, giveaway, link farm, crypto/NFT, AI-art account, or a post
  that is mostly hashtags/links. Not a reply/quote/retweet.
- Quirky, funny, or heartwarming, from a normal person.
- Not already in `backend/data/archive.json` (the importer refuses repeats).

Prefer: a "hidden gem" (not mega-viral; skip >50K likes), real engagement if
available (≥ 20 likes is nice but a lovely 7-like post is fine), video with sound
or a sharp photo, posted in the last 1–2 days.

## 3. Write the pick JSON

Save as `backend/picks/<date>-x.json` (committed as a record):

```json
{
  "source": "x",
  "date": "2026-10-02",
  "postUrl": "https://x.com/kervsky/status/2105834843473055909",
  "authorHandle": "kervsky",
  "authorName": "Kervsky | Tired | Meandering",
  "likes": 7,
  "title": "2 of my black cats gave birth on the same day",
  "text": "<the post's full text, copied verbatim>",
  "blurb": "<1–2 sentences, see below>",
  "xMedia": { "<the post's media object copied verbatim from includes.media>": "" }
}
```

- `title`: a short headline taken from the post's own words (≤ ~90 chars). If
  omitted, the first sentence of `text` is used.
- `xMedia`: paste the media object as-is (`type`, `url` / `preview_image_url`,
  `variants`, `width`, `height`). The importer picks the media for you:
  - `photo` → `mediaType: "image"`, `mediaUrl` = `url`, thumbnail = `url?name=small`
  - `video` → highest-bitrate `video/mp4` variant ≤ 2.5 Mbps as `mediaUrl`
    (X MP4s include audio), the `.m3u8` variant as `hlsUrl`,
    `preview_image_url` as poster; it confirms audio with ffprobe/the playlist
    and measures loudness if ffmpeg is installed.
  - `animated_gif` → silent looping video.
  Multi-photo posts: only the first media item is shown; pick the best one by
  copying that media object.
- Instead of `xMedia` you can give `mediaType`, `mediaUrl`, `thumbnail`/`posterUrl`,
  `hlsUrl`, `width`, `height` directly (media must be on pbs.twimg.com / video.twimg.com).

### The blurb (also used on Reddit days)

1–2 sentences, ≤ 300 characters, warm and a little playful. Base it **only** on
the post's own text and what is actually visible in the photo/video. Don't invent
names, ages, breeds, backstories or feelings the post doesn't support. Refer to
the poster neutrally ("their human", "the poster"). No hashtags or emojis needed.

Example (from the post above): "Two black cats had their litters on the same day,
so their human put all five newborns (four black, one white) in one big box, and
the moms are now raising them together. Here, a mama in a blue collar snuggles
the whole crew."

## 4. Import and check

```bash
cd /workspace/cat-of-the-day
git pull --rebase origin main
python3 backend/pick_cat.py --from-json backend/picks/2026-10-02-x.json --dry-run   # check output
python3 backend/pick_cat.py --from-json backend/picks/2026-10-02-x.json
```

This replaces today's entry in `backend/data/latest.json` and `archive.json`
(the date defaults to today in New York time; set `"date"` to be explicit).
Once today's entry is an X pick, the scheduled Reddit run won't overwrite it
(unless someone passes `--force`).

**Reddit day instead:** look at today's Reddit media (`thumbnail` or `mediaUrl`
in `latest.json`), then:

```bash
python3 backend/pick_cat.py --set-blurb "Meet Jolene, a young calico who ... upward stare."
```

(`--set-blurb ""` removes a blurb; `--date YYYY-MM-DD` targets another day.)

## 5. Publish

```bash
cd /workspace/cat-of-the-day
git add backend/data backend/picks
git commit -m "Cat of the day: <date> (X: @handle)"     # or "... blurb"
git pull --rebase origin main
git -c credential.helper= -c credential.helper='!gh auth git-credential' push origin main
```

GitHub Pages updates within a few minutes; the app picks it up on its next
load / pull-to-refresh. Check https://jm88825.github.io/cat-of-the-day/backend/data/latest.json.

## Data shape (what the importer writes)

X entries keep the legacy fields so older app builds (versionCode ≤ 2) still show
them correctly: `author` = handle, `permalink` = post URL, `score` = likes,
`scoreLabel` = "likes", `subreddit` = null. New fields: `source: "x"`,
`authorHandle`, `authorName`, `postUrl`, `postId`, `likes`, `text`, `blurb`,
`mediaType`, `mediaUrl`, `thumbnail` (poster), `width`, `height`, and for video
`hlsUrl`, `bitRate`, `hasAudio`, `mp4HasAudio`, `hlsHasAudio`, `audioMeanDb`,
`audioMaxDb`, `audioQuiet`.

Note: video.twimg.com returns 403 to browsers that send a non-X `Referer`. The
Android app sends none; the web build adds `<meta name="referrer" content="no-referrer">`.

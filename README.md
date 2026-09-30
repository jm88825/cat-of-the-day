# 🐱 Cat of the Day

An Android app (React Native / Expo, TypeScript) that shows the single most
viral cat picture or video of the day, plus an archive of the last 60 days.
Every post is credited to its creator with a link to the original.

```
cat-of-the-day/
├── app/                      Expo app (Android package com.catoftheday.app)
│   ├── config.ts             ← the ONE place the data URL is set
│   ├── App.tsx, src/         screens, components
│   ├── app.json, eas.json    Expo + EAS build config (Android AAB)
│   └── assets/               original generated icon / splash
├── backend/
│   ├── pick_cat.py           daily picker (Python 3.9+, stdlib only)
│   ├── serve.py              local test server (port 8081, with CORS)
│   ├── example-x-pick.json   template for recording an X post as the pick
│   └── data/                 latest.json + archive.json (served as static files)
├── .github/workflows/daily-cat.yml   runs the picker daily at 13:07 UTC
├── privacy.html / PRIVACY.md  privacy policy (served by GitHub Pages)
├── store-assets/             512px Play icon + 1024x500 feature graphic
├── screenshots/              web-build screenshots (390x844)
└── tools/                    icon generator + screenshot scripts (Node + Chrome)
```

## How it works

1. **Picker** – `backend/pick_cat.py` looks at today's top posts in
   r/cats, r/catpictures, r/catvideos, r/Catswithjobs, r/CatsAreAssholes,
   r/catsstandingup and r/aww (r/aww only when the title mentions
   cat/kitten/kitty). It skips NSFW posts, galleries and anything that isn't an
   image, GIF or video on `i.redd.it`, `v.redd.it` or Imgur, then takes the
   highest-ranked one.
   - It tries Reddit's JSON listing first (www → old → api.reddit.com); this
     gives real upvote counts.
   - If that's blocked (it often is for servers and cloud IPs; it was blocked
     when this was built), it falls back to Reddit's public **RSS feed** of the
     same "top of the day" listing. The feed is ordered by score but doesn't
     include the number, so `score` is saved as `null` and the app shows
     "#N on Reddit's top cat list" instead of an upvote count. Numbers are
     never guessed.
   - If every source fails, it exits with an error and leaves the existing data
     alone.
   - `v.redd.it` videos: `mediaUrl` is Reddit's direct MP4 (the same file as the
     API's `fallback_url`). **These MP4s have no audio**, because Reddit keeps
     audio in a separate track. The picker also saves the `dashUrl` manifest,
     which does include audio. On Android the app plays that manifest, so tap to
     unmute works there. The web build uses the silent MP4.
2. **Hosting** – `backend/data/*.json` are plain static files. GitHub Pages
   serves them for free, and the GitHub Actions workflow refreshes them every
   day.
3. **App** – downloads `latest.json` and `archive.json` from `DATA_BASE_URL`.

### Picker commands

```bash
python3 backend/pick_cat.py                 # pick today's cat (date = today in New York time)
python3 backend/pick_cat.py --dry-run       # show the pick without writing files
python3 backend/pick_cat.py --backfill 7    # fill empty past days (marked "backfilled": true)
python3 backend/pick_cat.py --from-json my-pick.json   # record an X (or other) post instead
```

`--from-json` needs `title`, `author`, `permalink` (the https link to the
original post), `mediaType` (`image` | `gif` | `video`) and `mediaUrl`. You can
also add `score`, `scoreLabel` (for example `"likes"`), `width`, `height`,
`thumbnail` and `date`. See `backend/example-x-pick.json`. Once a day has a
manual pick, the scheduled run won't overwrite it unless you pass `--force`.
**Only use media you're allowed to show, and always link the original post.**

## Run it locally

Requirements: Node 20.19.4+ or 22 LTS, and Python 3.9+.

```bash
# 1) data
python3 backend/pick_cat.py
python3 backend/serve.py            # serves backend/data at http://localhost:8081

# 2) app  (by default it reads the live GitHub Pages data; override for local data:)
cd app
npm install
npx tsc --noEmit                    # type check
EXPO_PUBLIC_DATA_URL=http://localhost:8081 npx expo start --web --port 8082
#   (Metro also defaults to 8081, so pick another port)
# or build static web files: npx expo export --platform web  → app/dist
```

On an Android emulator, set `EXPO_PUBLIC_DATA_URL=http://10.0.2.2:8081`. On a real phone, use
`http://<your-PC-LAN-IP>:8081`. Release builds only allow `https://`, so
production must use your GitHub Pages URL.

Regenerate the icons: `cd tools && npm install && node make-icons.mjs` (uses
Google Chrome). Retake the screenshots: `node tools/screenshot.mjs` while the
web build is served on port 8090 (`cd app/dist && python3 -m http.server 8090`).

---

## Publishing: step by step

### A. Put the data on GitHub Pages (free)

1. Create a **public** GitHub repo, for example `cat-of-the-day`, and push this
   whole folder to its `main` branch:
   ```bash
   cd cat-of-the-day
   git init && git add . && git commit -m "Cat of the Day"
   git branch -M main
   git remote add origin https://github.com/jm88825/cat-of-the-day.git
   git push -u origin main
   ```
2. In the repo, go to **Settings → Pages → Build and deployment → Source:
   "Deploy from a branch"**, then choose **Branch: `main`, folder `/ (root)`** and
   click Save. The empty `.nojekyll` file makes Pages serve the files as they
   are.
3. After a minute, check that these load in a browser:
   - `https://jm88825.github.io/cat-of-the-day/backend/data/latest.json`
   - `https://jm88825.github.io/cat-of-the-day/privacy.html` (use this as the
     privacy policy URL on Google Play)
4. Go to **Settings → Actions → General → Workflow permissions** and choose
   **"Read and write permissions"**, so the workflow can commit the new data.
5. Go to **Actions → Daily cat → Run workflow** to test it once. After that it
   runs every day at 13:07 UTC (9:07 AM Eastern in summer, 8:07 AM in winter).
   Each run commits `backend/data/`, and Pages republishes it automatically.
   - If the run fails with "no data source worked", Reddit is blocking
     GitHub's servers. The app keeps showing the last good day. Options: run
     the picker on your own computer or a small server and push the result, or
     record a pick by hand with `--from-json`.

### B. Point the app at your data

**Done.** `app/config.ts` already points at GitHub Pages:

```ts
const PRODUCTION_DATA_URL = 'https://jm88825.github.io/cat-of-the-day/backend/data';
// dev override: EXPO_PUBLIC_DATA_URL=http://localhost:8081 npx expo start --port 8082
```

The privacy policy contact (and content-removal address) is
**jm88825@gmail.com**. Use the same address as the developer contact email in the
Play Console.

### C. Build the Android App Bundle (AAB) with EAS (free tier)

1. Create a free Expo account at <https://expo.dev/signup>.
2. Log in and link the project:
   ```bash
   cd app
   npx eas-cli@latest login
   npx eas-cli@latest init          # creates the Expo project, adds its projectId to app.json
   ```
3. Build:
   ```bash
   npx eas-cli@latest build -p android --profile production
   ```
   When asked, let EAS **generate a new Android keystore**. EAS stores it for
   you, and every future update must be signed with this same key. When the
   cloud build finishes, download the `.aab` from the link it prints.
   (To test on a phone first: `--profile preview` builds an installable `.apk`.)
   EAS manages `versionCode` (`appVersionSource: remote`, `autoIncrement`).
   For each release, bump `version` in `app.json`.

### D. Upload to Google Play

1. In the [Play Console](https://play.google.com/console), click **Create app**:
   name "Cat of the Day", type App, Free.
2. **Testing → Internal testing → Create new release**, then upload the `.aab`.
   Keep **Play App Signing** turned on (the default). New personal developer
   accounts must also run a **closed test with at least 12 testers for 14
   days** before they can go to Production.
3. Fill in **App content**:
   - **Privacy policy:** `https://jm88825.github.io/cat-of-the-day/privacy.html`
   - **Data safety:** "No data collected" and "No data shared". The app has no
     analytics, accounts or ads.
   - **Ads:** No ads. **Target audience:** 13+ is safest, because the content
     is user-generated.
   - **Content rating** questionnaire: the app shows user-generated content from
     third-party sites. Say so honestly.
4. **Store listing:** use `store-assets/play-icon-512.png`,
   `store-assets/feature-graphic-1024x500.png`, and at least 2 phone
   screenshots. Take them on a real device or emulator. `screenshots/` has web
   previews.
   - Short description example: "One viral cat picture or video, every day."
5. Later updates: bump `version`, run `eas build` again, and upload the new AAB.
   (`eas submit -p android` can upload for you once you add a Play service
   account key.)

### Play policy notes (important for an app that shows other people's posts)

- **Credit every post.** Each post shows "Posted by u/X on r/Y – view original"
  with a link to the source. Keep that.
- **Don't re-host media.** The app streams images and videos from the original
  host (i.redd.it, v.redd.it, Imgur). It never copies them. If a post is
  deleted, it disappears from the app too.
- **Impersonation / IP policy:** don't call the app "Reddit ..." or use
  Reddit's logo. The in-app line "not affiliated with Reddit" helps. Respond
  quickly to takedown requests at the contact email in the privacy policy.
- **User-generated content:** the app only shows SFW posts. The picker skips
  NSFW posts, and the source subreddits are moderated, but the picks are
  automatic. Check them now and then. Use `--from-json` to replace a bad pick.
- **Reddit's terms:** using Reddit's public feeds in a commercial or
  high-volume way may require their Data API terms or approval. This app makes
  one request per day from a server, not one per user.
- **iOS later:** `app.json` already sets `ios.bundleIdentifier`, so you can run
  `eas build -p ios` once you have an Apple developer account.

## Status

- ✅ Picker verified locally (Reddit JSON blocked here; RSS worked).
- ✅ Web build exported and screenshotted; TypeScript and `expo-doctor` pass;
  Android `expo prebuild` config checked (package, permissions, name).
- ⚠️ Not yet tested: native Android build and playback on a device (including
  DASH audio), the GitHub Actions run on GitHub's servers, and GitHub Pages
  hosting.

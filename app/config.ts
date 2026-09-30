/**
 * Where the app downloads its data (latest.json + archive.json).
 *
 * This is the ONLY place the data location is configured.
 *
 * Production: GitHub Pages, refreshed daily by .github/workflows/daily-cat.yml.
 *
 * Local override for development (no code change needed). Expo inlines
 * EXPO_PUBLIC_* variables when bundling:
 *   EXPO_PUBLIC_DATA_URL=http://localhost:8081 npx expo start --port 8082
 *     - web / iOS simulator:        http://localhost:8081
 *     - Android emulator:           http://10.0.2.2:8081
 *     - phone on the same Wi-Fi:    http://<your-computer-LAN-IP>:8081
 *   (serve the data with: python3 backend/serve.py)
 *
 * Release Android builds block plain http://, so production must stay https.
 * Don't set EXPO_PUBLIC_DATA_URL in eas.json for production builds.
 */
const PRODUCTION_DATA_URL = 'https://jm88825.github.io/cat-of-the-day/backend/data';

export const DATA_BASE_URL: string = process.env.EXPO_PUBLIC_DATA_URL || PRODUCTION_DATA_URL;

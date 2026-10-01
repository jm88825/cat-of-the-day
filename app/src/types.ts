export type MediaType = 'image' | 'gif' | 'video';

export interface CatPick {
  date: string; // YYYY-MM-DD (America/New_York)
  title: string;
  subreddit: string | null; // null for non-Reddit picks (e.g. X)
  author: string;
  score: number | null; // null when the source didn't expose it
  scoreLabel?: string; // "upvotes" | "likes"
  rank?: number | null; // position in Reddit's top-of-day list (RSS source)
  permalink: string; // link to the original post (source credit)
  mediaType: MediaType;
  mediaUrl: string;
  width?: number | null;
  height?: number | null;
  thumbnail?: string | null;
  hlsUrl?: string | null; // v.redd.it HLS master playlist (video + audio)
  dashUrl?: string | null; // v.redd.it DASH manifest (video + audio; Android only)
  hasAudio?: boolean | null; // true if any stored stream has an audio track
  hlsHasAudio?: boolean | null;
  dashHasAudio?: boolean | null;
  mp4HasAudio?: boolean | null; // Reddit MP4s are video-only → false
  audioMeanDb?: number | null; // measured loudness (if ffmpeg was available)
  audioMaxDb?: number | null;
  audioQuiet?: boolean | null; // track exists but is nearly inaudible
  source?: string; // reddit-json | reddit-rss | x | manual
  pickedAt?: string;
}

export interface Archive {
  updatedAt?: string;
  days: CatPick[];
}

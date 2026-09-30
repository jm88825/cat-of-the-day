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
  dashUrl?: string | null; // v.redd.it DASH manifest (has audio; Android)
  hasAudio?: boolean | null;
  mp4HasAudio?: boolean | null;
  source?: string; // reddit-json | reddit-rss | x | manual
  pickedAt?: string;
}

export interface Archive {
  updatedAt?: string;
  days: CatPick[];
}

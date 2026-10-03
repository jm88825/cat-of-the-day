import { useEvent, useEventListener } from 'expo';
import { Image } from 'expo-image';
import { useVideoPlayer, VideoView, type VideoSource } from 'expo-video';
import { useEffect, useMemo, useState } from 'react';
import { Platform, Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { colors, radius } from '../theme';
import type { CatPick } from '../types';

/** Box size that keeps the media's aspect ratio but never gets absurdly tall. */
function useMediaBox(pick: CatPick) {
  const { width: winW, height: winH } = useWindowDimensions();
  const w = Math.min(winW - 32, 560);
  const aspect = pick.width && pick.height ? pick.width / pick.height : 1;
  // Keep the title + source credit visible without scrolling on most phones.
  const h = Math.min(w / aspect, winH * 0.5);
  return { width: w, height: Math.max(h, 220) };
}

export default function CatMedia({ pick }: { pick: CatPick }) {
  const box = useMediaBox(pick);
  return (
    <View style={[styles.frame, box]}>
      {pick.mediaType === 'video' ? (
        <CatVideo key={pick.mediaUrl} pick={pick} />
      ) : (
        <Image
          source={{ uri: pick.mediaUrl }}
          placeholder={pick.thumbnail ? { uri: pick.thumbnail } : undefined}
          style={StyleSheet.absoluteFill}
          contentFit="contain"
          transition={250}
          autoplay // animated GIFs
          accessibilityLabel={pick.title}
        />
      )}
    </View>
  );
}

type StreamKind = 'hls' | 'dash' | 'mp4';
interface Stream { kind: StreamKind; source: VideoSource; audio: boolean }

function webCanPlayHls(): boolean {
  if (Platform.OS !== 'web' || typeof document === 'undefined') return false;
  // Chrome answers "maybe" but can't play Reddit's CMAF HLS natively, so only
  // try it on Safari-style browsers. Elsewhere the web build uses the silent MP4.
  const ua = globalThis.navigator?.userAgent ?? '';
  if (/Chrome|Chromium|CriOS|Edg|Firefox|Android/i.test(ua)) return false;
  return document.createElement('video').canPlayType('application/vnd.apple.mpegurl') !== '';
}

/**
 * Playable streams in order of preference.
 *
 * Reddit's MP4 files (mediaUrl) are VIDEO-ONLY. Sound lives in a separate
 * audio track that only the HLS and DASH manifests reference. So:
 *   1. HLS  (HLSPlaylist.m3u8): Android ExoPlayer + iOS AVPlayer, with audio
 *   2. DASH (DASHPlaylist.mpd): Android only, with audio
 *   3. MP4: silent fallback (and what desktop browsers play)
 *
 * X (video.twimg.com) MP4s already include audio (mp4HasAudio: true), so on
 * web and as the native fallback they play with sound; their HLS playlist is
 * tried first on native just like Reddit's.
 */
export function streamsFor(pick: CatPick): Stream[] {
  const out: Stream[] = [];
  const native = Platform.OS === 'android' || Platform.OS === 'ios';
  const anyAudio = pick.hasAudio === true;
  if (pick.hlsUrl && (native || webCanPlayHls())) {
    out.push({ kind: 'hls', source: { uri: pick.hlsUrl, contentType: 'hls' },
      audio: pick.hlsHasAudio ?? anyAudio });
  }
  if (pick.dashUrl && Platform.OS === 'android') {
    out.push({ kind: 'dash', source: { uri: pick.dashUrl, contentType: 'dash' },
      audio: pick.dashHasAudio ?? anyAudio });
  }
  out.push({ kind: 'mp4', source: { uri: pick.mediaUrl }, audio: pick.mp4HasAudio === true });
  return out;
}

function CatVideo({ pick }: { pick: CatPick }) {
  const streams = useMemo(() => streamsFor(pick), [pick]);
  const [index, setIndex] = useState(0);
  const stream = streams[Math.min(index, streams.length - 1)];
  const hasNext = index < streams.length - 1;
  // A new player per stream: if HLS fails, try DASH, then the silent MP4.
  return (
    <StreamPlayer
      key={`${stream.kind}:${index}`}
      pick={pick}
      stream={stream}
      onFail={hasNext ? () => setIndex((i) => i + 1) : undefined}
    />
  );
}

function StreamPlayer({ pick, stream, onFail }:
  { pick: CatPick; stream: Stream; onFail?: () => void }) {
  const player = useVideoPlayer(stream.source, (p) => {
    p.loop = true;
    p.volume = 1;
    p.muted = true; // autoplay muted, tap to unmute
    p.play();
  });
  const { muted } = useEvent(player, 'mutedChange', { muted: player.muted });
  const { status } = useEvent(player, 'statusChange', { status: player.status });
  const { isPlaying } = useEvent(player, 'playingChange', { isPlaying: player.playing });
  const [firstFrame, setFirstFrame] = useState(false);

  useEventListener(player, 'statusChange', ({ status: s, error }) => {
    if (s === 'error') {
      console.warn(`[CatVideo] ${stream.kind} failed: ${error?.message ?? 'unknown error'}`);
      onFail?.();
    }
  });

  // On Android/iOS the player reports the audio tracks it actually found. If a
  // stream that should have sound loads without any, try the next stream.
  const [loadedWithoutAudio, setLoadedWithoutAudio] = useState(false);
  useEventListener(player, 'sourceLoad', ({ availableAudioTracks }) => {
    if (Platform.OS === 'web' || !stream.audio) return;
    if (availableAudioTracks.length === 0) {
      console.warn(`[CatVideo] ${stream.kind} loaded without audio tracks`);
      if (onFail) onFail();
      // X MP4s carry their own AAC track (checked by the picker). Media3 can
      // list no track for a progressive MP4 whose format has no id, so trust
      // the data and keep the sound button working instead of disabling it.
      else if (!(stream.kind === 'mp4' && pick.mp4HasAudio === true)) setLoadedWithoutAudio(true);
    } else if (player.audioTrack == null) {
      player.audioTrack = availableAudioTracks[0];
    }
  });
  const soundAvailable = stream.audio && !loadedWithoutAudio;

  // Autoplay: on web the <video> element may mount after the setup callback ran,
  // so (re)start playback once the source is ready.
  useEffect(() => {
    if (status === 'readyToPlay' && !isPlaying) player.play();
  }, [status, isPlaying, player]);

  const toggleSound = () => {
    if (!soundAvailable) return;
    if (player.muted) {
      player.muted = false;
      player.volume = 1; // make sure we're not unmuting at volume 0
      if (!player.playing) player.play();
    } else {
      player.muted = true;
    }
  };

  const label = status === 'error'
    ? '⚠️ Video unavailable'
    : !soundAvailable
      ? '🔇 No sound in this clip'
      : muted
        ? pick.audioQuiet ? '🔇 Tap for sound (very quiet clip)' : '🔇 Tap for sound'
        : '🔊 Sound on · tap to mute';

  return (
    <View style={StyleSheet.absoluteFill}>
      {!firstFrame && pick.thumbnail ? (
        <Image source={{ uri: pick.thumbnail }} style={StyleSheet.absoluteFill} contentFit="contain" />
      ) : null}
      <VideoView
        player={player}
        style={StyleSheet.absoluteFill}
        contentFit="contain"
        nativeControls={false}
        playsInline
        onFirstFrameRender={() => setFirstFrame(true)}
      />
      {/* Touch layer drawn ABOVE the native video surface so taps always reach JS. */}
      <Pressable
        style={StyleSheet.absoluteFill}
        onPress={toggleSound}
        disabled={!soundAvailable}
        accessibilityRole="button"
        accessibilityLabel={soundAvailable ? (muted ? 'Unmute video' : 'Mute video') : 'Video without sound'}
        testID="video-sound-toggle"
      >
        <View style={[styles.badge, soundAvailable && muted && styles.badgeCta]}>
          <Text style={styles.badgeText}>{label}</Text>
        </View>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  frame: {
    borderRadius: radius,
    overflow: 'hidden',
    backgroundColor: '#1E1614',
    alignSelf: 'center',
  },
  badge: {
    position: 'absolute',
    right: 12,
    bottom: 12,
    backgroundColor: 'rgba(0,0,0,0.55)',
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  badgeCta: { backgroundColor: 'rgba(224,119,42,0.92)' },
  badgeText: { color: '#fff', fontSize: 13, fontWeight: '700' },
});


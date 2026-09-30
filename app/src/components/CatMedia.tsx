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

function CatVideo({ pick }: { pick: CatPick }) {
  // Reddit's MP4 files are video-only. The DASH manifest carries the audio
  // track, and Android's player (ExoPlayer) can play DASH — so use it there.
  const canUseDash = Platform.OS === 'android' && !!pick.dashUrl && pick.hasAudio === true;
  const [useDash, setUseDash] = useState(canUseDash);
  const source = useMemo<VideoSource>(
    () => (useDash && pick.dashUrl ? { uri: pick.dashUrl, contentType: 'dash' } : { uri: pick.mediaUrl }),
    [useDash, pick.dashUrl, pick.mediaUrl],
  );
  const soundAvailable = useDash || pick.mp4HasAudio === true;

  const player = useVideoPlayer(source, (p) => {
    p.loop = true;
    p.muted = true; // autoplay muted
    p.play();
  });
  const { muted } = useEvent(player, 'mutedChange', { muted: player.muted });
  const { status } = useEvent(player, 'statusChange', { status: player.status });
  const [firstFrame, setFirstFrame] = useState(false);

  const { isPlaying } = useEvent(player, 'playingChange', { isPlaying: player.playing });
  // Autoplay: on web the <video> element may mount after the setup callback ran,
  // so (re)start playback once the source is ready.
  useEffect(() => {
    if (status === 'readyToPlay' && !isPlaying) {
      player.play();
    }
  }, [status, isPlaying, player]);

  useEventListener(player, 'statusChange', ({ status: s }) => {
    if (s === 'error' && useDash) setUseDash(false); // fall back to the silent MP4
  });

  const toggleSound = () => {
    if (!soundAvailable) return;
    player.muted = !player.muted;
    if (!player.playing) player.play();
  };

  return (
    <Pressable style={StyleSheet.absoluteFill} onPress={toggleSound}
      accessibilityRole="button"
      accessibilityLabel={soundAvailable ? (muted ? 'Unmute video' : 'Mute video') : 'Video without sound'}>
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
        pointerEvents="none"
      />
      <View style={styles.badge} pointerEvents="none">
        <Text style={styles.badgeText}>
          {status === 'error'
            ? '⚠️ Video unavailable'
            : soundAvailable
              ? muted ? '🔇 Tap for sound' : '🔊 Sound on'
              : '🔇 No sound in this clip'}
        </Text>
      </View>
    </Pressable>
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
  badgeText: { color: '#fff', fontSize: 13, fontWeight: '600' },
});


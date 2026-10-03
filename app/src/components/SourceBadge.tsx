import { StyleSheet, Text, View } from 'react-native';
import { sourceOf } from '../format';
import type { CatPick } from '../types';

/** Tiny "Reddit" / "X" chip. */
export default function SourceBadge({ pick, small }: { pick: CatPick; small?: boolean }) {
  const src = sourceOf(pick);
  if (src === 'other') return null;
  const x = src === 'x';
  return (
    <View style={[styles.badge, x ? styles.x : styles.reddit, small && styles.small]}
      accessibilityLabel={x ? 'From X' : 'From Reddit'}>
      <Text style={[styles.text, small && styles.smallText]}>{x ? 'X' : 'Reddit'}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: { borderRadius: 999, paddingHorizontal: 9, paddingVertical: 5, alignSelf: 'center' },
  reddit: { backgroundColor: '#FF4500' },
  x: { backgroundColor: '#111111', paddingHorizontal: 10 },
  small: { paddingHorizontal: 7, paddingVertical: 2 },
  text: { color: '#fff', fontWeight: '800', fontSize: 12.5 },
  smallText: { fontSize: 10.5 },
});

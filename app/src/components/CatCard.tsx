import { useState } from 'react';
import { Linking, Platform, Pressable, Share, StyleSheet, Text, View } from 'react-native';
import { creditLine, formatDate, originalUrl, popularityLabel } from '../format';
import SourceBadge from './SourceBadge';
import { colors, radius } from '../theme';
import type { CatPick } from '../types';
import CatMedia from './CatMedia';

export default function CatCard({ pick }: { pick: CatPick }) {
  const [toast, setToast] = useState<string | null>(null);

  const flash = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2500);
  };

  const link = originalUrl(pick);
  const openOriginal = () => Linking.openURL(link).catch(() => flash("Couldn't open the link"));

  const share = async () => {
    const message = `🐱 Cat of the Day (${formatDate(pick.date, 'short')}): "${pick.title}"\n${link}`;
    try {
      if (Platform.OS === 'web') {
        const nav = globalThis.navigator as Navigator | undefined;
        if (nav?.share) {
          await nav.share({ title: 'Cat of the Day', text: message, url: link });
        } else if (nav?.clipboard) {
          await nav.clipboard.writeText(message);
          flash('Link copied to clipboard 📋');
        }
        return;
      }
      await Share.share({ message, url: link, title: 'Cat of the Day' });
    } catch {
      /* user cancelled */
    }
  };

  return (
    <View style={styles.card}>
      <CatMedia pick={pick} />
      <View style={styles.body}>
        <Text style={styles.title}>{pick.title}</Text>
        {pick.blurb ? (
          <View style={styles.blurb}>
            <Text style={styles.blurbText}>{pick.blurb}</Text>
          </View>
        ) : null}
        <View style={styles.row}>
          <View style={styles.pillRow}>
            <SourceBadge pick={pick} />
            <View style={styles.pill}>
              <Text style={styles.pillText}>{popularityLabel(pick)}</Text>
            </View>
          </View>
          <Pressable onPress={share} style={({ pressed }) => [styles.shareBtn, pressed && styles.pressed]}
            accessibilityRole="button" accessibilityLabel="Share this cat">
            <Text style={styles.shareText}>Share ↗</Text>
          </Pressable>
        </View>
        <Pressable onPress={openOriginal} accessibilityRole="link"
          style={({ pressed }) => [styles.credit, pressed && styles.pressed]}>
          <Text style={styles.creditText}>
            {creditLine(pick)} – <Text style={styles.link}>view original</Text>
          </Text>
        </Pressable>
        <Text style={styles.disclaimer}>
          Media belongs to its creator and is shown from the original post. Cat of the Day is not
          affiliated with Reddit or X.
        </Text>
        {toast ? <Text style={styles.toast}>{toast}</Text> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderRadius: radius + 6,
    padding: 10,
    marginHorizontal: 6,
    shadowColor: '#C79770',
    shadowOpacity: 0.18,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 6 },
    elevation: 4,
  },
  body: { paddingHorizontal: 8, paddingTop: 14, paddingBottom: 8, gap: 12 },
  title: { fontSize: 21, lineHeight: 28, fontWeight: '800', color: colors.text },
  blurb: {
    backgroundColor: colors.soft + '80',
    borderLeftWidth: 4,
    borderLeftColor: colors.accent,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginTop: -2,
  },
  blurbText: { color: colors.text, fontSize: 15.5, lineHeight: 22 },
  pillRow: { flexDirection: 'row', alignItems: 'center', gap: 6, flexShrink: 1 },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  pill: {
    backgroundColor: colors.soft,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 999,
    flexShrink: 1,
  },
  pillText: { color: colors.accentDark, fontWeight: '700', fontSize: 14 },
  shareBtn: {
    backgroundColor: colors.accent,
    paddingHorizontal: 16,
    paddingVertical: 9,
    borderRadius: 999,
  },
  shareText: { color: '#fff', fontWeight: '800', fontSize: 15 },
  pressed: { opacity: 0.7 },
  credit: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 14,
    padding: 12,
    backgroundColor: '#FFFBF7',
  },
  creditText: { color: colors.text, fontSize: 14, lineHeight: 20 },
  link: { color: colors.accentDark, fontWeight: '700', textDecorationLine: 'underline' },
  disclaimer: { color: colors.muted, fontSize: 11.5, lineHeight: 16 },
  toast: { color: colors.accentDark, fontWeight: '700', textAlign: 'center' },
});

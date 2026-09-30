import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { colors } from '../theme';

export function Loading({ label = 'Fetching today’s cat…' }: { label?: string }) {
  return (
    <View style={styles.center}>
      <Text style={styles.emoji}>🐾</Text>
      <ActivityIndicator size="large" color={colors.accent} />
      <Text style={styles.muted}>{label}</Text>
    </View>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <View style={styles.center}>
      <Text style={styles.emoji}>😿</Text>
      <Text style={styles.title}>Couldn’t load the cat</Text>
      <Text style={styles.muted}>{message}</Text>
      <Pressable onPress={onRetry} style={({ pressed }) => [styles.btn, pressed && { opacity: 0.7 }]}
        accessibilityRole="button">
        <Text style={styles.btnText}>Try again</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32, gap: 12, minHeight: 400 },
  emoji: { fontSize: 48 },
  title: { fontSize: 20, fontWeight: '800', color: colors.text },
  muted: { color: colors.muted, textAlign: 'center', fontSize: 15 },
  btn: { marginTop: 8, backgroundColor: colors.accent, paddingHorizontal: 22, paddingVertical: 11, borderRadius: 999 },
  btnText: { color: '#fff', fontWeight: '800', fontSize: 16 },
});

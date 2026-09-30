import { Image } from 'expo-image';
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { fetchArchive } from '../api';
import { ErrorState, Loading } from '../components/States';
import { creditLine, formatDate, popularityLabel } from '../format';
import { colors } from '../theme';
import type { CatPick } from '../types';
import { useRemote } from '../useRemote';

export default function ArchiveScreen({ onOpen }: { onOpen: (p: CatPick) => void }) {
  const { data, error, loading, refreshing, refresh, retry } = useRemote(fetchArchive);

  if (loading && !data) return <Loading label="Opening the cat archive…" />;
  if (error && !data) return <ErrorState message={error} onRetry={retry} />;

  return (
    <FlatList
      data={data ?? []}
      keyExtractor={(p) => p.date}
      contentContainerStyle={styles.list}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh}
        tintColor={colors.accent} colors={[colors.accent]} />}
      ListHeaderComponent={<Text style={styles.header}>Past cats of the day</Text>}
      ListEmptyComponent={<Text style={styles.empty}>No cats yet — check back tomorrow! 🐈</Text>}
      ListFooterComponent={
        <Text style={styles.footer}>
          {(data?.length ?? 0) < 60
            ? 'The archive grows by one cat every day (up to 60 days).'
            : 'Showing the last 60 days.'}
        </Text>
      }
      renderItem={({ item }) => <Row pick={item} onPress={() => onOpen(item)} />}
    />
  );
}

function Row({ pick, onPress }: { pick: CatPick; onPress: () => void }) {
  const thumb = pick.thumbnail || (pick.mediaType !== 'video' ? pick.mediaUrl : undefined);
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.row, pressed && { opacity: 0.75 }]}
      accessibilityRole="button" accessibilityLabel={`${formatDate(pick.date)}: ${pick.title}`}>
      <View style={styles.thumbWrap}>
        {thumb ? <Image source={{ uri: thumb }} style={styles.thumb} contentFit="cover" transition={200} />
          : <Text style={{ fontSize: 30 }}>🐱</Text>}
        {pick.mediaType === 'video' ? <Text style={styles.play}>▶</Text> : null}
      </View>
      <View style={styles.rowText}>
        <Text style={styles.date}>{formatDate(pick.date, 'short')}</Text>
        <Text style={styles.title} numberOfLines={2}>{pick.title}</Text>
        <Text style={styles.meta} numberOfLines={1}>{popularityLabel(pick)}</Text>
        <Text style={styles.meta} numberOfLines={1}>{creditLine(pick)}</Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  list: { padding: 14, paddingBottom: 32, gap: 12, flexGrow: 1 },
  header: { fontSize: 22, fontWeight: '800', color: colors.text, marginBottom: 4, marginLeft: 4 },
  empty: { textAlign: 'center', color: colors.muted, marginTop: 40, fontSize: 16 },
  footer: { textAlign: 'center', color: colors.muted, marginTop: 12, fontSize: 12.5 },
  row: {
    flexDirection: 'row',
    gap: 12,
    backgroundColor: colors.card,
    borderRadius: 20,
    padding: 10,
    alignItems: 'center',
    shadowColor: '#C79770',
    shadowOpacity: 0.12,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 3 },
    elevation: 2,
  },
  thumbWrap: {
    width: 84, height: 84, borderRadius: 16, overflow: 'hidden',
    backgroundColor: colors.soft, alignItems: 'center', justifyContent: 'center',
  },
  thumb: { width: '100%', height: '100%' },
  play: {
    position: 'absolute', color: '#fff', fontSize: 22,
    textShadowColor: 'rgba(0,0,0,0.6)', textShadowRadius: 6,
  },
  rowText: { flex: 1, gap: 3 },
  date: { color: colors.accentDark, fontWeight: '800', fontSize: 12.5, textTransform: 'uppercase' },
  title: { color: colors.text, fontWeight: '700', fontSize: 16, lineHeight: 21 },
  meta: { color: colors.muted, fontSize: 12.5 },
});

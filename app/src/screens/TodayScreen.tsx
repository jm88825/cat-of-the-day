import { RefreshControl, ScrollView, StyleSheet, Text } from 'react-native';
import { fetchLatest } from '../api';
import CatCard from '../components/CatCard';
import { ErrorState, Loading } from '../components/States';
import { formatDate } from '../format';
import { colors } from '../theme';
import { useRemote } from '../useRemote';

export default function TodayScreen() {
  const { data, error, loading, refreshing, refresh, retry } = useRemote(fetchLatest);

  return (
    <ScrollView
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh}
        tintColor={colors.accent} colors={[colors.accent]} />}>
      {loading && !data ? (
        <Loading />
      ) : error && !data ? (
        <ErrorState message={error} onRetry={retry} />
      ) : data ? (
        <>
          <Text style={styles.kicker}>{formatDate(data.date)}</Text>
          <CatCard pick={data} />
          <Text style={styles.footer}>A new cat arrives every morning at 9 AM ET · Pull down to refresh</Text>
        </>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 10, paddingBottom: 32, flexGrow: 1 },
  kicker: {
    textAlign: 'center',
    color: colors.muted,
    fontWeight: '700',
    letterSpacing: 0.5,
    marginBottom: 10,
    textTransform: 'uppercase',
    fontSize: 12.5,
  },
  footer: { textAlign: 'center', color: colors.muted, fontSize: 12.5, marginTop: 16 },
});

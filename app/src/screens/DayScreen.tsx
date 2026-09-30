import { ScrollView, StyleSheet, Text } from 'react-native';
import CatCard from '../components/CatCard';
import { formatDate } from '../format';
import { colors } from '../theme';
import type { CatPick } from '../types';

export default function DayScreen({ pick }: { pick: CatPick }) {
  return (
    <ScrollView contentContainerStyle={styles.content}>
      <Text style={styles.kicker}>{formatDate(pick.date)}</Text>
      <CatCard pick={pick} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 10, paddingBottom: 32 },
  kicker: {
    textAlign: 'center', color: colors.muted, fontWeight: '700', letterSpacing: 0.5,
    marginBottom: 10, textTransform: 'uppercase', fontSize: 12.5,
  },
});

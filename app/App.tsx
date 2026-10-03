import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import { BackHandler, Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import ArchiveScreen from './src/screens/ArchiveScreen';
import DayScreen from './src/screens/DayScreen';
import TodayScreen from './src/screens/TodayScreen';
import { colors } from './src/theme';
import type { CatPick } from './src/types';

type Tab = 'today' | 'archive';

// video.twimg.com (X videos) returns 403 when a browser sends a non-X Referer.
// Native players send none; on web, tell the browser not to send one either.
if (Platform.OS === 'web' && typeof document !== 'undefined'
  && !document.querySelector('meta[name="referrer"]')) {
  const meta = document.createElement('meta');
  meta.name = 'referrer';
  meta.content = 'no-referrer';
  document.head.appendChild(meta);
}

export default function App() {
  const [tab, setTab] = useState<Tab>('today');
  const [openDay, setOpenDay] = useState<CatPick | null>(null);

  // Android hardware back: close a past day, then return to Today.
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (openDay) { setOpenDay(null); return true; }
      if (tab !== 'today') { setTab('today'); return true; }
      return false;
    });
    return () => sub.remove();
  }, [openDay, tab]);

  const switchTab = (t: Tab) => { setOpenDay(null); setTab(t); };

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.safe} edges={['top', 'left', 'right', 'bottom']}>
        <StatusBar style="dark" />
        <View style={styles.header}>
          {openDay ? (
            <Pressable onPress={() => setOpenDay(null)} hitSlop={12} accessibilityRole="button"
              accessibilityLabel="Back to archive" style={styles.back}>
              <Text style={styles.backText}>‹ Archive</Text>
            </Pressable>
          ) : null}
          <Text style={styles.brand}>🐱 Cat of the Day</Text>
        </View>

        <View style={styles.body}>
          {openDay ? <DayScreen pick={openDay} />
            : tab === 'today' ? <TodayScreen />
            : <ArchiveScreen onOpen={setOpenDay} />}
        </View>

        <View style={styles.tabs} accessibilityRole="tablist">
          <TabButton label="Today" icon="☀️" active={tab === 'today' && !openDay} onPress={() => switchTab('today')} />
          <TabButton label="Archive" icon="📚" active={tab === 'archive'} onPress={() => switchTab('archive')} />
        </View>
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

function TabButton({ label, icon, active, onPress }:
  { label: string; icon: string; active: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={[styles.tab, active && styles.tabActive]}
      accessibilityRole="tab" accessibilityState={{ selected: active }}>
      <Text style={styles.tabIcon}>{icon}</Text>
      <Text style={[styles.tabLabel, active && styles.tabLabelActive]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: { height: 54, alignItems: 'center', justifyContent: 'center' },
  brand: { fontSize: 22, fontWeight: '900', color: colors.text, letterSpacing: 0.2 },
  back: { position: 'absolute', left: 14, top: 0, bottom: 0, justifyContent: 'center' },
  backText: { color: colors.accentDark, fontWeight: '800', fontSize: 16 },
  body: { flex: 1 },
  tabs: {
    flexDirection: 'row',
    gap: 10,
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: '#FFFDFB',
  },
  tab: {
    flex: 1, flexDirection: 'row', gap: 6, alignItems: 'center', justifyContent: 'center',
    paddingVertical: 10, borderRadius: 999,
  },
  tabActive: { backgroundColor: colors.soft },
  tabIcon: { fontSize: 16 },
  tabLabel: { fontSize: 15, fontWeight: '700', color: colors.muted },
  tabLabelActive: { color: colors.accentDark },
});

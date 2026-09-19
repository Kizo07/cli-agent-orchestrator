import { useEffect, useState, Suspense } from 'react'
import { api, getControlToken, setControlToken } from './api'
import { useStore } from './store'
import { ErrorBoundary } from './components/ErrorBoundary'
import { DashboardHome } from './components/DashboardHome'
import { AgentPanel } from './components/AgentPanel'
import { FlowsPanel } from './components/FlowsPanel'
import { MemoryPanel } from './components/MemoryPanel'
import { ProfilesPanel } from './components/ProfilesPanel'
import { SettingsPanel } from './components/SettingsPanel'
import { WorkflowsPanel } from './components/WorkflowsPanel'
import { CaoMark } from './components/CaoMark'
import { Bot, Home, Clock, Settings, Brain, Workflow, CheckCircle, XCircle, Info, Wifi, WifiOff, Package } from 'lucide-react'
import { AppShell, Box, Button, Group, Notification, PasswordInput, Tabs, Text, Title } from '@mantine/core'

type TabKey = 'home' | 'profiles' | 'agents' | 'flows' | 'settings' | 'memory' | 'workflows'

// Profiles sits between Home and Agents (#510): browsing/authoring profiles
// precedes launching agents, and AgentPanel stays the launch picker. This was
// a one-time Alt+N renumbering of the tabs after it; Workflows + Memory remain
// appended last (Memory is conditional, so keeping it last stops the numbering
// of the always-visible tabs shifting with the memory backend's status).
const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: 'home', label: 'Home', icon: <Home size={16} /> },
  { key: 'profiles', label: 'Profiles', icon: <Package size={16} /> },
  { key: 'agents', label: 'Agents', icon: <Bot size={16} /> },
  { key: 'flows', label: 'Flows', icon: <Clock size={16} /> },
  { key: 'settings', label: 'Settings', icon: <Settings size={16} /> },
  { key: 'memory', label: 'Memory', icon: <Brain size={16} /> },
  { key: 'workflows', label: 'Workflows', icon: <Workflow size={16} /> },
]

const SNACKBAR_COLORS = { success: 'green', error: 'red', info: 'blue' } as const
const SNACKBAR_ICONS = {
  success: <CheckCircle size={18} />,
  error: <XCircle size={18} />,
  info: <Info size={18} />,
}

function Snackbar() {
  const { snackbar, hideSnackbar } = useStore()

  useEffect(() => {
    if (snackbar) {
      const timer = setTimeout(hideSnackbar, 3000)
      return () => clearTimeout(timer)
    }
  }, [snackbar, hideSnackbar])

  if (!snackbar) return null

  return (
    <Box className="fixed bottom-4 right-4 z-50">
      <Notification
        role="alert"
        color={SNACKBAR_COLORS[snackbar.type]}
        icon={SNACKBAR_ICONS[snackbar.type]}
        withBorder
        withCloseButton={false}
        title={snackbar.message}
      />
    </Box>
  )
}

function TokenGate({ onSaved }: { onSaved: () => void }) {
  const [value, setValue] = useState('')

  const save = () => {
    if (value.trim()) {
      setControlToken(value)
      onSaved()
    }
  }

  return (
    <Box className="border-b border-amber-700/50 bg-amber-900/20">
      <Group mx="auto" maw={1280} px="lg" py="xs" gap="sm" wrap="wrap">
        <Info size={16} className="shrink-0 self-center text-amber-400" />
        <Text size="sm" className="shrink-0 self-center text-amber-200">
          Control token required — paste CAO_CONTROL_TOKEN
        </Text>
        <PasswordInput
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') save()
          }}
          placeholder="control token"
          className="min-w-0 flex-1 max-w-sm"
          size="xs"
        />
        <Button onClick={save} color="green" size="xs">
          Connect
        </Button>
      </Group>
    </Box>
  )
}

export default function App() {
  const [tab, setTab] = useState<TabKey>('home')

  // The ONLY way any surface changes tabs. Refuses while an in-flight
  // interaction (an authoring modal's save) holds the navigation lock:
  // switching tabs unmounts the panel and its modal, so a deferred
  // validation/write rejection would land on an unmounted component and the
  // unsaved draft would be unrecoverable (#692 review round 7). Reads the
  // lock through getState() so the keydown listener never closes over a
  // stale value.
  const requestTabChange = (t: TabKey) => {
    if (useStore.getState().navLockCount > 0) return
    setTab(t)
  }
  // Default false (fail-closed): a dead backend hides the tab rather than showing a broken panel
  const [memoryEnabled, setMemoryEnabled] = useState(false)
  const [authNeeded, setAuthNeeded] = useState(() => !getControlToken())
  const { sessions, connected, fetchSessions } = useStore()
  // Subscribed (not just read via getState) so the tab strip re-renders
  // and visibly reflects the refusal while a save owns navigation --
  // matching the modal's own disabled Close/Cancel/mode-tab affordances
  // rather than silently ignoring clicks.
  const navLocked = useStore(s => s.navLockCount > 0)

  const visibleTabs = TABS.filter((t) => t.key !== 'memory' || memoryEnabled)

  useEffect(() => {
    fetchSessions()
    api
      .getMemoryStatus()
      .then((s) => setMemoryEnabled(s.enabled))
      .catch(() => {})
    const interval = setInterval(fetchSessions, 10000)
    return () => clearInterval(interval)
  }, [])

  // Show the token gate whenever any API call comes back 401 (plan V2 17.2).
  useEffect(() => {
    const onAuthRequired = () => setAuthNeeded(true)
    window.addEventListener('cao-auth-required', onAuthRequired)
    return () => window.removeEventListener('cao-auth-required', onAuthRequired)
  }, [])

  // Agent-system fork: Mission Control seeds the token (URL fragment or
  // postMessage) — dismiss an already-rendered gate and refetch.
  useEffect(() => {
    const onToken = () => {
      setAuthNeeded(false)
      fetchSessions()
      api
        .getMemoryStatus()
        .then((s) => setMemoryEnabled(s.enabled))
        .catch(() => {})
    }
    window.addEventListener('cao-token-provided', onToken)
    return () => window.removeEventListener('cao-token-provided', onToken)
  }, [])

  // The nav lock stops IN-APP navigation from unmounting an in-flight
  // save, but browser chrome (reload, tab close) bypasses it entirely --
  // the same draft-loss path one level up. While the lock is held, ask
  // the browser to confirm leaving.
  useEffect(() => {
    if (!navLocked) return
    const handler = (e: BeforeUnloadEvent) => { e.preventDefault() }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [navLocked])

  // Keyboard shortcuts: Alt+1-N over the visible tabs
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.altKey && e.key >= '1' && e.key <= String(visibleTabs.length)) {
        e.preventDefault()
        requestTabChange(visibleTabs[parseInt(e.key) - 1].key)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [memoryEnabled])

  return (
    <AppShell header={{ height: 56 }} padding={0} className="min-h-screen bg-[#0f0f14]">
      <AppShell.Header withBorder={false} className="border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm">
        <Group h="100%" mx="auto" maw={1280} px="lg" justify="space-between" gap="md" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <CaoMark size={32} />
            <Title order={1} size="lg" className="text-white">
              CLI Agent Orchestrator
            </Title>
          </Group>
          <Group gap="md" wrap="nowrap">
            <Text size="xs" c="dimmed">
              {sessions.length} session{sessions.length !== 1 ? 's' : ''}
            </Text>
            <Group gap={6} wrap="nowrap" title={connected ? 'Connected' : 'Disconnected'}>
              {connected ? (
                <Wifi size={14} className="text-emerald-400" />
              ) : (
                <WifiOff size={14} className="text-red-400" />
              )}
              <Text size="xs" c={connected ? 'var(--mantine-color-success-4)' : 'var(--mantine-color-danger-4)'}>
                {connected ? 'Live' : 'Offline'}
              </Text>
            </Group>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Main>
        {/* Control-token gate (agent-system fork, plan V2 17.2) */}
        {authNeeded && (
          <TokenGate
            onSaved={() => {
              setAuthNeeded(false)
              fetchSessions()
              api
                .getMemoryStatus()
                .then((s) => setMemoryEnabled(s.enabled))
                .catch(() => {})
            }}
          />
        )}

        <Tabs value={tab} onChange={(value) => value && requestTabChange(value as TabKey)} keepMounted={false} variant="pills">
          <Box className="border-b border-gray-800">
            <Tabs.List mx="auto" maw={1280} px="lg" className="flex gap-1 py-2" mb={0}>
              {visibleTabs.map((t, i) => (
                <Tabs.Tab
                  key={t.key}
                  value={t.key}
                  leftSection={t.icon}
                  disabled={navLocked && tab !== t.key}
                  aria-disabled={navLocked && tab !== t.key}
                  title={navLocked && tab !== t.key ? 'Finish or cancel the in-flight save first' : `Alt+${i + 1}`}
                  className="rounded-lg text-sm font-medium"
                  rightSection={
                    t.key === 'agents' && sessions.length > 0 ? (
                      <span className={tab === t.key ? 'rounded-full bg-white/20 px-1.5 py-0.5 text-xs' : 'rounded-full bg-gray-700 px-1.5 py-0.5 text-xs'}>{sessions.length}</span>
                    ) : undefined
                  }
                >
                  {t.label}
                </Tabs.Tab>
              ))}
            </Tabs.List>
          </Box>

          {visibleTabs.map((t) => (
            <Tabs.Panel key={t.key} value={t.key}>
              <Box maw={1280} mx="auto" px="lg" py="lg">
                <ErrorBoundary>
                  <Suspense
                    fallback={
                      <Box className="py-12 text-center">
                        <Text size="sm" c="dimmed">
                          Loading...
                        </Text>
                      </Box>
                    }
                  >
                    {t.key === 'home' && <DashboardHome onNavigate={(k) => requestTabChange(k as TabKey)} />}
                    {t.key === 'profiles' && <ProfilesPanel />}
                    {t.key === 'agents' && <AgentPanel />}
                    {t.key === 'flows' && <FlowsPanel />}
                    {t.key === 'settings' && <SettingsPanel />}
                    {t.key === 'memory' && <MemoryPanel />}
                    {t.key === 'workflows' && <WorkflowsPanel />}
                  </Suspense>
                </ErrorBoundary>
              </Box>
            </Tabs.Panel>
          ))}
        </Tabs>
      </AppShell.Main>

      <Snackbar />
    </AppShell>
  )
}

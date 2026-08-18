import { useEffect, useState, Suspense } from 'react'
import { api, getControlToken, setControlToken } from './api'
import { useStore } from './store'
import { ErrorBoundary } from './components/ErrorBoundary'
import { DashboardHome } from './components/DashboardHome'
import { AgentPanel } from './components/AgentPanel'
import { FlowsPanel } from './components/FlowsPanel'
import { MemoryPanel } from './components/MemoryPanel'
import { SettingsPanel } from './components/SettingsPanel'
import { Bot, Home, Clock, Settings, Brain, CheckCircle, XCircle, Info, Wifi, WifiOff } from 'lucide-react'
import { AppShell, Box, Button, Group, Notification, PasswordInput, Tabs, Text, Title } from '@mantine/core'

type TabKey = 'home' | 'agents' | 'flows' | 'settings' | 'memory'

// Memory appended last so Alt+N numbering of existing tabs never shifts
const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: 'home', label: 'Home', icon: <Home size={16} /> },
  { key: 'agents', label: 'Agents', icon: <Bot size={16} /> },
  { key: 'flows', label: 'Flows', icon: <Clock size={16} /> },
  { key: 'settings', label: 'Settings', icon: <Settings size={16} /> },
  { key: 'memory', label: 'Memory', icon: <Brain size={16} /> },
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
  // Default false (fail-closed): a dead backend hides the tab rather than showing a broken panel
  const [memoryEnabled, setMemoryEnabled] = useState(false)
  const [authNeeded, setAuthNeeded] = useState(() => !getControlToken())
  const { sessions, connected, fetchSessions } = useStore()

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

  // Keyboard shortcuts: Alt+1-N over the visible tabs
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.altKey && e.key >= '1' && e.key <= String(visibleTabs.length)) {
        e.preventDefault()
        setTab(visibleTabs[parseInt(e.key) - 1].key)
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
            <Box className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500 to-emerald-700">
              <Bot size={18} className="text-white" />
            </Box>
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

        <Tabs value={tab} onChange={(value) => value && setTab(value as TabKey)} keepMounted={false} variant="pills">
          <Box className="border-b border-gray-800">
            <Tabs.List mx="auto" maw={1280} px="lg" className="flex gap-1 py-2" mb={0}>
              {visibleTabs.map((t, i) => (
                <Tabs.Tab
                  key={t.key}
                  value={t.key}
                  leftSection={t.icon}
                  title={`Alt+${i + 1}`}
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
                    {t.key === 'home' && <DashboardHome onNavigate={(k) => setTab(k as TabKey)} />}
                    {t.key === 'agents' && <AgentPanel />}
                    {t.key === 'flows' && <FlowsPanel />}
                    {t.key === 'settings' && <SettingsPanel />}
                    {t.key === 'memory' && <MemoryPanel />}
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

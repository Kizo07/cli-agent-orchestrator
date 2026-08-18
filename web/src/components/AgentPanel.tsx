import { useState, useEffect, useRef } from 'react'
import { useStore } from '../store'
import { api, AgentProfileInfo, ProviderInfo } from '../api'
import { Bot, Play, Trash2, ChevronRight, Terminal as TermIcon, Monitor, Package, FolderOpen, Tag, Search, Mail, Plus, LogOut, Send, FileText } from 'lucide-react'
import { ActionIcon, Button, Group, Modal, TextInput, UnstyledButton } from '@mantine/core'
import { TerminalView } from './TerminalView'
import { ConfirmModal } from './ConfirmModal'
import { InboxPanel } from './InboxPanel'
import { CustomSelect, SelectOption } from './CustomSelect'
import { TerminalMeta } from '../api'
import { StatusBadge } from './StatusBadge'
import { OutputViewer } from './OutputViewer'

export const FALLBACK_PROVIDERS = ['kiro_cli', 'claude_code', 'q_cli', 'codex', 'gemini_cli', 'hermes', 'kimi_cli', 'copilot_cli', 'opencode_cli', 'cursor_cli']

const SOURCE_LABELS: Record<string, string> = {
  'built-in': 'Built-in',
  'local': 'Local',
  'kiro': 'Kiro',
  'q_cli': 'Q CLI',
  'opencode_cli': 'OpenCode',
}

export function AgentPanel() {
  const { sessions, fetchSessions, activeSession, activeSessionDetail, selectSession, createSession, deleteSession, terminalStatuses, setTerminalStatus } = useStore()
  const [provider, setProvider] = useState('kiro_cli')
  const [profile, setProfile] = useState('')
  const [creating, setCreating] = useState(false)
  // Synchronous in-flight lock: prevents a second submit (rapid double-click or
  // Enter in the form inputs, which bypass the button's disabled state) from
  // firing before the `creating` state re-renders and creating a duplicate session.
  const creatingRef = useRef(false)
  const [liveTerminal, setLiveTerminal] = useState<{ id: string; provider?: string; agentProfile?: string | null } | null>(null)
  const [profiles, setProfiles] = useState<AgentProfileInfo[]>([])
  const [loadingProfiles, setLoadingProfiles] = useState(true)
  const [providers, setProviders] = useState<ProviderInfo[]>([])

  useEffect(() => {
    api.listProviders()
      .then(p => {
        setProviders(p)
        // Default to first installed provider
        const firstInstalled = p.find(prov => prov.installed)
        if (firstInstalled) setProvider(firstInstalled.name)
      })
      .catch(() => {})
  }, [])
  const [pendingClose, setPendingClose] = useState<TerminalMeta | null>(null)
  const [closingTerminal, setClosingTerminal] = useState<string | null>(null)
  const [sessionSearch, setSessionSearch] = useState('')
  const [inboxTerminalId, setInboxTerminalId] = useState<string | null>(null)
  const [workingDirectory, setWorkingDirectory] = useState('')
  const [sessionName, setSessionName] = useState('')
  const [terminalWorkDirs, setTerminalWorkDirs] = useState<Record<string, string | null>>({})
  const [showAddAgent, setShowAddAgent] = useState(false)
  const [addProvider, setAddProvider] = useState('kiro_cli')
  const [addProfile, setAddProfile] = useState('')
  const [addWorkDir, setAddWorkDir] = useState('')
  const [addingAgent, setAddingAgent] = useState(false)
  const [pendingExit, setPendingExit] = useState<TerminalMeta | null>(null)
  const [exitingTerminal, setExitingTerminal] = useState<string | null>(null)
  const [sendInputOpen, setSendInputOpen] = useState<Record<string, boolean>>({})
  const [sendInputValues, setSendInputValues] = useState<Record<string, string>>({})
  const [sendingInput, setSendingInput] = useState<string | null>(null)
  const { showSnackbar } = useStore()
  const [outputTerminalId, setOutputTerminalId] = useState<string | null>(null)
  const [showSpawnModal, setShowSpawnModal] = useState(false)

  const handleDeleteTerminal = async () => {
    if (!pendingClose) return
    const id = pendingClose.id
    setClosingTerminal(id)
    try {
      await api.deleteTerminal(id)
      if (liveTerminal?.id === id) setLiveTerminal(null)
      if (activeSession) await selectSession(activeSession)
      showSnackbar({ type: 'success', message: `Terminal ${id} closed — tmux window killed` })
    } catch {
      showSnackbar({ type: 'error', message: `Failed to close terminal ${id}` })
    }
    setClosingTerminal(null)
    setPendingClose(null)
  }

  const handleExitTerminal = async () => {
    if (!pendingExit) return
    const id = pendingExit.id
    setExitingTerminal(id)
    try {
      await api.exitTerminal(id)
      if (activeSession) await selectSession(activeSession)
      showSnackbar({ type: 'success', message: `Graceful exit sent to terminal ${id}` })
    } catch {
      showSnackbar({ type: 'error', message: `Failed to send exit to terminal ${id}` })
    }
    setExitingTerminal(null)
    setPendingExit(null)
  }

  const handleSendInput = async (terminalId: string) => {
    const message = (sendInputValues[terminalId] || '').trim()
    if (!message) return
    setSendingInput(terminalId)
    try {
      await api.sendInput(terminalId, message)
      setSendInputValues(prev => ({ ...prev, [terminalId]: '' }))
      showSnackbar({ type: 'success', message: `Message sent to terminal ${terminalId}` })
    } catch {
      showSnackbar({ type: 'error', message: `Failed to send message to terminal ${terminalId}` })
    }
    setSendingInput(null)
  }

  useEffect(() => {
    api.listProfiles()
      .then(p => { setProfiles(p); setLoadingProfiles(false) })
      .catch(() => setLoadingProfiles(false))
  }, [])

  useEffect(() => {
    if (activeSession) {
      selectSession(activeSession)
      const interval = setInterval(() => selectSession(activeSession), 5000)
      return () => clearInterval(interval)
    }
  }, [activeSession])

  // Poll terminal statuses for visible terminals in the session detail
  useEffect(() => {
    if (!activeSessionDetail?.terminals.length) return
    const terminalIds = activeSessionDetail.terminals.map(t => t.id)
    const fetchStatuses = () => {
      terminalIds.forEach(id => {
        api.getTerminalStatus(id)
          .then(status => { if (status) setTerminalStatus(id, status) })
          .catch(() => {})
      })
    }
    fetchStatuses()
    const interval = setInterval(fetchStatuses, 3000)
    return () => clearInterval(interval)
  }, [activeSessionDetail?.terminals.map(t => t.id).join(',')])

  const handleCreate = async () => {
    if (creatingRef.current || !profile.trim()) return
    creatingRef.current = true
    setCreating(true)
    try {
      await createSession(provider, profile.trim(), workingDirectory.trim() || undefined, sessionName.trim() || undefined)
      setShowSpawnModal(false)
      setProfile('')
      setWorkingDirectory('')
      setSessionName('')
    } finally {
      setCreating(false)
      creatingRef.current = false
    }
  }

  const openTerminal = (terminalId: string, provider?: string, agentProfile?: string | null) => {
    setLiveTerminal({ id: terminalId, provider, agentProfile })
  }

  const [attachFocusSignal, setAttachFocusSignal] = useState(0)
  const [attaching, setAttaching] = useState<string | null>(null)

  // Attach button: open the session's tmux-backed terminal in the dashboard.
  // If that terminal is already open, just re-focus it (no remount, no
  // reconnect — the PTY stream and scrollback stay intact).
  const attachSession = async (s: { id: string; name: string }) => {
    setAttaching(s.id)
    try {
      const detail = await api.getSession(s.id)
      const terminals = [...detail.terminals]
      if (!terminals.length) {
        showSnackbar({ type: 'error', message: `${s.name || s.id} has no terminals to attach` })
        return
      }
      // Prefer the most recently active terminal in the session
      terminals.sort((a, b) => (b.last_active || '').localeCompare(a.last_active || ''))
      const target = terminals[0]
      if (liveTerminal && terminals.some(t => t.id === liveTerminal.id)) {
        setAttachFocusSignal(n => n + 1)  // already open — take the user there
        return
      }
      setLiveTerminal({ id: target.id, provider: target.provider, agentProfile: target.agent_profile })
    } catch (e: any) {
      showSnackbar({ type: 'error', message: e.message || 'Failed to attach to session' })
    } finally {
      setAttaching(null)
    }
  }

  // Fetch working directories for terminals in session detail
  useEffect(() => {
    if (!activeSessionDetail?.terminals.length) return
    activeSessionDetail.terminals.forEach(t => {
      if (terminalWorkDirs[t.id] === undefined) {
        api.getWorkingDirectory(t.id)
          .then(res => setTerminalWorkDirs(prev => ({ ...prev, [t.id]: res.working_directory })))
          .catch(() => setTerminalWorkDirs(prev => ({ ...prev, [t.id]: null })))
      }
    })
  }, [activeSessionDetail?.terminals.map(t => t.id).join(',')])

  const handleAddAgent = async () => {
    if (!addProfile.trim() || !activeSession) return
    setAddingAgent(true)
    try {
      await api.addTerminalToSession(activeSession, addProvider, addProfile.trim(), addWorkDir.trim() || undefined)
      showSnackbar({ type: 'success', message: 'Agent added to session' })
      setShowAddAgent(false)
      setAddProfile('')
      setAddWorkDir('')
      if (activeSession) await selectSession(activeSession)
    } catch (e: any) {
      showSnackbar({ type: 'error', message: e.message || 'Failed to add agent' })
    }
    setAddingAgent(false)
  }

  // Group profiles by source
  const profilesBySource = profiles.reduce<Record<string, AgentProfileInfo[]>>((acc, p) => {
    const key = p.source || 'unknown'
    if (!acc[key]) acc[key] = []
    acc[key].push(p)
    return acc
  }, {})

  return (
    <div className="space-y-6">
      {/* Sessions List */}
      <div className="bg-gray-800/60 border border-gray-700/50 rounded-xl p-5">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">
            Sessions ({sessions.length})
          </h3>
          <div className="flex items-center gap-2">
            {sessions.length > 3 && (
              <div className="relative">
                <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500" />
                <input
                  type="text"
                  value={sessionSearch}
                  onChange={e => setSessionSearch(e.target.value)}
                  placeholder="Filter sessions..."
                  className="bg-gray-900 border border-gray-700 text-gray-200 text-xs rounded-lg pl-8 pr-3 py-1.5 w-48 focus:border-emerald-500 focus:outline-none"
                />
              </div>
            )}
            <Button onClick={() => setShowSpawnModal(true)} leftSection={<Plus size={14} />}>
              Spawn Agent
            </Button>
          </div>
        </div>
        <p className="text-xs text-gray-500 mb-4">
          A session is a workspace where agents collaborate. Each session can have multiple agents that communicate via messages. Click a session to see its agents.
        </p>
        {sessions.length === 0 ? (
          <p className="text-gray-500 text-sm">No active sessions. Spawn an agent above to create one.</p>
        ) : (
          <div className="space-y-2">
            {sessions.filter(s => !sessionSearch || s.id.includes(sessionSearch) || s.name.includes(sessionSearch)).map(s => (
              <div
                key={s.id}
                className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ${
                  activeSession === s.id ? 'bg-emerald-900/30 border border-emerald-700/50' : 'bg-gray-900/50 border border-gray-700/30 hover:bg-gray-800/80'
                }`}
                onClick={() => selectSession(activeSession === s.id ? null : s.id)}
              >
                <div className="flex items-center gap-3">
                  <Bot size={16} className="text-emerald-400" />
                  <span className="text-sm text-gray-200 font-mono">{s.id}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${s.status === 'active' ? 'bg-emerald-900/50 text-emerald-400' : 'bg-gray-700 text-gray-400'}`}>
                    {s.status}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    size="xs"
                    variant="light"
                    onClick={(e) => { e.stopPropagation(); attachSession(s) }}
                    disabled={attaching === s.id}
                    title="Attach to this session's terminal (opens it, or focuses it if already open)"
                    leftSection={<TermIcon size={12} />}
                  >
                    {attaching === s.id ? 'Attaching…' : 'Attach'}
                  </Button>
                  <ActionIcon
                    variant="subtle"
                    color="gray"
                    onClick={(e) => { e.stopPropagation(); deleteSession(s.id) }}
                    title="Delete session"
                  >
                    <Trash2 size={14} />
                  </ActionIcon>
                  <ChevronRight size={14} className={`text-gray-500 transition-transform ${activeSession === s.id ? 'rotate-90' : ''}`} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Session Detail */}
      {activeSessionDetail && (
        <div className="bg-gray-800/60 border border-gray-700/50 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">
              Terminals in {activeSession}
            </h3>
            <Button
              size="xs"
              variant="default"
              onClick={() => setShowAddAgent(!showAddAgent)}
              title="Add another agent to this session so they can collaborate"
              leftSection={<Plus size={14} />}
            >
              Add Agent
            </Button>
          </div>

          {/* Add Agent Inline Form */}
          {showAddAgent && (
            <div className="mb-4 p-4 bg-gray-900/70 border border-gray-700/50 rounded-lg space-y-3">
              <p className="text-xs text-gray-500">
                Add another agent to this session. Agents in the same session can send messages to each other and coordinate on tasks. A supervisor can delegate work to agents you add here.
              </p>
              <div className="flex gap-3 items-end flex-wrap">
                <div className="min-w-[160px]">
                  <label className="block text-xs text-gray-500 mb-1">Provider</label>
                  <CustomSelect
                    value={addProvider}
                    onChange={setAddProvider}
                    placeholder="Select provider..."
                    options={(providers.length > 0 ? providers : FALLBACK_PROVIDERS.map(n => ({ name: n, binary: '', installed: true }))).map(p => ({
                      value: p.name,
                      label: p.name.replace(/_/g, ' '),
                      sublabel: !p.installed ? 'Not installed' : undefined,
                      disabled: !p.installed,
                    }))}
                  />
                </div>
                <div className="flex-1 min-w-[180px]">
                  <label className="block text-xs text-gray-500 mb-1">Agent Profile</label>
                  {profiles.length > 0 ? (
                    <CustomSelect
                      value={addProfile}
                      onChange={setAddProfile}
                      placeholder="Select a profile..."
                      options={profiles.map(p => ({
                        value: p.name,
                        label: p.name,
                        sublabel: p.description || undefined,
                        group: SOURCE_LABELS[p.source] || p.source,
                      }))}
                    />
                  ) : (
                    <TextInput
                      value={addProfile}
                      onChange={(e) => setAddProfile(e.target.value)}
                      placeholder="e.g. developer, reviewer"
                    />
                  )}
                </div>
                <Button
                  onClick={handleAddAgent}
                  disabled={!addProfile.trim() || addingAgent}
                  leftSection={<Plus size={14} />}
                >
                  {addingAgent ? 'Adding...' : 'Add'}
                </Button>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Working Directory</label>
                <TextInput
                  value={addWorkDir}
                  onChange={(e) => setAddWorkDir(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddAgent()}
                  placeholder="/path/to/project (optional)"
                  leftSection={<FolderOpen size={14} className="text-gray-500" />}
                  styles={{ input: { fontFamily: 'var(--mantine-font-family-monospace)' } }}
                />
              </div>
            </div>
          )}

          <div className="space-y-2">
            {activeSessionDetail.terminals.map(t => (
              <div key={t.id} className="bg-gray-900/50 border border-gray-700/30 rounded-lg p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <TermIcon size={14} className="text-gray-400" />
                    <span className="text-sm font-mono text-gray-300">{t.id}</span>
                    <StatusBadge status={terminalStatuses[t.id] || null} />
                    <span className="text-xs text-gray-500">{t.provider}</span>
                    {t.agent_profile && <span className="text-xs text-emerald-400">{t.agent_profile}</span>}
                  </div>
                  <div className="flex items-center gap-2">
                    <Button size="xs" variant="default" onClick={() => setInboxTerminalId(t.id)} leftSection={<Mail size={14} />} title="View inbox">Inbox</Button>
                    <Button size="xs" onClick={() => openTerminal(t.id, t.provider, t.agent_profile)} leftSection={<Monitor size={14} />} title="Open live terminal">Open Terminal</Button>
                    <Button size="xs" variant="default" onClick={() => setOutputTerminalId(t.id)} leftSection={<FileText size={14} />} title="View output">Output</Button>
                    <Button size="xs" color="warning" onClick={() => setPendingExit(t as TerminalMeta)} disabled={exitingTerminal === t.id} leftSection={<LogOut size={14} />} title="Graceful exit">
                      {exitingTerminal === t.id ? 'Exiting...' : 'Graceful Exit'}
                    </Button>
                    <Button size="xs" color="danger" onClick={() => setPendingClose(t as TerminalMeta)} disabled={closingTerminal === t.id} leftSection={<Trash2 size={14} />} title="Close terminal">
                      {closingTerminal === t.id ? 'Closing...' : 'Close'}
                    </Button>
                  </div>
                </div>
                {/* Working Directory Display */}
                {terminalWorkDirs[t.id] && (
                  <div className="flex items-center gap-1.5" title={terminalWorkDirs[t.id]!}>
                    <FolderOpen size={12} className="text-gray-600 shrink-0" />
                    <span className="text-xs font-mono text-gray-500 truncate max-w-[400px]">{terminalWorkDirs[t.id]}</span>
                  </div>
                )}
                {/* Quick Send Input */}
                {!sendInputOpen[t.id] ? (
                  <button
                    onClick={() => setSendInputOpen(prev => ({ ...prev, [t.id]: true }))}
                    className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
                  >
                    Message agent...
                  </button>
                ) : (
                  <Group gap="xs" wrap="nowrap">
                    <TextInput
                      className="flex-1"
                      size="xs"
                      value={sendInputValues[t.id] || ''}
                      onChange={(e) => setSendInputValues(prev => ({ ...prev, [t.id]: e.target.value }))}
                      onKeyDown={(e) => { if (e.key === 'Enter') handleSendInput(t.id) }}
                      placeholder="Type a message..."
                      autoFocus
                    />
                    <Button
                      size="xs"
                      onClick={() => handleSendInput(t.id)}
                      disabled={sendingInput === t.id || !(sendInputValues[t.id] || '').trim()}
                      leftSection={<Send size={12} />}
                    >
                      {sendingInput === t.id ? 'Sending...' : 'Send'}
                    </Button>
                  </Group>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Inbox Panel */}
      {inboxTerminalId && (
        <InboxPanel terminalId={inboxTerminalId} onClose={() => setInboxTerminalId(null)} />
      )}

      {/* Live Terminal */}
      {liveTerminal && (
        <TerminalView
          terminalId={liveTerminal.id}
          provider={liveTerminal.provider}
          agentProfile={liveTerminal.agentProfile}
          focusSignal={attachFocusSignal}
          onClose={() => setLiveTerminal(null)}
        />
      )}

      {/* Output Viewer Modal */}
      {outputTerminalId && (
        <OutputViewer
          terminalId={outputTerminalId}
          onClose={() => setOutputTerminalId(null)}
        />
      )}

      {/* Close Confirmation Modal */}
      <ConfirmModal
        open={!!pendingClose}
        title="Close Terminal"
        message="This will kill the tmux window and terminate the agent process. This action cannot be undone."
        details={pendingClose ? [
          { label: 'Terminal ID', value: pendingClose.id },
          { label: 'Provider', value: pendingClose.provider },
          { label: 'Profile', value: pendingClose.agent_profile || 'none' },
          { label: 'Session', value: pendingClose.tmux_session },
        ] : []}
        confirmLabel="Close Terminal"
        variant="danger"
        loading={!!closingTerminal}
        onConfirm={handleDeleteTerminal}
        onCancel={() => setPendingClose(null)}
      />

      {/* Graceful Exit Confirmation Modal */}
      <ConfirmModal
        open={!!pendingExit}
        title="Graceful Exit"
        message="This will send the provider-specific exit command (e.g., /exit). The agent will shut down gracefully."
        details={pendingExit ? [
          { label: 'Terminal ID', value: pendingExit.id },
          { label: 'Provider', value: pendingExit.provider },
          { label: 'Profile', value: pendingExit.agent_profile || 'none' },
          { label: 'Session', value: pendingExit.tmux_session },
        ] : []}
        confirmLabel="Send Exit"
        variant="warning"
        loading={!!exitingTerminal}
        onConfirm={handleExitTerminal}
        onCancel={() => setPendingExit(null)}
      />

      <Modal
        opened={showSpawnModal}
        onClose={() => setShowSpawnModal(false)}
        title={
          <div>
            <div className="text-base font-semibold text-gray-200">Spawn Agent</div>
            <div className="text-xs text-gray-500 mt-1">
              Launch a new AI agent in its own isolated tmux session.
            </div>
          </div>
        }
        size="lg"
        radius="lg"
      >
        <div className="space-y-4">
          <CustomSelect
            label="Provider"
            value={provider}
            onChange={setProvider}
            placeholder="Select provider..."
            options={(providers.length > 0 ? providers : FALLBACK_PROVIDERS.map(n => ({ name: n, binary: '', installed: true }))).map(p => ({
              value: p.name,
              label: p.name.replace(/_/g, ' '),
              sublabel: !p.installed ? 'Not installed' : undefined,
              disabled: !p.installed,
            }))}
          />

          {loadingProfiles ? (
            <TextInput label="Agent Profile" value="Loading profiles..." disabled className="w-full" />
          ) : profiles.length > 0 ? (
            <CustomSelect
              label="Agent Profile"
              value={profile}
              onChange={setProfile}
              placeholder="Select a profile..."
              options={profiles.map(p => ({
                value: p.name,
                label: p.name,
                sublabel: p.description || undefined,
                group: SOURCE_LABELS[p.source] || p.source,
              }))}
            />
          ) : (
            <TextInput
              label="Agent Profile"
              value={profile}
              onChange={(e) => setProfile(e.target.value)}
              placeholder="e.g. developer, reviewer"
            />
          )}

          <TextInput
            label={
              <span>Session Name <span className="text-gray-600">(optional)</span></span>
            }
            value={sessionName}
            onChange={(e) => setSessionName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            placeholder="my-session (or a random id like cao-a1b2c3d4)"
            leftSection={<Tag size={14} className="text-gray-500" />}
          />

          <TextInput
            label={
              <span>Working Directory <span className="text-gray-600">(optional)</span></span>
            }
            value={workingDirectory}
            onChange={(e) => setWorkingDirectory(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            placeholder="/path/to/project (defaults to home)"
            leftSection={<FolderOpen size={14} className="text-gray-500" />}
            styles={{ input: { fontFamily: 'var(--mantine-font-family-monospace)' } }}
          />

          {/* Quick-pick profiles */}
          {profiles.length > 0 && (
            <div>
              <div className="mb-2 text-xs text-gray-500">Quick pick</div>
              <div className="grid max-h-40 grid-cols-2 gap-1.5 overflow-y-auto">
                {profiles.slice(0, 12).map(p => (
                  <button
                    key={`${p.source}-${p.name}`}
                    onClick={() => setProfile(p.name)}
                    className={`text-left px-2.5 py-2 rounded-lg border text-xs transition-all ${
                      profile === p.name
                        ? 'bg-emerald-900/30 border-emerald-700/50 text-emerald-300'
                        : 'bg-gray-900/50 border-gray-700/30 hover:bg-gray-800/80 text-gray-300'
                    }`}
                  >
                    <span className="font-medium">{p.name}</span>
                    <span className="text-[10px] text-gray-600 ml-1.5">{SOURCE_LABELS[p.source] || p.source}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <Group justify="flex-end" gap="sm" mt="lg">
          <Button variant="default" onClick={() => setShowSpawnModal(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleCreate}
            disabled={!profile.trim() || creating}
            leftSection={<Play size={14} />}
          >
            {creating ? 'Spawning...' : 'Spawn Agent'}
          </Button>
        </Group>
      </Modal>

    </div>
  )
}

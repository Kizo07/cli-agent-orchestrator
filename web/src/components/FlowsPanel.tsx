import { useState, useEffect } from 'react'
import { api, Flow, AgentProfileInfo, ProviderInfo } from '../api'
import { useStore } from '../store'
import { ConfirmModal } from './ConfirmModal'
import { Clock, Play, Trash2, Plus, ChevronDown, ChevronRight, Loader2 } from 'lucide-react'
import { ActionIcon, Button, Group, Modal, Switch, TextInput, Textarea } from '@mantine/core'
import { CustomSelect } from './CustomSelect'

const SCHEDULE_PRESETS = [
  { label: 'Every 5 minutes', cron: '*/5 * * * *' },
  { label: 'Every 15 minutes', cron: '*/15 * * * *' },
  { label: 'Every hour', cron: '0 * * * *' },
  { label: 'Every 6 hours', cron: '0 */6 * * *' },
  { label: 'Daily at 9 AM', cron: '0 9 * * *' },
  { label: 'Weekdays at 9 AM', cron: '0 9 * * 1-5' },
  { label: 'Weekly (Monday 9 AM)', cron: '0 9 * * 1' },
  { label: 'Monthly (1st at midnight)', cron: '0 0 1 * *' },
]

const CUSTOM_CRON_VALUE = '__custom__'

function cronToLabel(cron: string): string {
  return SCHEDULE_PRESETS.find(p => p.cron === cron)?.label || cron
}

export function FlowsPanel() {
  const { showSnackbar } = useStore()

  // Flow list state
  const [flows, setFlows] = useState<Flow[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [togglingFlow, setTogglingFlow] = useState<string | null>(null)
  const [runningFlow, setRunningFlow] = useState<string | null>(null)

  // Delete confirmation state
  const [pendingDelete, setPendingDelete] = useState<Flow | null>(null)
  const [deleting, setDeleting] = useState(false)

  // Create modal state
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [name, setName] = useState('')
  const [schedule, setSchedule] = useState('')
  const [scheduleMode, setScheduleMode] = useState<'preset' | 'custom'>('preset')
  const [agentProfile, setAgentProfile] = useState('')
  const [provider, setProvider] = useState('')
  const [promptTemplate, setPromptTemplate] = useState('')
  const [creating, setCreating] = useState(false)

  // Profiles & providers for dropdowns
  const [profiles, setProfiles] = useState<AgentProfileInfo[]>([])
  const [providers, setProviders] = useState<ProviderInfo[]>([])

  const fetchFlows = async () => {
    try {
      const data = await api.listFlows()
      setFlows(data)
    } catch {
      setFlows([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchFlows()
    api.listProfiles()
      .then(p => setProfiles(p))
      .catch(() => {})
    api.listProviders()
      .then(p => {
        setProviders(p)
        const firstInstalled = p.find(prov => prov.installed)
        if (firstInstalled) setProvider(firstInstalled.name)
      })
      .catch(() => {})
  }, [])

  const resetForm = () => {
    setName('')
    setSchedule('')
    setScheduleMode('preset')
    setAgentProfile('')
    setPromptTemplate('')
  }

  const handleCreate = async () => {
    if (!name.trim() || !schedule.trim() || !agentProfile.trim() || !promptTemplate.trim()) return
    setCreating(true)
    try {
      await api.createFlow({
        name: name.trim(),
        schedule: schedule.trim(),
        agent_profile: agentProfile.trim(),
        provider: provider || undefined,
        prompt_template: promptTemplate,
      })
      showSnackbar({ type: 'success', message: `Flow "${name.trim()}" created` })
      resetForm()
      setShowCreateModal(false)
      await fetchFlows()
    } catch (e: any) {
      showSnackbar({ type: 'error', message: e.message || 'Failed to create flow' })
    } finally {
      setCreating(false)
    }
  }

  const handleToggle = async (flow: Flow) => {
    setTogglingFlow(flow.name)
    try {
      if (flow.enabled) {
        await api.disableFlow(flow.name)
        showSnackbar({ type: 'success', message: `Flow "${flow.name}" disabled` })
      } else {
        await api.enableFlow(flow.name)
        showSnackbar({ type: 'success', message: `Flow "${flow.name}" enabled` })
      }
      await fetchFlows()
    } catch (e: any) {
      showSnackbar({ type: 'error', message: e.message || `Failed to toggle flow` })
    } finally {
      setTogglingFlow(null)
    }
  }

  const handleRun = async (flow: Flow) => {
    setRunningFlow(flow.name)
    try {
      await api.runFlow(flow.name)
      showSnackbar({ type: 'success', message: `Flow "${flow.name}" executed` })
      await fetchFlows()
    } catch (e: any) {
      showSnackbar({ type: 'error', message: e.message || `Failed to run flow` })
    } finally {
      setRunningFlow(null)
    }
  }

  const handleDelete = async () => {
    if (!pendingDelete) return
    setDeleting(true)
    try {
      await api.deleteFlow(pendingDelete.name)
      showSnackbar({ type: 'success', message: `Flow "${pendingDelete.name}" deleted` })
      await fetchFlows()
    } catch (e: any) {
      showSnackbar({ type: 'error', message: e.message || 'Failed to delete flow' })
    } finally {
      setDeleting(false)
      setPendingDelete(null)
    }
  }

  if (loading) {
    return <div className="text-gray-500 text-sm py-8 text-center">Loading flows...</div>
  }

  const scheduleSelectOptions = [
    ...SCHEDULE_PRESETS.map(p => ({
      value: p.cron,
      label: p.label,
      sublabel: p.cron,
    })),
    { value: CUSTOM_CRON_VALUE, label: 'Custom cron expression', sublabel: 'Type your own schedule' },
  ]

  return (
    <div className="space-y-6">
      {/* Flow List */}
      <div className="bg-gray-800/60 border border-gray-700/50 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">
            Automated Flows ({flows.length})
          </h3>
          <Button onClick={() => { resetForm(); setShowCreateModal(true) }} leftSection={<Plus size={14} />}>
            Create Flow
          </Button>
        </div>

        {flows.length === 0 ? (
          <div className="text-center py-8">
            <Clock size={32} className="mx-auto text-gray-600 mb-3" />
            <p className="text-gray-500 text-sm">No flows configured.</p>
            <p className="text-gray-600 text-xs mt-1">
              Click "Create Flow" above or use the CLI: <code className="text-emerald-400">cao schedule add &lt;file.md&gt;</code>
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {flows.map(f => (
              <div key={f.name} className="bg-gray-900/50 border border-gray-700/30 rounded-lg">
                {/* Row header */}
                <div
                  className="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-800/50 transition-colors"
                  onClick={() => setExpanded(expanded === f.name ? null : f.name)}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <Clock size={14} className="text-gray-400 shrink-0" />
                    <span className="text-sm text-gray-200 font-medium truncate">{f.name}</span>
                    <span className="text-xs text-gray-500 shrink-0" title={f.schedule}>
                      {cronToLabel(f.schedule)}
                    </span>
                    <span className="text-xs text-gray-500 shrink-0">{f.agent_profile}</span>
                    {f.provider && (
                      <span className="text-xs text-gray-600 shrink-0">{f.provider}</span>
                    )}
                    <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${f.enabled ? 'bg-emerald-900/50 text-emerald-400' : 'bg-gray-700 text-gray-400'}`}>
                      {f.enabled ? 'enabled' : 'disabled'}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 shrink-0 ml-3">
                    {/* Toggle enable/disable */}
                    <Switch
                      checked={f.enabled}
                      onChange={(e) => { e.stopPropagation(); handleToggle(f) }}
                      disabled={togglingFlow === f.name}
                      size="sm"
                      aria-label={f.enabled ? 'Disable flow' : 'Enable flow'}
                      title={f.enabled ? 'Disable flow' : 'Enable flow'}
                      onClick={(e) => e.stopPropagation()}
                    />

                    {/* Run Now */}
                    <Button
                      size="xs"
                      onClick={(e) => { e.stopPropagation(); handleRun(f) }}
                      disabled={runningFlow === f.name}
                      leftSection={runningFlow === f.name ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                      title="Run flow now"
                    >
                      {runningFlow === f.name ? 'Running...' : 'Run Now'}
                    </Button>

                    {/* Delete */}
                    <ActionIcon
                      variant="subtle"
                      color="gray"
                      onClick={(e) => { e.stopPropagation(); setPendingDelete(f) }}
                      title="Delete flow"
                    >
                      <Trash2 size={14} />
                    </ActionIcon>

                    {/* Expand chevron */}
                    {expanded === f.name ? (
                      <ChevronDown size={14} className="text-gray-500" />
                    ) : (
                      <ChevronRight size={14} className="text-gray-500" />
                    )}
                  </div>
                </div>

                {/* Expanded details */}
                {expanded === f.name && (
                  <div className="px-3 pb-3 text-xs text-gray-400 space-y-3 border-t border-gray-700/30 pt-3">
                    <div className="grid grid-cols-2 gap-x-6 gap-y-1">
                      <div>Schedule: <span className="text-gray-300 font-mono">{f.schedule}</span></div>
                      <div>Provider: <span className="text-gray-300">{f.provider || 'default'}</span></div>
                      <div>Profile: <span className="text-gray-300">{f.agent_profile}</span></div>
                      <div>Last Run: <span className="text-gray-300">{f.last_run ? new Date(f.last_run).toLocaleString() : 'never'}</span></div>
                      <div>Next Run: <span className="text-gray-300">{f.next_run ? new Date(f.next_run).toLocaleString() : 'n/a'}</span></div>
                      {f.file_path && (
                        <div className="col-span-2">File: <span className="text-gray-300 font-mono">{f.file_path}</span></div>
                      )}
                    </div>
                    {f.prompt_template && (
                      <div>
                        <div className="text-[11px] text-gray-500 uppercase tracking-wider mb-1.5">Prompt</div>
                        <div className="bg-gray-950/60 border border-gray-700/30 rounded-lg p-3 text-sm text-gray-300 font-mono whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
                          {f.prompt_template}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <Modal
        opened={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title={
          <div>
            <div className="text-base font-semibold text-gray-200">Create Flow</div>
            <div className="text-xs text-gray-500 mt-1">
              Schedule an agent to run automatically on a recurring basis.
            </div>
          </div>
        }
        size="lg"
        radius="lg"
      >
        <div className="space-y-4">
          <TextInput
            label="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="my-daily-review"
            autoFocus
          />

          <div>
            <CustomSelect
              value={scheduleMode === 'custom' ? CUSTOM_CRON_VALUE : schedule}
              onChange={(val) => {
                if (val === CUSTOM_CRON_VALUE) {
                  setScheduleMode('custom')
                  setSchedule('')
                } else {
                  setScheduleMode('preset')
                  setSchedule(val)
                }
              }}
              placeholder="Pick a schedule..."
              options={scheduleSelectOptions}
            />
            {scheduleMode === 'custom' && (
              <TextInput
                className="mt-2"
                value={schedule}
                onChange={(e) => setSchedule(e.target.value)}
                placeholder="*/30 * * * *"
                styles={{ input: { fontFamily: 'var(--mantine-font-family-monospace)' } }}
                autoFocus
              />
            )}
            {schedule && (
              <p className="text-[11px] text-emerald-500/70 mt-1.5">
                {cronToLabel(schedule)}{scheduleMode === 'custom' && schedule ? ` — ${schedule}` : ''}
              </p>
            )}
          </div>

          <div className="flex gap-3">
            <div className="flex-1">
              {profiles.length > 0 ? (
                <CustomSelect
                  label="Agent Profile"
                  value={agentProfile}
                  onChange={setAgentProfile}
                  placeholder="Select a profile..."
                  options={profiles.map((p) => ({
                    value: p.name,
                    label: p.name,
                    sublabel: p.description || undefined,
                  }))}
                />
              ) : (
                <TextInput
                  label="Agent Profile"
                  value={agentProfile}
                  onChange={(e) => setAgentProfile(e.target.value)}
                  placeholder="e.g. developer"
                />
              )}
            </div>
            <div className="flex-1">
              <CustomSelect
                label="Provider"
                value={provider}
                onChange={setProvider}
                placeholder="Default"
                options={providers.map((p) => ({
                  value: p.name,
                  label: p.name.replace(/_/g, ' '),
                  sublabel: !p.installed ? 'Not installed' : undefined,
                  disabled: !p.installed,
                }))}
              />
            </div>
          </div>

          <Textarea
            label="Prompt"
            value={promptTemplate}
            onChange={(e) => setPromptTemplate(e.target.value)}
            placeholder="Describe what this flow should do..."
            rows={5}
            styles={{ input: { fontFamily: 'var(--mantine-font-family-monospace)' } }}
          />
        </div>

        <Group justify="flex-end" gap="sm" mt="lg">
          <Button variant="default" onClick={() => setShowCreateModal(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleCreate}
            disabled={!name.trim() || !schedule.trim() || !agentProfile.trim() || !promptTemplate.trim() || creating}
            leftSection={creating ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
          >
            {creating ? 'Creating...' : 'Create Flow'}
          </Button>
        </Group>
      </Modal>

      {/* Delete Confirmation Modal */}
      <ConfirmModal
        open={!!pendingDelete}
        title="Delete Flow"
        message="This will permanently remove the flow and its schedule. This action cannot be undone."
        details={pendingDelete ? [
          { label: 'Name', value: pendingDelete.name },
          { label: 'Schedule', value: pendingDelete.schedule },
          { label: 'Profile', value: pendingDelete.agent_profile },
          { label: 'Provider', value: pendingDelete.provider || 'default' },
        ] : []}
        confirmLabel="Delete Flow"
        variant="danger"
        loading={deleting}
        onConfirm={handleDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  )
}

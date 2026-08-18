import { useState, useEffect, useRef } from 'react'
import { api, InboxMessage } from '../api'
import { Send, Mail, Loader2 } from 'lucide-react'
import { Badge, Box, Button, Group, Modal, SegmentedControl, Text, TextInput } from '@mantine/core'

interface InboxPanelProps {
  terminalId: string
  onClose: () => void
}

type StatusFilter = 'all' | 'pending' | 'delivered' | 'failed'

const STATUS_FILTERS: { key: StatusFilter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'pending', label: 'Pending' },
  { key: 'delivered', label: 'Delivered' },
  { key: 'failed', label: 'Failed' },
]

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return ''
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const diffSec = Math.floor((now - then) / 1000)
  if (diffSec < 0) return 'just now'
  if (diffSec < 60) return `${diffSec}s ago`
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  return `${diffDay}d ago`
}

function MessageStatusBadge({ status }: { status: InboxMessage['status'] }) {
  const config = {
    delivered: { color: 'success', label: 'Delivered' },
    pending: { color: 'warning', label: 'Pending' },
    failed: { color: 'danger', label: 'Failed' },
  } as const
  const c = config[status] || config.pending
  return (
    <Badge color={c.color} variant="light" size="xs">
      {c.label}
    </Badge>
  )
}

export function InboxPanel({ terminalId, onClose }: InboxPanelProps) {
  const [messages, setMessages] = useState<InboxMessage[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<StatusFilter>('all')
  const [sendText, setSendText] = useState('')
  const [sending, setSending] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const fetchMessages = async () => {
    try {
      const status = filter === 'all' ? undefined : filter
      const data = await api.getInboxMessages(terminalId, 50, status)
      setMessages(data)
    } catch {
      // silently fail — will retry
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setLoading(true)
    fetchMessages()
    const interval = setInterval(fetchMessages, 5000)
    return () => clearInterval(interval)
  }, [terminalId, filter])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleSend = async () => {
    const text = sendText.trim()
    if (!text || sending) return
    setSending(true)
    try {
      await api.sendInboxMessage(terminalId, 'ui', text)
      setSendText('')
      await fetchMessages()
    } catch {
      // send failed — user can retry
    }
    setSending(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const isReceiver = (msg: InboxMessage) => msg.receiver_id === terminalId

  return (
    <Modal
      opened
      onClose={onClose}
      centered
      size="600px"
      radius="lg"
      title={
        <Group gap="sm" wrap="nowrap">
          <Box className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-900/50">
            <Mail size={16} className="text-emerald-400" />
          </Box>
          <Box>
            <Text size="sm" fw={600}>Agent Inbox</Text>
            <Text size="xs" c="dimmed">
              Messages between agents in this session{' '}
              <Text component="span" size="xs" className="font-mono">{terminalId}</Text>
            </Text>
          </Box>
        </Group>
      }
    >
      <Box className="mx-4 mb-3 overflow-x-auto">
        <SegmentedControl
          value={filter}
          onChange={(value) => setFilter(value as StatusFilter)}
          data={STATUS_FILTERS.map((f) => ({ value: f.key, label: f.label }))}
          size="xs"
        />
      </Box>

      <Box className="min-h-[200px] space-y-3 overflow-y-auto border-t border-b border-gray-700/30 px-5 py-4 mx-4" style={{ maxHeight: "calc(100vh - 380px)" }}>
        {loading && messages.length === 0 ? (
          <Box className="flex items-center justify-center py-12">
            <Loader2 size={20} className="animate-spin text-gray-500" />
          </Box>
        ) : messages.length === 0 ? (
          <Box className="flex flex-col items-center justify-center py-12 text-gray-500">
            <Mail size={32} className="mb-3 opacity-40" />
            <Text size="sm">No messages yet</Text>
            <Text size="xs" c="dimmed" mt={4}>
              Messages appear here when agents communicate via handoff, assign, or
              send_message. You can also send a message manually below.
            </Text>
          </Box>
        ) : (
          messages.map((msg) => {
            const incoming = isReceiver(msg)
            return (
              <Box key={msg.id} className={`flex flex-col ${incoming ? 'items-start' : 'items-end'}`}>
                <Box
                  className={`max-w-[85%] rounded-xl px-3.5 py-2.5 ${
                    incoming
                      ? 'bg-gray-800 border border-gray-700/40'
                      : 'bg-emerald-900/30 border border-emerald-700/30'
                  }`}
                >
                  <Group gap="xs" mb={4} wrap="nowrap">
                    <Text size="xs" className="font-mono text-gray-500">
                      {incoming ? msg.sender_id.slice(0, 8) : msg.receiver_id.slice(0, 8)}
                    </Text>
                    <MessageStatusBadge status={msg.status} />
                  </Group>
                  <Text size="sm" className="whitespace-pre-wrap break-words text-gray-200">
                    {msg.message}
                  </Text>
                  {msg.created_at && (
                    <Text size="xs" c="dimmed" mt={4}>
                      {formatRelativeTime(msg.created_at)}
                    </Text>
                  )}
                </Box>
              </Box>
            )
          })
        )}
        <Box ref={messagesEndRef} />
      </Box>

      <Group gap="xs" mx="md" my="md" wrap="nowrap" align="flex-end">
        <TextInput
          ref={inputRef}
          value={sendText}
          onChange={(e) => setSendText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message..."
          className="flex-1"
        />
        <Button
          onClick={handleSend}
          disabled={!sendText.trim() || sending}
          leftSection={sending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
        >
          Send
        </Button>
      </Group>
    </Modal>
  )
}
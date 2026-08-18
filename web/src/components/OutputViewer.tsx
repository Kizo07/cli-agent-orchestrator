import { useState, useEffect, useRef } from 'react'
import { api } from '../api'
import { RefreshCw, Copy, Check, FileText } from 'lucide-react'
import { ActionIcon, Badge, Box, Group, Loader, Modal, SegmentedControl } from '@mantine/core'

function stripAnsi(text: string): string {
  return text.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '').replace(/\x1b\][^\x07]*\x07/g, '')
}

interface OutputViewerProps {
  terminalId: string
  onClose: () => void
}

export function OutputViewer({ terminalId, onClose }: OutputViewerProps) {
  const [mode, setMode] = useState<'last' | 'full'>('last')
  const [output, setOutput] = useState('')
  const [loading, setLoading] = useState(true)
  const [copied, setCopied] = useState(false)
  const outputRef = useRef<HTMLPreElement>(null)

  const fetchOutput = async (m: 'last' | 'full') => {
    setLoading(true)
    try {
      const data = await api.getTerminalOutput(terminalId, m)
      setOutput(data.output || '')
    } catch {
      setOutput('')
    }
    setLoading(false)
  }

  useEffect(() => {
    fetchOutput(mode)
  }, [mode, terminalId])

  // Auto-scroll to bottom on full output mode
  useEffect(() => {
    if (mode === 'full' && outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight
    }
  }, [output, mode])

  const handleCopy = async () => {
    const clean = stripAnsi(output)
    try {
      await navigator.clipboard.writeText(clean)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard API may not be available
    }
  }

  const handleRefresh = () => {
    fetchOutput(mode)
  }

  const cleanOutput = stripAnsi(output)

  return (
    <Modal
      opened
      onClose={onClose}
      centered
      size="800px"
      radius="lg"
      title={
        <Group gap="sm" wrap="nowrap">
          <FileText size={16} className="text-emerald-400" />
          <span className="text-sm font-semibold text-white">Terminal Output</span>
          <Badge variant="light" color="gray" className="font-mono">{terminalId}</Badge>
        </Group>
      }
      closeButtonProps={{ 'aria-label': 'Close' }}
    >
      <Group justify="space-between" mx="md" mb="sm" wrap="nowrap">
        <Group gap="xs" wrap="nowrap">
          <ActionIcon
            variant="subtle"
            color="gray"
            onClick={handleCopy}
            disabled={!cleanOutput}
            title="Copy to clipboard"
          >
            {copied ? <Check size={16} className="text-emerald-400" /> : <Copy size={16} />}
          </ActionIcon>
          <ActionIcon
            variant="subtle"
            color="gray"
            onClick={handleRefresh}
            disabled={loading}
            title="Refresh output"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </ActionIcon>
          {copied && <span className="text-xs text-emerald-400">Copied!</span>}
        </Group>
        <SegmentedControl
          value={mode}
          onChange={(value) => setMode(value as 'last' | 'full')}
          data={[
            { value: 'last', label: 'Last Response' },
            { value: 'full', label: 'Full Output' },
          ]}
          size="xs"
        />
      </Group>

      <Box className="mx-3 px-2" style={{ minHeight: 0 }}>
        {loading ? (
          <Box className="flex min-h-[200px] items-center justify-center">
            <Loader color="gray" size="sm" />
          </Box>
        ) : cleanOutput ? (
          <pre
            ref={outputRef}
            className="overflow-y-auto whitespace-pre-wrap break-words rounded-lg bg-gray-950 p-4 font-mono text-sm text-gray-300"
            style={{ maxHeight: 'calc(80vh - 160px)' }}
          >
            {cleanOutput}
          </pre>
        ) : (
          <Box className="flex min-h-[200px] items-center justify-center">
            <p className="text-sm text-gray-500">No output available</p>
          </Box>
        )}
      </Box>
    </Modal>
  )
}
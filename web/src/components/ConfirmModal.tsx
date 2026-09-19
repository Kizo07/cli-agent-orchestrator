import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Loader2 } from 'lucide-react'
import { ActionIcon, Box, Button, Group, Modal, Stack, Text } from '@mantine/core'

interface ConfirmModalProps {
  open: boolean
  title: string
  message: string
  details?: { label: string; value: string }[]
  confirmLabel?: string
  cancelLabel?: string
  variant?: 'danger' | 'warning'
  loading?: boolean
  /**
   * Type-to-confirm gate. When set, an input is shown and the confirm button
   * stays disabled until the user types this exact string (e.g. the name of
   * the thing being deleted). Optional and additive: callers that omit it get
   * the original confirm-on-click behavior.
   */
  confirmationText?: string
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmModal({
  open,
  title,
  message,
  details,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'danger',
  loading = false,
  confirmationText,
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  const cancelRef = useRef<HTMLButtonElement>(null)
  const [typed, setTyped] = useState('')

  useEffect(() => {
    if (open) {
      cancelRef.current?.focus()
      // Reset per open so a previous confirmation never carries over.
      setTyped('')
    }
  }, [open, confirmationText])
  return (
    <Modal
      opened={open}
      onClose={onCancel}
      title={
        <Group gap="sm" wrap="nowrap" align="flex-start">
          <Box
            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${
              variant === 'danger' ? 'bg-red-900/40 text-red-400' : 'bg-yellow-900/40 text-yellow-400'
            }`}
          >
            <AlertTriangle size={20} />
          </Box>
          <Box>
            <Text fw={600}>{title}</Text>
            <Text size="sm" c="dimmed" mt={4}>
              {message}
            </Text>
          </Box>
        </Group>
      }
      closeButtonProps={{ 'aria-label': 'Close' }}
      centered
      size="md"
      radius="lg"
    >
      {details && details.length > 0 && (
        <Box className="mb-4 rounded-lg border border-gray-700/40 bg-gray-800/60 p-3" mx="md">
          <Stack gap={6}>
            {details.map((d) => (
              <Group key={d.label} justify="space-between" gap="sm" wrap="nowrap">
                <Text size="xs" c="dimmed">
                  {d.label}
                </Text>
                <Text size="xs" className="font-mono text-gray-300">
                  {d.value}
                </Text>
              </Group>
            ))}
          </Stack>
        </Box>
      )}

      {/* Type-to-confirm gate */}
      {confirmationText !== undefined && (
        <Box mx="md" mb="md">
          <label htmlFor="confirm-typed" className="block text-xs text-gray-400 mb-1.5">
            Type <span className="font-mono text-gray-200 select-all">{confirmationText}</span> to confirm:
          </label>
          <input
            id="confirm-typed"
            aria-label="Confirmation text"
            type="text"
            autoComplete="off"
            spellCheck={false}
            value={typed}
            onChange={e => setTyped(e.target.value)}
            className="w-full px-3 py-2 bg-gray-950 border border-gray-700 rounded-lg text-sm text-gray-200 font-mono placeholder-gray-600 focus:outline-none focus:border-red-600"
          />
        </Box>
      )}

      <Group justify="flex-end" gap="sm" mt="md">
        <Button variant="default" ref={cancelRef} onClick={onCancel} disabled={loading}>
          {cancelLabel}
        </Button>
        <Button
          color={variant === 'danger' ? 'danger' : 'warning'}
          onClick={onConfirm}
          disabled={loading || (confirmationText !== undefined && typed !== confirmationText)}
          leftSection={loading ? <Loader2 size={14} className="animate-spin" /> : undefined}
        >
          {loading ? 'Closing...' : confirmLabel}
        </Button>
      </Group>
    </Modal>
  )
}

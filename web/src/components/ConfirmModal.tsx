import { AlertTriangle, Loader2, X } from 'lucide-react'
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
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
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

      <Group justify="flex-end" gap="sm" mt="md">
        <Button variant="default" onClick={onCancel} disabled={loading}>
          {cancelLabel}
        </Button>
        <Button
          color={variant === 'danger' ? 'danger' : 'warning'}
          onClick={onConfirm}
          disabled={loading}
          leftSection={loading ? <Loader2 size={14} className="animate-spin" /> : undefined}
        >
          {loading ? 'Closing...' : confirmLabel}
        </Button>
      </Group>
    </Modal>
  )
}

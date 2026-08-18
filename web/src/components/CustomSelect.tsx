import { Box, CheckIcon, Group, Select, Text } from '@mantine/core'

export interface SelectOption {
  value: string
  label: string
  disabled?: boolean
  group?: string
  sublabel?: string
}

interface CustomSelectProps {
  value: string
  onChange: (value: string) => void
  options: SelectOption[]
  placeholder?: string
  className?: string
  label?: string
}

export function CustomSelect({ value, onChange, options, placeholder = 'Select...', className = '', label }: CustomSelectProps) {
  const data = options.map((opt) => {
    const item: { value: string; label: string; disabled?: boolean; group?: string; sublabel?: string } = {
      value: opt.value,
      label: opt.label,
    }
    if (opt.disabled) item.disabled = opt.disabled
    if (opt.group) item.group = opt.group
    if (opt.sublabel) item.sublabel = opt.sublabel
    return item
  })

  return (
    <Select
      value={value}
      onChange={(next) => onChange(next ?? '')}
      data={data}
      placeholder={placeholder}
      className={className}
      label={label}
      allowDeselect={false}
      searchable={false}
      maxDropdownHeight={256}
      comboboxProps={{ keepMounted: false }}
      renderOption={(item) => {
        const opt = item.option as (typeof data)[number]
        return (
          <Box style={{ minWidth: 0 }}>
            <Group gap="xs" wrap="nowrap">
              {item.checked && <CheckIcon size={14} className="shrink-0" />}
              <Text size="sm" truncate>
                {item.option.label}
              </Text>
            </Group>
            {opt?.sublabel && (
              <Text size="xs" c="dimmed" truncate>
                {opt.sublabel}
              </Text>
            )}
          </Box>
        )
      }}
    />
  )
}

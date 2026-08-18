import React from 'react'
import { render as rtlRender } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'
import { theme } from '../theme'

export function render(ui: React.ReactElement, options?: Parameters<typeof rtlRender>[1]) {
  return rtlRender(ui, {
    ...options,
    wrapper: ({ children }) => (
      <MantineProvider theme={theme} defaultColorScheme="dark" env="test">
        {children}
      </MantineProvider>
    ),
  })
}

export * from '@testing-library/react'

// Test render helper: wraps every render in a MantineProvider with the CAO
// theme so Mantine components resolve theme/color-scheme context in tests.
// `env="test"` keeps Mantine's CSS-in-JS behavior deterministic under Vitest.

import React from "react";
import { render as rtlRender } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { theme } from "../shared/theme";

export function render(
  ui: React.ReactElement,
  options?: Parameters<typeof rtlRender>[1],
) {
  return rtlRender(ui, {
    ...options,
    wrapper: ({ children }) => (
      <MantineProvider theme={theme} defaultColorScheme="auto" env="test">
        {children}
      </MantineProvider>
    ),
  });
}

export * from "@testing-library/react";

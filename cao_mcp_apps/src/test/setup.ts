// Vitest setup: ensure each test starts with a clean DOM and auto-cleanup of
// rendered React trees, plus the DOM APIs Mantine components rely on that
// happy-dom does not fully implement.

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});

// MantineProvider resolves the color scheme via matchMedia; happy-dom may not
// implement it in all versions.
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = (query: string): MediaQueryList =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}

// Mantine components observe element size (e.g. ScrollArea); happy-dom lacks
// ResizeObserver in some versions.
if (typeof globalThis !== "undefined" && !("ResizeObserver" in globalThis)) {
  (globalThis as any).ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

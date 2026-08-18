import '@testing-library/jest-dom'

// Sigma references WebGL2RenderingContext at module-load time to pick a
// renderer, but jsdom provides no WebGL. Any test that transitively imports a
// component pulling in `sigma` (e.g. MemoryPanel → MemoryGraphView) would crash
// at import otherwise. A no-op class stub lets the module load; tests that
// actually mount the graph mock `sigma` outright (see memory-graph.test.tsx).
for (const name of ['WebGLRenderingContext', 'WebGL2RenderingContext']) {
  if (typeof (globalThis as any)[name] === 'undefined') {
    ;(globalThis as any)[name] = class {}
  }
}

// MantineProvider resolves the color scheme via matchMedia; jsdom lacks it.
if (typeof window !== 'undefined' && !window.matchMedia) {
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
    }) as MediaQueryList
}

// Mantine Select/Floating UI observes element size; jsdom lacks ResizeObserver.
if (typeof globalThis !== 'undefined' && !('ResizeObserver' in globalThis)) {
  ;(globalThis as any).ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

// Mantine Select scrolls the selected option into view; jsdom lacks it.
if (typeof Element !== 'undefined' && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}

// Browser smoke check for the migrated cao_mcp_apps views.
//
// Starts the E2E harness server (serves the built single-file bundles inside
// the MCP host harness), then for each view checks:
//   - an h1 is present in the iframe,
//   - no horizontal overflow at desktop (native iframe width) and at a
//     390px mobile iframe width,
// and captures screenshots into the evidence dir.
//
// Usage: node scripts/smoke-check.mjs

import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { chromium } from "@playwright/test";

const PORT = 9891;
const EVIDENCE = resolve(
  import.meta.dirname,
  "../../../Mantine-Dashboard-Modernization-Plan/evidence/cao-mcp-apps",
);
mkdirSync(EVIDENCE, { recursive: true });

const VIEWS = ["dashboard", "agent", "event-stream", "graph"];

const server = spawn(
  process.execPath,
  [resolve(import.meta.dirname, "../e2e/server.mjs")],
  { env: { ...process.env, E2E_PORT: String(PORT) }, stdio: "ignore" },
);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitForServer(url, tries = 50) {
  for (let i = 0; i < tries; i++) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {
      /* not up yet */
    }
    await sleep(200);
  }
  throw new Error(`harness server did not come up at ${url}`);
}

async function checkView(page, view, width) {
  await page.goto(`http://127.0.0.1:${PORT}/host.html?view=${view}`);
  await page.evaluate(() => window.__host.ready());
  const frame = page.frameLocator(`iframe[data-view="${view}"]`);

  // Wait for the view to render something meaningful.
  await frame.locator("h1").first().waitFor({ timeout: 10_000 });

  // Resize the iframe to the target width (container queries respond to the
  // iframe width, not the viewport).
  await page.evaluate((w) => {
    const f = document.querySelector(`iframe[data-view]`);
    f.style.width = `${w}px`;
  }, width);
  await sleep(150);

  const metrics = await page
    .frames()
    .find((f) => f.url().includes(`/bundles/${view}.html`))
    .evaluate(() => {
      const doc = document.documentElement;
      const h1 = document.querySelector("h1");
      return {
        h1: h1 ? h1.textContent : null,
        scrollWidth: doc.scrollWidth,
        clientWidth: doc.clientWidth,
        overflowX: doc.scrollWidth > doc.clientWidth,
      };
    });

  const label = `${view}-${width}`;
  await page.screenshot({
    path: resolve(EVIDENCE, `${label}.png`),
    fullPage: true,
  });

  return metrics;
}

let failed = 0;
try {
  await waitForServer(`http://127.0.0.1:${PORT}/host.html?view=dashboard`);
  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width: 1440, height: 900 },
  });

  for (const view of VIEWS) {
    for (const width of [1280, 390]) {
      const m = await checkView(page, view, width);
      const ok = m.h1 !== null && !m.overflowX;
      console.log(
        `${ok ? "OK " : "FAIL"} ${view} @ ${width}px  h1=${JSON.stringify(m.h1)} overflowX=${m.overflowX} (${m.scrollWidth}/${m.clientWidth})`,
      );
      if (!ok) failed += 1;
    }
  }

  await browser.close();
} finally {
  server.kill();
}

process.exit(failed > 0 ? 1 : 0);

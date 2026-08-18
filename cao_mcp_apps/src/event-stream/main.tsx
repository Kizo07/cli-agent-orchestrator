// Entry point for ui://cao/event-stream.

import React from "react";
import { createRoot } from "react-dom/client";
import { MantineProvider } from "@mantine/core";
import "@mantine/core/styles.css";
import "../shared/styles.css";
import { McpApp } from "../shared/mcpApp";
import { theme } from "../shared/theme";
import { EventStreamView } from "./EventStreamView";

const app = new McpApp();
const container = document.getElementById("root")!;
createRoot(container).render(
  <React.StrictMode>
    <MantineProvider theme={theme} defaultColorScheme="auto">
      <EventStreamView app={app} />
    </MantineProvider>
  </React.StrictMode>,
);

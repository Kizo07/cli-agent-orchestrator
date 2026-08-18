// Entry point for ui://cao/agent.

import React from "react";
import { createRoot } from "react-dom/client";
import { MantineProvider } from "@mantine/core";
import "@mantine/core/styles.css";
import "../shared/styles.css";
import { McpApp } from "../shared/mcpApp";
import { theme } from "../shared/theme";
import { AgentView } from "./AgentView";

const app = new McpApp();
const container = document.getElementById("root")!;
createRoot(container).render(
  <React.StrictMode>
    <MantineProvider theme={theme} defaultColorScheme="auto">
      <AgentView app={app} />
    </MantineProvider>
  </React.StrictMode>,
);

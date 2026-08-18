// AgentStatus — a single agent (terminal) card with a status badge.
//
// Status text/provider/profile are rendered as escaped React children. The
// status string is also normalized to a CSS modifier class for the badge color
// (the color resolves to the host-overridable `--cao-status-<role>` variable,
// preserving SEP-1865 theming).

import React from "react";
import { Badge, Card, Group, Stack, Text } from "@mantine/core";
import type { TerminalView } from "./types";
import { STATUS } from "./status.generated";

// The known status taxonomy is generated from the shared SSOT
// (design-tokens/status.json) via `node design-tokens/gen.mjs`.
const KNOWN_STATUSES = new Set(Object.keys(STATUS));

export interface AgentStatusProps {
  terminal: TerminalView;
  onOpen?: (terminalId: string) => void;
  /** Render a "supervisor" role badge and accent (the fleet coordinator). */
  isSupervisor?: boolean;
}

export function AgentStatus({
  terminal,
  onOpen,
  isSupervisor = false,
}: AgentStatusProps): React.JSX.Element {
  const status = (terminal.status ?? "unknown").toLowerCase();
  const statusClass = KNOWN_STATUSES.has(status) ? status : "unknown";
  // Label/role/pulse are derived from the generated status SSOT; the color is
  // applied through the cao-status-<status> class, which resolves to the
  // role's host-overridable CSS variable in styles.css/tokens.generated.css.
  const semantics = STATUS[statusClass];
  const pulseClass = semantics?.pulse ? " cao-status-pulse" : "";
  return (
    <Card
      className={`cao-card${isSupervisor ? " cao-card-supervisor" : ""}`}
      data-testid="agent-card"
      data-terminal-id={terminal.id}
      role={onOpen ? "button" : undefined}
      tabIndex={onOpen ? 0 : undefined}
      onClick={onOpen ? () => onOpen(terminal.id) : undefined}
      onKeyDown={
        onOpen
          ? (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onOpen(terminal.id);
              }
            }
          : undefined
      }
      padding="sm"
      withBorder
    >
      <Group justify="space-between" align="center" gap="xs" wrap="nowrap">
        <Text fw={600} size="sm" style={{ overflowWrap: "anywhere" }}>
          {terminal.agent_profile ?? terminal.id}
          {isSupervisor && (
            <Badge
              size="xs"
              variant="light"
              color="info"
              ml={8}
              data-testid="role-badge"
            >
              supervisor
            </Badge>
          )}
        </Text>
        <Badge
          size="xs"
          variant="light"
          className={`cao-status cao-status-${statusClass}${pulseClass}`}
          data-testid="status-badge"
          title={semantics?.label}
        >
          {status}
        </Badge>
      </Group>
      <Stack gap={2} mt="xs">
        <Text size="xs" c="dimmed">
          <Text span fw={600} inherit>
            provider
          </Text>{" "}
          {terminal.provider}
        </Text>
        <Text size="xs" c="dimmed">
          <Text span fw={600} inherit>
            session
          </Text>{" "}
          {terminal.session_name}
        </Text>
      </Stack>
    </Card>
  );
}

// HeaderBar — title + fleet counts for the dashboard / views.
//
// All dynamic text is rendered as React children, which escapes it by default
// (no `dangerouslySetInnerHTML`), satisfying the escaped-string requirement.

import React from "react";
import { Badge, Group, Title } from "@mantine/core";

export interface HeaderBarProps {
  title: string;
  sessions?: number;
  terminals?: number;
}

export function HeaderBar({
  title,
  sessions,
  terminals,
}: HeaderBarProps): React.JSX.Element {
  return (
    <Group
      component="header"
      className="cao-header"
      mb="sm"
      gap="sm"
      align="baseline"
      wrap="wrap"
    >
      <Title order={1} className="cao-header-title" size="md">
        {title}
      </Title>
      {(sessions !== undefined || terminals !== undefined) && (
        <Group gap="xs" data-testid="header-counts">
          {sessions !== undefined && (
            <Badge
              size="xs"
              variant="light"
              color="neutral"
              data-testid="count-sessions"
            >
              {sessions} sessions
            </Badge>
          )}
          {terminals !== undefined && (
            <Badge
              size="xs"
              variant="light"
              color="neutral"
              data-testid="count-terminals"
            >
              {terminals} agents
            </Badge>
          )}
        </Group>
      )}
    </Group>
  );
}

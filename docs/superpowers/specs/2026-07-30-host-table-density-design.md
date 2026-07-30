# Host Management Naming And Table Density Design

## Goal

Rename the navigation group and its child entry from "主机管理" to "资产管理",
and make the host management table fill the available page width with more
compact columns while keeping the current visible columns, sorting, sticky
status/actions columns, and row actions unchanged.

## Scope

- Adjust the host table column minimum widths in `HostManager.vue`.
- Reduce the table row column gap and horizontal padding in `table.css`.
- Keep the table element at `width: 100%` so the page does not leave a blank
  panel on the right.
- Update the navigation group and host page label in `app/navigation.ts`.
- Keep the status and actions columns wide enough for their badges and icon
  buttons.
- Preserve the current column visibility behavior and existing uncommitted
  column-default changes.

## Implementation

Keep the existing navigation keys and routes, changing only the visible labels
from "主机管理" to "资产管理".

Use the existing CSS grid configuration for the table. Lower the minimum widths
and fractional widths for the regular host columns by roughly 15% to 25%,
reduce the grid gap from 12px to 6px, and reduce row horizontal padding from
18px to 10px.

Keep `.host-table` at `width: 100%` with a compact `min-width` so wide screens
fill the panel and narrow screens can still scroll horizontally.

The selection column remains compact. The status column remains at 86px and
the actions column remains at 132px so verification badges and action buttons
do not become cramped. The computed table minimum width will continue to be
derived from the configured column minimum widths.

## Validation

- Add focused structure/style tests that assert the navigation labels, compact
  grid spacing, full-width table behavior, and reduced representative column
  widths.
- Run the focused host manager tests.
- Run the frontend build to catch Vue and TypeScript integration issues.

## Non-goals

- No changes to host data, API contracts, sorting, pagination, or column
  visibility behavior.
- No responsive layout redesign.
- No changes to navigation keys, routes, permissions, or page behavior.

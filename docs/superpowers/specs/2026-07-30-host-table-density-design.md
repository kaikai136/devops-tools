# Host Table Density Design

## Goal

Make the host management table more compact as a whole, reducing unnecessary
horizontal whitespace while keeping the current visible columns, sorting,
sticky status/actions columns, and row actions unchanged.

## Scope

- Adjust the host table column minimum widths in `HostManager.vue`.
- Reduce the table row column gap and horizontal padding in `table.css`.
- Keep the status and actions columns wide enough for their badges and icon
  buttons.
- Preserve the current column visibility behavior and existing uncommitted
  column-default changes.

## Implementation

Use the existing CSS grid configuration. Lower the minimum widths and fractional
widths for the regular host columns by roughly 10% to 15%, reduce the grid gap
from 12px to 8px, and reduce row horizontal padding from 18px to 14px.

The selection column remains compact. The status column remains at 86px and
the actions column remains at 132px so verification badges and action buttons
do not become cramped. The computed table minimum width will continue to be
derived from the configured column minimum widths.

## Validation

- Add a focused structure/style test that asserts the compact grid spacing and
  the reduced representative column widths.
- Run the focused host manager tests.
- Run the frontend build to catch Vue and TypeScript integration issues.

## Non-goals

- No changes to host data, API contracts, sorting, pagination, or column
  visibility behavior.
- No responsive layout redesign.

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const shellState = readFileSync(new URL('../src/composables/app/useShellState.ts', import.meta.url), 'utf8');

test('does not auto-collapse the sidebar when selecting host management', () => {
  assert.doesNotMatch(shellState, /if\s*\(\s*key\s*===\s*['"]hosts['"]\s*\)\s*\{\s*sidebarCollapsed\.value\s*=\s*true\s*;/s);
});

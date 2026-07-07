import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const source = readFileSync(new URL('../src/composables/features/useHostManager.ts', import.meta.url), 'utf8');

test('creates a default group before opening a new host form when no group exists', () => {
  assert.match(source, /async function ensureDefaultHostGroup\(\)/);
  assert.match(source, /targetGroup = await ensureDefaultHostGroup\(\)/);
  assert.match(source, /createHostGroup\(\{\s*name: 'default'/);
});

import assert from 'node:assert/strict';
import test from 'node:test';

import { navGroups } from '../.tmp/navigation.mjs';

test('places network tools below host management in the sidebar', () => {
  assert.deepEqual(navGroups.map((group) => group.key), ['host', 'network', 'security', 'system']);
});

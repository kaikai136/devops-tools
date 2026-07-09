import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const component = readFileSync(new URL('../src/components/tools/AccountManager.vue', import.meta.url), 'utf8');

test('hides host credential port from account manager list and dialog', () => {
  assert.doesNotMatch(component, /credential\.port/);
  assert.doesNotMatch(component, /form\.value\.port/);
  assert.doesNotMatch(component, /v-model\.number="form\.port"/);
});

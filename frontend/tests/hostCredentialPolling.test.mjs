import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const verificationSource = readFileSync(
  new URL('../src/features/hosts/composables/useHostVerification.ts', import.meta.url),
  'utf8',
);

test('host verification reports when a credential was auto saved from account management', () => {
  assert.match(verificationSource, /credentialSaved/);
  assert.match(verificationSource, /已保存登录信息/);
});

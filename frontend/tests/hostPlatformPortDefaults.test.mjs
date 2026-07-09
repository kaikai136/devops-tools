import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const source = readFileSync(new URL('../src/composables/features/useHostManager.ts', import.meta.url), 'utf8');

test('new host form defaults port by selected platform', () => {
  assert.match(source, /function defaultPortForHostOs\(/);
  assert.match(source, /value === 'windows' \? RDP_DEFAULT_PORT : SSH_DEFAULT_PORT/);
  assert.match(source, /hostForm\.value\.port = defaultPortForHostOs\(nextOs\)/);
  assert.match(source, /hostDialog\.value\?\.mode !== 'create'/);
});

test('credential selection does not override host port', () => {
  const applyCredential = source.slice(source.indexOf('function applyCredentialToHostForm'), source.indexOf('function uploadHostPrivateKey'));
  assert.doesNotMatch(applyCredential, /hostForm\.value\.port/);
});

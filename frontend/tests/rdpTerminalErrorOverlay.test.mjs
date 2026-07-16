import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const source = readFileSync(new URL('../src/components/terminal/WebTerminalPage.vue', import.meta.url), 'utf8');

test('rdp terminal tabs expose a visible connection error overlay', () => {
  assert.match(source, /rdpErrorMessage/);
  assert.match(source, /terminal-rdp-status-overlay/);
  assert.match(source, /guacd/);
});

test('rdp tunnel passes width and height through Guacamole connect data', () => {
  assert.match(source, /function buildRdpConnectionQuery/);
  assert.match(source, /client\.connect\(buildRdpConnectionQuery\(tab\)\)/);
  assert.doesNotMatch(source, /rdp\/\$\{tab\.host\.id\}\/\?\$\{params\.toString\(\)\}/);
});

test('rdp display resize refits after the first remote frame reports dimensions', () => {
  assert.match(source, /display\.onresize = \(\) => fitTerminal\(tab\)/);
  assert.match(source, /display\.onresize = null/);
});

import assert from 'node:assert/strict';
import test from 'node:test';

import { readStoredTerminalFontSize } from '../.tmp/terminal-settings.mjs';

test('uses 17 when terminal font size storage is empty', () => {
  assert.equal(readStoredTerminalFontSize(null), 17);
});

test('keeps a saved terminal font size within the allowed range', () => {
  assert.equal(readStoredTerminalFontSize('19'), 19);
});

test('clamps out-of-range terminal font sizes', () => {
  assert.equal(readStoredTerminalFontSize('4'), 10);
  assert.equal(readStoredTerminalFontSize('40'), 24);
});

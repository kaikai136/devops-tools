import { readFileSync } from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';

test('simple host terminal has its own HTML entry and Vite input', () => {
  const viteConfig = readFileSync(new URL('../vite.config.ts', import.meta.url), 'utf8');
  const html = readFileSync(new URL('../host-terminal.html', import.meta.url), 'utf8');

  assert.match(viteConfig, /hostTerminal:\s*resolve\(__dirname,\s*'host-terminal\.html'\)/);
  assert.match(html, /id="host-terminal-app"/);
  assert.match(html, /src="\/src\/host-terminal\.ts"/);
});

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const styles = readFileSync(new URL('../src/styles/tools/system-settings.css', import.meta.url), 'utf8');

function cssRule(selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return [...styles.matchAll(new RegExp(`${escaped}\\s*\\{[^}]*\\}`, 'gs'))].map((match) => match[0]).join('\n');
}

test('login and footer previews expand instead of using internal vertical scrollbars', () => {
  assert.match(cssRule('.settings-preview-panel'), /grid-template-rows:\s*auto\s+auto;/);
  assert.match(cssRule('.settings-preview-panel'), /overflow:\s*visible;/);
  assert.match(cssRule('.settings-preview-body'), /overflow:\s*visible;/);
  assert.doesNotMatch(cssRule('.settings-preview-body'), /overflow:\s*auto;/);
});

test('login and footer preview text wraps so content can be shown completely', () => {
  assert.match(cssRule('.settings-preview-login strong'), /white-space:\s*normal;/);
  assert.match(cssRule('.settings-preview-login strong'), /overflow-wrap:\s*anywhere;/);
  assert.match(cssRule('.settings-preview-footer'), /flex-wrap:\s*wrap;/);
  assert.match(cssRule('.settings-preview-footer'), /overflow-wrap:\s*anywhere;/);
});

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const component = readFileSync(new URL('../src/shared/components/UserAvatar.vue', import.meta.url), 'utf8');

function styleBlock(selector) {
  const pattern = new RegExp(`${selector.replace('.', '\\.')}\\s*\\{(?<body>[^}]*)\\}`);
  const match = component.match(pattern);
  assert.ok(match?.groups?.body, `${selector} style block should exist`);
  return match.groups.body;
}

test('centers the fallback avatar initial inside the avatar square', () => {
  const initialStyles = styleBlock('.user-avatar-initial');

  assert.match(initialStyles, /display:\s*grid;/);
  assert.match(initialStyles, /place-items:\s*center;/);
  assert.match(initialStyles, /width:\s*100%;/);
  assert.match(initialStyles, /height:\s*100%;/);
  assert.doesNotMatch(initialStyles, /transform:/);
});

import assert from 'node:assert/strict';
import test from 'node:test';

import { getAvatarInitial } from '../.tmp/avatar-utils.mjs';

test('uses the first username character as an uppercase avatar initial', () => {
  assert.equal(getAvatarInitial({ username: 'kaikai', displayName: '运维船长' }), 'K');
});

test('falls back to display name when username is blank', () => {
  assert.equal(getAvatarInitial({ username: '  ', displayName: 'ops' }), 'O');
});

test('returns a question mark when no usable name is available', () => {
  assert.equal(getAvatarInitial({ username: '', displayName: '', firstName: '' }), '?');
});

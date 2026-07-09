import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const navigationSource = readFileSync(new URL('../src/navigation.ts', import.meta.url), 'utf8');

test('adds security scan under security tools navigation', () => {
  const securityGroup = navigationSource.slice(navigationSource.indexOf("key: 'security'"), navigationSource.indexOf("key: 'system'"));
  assert.match(securityGroup, /key: 'securityScan'/);
  assert.match(securityGroup, /label: '安全扫描'/);
});

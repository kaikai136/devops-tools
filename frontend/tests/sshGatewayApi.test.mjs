import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const apiSource = readFileSync(new URL('../src/features/terminal/api/terminal.ts', import.meta.url), 'utf8');
const typeSource = readFileSync(new URL('../src/features/terminal/types.ts', import.meta.url), 'utf8');

test('terminal API exposes SSH gateway connection and file audit helpers', () => {
  assert.match(typeSource, /interface SshGatewayConnectionInfo/);
  assert.match(typeSource, /interface TerminalFileAudit/);
  assert.match(apiSource, /getSshGatewayConnectionInfo/);
  assert.match(apiSource, /listTerminalFileAudits/);
  assert.match(apiSource, /ssh-gateway\/connection-info/);
  assert.match(apiSource, /file-audits/);
});

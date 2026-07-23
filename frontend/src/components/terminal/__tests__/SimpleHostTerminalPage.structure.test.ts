import { parse as parseSfc } from '@vue/compiler-sfc';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

function source() {
  return readFileSync(fileURLToPath(new URL('../SimpleHostTerminalPage.vue', import.meta.url)), 'utf8');
}

describe('SimpleHostTerminalPage structure', () => {
  it('checks current user terminal permission before loading and connecting a host', () => {
    const script = parseSfc(source(), { filename: 'SimpleHostTerminalPage.vue' }).descriptor.scriptSetup?.content ?? '';

    expect(script).toMatch(/const current = await getCurrentUser\(\)/);
    expect(script).toMatch(/if \(!canUseSimpleHostTerminal\(current\.user\.featurePermissionCodes\)\) \{/);
    expect(script).toMatch(/status\.value = 'denied'/);
    expect(script).toMatch(/return;\s*\}\s*const groups = await listTerminalTree\(\)/);
  });

  it('uses existing SSH and RDP protocol helpers for the standalone host terminal', () => {
    const script = parseSfc(source(), { filename: 'SimpleHostTerminalPage.vue' }).descriptor.scriptSetup?.content ?? '';

    expect(script).toContain('buildTerminalWebSocketUrl');
    expect(script).toContain('buildRdpWebSocketUrl');
    expect(script).toContain('buildRdpConnectionQuery');
    expect(script).toContain('getSimpleTerminalProtocol');
  });
});

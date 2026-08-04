import { parse as parseSfc } from '@vue/compiler-sfc';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

function source() {
  return readFileSync(fileURLToPath(new URL('../WebTerminalPage.vue', import.meta.url)), 'utf8');
}

describe('WebTerminalPage structure', () => {
  it('writes live SSH output to xterm without rewriting terminal control streams', () => {
    const script = parseSfc(source(), { filename: 'WebTerminalPage.vue' }).descriptor.scriptSetup?.content ?? '';

    expect(script).toContain("tab.terminal.write(message.data ?? '')");
    expect(script).not.toContain('tab.terminal.write(highlightTerminalOutput');
  });
});

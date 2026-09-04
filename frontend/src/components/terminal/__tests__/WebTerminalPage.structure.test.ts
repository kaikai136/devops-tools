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

  it('normalizes pasted shell command snippets before sending them to terminals', () => {
    const script = parseSfc(source(), { filename: 'WebTerminalPage.vue' }).descriptor.scriptSetup?.content ?? '';

    expect(script).toContain('normalizeTerminalPasteText');
  });

  it('keeps Element Plus tree row content in the row flex layout', () => {
    const styles = readFileSync(fileURLToPath(new URL('../../../styles/terminal.css', import.meta.url)), 'utf8').replace(/\r\n/g, '\n');

    expect(styles).toContain('.terminal-tree-row > span {\n  display: contents;\n}');
    expect(styles).toContain('.terminal-tree-row > span > span {');
    expect(styles).not.toContain('.terminal-tree-row span {');
  });
});

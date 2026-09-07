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

  it('lets terminal context menu contents participate in the button grid', () => {
    const styles = readFileSync(fileURLToPath(new URL('../../../styles/terminal.css', import.meta.url)), 'utf8').replace(/\r\n/g, '\n');

    expect(styles).toContain(
      '.terminal-context-menu-item > span,\n.terminal-tab-context-menu-item > span {\n  display: contents;\n}',
    );
  });

  it('keeps terminal submenu items out of the file browser two-column override', () => {
    const styles = readFileSync(fileURLToPath(new URL('../../../styles/terminal.css', import.meta.url)), 'utf8').replace(/\r\n/g, '\n');

    expect(styles).not.toMatch(
      /^\.terminal-file-context-submenu \.terminal-file-context-menu-item \{$/m,
    );
    expect(styles).toContain(
      '.terminal-file-context-menu:not(.terminal-context-menu) .terminal-file-context-submenu .terminal-file-context-menu-item {\n  grid-template-columns: 24px minmax(0, 1fr);\n}',
    );
    expect(styles).toContain(
      '.terminal-context-submenu > .terminal-context-menu-item {\n  grid-template-columns: 24px minmax(0, 1fr) auto;\n}',
    );
  });

  it('raises the hovered terminal context row above neighboring rows so submenus stay visible', () => {
    const styles = readFileSync(fileURLToPath(new URL('../../../styles/terminal.css', import.meta.url)), 'utf8').replace(/\r\n/g, '\n');

    expect(styles).toContain('.terminal-file-context-menu-row:hover {\n  z-index: 2;\n}');
    expect(styles).toContain('.terminal-file-context-menu-row:focus-within {\n  z-index: 2;\n}');
  });

  it('aligns terminal submenus to the parent outer edge without covering their left column', () => {
    const script = parseSfc(source(), { filename: 'WebTerminalPage.vue' }).descriptor.scriptSetup?.content ?? '';
    const template = parseSfc(source(), { filename: 'WebTerminalPage.vue' }).descriptor.template?.content ?? '';
    const styles = readFileSync(fileURLToPath(new URL('../../../styles/terminal.css', import.meta.url)), 'utf8').replace(/\r\n/g, '\n');

    expect(script).toContain('const TERMINAL_CONTEXT_SUBMENU_WIDTH = 226;');
    expect(script).toContain('const TERMINAL_TAB_CONTEXT_SUBMENU_WIDTH = 232;');
    expect(script).toContain('const TERMINAL_CONTEXT_SUBMENU_OFFSET = 1;');
    expect(script).toContain('function isTerminalContextSubmenuLeft(x: number, menuWidth: number, submenuWidth: number)');
    expect(script).toContain('const rightSpace = window.innerWidth - (x + menuWidth);');
    expect(script).toContain('const leftSpace = x;');
    expect(script).toContain('const requiredSubmenuSpace = submenuWidth + TERMINAL_CONTEXT_SUBMENU_OFFSET;');
    expect(script).toContain('if (rightSpace < requiredSubmenuSpace && leftSpace >= requiredSubmenuSpace) {');
    expect(script).toContain('if (leftSpace < requiredSubmenuSpace && rightSpace >= requiredSubmenuSpace) {');
    expect(script).toContain('return leftSpace > rightSpace;');
    expect(script).not.toContain('+ 16');
    expect(template).toContain(
      'isTerminalContextSubmenuLeft(terminalTabContextMenu.x, TERMINAL_TAB_CONTEXT_MENU_WIDTH, TERMINAL_TAB_CONTEXT_SUBMENU_WIDTH)',
    );
    expect(template).toContain(
      'isTerminalContextSubmenuLeft(terminalContextMenu.x, TERMINAL_CONTEXT_MENU_WIDTH, TERMINAL_CONTEXT_SUBMENU_WIDTH)',
    );
    expect(styles).toContain(
      '.terminal-file-context-submenu {\n  position: absolute;\n  top: -4px;\n  left: calc(100% + 1px);\n  display: none;\n  width: 190px;\n  z-index: 1;',
    );
    expect(styles).toContain(
      '.terminal-file-context-menu.submenu-left .terminal-file-context-submenu {\n  right: calc(100% + 1px);\n  left: auto;\n}',
    );
  });
});

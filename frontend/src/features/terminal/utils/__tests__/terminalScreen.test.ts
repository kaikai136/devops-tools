import { describe, expect, it } from 'vitest';

import {
  createTerminalScreenOptions,
  getTerminalVisibleText,
  handleTerminalCopyShortcut,
  toSingleLineTerminalText,
} from '../terminalScreen';

describe('terminal screen helpers', () => {
  it('creates the same black screen terminal options used by the full terminal', () => {
    const options = createTerminalScreenOptions(19);

    expect(options).toMatchObject({
      cursorBlink: true,
      convertEol: false,
      fontFamily: 'Consolas, "Courier New", monospace',
      fontSize: 19,
      lineHeight: 1.25,
      scrollback: 5000,
      theme: {
        background: '#000000',
        foreground: '#f5f7fb',
        cursor: '#f5f7fb',
        selectionBackground: '#7e22ce',
      },
    });
  });

  it('copies the selected terminal text for the terminal copy shortcut', async () => {
    const writes: string[] = [];
    const handled = handleTerminalCopyShortcut(
      { ctrlKey: true, metaKey: false, key: 'c' },
      {
        hasSelection: () => true,
        getSelection: () => 'root@host:~#',
      },
      {
        writeText: async (value) => {
          writes.push(value);
        },
      },
    );

    expect(handled).toBe(false);
    await Promise.resolve();
    expect(writes).toEqual(['root@host:~#']);
  });

  it('lets normal keyboard input continue when there is no selected text to copy', () => {
    const handled = handleTerminalCopyShortcut(
      { ctrlKey: true, metaKey: false, key: 'c' },
      {
        hasSelection: () => false,
        getSelection: () => '',
      },
      { writeText: async () => undefined },
    );

    expect(handled).toBe(true);
  });

  it('reads only the visible terminal rows for screen copy', () => {
    const lines = ['old output', 'visible one', 'visible two', 'below viewport'];
    const terminal = {
      rows: 2,
      buffer: {
        active: {
          viewportY: 1,
          length: lines.length,
          getLine: (index: number) => ({
            translateToString: () => lines[index],
          }),
        },
      },
    };

    expect(getTerminalVisibleText(terminal)).toBe('visible one\nvisible two');
  });

  it('normalizes multiline selected text for single-line paste', () => {
    expect(toSingleLineTerminalText('  ps aux\n\n grep nginx\r\n')).toBe('ps aux grep nginx');
  });
});

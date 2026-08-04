import { describe, expect, it } from 'vitest';

import {
  attachTerminalPasteHandler,
  getClipboardTextFromPasteEvent,
  createTerminalScreenOptions,
  getTerminalVisibleText,
  handleTerminalCopyShortcut,
  toSingleLineTerminalText,
  writeTextToClipboard,
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

  it('falls back to a hidden textarea copy command when clipboard write is blocked', async () => {
    const commands: string[] = [];
    const appended: unknown[] = [];
    const removed: unknown[] = [];
    const textarea = {
      value: '',
      style: {},
      focus: () => undefined,
      select: () => undefined,
    };
    const handled = await writeTextToClipboard(
      'copied from terminal',
      { writeText: async () => { throw new Error('blocked'); } },
      {
        createElement: () => textarea,
        execCommand: (command: string) => {
          commands.push(command);
          return true;
        },
        body: {
          appendChild: (node: unknown) => appended.push(node),
          removeChild: (node: unknown) => removed.push(node),
        },
      },
    );

    expect(handled).toBe(true);
    expect(textarea.value).toBe('copied from terminal');
    expect(commands).toEqual(['copy']);
    expect(appended).toEqual([textarea]);
    expect(removed).toEqual([textarea]);
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

  it('reads plain text from a paste event and prevents browser-only paste', () => {
    let prevented = false;
    const event = {
      preventDefault: () => {
        prevented = true;
      },
      clipboardData: {
        getData: (type: string) => (type === 'text/plain' ? 'echo pasted' : ''),
      },
    };

    expect(getClipboardTextFromPasteEvent(event)).toBe('echo pasted');
    expect(prevented).toBe(true);
  });

  it('falls back to generic clipboard text from a paste event', () => {
    const event = {
      preventDefault: () => undefined,
      clipboardData: {
        getData: (type: string) => (type === 'text' ? 'whoami' : ''),
      },
    };

    expect(getClipboardTextFromPasteEvent(event)).toBe('whoami');
  });

  it('attaches a window capture paste listener scoped to the terminal container and disposes it', () => {
    const sent: string[] = [];
    const listeners = new Map<string, EventListenerOrEventListenerObject>();
    const terminalChild = {};
    const outside = {};
    const container = {
      contains: (target: unknown) => target === terminalChild,
    } as HTMLElement;
    const eventTarget = {
      addEventListener: (type: string, listener: EventListenerOrEventListenerObject, capture?: boolean) => {
        if (capture) listeners.set(type, listener);
      },
      removeEventListener: (type: string, listener: EventListenerOrEventListenerObject, capture?: boolean) => {
        if (capture && listeners.get(type) === listener) listeners.delete(type);
      },
    };
    const disposable = attachTerminalPasteHandler(container, (value) => {
      sent.push(value);
    }, eventTarget);
    const pasteListener = listeners.get('paste');
    if (typeof pasteListener !== 'function') throw new Error('paste listener missing');

    pasteListener({
      target: outside,
      preventDefault: () => undefined,
      clipboardData: {
        getData: (type: string) => (type === 'text/plain' ? 'ignored' : ''),
      },
    } as unknown as ClipboardEvent);
    pasteListener({
      target: terminalChild,
      preventDefault: () => undefined,
      clipboardData: {
        getData: (type: string) => (type === 'text/plain' ? 'uptime' : ''),
      },
    } as unknown as ClipboardEvent);

    expect(sent).toEqual(['uptime']);
    disposable.dispose();
    expect(listeners.has('paste')).toBe(false);
  });
});

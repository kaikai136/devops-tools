import type { IBufferLine, ITerminalOptions, Terminal } from '@xterm/xterm';
import type { ISearchOptions } from '@xterm/addon-search';

export interface TerminalSearchMatch {
  row: number;
  col: number;
  size: number;
}

export const CONTROL_C = '\x03';
export const MOUSE_SELECTION_INTERRUPT_SUPPRESSION_MS = 250;
export const MOUSE_DOUBLE_CLICK_INTERRUPT_SUPPRESSION_MS = 1200;
export const TERMINAL_FONT_SIZE_STORAGE_KEY = 'ops-tool.web-terminal.font-size';
export const TERMINAL_SEARCH_DECORATIONS: NonNullable<ISearchOptions['decorations']> = {
  matchBackground: '#7c3aed',
  matchBorder: '#c084fc',
  matchOverviewRuler: '#a855f7',
  activeMatchBackground: '#a21caf',
  activeMatchBorder: '#f0abfc',
  activeMatchColorOverviewRuler: '#d946ef',
};

interface ClipboardWriter {
  writeText(value: string): Promise<void>;
}

interface TerminalSelectionReader {
  hasSelection(): boolean;
  getSelection(): string;
}

interface TerminalBufferTextReader {
  rows: number;
  buffer: {
    active: {
      viewportY: number;
      length: number;
      getLine(index: number): { translateToString(trimRight?: boolean): string } | undefined;
    };
  };
}

export function createTerminalScreenOptions(fontSize: number): ITerminalOptions {
  return {
    cursorBlink: true,
    convertEol: false,
    fontFamily: 'Consolas, "Courier New", monospace',
    fontSize,
    lineHeight: 1.25,
    scrollback: 5000,
    theme: {
      background: '#000000',
      foreground: '#f5f7fb',
      cursor: '#f5f7fb',
      selectionBackground: '#7e22ce',
    },
  };
}

export function handleTerminalCopyShortcut(
  event: Pick<KeyboardEvent, 'ctrlKey' | 'metaKey' | 'key'>,
  terminal: TerminalSelectionReader,
  clipboard: ClipboardWriter | undefined | null = globalThis.navigator?.clipboard,
) {
  const isCopyShortcut = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'c';
  if (!isCopyShortcut || !terminal.hasSelection()) return true;

  const selection = terminal.getSelection();
  if (selection) {
    clipboard?.writeText(selection).catch(() => undefined);
  }
  return false;
}

export function getSendableTerminalData(data: string, suppressInterruptUntil: number, now = Date.now()) {
  if (!data.includes(CONTROL_C) || now > suppressInterruptUntil) return data;
  return data.split(CONTROL_C).join('');
}

export function toSingleLineTerminalText(value: string) {
  return value.replace(/[\r\n]+/g, ' ').replace(/\s+/g, ' ').trim();
}

export function getTerminalVisibleText(terminal: TerminalBufferTextReader) {
  const buffer = terminal.buffer.active;
  const start = buffer.viewportY;
  const end = Math.min(buffer.length, start + terminal.rows);
  const lines: string[] = [];
  for (let index = start; index < end; index += 1) {
    lines.push(buffer.getLine(index)?.translateToString(true) ?? '');
  }
  return lines.join('\n').trimEnd();
}

export function getTerminalBufferText(terminal: TerminalBufferTextReader) {
  const buffer = terminal.buffer.active;
  const lines: string[] = [];
  for (let index = 0; index < buffer.length; index += 1) {
    lines.push(buffer.getLine(index)?.translateToString(true) ?? '');
  }
  return lines.join('\n').trimEnd();
}

export function sanitizeTerminalLogFileName(value: string) {
  return value.trim().replace(/[<>:"/\\|?*\x00-\x1f]/g, '_') || 'terminal';
}

export function getTerminalSearchOptions(incremental = false): ISearchOptions {
  return {
    caseSensitive: false,
    incremental,
    decorations: TERMINAL_SEARCH_DECORATIONS,
  };
}

export function collectTerminalSearchMatches(terminal: Terminal, query: string) {
  const normalizedQuery = query.toLowerCase();
  const matches: TerminalSearchMatch[] = [];
  if (!normalizedQuery) return matches;

  const buffer = terminal.buffer.active;
  const maxRow = buffer.baseY + terminal.rows;
  for (let row = 0; row < maxRow; row += 1) {
    const line = buffer.getLine(row);
    if (!line || line.isWrapped) continue;

    const logicalLine = getTerminalLogicalSearchLine(terminal, row, maxRow);
    const searchText = logicalLine.text.toLowerCase();
    let index = searchText.indexOf(normalizedQuery);
    while (index !== -1) {
      const position = getTerminalSearchBufferPosition(logicalLine.parts, index);
      if (position) {
        matches.push({
          row: position.row,
          col: position.col,
          size: Math.max(1, query.length),
        });
      }
      index = searchText.indexOf(normalizedQuery, index + Math.max(1, normalizedQuery.length));
    }
  }
  return matches;
}

export function selectTerminalSearchMatch(terminal: Terminal, match: TerminalSearchMatch | undefined) {
  if (!match) return;
  const buffer = terminal.buffer.active;
  if (match.row < buffer.viewportY || match.row >= buffer.viewportY + terminal.rows) {
    terminal.scrollToLine(Math.max(0, match.row - Math.floor(terminal.rows / 2)));
  }
  terminal.select(match.col, match.row, match.size);
}

function getTerminalLogicalSearchLine(terminal: Terminal, startRow: number, maxRow: number) {
  const parts: Array<{ row: number; line: IBufferLine; start: number; text: string }> = [];
  const buffer = terminal.buffer.active;
  let text = '';
  for (let row = startRow; row < maxRow; row += 1) {
    const line = buffer.getLine(row);
    if (!line) break;
    const nextLine = row + 1 < maxRow ? buffer.getLine(row + 1) : undefined;
    const lineText = line.translateToString(!nextLine?.isWrapped);
    parts.push({ row, line, start: text.length, text: lineText });
    text += lineText;
    if (!nextLine?.isWrapped) break;
  }
  return { text, parts };
}

function getTerminalSearchBufferPosition(
  parts: Array<{ row: number; line: IBufferLine; start: number; text: string }>,
  stringIndex: number,
) {
  for (const part of parts) {
    if (stringIndex < part.start || stringIndex >= part.start + part.text.length) continue;
    return {
      row: part.row,
      col: getTerminalColumnFromStringOffset(part.line, stringIndex - part.start),
    };
  }
  return null;
}

function getTerminalColumnFromStringOffset(line: IBufferLine, offset: number) {
  let consumed = 0;
  for (let col = 0; col < line.length; col += 1) {
    const cell = line.getCell(col);
    if (!cell || cell.getWidth() === 0) continue;
    const chars = cell.getChars() || ' ';
    const nextConsumed = consumed + chars.length;
    if (offset <= consumed || offset < nextConsumed) return col;
    consumed = nextConsumed;
  }
  return Math.max(0, Math.min(line.length - 1, offset));
}

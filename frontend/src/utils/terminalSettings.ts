export const TERMINAL_FONT_SIZE_DEFAULT = 17;
export const TERMINAL_FONT_SIZE_MIN = 10;
export const TERMINAL_FONT_SIZE_MAX = 24;

export function clampTerminalFontSize(value: number) {
  if (!Number.isFinite(value)) return TERMINAL_FONT_SIZE_DEFAULT;
  return Math.min(Math.max(Math.round(value), TERMINAL_FONT_SIZE_MIN), TERMINAL_FONT_SIZE_MAX);
}

export function readStoredTerminalFontSize(storedValue: string | null) {
  if (storedValue === null || !storedValue.trim()) return TERMINAL_FONT_SIZE_DEFAULT;
  return clampTerminalFontSize(Number(storedValue));
}

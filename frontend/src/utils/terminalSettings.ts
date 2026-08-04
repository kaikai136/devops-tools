import type { TerminalSettingsConfig } from '../types';

export const TERMINAL_FONT_SIZE_DEFAULT = 17;
export const TERMINAL_FONT_SIZE_MIN = 10;
export const TERMINAL_FONT_SIZE_MAX = 24;

export function createDefaultTerminalSettings(): TerminalSettingsConfig {
  return {
    sshConnectTimeoutSeconds: 15,
    sshBannerTimeoutSeconds: 30,
    sshAuthTimeoutSeconds: 20,
    sshConnectAttempts: 3,
    sshRetryDelayMs: 800,
    sshKeepaliveSeconds: 30,
    webSocketHeartbeatSeconds: 20,
    idleDisconnectMinutes: 0,
    initialReadTimeoutSeconds: 3,
    initialReadIdleTimeoutMs: 350,
    commandReadTimeoutSeconds: 30,
    commandReadIdleTimeoutMs: 350,
    readerPollIntervalMs: 30,
    cwdHookSuppressEchoMs: 2000,
    cwdHookDrainTimeoutMs: 800,
    cwdHookDrainIdleTimeoutMs: 120,
    defaultCols: 120,
    defaultRows: 36,
    defaultFontSize: 17,
    scrollbackLines: 5000,
  };
}

const terminalSettingLimits: Record<keyof TerminalSettingsConfig, [number, number]> = {
  sshConnectTimeoutSeconds: [1, 300],
  sshBannerTimeoutSeconds: [1, 300],
  sshAuthTimeoutSeconds: [1, 300],
  sshConnectAttempts: [1, 10],
  sshRetryDelayMs: [0, 10000],
  sshKeepaliveSeconds: [0, 3600],
  webSocketHeartbeatSeconds: [0, 3600],
  idleDisconnectMinutes: [0, 1440],
  initialReadTimeoutSeconds: [1, 60],
  initialReadIdleTimeoutMs: [50, 10000],
  commandReadTimeoutSeconds: [1, 3600],
  commandReadIdleTimeoutMs: [50, 10000],
  readerPollIntervalMs: [10, 1000],
  cwdHookSuppressEchoMs: [0, 10000],
  cwdHookDrainTimeoutMs: [100, 10000],
  cwdHookDrainIdleTimeoutMs: [50, 10000],
  defaultCols: [40, 300],
  defaultRows: [10, 120],
  defaultFontSize: [10, 24],
  scrollbackLines: [100, 50000],
};

function cleanInt(value: unknown, fallback: number, min: number, max: number) {
  const number = Number(value);
  if (!Number.isFinite(number)) return fallback;
  return Math.min(max, Math.max(min, Math.round(number)));
}

export function normalizeTerminalSettings(value: unknown): TerminalSettingsConfig {
  const defaults = createDefaultTerminalSettings();
  const raw = typeof value === 'object' && value !== null ? (value as Partial<TerminalSettingsConfig>) : {};
  const normalized = { ...defaults };
  for (const key of Object.keys(defaults) as Array<keyof TerminalSettingsConfig>) {
    const [min, max] = terminalSettingLimits[key];
    normalized[key] = cleanInt(raw[key], defaults[key], min, max);
  }
  return normalized;
}

export function clampTerminalFontSize(value: number, fallback = TERMINAL_FONT_SIZE_DEFAULT) {
  if (!Number.isFinite(value)) return fallback;
  return Math.min(Math.max(Math.round(value), TERMINAL_FONT_SIZE_MIN), TERMINAL_FONT_SIZE_MAX);
}

export function readStoredTerminalFontSize(storedValue: string | null, globalDefaultFontSize = TERMINAL_FONT_SIZE_DEFAULT) {
  const defaultFontSize = clampTerminalFontSize(globalDefaultFontSize);
  if (storedValue === null || !storedValue.trim()) return defaultFontSize;
  return clampTerminalFontSize(Number(storedValue), defaultFontSize);
}

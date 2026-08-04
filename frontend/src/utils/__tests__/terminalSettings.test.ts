import { describe, expect, it } from 'vitest';

import {
  createDefaultTerminalSettings,
  normalizeTerminalSettings,
  readStoredTerminalFontSize,
} from '../terminalSettings';

describe('terminal settings utilities', () => {
  it('normalizes missing terminal settings with current defaults', () => {
    expect(normalizeTerminalSettings({})).toEqual(createDefaultTerminalSettings());
  });

  it('clamps terminal settings into supported ranges', () => {
    const settings = normalizeTerminalSettings({
      sshConnectTimeoutSeconds: 0,
      sshBannerTimeoutSeconds: 999,
      sshAuthTimeoutSeconds: 12,
      sshConnectAttempts: 99,
      sshRetryDelayMs: -1,
      sshKeepaliveSeconds: 0,
      webSocketHeartbeatSeconds: 0,
      idleDisconnectMinutes: 2000,
      defaultFontSize: 40,
      scrollbackLines: 999999,
    });

    expect(settings.sshConnectTimeoutSeconds).toBe(1);
    expect(settings.sshBannerTimeoutSeconds).toBe(300);
    expect(settings.sshAuthTimeoutSeconds).toBe(12);
    expect(settings.sshConnectAttempts).toBe(10);
    expect(settings.sshRetryDelayMs).toBe(0);
    expect(settings.sshKeepaliveSeconds).toBe(0);
    expect(settings.webSocketHeartbeatSeconds).toBe(0);
    expect(settings.idleDisconnectMinutes).toBe(1440);
    expect(settings.defaultFontSize).toBe(24);
    expect(settings.scrollbackLines).toBe(50000);
  });

  it('uses global default terminal font size only when local storage is empty', () => {
    expect(readStoredTerminalFontSize(null, 19)).toBe(19);
    expect(readStoredTerminalFontSize('', 19)).toBe(19);
    expect(readStoredTerminalFontSize('15', 19)).toBe(15);
  });
});

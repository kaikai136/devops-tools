import { describe, expect, it } from 'vitest';

import {
  calculateRdpDisplayScale,
  buildRdpConnectionQuery,
  buildRdpWebSocketUrl,
  buildTerminalWebSocketUrl,
  formatRdpConnectionErrorMessage,
  formatTerminalFileSizeValue,
  parseTerminalHostQuery,
} from '../protocol';

describe('terminal protocol helpers', () => {
  it.each([
    ['', null],
    ['?host=42', 42],
    ['?host=0', null],
    ['?host=-3', -3],
    ['?host=not-a-number', null],
    ['?host=7&name=%E6%9C%BA%E5%99%A8%20A', 7],
  ])('parses terminal host query %s', (search, expected) => {
    expect(parseTerminalHostQuery(search)).toBe(expected);
  });

  it.each([
    ['http:', 'ops.example.test', 7, 'ws://ops.example.test/ws/web-terminal/7/'],
    ['https:', 'ops.example.test:8443', 8, 'wss://ops.example.test:8443/ws/web-terminal/8/'],
  ])('builds the SSH websocket URL', (protocol, host, hostId, expected) => {
    expect(buildTerminalWebSocketUrl(protocol, host, hostId)).toBe(expected);
  });

  it('builds the unchanged RDP websocket URL', () => {
    expect(buildRdpWebSocketUrl('https:', 'ops.example.test', 9)).toBe(
      'wss://ops.example.test/ws/web-terminal/rdp/9/',
    );
  });

  it.each([
    [1280, 720, 'width=1280&height=720'],
    [100, 80, 'width=320&height=240'],
    [1440.9, 900.8, 'width=1440&height=900'],
    [undefined, undefined, 'width=1280&height=720'],
  ])('clamps and serializes the RDP size', (width, height, expected) => {
    expect(buildRdpConnectionQuery(width, height)).toBe(expected);
  });

  it.each([
    [1280, 720, 1280, 720, 1],
    [960, 540, 1920, 1080, 0.5],
    [1200, 600, 1600, 1200, 0.5],
  ])('calculates the RDP display scale for %s x %s inside %s x %s', (viewportWidth, viewportHeight, displayWidth, displayHeight, expected) => {
    expect(calculateRdpDisplayScale(viewportWidth, viewportHeight, displayWidth, displayHeight)).toBe(expected);
  });

  it.each([
    [1280, 720, 0, 720],
    [1280, 720, 1280, 0],
    [0, 720, 1280, 720],
    [1280, Number.NaN, 1280, 720],
  ])('does not scale an RDP display before both viewport and display are measurable', (viewportWidth, viewportHeight, displayWidth, displayHeight) => {
    expect(calculateRdpDisplayScale(viewportWidth, viewportHeight, displayWidth, displayHeight)).toBeNull();
  });

  it.each([
    [0, '0 B'],
    [1023, '1023 B'],
    [1024, '1 KB'],
    [1536, '1.50 KB'],
    [10 * 1024, '10 KB'],
    ['12.5 MB', '12.5 MB'],
  ])('keeps file-size formatting for %s', (size, expected) => {
    expect(formatTerminalFileSizeValue(size)).toBe(expected);
  });

  it('formats RDP security negotiation failures with a Chinese actionable message', () => {
    expect(formatRdpConnectionErrorMessage(new Error('Server refused connection (wrong security type?)'))).toBe(
      'RDP 安全协商失败，请确认目标端口是 RDP 服务、远程桌面已开启，并检查 Windows 安全层/NLA 配置。',
    );
  });

  it('keeps explicit RDP error messages and falls back when none is available', () => {
    expect(formatRdpConnectionErrorMessage({ message: 'Authentication failed' })).toBe('Authentication failed');
    expect(formatRdpConnectionErrorMessage()).toBe('RDP 连接失败，请检查远程桌面服务。');
  });
});

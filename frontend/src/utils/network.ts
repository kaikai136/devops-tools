import type { HostResult } from '../types';

export function createHostGrid(segment: string): HostResult[] {
  const normalizedSegment = segment.trim() || '192.168.1';
  return Array.from({ length: 254 }, (_, index) => {
    const host = index + 1;
    return {
      host,
      ip: `${normalizedSegment}.${host}`,
      status: 'untested',
      response_time: null,
    };
  });
}

export function parsePortInput(input: string): number[] {
  const ports = new Set<number>();
  const tokens = input.replace(/，/g, ',').split(/[,\s]+/).map((item) => item.trim()).filter(Boolean);

  for (const token of tokens) {
    if (token.includes('-')) {
      const [startText, endText] = token.split('-', 2);
      const start = Number(startText);
      const end = Number(endText);
      if (!Number.isInteger(start) || !Number.isInteger(end) || start < 1 || end > 65535 || start > end) {
        throw new Error(`端口范围不正确：${token}`);
      }
      for (let port = start; port <= end; port += 1) ports.add(port);
    } else {
      const port = Number(token);
      if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error(`端口不正确：${token}`);
      ports.add(port);
    }
  }

  if (!ports.size) throw new Error('请至少输入一个端口');
  return Array.from(ports).sort((left, right) => left - right);
}

export function sleep(ms: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException('Aborted', 'AbortError'));
      return;
    }
    const timer = window.setTimeout(resolve, ms);
    signal.addEventListener(
      'abort',
      () => {
        window.clearTimeout(timer);
        reject(new DOMException('Aborted', 'AbortError'));
      },
      { once: true },
    );
  });
}

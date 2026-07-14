export function parseTerminalHostQuery(search: string) {
  const hostId = Number(new URLSearchParams(search).get('host'));
  return hostId ? hostId : null;
}

export function buildTerminalWebSocketUrl(locationProtocol: string, locationHost: string, hostId: number) {
  const protocol = locationProtocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${locationHost}/ws/web-terminal/${hostId}/`;
}

export function buildRdpWebSocketUrl(locationProtocol: string, locationHost: string, hostId: number) {
  const protocol = locationProtocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${locationHost}/ws/web-terminal/rdp/${hostId}/`;
}

export function buildRdpConnectionQuery(width?: number, height?: number) {
  return new URLSearchParams({
    width: String(Math.max(320, Math.floor(width || 1280))),
    height: String(Math.max(240, Math.floor(height || 720))),
  }).toString();
}

export function formatTerminalFileSizeValue(size: number | string) {
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  if (typeof size === 'string') return size;
  let valueSize = size;
  let unitIndex = 0;
  while (valueSize >= 1024 && unitIndex < units.length - 1) {
    valueSize /= 1024;
    unitIndex += 1;
  }
  const value = unitIndex === 0 ? String(valueSize) : valueSize.toFixed(valueSize >= 10 ? 1 : 2).replace(/\.0+$/, '');
  return `${value} ${units[unitIndex]}`;
}

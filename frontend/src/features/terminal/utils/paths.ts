export function parentTerminalDirectoryPath(path: string) {
  const value = String(path || '.').replace(/\/+$/, '');
  if (!value || value === '.' || value === '~') return '/';
  if (value === '/') return '/';
  if (value.startsWith('~/')) {
    const parent = value.slice(0, value.lastIndexOf('/'));
    return parent || '/';
  }
  if (!value.startsWith('/')) return '/';
  const parent = value.slice(0, value.lastIndexOf('/'));
  return parent || '/';
}

export function joinTerminalPath(directory: string, name: string) {
  const child = String(name || '').trim();
  if (child.startsWith('/') || child.startsWith('~') || child === '.') return child;
  const parent = directory === '' ? '' : String(directory || '.');
  if (parent === '/' || parent === '') return `/${child}`;
  if (parent === '.') return child;
  return `${parent.replace(/\/+$/, '')}/${child}`;
}

export function terminalPathName(path: string) {
  const value = String(path || '').replace(/\/+$/, '');
  if (!value || value === '/') return '/';
  return value.slice(value.lastIndexOf('/') + 1) || value;
}

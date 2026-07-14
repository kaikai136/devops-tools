import { describe, expect, it } from 'vitest';

import {
  joinTerminalPath,
  parentTerminalDirectoryPath,
  terminalPathName,
} from '../paths';

describe('terminal path helpers', () => {
  it.each([
    ['/', '/'],
    ['///', '/'],
    ['.', '/'],
    ['~', '/'],
    ['/srv/app/', '/srv'],
    ['/含 空格/目录/', '/含 空格'],
    ['~/projects/app', '~/projects'],
    ['relative/path', '/'],
  ])('preserves current parent behavior for %s', (path, expected) => {
    expect(parentTerminalDirectoryPath(path)).toBe(expected);
  });

  it.each([
    ['/', 'tmp', '/tmp'],
    ['', 'tmp', '/tmp'],
    ['/srv/', 'app', '/srv/app'],
    ['.', '日志 文件', '日志 文件'],
    ['~/projects', '应用', '~/projects/应用'],
    ['/srv/space ', 'child', '/srv/space /child'],
    ['/srv/app', '.hidden', '/srv/app/.hidden'],
    ['/srv/app', '../logs', '/srv/app/../logs'],
    ['/srv/app', '/absolute/path', '/absolute/path'],
    ['/srv/app', '~', '~'],
  ])('joins %s and %s without changing absolute paths', (directory, name, expected) => {
    expect(joinTerminalPath(directory, name)).toBe(expected);
  });

  it.each([
    ['/', '/'],
    ['/srv/app/', 'app'],
    ['~/projects/应用', '应用'],
    ['plain-name', 'plain-name'],
  ])('reads the final path name from %s', (path, expected) => {
    expect(terminalPathName(path)).toBe(expected);
  });
});

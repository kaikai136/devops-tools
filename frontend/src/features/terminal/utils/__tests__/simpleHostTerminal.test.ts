import { describe, expect, it } from 'vitest';

import {
  canUseSimpleHostTerminal,
  findTerminalHostById,
  getSimpleTerminalProtocol,
} from '../simpleHostTerminal';
import type { TerminalGroup, TerminalHost } from '../../types';

function host(overrides: Partial<TerminalHost>): TerminalHost {
  return {
    id: 1,
    name: 'linux-01',
    group: 1,
    privateIp: '10.0.0.1',
    publicIp: '',
    port: 22,
    loginUser: 'root',
    remark: '',
    verified: true,
    ...overrides,
  };
}

describe('simple host terminal helpers', () => {
  it('requires both host page access and terminal action permission', () => {
    expect(canUseSimpleHostTerminal(['access_hosts', 'action_hosts_terminal'])).toBe(true);
    expect(canUseSimpleHostTerminal(['access_hosts'])).toBe(false);
    expect(canUseSimpleHostTerminal(['action_hosts_terminal'])).toBe(false);
    expect(canUseSimpleHostTerminal([])).toBe(false);
  });

  it('finds a host in nested terminal groups by id', () => {
    const nested = host({ id: 42, name: 'nested' });
    const groups: TerminalGroup[] = [
      { id: 1, name: 'root', hosts: [host({ id: 1 })], children: [{ id: 2, name: 'child', hosts: [nested], children: [] }] },
    ];

    expect(findTerminalHostById(groups, 42)).toEqual(nested);
    expect(findTerminalHostById(groups, 404)).toBeNull();
  });

  it('selects RDP for explicit RDP and Windows hosts, otherwise SSH', () => {
    expect(getSimpleTerminalProtocol(host({ terminalProtocol: 'rdp' }))).toBe('rdp');
    expect(getSimpleTerminalProtocol(host({ platformType: 'windows' }))).toBe('rdp');
    expect(getSimpleTerminalProtocol(host({ os: 'windows' }))).toBe('rdp');
    expect(getSimpleTerminalProtocol(host({ terminalProtocol: 'ssh', platformType: 'linux' }))).toBe('ssh');
  });
});

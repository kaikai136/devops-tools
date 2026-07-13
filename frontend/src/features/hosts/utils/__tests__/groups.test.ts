import { describe, expect, it } from 'vitest';

import type { HostGroup, ManagedHost } from '../../types';
import { compareHosts, findGroup, flattenGroups, flattenVisibleGroups } from '../groups';

const nestedGroups: HostGroup[] = [
  {
    key: 10,
    label: '生产环境',
    count: 3,
    children: [
      {
        key: 11,
        label: '应用节点',
        count: 2,
        children: [{ key: 12, label: '灰度节点', count: 1, children: [] }],
      },
      { key: 13, label: '数据库节点', count: 1 },
    ],
  },
  { key: 20, label: '测试环境', count: 1, children: [{ key: 21, label: '集成测试', count: 1 }] },
];

function host(id: number, name: string, privateIp: string): ManagedHost {
  return {
    id,
    name,
    group: 10,
    publicIp: '',
    privateIp,
    port: 22,
    loginUser: 'root',
    loginPassword: '',
    privateKeyName: '',
    privateKey: '',
    machineName: '',
    systemArch: '',
    systemType: '',
    remark: '',
    cpu: 0,
    memory: 0,
    os: 'centos',
    verified: false,
  };
}

describe('host group pure utilities', () => {
  it('flattens nested groups in root/child order without changing keys or source objects', () => {
    const flattened = flattenGroups(nestedGroups);

    expect(flattened.map(({ key, level }) => ({ key, level }))).toEqual([
      { key: 10, level: 0 },
      { key: 11, level: 1 },
      { key: 12, level: 2 },
      { key: 13, level: 1 },
      { key: 20, level: 0 },
      { key: 21, level: 1 },
    ]);
    expect(flattened.map((group) => group.label)).toEqual(['生产环境', '应用节点', '灰度节点', '数据库节点', '测试环境', '集成测试']);
    expect(nestedGroups[0].key).toBe(10);
    expect(nestedGroups[0].children?.[0].key).toBe(11);
  });

  it('keeps collapsed groups visible while hiding all of their descendants', () => {
    expect(flattenVisibleGroups(nestedGroups, new Set([11])).map(({ key, level }) => ({ key, level }))).toEqual([
      { key: 10, level: 0 },
      { key: 11, level: 1 },
      { key: 13, level: 1 },
      { key: 20, level: 0 },
      { key: 21, level: 1 },
    ]);

    expect(flattenVisibleGroups(nestedGroups, new Set([10])).map((group) => group.key)).toEqual([10, 20, 21]);
  });

  it('finds nested groups by their unchanged numeric key and returns undefined when absent', () => {
    expect(findGroup(nestedGroups, 12)).toBe(nestedGroups[0].children?.[0].children?.[0]);
    expect(findGroup(nestedGroups, 999)).toBeUndefined();
  });

  it('provides deterministic IP ordering while preserving equal-item order', () => {
    const hosts = [host(1, 'first equal', '10.0.0.2'), host(2, 'lower', '10.0.0.1'), host(3, 'second equal', '10.0.0.2')];

    expect([...hosts].sort((left, right) => compareHosts(left, right, 'ip', 'asc')).map((item) => item.id)).toEqual([2, 1, 3]);
    expect([...hosts].sort((left, right) => compareHosts(left, right, 'ip', 'desc')).map((item) => item.id)).toEqual([1, 3, 2]);
  });
});

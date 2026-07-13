import { describe, expect, it } from 'vitest';

import type { ManagedHost } from '../../types';
import {
  buildHostExportPayload,
  formatExportCell,
  formatHostExportValue,
  hostExportColumnOptions,
  parseExportCell,
} from '../export';

const verifiedHost: ManagedHost = {
  id: 7,
  name: 'node-01',
  group: 10,
  publicIp: '203.0.113.7',
  privateIp: '10.0.0.7',
  port: 2222,
  loginUser: 'ops',
  loginPassword: '',
  privateKeyName: 'ops.pem',
  privateKey: '',
  machineName: 'prod-node-01',
  systemArch: 'x86_64',
  systemType: 'Rocky Linux 9',
  remark: 'primary',
  cpu: 8,
  memory: 32,
  os: 'centos',
  verified: true,
  verifyStatus: 'verified',
  createdAt: '2026-07-01T01:02:03Z',
  updatedAt: '2026-07-02T04:05:06Z',
  creator: 'admin',
  platformType: 'linux',
};

const failedHost = {
  ...verifiedHost,
  id: 8,
  name: 'node-02',
  publicIp: undefined,
  privateIp: '10.0.0.8',
  port: 0,
  loginUser: '',
  machineName: 'must-not-export',
  systemArch: null,
  systemType: null,
  remark: null,
  cpu: 16,
  memory: 64,
  os: 'windows',
  verified: false,
  verifyStatus: 'failed',
  createdAt: null,
  updatedAt: null,
  creator: null,
  platformType: null,
} as unknown as ManagedHost;

const groupName = (groupId: number) => ({ 10: '生产环境 / 应用节点' })[groupId] ?? '未分组';

describe('host export pure utilities', () => {
  it('preserves the exact host export field, header, and width order', () => {
    expect(hostExportColumnOptions).toEqual([
      { field: 'group', label: '主机分组', width: 18 },
      { field: 'name', label: '节点', width: 22 },
      { field: 'ip', label: 'IP地址', width: 24 },
      { field: 'machine', label: '机器名称', width: 24 },
      { field: 'systemArch', label: '系统架构', width: 16 },
      { field: 'systemType', label: '系统类型', width: 16 },
      { field: 'config', label: '配置信息', width: 18 },
      { field: 'platformType', label: '平台类型', width: 16 },
      { field: 'user', label: '用户', width: 16 },
      { field: 'port', label: '端口', width: 10 },
      { field: 'createdAt', label: '创建时间', width: 22 },
      { field: 'updatedAt', label: '更新时间', width: 22 },
      { field: 'creator', label: '创建者', width: 16 },
      { field: 'remark', label: '备注', width: 28 },
      { field: 'status', label: '状态', width: 14 },
    ]);
  });

  it('serializes verified host fields exactly in selected column order', () => {
    const payload = buildHostExportPayload([verifiedHost], hostExportColumnOptions, groupName);

    expect(payload).toEqual({
      version: 1,
      groups: [],
      credentials: [],
      hosts: [
        {
          group: '生产环境 / 应用节点',
          name: 'node-01',
          ip: '203.0.113.7\n10.0.0.7',
          machine: 'prod-node-01',
          systemArch: 'x86_64',
          systemType: 'Rocky Linux 9',
          config: '8核 32GB',
          platformType: 'linux',
          user: 'ops',
          port: 2222,
          createdAt: '2026-07-01T01:02:03Z',
          updatedAt: '2026-07-02T04:05:06Z',
          creator: 'admin',
          remark: 'primary',
          status: '已验证',
        },
      ],
    });
    expect(Object.keys(payload.hosts[0])).toEqual(hostExportColumnOptions.map((column) => column.field));
  });

  it('preserves null, fallback, boolean, and failed verification serialization', () => {
    expect(formatHostExportValue(failedHost, 'ip', groupName)).toBe('10.0.0.8');
    expect(formatHostExportValue(failedHost, 'machine', groupName)).toBe('');
    expect(formatHostExportValue(failedHost, 'config', groupName)).toBe('');
    expect(formatHostExportValue(failedHost, 'platformType', groupName)).toBe('windows');
    expect(formatHostExportValue(failedHost, 'port', groupName)).toBe(22);
    expect(formatHostExportValue(failedHost, 'createdAt', groupName)).toBe('');
    expect(formatHostExportValue(failedHost, 'creator', groupName)).toBe('');
    expect(formatHostExportValue(failedHost, 'remark', groupName)).toBe('');
    expect(formatHostExportValue(failedHost, 'systemArch', groupName)).toBe('');
    expect(formatHostExportValue(failedHost, 'status', groupName)).toBe('验证失败');

    expect(formatExportCell('remark', null)).toBe('');
    expect(formatExportCell('enabled', true)).toBe('true');
    expect(formatExportCell('verified', true)).toBe('已验证');
    expect(formatExportCell('verified', false)).toBe('未验证');
    expect(parseExportCell('verified', '是')).toBe(true);
    expect(parseExportCell('verified', 'false')).toBe(false);
    expect(parseExportCell('port', '')).toBe(0);
  });
});

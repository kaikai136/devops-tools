export type TerminalStatus = 'connecting' | 'connected' | 'closed' | 'error';
export type TerminalTabKind = 'ssh' | 'rdp';
export type TerminalDownloadProtocol = 'auto' | 'scp' | 'sftp';

export interface TerminalHost {
  id: number;
  name: string;
  group: number;
  privateIp: string;
  publicIp: string;
  port: number;
  loginUser: string;
  remark: string;
  verified: boolean;
  verifyStatus?: 'unverified' | 'verified' | 'failed';
  os?: string;
  platformType?: string;
  terminalProtocol?: TerminalTabKind;
}

export interface TerminalGroup {
  id: number;
  name: string;
  hosts: TerminalHost[];
  children: TerminalGroup[];
}

export interface TerminalFileEntry {
  name: string;
  type: 'directory' | 'file';
  modifiedAt: string;
  path: string;
  size?: number | string;
  permissions?: string;
  owner?: string;
  group?: string;
}

export interface TerminalFileListResponse {
  path: string;
  protocol: string;
  entries: TerminalFileEntry[];
}

export interface TerminalQuickCommand {
  id: number;
  name: string;
  category: string;
  command: string;
  description: string;
  enabled: boolean;
  sortOrder: number;
  createdAt: string;
  updatedAt: string;
}

export interface TerminalFileProperties {
  name: string;
  path: string;
  directory: string;
  type: 'directory' | 'file';
  size: number;
  modifiedAt: string;
  accessedAt: string;
  owner: string;
  group: string;
  uid: number;
  gid: number;
  permissions: string;
  mode: number;
  octalMode: string;
  special: {
    setuid: boolean;
    setgid: boolean;
    sticky: boolean;
  };
}

export interface TerminalMonitorResponse {
  system: {
    hostname: string;
    arch: string;
    os: string;
    kernel: string;
    uptimeSeconds: number;
  };
  cpu: {
    usagePercent: number;
    load1: number;
    load5: number;
    load15: number;
    cores: number;
  };
  memory: {
    totalBytes: number;
    usedBytes: number;
    availableBytes: number;
    cacheBytes: number;
    usagePercent: number;
  };
  network: Array<{
    name: string;
    rxBytesPerSecond: number;
    txBytesPerSecond: number;
  }>;
  disks: Array<{
    filesystem: string;
    type: string;
    mountpoint: string;
    totalBytes: number;
    usedBytes: number;
    availableBytes: number;
    usagePercent: number;
  }>;
}

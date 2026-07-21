import type { HostGroup, ManagedHost } from '../../types';

export type { HostCredential, HostGroup, ManagedHost } from '../../types';

export type ExportRow = Record<string, string | number | boolean | null>;

export interface HostManagementExport {
  version: number;
  groups: ExportRow[];
  hosts: ExportRow[];
  credentials: ExportRow[];
}

export interface HostManagementImportResponse {
  imported: {
    groups: number;
    hosts: number;
    credentials: number;
  };
}

export interface HostVerifyResponse {
  host: ManagedHost;
  verified: boolean;
  error: string | null;
  credentialSaved: boolean;
}

export interface HostGroupMutationResponse {
  group?: HostGroup;
  groups: HostGroup[];
}

export type HostMutationPayload = Record<string, unknown>;
export type HostGroupMutationPayload = Record<string, unknown>;
export type HostCredentialMutationPayload = Record<string, unknown>;

export type HostTransferFormat = 'json' | 'excel';
export type HostExportScope = 'all' | 'selected';
export type HostExportColumnKey =
  | 'group'
  | 'name'
  | 'ip'
  | 'machine'
  | 'systemArch'
  | 'systemType'
  | 'config'
  | 'platformType'
  | 'user'
  | 'port'
  | 'createdAt'
  | 'updatedAt'
  | 'creator'
  | 'remark'
  | 'status';

export interface ExportColumn {
  field: string;
  label: string;
  width: number;
}

export type HostExportColumnOption = ExportColumn & { field: HostExportColumnKey };

export interface HostExportOptions {
  scope?: HostExportScope;
  selectedIds?: number[];
  columns?: HostExportColumnKey[];
}

export interface EncryptedHostBackup {
  version: 2;
  encrypted: true;
  algorithm: 'AES-GCM';
  kdf: 'PBKDF2-SHA-256';
  keyMode?: 'app-managed';
  iterations: number;
  salt: string;
  iv: string;
  data: string;
  createdAt: string;
}

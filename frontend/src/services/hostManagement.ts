import { apiDelete, apiGet, apiPost, apiPut } from '../api';
import type { HostCredential, HostGroup, ManagedHost } from '../types';

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
}

export interface HostGroupMutationResponse {
  group?: HostGroup;
  groups: HostGroup[];
}

export type HostMutationPayload = Record<string, unknown>;
export type HostGroupMutationPayload = Record<string, unknown>;
export type HostCredentialMutationPayload = Record<string, unknown>;

const baseUrl = '/api/host-management';

export function listHostGroups() {
  return apiGet<HostGroup[]>(`${baseUrl}/groups/`);
}

export function createHostGroup(payload: HostGroupMutationPayload) {
  return apiPost<HostGroupMutationResponse>(`${baseUrl}/groups/`, payload);
}

export function updateHostGroup(groupId: number, payload: HostGroupMutationPayload) {
  return apiPut<HostGroupMutationResponse>(`${baseUrl}/groups/${groupId}/`, payload);
}

export function deleteHostGroup(groupId: number) {
  return apiDelete<{ groups: HostGroup[] }>(`${baseUrl}/groups/${groupId}/`);
}

export function listManagedHosts() {
  return apiGet<ManagedHost[]>(`${baseUrl}/hosts/`);
}

export function createManagedHost(payload: HostMutationPayload) {
  return apiPost<ManagedHost>(`${baseUrl}/hosts/`, payload);
}

export function updateManagedHost(hostId: number, payload: HostMutationPayload) {
  return apiPut<ManagedHost>(`${baseUrl}/hosts/${hostId}/`, payload);
}

export function deleteManagedHost(hostId: number) {
  return apiDelete<{ deleted: boolean }>(`${baseUrl}/hosts/${hostId}/`);
}

export function verifyManagedHost(hostId: number) {
  return apiPost<HostVerifyResponse>(`${baseUrl}/hosts/${hostId}/verify/`, {});
}

export function listHostCredentials() {
  return apiGet<HostCredential[]>(`${baseUrl}/accounts/`);
}

export function createHostCredential(payload: HostCredentialMutationPayload) {
  return apiPost<HostCredential>(`${baseUrl}/accounts/`, payload);
}

export function updateHostCredential(credentialId: number, payload: HostCredentialMutationPayload) {
  return apiPut<HostCredential>(`${baseUrl}/accounts/${credentialId}/`, payload);
}

export function deleteHostCredential(credentialId: number) {
  return apiDelete<{ deleted: boolean }>(`${baseUrl}/accounts/${credentialId}/`);
}

export function exportHostManagementBackup() {
  return apiGet<HostManagementExport>(`${baseUrl}/export/`);
}

export function importHostManagementBackup(payload: HostManagementExport) {
  return apiPost<HostManagementImportResponse>(`${baseUrl}/import/`, payload);
}

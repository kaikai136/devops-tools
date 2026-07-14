import { apiDelete, apiGet, apiPost, apiPut } from '../../../api';
import type {
  TerminalDownloadProtocol,
  TerminalFileListResponse,
  TerminalFileProperties,
  TerminalGroup,
  TerminalMonitorResponse,
  TerminalQuickCommand,
} from '../types';

const terminalBaseUrl = '/api/web-terminal';

export function listTerminalTree() {
  return apiGet<TerminalGroup[]>(`${terminalBaseUrl}/tree/`);
}

export function listTerminalQuickCommands() {
  return apiGet<TerminalQuickCommand[]>(`${terminalBaseUrl}/quick-commands/`);
}

export function createTerminalQuickCommand(payload: unknown) {
  return apiPost<TerminalQuickCommand>(`${terminalBaseUrl}/quick-commands/`, payload);
}

export function updateTerminalQuickCommand(commandId: number, payload: unknown) {
  return apiPut<TerminalQuickCommand>(`${terminalBaseUrl}/quick-commands/${commandId}/`, payload);
}

export function removeTerminalQuickCommand(commandId: number) {
  return apiDelete<{ deleted: boolean }>(`${terminalBaseUrl}/quick-commands/${commandId}/`);
}

export function reorderTerminalQuickCommands(ids: number[]) {
  return apiPost<TerminalQuickCommand[]>(`${terminalBaseUrl}/quick-commands/reorder/`, { ids });
}

export function listTerminalFiles(hostId: number, payload: unknown, options: RequestInit = {}) {
  return apiPost<TerminalFileListResponse>(`${terminalBaseUrl}/hosts/${hostId}/files/list/`, payload, options);
}

export function listTerminalDownloadFiles(hostId: number, payload: unknown, options: RequestInit = {}) {
  return apiPost<TerminalFileListResponse>(`${terminalBaseUrl}/hosts/${hostId}/files/list-download/`, payload, options);
}

export function uploadTerminalFile(hostId: number, payload: unknown, options: RequestInit = {}) {
  return apiPost<{ protocol: string }>(`${terminalBaseUrl}/hosts/${hostId}/files/upload/`, payload, options);
}

export function createTerminalFileEntry(hostId: number, endpoint: string, payload: unknown) {
  return apiPost<TerminalFileProperties>(`${terminalBaseUrl}/hosts/${hostId}/files/${endpoint}/`, payload);
}

export function deleteTerminalFileEntry(hostId: number, payload: unknown) {
  return apiPost<{ deleted: boolean }>(`${terminalBaseUrl}/hosts/${hostId}/files/delete/`, payload);
}

export function renameTerminalFileEntry(hostId: number, payload: unknown) {
  return apiPost<TerminalFileProperties>(`${terminalBaseUrl}/hosts/${hostId}/files/rename/`, payload);
}

export function getTerminalFileProperties(hostId: number, path: string) {
  return apiPost<TerminalFileProperties>(`${terminalBaseUrl}/hosts/${hostId}/files/properties/`, { path });
}

export function updateTerminalFileProperties(hostId: number, payload: unknown) {
  return apiPost<TerminalFileProperties>(`${terminalBaseUrl}/hosts/${hostId}/files/properties/update/`, payload);
}

export function getTerminalMonitor(hostId: number) {
  return apiPost<TerminalMonitorResponse>(`${terminalBaseUrl}/hosts/${hostId}/monitor/`, {});
}

export function buildTerminalFileDownloadRawUrl(hostId: number, path: string, protocol: TerminalDownloadProtocol) {
  const params = new URLSearchParams({ path, protocol });
  return `${terminalBaseUrl}/hosts/${hostId}/files/download/raw/?${params.toString()}`;
}

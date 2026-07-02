import { apiDelete, apiGet, apiPost, apiPut } from '../api';

export interface QuickCommand {
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

export interface QuickCommandPayload {
  name: string;
  category: string;
  command: string;
  description: string;
  enabled: boolean;
  sortOrder: number;
}

const baseUrl = '/api/web-terminal/quick-commands';

export function listQuickCommands() {
  return apiGet<QuickCommand[]>(`${baseUrl}/`);
}

export function createQuickCommand(payload: QuickCommandPayload) {
  return apiPost<QuickCommand>(`${baseUrl}/`, payload);
}

export function updateQuickCommand(commandId: number, payload: QuickCommandPayload) {
  return apiPut<QuickCommand>(`${baseUrl}/${commandId}/`, payload);
}

export function deleteQuickCommand(commandId: number) {
  return apiDelete<{ deleted: boolean }>(`${baseUrl}/${commandId}/`);
}

export function reorderQuickCommands(commandIds: number[]) {
  return apiPost<QuickCommand[]>(`${baseUrl}/reorder/`, { ids: commandIds });
}

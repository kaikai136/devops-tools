import { apiDelete, apiGet, apiPost } from '../api';
import type { SecurityScanCreatePayload, SecurityScanFindingPage, SecurityScanHostTarget, SecurityScanTask, SecurityScanTaskDetail } from '../types';

const baseUrl = '/api/security-scans';

export function listSecurityScanHosts() {
  return apiGet<SecurityScanHostTarget[]>(`${baseUrl}/hosts/`);
}

export function listSecurityScanTasks(params: { status?: string; keyword?: string } = {}) {
  const query = new URLSearchParams();
  if (params.status) query.set('status', params.status);
  if (params.keyword) query.set('keyword', params.keyword);
  const suffix = query.toString() ? `?${query}` : '';
  return apiGet<SecurityScanTask[]>(`${baseUrl}/tasks/${suffix}`);
}

export function createSecurityScanTask(payload: SecurityScanCreatePayload) {
  return apiPost<SecurityScanTask>(`${baseUrl}/tasks/`, payload);
}

export function getSecurityScanTask(taskId: number) {
  return apiGet<SecurityScanTaskDetail>(`${baseUrl}/tasks/${taskId}/`);
}

export function listSecurityScanFindings(taskId: number, params: { page?: number; pageSize?: number } = {}) {
  const query = new URLSearchParams();
  if (params.page) query.set('page', String(params.page));
  if (params.pageSize) query.set('pageSize', String(params.pageSize));
  const suffix = query.toString() ? `?${query}` : '';
  return apiGet<SecurityScanFindingPage>(`${baseUrl}/tasks/${taskId}/findings/${suffix}`);
}

export function deleteSecurityScanTask(taskId: number) {
  return apiDelete<{ deleted: boolean }>(`${baseUrl}/tasks/${taskId}/`);
}

export async function exportSecurityScanTask(taskId: number, format: 'csv' | 'json') {
  const response = await fetch(`${baseUrl}/tasks/${taskId}/export/?format=${format}`, { credentials: 'include' });
  if (!response.ok) {
    throw new Error(await response.text() || '导出安全扫描报告失败');
  }
  return response.blob();
}

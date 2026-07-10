import { apiDelete, apiGet, apiPost } from '../api';
import type {
  SecurityScanCreatePayload,
  SecurityScanFindingPage,
  SecurityScanSummary,
  SecurityScanTarget,
  SecurityScanTask,
  SecurityScanTaskDetail,
} from '../types';

const baseUrl = '/api/security-scans';

export function listSecurityScanTargets() {
  return apiGet<SecurityScanTarget[]>(`${baseUrl}/targets/`);
}

export function getSecurityScanSummary() {
  return apiGet<SecurityScanSummary>(`${baseUrl}/summary/`);
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

export function cancelSecurityScanTask(taskId: number) {
  return apiPost<{ cancelRequested: boolean; status: SecurityScanTask['status'] }>(`${baseUrl}/tasks/${taskId}/cancel/`, {});
}

export function retryFailedSecurityScanTargets(taskId: number) {
  return apiPost<{ retryTargetIds: number[]; task: SecurityScanTask }>(`${baseUrl}/tasks/${taskId}/retry-failed/`, {});
}

export function listSecurityScanFindings(
  taskId: number,
  params: { page?: number; pageSize?: number; severity?: string; category?: string; hostId?: number | string; keyword?: string } = {},
) {
  const query = new URLSearchParams();
  if (params.page) query.set('page', String(params.page));
  if (params.pageSize) query.set('pageSize', String(params.pageSize));
  if (params.severity) query.set('severity', params.severity);
  if (params.category) query.set('category', params.category);
  if (params.hostId) query.set('hostId', String(params.hostId));
  if (params.keyword) query.set('keyword', params.keyword);
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

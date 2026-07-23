import { apiDelete, apiGet, apiPost } from '../../../api';
import type {
  BulkExecutionCreatePayload,
  BulkExecutionTarget,
  BulkExecutionTask,
  BulkExecutionTaskDetail,
  BulkExecutionTaskPage,
} from '../types';

const baseUrl = '/api/bulk-execution';

export function listBulkExecutionTargets() {
  return apiGet<BulkExecutionTarget[]>(`${baseUrl}/targets/`);
}

export function listBulkExecutionTasks(params: { status?: string; keyword?: string; host?: number | string; page?: number; pageSize?: number } = {}) {
  const query = new URLSearchParams();
  if (params.status) query.set('status', params.status);
  if (params.keyword) query.set('keyword', params.keyword);
  if (params.host) query.set('host', String(params.host));
  if (params.page) query.set('page', String(params.page));
  if (params.pageSize) query.set('pageSize', String(params.pageSize));
  const suffix = query.toString() ? `?${query}` : '';
  return apiGet<BulkExecutionTaskPage>(`${baseUrl}/tasks/${suffix}`);
}

export function createBulkExecutionTask(payload: BulkExecutionCreatePayload) {
  return apiPost<BulkExecutionTask>(`${baseUrl}/tasks/`, payload);
}

export function getBulkExecutionTask(taskId: number) {
  return apiGet<BulkExecutionTaskDetail>(`${baseUrl}/tasks/${taskId}/`);
}

export function cancelBulkExecutionTask(taskId: number) {
  return apiPost<{ cancelRequested: boolean; status: BulkExecutionTask['status'] }>(`${baseUrl}/tasks/${taskId}/cancel/`, {});
}

export function deleteBulkExecutionTask(taskId: number) {
  return apiDelete<{ deleted: boolean }>(`${baseUrl}/tasks/${taskId}/`);
}

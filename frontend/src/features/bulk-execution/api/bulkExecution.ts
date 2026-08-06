import { apiDelete, apiGet, apiPost, apiPostForm } from '../../../api';
import type {
  BulkExecutionCreatePayload,
  BulkFileUploadCreatePayload,
  BulkExecutionTarget,
  BulkExecutionTargetTree,
  BulkExecutionTask,
  BulkExecutionTaskDetail,
  BulkExecutionTaskPage,
  BulkUploadCheckPayload,
  BulkUploadCheckResult,
} from '../types';

const baseUrl = '/api/bulk-execution';

export function listBulkExecutionTargets() {
  return apiGet<BulkExecutionTarget[]>(`${baseUrl}/targets/`);
}

export function listBulkExecutionTargetTree() {
  return apiGet<BulkExecutionTargetTree>(`${baseUrl}/target-tree/`);
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

export function createBulkFileUploadTask(payload: BulkFileUploadCreatePayload) {
  const form = new FormData();
  const files = payload.files?.length ? payload.files : payload.file ? [payload.file] : [];
  form.append('executionType', 'file_upload');
  form.append('targetIds', JSON.stringify(payload.targetIds));
  form.append('remoteDirectory', payload.remoteDirectory);
  form.append('overwrite', String(Boolean(payload.overwrite)));
  form.append('name', payload.name);
  for (const file of files) {
    form.append('files', file);
  }
  return apiPostForm<BulkExecutionTask>(`${baseUrl}/tasks/`, form);
}

export function checkBulkFileUpload(payload: BulkUploadCheckPayload) {
  return apiPost<BulkUploadCheckResult>(`${baseUrl}/uploads/check/`, payload);
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

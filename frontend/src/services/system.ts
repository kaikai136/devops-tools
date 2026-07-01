import { ApiResponseError, apiGet, apiPost, apiPut } from '../api';
import type { SystemSetting } from '../types';

export interface SystemSettingPayload {
  key: string;
  label: string;
  description: string;
  value: unknown;
}

const baseUrl = '/api/system';

export function getSystemSetting(key: string) {
  return apiGet<SystemSetting>(`${baseUrl}/settings/${key}/`);
}

export async function getSystemSettingOrNull(key: string) {
  try {
    return await getSystemSetting(key);
  } catch (error) {
    if (error instanceof ApiResponseError && error.status === 404) return null;
    throw error;
  }
}

export function createSystemSetting(payload: SystemSettingPayload) {
  return apiPost<SystemSetting>(`${baseUrl}/settings/`, payload);
}

export function updateSystemSetting(key: string, payload: SystemSettingPayload) {
  return apiPut<SystemSetting>(`${baseUrl}/settings/${key}/`, payload);
}

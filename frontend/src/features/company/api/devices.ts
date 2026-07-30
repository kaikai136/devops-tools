import { apiDelete, apiGet, apiPost, apiPut } from '../../../api';
import type { CompanyDevice, CompanyDevicePayload } from '../types';

const baseUrl = '/api/company-devices';

export function listCompanyDevices() {
  return apiGet<CompanyDevice[]>(`${baseUrl}/`);
}

export function createCompanyDevice(payload: CompanyDevicePayload) {
  return apiPost<CompanyDevice>(`${baseUrl}/`, payload);
}

export function updateCompanyDevice(deviceId: number, payload: CompanyDevicePayload) {
  return apiPut<CompanyDevice>(`${baseUrl}/${deviceId}/`, payload);
}

export function deleteCompanyDevice(deviceId: number) {
  return apiDelete<{ deleted: boolean }>(`${baseUrl}/${deviceId}/`);
}

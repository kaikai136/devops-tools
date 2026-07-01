import { apiDelete, apiGet, apiPost, apiPut } from '../api';
import type { AuthEntry } from '../types';

export type AuthEntryPayload = {
  issuer: string;
  account_name: string;
  secret: string;
  digits: number;
  period: number;
  algorithm: string;
};

export interface AuthenticatorQrCode {
  uri: string;
  data_url: string;
}

const baseUrl = '/api/authenticators';

export function listAuthEntries() {
  return apiGet<AuthEntry[]>(`${baseUrl}/`);
}

export function createAuthEntry(payload: AuthEntryPayload) {
  return apiPost<AuthEntry>(`${baseUrl}/`, payload);
}

export function updateAuthEntry(entryId: number, payload: AuthEntryPayload) {
  return apiPut<AuthEntry>(`${baseUrl}/${entryId}/`, payload);
}

export function deleteAuthEntry(entryId: number) {
  return apiDelete<{ deleted: boolean }>(`${baseUrl}/${entryId}/`);
}

export function getAuthEntryQrCode(entryId: number) {
  return apiGet<AuthenticatorQrCode>(`${baseUrl}/${entryId}/qrcode/`);
}

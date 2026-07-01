import { apiGet, apiPost } from '../api';
import type { AccountUser, LoginPayload, LoginResult } from '../types';

export interface CurrentUserResponse {
  user: AccountUser;
  locked?: boolean;
}

export interface UnlockSessionResponse {
  locked: boolean;
  user: AccountUser;
}

export interface SliderChallenge {
  challengeId: string;
  targetX: number;
  trackWidth: number;
  tolerance: number;
  expiresIn: number;
}

export interface SliderVerifyPayload {
  challengeId: string;
  offsetX: number;
  elapsedMs: number;
}

export interface SliderVerifyResponse {
  verified: boolean;
  sliderToken: string;
}

const baseUrl = '/api/auth';

export function getCurrentUser() {
  return apiGet<CurrentUserResponse>(`${baseUrl}/me/`);
}

export function login(payload: LoginPayload) {
  return apiPost<LoginResult>(`${baseUrl}/login/`, payload);
}

export function verifyTwoFactorLogin(code: string) {
  return apiPost<{ user: AccountUser }>(`${baseUrl}/login/2fa/`, { code });
}

export function verifyTwoFactorSetupLogin(code: string) {
  return apiPost<{ user: AccountUser }>(`${baseUrl}/login/2fa/setup/`, { code });
}

export function lockSession() {
  return apiPost<{ locked: boolean }>(`${baseUrl}/lock/`, {});
}

export function unlockSession(password: string) {
  return apiPost<UnlockSessionResponse>(`${baseUrl}/unlock/`, { password });
}

export function logout() {
  return apiPost<{ ok: boolean }>(`${baseUrl}/logout/`, {});
}

export function getSliderChallenge() {
  return apiGet<SliderChallenge>(`${baseUrl}/slider-challenge/`);
}

export function verifySliderChallenge(payload: SliderVerifyPayload) {
  return apiPost<SliderVerifyResponse>(`${baseUrl}/slider-verify/`, payload);
}

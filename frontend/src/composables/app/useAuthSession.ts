import { computed, ref } from 'vue';

import { apiGet, apiPost } from '../../api';
import type { AccountUser, LoginPayload, LoginResult } from '../../types';

export const AUTH_LOGOUT_EVENT_KEY = 'ops-tool.auth.logout-at';

export function useAuthSession({ loadWorkspaceData, clearSessionUi }: { loadWorkspaceData: () => Promise<void>; clearSessionUi: () => void }) {
  const currentUser = ref<AccountUser | null>(null);
  const isLocked = ref(false);
  const hasWorkspaceDataLoaded = ref(false);
  const isAuthReady = ref(false);
  const isAuthenticated = computed(() => Boolean(currentUser.value));

  async function loadCurrentUser() {
    try {
      const data = await apiGet<{ user: AccountUser; locked?: boolean }>('/api/auth/me/');
      currentUser.value = data.user;
      isLocked.value = Boolean(data.locked);
      if (!isLocked.value) {
        await loadUnlockedWorkspace();
      } else {
        hasWorkspaceDataLoaded.value = false;
      }
    } catch {
      currentUser.value = null;
      isLocked.value = false;
      hasWorkspaceDataLoaded.value = false;
    } finally {
      isAuthReady.value = true;
    }
  }

  async function applyAuthenticatedUser(user: AccountUser) {
    currentUser.value = user;
    isLocked.value = false;
    void loadUnlockedWorkspace();
  }

  async function login(payload: LoginPayload): Promise<LoginResult> {
    const data = await apiPost<LoginResult>('/api/auth/login/', payload);
    if ('user' in data) {
      await applyAuthenticatedUser(data.user);
    }
    return data;
  }

  async function verifyTwoFactorLogin(code: string): Promise<AccountUser> {
    const data = await apiPost<{ user: AccountUser }>('/api/auth/login/2fa/', { code });
    await applyAuthenticatedUser(data.user);
    return data.user;
  }

  async function verifyTwoFactorSetupLogin(code: string): Promise<AccountUser> {
    const data = await apiPost<{ user: AccountUser }>('/api/auth/login/2fa/setup/', { code });
    await applyAuthenticatedUser(data.user);
    return data.user;
  }

  function updateCurrentUser(user: AccountUser) {
    currentUser.value = user;
  }

  async function refreshCurrentUser() {
    const data = await apiGet<{ user: AccountUser; locked?: boolean }>('/api/auth/me/');
    currentUser.value = data.user;
    isLocked.value = Boolean(data.locked);
    return data.user;
  }

  async function lockSession() {
    await apiPost<{ locked: boolean }>('/api/auth/lock/', {});
    isLocked.value = true;
  }

  async function unlockSession(password: string) {
    const data = await apiPost<{ locked: boolean; user: AccountUser }>('/api/auth/unlock/', { password });
    currentUser.value = data.user;
    isLocked.value = Boolean(data.locked);
    await loadUnlockedWorkspace();
    return data.user;
  }

  async function loadUnlockedWorkspace() {
    await loadWorkspaceData();
    hasWorkspaceDataLoaded.value = true;
  }

  async function logout() {
    try {
      await apiPost<{ ok: boolean }>('/api/auth/logout/', {});
    } finally {
      currentUser.value = null;
      isLocked.value = false;
      hasWorkspaceDataLoaded.value = false;
      clearSessionUi();
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(AUTH_LOGOUT_EVENT_KEY, String(Date.now()));
      }
    }
  }

  return {
    currentUser,
    isLocked,
    hasWorkspaceDataLoaded,
    isAuthReady,
    isAuthenticated,
    loadCurrentUser,
    login,
    verifyTwoFactorLogin,
    verifyTwoFactorSetupLogin,
    updateCurrentUser,
    refreshCurrentUser,
    lockSession,
    unlockSession,
    logout,
  };
}

import { computed, ref } from 'vue';

import { apiGet, apiPost } from '../../api';
import type { AccountUser, LoginPayload } from '../../types';

export function useAuthSession({ loadWorkspaceData, clearSessionUi }: { loadWorkspaceData: () => Promise<void>; clearSessionUi: () => void }) {
  const currentUser = ref<AccountUser | null>(null);
  const isAuthReady = ref(false);
  const isAuthenticated = computed(() => Boolean(currentUser.value));

  async function loadCurrentUser() {
    try {
      const data = await apiGet<{ user: AccountUser }>('/api/auth/me/');
      currentUser.value = data.user;
      await loadWorkspaceData();
    } catch {
      currentUser.value = null;
    } finally {
      isAuthReady.value = true;
    }
  }

  async function login(payload: LoginPayload) {
    const data = await apiPost<{ user: AccountUser }>('/api/auth/login/', payload);
    currentUser.value = data.user;
    void loadWorkspaceData();
  }

  async function logout() {
    try {
      await apiPost<{ ok: boolean }>('/api/auth/logout/', {});
    } finally {
      currentUser.value = null;
      clearSessionUi();
    }
  }

  return {
    currentUser,
    isAuthReady,
    isAuthenticated,
    loadCurrentUser,
    login,
    logout,
  };
}

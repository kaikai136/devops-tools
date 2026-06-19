import { inject, type InjectionKey } from 'vue';

import type { AppState } from './composables/useAppState';

export const appContextKey = Symbol('app-context') as InjectionKey<AppState>;

export function useAppContext() {
  const context = inject(appContextKey);
  if (!context) throw new Error('App context is not available.');
  return context;
}

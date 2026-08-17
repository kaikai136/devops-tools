import { apiGet, apiPost, apiPut } from '../../../api';
import type {
  ApplicationMarketAction,
  ApplicationMarketApp,
  ApplicationMarketCatalogResponse,
  ApplicationMarketPage,
  ApplicationMarketPlan,
  ApplicationMarketSource,
  ApplicationMarketTarget,
  ApplicationMarketTask,
} from '../types';

const baseUrl = '/api/application-market';

function toQuery(params: Record<string, string | number | boolean | null | undefined>) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value));
  });
  const text = query.toString();
  return text ? `?${text}` : '';
}

export function listApplicationMarketCatalog(params: { target?: string; keyword?: string; category?: string; source?: string; status?: string } = {}) {
  return apiGet<ApplicationMarketCatalogResponse>(`${baseUrl}/catalog/${toQuery(params)}`);
}

export function getApplicationMarketApp(appId: string) {
  return apiGet<ApplicationMarketApp>(`${baseUrl}/apps/${encodeURIComponent(appId)}/`);
}

export function listApplicationMarketTargets() {
  return apiGet<{ targets: ApplicationMarketTarget[] }>(`${baseUrl}/targets/`);
}

export function listApplicationMarketInstalled(target?: string) {
  return apiGet<{ installed: unknown[] }>(`${baseUrl}/installed/${toQuery({ target })}`);
}

export function previewApplicationMarketAction(payload: {
  appId: string;
  target: string;
  action: ApplicationMarketAction;
  config: Record<string, unknown>;
}) {
  return apiPost<ApplicationMarketPlan>(`${baseUrl}/preview/`, payload);
}

export function createApplicationMarketTask(payload: {
  appId: string;
  target: string;
  action: ApplicationMarketAction;
  config: Record<string, unknown>;
  planDigest: string;
}) {
  return apiPost<ApplicationMarketTask>(`${baseUrl}/tasks/`, payload);
}

export function listApplicationMarketTasks(params: { page?: number; pageSize?: number; status?: string; keyword?: string } = {}) {
  return apiGet<ApplicationMarketPage<ApplicationMarketTask>>(`${baseUrl}/tasks/${toQuery(params)}`);
}

export function getApplicationMarketTask(taskId: number) {
  return apiGet<ApplicationMarketTask>(`${baseUrl}/tasks/${taskId}/`);
}

export function cancelApplicationMarketTask(taskId: number) {
  return apiPost<{ cancelRequested: boolean; status: string }>(`${baseUrl}/tasks/${taskId}/cancel/`, {});
}

export function listApplicationMarketSources() {
  return apiGet<{ sources: ApplicationMarketSource[] }>(`${baseUrl}/sources/`);
}

export function syncApplicationMarketSources() {
  return apiPost<{ results: unknown[] }>(`${baseUrl}/sources/sync/`, {});
}

export function updateApplicationMarketSource(sourceId: number, payload: Partial<Pick<ApplicationMarketSource, 'name' | 'url' | 'enabled'>>) {
  return apiPut<ApplicationMarketSource>(`${baseUrl}/sources/${sourceId}/`, payload);
}

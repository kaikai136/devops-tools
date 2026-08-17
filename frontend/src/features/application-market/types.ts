export type ApplicationMarketAction = 'install' | 'update' | 'uninstall' | 'start' | 'stop' | 'restart';
export type ApplicationMarketTaskStatus = 'queued' | 'running' | 'success' | 'failed' | 'canceled' | 'unknown';

export interface ApplicationMarketConfigField {
  key: string;
  label: string;
  type: 'text' | 'number' | 'password' | 'boolean' | 'select' | string;
  required?: boolean;
  default?: string | number | boolean;
  min?: number;
  max?: number;
  options?: Array<{ label: string; value: string | number | boolean } | string>;
}

export interface ApplicationMarketApp {
  appId: string;
  name: string;
  category: string;
  description: string;
  icon: string;
  version: string;
  source: string;
  installMode: string;
  requirements: Record<string, unknown>;
  configSchema: ApplicationMarketConfigField[];
  manifest: Record<string, unknown>;
  capabilities: ApplicationMarketAction[];
  installed?: boolean;
  status?: string;
}

export interface ApplicationMarketTarget {
  id: string;
  type: 'local' | 'managed_host' | string;
  hostId?: number;
  name: string;
  ip: string;
  os: string;
  supported: boolean;
  docker?: boolean;
  dockerVersion?: string;
  compose?: boolean;
  composeVersion?: string;
  diskFree?: number | null;
  reason?: string;
  containers?: Array<Record<string, unknown>>;
  ports?: string[];
}

export interface ApplicationMarketPlan {
  appId: string;
  appName: string;
  version: string;
  action: ApplicationMarketAction;
  target: string;
  targetType: string;
  targetHostId: number | null;
  config: Record<string, unknown>;
  manifest: Record<string, unknown>;
  command?: string;
  summary: {
    containers?: string[];
    images?: string[];
    ports?: string[];
    directories?: string[];
  };
  warnings: string[];
  planDigest: string;
}

export interface ApplicationMarketTask {
  id: number;
  appId: string;
  appName: string;
  action: ApplicationMarketAction;
  targetKey: string;
  targetType: string;
  targetHost: number | null;
  status: ApplicationMarketTaskStatus;
  cancelRequested: boolean;
  version: string;
  config: Record<string, unknown>;
  planDigest: string;
  logOutput: string;
  error: string;
  createdBy: string;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
}

export interface ApplicationMarketSource {
  id: number;
  name: string;
  sourceType: string;
  url: string;
  enabled: boolean;
  lastSyncedAt: string | null;
  lastError: string;
}

export interface ApplicationMarketCatalogResponse {
  apps: ApplicationMarketApp[];
  categories: string[];
  sources: string[];
}

export interface ApplicationMarketPage<T> {
  results: T[];
  total: number;
  count: number;
  page: number;
  pageSize: number;
  hasNext: boolean;
}

import { apiGet } from '../api';

export type SessionAuditRiskLevel = 'accept' | 'medium' | 'high';

export interface TerminalSessionAudit {
  id: number;
  username: string;
  command: string;
  output: string;
  riskLevel: SessionAuditRiskLevel;
  assetName: string;
  ipAddress: string;
  sessionId: string;
  hostId: number;
  executedAt: string | null;
}

export interface SessionAuditListParams {
  search?: string;
  riskLevel?: SessionAuditRiskLevel | '';
  host?: number | '';
  dateFrom?: string;
  dateTo?: string;
  page?: number;
  pageSize?: number;
}

export interface SessionAuditListResponse {
  count: number;
  page: number;
  pageSize: number;
  results: TerminalSessionAudit[];
}

export function listSessionAudits(params: SessionAuditListParams = {}) {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.set(key, String(value));
    }
  });
  const query = searchParams.toString();
  return apiGet<SessionAuditListResponse>(`/api/web-terminal/session-audits/${query ? `?${query}` : ''}`);
}

export function sessionRecordingUrl(sessionId: string) {
  return `/api/web-terminal/sessions/${encodeURIComponent(sessionId)}/recording.cast`;
}

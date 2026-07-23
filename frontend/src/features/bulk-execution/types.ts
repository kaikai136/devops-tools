export type BulkExecutionStatus = 'queued' | 'running' | 'completed' | 'failed' | 'canceled';
export type BulkExecutionResultStatus = 'pending' | 'running' | 'success' | 'failed' | 'skipped';

export interface BulkExecutionTarget {
  id: number;
  name: string;
  group: number;
  groupName: string;
  privateIp: string;
  publicIp?: string | null;
  port: number;
  loginUser: string;
  os: string;
  systemType: string;
  systemArch: string;
  verified: boolean;
}

export interface BulkExecutionResult {
  id: number;
  host: number | null;
  hostName: string;
  hostIp: string;
  hostPort: number;
  loginUser: string;
  os: string;
  systemType: string;
  systemArch: string;
  status: BulkExecutionResultStatus;
  stdout: string;
  stderr: string;
  exitCode: number | null;
  error: string;
  outputTruncated: boolean;
  startedAt: string | null;
  finishedAt: string | null;
}

export interface BulkExecutionTask {
  id: number;
  name: string;
  command: string;
  status: BulkExecutionStatus;
  cancelRequested: boolean;
  targetCount: number;
  completedCount: number;
  successCount: number;
  failedCount: number;
  skippedCount: number;
  error: string;
  createdBy: string;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
}

export interface BulkExecutionTaskDetail extends BulkExecutionTask {
  results: BulkExecutionResult[];
}

export interface BulkExecutionTaskPage {
  count: number;
  page: number;
  pageSize: number;
  results: BulkExecutionTask[];
}

export interface BulkExecutionCreatePayload {
  targetIds: number[];
  command: string;
  name?: string;
}

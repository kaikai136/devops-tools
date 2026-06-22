export type ToolKey =
  | 'ip'
  | 'hosts'
  | 'accounts'
  | 'ports'
  | 'subnet'
  | 'auth'
  | 'password'
  | 'loginLogs'
  | 'users'
  | 'roles'
  | 'systemSettings';

export interface HostResult {
  host: number;
  ip: string;
  status: 'online' | 'offline' | 'untested';
  response_time: number | null;
}

export interface IpScanResponse {
  results: HostResult[];
  total_hosts: number;
  active_hosts: number;
  duration: number;
  timeout_ms?: number;
  retries?: number;
  concurrency?: number;
}

export interface HostGroup {
  key: number;
  label: string;
  count: number;
  children?: HostGroup[];
}

export interface ManagedHost {
  id: number;
  name: string;
  group: number;
  publicIp?: string;
  privateIp: string;
  port: number;
  loginUser: string;
  loginPassword: string;
  privateKeyName: string;
  privateKey: string;
  machineName: string;
  remark: string;
  cpu: number;
  memory: number;
  os: 'ubuntu' | 'centos' | 'debian';
  verified: boolean;
  verifyStatus?: 'unverified' | 'verified' | 'failed';
}

export interface HostCredential {
  id: number;
  name: string;
  username: string;
  password: string;
  port: number;
  privateKeyName: string;
  privateKey: string;
  remark: string;
}

export interface AccountUser {
  id: number;
  username: string;
  email: string;
  first_name: string;
  is_active: boolean;
  is_staff: boolean;
  is_superuser: boolean;
  last_login: string | null;
  date_joined: string | null;
}

export interface LoginPayload {
  account: string;
  password: string;
  remember: boolean;
}

export interface PortScanResult {
  host: string;
  open_ports: number[];
  open_details?: Array<{ port: number; duration: number; service: string }>;
  scanned_ports: number;
  total_ports?: number;
  timeout_ms?: number;
  concurrency?: number;
  duration: number;
  error?: string;
}

export interface PingDetail {
  sequence: number;
  target: string;
  ip: string;
  status: 'online' | 'timeout';
  response_time: number | null;
  timestamp?: number;
}

export interface PingSession {
  details: PingDetail[];
  metrics: {
    success_count: number;
    failure_count: number;
    loss_rate: number;
    average_response_time: number | null;
    min_response_time: number | null;
    max_response_time: number | null;
    jitter: number | null;
    total_count: number;
  };
}

export interface SubnetResult {
  normalized_input: string;
  ip: string;
  prefix: number;
  mask: string;
  network: string;
  broadcast: string;
  first_host: string;
  last_host: string;
  usable_host_count: number;
  address_count: number;
  is_private?: boolean;
  is_loopback?: boolean;
  is_multicast?: boolean;
  binary: { ip: string; mask: string; network: string; broadcast: string };
  subnets?: Array<{
    index: number;
    cidr: string;
    network: string;
    first_host: string;
    last_host: string;
    gateway: string;
    broadcast: string;
    usable_host_count: number;
  }>;
}

export interface PasswordRecord {
  id: number;
  project_name: string;
  password: string;
  length: number;
  include_uppercase: boolean;
  include_lowercase: boolean;
  include_numbers: boolean;
  include_symbols: boolean;
  created_at: string;
}

export interface PasswordImportRecord {
  project_name: string;
  password: string;
  length: number;
  include_uppercase: boolean;
  include_lowercase: boolean;
  include_numbers: boolean;
  include_symbols: boolean;
}

export interface AuthEntry {
  id: number;
  issuer: string;
  account_name: string;
  secret: string;
  digits: number;
  period: number;
  algorithm: string;
  created_at: string;
  totp?: { code: string; remaining_seconds: number; period: number };
}

export interface QrPreview {
  dataUrl: string;
  uri: string;
  issuer: string;
  account: string;
}

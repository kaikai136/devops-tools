<script setup lang="ts">
import jsQR from 'jsqr';
import { computed, onMounted, onUnmounted, ref } from 'vue';

import { apiDelete, apiGet, apiPost, apiPut } from './api';

type ToolKey = 'ip' | 'ports' | 'ping' | 'subnet' | 'auth' | 'password';

interface HostResult {
  host: number;
  ip: string;
  status: 'online' | 'offline' | 'untested';
  response_time: number | null;
}

interface IpScanResponse {
  results: HostResult[];
  total_hosts: number;
  active_hosts: number;
  duration: number;
}

interface PortScanResult {
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

interface PingDetail {
  sequence: number;
  target: string;
  ip: string;
  status: 'online' | 'timeout';
  response_time: number | null;
  timestamp?: number;
}

interface PingSession {
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

interface SubnetResult {
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

interface PasswordRecord {
  id: number;
  project_name: string;
  password: string;
  length: number;
  created_at: string;
}

interface AuthEntry {
  id: number;
  issuer: string;
  account: string;
  secret: string;
  digits: number;
  period: number;
  algorithm: string;
  totp?: { code: string; remaining: number };
}

const activeTool = ref<ToolKey>('ip');
const groupsOpen = ref({ network: true, security: true });
const toast = ref<{ title: string; message: string; visible: boolean; leaving: boolean; scope: ToolKey } | null>(null);
let toastTimer: number | undefined;
let toastLeaveTimer: number | undefined;

const localIp = ref('198.18.0.1');
const selectedHost = ref('192.168.1.1');

const networkSegment = ref('192.168.1');
const hosts = ref<HostResult[]>(createHostGrid(networkSegment.value));
const ipProgress = ref(0);
const isScanningIp = ref(false);
const ipScanMessage = ref('');

const portHost = ref('192.168.1.1');
const portsInput = ref('80,443,8000,8080,8443,9000');
const portTimeout = ref(600);
const portConcurrency = ref(300);
const portResult = ref<PortScanResult | null>(null);
const portProgress = ref(0);
const portScanMessage = ref('');
const portStartedAt = ref(0);
const isScanningPorts = ref(false);
const portAbort = ref<AbortController | null>(null);
const quickPortsInput = ref('22,80,443');
const quickResults = ref<Array<{ port: number; is_open: boolean; duration: number }>>([]);

const pingHost = ref('192.168.1.1');
const pingCount = ref(4);
const pingTimeout = ref(3000);
const pingInterval = ref(1000);
const pingContinuous = ref(false);
const pingDetails = ref<PingDetail[]>([]);
const isPinging = ref(false);
const pingAbort = ref<AbortController | null>(null);
const pingStartedAt = ref(0);

const subnetInput = ref('192.168.1.0/24');
const subnetPrefix = ref(24);
const subnetTargetPrefix = ref(26);
const subnetMode = ref<'count' | 'hosts'>('count');
const subnetResult = ref<SubnetResult | null>(null);
const subnetPresets = ['192.168.1.0/24', '10.0.0.0/8', '172.16.0.0/16', '192.168.0.0/16', '10.10.10.0/24'];

const passwordProject = ref('');
const passwordLength = ref(16);
const passwordOptions = ref({ include_uppercase: true, include_lowercase: true, include_numbers: true, include_symbols: false });
const passwordHistory = ref<PasswordRecord[]>([]);

const authEntries = ref<AuthEntry[]>([]);
const authForm = ref({ issuer: '', account: '', secret: '', digits: 6, period: 30, algorithm: 'SHA1' });
const authImport = ref('');
const editingAuthId = ref<number | null>(null);
const qrPreview = ref('');
const imageInput = ref<HTMLInputElement | null>(null);

const navGroups = [
  {
    key: 'network' as const,
    label: '网络工具',
    items: [
      { key: 'ip' as const, label: 'IP 探活', desc: '1-254 主机在线探测' },
      { key: 'ports' as const, label: '端口探测', desc: '批量端口扫描与快速测试' },
      { key: 'ping' as const, label: 'Ping 工具', desc: '连通性与延迟检测' },
      { key: 'subnet' as const, label: 'IPv4 子网划分', desc: 'CIDR 计算与子网拆分' },
    ],
  },
  {
    key: 'security' as const,
    label: '安全工具',
    items: [
      { key: 'auth' as const, label: '双因子认证', desc: 'TOTP 动态口令' },
      { key: 'password' as const, label: '密码生成器', desc: '强密码生成与记录' },
    ],
  },
];

const activeNavItem = computed(() => navGroups.flatMap((group) => group.items).find((item) => item.key === activeTool.value) ?? navGroups[0].items[0]);
const onlineHosts = computed(() => hosts.value.filter((host) => host.status === 'online'));
const offlineHosts = computed(() => hosts.value.filter((host) => host.status !== 'online'));
const scopedToastVisible = computed(() => toast.value?.visible && toast.value.scope === activeTool.value);
const pingMetrics = computed(() => calculatePingMetrics(pingDetails.value));
const pingChart = computed(() => buildPingChart(pingDetails.value));
const prefixOptions = computed(() =>
  Array.from({ length: 31 }, (_, index) => index + 1).map((prefix) => ({
    value: prefix,
    label: `/${prefix} (${prefixToMask(prefix)})`,
  })),
);
const splitOptions = computed(() => {
  const start = Math.max(subnetPrefix.value + 1, 1);
  return Array.from({ length: 32 - start + 1 }, (_, index) => start + index).map((prefix) => ({
    value: prefix,
    label: `${2 ** (prefix - subnetPrefix.value)} 个子网`,
  }));
});

function calculatePingMetrics(details: PingDetail[]) {
  const responseTimes = details.filter((item) => item.status === 'online' && item.response_time !== null).map((item) => item.response_time as number);
  const successCount = responseTimes.length;
  const failureCount = details.length - successCount;
  const jitterValues = responseTimes.slice(1).map((value, index) => Math.abs(value - responseTimes[index]));

  return {
    success_count: successCount,
    failure_count: failureCount,
    loss_rate: details.length ? Math.round((failureCount / details.length) * 100) : 0,
    average_response_time: responseTimes.length ? Math.round(responseTimes.reduce((sum, value) => sum + value, 0) / responseTimes.length) : null,
    min_response_time: responseTimes.length ? Math.min(...responseTimes) : null,
    max_response_time: responseTimes.length ? Math.max(...responseTimes) : null,
    jitter: jitterValues.length ? Math.round(jitterValues.reduce((sum, value) => sum + value, 0) / jitterValues.length) : null,
    total_count: details.length,
  };
}

function buildPingChart(details: PingDetail[]) {
  const width = 860;
  const height = 190;
  const padding = { top: 18, right: 12, bottom: 32, left: 46 };
  const visible = details.slice(-60);
  const responseValues = visible.map((item) => item.response_time).filter((value): value is number => value !== null);
  const maxResponse = Math.max(10, ...responseValues, pingMetrics.value.average_response_time ?? 0);
  const maxValue = Math.max(80, Math.ceil(maxResponse / 20) * 20);
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const yTicks = Array.from({ length: 5 }, (_, index) => {
    const value = Math.round((maxValue / 4) * (4 - index));
    const y = padding.top + index * (plotHeight / 4);
    return { value, y };
  });
  const points = visible.map((item, index) => {
    const x = visible.length <= 1 ? padding.left : padding.left + (index / (visible.length - 1)) * plotWidth;
    const value = item.response_time ?? maxValue;
    const y = padding.top + plotHeight - (Math.min(value, maxValue) / maxValue) * plotHeight;
    return { x, y, item };
  });
  const latencyPath = points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(' ');
  const average = pingMetrics.value.average_response_time;
  const averageY = average === null ? null : padding.top + plotHeight - (average / maxValue) * plotHeight;
  return { width, height, padding, plotWidth, plotHeight, points, latencyPath, averageY, yTicks };
}

function showToast(title: string, message: string) {
  window.clearTimeout(toastTimer);
  window.clearTimeout(toastLeaveTimer);
  toast.value = { title, message, visible: true, leaving: false, scope: activeTool.value };
  toastTimer = window.setTimeout(() => {
    if (!toast.value) return;
    toast.value.leaving = true;
    toastLeaveTimer = window.setTimeout(() => {
      toast.value = null;
    }, 600);
  }, 5000);
}

async function copyText(text: string, message = '已复制到剪贴板。') {
  await navigator.clipboard.writeText(text);
  showToast('操作成功', message);
}

function setActiveTool(key: ToolKey) {
  activeTool.value = key;
}

function createHostGrid(segment: string): HostResult[] {
  const normalizedSegment = segment.trim() || '192.168.1';
  return Array.from({ length: 254 }, (_, index) => {
    const host = index + 1;
    return {
      host,
      ip: `${normalizedSegment}.${host}`,
      status: 'untested',
      response_time: null,
    };
  });
}

async function loadLocalIp() {
  try {
    const data = await apiGet<{ ip: string }>('/api/local-ip/');
    localIp.value = data.ip;
  } catch {
    localIp.value = '198.18.0.1';
  }
}

async function scanIp() {
  if (isScanningIp.value) return;
  isScanningIp.value = true;
  ipProgress.value = 6;
  ipScanMessage.value = '';
  const started = performance.now();
  const timer = window.setInterval(() => {
    const elapsed = performance.now() - started;
    const estimatedDuration = 2400;
    const nextProgress = 6 + Math.floor((elapsed / estimatedDuration) * 93);
    ipProgress.value = Math.min(Math.max(ipProgress.value + 1, nextProgress), 99);
  }, 140);
  try {
    const result = await apiPost<HostResult[] | IpScanResponse>('/api/scan/ip/', { network: networkSegment.value });
    const scanResults = Array.isArray(result) ? result : result.results;
    hosts.value = scanResults;
    const firstOnline = scanResults.find((host) => host.status === 'online');
    if (firstOnline) selectedHost.value = firstOnline.ip;
    ipProgress.value = 100;
    ipScanMessage.value = `扫描完成：${onlineHosts.value.length}/254 在线，耗时 ${Math.round(performance.now() - started)} ms`;
  } catch (error) {
    showToast('操作失败', (error as Error).message);
  } finally {
    window.clearInterval(timer);
    isScanningIp.value = false;
  }
}

function selectHost(ip: string) {
  selectedHost.value = ip;
  portHost.value = ip;
  pingHost.value = ip;
}

function openPingFromHost(ip: string) {
  selectHost(ip);
  activeTool.value = 'ping';
}

function applyPortPreset(value: string) {
  const presets: Record<string, string> = {
    common: '21,22,23,25,53,80,110,143,443,445,993,995,3389',
    top100: Array.from({ length: 100 }, (_, index) => index + 1).join(','),
    top1024: '1-1024',
    all: '1-65535',
    database: '1433,1521,3306,5432,6379,27017',
    web: '80,443,8000,8080,8443,9000',
  };
  portsInput.value = presets[value] ?? portsInput.value;
}

function parsePortInput(input: string): number[] {
  const ports = new Set<number>();
  const tokens = input.replace(/，/g, ',').split(/[,\s]+/).map((item) => item.trim()).filter(Boolean);
  for (const token of tokens) {
    if (token.includes('-')) {
      const [startText, endText] = token.split('-', 2);
      const start = Number(startText);
      const end = Number(endText);
      if (!Number.isInteger(start) || !Number.isInteger(end) || start < 1 || end > 65535 || start > end) {
        throw new Error(`端口范围不正确：${token}`);
      }
      for (let port = start; port <= end; port += 1) ports.add(port);
    } else {
      const port = Number(token);
      if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error(`端口不正确：${token}`);
      ports.add(port);
    }
  }
  if (!ports.size) throw new Error('请至少输入一个端口');
  return Array.from(ports).sort((left, right) => left - right);
}

async function scanPorts() {
  if (isScanningPorts.value) return;
  let ports: number[] = [];
  try {
    ports = parsePortInput(portsInput.value);
  } catch (error) {
    showToast('操作失败', (error as Error).message);
    return;
  }

  const totalPorts = ports.length;
  const effectiveTimeout = Math.max(100, Math.min(5000, Number(portTimeout.value) || 600));
  const effectiveConcurrency = Math.max(1, Math.min(512, Number(portConcurrency.value) || 300, totalPorts));
  const batchSize = Math.max(1, Math.min(totalPorts, Math.max(effectiveConcurrency, 200)));

  isScanningPorts.value = true;
  portStartedAt.value = performance.now();
  portProgress.value = 0;
  portScanMessage.value = `准备扫描 ${totalPorts} 个端口`;
  portResult.value = {
    host: portHost.value,
    open_ports: [],
    open_details: [],
    scanned_ports: 0,
    total_ports: totalPorts,
    timeout_ms: effectiveTimeout,
    concurrency: effectiveConcurrency,
    duration: 0,
  };
  const controller = new AbortController();
  portAbort.value = controller;

  try {
    for (let index = 0; index < ports.length; index += batchSize) {
      if (controller.signal.aborted) break;
      const batch = ports.slice(index, index + batchSize);
      portScanMessage.value = `扫描中：${portResult.value.scanned_ports}/${totalPorts} · 本批 ${batch.length} 个端口`;
      const batchResult = await apiPost<PortScanResult>(
        '/api/scan/ports/',
        { host: portHost.value, ports: batch.join(','), timeout_ms: effectiveTimeout, concurrency: effectiveConcurrency },
        { signal: controller.signal },
      );

      portResult.value.host = batchResult.host;
      portResult.value.scanned_ports += batchResult.scanned_ports;
      portResult.value.duration = Math.round(performance.now() - portStartedAt.value);
      portResult.value.open_ports = Array.from(new Set([...portResult.value.open_ports, ...batchResult.open_ports])).sort((left, right) => left - right);
      portResult.value.open_details = [...(portResult.value.open_details ?? []), ...(batchResult.open_details ?? [])].sort((left, right) => left.port - right.port);
      portResult.value.error = batchResult.error;
      portProgress.value = Math.round((portResult.value.scanned_ports / totalPorts) * 100);

      if (batchResult.error) break;
    }

    portProgress.value = 100;
    portResult.value.duration = Math.round(performance.now() - portStartedAt.value);
    portScanMessage.value = portResult.value?.error
      ? `扫描异常：${portResult.value.error}`
      : `扫描完成：${portResult.value.scanned_ports}/${portResult.value.total_ports ?? totalPorts} 个端口，发现 ${portResult.value.open_ports.length} 个开放`;
  } catch (error) {
    if ((error as Error).name !== 'AbortError') {
      portScanMessage.value = '';
      showToast('操作失败', (error as Error).message);
    }
  } finally {
    isScanningPorts.value = false;
    portAbort.value = null;
  }
}

function stopPortScan() {
  portAbort.value?.abort();
  isScanningPorts.value = false;
  portProgress.value = 0;
  portScanMessage.value = '扫描已停止';
}

async function quickTestPorts() {
  const ports = parsePortInput(quickPortsInput.value);
  const result = await apiPost<PortScanResult>('/api/scan/ports/', {
    host: portHost.value,
    ports: ports.join(','),
    timeout_ms: portTimeout.value,
    concurrency: Math.min(portConcurrency.value, ports.length),
  });
  quickResults.value = ports.map((port) => ({
    port,
    is_open: result.open_ports.includes(port),
    duration: result.open_details?.find((item) => item.port === port)?.duration ?? 0,
  }));
  if (result.error) showToast('扫描异常', result.error);
}

function setPingPreset(host: string) {
  pingHost.value = host;
}

function useSelectedIpForPing() {
  pingHost.value = selectedHost.value;
}

async function runPing() {
  if (isPinging.value) return;
  pingDetails.value = [];
  isPinging.value = true;
  pingStartedAt.value = performance.now();
  const controller = new AbortController();
  pingAbort.value = controller;

  try {
    if (pingContinuous.value) {
      let sequence = 1;
      while (!controller.signal.aborted) {
        const session = await apiPost<PingSession>(
          '/api/ping/',
          { host: pingHost.value, count: 1, timeout_ms: pingTimeout.value, interval_ms: pingInterval.value },
          { signal: controller.signal },
        );
        appendPingDetails(session.details, sequence);
        sequence += session.details.length;
        await sleep(Math.max(100, pingInterval.value), controller.signal);
      }
    } else {
      const session = await apiPost<PingSession>(
        '/api/ping/',
        { host: pingHost.value, count: pingCount.value, timeout_ms: pingTimeout.value, interval_ms: pingInterval.value },
        { signal: controller.signal },
      );
      appendPingDetails(session.details, 1);
    }
  } catch (error) {
    if ((error as Error).name !== 'AbortError') showToast('Ping 失败', (error as Error).message);
  } finally {
    isPinging.value = false;
    pingAbort.value = null;
  }
}

function appendPingDetails(details: PingDetail[], startSequence: number) {
  const normalized = details.map((detail, index) => ({
    ...detail,
    sequence: startSequence + index,
    timestamp: detail.timestamp ?? Date.now(),
  }));
  pingDetails.value = [...pingDetails.value, ...normalized];
}

function stopPing() {
  pingAbort.value?.abort();
  isPinging.value = false;
}

function clearPingResults() {
  pingDetails.value = [];
}

function exportPingResults() {
  if (!pingDetails.value.length) {
    showToast('导出失败', '还没有可导出的 Ping 结果。');
    return;
  }
  const rows = [
    ['序号', '目标', '解析 IP', '状态', '延迟(ms)', '时间'],
    ...pingDetails.value.map((item) => [
      String(item.sequence),
      item.target,
      item.ip,
      item.status === 'online' ? '成功' : '超时',
      item.response_time === null ? '' : String(item.response_time),
      new Date(item.timestamp ?? Date.now()).toLocaleString(),
    ]),
  ];
  const csv = rows.map((row) => row.map((cell) => `"${cell.replace(/"/g, '""')}"`).join(',')).join('\n');
  const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `ping-${pingHost.value}-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function sleep(ms: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException('Aborted', 'AbortError'));
      return;
    }
    const timer = window.setTimeout(resolve, ms);
    signal.addEventListener(
      'abort',
      () => {
        window.clearTimeout(timer);
        reject(new DOMException('Aborted', 'AbortError'));
      },
      { once: true },
    );
  });
}

function normalizedSubnetInput() {
  const base = subnetInput.value.trim().split('/')[0] || '192.168.1.0';
  return `${base}/${subnetPrefix.value}`;
}

async function calculateSubnet(withSplit = false) {
  subnetInput.value = normalizedSubnetInput();
  subnetResult.value = await apiPost<SubnetResult>('/api/subnet/calculate/', {
    input: subnetInput.value,
    prefix: subnetPrefix.value,
    ...(withSplit ? { target_prefix: subnetTargetPrefix.value } : {}),
  });
  if (withSplit) showToast('操作成功', 'IPv4 子网划分已完成。');
}

async function handlePrefixChange() {
  subnetInput.value = normalizedSubnetInput();
  if (subnetTargetPrefix.value <= subnetPrefix.value) subnetTargetPrefix.value = Math.min(subnetPrefix.value + 1, 32);
  await calculateSubnet(false);
}

function setSubnetPreset(value: string) {
  subnetInput.value = value;
  const [, prefix] = value.split('/');
  subnetPrefix.value = Number(prefix || 24);
  subnetTargetPrefix.value = Math.min(subnetPrefix.value + 2, 32);
  calculateSubnet(false);
}

function clearSubnet() {
  subnetInput.value = '192.168.1.0/24';
  subnetPrefix.value = 24;
  subnetTargetPrefix.value = 26;
  subnetResult.value = null;
}

async function generatePassword() {
  const record = await apiPost<PasswordRecord>('/api/passwords/generate/', {
    project_name: passwordProject.value || '未命名项目',
    length: passwordLength.value,
    ...passwordOptions.value,
  });
  passwordHistory.value = [record, ...passwordHistory.value].slice(0, 20);
  passwordProject.value = '';
  await copyText(record.password, `已复制 ${record.project_name} 的密码。`);
}

async function loadPasswords() {
  passwordHistory.value = await apiGet<PasswordRecord[]>('/api/passwords/history/');
}

async function deletePassword(record: PasswordRecord) {
  await apiDelete(`/api/passwords/history/${record.id}/`);
  passwordHistory.value = passwordHistory.value.filter((item) => item.id !== record.id);
}

async function loadAuthEntries() {
  authEntries.value = await apiGet<AuthEntry[]>('/api/authenticators/');
}

async function saveAuthEntry() {
  if (editingAuthId.value) {
    await apiPut<AuthEntry>(`/api/authenticators/${editingAuthId.value}/`, authForm.value);
  } else {
    await apiPost<AuthEntry>('/api/authenticators/', authForm.value);
  }
  resetAuthForm();
  await loadAuthEntries();
  showToast('操作成功', '动态口令条目已保存。');
}

function editAuth(entry: AuthEntry) {
  editingAuthId.value = entry.id;
  authForm.value = {
    issuer: entry.issuer,
    account: entry.account,
    secret: entry.secret,
    digits: entry.digits,
    period: entry.period,
    algorithm: entry.algorithm,
  };
}

async function deleteAuth(entry: AuthEntry) {
  await apiDelete(`/api/authenticators/${entry.id}/`);
  authEntries.value = authEntries.value.filter((item) => item.id !== entry.id);
}

async function clearAuthEntries() {
  await Promise.all(authEntries.value.map((entry) => apiDelete(`/api/authenticators/${entry.id}/`)));
  authEntries.value = [];
  showToast('操作成功', '验证码列表已清空。');
}

async function copyAuthCode(entry: AuthEntry) {
  if (!entry.totp?.code) return;
  await copyText(entry.totp.code, `已复制 ${entry.issuer || entry.account} 的当前验证码。`);
}

async function showQr(entry: AuthEntry) {
  const result = await apiGet<{ uri: string; data_url: string }>(`/api/authenticators/${entry.id}/qrcode/`);
  qrPreview.value = result.data_url;
}

function resetAuthForm() {
  editingAuthId.value = null;
  authImport.value = '';
  authForm.value = { issuer: '', account: '', secret: '', digits: 6, period: 30, algorithm: 'SHA1' };
}

function parseAuthImport() {
  const uri = authImport.value.trim();
  if (!uri.startsWith('otpauth://')) {
    showToast('解析失败', '请输入有效的 otpauth:// 链接。');
    return;
  }
  const url = new URL(uri);
  const label = decodeURIComponent(url.pathname.replace(/^\//, ''));
  const [issuerFromLabel, accountFromLabel] = label.includes(':') ? label.split(':') : ['', label];
  authForm.value = {
    issuer: url.searchParams.get('issuer') || issuerFromLabel || authForm.value.issuer,
    account: accountFromLabel || authForm.value.account,
    secret: url.searchParams.get('secret') || authForm.value.secret,
    digits: Number(url.searchParams.get('digits') || 6),
    period: Number(url.searchParams.get('period') || 30),
    algorithm: (url.searchParams.get('algorithm') || 'SHA1').toUpperCase(),
  };
  showToast('操作成功', '链接已解析到表单。');
}

function triggerImageImport() {
  imageInput.value?.click();
}

async function handleImageImport(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0];
  if (!file) return;
  const bitmap = await createImageBitmap(file);
  const canvas = document.createElement('canvas');
  canvas.width = bitmap.width;
  canvas.height = bitmap.height;
  const context = canvas.getContext('2d');
  if (!context) return;
  context.drawImage(bitmap, 0, 0);
  const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
  const qr = jsQR(imageData.data, imageData.width, imageData.height);
  if (!qr?.data) {
    showToast('识别失败', '图片中没有识别到二维码。');
    return;
  }
  authImport.value = qr.data;
  parseAuthImport();
  (event.target as HTMLInputElement).value = '';
}

function prefixToMask(prefix: number) {
  const mask = prefix === 0 ? 0 : (0xffffffff << (32 - prefix)) >>> 0;
  return [24, 16, 8, 0].map((shift) => (mask >>> shift) & 255).join('.');
}

function setupClickWords() {
  const words = ['❤😀❤', '❤😂❤', 'C++', 'Python', '❤😘❤', '❤🤠❤', 'PHP', 'Java', 'HTML', 'CSS', 'JavaScript', 'MySQL', 'Linux'];
  let index = 0;
  const handler = (event: MouseEvent) => {
    const span = document.createElement('span');
    span.className = 'click-word';
    span.textContent = words[index];
    index = (index + 1) % words.length;
    span.style.left = `${event.pageX}px`;
    span.style.top = `${event.pageY - 20}px`;
    span.style.color = `rgb(${Math.random() * 220},${Math.random() * 180},${120 + Math.random() * 120})`;
    document.body.appendChild(span);
    window.setTimeout(() => span.remove(), 1500);
  };
  document.body.addEventListener('click', handler);
  return () => document.body.removeEventListener('click', handler);
}

function setupPointerTrail() {
  let last = 0;
  const handler = (event: PointerEvent) => {
    if (!(event.buttons & 1) || performance.now() - last < 28) return;
    last = performance.now();
    const dot = document.createElement('span');
    dot.className = 'pointer-trail';
    dot.style.left = `${event.pageX}px`;
    dot.style.top = `${event.pageY}px`;
    dot.style.setProperty('--hue', `${Math.round(Math.random() * 280 + 180)}deg`);
    document.body.appendChild(dot);
    window.setTimeout(() => dot.remove(), 900);
  };
  window.addEventListener('pointermove', handler);
  return () => window.removeEventListener('pointermove', handler);
}

let cleanupClickWords: (() => void) | undefined;
let cleanupPointerTrail: (() => void) | undefined;
let authTimer: number | undefined;

onMounted(async () => {
  document.title = '运维船长';
  cleanupClickWords = setupClickWords();
  cleanupPointerTrail = setupPointerTrail();
  await Promise.allSettled([loadLocalIp(), loadAuthEntries(), loadPasswords(), calculateSubnet(false)]);
  authTimer = window.setInterval(() => {
    if (activeTool.value === 'auth') loadAuthEntries();
  }, 1000);
});

onUnmounted(() => {
  cleanupClickWords?.();
  cleanupPointerTrail?.();
  window.clearInterval(authTimer);
  window.clearTimeout(toastTimer);
  window.clearTimeout(toastLeaveTimer);
});
</script>

<template>
  <main class="app-shell">
    <aside class="sidebar">
      <div class="sidebar-brand">
        <img src="/captain-banner.png" alt="运维船长" />
      </div>

      <nav class="sidebar-nav">
        <section v-for="group in navGroups" :key="group.key" class="nav-group">
          <button class="nav-group-button" type="button" @click="groupsOpen[group.key] = !groupsOpen[group.key]">
            <span class="nav-icon">{{ group.key === 'network' ? 'Ⅱ' : '⚙' }}</span>
            <span>{{ group.label }}</span>
            <span class="nav-caret">{{ groupsOpen[group.key] ? '⌃' : '⌄' }}</span>
          </button>
          <div v-show="groupsOpen[group.key]" class="nav-items">
            <button
              v-for="item in group.items"
              :key="item.key"
              class="nav-item"
              :class="{ active: activeTool === item.key }"
              type="button"
              @click="setActiveTool(item.key)"
            >
              <span class="nav-dot">{{ item.key === 'auth' ? '⊙' : item.key === 'password' ? '✦' : item.key === 'ports' ? '▣' : item.key === 'ping' ? '∞' : item.key === 'subnet' ? '╫' : '⌂' }}</span>
              <span>{{ item.label }}</span>
            </button>
          </div>
        </section>
      </nav>
    </aside>

    <section class="workspace">
      <div v-if="scopedToastVisible" class="top-toast" :class="{ leaving: toast?.leaving }">
        <div>
          <strong>{{ toast?.title }}</strong>
          <p>{{ toast?.message }}</p>
        </div>
        <button type="button" @click="toast = null">×</button>
      </div>

      <header class="page-header">
        <div>
          <h1>{{ activeNavItem.label }}</h1>
          <p>
            {{ activeNavItem.desc }}
            <span v-if="activeTool === 'ip' && ipScanMessage" class="inline-status">{{ ipScanMessage }}</span>
          </p>
        </div>
        <div class="header-stats">
          <article><span>本机 IP</span><strong>{{ localIp }}</strong></article>
          <article><span>选中 IP</span><strong>{{ selectedHost }}</strong></article>
        </div>
      </header>

      <section v-if="activeTool === 'ip'" class="tool-stack ip-page">
        <article class="panel ip-toolbar">
          <label class="segment-field"><span>网段</span><input v-model="networkSegment" @keyup.enter="scanIp" /></label>
          <button class="primary" type="button" :disabled="isScanningIp" @click="scanIp">{{ isScanningIp ? '扫描中' : '扫描 IP' }}</button>
          <div class="selected-chip">选中 IP <strong>{{ selectedHost }}</strong></div>
        </article>
        <article class="panel progress-panel">
          <div><span>扫描进度</span><strong>{{ ipProgress }}%</strong></div>
          <div class="progress"><span :style="{ width: `${ipProgress}%` }"></span></div>
        </article>
        <div class="metric-row">
          <article><strong>{{ hosts.length }}/254</strong><span>已扫描</span></article>
          <article><strong class="green">{{ onlineHosts.length }}</strong><span>在线主机</span></article>
          <article><strong class="muted">{{ offlineHosts.length }}</strong><span>离线主机</span></article>
          <article><strong>{{ selectedHost }}</strong><span>当前选中</span></article>
        </div>
        <article class="ip-grid-panel">
          <button
            v-for="host in hosts"
            :key="host.ip"
            class="ip-cell"
            :class="{ online: host.status === 'online', selected: selectedHost === host.ip }"
            :title="host.ip"
            type="button"
            @click="selectHost(host.ip)"
            @dblclick="openPingFromHost(host.ip)"
          >
            {{ host.host }}
          </button>
        </article>
      </section>

      <section v-if="activeTool === 'ports'" class="tool-grid">
        <article class="panel ports-config">
          <h2>端口探测</h2>
          <label><span>目标</span><input v-model="portHost" @keyup.enter="scanPorts" /></label>
          <label><span>端口</span><input v-model="portsInput" @keyup.enter="scanPorts" /></label>
          <div class="preset-row">
            <button type="button" @click="applyPortPreset('common')">常用端口</button>
            <button type="button" @click="applyPortPreset('top100')">1-100</button>
            <button type="button" @click="applyPortPreset('top1024')">1-1024</button>
            <button type="button" @click="applyPortPreset('all')">全端口</button>
            <button type="button" @click="applyPortPreset('database')">数据库</button>
            <button type="button" @click="applyPortPreset('web')">Web 服务</button>
          </div>
          <label><span>超时</span><input v-model.number="portTimeout" type="number" @keyup.enter="scanPorts" /></label>
          <label><span>并发</span><input v-model.number="portConcurrency" type="number" @keyup.enter="scanPorts" /></label>
          <div class="split-actions">
            <button class="primary" type="button" :disabled="isScanningPorts" @click="scanPorts">开始扫描</button>
            <button type="button" :disabled="!isScanningPorts" @click="stopPortScan">停止</button>
          </div>
        </article>
        <article class="panel">
          <h2>扫描结果</h2>
          <div class="progress"><span :style="{ width: `${portProgress}%` }"></span></div>
          <p v-if="portScanMessage" class="inline-status">{{ portScanMessage }}</p>
          <div v-if="portResult" class="port-summary">
            <article><span>目标</span><strong>{{ portResult.host }}</strong></article>
            <article><span>进度</span><strong>{{ portResult.scanned_ports }}/{{ portResult.total_ports ?? portResult.scanned_ports }}</strong></article>
            <article><span>开放</span><strong class="green">{{ portResult.open_ports.length }}</strong></article>
            <article><span>耗时</span><strong>{{ portResult.duration }} ms</strong></article>
          </div>
          <p v-if="portResult?.error" class="result-warning">{{ portResult.error }}</p>
          <div v-if="portResult && !portResult.error" class="port-open-list">
            <button
              v-for="item in portResult.open_details"
              :key="item.port"
              class="port-open-item"
              type="button"
              @click="copyText(String(item.port), `已复制端口 ${item.port}。`)"
            >
              <strong>{{ item.port }}</strong>
              <span>{{ item.service }}</span>
              <small>{{ item.duration }} ms</small>
            </button>
            <p v-if="!portResult.open_ports.length && !isScanningPorts" class="empty-state">没有发现开放端口</p>
          </div>
          <div class="quick-box">
            <h3>快速测试</h3>
            <label><span>端口</span><input v-model="quickPortsInput" @keyup.enter="quickTestPorts" /></label>
            <button type="button" @click="quickTestPorts">测试端口</button>
            <div class="quick-results">
              <button
                v-for="item in quickResults"
                :key="item.port"
                class="quick-pill"
                :class="{ open: item.is_open }"
                type="button"
                @click="copyText(String(item.port), `已复制端口 ${item.port}。`)"
              >
                {{ item.port }} {{ item.is_open ? '开放' : '关闭' }} · {{ item.duration }} ms
              </button>
            </div>
          </div>
        </article>
      </section>

      <section v-if="activeTool === 'ping'" class="tool-stack ping-page">
        <article class="panel ping-config">
          <h2>测试配置</h2>
          <div class="ping-presets">
            <button type="button" @click="setPingPreset('223.5.5.5')">阿里DNS</button>
            <button type="button" @click="setPingPreset('119.29.29.29')">腾讯DNS</button>
            <button type="button" @click="setPingPreset('114.114.114.114')">114DNS</button>
            <button type="button" @click="setPingPreset('8.8.8.8')">Google DNS</button>
            <button type="button" @click="setPingPreset('baidu.com')">百度</button>
          </div>
          <div class="ping-form-grid">
            <label><span>目标主机</span><input v-model="pingHost" @keyup.enter="runPing" /></label>
            <label><span>次数</span><input v-model.number="pingCount" min="1" max="200" type="number" @keyup.enter="runPing" /></label>
            <label><span>超时 (ms)</span><input v-model.number="pingTimeout" min="300" max="30000" step="100" type="number" @keyup.enter="runPing" /></label>
            <label><span>间隔 (ms)</span><input v-model.number="pingInterval" min="100" max="10000" step="100" type="number" @keyup.enter="runPing" /></label>
          </div>
          <label class="check-line ping-check"><input v-model="pingContinuous" type="checkbox" />连续 Ping（直到手动停止）</label>
          <div class="ping-actions">
            <button class="primary" type="button" :disabled="isPinging" @click="runPing">{{ isPinging ? 'Ping 中' : '开始 Ping' }}</button>
            <button type="button" :disabled="!isPinging" @click="stopPing">停止</button>
            <button type="button" :disabled="!pingDetails.length" @click="exportPingResults">导出</button>
          </div>
          <button class="link-button" type="button" @click="useSelectedIpForPing">使用选中 IP</button>
        </article>

        <article class="panel ping-results">
          <div class="panel-title">
            <h2>测试结果</h2>
          </div>
          <section class="ping-detail-box">
            <div class="ping-section-title">
              <h3>详细结果</h3>
              <button type="button" :disabled="!pingDetails.length || isPinging" @click="clearPingResults">清空</button>
            </div>
            <div class="ping-detail-list">
              <div v-if="!pingDetails.length" class="ping-empty">还没有测试结果。</div>
              <div
                v-for="row in pingDetails"
                :key="row.sequence"
                class="ping-row"
                :class="{ timeout: row.status === 'timeout' }"
              >
                <span>#{{ row.sequence }}</span>
                <strong>{{ row.ip }}</strong>
                <span>{{ row.status === 'online' ? '成功' : '超时' }}</span>
                <span>{{ row.response_time ?? '--' }} ms</span>
              </div>
            </div>
          </section>
          <div class="ping-metrics">
            <article><strong class="green">{{ pingMetrics.success_count }}</strong><span>成功</span></article>
            <article><strong class="danger-text">{{ pingMetrics.failure_count }}</strong><span>失败</span></article>
            <article><strong class="orange">{{ pingMetrics.loss_rate }}%</strong><span>丢包率</span></article>
            <article><strong>{{ pingMetrics.average_response_time ?? '--' }}</strong><span>平均 (ms)</span></article>
            <article><strong class="green">{{ pingMetrics.min_response_time ?? '--' }}</strong><span>最小 (ms)</span></article>
            <article><strong class="danger-text">{{ pingMetrics.max_response_time ?? '--' }}</strong><span>最大 (ms)</span></article>
            <article><strong class="purple-text">{{ pingMetrics.jitter ?? '--' }}</strong><span>抖动 (ms)</span></article>
            <article><strong>{{ pingMetrics.total_count }}</strong><span>总计</span></article>
          </div>
          <section class="ping-chart-panel">
            <div class="ping-section-title">
              <h3>延迟波形图</h3>
              <div class="ping-legend">
                <span><i class="latency-dot"></i>延迟</span>
                <span><i class="average-dot"></i>平均</span>
                <span><i class="timeout-dot"></i>超时</span>
              </div>
            </div>
            <div class="ping-chart">
              <svg v-if="pingDetails.length" :viewBox="`0 0 ${pingChart.width} ${pingChart.height}`" role="img" aria-label="Ping 延迟波形图">
                <g class="chart-grid">
                  <g v-for="tick in pingChart.yTicks" :key="tick.value">
                    <text :x="pingChart.padding.left - 10" :y="tick.y + 4" text-anchor="end">{{ tick.value }}</text>
                    <line :x1="pingChart.padding.left" :x2="pingChart.width - pingChart.padding.right" :y1="tick.y" :y2="tick.y" />
                  </g>
                </g>
                <line
                  v-if="pingChart.averageY !== null"
                  :x1="pingChart.padding.left"
                  :x2="pingChart.width - pingChart.padding.right"
                  :y1="pingChart.averageY"
                  :y2="pingChart.averageY"
                  class="average-line"
                />
                <path :d="pingChart.latencyPath" class="latency-line" />
                <circle
                  v-for="point in pingChart.points"
                  :key="point.item.sequence"
                  :cx="point.x"
                  :cy="point.y"
                  r="4"
                  :class="point.item.status === 'timeout' ? 'timeout-point' : 'latency-point'"
                />
                <g class="chart-x-axis">
                  <text
                    v-for="point in pingChart.points"
                    :key="`label-${point.item.sequence}`"
                    :x="point.x"
                    :y="pingChart.height - 10"
                    text-anchor="middle"
                  >
                    #{{ point.item.sequence }}
                  </text>
                </g>
              </svg>
              <div v-else class="ping-empty chart-empty">开始测试后，这里会展示延迟波形。</div>
            </div>
          </section>
        </article>
      </section>

      <section v-if="activeTool === 'subnet'" class="tool-stack subnet-page">
        <article class="panel subnet-card accent-cyan">
          <h2>子网计算器</h2>
          <div class="subnet-presets">
            <button v-for="preset in subnetPresets" :key="preset" type="button" @click="setSubnetPreset(preset)">{{ preset }}</button>
          </div>
          <div class="subnet-one-line">
            <label><span>IP 地址 / CIDR</span><input v-model="subnetInput" @keyup.enter="calculateSubnet(false)" /></label>
            <label><span>子网掩码</span><select v-model.number="subnetPrefix" @change="handlePrefixChange"><option v-for="item in prefixOptions" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
            <button class="primary" type="button" @click="calculateSubnet(false)">计算</button>
            <button type="button" @click="clearSubnet">清空</button>
          </div>
        </article>
        <article v-if="subnetResult" class="panel subnet-card accent-purple">
          <h2>计算结果</h2>
          <div class="result-grid subnet-results">
            <article><span>IP 地址</span><strong>{{ subnetResult.ip }}</strong></article>
            <article><span>子网掩码</span><strong>{{ subnetResult.mask }}</strong></article>
            <article><span>网络地址</span><strong class="green">{{ subnetResult.network }}/{{ subnetResult.prefix }}</strong></article>
            <article><span>广播地址</span><strong class="orange">{{ subnetResult.broadcast }}</strong></article>
            <article><span>可用主机范围</span><strong>{{ subnetResult.first_host }} - {{ subnetResult.last_host }}</strong></article>
            <article><span>可用主机数</span><strong>{{ subnetResult.usable_host_count }}</strong></article>
          </div>
          <pre class="binary-box">IP 地址     {{ subnetResult.binary.ip }}
子网掩码    {{ subnetResult.binary.mask }}
网络地址    {{ subnetResult.binary.network }}
广播地址    {{ subnetResult.binary.broadcast }}</pre>
        </article>
        <article class="panel subnet-card">
          <h2>IPv4子网划分</h2>
          <div class="segmented">
            <button :class="{ active: subnetMode === 'count' }" type="button" @click="subnetMode = 'count'">按子网数量</button>
            <button :class="{ active: subnetMode === 'hosts' }" type="button" @click="subnetMode = 'hosts'">按主机数量</button>
          </div>
          <div class="split-line">
            <label><span>划分子网数量</span><select v-model.number="subnetTargetPrefix"><option v-for="item in splitOptions" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
            <button class="primary small" type="button" @click="calculateSubnet(true)">划分</button>
          </div>
          <div v-if="subnetResult?.subnets?.length" class="subnet-table">
            <div class="subnet-table-head">
              <span>序号</span><span>网络地址</span><span>可用范围</span><span>广播地址</span><span>网关</span><span>主机数</span>
            </div>
            <div v-for="subnet in subnetResult.subnets" :key="subnet.index" class="subnet-table-row">
              <span>#{{ subnet.index + 1 }}</span>
              <strong>{{ subnet.cidr }}</strong>
              <span class="green">{{ subnet.first_host }} - {{ subnet.last_host }}</span>
              <span class="orange">{{ subnet.broadcast }}</span>
              <span>{{ subnet.gateway }}</span>
              <span>{{ subnet.usable_host_count }}</span>
            </div>
          </div>
        </article>
      </section>

      <section v-if="activeTool === 'auth'" class="auth-layout">
        <article class="panel auth-form-panel">
          <div class="scan-card">
            <div>
              <h2>扫码加入</h2>
              <p>支持 otpauth 链接导入，也可以识别二维码截图或图片文件。</p>
            </div>
            <div class="scan-actions">
              <button type="button" @click="triggerImageImport">识别图片</button>
              <button type="button" @click="parseAuthImport">解析链接</button>
              <input ref="imageInput" hidden type="file" accept="image/*" @change="handleImageImport" />
            </div>
          </div>
          <label><span>快速导入</span><textarea v-model="authImport" placeholder="粘贴 otpauth://totp/... 链接后，点击下方“解析导入”"></textarea></label>
          <div class="split-actions">
            <button type="button" @click="parseAuthImport">解析导入</button>
            <button type="button" @click="resetAuthForm">重置表单</button>
          </div>
          <div class="form-grid two">
            <label><span>服务名称</span><input v-model="authForm.issuer" placeholder="例如 GitHub / 阿里云" /></label>
            <label><span>账号备注</span><input v-model="authForm.account" placeholder="例如 admin@example.com" /></label>
          </div>
          <label><span>Base32 密钥</span><input v-model="authForm.secret" placeholder="输入或粘贴 Base32 Secret，支持空格和短杠" /></label>
          <div class="form-grid three">
            <label><span>位数</span><select v-model.number="authForm.digits"><option :value="6">6 位</option><option :value="8">8 位</option></select></label>
            <label><span>刷新周期</span><select v-model.number="authForm.period"><option :value="30">30 秒</option><option :value="60">60 秒</option></select></label>
            <label><span>算法</span><select v-model="authForm.algorithm"><option>SHA1</option><option>SHA256</option><option>SHA512</option></select></label>
          </div>
          <button class="primary full" type="button" @click="saveAuthEntry">{{ editingAuthId ? '保存修改' : '添加条目' }}</button>
        </article>

        <article class="panel auth-list-panel">
          <div class="panel-title">
            <div>
              <h2>验证码列表</h2>
              <p>点击卡片中的数字即可复制当前验证码。</p>
            </div>
            <div class="title-actions">
              <strong>{{ authEntries.length }} 条</strong>
              <button type="button" @click="loadAuthEntries">刷新</button>
              <button class="danger" type="button" @click="clearAuthEntries">清空</button>
            </div>
          </div>
          <div class="auth-card-grid">
            <article v-for="entry in authEntries" :key="entry.id" class="auth-card">
              <div class="auth-card-head">
                <div><h3>{{ entry.issuer }}</h3><p>{{ entry.account }}</p></div>
                <div class="card-actions">
                  <button type="button" @click="editAuth(entry)">编辑</button>
                  <button class="danger" type="button" @click="deleteAuth(entry)">删除</button>
                </div>
              </div>
              <div class="code-row">
                <button class="auth-code" type="button" @click="copyAuthCode(entry)">{{ entry.totp?.code ?? '------' }}</button>
                <div class="countdown" :style="{ '--progress': `${((entry.totp?.remaining ?? 0) / entry.period) * 360}deg` }">
                  <span>{{ entry.totp?.remaining ?? '-' }}</span>
                </div>
              </div>
              <p class="copy-hint">点击复制当前验证码</p>
              <div class="tag-line">
                <span>{{ entry.digits }} 位验证码</span>
                <span>{{ entry.period }} 秒刷新</span>
                <span>{{ entry.algorithm.replace('SHA', 'SHA-') }}</span>
                <button class="qr-button" type="button" @click="showQr(entry)">▦</button>
              </div>
            </article>
          </div>
        </article>
      </section>

      <section v-if="activeTool === 'password'" class="tool-grid">
        <article class="panel">
          <h2>密码生成器</h2>
          <label><span>项目名称</span><input v-model="passwordProject" placeholder="例如 数据库账号" /></label>
          <label><span>长度</span><input v-model.number="passwordLength" type="number" min="6" max="64" /></label>
          <label class="check-line"><input v-model="passwordOptions.include_uppercase" type="checkbox" />大写字母</label>
          <label class="check-line"><input v-model="passwordOptions.include_lowercase" type="checkbox" />小写字母</label>
          <label class="check-line"><input v-model="passwordOptions.include_numbers" type="checkbox" />数字</label>
          <label class="check-line"><input v-model="passwordOptions.include_symbols" type="checkbox" />符号</label>
          <button class="primary full" type="button" @click="generatePassword">生成并复制</button>
        </article>
        <article class="panel">
          <h2>最近记录</h2>
          <div class="password-list">
            <article v-for="record in passwordHistory" :key="record.id">
              <strong>{{ record.password }}</strong>
              <span>{{ record.project_name }} · {{ record.length }} 位</span>
              <div>
                <button type="button" @click="copyText(record.password, `已复制 ${record.project_name} 的密码。`)">复制</button>
                <button class="danger" type="button" @click="deletePassword(record)">删除</button>
              </div>
            </article>
          </div>
        </article>
      </section>
    </section>

    <div v-if="qrPreview" class="modal-backdrop" @click.self="qrPreview = ''">
      <article class="qr-modal">
        <button type="button" @click="qrPreview = ''">×</button>
        <img :src="qrPreview" alt="TOTP 二维码" />
      </article>
    </div>
  </main>
</template>

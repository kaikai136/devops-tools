<script setup lang="ts">
import { computed, markRaw, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { FitAddon } from '@xterm/addon-fit';
import { Terminal } from '@xterm/xterm';
import type { IDisposable } from '@xterm/xterm';
import '@xterm/xterm/css/xterm.css';

import { apiGet, apiPost } from '../../api';
import AppIcon from '../common/AppIcon.vue';

interface TerminalHost {
  id: number;
  name: string;
  group: number;
  privateIp: string;
  publicIp: string;
  port: number;
  loginUser: string;
  remark: string;
  verified: boolean;
  verifyStatus?: 'unverified' | 'verified' | 'failed';
}

interface TerminalGroup {
  id: number;
  name: string;
  hosts: TerminalHost[];
  children: TerminalGroup[];
}

type TerminalStatus = 'connecting' | 'connected' | 'closed' | 'error';
type TerminalSidebarMode = 'hosts' | 'files';

interface TerminalTab {
  id: string;
  host: TerminalHost;
  status: TerminalStatus;
  terminal: Terminal;
  fitAddon: FitAddon;
  socket: WebSocket | null;
  sessionId: string | null;
  mounted: boolean;
  disposables: IDisposable[];
  resizeObserver: ResizeObserver | null;
  highlightState: TerminalHighlightState;
  suppressInterruptUntil: number;
  hasUnreadOutput: boolean;
}

type TreeRow =
  | { kind: 'root'; group: TerminalRoot; level: number }
  | { kind: 'group'; group: TerminalGroup; level: number }
  | { kind: 'host'; host: TerminalHost; level: number };

interface TerminalRoot {
  id: null;
  name: string;
  count: number;
}

interface TerminalMessage {
  type: 'ready' | 'output' | 'error' | 'closed';
  sessionId?: string;
  data?: string;
  message?: string;
  reason?: string;
}

interface TerminalHighlightRule {
  name: string;
  pattern: RegExp;
  open: string;
  close: string;
}

interface TerminalHighlightState {
  sgrActive: boolean;
  pendingControl: string;
}

interface PersistedTerminalTab {
  id: string;
  hostId: number;
}

interface PersistedTerminalWorkspace {
  tabs: PersistedTerminalTab[];
  activeTabId: string | null;
}

interface TerminalFileEntry {
  name: string;
  type: 'directory' | 'file';
  modifiedAt: string;
  path: string;
  size?: number | string;
}

interface TerminalFilePreviewResponse {
  path: string;
  protocol: string;
  attempts: Array<{ protocol: string; status: 'success' | 'failed'; error?: string }>;
  content: string;
}

interface TerminalFileListResponse {
  path: string;
  protocol: string;
  entries: TerminalFileEntry[];
}

interface TerminalFileDownloadResponse {
  path: string;
  protocol: string;
  filename: string;
  contentBase64: string;
}

const ANSI_CONTROL_PATTERN = /\x1b\][^\x07]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]/g;
const ANSI_CONTROL_PREFIX_PATTERN = /^\x1b(?:\[[0-?]*[ -/]*)?$/;
const CONTROL_C = '\x03';
const MOUSE_SELECTION_INTERRUPT_SUPPRESSION_MS = 250;
const MOUSE_DOUBLE_CLICK_INTERRUPT_SUPPRESSION_MS = 1200;
const MAX_CONNECTING_TERMINALS = 2;
const TERMINAL_WORKSPACE_STORAGE_KEY = 'ops-tool.web-terminal.workspace';
const TERMINAL_SIDEBAR_WIDTH_STORAGE_KEY = 'ops-tool.web-terminal.sidebar-width';
const TERMINAL_SIDEBAR_MIN_WIDTH = 200;
const TERMINAL_SIDEBAR_MAX_WIDTH = 520;
const terminalHighlightRules: TerminalHighlightRule[] = [
  {
    name: 'danger',
    pattern: /\b(error|failed|failure|exception|traceback|denied|refused|fatal|critical)\b/gi,
    open: '\x1b[48;5;52m',
    close: '\x1b[49m',
  },
  {
    name: 'warning',
    pattern: /\b(warn|warning|timeout|retry|deprecated|unreachable)\b/gi,
    open: '\x1b[48;5;58m',
    close: '\x1b[49m',
  },
  {
    name: 'success',
    pattern: /\b(success|succeeded|ok|done|completed|running|started|active)\b/gi,
    open: '\x1b[48;5;22m',
    close: '\x1b[49m',
  },
  {
    name: 'ip',
    pattern: /\b(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}\b/g,
    open: '\x1b[48;5;24m',
    close: '\x1b[49m',
  },
];
const initialTerminalFileEntries: TerminalFileEntry[] = [
  { name: '..', type: 'directory', modifiedAt: '', path: '..' },
  { name: '.ansible', type: 'directory', modifiedAt: '2025/03/11', path: '~/.ansible' },
  { name: '.cache', type: 'directory', modifiedAt: '2025/05/07', path: '~/.cache' },
  { name: '.config', type: 'directory', modifiedAt: '2025/05/07', path: '~/.config' },
  { name: '.ctcss', type: 'directory', modifiedAt: '2025/08/01', path: '~/.ctcss' },
  { name: '.docker', type: 'directory', modifiedAt: '2026/01/20', path: '~/.docker' },
  { name: '.ssh', type: 'directory', modifiedAt: '2025/03/11', path: '~/.ssh' },
  { name: '.vim', type: 'directory', modifiedAt: '2026/04/10', path: '~/.vim' },
  { name: 'download_test', type: 'directory', modifiedAt: '2026/01/14', path: '~/download_test' },
  { name: '.bash_history', type: 'file', modifiedAt: '2026/05/25', path: '~/.bash_history', size: '18.5 KB' },
  { name: '.bashrc', type: 'file', modifiedAt: '2019/12/05', path: '~/.bashrc', size: '3.7 KB' },
  { name: '.lesshst', type: 'file', modifiedAt: '2025/10/15', path: '~/.lesshst', size: '1.2 KB' },
];

const terminalFileEntries = ref<TerminalFileEntry[]>(initialTerminalFileEntries);
const selectedTerminalFile = ref<TerminalFileEntry | null>(initialTerminalFileEntries.find((entry) => entry.type === 'file') ?? null);
const terminalFilePath = ref('.');
const terminalFileListProtocol = ref('');
const terminalFileListError = ref('');
const isTerminalFileListLoading = ref(false);
const terminalFilePreviewContent = ref('');
const terminalFilePreviewProtocol = ref('');
const terminalFilePreviewError = ref('');
const isTerminalFilePreviewLoading = ref(false);
const terminalFileUploadInput = ref<HTMLInputElement | null>(null);
const terminalFileListHeight = ref(0.54);
const terminalFilePreviewHeight = ref(0.5);
const terminalFileResizeMode = ref<'list' | 'preview' | null>(null);
let terminalFilePreviewRequestId = 0;
let terminalFileListRequestId = 0;

const groups = ref<TerminalGroup[]>([]);
const collapsed = ref<Set<number>>(new Set());
const rootExpanded = ref(true);
const rootLabel = ref(readTerminalRootLabel());
const search = ref('');
const tabs = ref<TerminalTab[]>([]);
const activeTabId = ref<string | null>(null);
const isLoadingTree = ref(false);
const treeError = ref('');
const highlightEnabled = ref(true);
const terminalSidebarMode = ref<TerminalSidebarMode>('hosts');
const sidebarWidth = ref(readTerminalSidebarWidth());
const isResizingSidebar = ref(false);
const terminalContainers = new Map<string, HTMLElement>();
const pendingConnectTabIds: string[] = [];
const connectingTabIds = new Set<string>();

const rows = computed(() => {
  const query = search.value.trim().toLowerCase();
  const root: TreeRow = { kind: 'root', group: terminalRoot.value, level: 0 };
  const treeRows = rootExpanded.value ? [root, ...flattenTerminalRows(groups.value, collapsed.value, 1)] : [root];
  return treeRows.filter((row) => {
    if (!query) return true;
    if (row.kind === 'root') return row.group.name.toLowerCase().includes(query);
    if (row.kind === 'group') return row.group.name.toLowerCase().includes(query);
    return [row.host.name, row.host.privateIp, row.host.publicIp, row.host.loginUser]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query));
  });
});

const activeTab = computed(() => tabs.value.find((tab) => tab.id === activeTabId.value) ?? null);
const activeTerminalNodeName = computed(() => activeTab.value?.host.name ?? '未选择主机');
const previewableTerminalFile = computed(() =>
  selectedTerminalFile.value?.type === 'file' ? selectedTerminalFile.value : null,
);
const terminalFilePreviewAttempts = computed(() =>
  terminalFilePreviewProtocol.value
    ? `已使用 ${terminalFilePreviewProtocol.value}`
    : '按 SFTP、SCP enhanced、SCP 顺序尝试',
);
const terminalFileStatusText = computed(() => {
  if (isTerminalFileListLoading.value) return '目录加载中...';
  if (terminalFileListProtocol.value) return `目录 ${terminalFileListProtocol.value}`;
  return '目录待加载';
});
const terminalRoot = computed<TerminalRoot>(() => ({
  id: null,
  name: rootLabel.value,
  count: countTerminalHosts(groups.value),
}));

const workspaceTitle = computed(() => {
  if (!activeTab.value) return '选择左侧主机开始连接';
  const host = activeTab.value.host;
  return `${host.name} / ${host.publicIp || host.privateIp}:${host.port}`;
});

function selectTerminalFile(entry: TerminalFileEntry) {
  if (!activeTab.value) return;
  selectedTerminalFile.value = entry;
}

async function loadTerminalDirectory(path = terminalFilePath.value) {
  if (!activeTab.value) return;
  const targetPath = resolveTerminalDirectoryPath(path);
  const requestId = ++terminalFileListRequestId;
  isTerminalFileListLoading.value = true;
  terminalFileListError.value = '';

  try {
    const response = await apiPost<TerminalFileListResponse>(
      `/api/web-terminal/hosts/${activeTab.value.host.id}/files/list/`,
      { path: targetPath },
    );
    if (requestId !== terminalFileListRequestId) return;
    terminalFilePath.value = response.path;
    terminalFileEntries.value = response.entries;
    terminalFileListProtocol.value = response.protocol;
    selectedTerminalFile.value = response.entries.find((entry) => entry.type === 'file') ?? response.entries[0] ?? null;
  } catch (error) {
    if (requestId !== terminalFileListRequestId) return;
    terminalFileListError.value = error instanceof Error ? error.message : '目录加载失败';
  } finally {
    if (requestId === terminalFileListRequestId) {
      isTerminalFileListLoading.value = false;
    }
  }
}

function openTerminalDirectory(entry: TerminalFileEntry) {
  if (!activeTab.value || entry.type !== 'directory') return;
  void loadTerminalDirectory(entry.path);
}

function openTerminalParentDirectory() {
  void loadTerminalDirectory(parentTerminalDirectoryPath(terminalFilePath.value));
}

function resolveTerminalDirectoryPath(path: string) {
  const value = String(path || '.').trim();
  if (value === '..') return parentTerminalDirectoryPath(terminalFilePath.value);
  if (value.startsWith('/') || value.startsWith('~') || value === '.') return value;
  if (terminalFilePath.value === '/' || terminalFilePath.value === '') return `/${value}`;
  if (terminalFilePath.value === '.') return value;
  return `${terminalFilePath.value.replace(/\/+$/, '')}/${value}`;
}

function parentTerminalDirectoryPath(path: string) {
  const value = String(path || '.').replace(/\/+$/, '');
  if (!value || value === '.' || value === '~') return '.';
  if (value === '/') return '/';
  if (value.startsWith('~/')) {
    const parent = value.slice(0, value.lastIndexOf('/'));
    return parent || '~';
  }
  const parent = value.slice(0, value.lastIndexOf('/'));
  return parent || (value.startsWith('/') ? '/' : '.');
}

async function previewTerminalFile(entry = selectedTerminalFile.value) {
  if (!activeTab.value) return;
  if (!entry || entry.type !== 'file') return;
  selectedTerminalFile.value = entry;
  const requestId = ++terminalFilePreviewRequestId;
  isTerminalFilePreviewLoading.value = true;
  terminalFilePreviewError.value = '';
  terminalFilePreviewProtocol.value = '';

  try {
    const response = await apiPost<TerminalFilePreviewResponse>(
      `/api/web-terminal/hosts/${activeTab.value.host.id}/files/preview/`,
      { path: entry.path },
    );
    if (requestId !== terminalFilePreviewRequestId) return;
    terminalFilePreviewContent.value = response.content;
    terminalFilePreviewProtocol.value = response.protocol;
  } catch (error) {
    if (requestId !== terminalFilePreviewRequestId) return;
    terminalFilePreviewContent.value = '';
    terminalFilePreviewError.value = error instanceof Error ? error.message : '文件预览失败';
  } finally {
    if (requestId === terminalFilePreviewRequestId) {
      isTerminalFilePreviewLoading.value = false;
    }
  }
}

async function downloadTerminalFile(entry = selectedTerminalFile.value) {
  if (!activeTab.value || !entry || entry.type !== 'file') return;
  try {
    const response = await apiPost<TerminalFileDownloadResponse>(
      `/api/web-terminal/hosts/${activeTab.value.host.id}/files/download/`,
      { path: entry.path },
    );
    terminalFilePreviewProtocol.value = response.protocol;
    const bytes = Uint8Array.from(window.atob(response.contentBase64), (char) => char.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes]));
    const link = document.createElement('a');
    link.href = url;
    link.download = response.filename || entry.name;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    terminalFilePreviewError.value = error instanceof Error ? error.message : '文件下载失败';
  }
}

function openTerminalUpload() {
  if (!activeTab.value) return;
  terminalFileUploadInput.value?.click();
}

async function uploadTerminalFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (!activeTab.value || !file) return;
  try {
    const contentBase64 = await fileToBase64(file);
    const response = await apiPost<{ protocol: string }>(
      `/api/web-terminal/hosts/${activeTab.value.host.id}/files/upload/`,
      { directory: terminalFilePath.value, filename: file.name, contentBase64 },
    );
    terminalFileListProtocol.value = response.protocol;
    await loadTerminalDirectory(terminalFilePath.value);
  } catch (error) {
    terminalFileListError.value = error instanceof Error ? error.message : '文件上传失败';
  }
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || '');
      resolve(result.includes(',') ? result.split(',')[1] : result);
    };
    reader.onerror = () => reject(reader.error ?? new Error('文件读取失败'));
    reader.readAsDataURL(file);
  });
}

watch([activeTabId, terminalSidebarMode], () => {
  terminalFilePreviewRequestId += 1;
  terminalFilePreviewContent.value = '';
  terminalFilePreviewProtocol.value = '';
  terminalFilePreviewError.value = '';
  isTerminalFilePreviewLoading.value = false;
  if (activeTab.value && terminalSidebarMode.value === 'files') {
    terminalFilePath.value = '.';
    void loadTerminalDirectory('.');
  }
});

const workspaceStatus = computed(() => {
  if (!activeTab.value) return '';
  if (activeTab.value.status === 'connecting') return '连接中...';
  if (activeTab.value.status === 'connected') return '已连接';
  if (activeTab.value.status === 'error') return '连接失败';
  return '已关闭';
});
const terminalShellStyle = computed<Record<string, string>>(() => ({
  '--terminal-sidebar-width': `${sidebarWidth.value}px`,
}));
const terminalFileBrowserStyle = computed<Record<string, string>>(() => ({
  '--terminal-file-list-fr': `${terminalFileListHeight.value}fr`,
  '--terminal-file-preview-fr': `${terminalFilePreviewHeight.value}fr`,
  '--terminal-file-transfer-fr': `${1 - terminalFilePreviewHeight.value}fr`,
}));

onMounted(async () => {
  await loadTree();
  await restoreTerminalWorkspace();
  const params = new URLSearchParams(window.location.search);
  const hostId = Number(params.get('host'));
  if (hostId) {
    const restoredTab = tabs.value.find((tab) => tab.host.id === hostId);
    if (restoredTab) {
      await activateTab(restoredTab.id);
    } else {
      const host = findHostById(groups.value, hostId);
      if (host) await openHostTab(host);
    }
  }
});

onBeforeUnmount(() => {
  stopSidebarResize();
  stopTerminalFileResize();
  for (const tab of tabs.value) disposeTab(tab);
});

async function loadTree() {
  isLoadingTree.value = true;
  treeError.value = '';
  try {
    groups.value = await apiGet<TerminalGroup[]>('/api/web-terminal/tree/');
  } catch (error) {
    treeError.value = (error as Error).message;
  } finally {
    isLoadingTree.value = false;
  }
}

function toggleGroup(group: TerminalGroup) {
  const next = new Set(collapsed.value);
  if (next.has(group.id)) {
    next.delete(group.id);
  } else {
    next.add(group.id);
  }
  collapsed.value = next;
}

async function openHostTab(host: TerminalHost) {
  const createdTab = createTerminalTab(host);
  tabs.value = [...tabs.value, createdTab];
  activeTabId.value = createdTab.id;
  saveTerminalWorkspace();
  await nextTick();
  const tab = getTabById(createdTab.id) ?? createdTab;
  mountTerminal(tab);
  enqueueConnectTab(tab);
}

function toggleRoot() {
  rootExpanded.value = !rootExpanded.value;
}

async function activateTab(tabId: string) {
  activeTabId.value = tabId;
  saveTerminalWorkspace();
  await nextTick();
  const tab = tabs.value.find((item) => item.id === tabId);
  if (tab) {
    tab.hasUnreadOutput = false;
    mountTerminal(tab);
    fitTerminal(tab);
    tab.terminal.focus();
  }
}

function createTerminalTab(host: TerminalHost, tabId = createTerminalTabId(host.id)): TerminalTab {
  const terminal = markRaw(
    new Terminal({
      cursorBlink: true,
      convertEol: false,
      fontFamily: 'Consolas, "Courier New", monospace',
      fontSize: 14,
      lineHeight: 1.25,
      scrollback: 5000,
      theme: {
        background: '#000000',
        foreground: '#f5f7fb',
        cursor: '#f5f7fb',
        selectionBackground: '#31588f',
      },
    }),
  );
  const fitAddon = markRaw(new FitAddon());
  terminal.loadAddon(fitAddon);
  terminal.attachCustomKeyEventHandler((event) => handleTerminalKey(event, terminal));
  terminal.writeln('CAPTAIN WEB TERMINAL');
  terminal.writeln(`正在连接 ${host.name} (${host.publicIp || host.privateIp}:${host.port})...`);

  return {
    id: tabId,
    host,
    status: 'connecting',
    terminal,
    fitAddon,
    socket: null,
    sessionId: null,
    mounted: false,
    disposables: [],
    resizeObserver: null,
    highlightState: {
      sgrActive: false,
      pendingControl: '',
    },
    suppressInterruptUntil: 0,
    hasUnreadOutput: false,
  };
}

function createTerminalTabId(hostId: number) {
  return `${hostId}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function handleTerminalKey(event: KeyboardEvent, terminal: Terminal) {
  const isCopyShortcut = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'c';
  if (!isCopyShortcut || !terminal.hasSelection()) return true;

  const selection = terminal.getSelection();
  if (selection) {
    navigator.clipboard?.writeText(selection).catch(() => undefined);
  }
  return false;
}

function suppressMouseInterrupt(tab: TerminalTab, duration: number) {
  tab.suppressInterruptUntil = Math.max(tab.suppressInterruptUntil, Date.now() + duration);
}

function markTerminalDoubleClick(tab: TerminalTab) {
  suppressMouseInterrupt(tab, MOUSE_DOUBLE_CLICK_INTERRUPT_SUPPRESSION_MS);
}

function getSendableTerminalData(tab: TerminalTab, data: string) {
  if (!data.includes(CONTROL_C) || Date.now() > tab.suppressInterruptUntil) return data;
  return data.split(CONTROL_C).join('');
}

function mountTerminal(tab: TerminalTab) {
  if (tab.mounted) return;
  const container = terminalContainers.get(tab.id);
  if (!container) return;

  tab.terminal.open(container);
  tab.mounted = true;
  tab.disposables.push(
    tab.terminal.onData((data) => {
      const sendableData = getSendableTerminalData(tab, data);
      if (!sendableData) return;

      if (tab.socket?.readyState === WebSocket.OPEN) {
        tab.socket.send(JSON.stringify({ type: 'input', data: sendableData }));
      }
    }),
  );
  const handleMouseDown = (event: MouseEvent) => {
    if (event.button !== 0) return;
    suppressMouseInterrupt(tab, MOUSE_SELECTION_INTERRUPT_SUPPRESSION_MS);
    if (event.detail >= 2) markTerminalDoubleClick(tab);
  };
  const handleDoubleClick = () => markTerminalDoubleClick(tab);
  container.addEventListener('mousedown', handleMouseDown, true);
  container.addEventListener('dblclick', handleDoubleClick, true);
  tab.disposables.push({
    dispose: () => {
      container.removeEventListener('mousedown', handleMouseDown, true);
      container.removeEventListener('dblclick', handleDoubleClick, true);
    },
  });
  tab.resizeObserver = new ResizeObserver(() => fitTerminal(tab));
  tab.resizeObserver.observe(container);
  fitTerminal(tab);
  tab.terminal.focus();
}

function enqueueConnectTab(tab: TerminalTab) {
  if (tab.status !== 'connecting' || pendingConnectTabIds.includes(tab.id) || connectingTabIds.has(tab.id)) return;
  pendingConnectTabIds.push(tab.id);
  drainConnectQueue();
}

function drainConnectQueue() {
  while (connectingTabIds.size < MAX_CONNECTING_TERMINALS && pendingConnectTabIds.length) {
    const tabId = pendingConnectTabIds.shift();
    if (!tabId) continue;

    const tab = getTabById(tabId);
    if (!tab || tab.status !== 'connecting') continue;

    connectingTabIds.add(tab.id);
    connectTab(tab);
  }
}

function finishConnectingTab(tab: TerminalTab) {
  if (!connectingTabIds.delete(tab.id)) return;
  drainConnectQueue();
}

function connectTab(tab: TerminalTab) {
  const socket = new WebSocket(buildWebSocketUrl(tab.host.id));
  tab.socket = socket;

  socket.addEventListener('open', () => fitTerminal(tab));
  socket.addEventListener('message', (event) => handleSocketMessage(tab, event));
  socket.addEventListener('error', () => {
    if (tab.status !== 'closed') {
      tab.status = 'error';
      tab.terminal.writeln('\r\n\x1b[31mWebSocket 连接失败。\x1b[0m');
    }
    finishConnectingTab(tab);
  });
  socket.addEventListener('close', () => {
    tab.socket = null;
    finishConnectingTab(tab);
    if (tab.status === 'connected' || tab.status === 'connecting') {
      tab.status = 'closed';
      tab.terminal.writeln('\r\n\x1b[33m连接已关闭。\x1b[0m');
    }
  });
}

function handleSocketMessage(tab: TerminalTab, event: MessageEvent<string>) {
  let message: TerminalMessage;
  try {
    message = JSON.parse(event.data) as TerminalMessage;
  } catch {
    tab.terminal.writeln('\r\n\x1b[31m终端消息解析失败。\x1b[0m');
    return;
  }

  if (message.type === 'ready') {
    tab.status = 'connected';
    tab.sessionId = message.sessionId ?? null;
    finishConnectingTab(tab);
    fitTerminal(tab);
    return;
  }

  if (message.type === 'output') {
    tab.terminal.write(highlightTerminalOutput(message.data ?? '', tab.highlightState));
    if (tab.id !== activeTabId.value) {
      markTabUnread(tab.id);
    }
    return;
  }

  if (message.type === 'error') {
    tab.status = 'error';
    finishConnectingTab(tab);
    tab.terminal.writeln(`\r\n\x1b[31m${message.message ?? '终端连接失败'}\x1b[0m`);
    return;
  }

  if (message.type === 'closed') {
    tab.status = 'closed';
    finishConnectingTab(tab);
    tab.terminal.writeln(`\r\n\x1b[33m${message.reason ?? '连接已关闭'}\x1b[0m`);
  }
}

function getTabById(tabId: string) {
  return tabs.value.find((item) => item.id === tabId) ?? null;
}

function markTabUnread(tabId: string) {
  const tab = getTabById(tabId);
  if (tab && tab.id !== activeTabId.value) {
    tab.hasUnreadOutput = true;
  }
}

function fitTerminal(tab: TerminalTab) {
  if (!tab.mounted || activeTabId.value !== tab.id) return;
  try {
    tab.fitAddon.fit();
    if (tab.socket?.readyState === WebSocket.OPEN) {
      tab.socket.send(JSON.stringify({ type: 'resize', cols: tab.terminal.cols, rows: tab.terminal.rows }));
    }
  } catch {
    // xterm cannot fit until the container has a measurable size.
  }
}

function startSidebarResize(event: MouseEvent) {
  event.preventDefault();
  isResizingSidebar.value = true;
  window.addEventListener('mousemove', resizeSidebar);
  window.addEventListener('mouseup', stopSidebarResize);
  document.body.classList.add('terminal-resizing');
}

function resizeSidebar(event: MouseEvent) {
  if (!isResizingSidebar.value) return;
  const nextWidth = Math.min(Math.max(event.clientX, TERMINAL_SIDEBAR_MIN_WIDTH), TERMINAL_SIDEBAR_MAX_WIDTH);
  sidebarWidth.value = nextWidth;
  window.localStorage.setItem(TERMINAL_SIDEBAR_WIDTH_STORAGE_KEY, String(nextWidth));
  fitActiveTerminalSoon();
}

function stopSidebarResize() {
  if (!isResizingSidebar.value) return;
  isResizingSidebar.value = false;
  window.removeEventListener('mousemove', resizeSidebar);
  window.removeEventListener('mouseup', stopSidebarResize);
  document.body.classList.remove('terminal-resizing');
  fitActiveTerminalSoon();
}

function startTerminalFileResize(mode: 'list' | 'preview', event: MouseEvent) {
  event.preventDefault();
  terminalFileResizeMode.value = mode;
  document.body.classList.add('terminal-file-resizing');
  resizeTerminalFilePanels(event);
  window.addEventListener('mousemove', resizeTerminalFilePanels);
  window.addEventListener('mouseup', stopTerminalFileResize);
}

function resizeTerminalFilePanels(event: MouseEvent) {
  const mode = terminalFileResizeMode.value;
  const browser = document.querySelector<HTMLElement>('.terminal-file-browser');
  if (!mode || !browser) return;

  const rect = browser.getBoundingClientRect();
  const fixedRowsHeight = 36 + 38 + 30 + 34 + 12 + 28;
  const availableHeight = Math.max(240, rect.height - fixedRowsHeight);

  if (mode === 'list') {
    const listY = event.clientY - rect.top - 36 - 38 - 30;
    terminalFileListHeight.value = Math.min(0.76, Math.max(0.28, listY / availableHeight));
    return;
  }

  const lowerHeight = availableHeight * Math.max(0.24, 1 - terminalFileListHeight.value);
  const lowerTop = 36 + 38 + 30 + availableHeight * terminalFileListHeight.value + 34 + 6;
  const previewY = event.clientY - rect.top - lowerTop;
  terminalFilePreviewHeight.value = Math.min(0.78, Math.max(0.25, previewY / lowerHeight));
}

function stopTerminalFileResize() {
  if (!terminalFileResizeMode.value) return;
  terminalFileResizeMode.value = null;
  window.removeEventListener('mousemove', resizeTerminalFilePanels);
  window.removeEventListener('mouseup', stopTerminalFileResize);
  document.body.classList.remove('terminal-file-resizing');
}

function fitActiveTerminalSoon() {
  window.requestAnimationFrame(() => {
    const tab = activeTab.value;
    if (tab) fitTerminal(tab);
  });
}

async function closeTab(tab: TerminalTab) {
  const index = tabs.value.findIndex((item) => item.id === tab.id);
  disposeTab(tab);
  tabs.value = tabs.value.filter((item) => item.id !== tab.id);
  terminalContainers.delete(tab.id);

  if (activeTabId.value === tab.id) {
    const nextTab = tabs.value[Math.min(index, tabs.value.length - 1)] ?? null;
    activeTabId.value = nextTab?.id ?? null;
    if (nextTab) await activateTab(nextTab.id);
  }
  saveTerminalWorkspace();
}

async function restoreTerminalWorkspace() {
  const workspace = loadTerminalWorkspace();
  if (!workspace?.tabs.length || treeError.value) return;

  const restoredTabs = workspace.tabs
    .map((item) => {
      const host = findHostById(groups.value, item.hostId);
      return host ? createTerminalTab(host, item.id) : null;
    })
    .filter((tab): tab is TerminalTab => Boolean(tab));

  if (!restoredTabs.length) {
    saveTerminalWorkspace();
    return;
  }

  tabs.value = restoredTabs;
  activeTabId.value = restoredTabs.some((tab) => tab.id === workspace.activeTabId) ? workspace.activeTabId : restoredTabs[0].id;
  saveTerminalWorkspace();

  await nextTick();
  for (const tab of restoredTabs) {
    mountTerminal(tab);
    enqueueConnectTab(tab);
  }
}

function loadTerminalWorkspace(): PersistedTerminalWorkspace | null {
  if (typeof window === 'undefined') return null;

  const raw = window.sessionStorage.getItem(TERMINAL_WORKSPACE_STORAGE_KEY);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as Partial<PersistedTerminalWorkspace>;
    if (!Array.isArray(parsed.tabs)) return null;

    const seenIds = new Set<string>();
    const persistedTabs = parsed.tabs.flatMap((item) => {
      if (!item || typeof item !== 'object') return [];
      const id = typeof item.id === 'string' && item.id ? item.id : '';
      const hostId = Number(item.hostId);
      if (!id || !Number.isFinite(hostId) || seenIds.has(id)) return [];
      seenIds.add(id);
      return [{ id, hostId }];
    });

    return {
      tabs: persistedTabs,
      activeTabId: typeof parsed.activeTabId === 'string' ? parsed.activeTabId : null,
    };
  } catch {
    return null;
  }
}

function saveTerminalWorkspace() {
  if (typeof window === 'undefined') return;

  const workspace: PersistedTerminalWorkspace = {
    tabs: tabs.value.map((tab) => ({ id: tab.id, hostId: tab.host.id })),
    activeTabId: activeTabId.value,
  };

  if (!workspace.tabs.length) {
    window.sessionStorage.removeItem(TERMINAL_WORKSPACE_STORAGE_KEY);
    return;
  }

  window.sessionStorage.setItem(TERMINAL_WORKSPACE_STORAGE_KEY, JSON.stringify(workspace));
}

function disposeTab(tab: TerminalTab) {
  tab.status = 'closed';
  removePendingConnectTab(tab.id);
  finishConnectingTab(tab);
  if (tab.socket && tab.socket.readyState !== WebSocket.CLOSED) {
    tab.socket.close();
  }
  tab.socket = null;
  tab.resizeObserver?.disconnect();
  tab.resizeObserver = null;
  for (const disposable of tab.disposables) disposable.dispose();
  tab.disposables = [];
  tab.terminal.dispose();
}

function removePendingConnectTab(tabId: string) {
  const index = pendingConnectTabIds.indexOf(tabId);
  if (index !== -1) {
    pendingConnectTabIds.splice(index, 1);
  }
}

function setTerminalContainer(tabId: string, element: unknown) {
  if (element instanceof HTMLElement) {
    terminalContainers.set(tabId, element);
    const tab = tabs.value.find((item) => item.id === tabId);
    if (tab) mountTerminal(tab);
  } else {
    terminalContainers.delete(tabId);
  }
}

function buildWebSocketUrl(hostId: number) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/ws/web-terminal/${hostId}/`;
}

function highlightTerminalOutput(output: string, state: TerminalHighlightState) {
  if (!output && !state.pendingControl) return '';

  const source = state.pendingControl + output;
  state.pendingControl = getTrailingAnsiPrefix(source);
  const parseableOutput = state.pendingControl ? source.slice(0, -state.pendingControl.length) : source;
  const shouldHighlight = highlightEnabled.value;

  let result = '';
  let lastIndex = 0;
  ANSI_CONTROL_PATTERN.lastIndex = 0;

  for (let match = ANSI_CONTROL_PATTERN.exec(parseableOutput); match; match = ANSI_CONTROL_PATTERN.exec(parseableOutput)) {
    if (match.index > lastIndex) {
      const plainText = parseableOutput.slice(lastIndex, match.index);
      result += shouldHighlight && !state.sgrActive ? highlightPlainText(plainText) : plainText;
    }

    const controlSequence = match[0];
    result += controlSequence;
    state.sgrActive = getNextSgrState(controlSequence, state.sgrActive);
    lastIndex = match.index + controlSequence.length;
  }

  if (lastIndex < parseableOutput.length) {
    const plainText = parseableOutput.slice(lastIndex);
    result += shouldHighlight && !state.sgrActive ? highlightPlainText(plainText) : plainText;
  }

  return result;
}

function getTrailingAnsiPrefix(output: string) {
  const escapeIndex = output.lastIndexOf('\x1b');
  if (escapeIndex === -1) return '';

  const suffix = output.slice(escapeIndex);
  if (suffix.startsWith('\x1b]')) {
    const bellIndex = suffix.indexOf('\x07', 2);
    const stringTerminatorIndex = suffix.indexOf('\x1b\\', 2);
    return bellIndex === -1 && stringTerminatorIndex === -1 ? suffix : '';
  }

  return ANSI_CONTROL_PREFIX_PATTERN.test(suffix) ? suffix : '';
}

function highlightPlainText(text: string) {
  const matches: Array<{ start: number; end: number; rule: TerminalHighlightRule; priority: number }> = [];

  terminalHighlightRules.forEach((rule, priority) => {
    rule.pattern.lastIndex = 0;
    for (let match = rule.pattern.exec(text); match; match = rule.pattern.exec(text)) {
      if (!match[0]) {
        rule.pattern.lastIndex += 1;
        continue;
      }
      matches.push({ start: match.index, end: match.index + match[0].length, rule, priority });
    }
  });

  if (!matches.length) return text;

  matches.sort((left, right) => left.start - right.start || left.priority - right.priority || right.end - left.end);

  let result = '';
  let cursor = 0;
  for (const match of matches) {
    if (match.start < cursor) continue;
    result += text.slice(cursor, match.start);
    result += `${match.rule.open}${text.slice(match.start, match.end)}${match.rule.close}`;
    cursor = match.end;
  }
  result += text.slice(cursor);

  return result;
}

function getNextSgrState(sequence: string, current: boolean) {
  if (!sequence.endsWith('m')) return current;

  const rawParams = sequence.slice(2, -1);
  const params = rawParams ? rawParams.split(';') : ['0'];
  if (params.some((param) => param === '' || param === '0')) return false;

  return true;
}

function flattenTerminalRows(source: TerminalGroup[], hidden: Set<number>, level = 0): TreeRow[] {
  return source.flatMap((group) => {
    const current: TreeRow[] = [{ kind: 'group', group, level }];
    if (!hidden.has(group.id)) {
      current.push(...flattenTerminalRows(group.children, hidden, level + 1));
      current.push(...group.hosts.map((host) => ({ kind: 'host' as const, host, level: level + 1 })));
    }
    return current;
  });
}

function countTerminalHosts(source: TerminalGroup[]): number {
  return source.reduce((total, group) => total + group.hosts.length + countTerminalHosts(group.children), 0);
}

function findHostById(source: TerminalGroup[], hostId: number): TerminalHost | null {
  for (const group of source) {
    const host = group.hosts.find((item) => item.id === hostId);
    if (host) return host;
    const childHost = findHostById(group.children, hostId);
    if (childHost) return childHost;
  }
  return null;
}

function readTerminalRootLabel() {
  if (typeof window === 'undefined') return 'DEFAULT';
  return window.localStorage.getItem('ops-tool.host-manager.root-label') || 'DEFAULT';
}

function readTerminalSidebarWidth() {
  if (typeof window === 'undefined') return 284;
  const saved = Number(window.localStorage.getItem(TERMINAL_SIDEBAR_WIDTH_STORAGE_KEY));
  if (!Number.isFinite(saved)) return 284;
  return Math.min(Math.max(saved, TERMINAL_SIDEBAR_MIN_WIDTH), TERMINAL_SIDEBAR_MAX_WIDTH);
}
</script>

<template>
  <main class="terminal-shell" :class="{ resizing: isResizingSidebar }" :style="terminalShellStyle">
    <aside class="terminal-sidebar">
      <nav class="terminal-side-switch" aria-label="终端侧栏切换">
        <button
          type="button"
          title="服务器列表"
          aria-label="服务器列表"
          :class="{ active: terminalSidebarMode === 'hosts' }"
          @click="terminalSidebarMode = 'hosts'"
        >
          <AppIcon name="server" :size="18" />
        </button>
        <button
          type="button"
          title="FTP 文件夹"
          aria-label="FTP 文件夹"
          :class="{ active: terminalSidebarMode === 'files' }"
          @click="terminalSidebarMode = 'files'"
        >
          <AppIcon name="folder" :size="19" />
        </button>
      </nav>
      <div class="terminal-sidebar-panel">
        <template v-if="terminalSidebarMode === 'hosts'">
          <div class="terminal-search">
            <input v-model="search" placeholder="输入主机名/IP检索" />
            <button type="button" title="刷新" aria-label="刷新" @click="loadTree"><AppIcon name="refresh" :size="16" /></button>
          </div>
          <div class="terminal-tree">
            <button
              v-for="row in rows"
              :key="row.kind === 'root' ? 'group-root' : row.kind === 'group' ? `group-${row.group.id}` : `host-${row.host.id}`"
              class="terminal-tree-row"
              :class="{ root: row.kind === 'root', host: row.kind === 'host', active: row.kind === 'host' && activeTab?.host.id === row.host.id }"
              :style="{ paddingLeft: `${12 + row.level * 24}px` }"
              type="button"
              @click="row.kind === 'root' ? toggleRoot() : row.kind === 'group' && toggleGroup(row.group)"
              @dblclick="row.kind === 'host' && openHostTab(row.host)"
            >
              <template v-if="row.kind === 'root'">
                <span><AppIcon :name="rootExpanded ? 'chevronDown' : 'chevronRight'" :size="15" /></span>
                <strong><AppIcon name="folder" :size="16" />{{ row.group.name }}</strong>
                <em>{{ row.group.count }}</em>
              </template>
              <template v-else-if="row.kind === 'group'">
                <span><AppIcon :name="collapsed.has(row.group.id) ? 'chevronRight' : 'chevronDown'" :size="15" /></span>
                <strong><AppIcon name="folder" :size="16" />{{ row.group.name }}</strong>
              </template>
              <template v-else>
                <span><AppIcon name="server" :size="15" /></span>
                <strong>{{ row.host.name }}</strong>
                <i
                  v-if="row.host.verified || row.host.verifyStatus === 'failed'"
                  class="terminal-host-verify-dot"
                  :class="{ failed: row.host.verifyStatus === 'failed' }"
                  :title="row.host.verifyStatus === 'failed' ? '验证失败' : '已验证'"
                  :aria-label="row.host.verifyStatus === 'failed' ? '验证失败' : '已验证'"
                ></i>
              </template>
            </button>
            <p v-if="isLoadingTree" class="terminal-tree-empty">加载中...</p>
            <p v-else-if="treeError" class="terminal-tree-empty">{{ treeError }}</p>
            <p v-else-if="!rows.length" class="terminal-tree-empty">没有匹配的主机。</p>
          </div>
        </template>
        <template v-else>
          <div class="terminal-file-browser" :style="terminalFileBrowserStyle">
            <header class="terminal-file-title">
              <strong>文件浏览器</strong>
              <span class="terminal-file-node">{{ activeTerminalNodeName }}</span>
            </header>
            <div class="terminal-file-toolbar">
              <button type="button" title="新建文件" aria-label="新建文件"><AppIcon name="plus" :size="15" /></button>
              <button type="button" title="新建文件夹" aria-label="新建文件夹"><AppIcon name="folderPlus" :size="15" /></button>
              <span></span>
              <button type="button" title="上传" aria-label="上传" @click="openTerminalUpload"><AppIcon name="upload" :size="15" /></button>
              <button type="button" title="下载" aria-label="下载" @click="downloadTerminalFile()"><AppIcon name="download" :size="15" /></button>
              <button type="button" title="删除" aria-label="删除"><AppIcon name="trash" :size="15" /></button>
              <span></span>
              <button type="button" title="返回上级" aria-label="返回上级" @click="openTerminalParentDirectory"><AppIcon name="chevronRight" :size="15" /></button>
              <button type="button" title="刷新" aria-label="刷新" @click="loadTerminalDirectory()"><AppIcon name="refresh" :size="15" /></button>
              <span></span>
              <button type="button" title="搜索" aria-label="搜索"><AppIcon name="search" :size="15" /></button>
            </div>
            <div class="terminal-file-path">
              <span>{{ terminalFilePath }}</span>
              <button type="button" title="收藏路径" aria-label="收藏路径"><AppIcon name="folder" :size="14" /></button>
            </div>
            <div class="terminal-file-table">
              <div class="terminal-file-table-head">
                <button type="button">名称 <em>▲</em></button>
                <span>修改时间</span>
                <span>操作</span>
              </div>
              <div class="terminal-file-list">
                <div
                  v-for="entry in terminalFileEntries"
                  :key="entry.name"
                  class="terminal-file-item"
                  :class="{ selected: selectedTerminalFile?.name === entry.name }"
                  role="button"
                  :tabindex="activeTab ? 0 : -1"
                  :aria-disabled="!activeTab"
                  @click="selectTerminalFile(entry)"
                  @dblclick="entry.type === 'directory' ? openTerminalDirectory(entry) : previewTerminalFile(entry)"
                  @keydown.enter.prevent="entry.type === 'directory' ? openTerminalDirectory(entry) : previewTerminalFile(entry)"
                >
                  <span class="terminal-file-name">
                    <AppIcon :name="entry.type === 'directory' ? 'folder' : 'settings'" :size="15" />
                    <strong>{{ entry.name }}</strong>
                  </span>
                  <time>{{ entry.modifiedAt }}</time>
                  <span class="terminal-file-actions">
                    <button v-if="entry.type === 'file'" type="button" title="预览" aria-label="预览" @click.stop="previewTerminalFile(entry)">
                      <AppIcon name="eye" :size="13" />
                    </button>
                    <button v-if="entry.type === 'file'" type="button" title="下载" aria-label="下载" @click.stop="downloadTerminalFile(entry)">
                      <AppIcon name="download" :size="13" />
                    </button>
                    <button type="button" title="删除" aria-label="删除" @click.stop>
                      <AppIcon name="trash" :size="13" />
                    </button>
                  </span>
                </div>
                <p v-if="!activeTab" class="terminal-tree-empty">请选择服务器</p>
                <p v-else-if="isTerminalFileListLoading" class="terminal-tree-empty">目录加载中...</p>
                <p v-else-if="terminalFileListError" class="terminal-tree-empty">{{ terminalFileListError }}</p>
              </div>
            </div>
            <footer class="terminal-file-status">
              <span>共 {{ terminalFileEntries.length }} 项</span>
              <span>{{ terminalFileStatusText }}</span>
              <div>
                <button type="button" title="打开本地目录" aria-label="打开本地目录"><AppIcon name="folder" :size="15" /></button>
                <button type="button" title="同步" aria-label="同步" @click="loadTerminalDirectory()"><AppIcon name="refresh" :size="15" /></button>
                <button type="button" title="传输队列" aria-label="传输队列" @click="openTerminalUpload"><AppIcon name="upload" :size="15" /></button>
              </div>
            </footer>
            <div
              class="terminal-file-splitter"
              role="separator"
              aria-label="调整文件列表高度"
              @mousedown="startTerminalFileResize('list', $event)"
            ></div>
            <input ref="terminalFileUploadInput" hidden type="file" @change="uploadTerminalFile" />
            <section class="terminal-file-preview">
              <header>
                <strong>文件预览</strong>
                <span>{{ previewableTerminalFile?.name || '未选择文件' }}</span>
              </header>
              <div class="terminal-file-preview-meta">
                <span>{{ terminalFilePreviewAttempts }}</span>
              </div>
              <pre v-if="terminalFilePreviewContent">{{ terminalFilePreviewContent }}</pre>
              <div v-else-if="isTerminalFilePreviewLoading" class="terminal-file-preview-empty">正在尝试连接...</div>
              <div v-else-if="terminalFilePreviewError" class="terminal-file-preview-empty error">{{ terminalFilePreviewError }}</div>
              <div v-else class="terminal-file-preview-empty">请选择文件预览</div>
            </section>
            <div
              class="terminal-file-splitter"
              role="separator"
              aria-label="调整文件预览高度"
              @mousedown="startTerminalFileResize('preview', $event)"
            ></div>
            <section class="terminal-transfer-panel">
              <header>
                <strong>文件传输</strong>
                <div>
                  <button type="button" title="暂停" aria-label="暂停">Ⅱ</button>
                  <button type="button" title="开始" aria-label="开始">▶</button>
                  <button type="button" title="清空" aria-label="清空"><AppIcon name="trash" :size="15" /></button>
                </div>
              </header>
              <div class="terminal-transfer-empty">
                <span>↔</span>
                <strong>无传输记录</strong>
              </div>
            </section>
            <div class="terminal-local-path">C:\Users\kaikai\Downloads</div>
          </div>
        </template>
      </div>
    </aside>
    <div
      class="terminal-sidebar-resizer"
      role="separator"
      aria-label="调整主机列表宽度"
      aria-orientation="vertical"
      @mousedown="startSidebarResize"
    ></div>

    <section class="terminal-workspace">
      <div class="terminal-hint">
        <span>{{ workspaceTitle }}</span>
        <div class="terminal-hint-actions">
          <strong v-if="workspaceStatus">{{ workspaceStatus }}</strong>
          <label class="terminal-highlight-toggle" title="关键词高亮">
            <input v-model="highlightEnabled" type="checkbox" />
            <span></span>
            <em>高亮</em>
          </label>
        </div>
      </div>
      <div class="terminal-tabs">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          type="button"
          class="terminal-tab"
          :class="{ active: tab.id === activeTabId, closed: tab.status === 'closed', error: tab.status === 'error' }"
          @click="activateTab(tab.id)"
        >
          <span class="terminal-tab-label">{{ tab.host.name }}</span>
          <span class="terminal-tab-status" :class="[tab.status, { unread: tab.hasUnreadOutput && tab.id !== activeTabId }]"></span>
          <span class="terminal-tab-close" title="关闭" @click.stop="closeTab(tab)"><AppIcon name="x" :size="13" /></span>
        </button>
      </div>
      <div class="terminal-screen">
        <div v-if="!tabs.length" class="terminal-empty">双击左侧主机名连接 SSH 终端。</div>
        <div
          v-for="tab in tabs"
          :key="tab.id"
          :ref="(element) => setTerminalContainer(tab.id, element)"
          class="terminal-panel"
          :class="{ active: tab.id === activeTabId }"
          :aria-hidden="tab.id !== activeTabId"
        ></div>
      </div>
    </section>
  </main>
</template>

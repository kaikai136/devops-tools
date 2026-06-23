<script setup lang="ts">
import { computed, markRaw, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { FitAddon } from '@xterm/addon-fit';
import { Terminal } from '@xterm/xterm';
import type { IDisposable } from '@xterm/xterm';
import '@xterm/xterm/css/xterm.css';

import { apiGet } from '../../api';
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

const ANSI_CONTROL_PATTERN = /\x1b\][^\x07]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]/g;
const ANSI_CONTROL_PREFIX_PATTERN = /^\x1b(?:\[[0-?]*[ -/]*)?$/;
const CONTROL_C = '\x03';
const MOUSE_SELECTION_INTERRUPT_SUPPRESSION_MS = 250;
const MOUSE_DOUBLE_CLICK_INTERRUPT_SUPPRESSION_MS = 1200;
const MAX_CONNECTING_TERMINALS = 2;
const TERMINAL_WORKSPACE_STORAGE_KEY = 'ops-tool.web-terminal.workspace';
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

const workspaceStatus = computed(() => {
  if (!activeTab.value) return '';
  if (activeTab.value.status === 'connecting') return '连接中...';
  if (activeTab.value.status === 'connected') return '已连接';
  if (activeTab.value.status === 'error') return '连接失败';
  return '已关闭';
});

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
  terminal.writeln('SPUG WEB TERMINAL');
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
</script>

<template>
  <main class="terminal-shell">
    <aside class="terminal-sidebar">
      <div class="terminal-brand">
        <strong>SPUG</strong>
      </div>
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
    </aside>

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

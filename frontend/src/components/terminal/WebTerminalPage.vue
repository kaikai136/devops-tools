<script setup lang="ts">
import { computed, markRaw, nextTick, onBeforeUnmount, onMounted, ref, watch, type ComponentPublicInstance } from 'vue';
import { FitAddon } from '@xterm/addon-fit';
import { SearchAddon, type ISearchOptions } from '@xterm/addon-search';
import { Terminal } from '@xterm/xterm';
import type { IBufferLine, IDisposable } from '@xterm/xterm';
import '@xterm/xterm/css/xterm.css';

import { ApiUnauthorizedError, apiDelete, apiGet, apiPost, apiPut } from '../../api';
import { AUTH_LOGOUT_EVENT_KEY } from '../../composables/app/useAuthSession';
import { getCurrentUser } from '../../services/auth';
import {
  TERMINAL_FONT_SIZE_DEFAULT,
  TERMINAL_FONT_SIZE_MAX,
  TERMINAL_FONT_SIZE_MIN,
  clampTerminalFontSize,
  readStoredTerminalFontSize,
} from '../../utils/terminalSettings';
import AppIcon from '../common/AppIcon.vue';
import type { IconName } from '../common/AppIcon.vue';
import type { AccountUser } from '../../types';

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
type TerminalSidebarMode = 'hosts' | 'files' | 'commands';
type TerminalSplitMode = 'single' | 'auto' | 'horizontal' | 'vertical';
type TerminalTransferKind = 'upload' | 'download';
type TerminalTransferStatus = 'queued' | 'running' | 'success' | 'error' | 'canceled';
type TerminalDownloadProtocol = 'auto' | 'scp' | 'sftp';
type TerminalTabColorId =
  | 'red'
  | 'orange'
  | 'amber'
  | 'yellow'
  | 'green'
  | 'emerald'
  | 'cyan'
  | 'sky'
  | 'blue'
  | 'violet'
  | 'pink'
  | 'rose';

interface TerminalTab {
  id: string;
  host: TerminalHost;
  customTitle: string;
  colorId: TerminalTabColorId | null;
  status: TerminalStatus;
  terminal: Terminal;
  fitAddon: FitAddon;
  searchAddon: SearchAddon;
  socket: WebSocket | null;
  sessionId: string | null;
  mounted: boolean;
  disposables: IDisposable[];
  resizeObserver: ResizeObserver | null;
  highlightState: TerminalHighlightState;
  suppressInterruptUntil: number;
  hasUnreadOutput: boolean;
  currentCwd: string;
  reconnectHintShown: boolean;
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
  type: 'ready' | 'output' | 'cwd' | 'error' | 'closed';
  sessionId?: string;
  data?: string;
  path?: string;
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

interface TerminalSearchMatch {
  row: number;
  col: number;
  size: number;
}

interface PersistedTerminalTab {
  id: string;
  hostId: number;
  title?: string;
  colorId?: TerminalTabColorId;
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
  permissions?: string;
  owner?: string;
  group?: string;
}

interface TerminalFileListResponse {
  path: string;
  protocol: string;
  entries: TerminalFileEntry[];
}

interface TerminalLocalWritableFile {
  write(data: Blob | Uint8Array): Promise<void>;
  close(): Promise<void>;
  abort?: () => Promise<void>;
}

interface TerminalLocalFileHandle {
  createWritable(): Promise<TerminalLocalWritableFile>;
}

interface TerminalLocalDirectoryHandle {
  getFileHandle(name: string, options?: { create?: boolean }): Promise<TerminalLocalFileHandle>;
  getDirectoryHandle(name: string, options?: { create?: boolean }): Promise<TerminalLocalDirectoryHandle>;
}

interface TerminalDirectoryPickerWindow extends Window {
  showDirectoryPicker?: (options?: { id?: string; mode?: 'read' | 'readwrite' }) => Promise<TerminalLocalDirectoryHandle>;
}

interface TerminalFileUploadItem {
  file: File;
  relativePath?: string;
}

interface TerminalFileSystemEntry {
  isFile: boolean;
  isDirectory: boolean;
  name: string;
  file?: (success: (file: File) => void, error?: (error: DOMException) => void) => void;
  createReader?: () => {
    readEntries(success: (entries: TerminalFileSystemEntry[]) => void, error?: (error: DOMException) => void): void;
  };
}

interface TerminalTransferRecord {
  id: string;
  kind: TerminalTransferKind;
  status: TerminalTransferStatus;
  name: string;
  path: string;
  currentFile: string;
  currentBytes: number;
  currentTotalBytes: number;
  completedFiles: number;
  totalFiles: number;
  progress: number;
  error: string;
  canceled: boolean;
  abortController: AbortController;
  createdAt: number;
  updatedAt: number;
}

interface TerminalMonitorResponse {
  system: {
    hostname: string;
    arch: string;
    os: string;
    kernel: string;
    uptimeSeconds: number;
  };
  cpu: {
    usagePercent: number;
    load1: number;
    load5: number;
    load15: number;
    cores: number;
  };
  memory: {
    totalBytes: number;
    usedBytes: number;
    availableBytes: number;
    cacheBytes: number;
    usagePercent: number;
  };
  network: Array<{
    name: string;
    rxBytesPerSecond: number;
    txBytesPerSecond: number;
  }>;
  disks: Array<{
    filesystem: string;
    type: string;
    mountpoint: string;
    totalBytes: number;
    usedBytes: number;
    availableBytes: number;
    usagePercent: number;
  }>;
}

interface TerminalQuickCommand {
  id: number;
  name: string;
  category: string;
  command: string;
  description: string;
  enabled: boolean;
  sortOrder: number;
  createdAt: string;
  updatedAt: string;
}

interface TerminalQuickCommandDraft {
  name: string;
  category: string;
  command: string;
  description: string;
  enabled: boolean;
  sortOrder: number;
}

interface TerminalQuickCommandDialogState {
  visible: boolean;
  mode: 'create' | 'edit';
  commandId: number | null;
  draft: TerminalQuickCommandDraft;
  saving: boolean;
  error: string;
}

interface TerminalFileProperties {
  name: string;
  path: string;
  directory: string;
  type: 'directory' | 'file';
  size: number;
  modifiedAt: string;
  accessedAt: string;
  owner: string;
  group: string;
  uid: number;
  gid: number;
  permissions: string;
  mode: number;
  octalMode: string;
  special: {
    setuid: boolean;
    setgid: boolean;
    sticky: boolean;
  };
}

interface TerminalFilePropertiesDraft {
  owner: string;
  group: string;
  octalMode: string;
}

interface TerminalFilePropertiesDialogState {
  visible: boolean;
  loading: boolean;
  saving: boolean;
  error: string;
  entry: TerminalFileEntry | null;
  properties: TerminalFileProperties | null;
  draft: TerminalFilePropertiesDraft;
  recursive: boolean;
}

interface TerminalFileContextMenuState {
  visible: boolean;
  x: number;
  y: number;
  entry: TerminalFileEntry | null;
}

interface TerminalFileContextMenuItem {
  id: string;
  label: string;
  icon: IconName;
  enabled: boolean;
  danger?: boolean;
  separatorBefore?: boolean;
  children?: TerminalFileContextMenuItem[];
  action: () => void | Promise<void>;
}

interface TerminalContextMenuState {
  visible: boolean;
  x: number;
  y: number;
  tabId: string | null;
  selectedText: string;
}

interface TerminalContextMenuItem {
  id: string;
  label: string;
  icon: IconName;
  enabled: boolean;
  danger?: boolean;
  selected?: boolean;
  swatchColor?: string;
  separatorBefore?: boolean;
  shortcut?: string;
  children?: TerminalContextMenuItem[];
  action: () => void | Promise<void>;
}

interface TerminalTabContextMenuState {
  visible: boolean;
  x: number;
  y: number;
  tabId: string | null;
}

interface TerminalTabColorOption {
  id: TerminalTabColorId;
  label: string;
  swatch: string;
  background: string;
  color: string;
  border: string;
  activeBackground: string;
  activeColor: string;
  activeBorder: string;
}

interface TerminalSplitModeOption {
  mode: TerminalSplitMode;
  label: string;
  icon: IconName;
}

interface TerminalFileRenameState {
  path: string;
  originalName: string;
  draftName: string;
  saving: boolean;
  error: string;
}

interface TerminalFileDeleteDialogState {
  visible: boolean;
  entry: TerminalFileEntry | null;
  entries: TerminalFileEntry[];
  deleting: boolean;
  error: string;
}

interface TerminalFileMarqueeState {
  active: boolean;
  startX: number;
  startY: number;
  currentX: number;
  currentY: number;
  additive: boolean;
  basePaths: string[];
}

type TerminalFileCreateMode = 'file' | 'directory' | 'symlink';

interface TerminalFileCreateDialogState {
  visible: boolean;
  mode: TerminalFileCreateMode;
  name: string;
  targetPath: string;
  octalMode: string;
  openAfterCreate: boolean;
  saving: boolean;
  error: string;
}

const ANSI_CONTROL_PATTERN = /\x1b\][^\x07]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]/g;
const ANSI_CONTROL_PREFIX_PATTERN = /^\x1b(?:\[[0-?]*[ -/]*)?$/;
const CONTROL_C = '\x03';
const MOUSE_SELECTION_INTERRUPT_SUPPRESSION_MS = 250;
const MOUSE_DOUBLE_CLICK_INTERRUPT_SUPPRESSION_MS = 1200;
const MAX_CONNECTING_TERMINALS = 2;
const TERMINAL_WORKSPACE_STORAGE_KEY = 'ops-tool.web-terminal.workspace';
const TERMINAL_SIDEBAR_WIDTH_STORAGE_KEY = 'ops-tool.web-terminal.sidebar-width';
const TERMINAL_SIDEBAR_COLLAPSED_STORAGE_KEY = 'ops-tool.web-terminal.sidebar-collapsed';
const TERMINAL_FONT_SIZE_STORAGE_KEY = 'ops-tool.web-terminal.font-size';
const TERMINAL_SPLIT_MODE_STORAGE_KEY = 'ops-tool.web-terminal.split-mode';
const TERMINAL_SIDEBAR_DEFAULT_WIDTH = 284;
const TERMINAL_SIDEBAR_MIN_WIDTH = 200;
const TERMINAL_WORKSPACE_MIN_WIDTH = 360;
const TERMINAL_FILE_CONTEXT_MENU_WIDTH = 220;
const TERMINAL_FILE_CONTEXT_MENU_HEIGHT = 540;
const TERMINAL_DIRECTORY_CONTEXT_MENU_HEIGHT = 300;
const TERMINAL_CONTEXT_MENU_WIDTH = 248;
const TERMINAL_CONTEXT_MENU_HEIGHT = 560;
const TERMINAL_TAB_CONTEXT_MENU_WIDTH = 252;
const TERMINAL_TAB_CONTEXT_MENU_HEIGHT = 560;
const TERMINAL_TAB_TITLE_MAX_LENGTH = 40;
const TERMINAL_MONITOR_REFRESH_MS = 5000;
const TERMINAL_TRANSFER_PANEL_DEFAULT_HEIGHT = 170;
const TERMINAL_TRANSFER_PANEL_MIN_HEIGHT = 96;
const TERMINAL_TRANSFER_PANEL_MAX_HEIGHT = 360;
const TERMINAL_QUICK_COMMAND_PANEL_HEIGHT_STORAGE_KEY = 'ops-tool.web-terminal.quick-command-panel-height';
const TERMINAL_QUICK_COMMAND_PANEL_COLLAPSED_STORAGE_KEY = 'ops-tool.web-terminal.quick-command-panel-collapsed';
const TERMINAL_QUICK_COMMAND_PANEL_DEFAULT_HEIGHT = 260;
const TERMINAL_QUICK_COMMAND_PANEL_MIN_HEIGHT = 160;
const TERMINAL_QUICK_COMMAND_PANEL_MAX_HEIGHT = 420;
const TERMINAL_DOWNLOAD_FILE_CONCURRENCY = 1;
const TERMINAL_DOWNLOAD_DIRECTORY_PICKER_ID = 'terminal-download-directory';
const TERMINAL_SEARCH_DECORATIONS: NonNullable<ISearchOptions['decorations']> = {
  matchBackground: '#7c3aed',
  matchBorder: '#c084fc',
  matchOverviewRuler: '#a855f7',
  activeMatchBackground: '#a21caf',
  activeMatchBorder: '#f0abfc',
  activeMatchColorOverviewRuler: '#d946ef',
};
const TERMINAL_LOCAL_FILENAME_RESERVED_CHARS = /[<>:"/\\|?*\x00-\x1f]/g;
const TERMINAL_LOCAL_FILENAME_RESERVED_NAMES = new Set([
  'CON',
  'PRN',
  'AUX',
  'NUL',
  'COM1',
  'COM2',
  'COM3',
  'COM4',
  'COM5',
  'COM6',
  'COM7',
  'COM8',
  'COM9',
  'LPT1',
  'LPT2',
  'LPT3',
  'LPT4',
  'LPT5',
  'LPT6',
  'LPT7',
  'LPT8',
  'LPT9',
]);
const terminalTabColorOptions: TerminalTabColorOption[] = [
  {
    id: 'red',
    label: '红色',
    swatch: '#ef4444',
    background: '#fff1f2',
    color: '#991b1b',
    border: '#f87171',
    activeBackground: '#dc2626',
    activeColor: '#ffffff',
    activeBorder: '#ef4444',
  },
  {
    id: 'orange',
    label: '橙色',
    swatch: '#f97316',
    background: '#fff7ed',
    color: '#9a3412',
    border: '#fb923c',
    activeBackground: '#ea580c',
    activeColor: '#ffffff',
    activeBorder: '#f97316',
  },
  {
    id: 'amber',
    label: '琥珀',
    swatch: '#f59e0b',
    background: '#fffbeb',
    color: '#92400e',
    border: '#fbbf24',
    activeBackground: '#d97706',
    activeColor: '#ffffff',
    activeBorder: '#f59e0b',
  },
  {
    id: 'yellow',
    label: '黄色',
    swatch: '#eab308',
    background: '#fefce8',
    color: '#854d0e',
    border: '#facc15',
    activeBackground: '#ca8a04',
    activeColor: '#ffffff',
    activeBorder: '#eab308',
  },
  {
    id: 'green',
    label: '绿色',
    swatch: '#22c55e',
    background: '#f0fdf4',
    color: '#166534',
    border: '#4ade80',
    activeBackground: '#16a34a',
    activeColor: '#ffffff',
    activeBorder: '#22c55e',
  },
  {
    id: 'emerald',
    label: '翡翠',
    swatch: '#10b981',
    background: '#ecfdf5',
    color: '#065f46',
    border: '#34d399',
    activeBackground: '#059669',
    activeColor: '#ffffff',
    activeBorder: '#10b981',
  },
  {
    id: 'cyan',
    label: '青色',
    swatch: '#06b6d4',
    background: '#ecfeff',
    color: '#155e75',
    border: '#22d3ee',
    activeBackground: '#0891b2',
    activeColor: '#ffffff',
    activeBorder: '#06b6d4',
  },
  {
    id: 'sky',
    label: '天蓝',
    swatch: '#0ea5e9',
    background: '#f0f9ff',
    color: '#075985',
    border: '#38bdf8',
    activeBackground: '#0284c7',
    activeColor: '#ffffff',
    activeBorder: '#0ea5e9',
  },
  {
    id: 'blue',
    label: '蓝色',
    swatch: '#3b82f6',
    background: '#eff6ff',
    color: '#1e40af',
    border: '#60a5fa',
    activeBackground: '#2563eb',
    activeColor: '#ffffff',
    activeBorder: '#3b82f6',
  },
  {
    id: 'violet',
    label: '紫色',
    swatch: '#8b5cf6',
    background: '#f5f3ff',
    color: '#5b21b6',
    border: '#a78bfa',
    activeBackground: '#7c3aed',
    activeColor: '#ffffff',
    activeBorder: '#8b5cf6',
  },
  {
    id: 'pink',
    label: '粉色',
    swatch: '#ec4899',
    background: '#fdf2f8',
    color: '#9d174d',
    border: '#f472b6',
    activeBackground: '#db2777',
    activeColor: '#ffffff',
    activeBorder: '#ec4899',
  },
  {
    id: 'rose',
    label: '玫红',
    swatch: '#f43f5e',
    background: '#fff1f2',
    color: '#9f1239',
    border: '#fb7185',
    activeBackground: '#e11d48',
    activeColor: '#ffffff',
    activeBorder: '#f43f5e',
  },
];
const terminalTabColorOptionMap = new Map<TerminalTabColorId, TerminalTabColorOption>(
  terminalTabColorOptions.map((option) => [option.id, option]),
);
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
const terminalSplitModeOptions: TerminalSplitModeOption[] = [
  { mode: 'single', label: '单屏模式', icon: 'maximize' },
  { mode: 'auto', label: '自动平铺所有会话', icon: 'dashboard' },
  { mode: 'horizontal', label: '水平平铺', icon: 'rows' },
  { mode: 'vertical', label: '垂直平铺', icon: 'panelLeft' },
];
const initialTerminalFileEntries: TerminalFileEntry[] = [
  { name: '..', type: 'directory', modifiedAt: '', path: '..', permissions: '', owner: '', group: '' },
  { name: '.ansible', type: 'directory', modifiedAt: '2025/03/11 13:20', path: '~/.ansible', permissions: 'drwx------', owner: 'root', group: 'root' },
  { name: '.cache', type: 'directory', modifiedAt: '2025/05/07 17:53', path: '~/.cache', permissions: 'drwxr-xr-x', owner: 'root', group: 'root' },
  { name: '.config', type: 'directory', modifiedAt: '2025/05/07 16:47', path: '~/.config', permissions: 'drwx------', owner: 'root', group: 'root' },
  { name: '.ctcss', type: 'directory', modifiedAt: '2025/08/01 11:23', path: '~/.ctcss', permissions: 'd---------', owner: 'root', group: 'root' },
  { name: '.docker', type: 'directory', modifiedAt: '2026/01/20 20:58', path: '~/.docker', permissions: 'drwx------', owner: 'root', group: 'root' },
  { name: '.ssh', type: 'directory', modifiedAt: '2025/03/11 20:58', path: '~/.ssh', permissions: 'drwx------', owner: 'root', group: 'root' },
  { name: '.vim', type: 'directory', modifiedAt: '2026/04/10 17:15', path: '~/.vim', permissions: 'drwxr-xr-x', owner: 'root', group: 'root' },
  { name: 'download_test', type: 'directory', modifiedAt: '2026/01/14 19:03', path: '~/download_test', permissions: 'drwxr-xr-x', owner: 'root', group: 'root' },
  { name: '.bash_history', type: 'file', modifiedAt: '2026/05/25 11:07', path: '~/.bash_history', size: 39200, permissions: '-rw-------', owner: 'root', group: 'root' },
  { name: '.bashrc', type: 'file', modifiedAt: '2019/12/05 13:37', path: '~/.bashrc', size: 241, permissions: '-rw-r--r--', owner: 'root', group: 'root' },
  { name: '.lesshst', type: 'file', modifiedAt: '2025/10/15 16:48', path: '~/.lesshst', size: 1200, permissions: '-rw-------', owner: 'root', group: 'root' },
];

const initialSelectedTerminalFile = initialTerminalFileEntries.find((entry) => entry.type === 'file') ?? null;
const terminalFileEntries = ref<TerminalFileEntry[]>(initialTerminalFileEntries);
const selectedTerminalFile = ref<TerminalFileEntry | null>(initialSelectedTerminalFile);
const selectedTerminalFilePaths = ref<Set<string>>(new Set(initialSelectedTerminalFile ? [initialSelectedTerminalFile.path] : []));
const terminalFileSelectionAnchorPath = ref(initialSelectedTerminalFile?.path ?? '');
const terminalFilePath = ref('.');
const terminalFileListProtocol = ref('');
const terminalFileListError = ref('');
const isTerminalFileFollowingCwd = ref(false);
const isTerminalFileListLoading = ref(false);
const terminalFileListRef = ref<HTMLElement | null>(null);
const terminalFileUploadInput = ref<HTMLInputElement | null>(null);
const terminalFolderUploadInput = ref<HTMLInputElement | null>(null);
const terminalFileRenameInput = ref<HTMLInputElement | null>(null);
const terminalFileBrowserRef = ref<HTMLElement | null>(null);
const terminalFileContextMenu = ref<TerminalFileContextMenuState>({
  visible: false,
  x: 0,
  y: 0,
  entry: null,
});
const terminalDirectoryContextMenu = ref<Omit<TerminalFileContextMenuState, 'entry'>>({
  visible: false,
  x: 0,
  y: 0,
});
const terminalContextMenu = ref<TerminalContextMenuState>({
  visible: false,
  x: 0,
  y: 0,
  tabId: null,
  selectedText: '',
});
const terminalTabContextMenu = ref<TerminalTabContextMenuState>({
  visible: false,
  x: 0,
  y: 0,
  tabId: null,
});
const terminalFileRename = ref<TerminalFileRenameState | null>(null);
const terminalFileDeleteDialog = ref<TerminalFileDeleteDialogState>({
  visible: false,
  entry: null,
  entries: [],
  deleting: false,
  error: '',
});
const isTerminalFileDragOver = ref(false);
const terminalFileMarquee = ref<TerminalFileMarqueeState>({
  active: false,
  startX: 0,
  startY: 0,
  currentX: 0,
  currentY: 0,
  additive: false,
  basePaths: [],
});
let shouldSuppressTerminalFileClick = false;
const terminalTransferRecords = ref<TerminalTransferRecord[]>([]);
const terminalDownloadProtocol = ref<TerminalDownloadProtocol>('auto');
const terminalTransferPanelHeight = ref(TERMINAL_TRANSFER_PANEL_DEFAULT_HEIGHT);
const isTerminalTransferPanelResizing = ref(false);
let terminalTransferResizeStartY = 0;
let terminalTransferResizeStartHeight = TERMINAL_TRANSFER_PANEL_DEFAULT_HEIGHT;
const terminalFileCreateDialog = ref<TerminalFileCreateDialogState>({
  visible: false,
  mode: 'file',
  name: '',
  targetPath: '',
  octalMode: '0644',
  openAfterCreate: false,
  saving: false,
  error: '',
});
const terminalFilePropertiesDialog = ref<TerminalFilePropertiesDialogState>({
  visible: false,
  loading: false,
  saving: false,
  error: '',
  entry: null,
  properties: null,
  draft: { owner: '', group: '', octalMode: '0000' },
  recursive: false,
});
let terminalFileListRequestId = 0;
const terminalMonitorData = ref<TerminalMonitorResponse | null>(null);
const isTerminalMonitorLoading = ref(false);
const terminalMonitorError = ref('');
const isTerminalMonitorPanelOpen = ref(false);
let terminalMonitorRequestId = 0;
let terminalMonitorTimer: ReturnType<typeof window.setInterval> | null = null;
const terminalQuickCommands = ref<TerminalQuickCommand[]>([]);
const terminalQuickCommandCategory = ref('all');
const terminalQuickCommandSearch = ref('');
const isTerminalQuickCommandLoading = ref(false);
const terminalQuickCommandError = ref('');
const terminalQuickCommandPanelHeight = ref(readTerminalQuickCommandPanelHeight());
const isTerminalQuickCommandPanelCollapsed = ref(readTerminalQuickCommandPanelCollapsed());
const isTerminalQuickCommandPanelResizing = ref(false);
const terminalQuickCommandDialog = ref<TerminalQuickCommandDialogState>({
  visible: false,
  mode: 'create',
  commandId: null,
  draft: createTerminalQuickCommandDraft(),
  saving: false,
  error: '',
});
const terminalCurrentUser = ref<AccountUser | null>(null);
let terminalQuickCommandResizeStartY = 0;
let terminalQuickCommandResizeStartHeight = TERMINAL_QUICK_COMMAND_PANEL_DEFAULT_HEIGHT;

const groups = ref<TerminalGroup[]>([]);
const collapsed = ref<Set<number>>(new Set());
const rootExpanded = ref(true);
const rootLabel = ref(readTerminalRootLabel());
const search = ref('');
const tabs = ref<TerminalTab[]>([]);
const activeTabId = ref<string | null>(null);
const isTerminalTabMenuOpen = ref(false);
const isTerminalSplitMenuOpen = ref(false);
const isTerminalMultiExecutionEnabled = ref(false);
const multiExecutionExcludedTabIds = ref<Set<string>>(new Set());
const isTerminalSearchOpen = ref(false);
const terminalSearchQuery = ref('');
const terminalSearchResultIndex = ref(-1);
const terminalSearchResultCount = ref(0);
const terminalSearchInputRef = ref<HTMLInputElement | null>(null);
const terminalTabsRef = ref<HTMLElement | null>(null);
const canScrollTerminalTabsLeft = ref(false);
const canScrollTerminalTabsRight = ref(false);
const isLoadingTree = ref(false);
const treeError = ref('');
const highlightEnabled = ref(false);
const terminalFontSize = ref(readTerminalFontSize());
const terminalSplitMode = ref<TerminalSplitMode>(readTerminalSplitMode());
const terminalSidebarMode = ref<TerminalSidebarMode>('hosts');
const sidebarWidth = ref(readTerminalSidebarWidth());
const isTerminalSidebarCollapsed = ref(readTerminalSidebarCollapsed());
const isResizingSidebar = ref(false);
let sidebarResizeStartX = 0;
let sidebarResizeStartWidth = TERMINAL_SIDEBAR_DEFAULT_WIDTH;
const terminalContainers = new Map<string, HTMLElement>();
const pendingConnectTabIds: string[] = [];
const connectingTabIds = new Set<string>();
let terminalAuthRedirecting = false;

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
const connectedTerminalTabs = computed(() => tabs.value.filter((tab) => tab.status === 'connected'));
const isTerminalSplitActive = computed(
  () => terminalSplitMode.value !== 'single' && connectedTerminalTabs.value.length >= 2 && activeTab.value?.status === 'connected',
);
const visibleTerminalTabs = computed(() => (isTerminalSplitActive.value ? connectedTerminalTabs.value : activeTab.value ? [activeTab.value] : []));
const terminalSplitModeLabel = computed(
  () => terminalSplitModeOptions.find((option) => option.mode === terminalSplitMode.value)?.label ?? '单屏模式',
);
const terminalScreenStyle = computed<Record<string, string>>(() => {
  if (!isTerminalSplitActive.value) return {} as Record<string, string>;
  const count = visibleTerminalTabs.value.length;
  const columns =
    terminalSplitMode.value === 'horizontal'
      ? 1
      : terminalSplitMode.value === 'vertical'
        ? count
        : Math.ceil(Math.sqrt(count));
  const rows = terminalSplitMode.value === 'vertical' ? 1 : Math.ceil(count / columns);
  return {
    '--terminal-split-columns': String(columns),
    '--terminal-split-rows': String(rows),
  };
});
const activeTerminalNodeName = computed(() => activeTab.value?.host.name ?? '未选择主机');
const terminalSidebarToggleLabel = computed(() => (isTerminalSidebarCollapsed.value ? '展开侧栏' : '收起侧栏'));
const selectedTerminalFiles = computed(() =>
  terminalFileEntries.value.filter((entry) => selectedTerminalFilePaths.value.has(entry.path) && !isParentDirectoryEntry(entry)),
);
const selectedTerminalDownloadableEntries = computed(() => selectedTerminalFiles.value);
const selectedTerminalFileCount = computed(() => selectedTerminalFiles.value.length);
const canDownloadSelectedTerminalFiles = computed(() => selectedTerminalDownloadableEntries.value.length > 0);
const terminalFileSelectionStatusText = computed(() => {
  const total = terminalFileEntries.value.length;
  return selectedTerminalFileCount.value > 1 ? `已选 ${selectedTerminalFileCount.value} 项 / 共 ${total} 项` : `共 ${total} 项`;
});
const terminalFileMarqueeStyle = computed<Record<string, string>>(() => {
  const state = terminalFileMarquee.value;
  if (!state.active) return {} as Record<string, string>;
  const left = Math.min(state.startX, state.currentX);
  const top = Math.min(state.startY, state.currentY);
  return {
    left: `${left}px`,
    top: `${top}px`,
    width: `${Math.abs(state.currentX - state.startX)}px`,
    height: `${Math.abs(state.currentY - state.startY)}px`,
  };
});
const terminalTransferPanelStyle = computed<Record<string, string>>(() => ({
  '--terminal-transfer-height': `${terminalTransferPanelHeight.value}px`,
}));
const hasRunningTerminalTransfers = computed(() => terminalTransferRecords.value.some((record) => isTerminalTransferActive(record)));
const hasClearableTerminalTransfers = computed(() => terminalTransferRecords.value.some((record) => !isTerminalTransferActive(record)));
const terminalFileProtocolLabel = computed(() => formatTerminalFileProtocol(terminalFileListProtocol.value));
const terminalFileStatus = computed<'idle' | 'loading' | 'success' | 'error'>(() => {
  if (isTerminalFileListLoading.value) return 'loading';
  if (terminalFileListError.value) return 'error';
  if (terminalFileListProtocol.value) return 'success';
  return 'idle';
});
const terminalFileStatusText = computed(() => {
  if (terminalFileStatus.value === 'loading') return '读取中';
  if (terminalFileStatus.value === 'error') return '读取失败';
  if (terminalFileStatus.value === 'success') return terminalFileProtocolLabel.value;
  return '待加载';
});
const terminalFileFollowCwdLabel = computed(() => (isTerminalFileFollowingCwd.value ? '停止跟踪终端目录' : '跟踪终端目录'));
const terminalMonitorNodeName = computed(() => activeTab.value?.host.name ?? '请选择服务器');
const terminalQuickCommandCategories = computed(() => {
  const categories = terminalQuickCommands.value.map((command) => command.category).filter(Boolean);
  return [...new Set(categories)].sort((left, right) => left.localeCompare(right, 'zh-Hans-CN'));
});
const filteredTerminalQuickCommands = computed(() => {
  const query = terminalQuickCommandSearch.value.trim().toLowerCase();
  return terminalQuickCommands.value.filter((command) => {
    const matchesCategory = terminalQuickCommandCategory.value === 'all' || command.category === terminalQuickCommandCategory.value;
    if (!matchesCategory) return false;
    if (!query) return true;
    return [command.name, command.category, command.command, command.description]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query));
  });
});
const activeTerminalReady = computed(() => activeTab.value?.status === 'connected' && activeTab.value.socket?.readyState === WebSocket.OPEN);
const terminalSearchResultText = computed(() => {
  if (!terminalSearchQuery.value.trim()) return '';
  if (terminalSearchResultCount.value <= 0) return '0';
  if (terminalSearchResultIndex.value < 0) return String(terminalSearchResultCount.value);
  return `${terminalSearchResultIndex.value + 1}/${terminalSearchResultCount.value}`;
});
const terminalMultiExecutionTargets = computed(() =>
  tabs.value.filter((tab) => isTerminalTabReady(tab) && !multiExecutionExcludedTabIds.value.has(tab.id)),
);
const terminalMultiExecutionTargetCount = computed(() => terminalMultiExecutionTargets.value.length);
const hasTerminalMultiExecutionCandidates = computed(() => tabs.value.some((tab) => isTerminalTabReady(tab)));
const canSendToTerminalMultiExecutionTargets = computed(
  () => isTerminalMultiExecutionEnabled.value && terminalMultiExecutionTargetCount.value > 0,
);
const terminalQuickCommandReady = computed(() =>
  isTerminalMultiExecutionEnabled.value ? canSendToTerminalMultiExecutionTargets.value : activeTerminalReady.value,
);
const canDecreaseTerminalFontSize = computed(() => terminalFontSize.value > TERMINAL_FONT_SIZE_MIN);
const canIncreaseTerminalFontSize = computed(() => terminalFontSize.value < TERMINAL_FONT_SIZE_MAX);
const canUseTerminalQuickCommands = computed(() => {
  const user = terminalCurrentUser.value;
  if (!user) return false;
  if (user.is_superuser || user.is_staff) return true;
  return (user.featurePermissionCodes ?? []).includes('action_hosts_quick_commands');
});
const shouldShowTerminalQuickCommandPanel = computed(() => canUseTerminalQuickCommands.value && terminalQuickCommands.value.length > 0);
const terminalQuickCommandPanelStyle = computed<Record<string, string>>(() => ({
  '--terminal-quick-command-height':
    !shouldShowTerminalQuickCommandPanel.value || isTerminalQuickCommandPanelCollapsed.value ? '0px' : `${terminalQuickCommandPanelHeight.value}px`,
}));
const terminalFileContextMenuItems = computed<TerminalFileContextMenuItem[]>(() => {
  const entry = terminalFileContextMenu.value.entry;
  const targetEntries = getTerminalFileActionEntries(entry);
  const isMultiple = targetEntries.length > 1;
  const isSingle = targetEntries.length === 1;
  const hasEntry = Boolean(entry);
  const isParent = isParentDirectoryEntry(entry);
  const isDirectory = entry?.type === 'directory';
  const path = entry ? getTerminalFileResolvedPath(entry) : '';
  const name = entry?.name ?? '';
  const directoryPath = entry ? getTerminalFileDirectoryPath(entry) : '';
  const targetPathsText = targetEntries.map((item) => getTerminalFileResolvedPath(item)).join('\n');
  const targetNamesText = targetEntries.map((item) => item.name).join('\n');
  const canDownload = targetEntries.length > 0;

  const items: TerminalFileContextMenuItem[] = [
    { id: 'open', label: '打开', icon: 'folder', enabled: Boolean(isDirectory) && (isSingle || isParent), action: () => { if (entry) openTerminalDirectory(entry); } },
    { id: 'refresh', label: '刷新', icon: 'refresh', enabled: true, action: () => loadTerminalDirectory() },
    { id: 'upload', label: '上传到当前文件夹...', icon: 'upload', enabled: hasEntry && !isParent, action: () => openTerminalUpload() },
    { id: 'download', label: isMultiple ? '下载所选到目录...' : '下载到目录...', icon: 'download', enabled: canDownload, action: () => downloadTerminalFiles(targetEntries) },
    { id: 'rename', label: '重命名...', icon: 'edit', enabled: false, separatorBefore: true, action: () => undefined },
    { id: 'move', label: '移动到...', icon: 'moveRight', enabled: false, action: () => undefined },
    { id: 'delete', label: isMultiple ? '删除所选' : '删除', icon: 'trash', enabled: false, danger: true, action: () => undefined },
    { id: 'favorite', label: '添加到收藏夹', icon: 'bookmark', enabled: false, separatorBefore: true, action: () => undefined },
    { id: 'copy-path', label: isMultiple ? '复制所选路径' : '复制路径', icon: 'copy', enabled: targetEntries.length > 0 || hasEntry, separatorBefore: true, action: () => copyTerminalFileText(targetEntries.length > 0 ? targetPathsText : path) },
    { id: 'copy-name', label: isMultiple ? '复制所选名称' : '复制名称', icon: 'copy', enabled: targetEntries.length > 0, action: () => copyTerminalFileText(isMultiple ? targetNamesText : name) },
    { id: 'copy-directory', label: '复制目录路径', icon: 'folder', enabled: hasEntry && !isParent, action: () => copyTerminalFileText(directoryPath) },
    { id: 'send-path', label: isMultiple ? '将所选路径发送到终端' : '将路径发送到终端', icon: 'cornerDownLeft', enabled: targetEntries.length > 0 || hasEntry, separatorBefore: true, action: () => sendTerminalFileTextToActiveTerminal(targetEntries.length > 0 ? targetPathsText : path) },
    { id: 'send-name', label: isMultiple ? '将所选名称发送到终端' : '将名称发送到终端', icon: 'chevronRight', enabled: targetEntries.length > 0, action: () => sendTerminalFileTextToActiveTerminal(isMultiple ? targetNamesText : name) },
    { id: 'send-directory', label: '将目录路径发送到终端', icon: 'chevronsRight', enabled: hasEntry && !isParent, action: () => sendTerminalFileTextToActiveTerminal(directoryPath) },
    { id: 'properties', label: '属性...', icon: 'info', enabled: hasEntry && !isParent && isSingle, separatorBefore: true, action: async () => { if (entry) await openTerminalFileProperties(entry); } },
  ];
  return items.map((item) => {
    if (item.id === 'rename') {
      return { ...item, enabled: hasEntry && !isParent && isSingle, action: () => { if (entry) startTerminalFileRename(entry); } };
    }
    if (item.id === 'delete') {
      return { ...item, enabled: targetEntries.length > 0, action: () => openTerminalFileDeleteDialog(targetEntries) };
    }
    return item;
  });
});
const terminalDirectoryContextMenuItems = computed<TerminalFileContextMenuItem[]>(() => [
  { id: 'refresh', label: '刷新', icon: 'refresh', enabled: Boolean(activeTab.value), action: () => loadTerminalDirectory() },
  {
    id: 'upload',
    label: '上传到当前文件夹...',
    icon: 'upload',
    enabled: Boolean(activeTab.value),
    action: () => undefined,
    children: [
      { id: 'upload-file', label: '上传文件', icon: 'file', enabled: Boolean(activeTab.value), action: () => openTerminalUpload() },
      { id: 'upload-folder', label: '上传文件夹', icon: 'folder', enabled: Boolean(activeTab.value), action: () => openTerminalFolderUpload() },
    ],
  },
  { id: 'create-file', label: '新建文件', icon: 'file', enabled: Boolean(activeTab.value), separatorBefore: true, action: () => openTerminalFileCreateDialog('file') },
  { id: 'create-directory', label: '新建文件夹', icon: 'folderPlus', enabled: Boolean(activeTab.value), action: () => openTerminalFileCreateDialog('directory') },
  { id: 'create-symlink', label: '新建符号链接', icon: 'link', enabled: Boolean(activeTab.value), action: () => openTerminalFileCreateDialog('symlink') },
  { id: 'copy-directory', label: '复制目录路径', icon: 'copy', enabled: Boolean(activeTab.value), separatorBefore: true, action: () => copyTerminalFileText(terminalFilePath.value) },
  { id: 'send-directory', label: '将目录路径发送到终端', icon: 'cornerDownLeft', enabled: Boolean(activeTab.value), action: () => sendTerminalFileTextToActiveTerminal(terminalFilePath.value) },
  { id: 'properties', label: '属性', icon: 'info', enabled: Boolean(activeTab.value), separatorBefore: true, action: () => openTerminalCurrentDirectoryProperties() },
]);
const terminalContextMenuItems = computed<TerminalContextMenuItem[]>(() => {
  const tab = getTerminalContextMenuTab();
  const selectedText = terminalContextMenu.value.selectedText.trim();
  const hasSelection = Boolean(selectedText);
  const isReady = Boolean(tab && isTerminalTabReady(tab));
  const items: TerminalContextMenuItem[] = [];

  if (hasSelection) {
    items.push(
      { id: 'copy-selection', label: '复制', icon: 'copy', enabled: true, shortcut: 'Ctrl+Shift+C', action: () => copyTerminalContextText(selectedText) },
      { id: 'find-selection', label: '查找选中内容', icon: 'search', enabled: true, shortcut: 'Ctrl+Shift+F', action: () => findTerminalText(selectedText) },
      {
        id: 'online-search',
        label: '在线搜索',
        icon: 'globe',
        enabled: true,
        action: () => undefined,
        children: [
          { id: 'search-selection', label: '搜索选中内容', icon: 'search', enabled: true, action: () => openTerminalOnlineSearch(selectedText) },
          { id: 'search-error', label: '搜索报错关键词', icon: 'alert', enabled: true, action: () => openTerminalOnlineSearch(`${selectedText} linux error`) },
          { id: 'search-command', label: '搜索命令用法', icon: 'terminal', enabled: true, action: () => openTerminalOnlineSearch(`${selectedText} linux command usage`) },
        ],
      },
      {
        id: 'ai',
        label: 'AI',
        icon: 'zap',
        enabled: true,
        action: () => undefined,
        children: [
          { id: 'ai-explain', label: '解释选中内容', icon: 'circleHelp', enabled: false, action: () => undefined },
          { id: 'ai-error', label: '分析错误原因', icon: 'alert', enabled: false, action: () => undefined },
          { id: 'ai-fix', label: '生成修复建议', icon: 'settings', enabled: false, action: () => undefined },
          { id: 'ai-summary', label: '总结这段输出', icon: 'file', enabled: false, action: () => undefined },
        ],
      },
      {
        id: 'translate',
        label: '翻译',
        icon: 'globe',
        enabled: true,
        action: () => undefined,
        children: [
          { id: 'translate-zh', label: '翻译为中文', icon: 'globe', enabled: true, action: () => openTerminalTranslation(selectedText, 'zh-Hans') },
          { id: 'translate-en', label: '翻译为英文', icon: 'globe', enabled: true, action: () => openTerminalTranslation(selectedText, 'en') },
        ],
      },
      { id: 'paste-selection', label: '粘贴选定文本到终端', icon: 'clipboard', enabled: isReady, separatorBefore: true, action: () => sendTextToTerminal(selectedText, tab) },
      { id: 'paste-selection-single-line', label: '粘贴为单行', icon: 'cornerDownLeft', enabled: isReady, action: () => sendTextToTerminal(toSingleLineTerminalText(selectedText), tab) },
      { id: 'save-selection-command', label: '保存为快捷命令...', icon: 'bookmark', enabled: canUseTerminalQuickCommands.value, action: () => openTerminalQuickCommandDialogFromText(selectedText) },
    );
  } else {
    items.push(
      { id: 'paste', label: '粘贴', icon: 'clipboard', enabled: isReady, shortcut: 'Ctrl+Shift+V', action: () => pasteClipboardToTerminal(tab) },
      { id: 'find', label: '查找...', icon: 'search', enabled: true, shortcut: 'Ctrl+Shift+F', action: () => promptFindTerminalText() },
      {
        id: 'quick-commands',
        label: '快捷命令',
        icon: 'zap',
        enabled: canUseTerminalQuickCommands.value,
        action: () => undefined,
        children: getTerminalQuickCommandContextItems(tab),
      },
    );
  }

  return [
    ...items,
    getTerminalSessionContextMenu(tab),
    getTerminalControlKeyContextMenu(tab),
    getTerminalViewContextMenu(tab),
    getTerminalBufferContextMenu(tab),
  ];
});

const terminalTabContextMenuItems = computed<TerminalContextMenuItem[]>(() => {
  const tab = getTerminalTabContextMenuTab();
  const hasTab = Boolean(tab);
  const serverIp = tab ? getTerminalServerIp(tab) : '';
  const rightSideTabs = tab ? getTerminalTabsRightOf(tab) : [];
  const hasInactiveTabs = Boolean(tab && tabs.value.some((item) => item.id !== tab.id));

  return [
    {
      id: 'tab-color',
      label: '设置标签页颜色',
      icon: 'palette',
      enabled: hasTab,
      action: () => undefined,
      children: [
        ...terminalTabColorOptions.map<TerminalContextMenuItem>((option) => ({
          id: `tab-color-${option.id}`,
          label: option.label,
          icon: 'palette',
          enabled: hasTab,
          selected: tab?.colorId === option.id,
          swatchColor: option.swatch,
          action: () => {
            if (tab) setTerminalTabColor(tab, option.id);
          },
        })),
        {
          id: 'tab-color-reset',
          label: '恢复默认颜色',
          icon: 'reset',
          enabled: Boolean(tab?.colorId),
          selected: Boolean(tab && !tab.colorId),
          separatorBefore: true,
          action: () => {
            if (tab) setTerminalTabColor(tab, null);
          },
        },
      ],
    },
    { id: 'tab-rename', label: '重命名标签名称', icon: 'edit', enabled: hasTab, action: () => { if (tab) renameTerminalTab(tab); } },
    { id: 'tab-copy-name', label: '复制标签名称', icon: 'copy', enabled: hasTab, action: async () => { if (tab) await copyTerminalContextText(getTerminalTabLabel(tab)); } },
    { id: 'tab-copy-ip', label: '复制服务器 IP', icon: 'copy', enabled: Boolean(serverIp), action: () => copyTerminalContextText(serverIp) },
    {
      id: 'tab-copy-session',
      label: '复制会话信息',
      icon: 'copy',
      enabled: hasTab,
      separatorBefore: true,
      action: async () => {
        if (tab) await copyTerminalContextText(getTerminalSessionInfo(tab));
      },
    },
    { id: 'tab-duplicate', label: '新建同主机标签', icon: 'plus', enabled: hasTab, action: async () => { if (tab) await openHostTab(tab.host); } },
    {
      id: 'tab-quick-commands',
      label: '快捷命令',
      icon: 'zap',
      enabled: canUseTerminalQuickCommands.value,
      action: () => undefined,
      children: getTerminalTabQuickCommandItems(tab),
    },
    {
      id: 'tab-reconnect',
      label: '重新连接',
      icon: 'refresh',
      enabled: Boolean(tab && (tab.status === 'closed' || tab.status === 'error')),
      separatorBefore: true,
      action: () => {
        if (tab) reconnectTerminalTab(tab);
      },
    },
    {
      id: 'tab-disconnect',
      label: '断开连接',
      icon: 'logout',
      enabled: canDisconnectTerminalTab(tab),
      danger: true,
      action: () => {
        if (tab) disconnectTerminalTab(tab);
      },
    },
    { id: 'tab-split-horizontal', label: '水平拆分会话', icon: 'rows', enabled: true, separatorBefore: true, action: () => setTerminalSplitMode('horizontal') },
    { id: 'tab-split-vertical', label: '垂直拆分会话', icon: 'panelLeft', enabled: true, action: () => setTerminalSplitMode('vertical') },
    { id: 'tab-split-single', label: '合并所有窗格', icon: 'maximize', enabled: terminalSplitMode.value !== 'single', action: () => setTerminalSplitMode('single') },
    {
      id: 'tab-close-current',
      label: '关闭当前',
      icon: 'x',
      enabled: hasTab,
      danger: true,
      separatorBefore: true,
      action: async () => {
        if (tab) await closeTab(tab);
      },
    },
    {
      id: 'tab-close-all',
      label: '关闭所有',
      icon: 'x',
      enabled: tabs.value.length > 0,
      danger: true,
      action: () => closeTerminalTabs(tabs.value),
    },
    {
      id: 'tab-close-inactive',
      label: '关闭非活动',
      icon: 'x',
      enabled: hasInactiveTabs,
      danger: true,
      action: async () => {
        if (tab) await closeTerminalTabs(tabs.value.filter((item) => item.id !== tab.id));
      },
    },
    {
      id: 'tab-close-right',
      label: '关闭右侧标签',
      icon: 'moveRight',
      enabled: rightSideTabs.length > 0,
      danger: true,
      action: () => closeTerminalTabs(rightSideTabs),
    },
  ];
});

const terminalRoot = computed<TerminalRoot>(() => ({
  id: null,
  name: rootLabel.value,
  count: countTerminalHosts(groups.value),
}));

const workspaceTitle = computed(() => {
  if (!activeTab.value) return '选择左侧主机开始连接';
  const tab = activeTab.value;
  const host = tab.host;
  return `${getTerminalTabLabel(tab)} / ${host.publicIp || host.privateIp}:${host.port}`;
});

function normalizeTerminalTabTitle(value: unknown) {
  if (typeof value !== 'string') return '';
  return value.trim().slice(0, TERMINAL_TAB_TITLE_MAX_LENGTH);
}

function isTerminalTabColorId(value: unknown): value is TerminalTabColorId {
  return typeof value === 'string' && terminalTabColorOptionMap.has(value as TerminalTabColorId);
}

function normalizeTerminalTabColorId(value: unknown): TerminalTabColorId | null {
  return isTerminalTabColorId(value) ? value : null;
}

function getTerminalTabLabel(tab: TerminalTab) {
  return tab.customTitle || tab.host.name;
}

function getTerminalMultiExecutionStatusText() {
  const total = tabs.value.filter((tab) => isTerminalTabReady(tab)).length;
  const targetCount = terminalMultiExecutionTargetCount.value;
  if (!total) return '没有已连接终端';
  return `键入内容将发送到 ${targetCount} / ${total} 个已连接终端`;
}

function isTerminalMultiExecutionExcluded(tab: TerminalTab) {
  return multiExecutionExcludedTabIds.value.has(tab.id);
}

function shouldShowTerminalMultiExecutionTabIndicator(tab: TerminalTab) {
  return isTerminalMultiExecutionEnabled.value && isTerminalTabReady(tab) && !isTerminalMultiExecutionExcluded(tab);
}

function setTerminalMultiExecutionExcluded(tab: TerminalTab, excluded: boolean) {
  const next = new Set(multiExecutionExcludedTabIds.value);
  if (excluded) {
    next.add(tab.id);
  } else {
    next.delete(tab.id);
  }
  multiExecutionExcludedTabIds.value = next;
}

function setTerminalMultiExecutionExcludedFromEvent(tab: TerminalTab, event: Event) {
  const input = event.target;
  if (!(input instanceof HTMLInputElement)) return;
  setTerminalMultiExecutionExcluded(tab, input.checked);
}

function pruneTerminalMultiExecutionExclusions() {
  if (!multiExecutionExcludedTabIds.value.size) return;
  const knownTabIds = new Set(tabs.value.map((tab) => tab.id));
  const next = new Set([...multiExecutionExcludedTabIds.value].filter((tabId) => knownTabIds.has(tabId)));
  if (next.size !== multiExecutionExcludedTabIds.value.size) {
    multiExecutionExcludedTabIds.value = next;
  }
}

async function enableTerminalMultiExecution() {
  if (!hasTerminalMultiExecutionCandidates.value) return;
  const firstTarget = terminalMultiExecutionTargets.value[0];
  if (firstTarget && !isTerminalTabReady(activeTab.value)) {
    await activateTab(firstTarget.id);
  }
  isTerminalMultiExecutionEnabled.value = true;
  pruneTerminalMultiExecutionExclusions();
  if (terminalSplitMode.value === 'single' && connectedTerminalTabs.value.length >= 2) {
    setTerminalSplitMode('auto');
  } else {
    fitVisibleTerminalsSoon();
  }
}

function exitTerminalMultiExecution() {
  isTerminalMultiExecutionEnabled.value = false;
  multiExecutionExcludedTabIds.value = new Set();
  fitVisibleTerminalsSoon();
}

async function toggleTerminalMultiExecution() {
  if (isTerminalMultiExecutionEnabled.value) {
    exitTerminalMultiExecution();
  } else {
    await enableTerminalMultiExecution();
  }
}

function sendTerminalInput(tab: TerminalTab | null, data: string, options: { focus?: boolean } = {}) {
  if (!data || !isTerminalTabReady(tab)) return false;
  tab.socket?.send(JSON.stringify({ type: 'input', data }));
  if (options.focus) tab.terminal.focus();
  return true;
}

function getTerminalMultiExecutionBroadcastTargets(sourceTab: TerminalTab | null = null) {
  if (!isTerminalMultiExecutionEnabled.value) return [];
  if (sourceTab && isTerminalMultiExecutionExcluded(sourceTab)) return [];
  return terminalMultiExecutionTargets.value.filter((tab) => tab.id !== sourceTab?.id);
}

function broadcastTerminalInputToMultiExecutionTargets(data: string, sourceTab: TerminalTab | null = null) {
  if (!data) return 0;
  const targets = sourceTab ? getTerminalMultiExecutionBroadcastTargets(sourceTab) : terminalMultiExecutionTargets.value;
  let sentCount = 0;
  for (const tab of targets) {
    if (sendTerminalInput(tab, data)) sentCount += 1;
  }
  return sentCount;
}

function sendTerminalInputToMultiExecutionTargets(data: string) {
  if (!data || !canSendToTerminalMultiExecutionTargets.value) return false;
  const sentCount = broadcastTerminalInputToMultiExecutionTargets(data);
  activeTab.value?.terminal.focus();
  return sentCount > 0;
}

async function pasteClipboardToTerminalMultiExecutionTargets() {
  if (!canSendToTerminalMultiExecutionTargets.value) return;
  try {
    const value = await navigator.clipboard?.readText();
    if (value) sendTerminalInputToMultiExecutionTargets(value);
  } catch {
    // Keep the multi-paste action quiet when the browser blocks clipboard reads.
  }
}

function canSendQuickCommandToTab(tab: TerminalTab | null) {
  return isTerminalMultiExecutionEnabled.value ? canSendToTerminalMultiExecutionTargets.value : isTerminalTabReady(tab);
}

function getTerminalServerIp(tab: TerminalTab | null) {
  return tab?.host.publicIp || tab?.host.privateIp || '';
}

function getTerminalTabStyle(tab: TerminalTab): Record<string, string> {
  const option = tab.colorId ? terminalTabColorOptionMap.get(tab.colorId) : null;
  if (!option) return {};
  return {
    '--terminal-tab-bg': option.background,
    '--terminal-tab-color': option.color,
    '--terminal-tab-border': option.border,
    '--terminal-tab-hover-bg': option.background,
    '--terminal-tab-hover-color': option.color,
    '--terminal-tab-active-bg': option.activeBackground,
    '--terminal-tab-active-color': option.activeColor,
    '--terminal-tab-active-border': option.activeBorder,
  };
}

function setTerminalTabColor(tab: TerminalTab, colorId: TerminalTabColorId | null) {
  tab.colorId = colorId;
  saveTerminalWorkspace();
}

function renameTerminalTab(tab: TerminalTab) {
  const nextTitle = window.prompt('重命名标签名称', getTerminalTabLabel(tab));
  if (nextTitle === null) return;
  const normalized = normalizeTerminalTabTitle(nextTitle);
  if (!normalized) return;
  tab.customTitle = normalized === tab.host.name ? '' : normalized;
  saveTerminalWorkspace();
}

function getTerminalTabsRightOf(tab: TerminalTab) {
  const index = tabs.value.findIndex((item) => item.id === tab.id);
  return index === -1 ? [] : tabs.value.slice(index + 1);
}

function sendQuickCommandToTerminalTab(command: TerminalQuickCommand, execute: boolean, tab: TerminalTab | null) {
  if (!command.enabled || !canSendQuickCommandToTab(tab)) return;
  const data = execute ? `${command.command}\r` : command.command;
  if (isTerminalMultiExecutionEnabled.value) {
    sendTerminalInputToMultiExecutionTargets(data);
    return;
  }
  sendTerminalInput(tab, data, { focus: true });
}

function getTerminalTabQuickCommandItems(tab: TerminalTab | null): TerminalContextMenuItem[] {
  const items: TerminalContextMenuItem[] = [
    {
      id: 'tab-quick-panel',
      label: isTerminalQuickCommandPanelCollapsed.value ? '展开快捷命令面板' : '收起快捷命令面板',
      icon: 'zap',
      enabled: shouldShowTerminalQuickCommandPanel.value,
      action: () => toggleTerminalQuickCommandPanel(),
    },
    { id: 'tab-quick-new', label: '新增命令...', icon: 'plus', enabled: canUseTerminalQuickCommands.value, action: () => openTerminalQuickCommandDialog() },
  ];
  const commands = terminalQuickCommands.value.filter((command) => command.enabled).slice(0, 6);
  if (!commands.length) {
    items.push({ id: 'tab-quick-empty', label: '暂无可用快捷命令', icon: 'terminal', enabled: false, separatorBefore: true, action: () => undefined });
    return items;
  }
  for (const command of commands) {
    items.push(
      {
        id: `tab-quick-append-${command.id}`,
        label: `追加：${command.name}`,
        icon: 'cornerDownLeft',
        enabled: canSendQuickCommandToTab(tab),
        separatorBefore: items.length === 2,
        action: () => sendQuickCommandToTerminalTab(command, false, tab),
      },
      {
        id: `tab-quick-run-${command.id}`,
        label: `执行：${command.name}`,
        icon: 'zap',
        enabled: canSendQuickCommandToTab(tab),
        action: () => sendQuickCommandToTerminalTab(command, true, tab),
      },
    );
  }
  return items;
}

function selectTerminalFile(entry: TerminalFileEntry, event?: MouseEvent | KeyboardEvent) {
  if (!activeTab.value) return;
  if (shouldSuppressTerminalFileClick) {
    shouldSuppressTerminalFileClick = false;
    return;
  }
  if (event?.shiftKey && terminalFileSelectionAnchorPath.value) {
    selectTerminalFileRange(terminalFileSelectionAnchorPath.value, entry);
    return;
  }
  setTerminalFileSelection([entry], isParentDirectoryEntry(entry) ? '' : entry.path);
}

function setTerminalFileSelection(entries: TerminalFileEntry[], anchorPath = entries[0]?.path ?? '') {
  const selectableEntries = entries.filter((entry) => !isParentDirectoryEntry(entry));
  selectedTerminalFilePaths.value = new Set(selectableEntries.map((entry) => entry.path));
  selectedTerminalFile.value = selectableEntries[selectableEntries.length - 1] ?? entries[entries.length - 1] ?? null;
  terminalFileSelectionAnchorPath.value = anchorPath && !isParentDirectoryEntry(entries.find((entry) => entry.path === anchorPath)) ? anchorPath : selectableEntries[0]?.path ?? '';
}

function selectTerminalFileRange(anchorPath: string, entry: TerminalFileEntry) {
  const anchorIndex = terminalFileEntries.value.findIndex((item) => item.path === anchorPath);
  const targetIndex = terminalFileEntries.value.findIndex((item) => item.path === entry.path);
  if (anchorIndex === -1 || targetIndex === -1) {
    setTerminalFileSelection([entry], isParentDirectoryEntry(entry) ? '' : entry.path);
    return;
  }
  const start = Math.min(anchorIndex, targetIndex);
  const end = Math.max(anchorIndex, targetIndex);
  const range = terminalFileEntries.value.slice(start, end + 1).filter((item) => !isParentDirectoryEntry(item));
  setTerminalFileSelection(range, anchorPath);
  selectedTerminalFile.value = isParentDirectoryEntry(entry) ? range[range.length - 1] ?? null : entry;
}

function startTerminalFileMarquee(event: MouseEvent) {
  if (!activeTab.value || event.button !== 0 || !terminalFileListRef.value) return;
  const target = event.target as Element | null;
  const currentTarget = event.currentTarget as Element | null;
  const isListBlank = target === currentTarget && currentTarget?.classList.contains('terminal-file-list');
  const isFileRow = currentTarget?.classList.contains('terminal-file-item') && !target?.closest('input');
  if (!isListBlank && !isFileRow) return;
  event.preventDefault();
  closeTerminalContextMenus();
  const point = getTerminalFileListPoint(event);
  terminalFileMarquee.value = {
    active: true,
    startX: point.x,
    startY: point.y,
    currentX: point.x,
    currentY: point.y,
    additive: event.shiftKey || event.ctrlKey || event.metaKey,
    basePaths: Array.from(selectedTerminalFilePaths.value),
  };
  updateTerminalFileMarqueeSelection();
  window.addEventListener('mousemove', moveTerminalFileMarquee);
  window.addEventListener('mouseup', stopTerminalFileMarquee);
}

function moveTerminalFileMarquee(event: MouseEvent) {
  if (!terminalFileMarquee.value.active) return;
  const point = getTerminalFileListPoint(event);
  terminalFileMarquee.value = { ...terminalFileMarquee.value, currentX: point.x, currentY: point.y };
  updateTerminalFileMarqueeSelection();
}

function stopTerminalFileMarquee() {
  if (!terminalFileMarquee.value.active) return;
  const state = terminalFileMarquee.value;
  shouldSuppressTerminalFileClick = Math.abs(state.currentX - state.startX) > 4 || Math.abs(state.currentY - state.startY) > 4;
  updateTerminalFileMarqueeSelection();
  terminalFileMarquee.value = { ...terminalFileMarquee.value, active: false };
  window.removeEventListener('mousemove', moveTerminalFileMarquee);
  window.removeEventListener('mouseup', stopTerminalFileMarquee);
  window.setTimeout(() => {
    shouldSuppressTerminalFileClick = false;
  }, 0);
}

function getTerminalFileListPoint(event: MouseEvent) {
  const list = terminalFileListRef.value;
  if (!list) return { x: 0, y: 0 };
  const rect = list.getBoundingClientRect();
  return {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top + list.scrollTop,
  };
}

function updateTerminalFileMarqueeSelection() {
  const list = terminalFileListRef.value;
  if (!list) return;
  const state = terminalFileMarquee.value;
  const marquee = {
    left: Math.min(state.startX, state.currentX),
    right: Math.max(state.startX, state.currentX),
    top: Math.min(state.startY, state.currentY),
    bottom: Math.max(state.startY, state.currentY),
  };
  const listRect = list.getBoundingClientRect();
  const selectedEntries = terminalFileEntries.value.filter((entry) => {
    if (isParentDirectoryEntry(entry)) return false;
    const row = list.querySelector<HTMLElement>(`[data-terminal-file-path="${cssEscape(entry.path)}"]`);
    if (!row) return false;
    const rowRect = row.getBoundingClientRect();
    const rowBox = {
      left: rowRect.left - listRect.left,
      right: rowRect.right - listRect.left,
      top: rowRect.top - listRect.top + list.scrollTop,
      bottom: rowRect.bottom - listRect.top + list.scrollTop,
    };
    return boxesIntersect(marquee, rowBox);
  });
  const nextPaths = new Set(state.additive ? state.basePaths : []);
  for (const entry of selectedEntries) nextPaths.add(entry.path);
  const nextEntries = terminalFileEntries.value.filter((entry) => nextPaths.has(entry.path) && !isParentDirectoryEntry(entry));
  setTerminalFileSelection(nextEntries, nextEntries[0]?.path ?? '');
}

function boxesIntersect(
  first: { left: number; right: number; top: number; bottom: number },
  second: { left: number; right: number; top: number; bottom: number },
) {
  return first.left <= second.right && first.right >= second.left && first.top <= second.bottom && first.bottom >= second.top;
}

function cssEscape(value: string) {
  const escape = window.CSS?.escape;
  return escape ? escape(value) : value.replace(/["\\]/g, '\\$&');
}

function syncTerminalFileSelectionAfterEntriesChange(preferredEntry?: TerminalFileEntry | null) {
  const availablePaths = new Set(terminalFileEntries.value.map((entry) => entry.path));
  const nextPaths = new Set(Array.from(selectedTerminalFilePaths.value).filter((path) => availablePaths.has(path)));
  if (preferredEntry && !isParentDirectoryEntry(preferredEntry) && availablePaths.has(preferredEntry.path)) {
    nextPaths.add(preferredEntry.path);
  }
  selectedTerminalFilePaths.value = nextPaths;
  selectedTerminalFile.value =
    (preferredEntry && availablePaths.has(preferredEntry.path) ? preferredEntry : null) ??
    terminalFileEntries.value.find((entry) => nextPaths.has(entry.path)) ??
    getDefaultSelectedTerminalFile(terminalFileEntries.value);
  if (selectedTerminalFile.value && !isParentDirectoryEntry(selectedTerminalFile.value)) {
    terminalFileSelectionAnchorPath.value = selectedTerminalFile.value.path;
    if (!selectedTerminalFilePaths.value.has(selectedTerminalFile.value.path)) {
      selectedTerminalFilePaths.value = new Set([selectedTerminalFile.value.path]);
    }
  } else {
    terminalFileSelectionAnchorPath.value = '';
  }
}

function isTerminalFileSelected(entry: TerminalFileEntry) {
  return selectedTerminalFilePaths.value.has(entry.path);
}

function getTerminalFileActionEntries(entry: TerminalFileEntry | null | undefined = selectedTerminalFile.value) {
  if (entry && !isParentDirectoryEntry(entry) && selectedTerminalFilePaths.value.has(entry.path)) {
    return selectedTerminalFiles.value;
  }
  if (entry && !isParentDirectoryEntry(entry)) return [entry];
  return selectedTerminalFiles.value;
}

function openTerminalFileContextMenu(entry: TerminalFileEntry, event: MouseEvent) {
  if (!activeTab.value) return;
  event.preventDefault();
  event.stopPropagation();
  if (!isTerminalFileSelected(entry)) {
    setTerminalFileSelection([entry], isParentDirectoryEntry(entry) ? '' : entry.path);
  } else {
    selectedTerminalFile.value = entry;
  }
  closeTerminalContextMenu();
  closeTerminalTabContextMenu();
  closeTerminalDirectoryContextMenu();
  closeTerminalTabMenu();
  closeTerminalSplitMenu();
  terminalFileContextMenu.value = {
    visible: true,
    ...getTerminalFileContextMenuPosition(event),
    entry,
  };
}

function openTerminalDirectoryContextMenu(event: MouseEvent) {
  if (!activeTab.value) return;
  const target = event.target as Element | null;
  if (target?.closest('.terminal-file-item') || target?.closest('.terminal-file-context-menu')) return;
  event.preventDefault();
  event.stopPropagation();
  setTerminalFileSelection([], '');
  closeTerminalContextMenu();
  closeTerminalTabContextMenu();
  closeTerminalFileContextMenu();
  closeTerminalTabMenu();
  closeTerminalSplitMenu();
  terminalDirectoryContextMenu.value = {
    visible: true,
    ...getTerminalFileContextMenuPosition(event, TERMINAL_DIRECTORY_CONTEXT_MENU_HEIGHT),
  };
}

function getTerminalFileContextMenuPosition(event: MouseEvent, menuHeight = TERMINAL_FILE_CONTEXT_MENU_HEIGHT) {
  const padding = 8;
  return {
    x: Math.max(padding, Math.min(event.clientX, window.innerWidth - TERMINAL_FILE_CONTEXT_MENU_WIDTH - padding)),
    y: Math.max(padding, Math.min(event.clientY, window.innerHeight - menuHeight - padding)),
  };
}

function isTerminalContextSubmenuLeft(x: number, menuWidth = TERMINAL_FILE_CONTEXT_MENU_WIDTH) {
  return x + menuWidth * 2 + 16 > window.innerWidth;
}

function closeTerminalFileContextMenu() {
  if (!terminalFileContextMenu.value.visible) return;
  terminalFileContextMenu.value = { visible: false, x: 0, y: 0, entry: null };
}

function closeTerminalDirectoryContextMenu() {
  if (!terminalDirectoryContextMenu.value.visible) return;
  terminalDirectoryContextMenu.value = { visible: false, x: 0, y: 0 };
}

function toggleTerminalTabMenu() {
  isTerminalTabMenuOpen.value = !isTerminalTabMenuOpen.value;
  if (isTerminalTabMenuOpen.value) {
    closeTerminalContextMenu();
    closeTerminalTabContextMenu();
    closeTerminalSplitMenu();
  }
}

function closeTerminalTabMenu() {
  isTerminalTabMenuOpen.value = false;
}

function toggleTerminalSplitMenu() {
  isTerminalSplitMenuOpen.value = !isTerminalSplitMenuOpen.value;
  if (isTerminalSplitMenuOpen.value) {
    closeTerminalContextMenu();
    closeTerminalTabContextMenu();
    closeTerminalTabMenu();
  }
}

function closeTerminalSplitMenu() {
  isTerminalSplitMenuOpen.value = false;
}

function setTerminalSplitMode(mode: TerminalSplitMode) {
  terminalSplitMode.value = mode;
  window.localStorage.setItem(TERMINAL_SPLIT_MODE_STORAGE_KEY, mode);
  closeTerminalSplitMenu();
  fitVisibleTerminalsSoon();
}

function syncTerminalTabsScrollState() {
  const tabsElement = terminalTabsRef.value;
  if (!tabsElement) {
    canScrollTerminalTabsLeft.value = false;
    canScrollTerminalTabsRight.value = false;
    return;
  }

  const maxScrollLeft = Math.max(0, tabsElement.scrollWidth - tabsElement.clientWidth);
  canScrollTerminalTabsLeft.value = tabsElement.scrollLeft > 1;
  canScrollTerminalTabsRight.value = tabsElement.scrollLeft < maxScrollLeft - 1;
}

function syncTerminalTabsScrollStateSoon() {
  window.requestAnimationFrame(syncTerminalTabsScrollState);
}

function scrollTerminalTabs(direction: 'left' | 'right') {
  const tabsElement = terminalTabsRef.value;
  if (!tabsElement) return;
  const distance = Math.max(120, tabsElement.clientWidth * 0.7);
  tabsElement.scrollBy({
    left: direction === 'left' ? -distance : distance,
    behavior: 'smooth',
  });
  window.setTimeout(syncTerminalTabsScrollState, 220);
}

function scrollActiveTerminalTabIntoView() {
  const tabsElement = terminalTabsRef.value;
  if (!tabsElement || !activeTabId.value) {
    syncTerminalTabsScrollStateSoon();
    return;
  }
  const activeButton = tabsElement.querySelector<HTMLElement>(`[data-terminal-tab-id="${cssEscape(activeTabId.value)}"]`);
  activeButton?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
  window.setTimeout(syncTerminalTabsScrollState, 220);
}

function createTerminalQuickCommandDraft(command?: TerminalQuickCommand | null): TerminalQuickCommandDraft {
  return {
    name: command?.name ?? '',
    category: command?.category ?? terminalQuickCommands.value[0]?.category ?? 'Linux',
    command: command?.command ?? '',
    description: command?.description ?? '',
    enabled: command?.enabled ?? true,
    sortOrder: command?.sortOrder ?? 0,
  };
}

async function loadTerminalQuickCommands() {
  isTerminalQuickCommandLoading.value = true;
  terminalQuickCommandError.value = '';
  try {
    terminalQuickCommands.value = await apiGet<TerminalQuickCommand[]>('/api/web-terminal/quick-commands/');
    if (
      terminalQuickCommandCategory.value !== 'all' &&
      !terminalQuickCommands.value.some((command) => command.category === terminalQuickCommandCategory.value)
    ) {
      terminalQuickCommandCategory.value = 'all';
    }
  } catch (error) {
    if (handleTerminalAuthExpired(error)) return;
    terminalQuickCommandError.value = error instanceof Error ? error.message : '快捷命令加载失败';
  } finally {
    isTerminalQuickCommandLoading.value = false;
  }
}

function openTerminalQuickCommandDialog(command: TerminalQuickCommand | null = null) {
  terminalQuickCommandDialog.value = {
    visible: true,
    mode: command ? 'edit' : 'create',
    commandId: command?.id ?? null,
    draft: createTerminalQuickCommandDraft(command),
    saving: false,
    error: '',
  };
}

function closeTerminalQuickCommandDialog() {
  if (terminalQuickCommandDialog.value.saving) return;
  terminalQuickCommandDialog.value = {
    visible: false,
    mode: 'create',
    commandId: null,
    draft: createTerminalQuickCommandDraft(),
    saving: false,
    error: '',
  };
}

function terminalQuickCommandPayload(draft: TerminalQuickCommandDraft) {
  return {
    name: draft.name.trim(),
    category: draft.category.trim(),
    command: draft.command.trim(),
    description: draft.description.trim(),
    enabled: draft.enabled,
    sortOrder: draft.sortOrder,
  };
}

async function saveTerminalQuickCommandDialog() {
  const dialog = terminalQuickCommandDialog.value;
  if (!dialog.visible || dialog.saving) return;
  const payload = terminalQuickCommandPayload(dialog.draft);
  if (!payload.name || !payload.category || !payload.command) {
    terminalQuickCommandDialog.value = { ...dialog, error: '请填写名称、分类和命令内容' };
    return;
  }

  terminalQuickCommandDialog.value = { ...dialog, saving: true, error: '' };
  try {
    const saved =
      dialog.mode === 'edit' && dialog.commandId
        ? await apiPut<TerminalQuickCommand>(`/api/web-terminal/quick-commands/${dialog.commandId}/`, payload)
        : await apiPost<TerminalQuickCommand>('/api/web-terminal/quick-commands/', payload);
    const nextCommands =
      dialog.mode === 'edit'
        ? terminalQuickCommands.value.map((command) => (command.id === saved.id ? saved : command))
        : [...terminalQuickCommands.value, saved];
    terminalQuickCommands.value = sortTerminalQuickCommands(nextCommands);
    terminalQuickCommandCategory.value = saved.category;
    closeTerminalQuickCommandDialog();
  } catch (error) {
    if (handleTerminalAuthExpired(error)) return;
    terminalQuickCommandDialog.value = {
      ...dialog,
      saving: false,
      error: error instanceof Error ? error.message : '快捷命令保存失败',
    };
  }
}

async function deleteTerminalQuickCommand(command: TerminalQuickCommand) {
  if (!window.confirm(`删除快捷命令“${command.name}”？`)) return;
  try {
    await apiDelete<{ deleted: boolean }>(`/api/web-terminal/quick-commands/${command.id}/`);
    terminalQuickCommands.value = terminalQuickCommands.value.filter((item) => item.id !== command.id);
  } catch (error) {
    if (handleTerminalAuthExpired(error)) return;
    terminalQuickCommandError.value = error instanceof Error ? error.message : '快捷命令删除失败';
  }
}

async function toggleTerminalQuickCommand(command: TerminalQuickCommand) {
  try {
    const saved = await apiPut<TerminalQuickCommand>(`/api/web-terminal/quick-commands/${command.id}/`, {
      ...command,
      enabled: !command.enabled,
    });
    terminalQuickCommands.value = terminalQuickCommands.value.map((item) => (item.id === saved.id ? saved : item));
  } catch (error) {
    if (handleTerminalAuthExpired(error)) return;
    terminalQuickCommandError.value = error instanceof Error ? error.message : '快捷命令状态更新失败';
  }
}

async function moveTerminalQuickCommand(command: TerminalQuickCommand, direction: -1 | 1) {
  const visibleCommands = filteredTerminalQuickCommands.value;
  const visibleIndex = visibleCommands.findIndex((item) => item.id === command.id);
  const target = visibleCommands[visibleIndex + direction];
  if (!target) return;

  const nextCommands = [...terminalQuickCommands.value];
  const sourceIndex = nextCommands.findIndex((item) => item.id === command.id);
  const targetIndex = nextCommands.findIndex((item) => item.id === target.id);
  if (sourceIndex === -1 || targetIndex === -1) return;

  [nextCommands[sourceIndex], nextCommands[targetIndex]] = [nextCommands[targetIndex], nextCommands[sourceIndex]];
  await saveTerminalQuickCommandOrder(nextCommands);
}

async function saveTerminalQuickCommandOrder(nextCommands: TerminalQuickCommand[]) {
  const previousCommands = terminalQuickCommands.value;
  terminalQuickCommands.value = nextCommands.map((command, index) => ({ ...command, sortOrder: (index + 1) * 10 }));
  try {
    terminalQuickCommands.value = await apiPost<TerminalQuickCommand[]>('/api/web-terminal/quick-commands/reorder/', {
      ids: terminalQuickCommands.value.map((command) => command.id),
    });
  } catch (error) {
    if (handleTerminalAuthExpired(error)) return;
    terminalQuickCommands.value = previousCommands;
    terminalQuickCommandError.value = error instanceof Error ? error.message : '快捷命令排序保存失败';
  }
}

function sortTerminalQuickCommands(commands: TerminalQuickCommand[]) {
  return [...commands].sort(
    (left, right) =>
      left.category.localeCompare(right.category, 'zh-Hans-CN') ||
      left.sortOrder - right.sortOrder ||
      left.id - right.id,
  );
}

function isTerminalAuthError(error: unknown) {
  return error instanceof ApiUnauthorizedError;
}

function handleTerminalAuthExpired(error?: unknown) {
  if (error && !isTerminalAuthError(error)) return false;
  if (terminalAuthRedirecting) return true;
  terminalAuthRedirecting = true;
  stopTerminalMonitorPolling();
  pendingConnectTabIds.splice(0, pendingConnectTabIds.length);
  connectingTabIds.clear();
  if (typeof window !== 'undefined') {
    window.sessionStorage.removeItem(TERMINAL_WORKSPACE_STORAGE_KEY);
  }
  for (const tab of tabs.value) {
    tab.status = 'closed';
    if (tab.socket && tab.socket.readyState !== WebSocket.CLOSED) {
      tab.socket.close();
    }
    tab.socket = null;
  }
  window.location.replace('/');
  return true;
}

function handleTerminalAuthStorageEvent(event: StorageEvent) {
  if (event.key === AUTH_LOGOUT_EVENT_KEY) {
    handleTerminalAuthExpired();
  }
}

function sendQuickCommandToTerminal(command: TerminalQuickCommand, execute: boolean) {
  if (!command.enabled) return;
  const data = execute ? `${command.command}\r` : command.command;
  if (isTerminalMultiExecutionEnabled.value) {
    sendTerminalInputToMultiExecutionTargets(data);
    return;
  }
  if (!activeTerminalReady.value || !activeTab.value) return;
  sendTerminalInput(activeTab.value, data, { focus: true });
}

function closeTerminalContextMenus() {
  closeTerminalContextMenu();
  closeTerminalTabContextMenu();
  closeTerminalFileContextMenu();
  closeTerminalDirectoryContextMenu();
  closeTerminalTabMenu();
  closeTerminalSplitMenu();
}

async function selectTerminalTabFromMenu(tab: TerminalTab) {
  closeTerminalTabMenu();
  await activateTab(tab.id);
}

async function runTerminalFileContextMenuItem(item: TerminalFileContextMenuItem) {
  if (!item.enabled) return;
  if (item.children?.length) return;
  closeTerminalContextMenus();
  await item.action();
}

async function runTerminalContextMenuItem(item: TerminalContextMenuItem) {
  if (!item.enabled) return;
  if (item.children?.length) return;
  closeTerminalContextMenus();
  await item.action();
}

async function runTerminalTabContextMenuItem(item: TerminalContextMenuItem) {
  if (!item.enabled) return;
  if (item.children?.length) return;
  closeTerminalContextMenus();
  await item.action();
}

function openTerminalTabContextMenu(tab: TerminalTab, event: MouseEvent) {
  event.preventDefault();
  event.stopPropagation();
  if (tab.id !== activeTabId.value) {
    void activateTab(tab.id);
  }
  closeTerminalContextMenu();
  closeTerminalFileContextMenu();
  closeTerminalDirectoryContextMenu();
  closeTerminalTabMenu();
  closeTerminalSplitMenu();
  terminalTabContextMenu.value = {
    visible: true,
    tabId: tab.id,
    ...getTerminalTabContextMenuPosition(event),
  };
}

function openTerminalContextMenu(tab: TerminalTab, event: MouseEvent) {
  event.preventDefault();
  event.stopPropagation();
  if (!isTerminalTabVisible(tab)) return;
  if (tab.id !== activeTabId.value) {
    void activateTab(tab.id);
  }
  const selectedText = tab.terminal.hasSelection() ? tab.terminal.getSelection() : '';
  closeTerminalTabContextMenu();
  closeTerminalFileContextMenu();
  closeTerminalDirectoryContextMenu();
  closeTerminalTabMenu();
  closeTerminalSplitMenu();
  terminalContextMenu.value = {
    visible: true,
    tabId: tab.id,
    selectedText,
    ...getTerminalContextMenuPosition(event),
  };
}

function getTerminalTabContextMenuPosition(event: MouseEvent) {
  const padding = 8;
  return {
    x: Math.max(padding, Math.min(event.clientX, window.innerWidth - TERMINAL_TAB_CONTEXT_MENU_WIDTH - padding)),
    y: Math.max(padding, Math.min(event.clientY, window.innerHeight - TERMINAL_TAB_CONTEXT_MENU_HEIGHT - padding)),
  };
}

function getTerminalContextMenuPosition(event: MouseEvent) {
  const padding = 8;
  return {
    x: Math.max(padding, Math.min(event.clientX, window.innerWidth - TERMINAL_CONTEXT_MENU_WIDTH - padding)),
    y: Math.max(padding, Math.min(event.clientY, window.innerHeight - TERMINAL_CONTEXT_MENU_HEIGHT - padding)),
  };
}

function closeTerminalContextMenu() {
  if (!terminalContextMenu.value.visible) return;
  terminalContextMenu.value = { visible: false, x: 0, y: 0, tabId: null, selectedText: '' };
}

function closeTerminalTabContextMenu() {
  if (!terminalTabContextMenu.value.visible) return;
  terminalTabContextMenu.value = { visible: false, x: 0, y: 0, tabId: null };
}

function getTerminalContextMenuTab() {
  const tabId = terminalContextMenu.value.tabId;
  return tabId ? getTabById(tabId) : activeTab.value;
}

function getTerminalTabContextMenuTab() {
  const tabId = terminalTabContextMenu.value.tabId;
  return tabId ? getTabById(tabId) : activeTab.value;
}

function isTerminalTabReady(tab: TerminalTab | null): tab is TerminalTab {
  return Boolean(tab && tab.status === 'connected' && tab.socket?.readyState === WebSocket.OPEN);
}

function canDisconnectTerminalTab(tab: TerminalTab | null) {
  return Boolean(tab && (tab.status === 'connecting' || tab.status === 'connected' || tab.socket));
}

async function copyTerminalContextText(value: string) {
  if (!value) return;
  try {
    await navigator.clipboard?.writeText(value);
  } catch {
    // Clipboard access can be denied outside a secure context or without permission.
  }
}

async function pasteClipboardToTerminal(tab: TerminalTab | null) {
  if (!isTerminalTabReady(tab)) return;
  try {
    const value = await navigator.clipboard?.readText();
    if (value) sendTextToTerminal(value, tab);
  } catch {
    // Keep the menu action quiet when the browser blocks clipboard reads.
  }
}

function sendTextToTerminal(value: string, tab: TerminalTab | null) {
  sendTerminalInput(tab, value, { focus: true });
}

function sendControlToTerminal(value: string, tab: TerminalTab | null) {
  sendTextToTerminal(value, tab);
}

function toSingleLineTerminalText(value: string) {
  return value.replace(/[\r\n]+/g, ' ').replace(/\s+/g, ' ').trim();
}

function openTerminalOnlineSearch(query: string) {
  const value = query.trim();
  if (!value) return;
  window.open(`https://www.bing.com/search?q=${encodeURIComponent(value)}`, '_blank', 'noopener,noreferrer');
}

function openTerminalTranslation(text: string, targetLanguage: 'zh-Hans' | 'en') {
  const value = text.trim();
  if (!value) return;
  window.open(
    `https://www.bing.com/translator?to=${encodeURIComponent(targetLanguage)}&text=${encodeURIComponent(value)}`,
    '_blank',
    'noopener,noreferrer',
  );
}

function findTerminalText(query: string) {
  const value = query.trim();
  if (!value) return;
  openTerminalSearch(value);
}

function promptFindTerminalText() {
  openTerminalSearch();
}

function getTerminalSearchOptions(incremental = false): ISearchOptions {
  return {
    caseSensitive: false,
    incremental,
    decorations: TERMINAL_SEARCH_DECORATIONS,
  };
}

function resetTerminalSearchResultState() {
  terminalSearchResultIndex.value = -1;
  terminalSearchResultCount.value = 0;
}

function focusTerminalSearchInputSoon(select = false) {
  void nextTick(() => {
    const input = terminalSearchInputRef.value;
    if (!input) return;
    input.focus();
    if (select) input.select();
  });
}

function openTerminalSearch(initialQuery = '') {
  if (!activeTab.value) return;
  closeTerminalContextMenus();
  isTerminalSearchOpen.value = true;
  if (initialQuery.trim()) {
    terminalSearchQuery.value = initialQuery.trim();
  }
  resetTerminalSearchResultState();
  focusTerminalSearchInputSoon(!initialQuery.trim());
  if (terminalSearchQuery.value.trim()) {
    void nextTick(() => searchCurrentTerminal('next', true));
  }
}

function clearTerminalSearchDecorations(tab: TerminalTab | null = activeTab.value) {
  tab?.searchAddon.clearDecorations();
}

function clearAllTerminalSearchDecorations() {
  for (const tab of tabs.value) clearTerminalSearchDecorations(tab);
}

function closeTerminalSearch() {
  if (!isTerminalSearchOpen.value) return;
  isTerminalSearchOpen.value = false;
  clearAllTerminalSearchDecorations();
  resetTerminalSearchResultState();
  activeTab.value?.terminal.focus();
}

function searchCurrentTerminal(direction: 'next' | 'previous' = 'next', incremental = false) {
  const query = terminalSearchQuery.value.trim();
  const tab = activeTab.value;
  if (!tab) {
    resetTerminalSearchResultState();
    return false;
  }
  if (!query) {
    clearTerminalSearchDecorations(tab);
    tab.terminal.clearSelection();
    resetTerminalSearchResultState();
    return false;
  }
  clearTerminalSearchDecorations(tab);
  const matches = collectTerminalSearchMatches(tab, query);
  terminalSearchResultCount.value = matches.length;
  if (!matches.length) {
    terminalSearchResultIndex.value = -1;
    tab.terminal.clearSelection();
    return false;
  }

  const currentIndex = terminalSearchResultIndex.value;
  const nextIndex =
    incremental || currentIndex < 0
      ? 0
      : direction === 'previous'
        ? (currentIndex - 1 + matches.length) % matches.length
        : (currentIndex + 1) % matches.length;
  terminalSearchResultIndex.value = nextIndex;
  decorateTerminalSearchMatches(tab, query);
  selectTerminalSearchMatch(tab, matches[nextIndex]);
  return true;
}

function decorateTerminalSearchMatches(tab: TerminalTab, query: string) {
  try {
    tab.searchAddon.findNext(query, getTerminalSearchOptions(false));
  } catch {
    // The buffer scan above is the source of truth; addon decorations are best-effort.
  }
}

function selectTerminalSearchMatch(tab: TerminalTab, match: TerminalSearchMatch | undefined) {
  if (!match) return;
  const buffer = tab.terminal.buffer.active;
  if (match.row < buffer.viewportY || match.row >= buffer.viewportY + tab.terminal.rows) {
    tab.terminal.scrollToLine(Math.max(0, match.row - Math.floor(tab.terminal.rows / 2)));
  }
  tab.terminal.select(match.col, match.row, match.size);
}

function collectTerminalSearchMatches(tab: TerminalTab, query: string) {
  const normalizedQuery = query.toLowerCase();
  const matches: TerminalSearchMatch[] = [];
  if (!normalizedQuery) return matches;

  const buffer = tab.terminal.buffer.active;
  const maxRow = buffer.baseY + tab.terminal.rows;
  for (let row = 0; row < maxRow; row += 1) {
    const line = buffer.getLine(row);
    if (!line || line.isWrapped) continue;

    const logicalLine = getTerminalLogicalSearchLine(tab, row, maxRow);
    const searchText = logicalLine.text.toLowerCase();
    let index = searchText.indexOf(normalizedQuery);
    while (index !== -1) {
      const position = getTerminalSearchBufferPosition(logicalLine.parts, index);
      if (position) {
        matches.push({
          row: position.row,
          col: position.col,
          size: Math.max(1, query.length),
        });
      }
      index = searchText.indexOf(normalizedQuery, index + Math.max(1, normalizedQuery.length));
    }
  }
  return matches;
}

function getTerminalLogicalSearchLine(tab: TerminalTab, startRow: number, maxRow: number) {
  const parts: Array<{ row: number; line: IBufferLine; start: number; text: string }> = [];
  const buffer = tab.terminal.buffer.active;
  let text = '';
  for (let row = startRow; row < maxRow; row += 1) {
    const line = buffer.getLine(row);
    if (!line) break;
    const nextLine = row + 1 < maxRow ? buffer.getLine(row + 1) : undefined;
    const lineText = line.translateToString(!nextLine?.isWrapped);
    parts.push({ row, line, start: text.length, text: lineText });
    text += lineText;
    if (!nextLine?.isWrapped) break;
  }
  return { text, parts };
}

function getTerminalSearchBufferPosition(
  parts: Array<{ row: number; line: IBufferLine; start: number; text: string }>,
  stringIndex: number,
) {
  for (const part of parts) {
    if (stringIndex < part.start || stringIndex >= part.start + part.text.length) continue;
    return {
      row: part.row,
      col: getTerminalColumnFromStringOffset(part.line, stringIndex - part.start),
    };
  }
  return null;
}

function getTerminalColumnFromStringOffset(line: IBufferLine, offset: number) {
  let consumed = 0;
  for (let col = 0; col < line.length; col += 1) {
    const cell = line.getCell(col);
    if (!cell || cell.getWidth() === 0) continue;
    const chars = cell.getChars() || ' ';
    const nextConsumed = consumed + chars.length;
    if (offset <= consumed || offset < nextConsumed) return col;
    consumed = nextConsumed;
  }
  return Math.max(0, Math.min(line.length - 1, offset));
}

function openTerminalQuickCommandDialogFromText(commandText: string) {
  const command = commandText.trim();
  if (!command) return;
  const firstLine = command.split(/\r?\n/).find(Boolean) ?? '快捷命令';
  terminalQuickCommandDialog.value = {
    visible: true,
    mode: 'create',
    commandId: null,
    draft: {
      ...createTerminalQuickCommandDraft(),
      name: firstLine.slice(0, 40),
      command,
      description: '从终端选中内容保存',
      enabled: true,
    },
    saving: false,
    error: '',
  };
  if (isTerminalQuickCommandPanelCollapsed.value && shouldShowTerminalQuickCommandPanel.value) {
    toggleTerminalQuickCommandPanel();
  }
}

function getTerminalQuickCommandContextItems(tab: TerminalTab | null): TerminalContextMenuItem[] {
  const items: TerminalContextMenuItem[] = [
    {
      id: 'quick-panel',
      label: isTerminalQuickCommandPanelCollapsed.value ? '展开快捷命令面板' : '收起快捷命令面板',
      icon: 'zap',
      enabled: shouldShowTerminalQuickCommandPanel.value,
      action: () => toggleTerminalQuickCommandPanel(),
    },
    { id: 'quick-new', label: '新增命令...', icon: 'plus', enabled: canUseTerminalQuickCommands.value, action: () => openTerminalQuickCommandDialog() },
  ];
  const commands = terminalQuickCommands.value.filter((command) => command.enabled).slice(0, 6);
  for (const command of commands) {
    items.push({
      id: `quick-${command.id}`,
      label: command.name,
      icon: 'terminal',
      enabled: canSendQuickCommandToTab(tab),
      separatorBefore: items.length === 2,
      action: () => sendQuickCommandToTerminal(command, false),
    });
  }
  return items;
}

function getTerminalSessionContextMenu(tab: TerminalTab | null): TerminalContextMenuItem {
  return {
    id: 'session',
    label: '会话',
    icon: 'server',
    enabled: Boolean(tab),
    separatorBefore: true,
    action: () => undefined,
    children: [
      {
        id: 'session-reconnect',
        label: '重新连接',
        icon: 'refresh',
        enabled: Boolean(tab && (tab.status === 'closed' || tab.status === 'error')),
        action: () => {
          if (tab) reconnectTerminalTab(tab);
        },
      },
      {
        id: 'session-copy-info',
        label: '复制当前主机信息',
        icon: 'copy',
        enabled: Boolean(tab),
        action: async () => {
          if (tab) await copyTerminalContextText(getTerminalSessionInfo(tab));
        },
      },
      {
        id: 'session-duplicate',
        label: '新建同主机标签',
        icon: 'plus',
        enabled: Boolean(tab),
        action: async () => {
          if (tab) await openHostTab(tab.host);
        },
      },
      {
        id: 'session-close',
        label: '关闭当前标签',
        icon: 'x',
        enabled: Boolean(tab),
        danger: true,
        separatorBefore: true,
        action: async () => {
          if (tab) await closeTab(tab);
        },
      },
    ],
  };
}

function getTerminalControlKeyContextMenu(tab: TerminalTab | null): TerminalContextMenuItem {
  const enabled = isTerminalTabReady(tab);
  return {
    id: 'control-keys',
    label: '发送控制键',
    icon: 'terminal',
    enabled,
    action: () => undefined,
    children: [
      { id: 'control-c', label: '中断', icon: 'x', enabled, shortcut: 'Ctrl+C', action: () => sendControlToTerminal('\x03', tab) },
      { id: 'control-d', label: 'EOF', icon: 'logout', enabled, shortcut: 'Ctrl+D', action: () => sendControlToTerminal('\x04', tab) },
      { id: 'control-z', label: '挂起', icon: 'minimize', enabled, shortcut: 'Ctrl+Z', action: () => sendControlToTerminal('\x1a', tab) },
      { id: 'control-u', label: '清空当前输入', icon: 'trash', enabled, shortcut: 'Ctrl+U', action: () => sendControlToTerminal('\x15', tab) },
      { id: 'control-l', label: '清屏', icon: 'rows', enabled, shortcut: 'Ctrl+L', action: () => sendControlToTerminal('\x0c', tab) },
    ],
  };
}

function getTerminalViewContextMenu(tab: TerminalTab | null): TerminalContextMenuItem {
  const filePanelOpen = terminalSidebarMode.value === 'files' && !isTerminalSidebarCollapsed.value;
  const splitItems: TerminalContextMenuItem[] = terminalSplitModeOptions.map((option, index) => ({
    id: `split-${option.mode}`,
    label: terminalSplitMode.value === option.mode ? `${option.label} ✓` : option.label,
    icon: option.icon,
    enabled: true,
    separatorBefore: index === 0,
    action: () => setTerminalSplitMode(option.mode),
  }));
  return {
    id: 'view',
    label: '视图',
    icon: 'settings',
    enabled: true,
    action: () => undefined,
    children: [
      { id: 'view-files', label: filePanelOpen ? '关闭文件面板' : '打开文件面板', icon: 'folder', enabled: Boolean(tab), action: () => toggleTerminalFilePanel() },
      { id: 'view-monitor', label: isTerminalMonitorPanelOpen.value ? '关闭资源监控' : '打开资源监控', icon: 'monitor', enabled: Boolean(tab), action: () => toggleTerminalMonitorPanel() },
      ...splitItems,
      { id: 'font-decrease', label: '字号减小', icon: 'zoomOut', enabled: canDecreaseTerminalFontSize.value, separatorBefore: true, action: () => decreaseTerminalFontSize() },
      { id: 'font-increase', label: '字号增大', icon: 'zoomIn', enabled: canIncreaseTerminalFontSize.value, action: () => increaseTerminalFontSize() },
      { id: 'font-reset', label: '重置字号', icon: 'reset', enabled: terminalFontSize.value !== TERMINAL_FONT_SIZE_DEFAULT, action: () => setTerminalFontSize(TERMINAL_FONT_SIZE_DEFAULT) },
      { id: 'highlight-toggle', label: highlightEnabled.value ? '关闭高亮' : '开启高亮', icon: 'sun', enabled: true, separatorBefore: true, action: () => { highlightEnabled.value = !highlightEnabled.value; } },
    ],
  };
}

function getTerminalBufferContextMenu(tab: TerminalTab | null): TerminalContextMenuItem {
  const hasTab = Boolean(tab);
  const ready = isTerminalTabReady(tab);
  return {
    id: 'buffer',
    label: '缓冲区',
    icon: 'rows',
    enabled: hasTab,
    action: () => undefined,
    children: [
      { id: 'buffer-clear-screen', label: '清屏', icon: 'rows', enabled: ready, shortcut: 'Ctrl+L', action: () => sendControlToTerminal('\x0c', tab) },
      { id: 'buffer-clear-all', label: '全部清除', icon: 'trash', enabled: hasTab, action: () => tab?.terminal.clear() },
      { id: 'buffer-bottom', label: '滚动到底部', icon: 'chevronDown', enabled: hasTab, action: () => tab?.terminal.scrollToBottom() },
      {
        id: 'buffer-copy-screen',
        label: '复制当前屏幕',
        icon: 'copy',
        enabled: hasTab,
        separatorBefore: true,
        action: async () => {
          if (tab) await copyTerminalContextText(getTerminalVisibleText(tab));
        },
      },
      {
        id: 'buffer-export',
        label: '导出终端日志...',
        icon: 'download',
        enabled: hasTab,
        action: () => {
          if (tab) exportTerminalLog(tab);
        },
      },
      { id: 'buffer-select-all', label: '全选', icon: 'scan', enabled: hasTab, shortcut: 'Ctrl+Shift+A', separatorBefore: true, action: () => tab?.terminal.selectAll() },
    ],
  };
}

function toggleTerminalFilePanel() {
  if (terminalSidebarMode.value === 'files' && !isTerminalSidebarCollapsed.value) {
    setTerminalSidebarCollapsed(true);
    return;
  }
  selectTerminalSidebarMode('files');
}

function getTerminalSessionInfo(tab: TerminalTab) {
  const host = tab.host;
  return [
    `主机：${host.name}`,
    `登录用户：${host.loginUser || '-'}`,
    `公网 IP：${host.publicIp || '-'}`,
    `内网 IP：${host.privateIp || '-'}`,
    `端口：${host.port}`,
    `当前目录：${tab.currentCwd || '-'}`,
    `状态：${tab.status}`,
  ].join('\n');
}

function getTerminalVisibleText(tab: TerminalTab) {
  const buffer = tab.terminal.buffer.active;
  const start = buffer.viewportY;
  const end = Math.min(buffer.length, start + tab.terminal.rows);
  const lines: string[] = [];
  for (let index = start; index < end; index += 1) {
    lines.push(buffer.getLine(index)?.translateToString(true) ?? '');
  }
  return lines.join('\n').trimEnd();
}

function getTerminalBufferText(tab: TerminalTab) {
  const buffer = tab.terminal.buffer.active;
  const lines: string[] = [];
  for (let index = 0; index < buffer.length; index += 1) {
    lines.push(buffer.getLine(index)?.translateToString(true) ?? '');
  }
  return lines.join('\n').trimEnd();
}

function exportTerminalLog(tab: TerminalTab) {
  const content = getTerminalBufferText(tab);
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `${sanitizeTerminalLogFileName(tab.host.name)}-${new Date().toISOString().replace(/[:.]/g, '-')}.log`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function sanitizeTerminalLogFileName(value: string) {
  return value.trim().replace(/[<>:"/\\|?*\x00-\x1f]/g, '_') || 'terminal';
}

function startTerminalFileRename(entry: TerminalFileEntry) {
  if (!activeTab.value || isParentDirectoryEntry(entry)) return;
  setTerminalFileSelection([entry], entry.path);
  terminalFileRename.value = {
    path: entry.path,
    originalName: entry.name,
    draftName: entry.name,
    saving: false,
    error: '',
  };
  void nextTick(() => {
    terminalFileRenameInput.value?.focus();
    terminalFileRenameInput.value?.select();
  });
}

function setTerminalFileRenameInput(element: Element | ComponentPublicInstance | null) {
  terminalFileRenameInput.value = element instanceof HTMLInputElement ? element : null;
}

function cancelTerminalFileRename() {
  terminalFileRename.value = null;
}

async function saveTerminalFileRename() {
  const state = terminalFileRename.value;
  if (!activeTab.value || !state || state.saving) return;
  const newName = state.draftName.trim();
  if (!newName) {
    terminalFileRename.value = { ...state, error: '请输入新名称' };
    return;
  }
  if (newName === state.originalName) {
    cancelTerminalFileRename();
    return;
  }
  terminalFileRename.value = { ...state, saving: true, error: '' };
  try {
    await apiPost<TerminalFileProperties>(
      `/api/web-terminal/hosts/${activeTab.value.host.id}/files/rename/`,
      { path: state.path, newName },
    );
    terminalFileRename.value = null;
    await loadTerminalDirectory(terminalFilePath.value);
  } catch (error) {
    if (handleTerminalAuthExpired(error)) return;
    terminalFileRename.value = {
      ...state,
      saving: false,
      error: error instanceof Error ? error.message : '重命名失败',
    };
    void nextTick(() => terminalFileRenameInput.value?.focus());
  }
}

function isTerminalFileRenaming(entry: TerminalFileEntry) {
  return terminalFileRename.value?.path === entry.path;
}

function openTerminalFileDeleteDialog(target: TerminalFileEntry | TerminalFileEntry[] | null = getTerminalFileActionEntries()) {
  if (!activeTab.value) return;
  const entries = Array.isArray(target) ? target : target ? [target] : [];
  const deletableEntries = entries.filter((entry) => !isParentDirectoryEntry(entry));
  if (!deletableEntries.length) return;
  setTerminalFileSelection(deletableEntries, deletableEntries[0].path);
  terminalFileDeleteDialog.value = {
    visible: true,
    entry: deletableEntries[0],
    entries: deletableEntries,
    deleting: false,
    error: '',
  };
}

function closeTerminalFileDeleteDialog() {
  if (terminalFileDeleteDialog.value.deleting) return;
  terminalFileDeleteDialog.value = {
    visible: false,
    entry: null,
    entries: [],
    deleting: false,
    error: '',
  };
}

async function confirmTerminalFileDelete() {
  const dialog = terminalFileDeleteDialog.value;
  const entries = dialog.entries.length ? dialog.entries : dialog.entry ? [dialog.entry] : [];
  if (!activeTab.value || !entries.length || dialog.deleting) return;
  terminalFileDeleteDialog.value = { ...dialog, deleting: true, error: '' };
  try {
    for (const entry of entries) {
      await apiPost<{ deleted: boolean }>(
        `/api/web-terminal/hosts/${activeTab.value.host.id}/files/delete/`,
        { path: entry.path },
      );
    }
    terminalFileDeleteDialog.value = { visible: false, entry: null, entries: [], deleting: false, error: '' };
    setTerminalFileSelection([], '');
    await loadTerminalDirectory(terminalFilePath.value);
  } catch (error) {
    if (handleTerminalAuthExpired(error)) return;
    terminalFileDeleteDialog.value = {
      ...dialog,
      deleting: false,
      error: error instanceof Error ? error.message : '删除失败',
    };
  }
}

function openTerminalFileCreateDialog(mode: TerminalFileCreateMode) {
  if (!activeTab.value) return;
  const isDirectory = mode === 'directory';
  terminalFileCreateDialog.value = {
    visible: true,
    mode,
    name: mode === 'file' ? 'new-file' : isDirectory ? 'new-folder' : 'new-link',
    targetPath: '',
    octalMode: isDirectory ? '0755' : '0644',
    openAfterCreate: isDirectory,
    saving: false,
    error: '',
  };
}

function closeTerminalFileCreateDialog() {
  if (terminalFileCreateDialog.value.saving) return;
  terminalFileCreateDialog.value = {
    visible: false,
    mode: 'file',
    name: '',
    targetPath: '',
    octalMode: '0644',
    openAfterCreate: false,
    saving: false,
    error: '',
  };
}

async function saveTerminalFileCreateDialog() {
  const dialog = terminalFileCreateDialog.value;
  if (!activeTab.value || !dialog.visible || dialog.saving) return;
  const name = dialog.name.trim();
  if (!name) {
    terminalFileCreateDialog.value = { ...dialog, error: '请输入名称' };
    return;
  }
  if (dialog.mode === 'symlink' && !dialog.targetPath.trim()) {
    terminalFileCreateDialog.value = { ...dialog, error: '请输入目标路径' };
    return;
  }
  terminalFileCreateDialog.value = { ...dialog, saving: true, error: '' };
  try {
    const endpoint =
      dialog.mode === 'file'
        ? 'create-file'
        : dialog.mode === 'directory'
          ? 'create-directory'
          : 'create-symlink';
    const payload =
      dialog.mode === 'file'
        ? { directory: terminalFilePath.value, filename: name, octalMode: normalizeTerminalFileOctalMode(dialog.octalMode) }
        : dialog.mode === 'directory'
          ? { directory: terminalFilePath.value, dirname: name, octalMode: normalizeTerminalFileOctalMode(dialog.octalMode) }
          : { directory: terminalFilePath.value, linkName: name, targetPath: dialog.targetPath.trim() };
    const created = await apiPost<TerminalFileProperties>(`/api/web-terminal/hosts/${activeTab.value.host.id}/files/${endpoint}/`, payload);
    terminalFileCreateDialog.value = {
      visible: false,
      mode: 'file',
      name: '',
      targetPath: '',
      octalMode: '0644',
      openAfterCreate: false,
      saving: false,
      error: '',
    };
    if (dialog.mode === 'directory' && dialog.openAfterCreate) {
      await loadTerminalDirectory(created.path);
      return;
    }
    await loadTerminalDirectory(terminalFilePath.value);
    const createdEntry = terminalFileEntries.value.find((entry) => entry.path === created.path || entry.name === created.name) ?? null;
    setTerminalFileSelection(createdEntry ? [createdEntry] : [], createdEntry?.path ?? '');
  } catch (error) {
    if (handleTerminalAuthExpired(error)) return;
    terminalFileCreateDialog.value = {
      ...dialog,
      saving: false,
      error: error instanceof Error ? error.message : '创建失败',
    };
  }
}

function terminalFileCreateTitle() {
  if (terminalFileCreateDialog.value.mode === 'file') return '新建文件';
  if (terminalFileCreateDialog.value.mode === 'directory') return '新建文件夹';
  return '新建符号链接';
}

function terminalFileCreateNameLabel() {
  if (terminalFileCreateDialog.value.mode === 'directory') return '目录：';
  if (terminalFileCreateDialog.value.mode === 'file') return '文件：';
  return '名称：';
}

function terminalFileCreateOpenLabel() {
  return terminalFileCreateDialog.value.mode === 'directory' ? '创建后打开目录' : '创建后打开文件';
}

function isTerminalFileCreatePermissionChecked(mask: number) {
  const mode = Number.parseInt(terminalFileCreateDialog.value.octalMode || '0', 8) || 0;
  return Boolean(mode & mask);
}

function setTerminalFileCreatePermission(mask: number, checked: boolean) {
  const current = Number.parseInt(terminalFileCreateDialog.value.octalMode || '0', 8) || 0;
  const next = checked ? current | mask : current & ~mask;
  terminalFileCreateDialog.value.octalMode = (next & 0o7777).toString(8).padStart(4, '0');
}

function setTerminalFileCreatePermissionFromEvent(mask: number, event: Event) {
  setTerminalFileCreatePermission(mask, (event.target as HTMLInputElement).checked);
}

function getTerminalFileCreateSpecialOctalDigit() {
  return normalizeTerminalFileOctalMode(terminalFileCreateDialog.value.octalMode).charAt(0);
}

function getTerminalFileCreateStandardOctalMode() {
  return normalizeTerminalFileOctalMode(terminalFileCreateDialog.value.octalMode).slice(1);
}

function updateTerminalFileCreateOctalMode(event: Event) {
  const input = event.target as HTMLInputElement;
  const standardMode = String(input.value || '').replace(/[^0-7]/g, '').slice(-3).padStart(3, '0');
  terminalFileCreateDialog.value.octalMode = `${getTerminalFileCreateSpecialOctalDigit()}${standardMode}`;
}

function openTerminalCurrentDirectoryProperties() {
  if (!activeTab.value) return;
  void openTerminalFileProperties({
    name: currentTerminalDirectoryName(),
    type: 'directory',
    modifiedAt: '',
    path: terminalFilePath.value,
  });
}

function currentTerminalDirectoryName() {
  const value = String(terminalFilePath.value || '.').replace(/\/+$/, '');
  if (!value || value === '.') return '.';
  if (value === '/') return '/';
  return value.split('/').filter(Boolean).pop() || value;
}

async function openTerminalFileProperties(entry: TerminalFileEntry) {
  if (!activeTab.value || isParentDirectoryEntry(entry)) return;
  setTerminalFileSelection([entry], entry.path);
  terminalFilePropertiesDialog.value = {
    visible: true,
    loading: true,
    saving: false,
    error: '',
    entry,
    properties: null,
    draft: { owner: '', group: '', octalMode: '0000' },
    recursive: false,
  };
  try {
    const properties = mergeTerminalFilePropertiesEntryIdentity(
      await apiPost<TerminalFileProperties>(
        `/api/web-terminal/hosts/${activeTab.value.host.id}/files/properties/`,
        { path: entry.path },
      ),
      entry,
    );
    terminalFilePropertiesDialog.value = {
      ...terminalFilePropertiesDialog.value,
      loading: false,
      properties,
      draft: {
        owner: getTerminalFileOwnerLabel(properties),
        group: getTerminalFileGroupLabel(properties),
        octalMode: normalizeTerminalFileOctalMode(properties.octalMode),
      },
    };
  } catch (error) {
    if (handleTerminalAuthExpired(error)) return;
    terminalFilePropertiesDialog.value = {
      ...terminalFilePropertiesDialog.value,
      loading: false,
      error: error instanceof Error ? error.message : '属性读取失败',
    };
  }
}

function closeTerminalFilePropertiesDialog() {
  if (terminalFilePropertiesDialog.value.saving) return;
  terminalFilePropertiesDialog.value = {
    visible: false,
    loading: false,
    saving: false,
    error: '',
    entry: null,
    properties: null,
    draft: { owner: '', group: '', octalMode: '0000' },
    recursive: false,
  };
}

async function saveTerminalFileProperties() {
  const dialog = terminalFilePropertiesDialog.value;
  if (!activeTab.value || !dialog.properties || dialog.loading || dialog.saving) return;
  const recursive = dialog.properties.type === 'directory' && dialog.recursive;
  if (recursive && !window.confirm('确认要将所有权和权限递归应用到此目录及所有子目录/文件吗？')) return;
  terminalFilePropertiesDialog.value = { ...dialog, saving: true, error: '' };
  try {
    const properties = await apiPost<TerminalFileProperties>(
      `/api/web-terminal/hosts/${activeTab.value.host.id}/files/properties/update/`,
      {
        path: dialog.properties.path,
        owner: dialog.draft.owner,
        group: dialog.draft.group,
        octalMode: normalizeTerminalFileOctalMode(dialog.draft.octalMode),
        recursive,
      },
    );
    terminalFilePropertiesDialog.value = {
      ...terminalFilePropertiesDialog.value,
      saving: false,
      properties,
      draft: {
        owner: getTerminalFileOwnerLabel(properties),
        group: getTerminalFileGroupLabel(properties),
        octalMode: normalizeTerminalFileOctalMode(properties.octalMode),
      },
      recursive: false,
    };
    closeTerminalFilePropertiesDialog();
    await loadTerminalDirectory(terminalFilePath.value);
  } catch (error) {
    if (handleTerminalAuthExpired(error)) return;
    terminalFilePropertiesDialog.value = {
      ...terminalFilePropertiesDialog.value,
      saving: false,
      error: error instanceof Error ? error.message : '属性保存失败',
    };
  }
}

async function loadTerminalDirectory(path = terminalFilePath.value) {
  if (!activeTab.value) return;
  closeTerminalContextMenus();
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
    terminalFileEntries.value = sortTerminalFileEntries(response.entries);
    terminalFileListProtocol.value = response.protocol;
    syncTerminalFileSelectionAfterEntriesChange();
  } catch (error) {
    if (handleTerminalAuthExpired(error)) return;
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

function toggleTerminalFileCwdFollow() {
  isTerminalFileFollowingCwd.value = !isTerminalFileFollowingCwd.value;
  if (isTerminalFileFollowingCwd.value && activeTab.value?.currentCwd) {
    void loadTerminalDirectory(activeTab.value.currentCwd);
  }
}

function getTerminalFileDeleteDialogEntries() {
  const dialog = terminalFileDeleteDialog.value;
  return dialog.entries.length ? dialog.entries : dialog.entry ? [dialog.entry] : [];
}

function getTerminalFileDeleteDialogVisualType() {
  const entries = getTerminalFileDeleteDialogEntries();
  if (entries.length === 1) return entries[0].type;
  return entries.length > 0 && entries.every((entry) => entry.type === 'directory') ? 'directory' : 'file';
}

function getTerminalFileDeleteDialogTitle() {
  const entries = getTerminalFileDeleteDialogEntries();
  if (entries.length > 1) return `确定要删除所选 ${entries.length} 项吗？`;
  return `确定要删除“${entries[0]?.name ?? ''}”吗？`;
}

function getTerminalFileDeleteDialogDescription() {
  const entries = getTerminalFileDeleteDialogEntries();
  if (entries.length <= 1) {
    return `此操作会从远端主机删除该${entries[0]?.type === 'directory' ? '目录及其内容' : '文件'}。`;
  }
  const directoryCount = entries.filter((entry) => entry.type === 'directory').length;
  const fileCount = entries.length - directoryCount;
  if (directoryCount && fileCount) return `此操作会从远端主机删除 ${fileCount} 个文件和 ${directoryCount} 个目录及其内容。`;
  if (directoryCount) return `此操作会从远端主机删除 ${directoryCount} 个目录及其内容。`;
  return `此操作会从远端主机删除 ${fileCount} 个文件。`;
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
  if (!value || value === '.' || value === '~') return '/';
  if (value === '/') return '/';
  if (value.startsWith('~/')) {
    const parent = value.slice(0, value.lastIndexOf('/'));
    return parent || '/';
  }
  if (!value.startsWith('/')) return '/';
  const parent = value.slice(0, value.lastIndexOf('/'));
  return parent || '/';
}

function isParentDirectoryEntry(entry: TerminalFileEntry | null | undefined) {
  return entry?.type === 'directory' && entry.name === '..';
}

function sortTerminalFileEntries(entries: TerminalFileEntry[]) {
  const parentEntries = entries.filter(isParentDirectoryEntry);
  const normalEntries = entries.filter((entry) => !isParentDirectoryEntry(entry));
  normalEntries.sort(compareTerminalFileEntries);
  return [...parentEntries.slice(0, 1), ...normalEntries];
}

function compareTerminalFileEntries(left: TerminalFileEntry, right: TerminalFileEntry) {
  const leftRank = getTerminalFileSortRank(left);
  const rightRank = getTerminalFileSortRank(right);
  if (leftRank !== rightRank) return leftRank - rightRank;
  return left.name.localeCompare(right.name, undefined, { numeric: true, sensitivity: 'base' });
}

function getTerminalFileSortRank(entry: TerminalFileEntry) {
  if (entry.name.startsWith('.')) return 0;
  if (entry.type === 'directory') return 1;
  return 2;
}

function getDefaultSelectedTerminalFile(entries: TerminalFileEntry[]) {
  return entries.find((entry) => entry.type === 'file') ?? entries.find((entry) => entry.type === 'directory' && !isParentDirectoryEntry(entry)) ?? null;
}

function formatTerminalFileProtocol(protocol: string) {
  const value = protocol.trim().toLowerCase();
  if (!value) return '';
  if (value.includes('sftp')) return 'SFTP';
  if (value.includes('enhanced')) return 'SCP enhanced';
  if (value.includes('scp')) return 'SCP normal';
  return protocol;
}

function formatTerminalFileSize(entry: TerminalFileEntry) {
  if (entry.type === 'directory') return '-';
  if (entry.size === undefined || entry.size === null || entry.size === '') return '-';
  return formatTerminalFileSizeValue(entry.size);
}

function formatTerminalFilePropertiesSize(properties: TerminalFileProperties | null) {
  if (!properties) return '-';
  return formatTerminalFileSizeValue(properties.size);
}

function formatTerminalFileSizeValue(size: number | string) {
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  if (typeof size === 'string') return size;
  let valueSize = size;
  let unitIndex = 0;
  while (valueSize >= 1024 && unitIndex < units.length - 1) {
    valueSize /= 1024;
    unitIndex += 1;
  }
  const value = unitIndex === 0 ? String(valueSize) : valueSize.toFixed(valueSize >= 10 ? 1 : 2).replace(/\.0+$/, '');
  return `${value} ${units[unitIndex]}`;
}

function terminalFileText(value?: string | number) {
  if (value === undefined || value === null || value === '') return '-';
  return String(value);
}

function getTerminalFileDirectoryPath(entry: TerminalFileEntry) {
  if (isParentDirectoryEntry(entry)) return parentTerminalDirectoryPath(terminalFilePath.value);
  if (entry.type === 'directory') return entry.path;
  return parentTerminalDirectoryPath(entry.path);
}

function getTerminalFileResolvedPath(entry: TerminalFileEntry) {
  if (isParentDirectoryEntry(entry)) return parentTerminalDirectoryPath(terminalFilePath.value);
  return entry.path;
}

async function copyTerminalFileText(value: string) {
  if (!value) return;
  await navigator.clipboard?.writeText(value);
}

function sendTerminalFileTextToActiveTerminal(value: string) {
  if (!value || !activeTab.value) return;
  activeTab.value.terminal.write(value);
  activeTab.value.terminal.focus();
}

function getTerminalFilePropertiesTypeLabel(properties: TerminalFileProperties | null) {
  if (!properties) return '-';
  return properties.type === 'directory' ? '文件夹' : '文件';
}

function getTerminalFileOwnerLabel(properties: TerminalFileProperties | null) {
  if (!properties) return '-';
  return properties.owner || String(properties.uid);
}

function mergeTerminalFilePropertiesEntryIdentity(properties: TerminalFileProperties, entry: TerminalFileEntry): TerminalFileProperties {
  const owner = shouldUseTerminalFileEntryIdentity(properties.owner, properties.uid, entry.owner) ? String(entry.owner) : properties.owner;
  const group = shouldUseTerminalFileEntryIdentity(properties.group, properties.gid, entry.group) ? String(entry.group) : properties.group;
  if (owner === properties.owner && group === properties.group) return properties;
  return { ...properties, owner, group };
}

function shouldUseTerminalFileEntryIdentity(current: string, numericId: number, entryValue?: string) {
  const value = String(entryValue || '').trim();
  return Boolean(value && value !== '-' && value !== String(numericId) && String(current || '').trim() === String(numericId));
}

function getTerminalFileGroupLabel(properties: TerminalFileProperties | null) {
  if (!properties) return '-';
  return properties.group || String(properties.gid);
}

function normalizeTerminalFileOctalMode(value: string) {
  const normalized = String(value || '').replace(/[^0-7]/g, '').slice(-4);
  return normalized.padStart(4, '0');
}

function updateTerminalFileOctalMode(event: Event) {
  const input = event.target as HTMLInputElement;
  const standardMode = String(input.value || '').replace(/[^0-7]/g, '').slice(-3).padStart(3, '0');
  terminalFilePropertiesDialog.value.draft.octalMode = `${getTerminalFileSpecialOctalDigit()}${standardMode}`;
}

function isTerminalFilePermissionChecked(mask: number) {
  const mode = Number.parseInt(terminalFilePropertiesDialog.value.draft.octalMode || '0', 8) || 0;
  return Boolean(mode & mask);
}

function setTerminalFilePermission(mask: number, checked: boolean) {
  const current = Number.parseInt(terminalFilePropertiesDialog.value.draft.octalMode || '0', 8) || 0;
  const next = checked ? current | mask : current & ~mask;
  terminalFilePropertiesDialog.value.draft.octalMode = (next & 0o7777).toString(8).padStart(4, '0');
}

function setTerminalFilePermissionFromEvent(mask: number, event: Event) {
  setTerminalFilePermission(mask, (event.target as HTMLInputElement).checked);
}

function getTerminalFileSpecialOctalDigit() {
  return normalizeTerminalFileOctalMode(terminalFilePropertiesDialog.value.draft.octalMode).charAt(0);
}

function getTerminalFileStandardOctalMode() {
  return normalizeTerminalFileOctalMode(terminalFilePropertiesDialog.value.draft.octalMode).slice(1);
}

async function downloadTerminalFile(entry = selectedTerminalFile.value) {
  if (!activeTab.value || !entry || isParentDirectoryEntry(entry)) return;
  await downloadTerminalFiles([entry]);
}

async function downloadTerminalFiles(entries = getTerminalFileActionEntries()) {
  const tab = activeTab.value;
  const downloadableEntries = entries.filter((entry) => !isParentDirectoryEntry(entry));
  if (!tab || !downloadableEntries.length) return;
  try {
    terminalFileListError.value = '';
    const directoryHandle = await pickTerminalDownloadDirectory();
    if (!directoryHandle) return;
    const hostId = tab.host.id;
    const usedNames = new Set<string>();
    for (const entry of downloadableEntries) {
      const record = createTerminalTransferRecord('download', entry.name, entry.path, entry.type === 'file' ? 1 : 0);
      if (entry.type === 'directory') {
        await runTerminalTransfer(record, async () => {
          await downloadTerminalDirectory(entry, directoryHandle, usedNames, hostId, record);
        });
        continue;
      }
      await runTerminalTransfer(record, async () => {
        await downloadTerminalFileToDirectory(entry, directoryHandle, usedNames, hostId, record);
      });
    }
  } catch (error) {
    if (isTerminalDownloadAbortError(error)) return;
    if (handleTerminalAuthExpired(error)) return;
    terminalFileListError.value = error instanceof Error ? error.message : '下载失败';
  }
}

function getTerminalFileDownloadUrl(entry: TerminalFileEntry) {
  if (!activeTab.value) return '';
  return getTerminalFileDownloadRawUrl(activeTab.value.host.id, entry.path, terminalDownloadProtocol.value);
}

function getTerminalFileDownloadRawUrl(hostId: number, path: string, protocol: TerminalDownloadProtocol) {
  const params = new URLSearchParams({ path, protocol });
  return `/api/web-terminal/hosts/${hostId}/files/download/raw/?${params.toString()}`;
}

async function downloadTerminalDirectory(
  entry: TerminalFileEntry,
  directoryHandle: TerminalLocalDirectoryHandle,
  usedNames: Set<string>,
  hostId: number,
  record?: TerminalTransferRecord,
) {
  throwIfTerminalTransferCanceled(record);
  const directoryName = getUniqueTerminalDownloadFilename(sanitizeTerminalLocalFilename(entry.name || 'download'), usedNames);
  const childDirectoryHandle = await directoryHandle.getDirectoryHandle(directoryName, { create: true });
  await downloadTerminalDirectoryContents(entry.path, childDirectoryHandle, hostId, record);
}

async function downloadTerminalDirectoryContents(
  path: string,
  directoryHandle: TerminalLocalDirectoryHandle,
  hostId: number,
  record?: TerminalTransferRecord,
) {
  throwIfTerminalTransferCanceled(record);
  const response = await apiPost<TerminalFileListResponse>(
    `/api/web-terminal/hosts/${hostId}/files/list-download/`,
    { path },
    getTerminalTransferRequestOptions(record),
  );
  const usedNames = new Set<string>();
  const files = response.entries.filter((child) => child.type === 'file' && !isParentDirectoryEntry(child));
  const directories = response.entries.filter((child) => child.type === 'directory' && !isParentDirectoryEntry(child));
  if (record && files.length) incrementTerminalTransferTotal(record, files.length);
  for (const child of directories) {
    throwIfTerminalTransferCanceled(record);
    await downloadTerminalDirectory(child, directoryHandle, usedNames, hostId, record);
  }
  await runTerminalTransferPool(files, TERMINAL_DOWNLOAD_FILE_CONCURRENCY, async (child) => {
    throwIfTerminalTransferCanceled(record);
    await downloadTerminalFileToDirectory(child, directoryHandle, usedNames, hostId, record);
  });
}

async function downloadTerminalFileToDirectory(
  entry: TerminalFileEntry,
  directoryHandle: TerminalLocalDirectoryHandle,
  usedNames: Set<string>,
  hostId: number,
  record?: TerminalTransferRecord,
) {
  throwIfTerminalTransferCanceled(record);
  setTerminalTransferCurrentFile(record, entry.name);
  const response = await fetch(getTerminalFileDownloadRawUrl(hostId, entry.path, terminalDownloadProtocol.value), {
    credentials: 'include',
    ...getTerminalTransferRequestOptions(record),
  });
  if (response.status === 401) throw new ApiUnauthorizedError(await readTerminalDownloadError(response));
  if (!response.ok) throw new Error(await readTerminalDownloadError(response));
  throwIfTerminalTransferCanceled(record);
  const filename = getTerminalDownloadFilename(entry, getTerminalDownloadResponseFilename(response), usedNames);
  await writeTerminalResponseToDirectory(directoryHandle, filename, response, record);
  completeTerminalTransferFile(record);
}

async function runTerminalTransferPool<T>(items: T[], concurrency: number, worker: (item: T) => Promise<void>) {
  let cursor = 0;
  const workerCount = Math.min(Math.max(1, concurrency), items.length);
  await Promise.all(
    Array.from({ length: workerCount }, async () => {
      while (cursor < items.length) {
        const item = items[cursor];
        cursor += 1;
        await worker(item);
      }
    }),
  );
}

async function pickTerminalDownloadDirectory() {
  const picker = (window as TerminalDirectoryPickerWindow).showDirectoryPicker;
  if (!picker) {
    throw new Error('当前浏览器不支持选择下载目录，请使用新版 Chrome 或 Edge，并通过 HTTPS 或 localhost 打开。');
  }
  return picker({ id: TERMINAL_DOWNLOAD_DIRECTORY_PICKER_ID, mode: 'readwrite' });
}

async function writeTerminalBlobToDirectory(directoryHandle: TerminalLocalDirectoryHandle, filename: string, blob: Blob) {
  const fileHandle = await directoryHandle.getFileHandle(filename, { create: true });
  const writable = await fileHandle.createWritable();
  try {
    await writable.write(blob);
    await writable.close();
  } catch (error) {
    await writable.abort?.();
    throw error;
  }
}

async function writeTerminalResponseToDirectory(
  directoryHandle: TerminalLocalDirectoryHandle,
  filename: string,
  response: Response,
  record?: TerminalTransferRecord,
) {
  const fileHandle = await directoryHandle.getFileHandle(filename, { create: true });
  const writable = await fileHandle.createWritable();
  const totalBytes = Number(response.headers.get('Content-Length') || 0);
  updateTerminalTransferBytes(record, {
    currentBytes: 0,
    currentTotalBytes: Number.isFinite(totalBytes) && totalBytes > 0 ? totalBytes : 0,
  });
  try {
    if (!response.body) {
      const blob = await response.blob();
      throwIfTerminalTransferCanceled(record);
      await writable.write(blob);
      updateTerminalTransferBytes(record, { currentBytes: blob.size });
      await writable.close();
      return;
    }
    const reader = response.body.getReader();
    let writtenBytes = 0;
    while (true) {
      throwIfTerminalTransferCanceled(record);
      const { done, value } = await reader.read();
      if (done) break;
      if (!value) continue;
      await writable.write(value);
      writtenBytes += value.byteLength;
      updateTerminalTransferBytes(record, { currentBytes: writtenBytes });
    }
    throwIfTerminalTransferCanceled(record);
    await writable.close();
  } catch (error) {
    await writable.abort?.();
    throw error;
  }
}

function updateTerminalTransferBytes(record: TerminalTransferRecord | undefined, patch: Pick<Partial<TerminalTransferRecord>, 'currentBytes' | 'currentTotalBytes'>) {
  if (!record) return;
  updateTerminalTransferRecord(record, patch);
}

async function readTerminalDownloadError(response: Response) {
  const text = await response.text();
  if (!text) return '下载失败';
  try {
    const payload = JSON.parse(text) as { error?: unknown };
    return typeof payload.error === 'string' && payload.error ? payload.error : '下载失败';
  } catch {
    return text;
  }
}

function getTerminalDownloadResponseFilename(response: Response) {
  const disposition = response.headers.get('Content-Disposition') || '';
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  if (encoded) {
    try {
      return decodeURIComponent(encoded);
    } catch {
      return encoded;
    }
  }
  const quoted = disposition.match(/filename="?([^";]+)"?/i)?.[1];
  return quoted || '';
}

function getTerminalDownloadFilename(entry: TerminalFileEntry, responseFilename: string, usedNames: Set<string>) {
  return getUniqueTerminalDownloadFilename(
    sanitizeTerminalLocalFilename(responseFilename || entry.name || 'download'),
    usedNames,
  );
}

function sanitizeTerminalLocalFilename(filename: string) {
  const replaced = String(filename || 'download')
    .replace(TERMINAL_LOCAL_FILENAME_RESERVED_CHARS, '_')
    .replace(/[. ]+$/g, '')
    .trim();
  const safeName = replaced || 'download';
  return TERMINAL_LOCAL_FILENAME_RESERVED_NAMES.has(safeName.toUpperCase()) ? `${safeName}_` : safeName;
}

function getUniqueTerminalDownloadFilename(filename: string, usedNames: Set<string>) {
  if (!usedNames.has(filename.toLowerCase())) {
    usedNames.add(filename.toLowerCase());
    return filename;
  }
  const extensionIndex = filename.lastIndexOf('.');
  const hasExtension = extensionIndex > 0;
  const baseName = hasExtension ? filename.slice(0, extensionIndex) : filename;
  const extension = hasExtension ? filename.slice(extensionIndex) : '';
  let index = 2;
  let nextName = `${baseName} (${index})${extension}`;
  while (usedNames.has(nextName.toLowerCase())) {
    index += 1;
    nextName = `${baseName} (${index})${extension}`;
  }
  usedNames.add(nextName.toLowerCase());
  return nextName;
}

function isTerminalDownloadAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError';
}

function startTerminalFileDragDownload(entry: TerminalFileEntry, event: DragEvent) {
  if (!activeTab.value || entry.type !== 'file' || isParentDirectoryEntry(entry) || !event.dataTransfer) return;
  if (!isTerminalFileSelected(entry)) setTerminalFileSelection([entry], entry.path);
  selectedTerminalFile.value = entry;
  const downloadableEntries = getTerminalFileDragDownloadEntries(entry);
  if (!downloadableEntries.length) return;
  const downloadItems = downloadableEntries.map((item) => ({
    mimeType: 'application/octet-stream',
    filename: item.name,
    url: new URL(getTerminalFileDownloadUrl(item), window.location.origin).toString(),
  }));
  event.dataTransfer.effectAllowed = 'copy';
  const firstItem = downloadItems[0];
  event.dataTransfer.setData('DownloadURL', `${firstItem.mimeType}:${firstItem.filename}:${firstItem.url}`);
  if (downloadItems.length === 1) {
    event.dataTransfer.setData('text/uri-list', firstItem.url);
    event.dataTransfer.setData('text/plain', firstItem.filename);
    return;
  }
  event.dataTransfer.setData('DownloadURL-list', JSON.stringify(downloadItems));
  event.dataTransfer.setData('text/uri-list', downloadItems.map((item) => item.url).join('\n'));
  event.dataTransfer.setData('text/plain', downloadItems.map((item) => item.filename).join('\n'));
}

function getTerminalFileDragDownloadEntries(entry: TerminalFileEntry) {
  const selectedEntries = selectedTerminalFiles.value.filter((item) => item.type === 'file' && !isParentDirectoryEntry(item));
  if (isTerminalFileSelected(entry) && selectedEntries.length) return selectedEntries;
  return entry.type === 'file' && !isParentDirectoryEntry(entry) ? [entry] : [];
}

function openTerminalUpload() {
  if (!activeTab.value || isParentDirectoryEntry(selectedTerminalFile.value)) return;
  closeTerminalContextMenus();
  terminalFileUploadInput.value?.click();
}

function openTerminalFolderUpload() {
  if (!activeTab.value) return;
  closeTerminalContextMenus();
  terminalFolderUploadInput.value?.click();
}

async function uploadTerminalFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (!activeTab.value || !file) return;
  await uploadTerminalFiles([{ file }]);
}

async function uploadTerminalFolder(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  input.value = '';
  if (!activeTab.value || !files.length) return;
  await uploadTerminalFiles(
    files.map((file) => ({
      file,
      relativePath: (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name,
    })),
  );
}

async function uploadTerminalFiles(items: TerminalFileUploadItem[]) {
  const tab = activeTab.value;
  if (!tab || !items.length) return;
  const targetDirectory = terminalFilePath.value;
  try {
    terminalFileListError.value = '';
    const groups = groupTerminalUploadItems(items);
    for (const group of groups) {
      const record = createTerminalTransferRecord('upload', group.name, targetDirectory, group.items.length);
      await runTerminalTransfer(record, async () => {
        for (const item of group.items) {
          throwIfTerminalTransferCanceled(record);
          const file = item.file;
          setTerminalTransferCurrentFile(record, item.relativePath || file.name);
          const contentBase64 = await fileToBase64(file);
          throwIfTerminalTransferCanceled(record);
          await apiPost<{ protocol: string }>(
            `/api/web-terminal/hosts/${tab.host.id}/files/upload/`,
            { directory: targetDirectory, filename: file.name, relativePath: item.relativePath || '', contentBase64 },
            getTerminalTransferRequestOptions(record),
          );
          completeTerminalTransferFile(record);
        }
      });
    }
    if (activeTab.value?.id === tab.id && terminalFilePath.value === targetDirectory) {
      await loadTerminalDirectory(targetDirectory);
    }
  } catch (error) {
    if (isTerminalTransferCancelError(error)) return;
    if (handleTerminalAuthExpired(error)) return;
    terminalFileListError.value = error instanceof Error ? error.message : '文件上传失败';
  } finally {
    isTerminalFileDragOver.value = false;
  }
}

function onTerminalFileDragEnter(event: DragEvent) {
  if (!activeTab.value || !hasLocalDragFiles(event)) return;
  event.preventDefault();
  isTerminalFileDragOver.value = true;
}

function onTerminalFileDragOver(event: DragEvent) {
  if (!activeTab.value || !hasLocalDragFiles(event)) return;
  event.preventDefault();
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy';
  isTerminalFileDragOver.value = true;
}

function onTerminalFileDragLeave(event: DragEvent) {
  if (!(event.currentTarget instanceof HTMLElement)) return;
  const nextTarget = event.relatedTarget;
  if (nextTarget instanceof Node && event.currentTarget.contains(nextTarget)) return;
  isTerminalFileDragOver.value = false;
}

async function onTerminalFileDrop(event: DragEvent) {
  if (!activeTab.value || !hasLocalDragFiles(event)) return;
  event.preventDefault();
  isTerminalFileDragOver.value = false;
  const items = await getDroppedUploadItems(event);
  if (!items.length) return;
  await uploadTerminalFiles(items);
}

function hasLocalDragFiles(event: DragEvent) {
  return Array.from(event.dataTransfer?.types || []).includes('Files');
}

async function getDroppedUploadItems(event: DragEvent): Promise<TerminalFileUploadItem[]> {
  const entries = Array.from(event.dataTransfer?.items || [])
    .map((item) => getTerminalDroppedFileSystemEntry(item))
    .filter((entry): entry is TerminalFileSystemEntry => Boolean(entry));
  if (entries.length) {
    return (await Promise.all(entries.map((entry) => readTerminalDroppedEntry(entry)))).flat();
  }
  return Array.from(event.dataTransfer?.files || []).map((file) => ({ file, relativePath: getDroppedFileRelativePath(file) }));
}

function getTerminalDroppedFileSystemEntry(item: DataTransferItem): TerminalFileSystemEntry | null {
  const maybeEntryItem = item as DataTransferItem & { webkitGetAsEntry?: () => TerminalFileSystemEntry | null };
  return maybeEntryItem.webkitGetAsEntry?.() ?? null;
}

async function readTerminalDroppedEntry(entry: TerminalFileSystemEntry, parentPath = ''): Promise<TerminalFileUploadItem[]> {
  const relativePath = parentPath ? `${parentPath}/${entry.name}` : entry.name;
  if (entry.isFile && entry.file) {
    const file = await readTerminalDroppedFile(entry);
    return [{ file, relativePath }];
  }
  if (!entry.isDirectory || !entry.createReader) return [];
  const children = await readTerminalDroppedDirectoryEntries(entry);
  return (await Promise.all(children.map((child) => readTerminalDroppedEntry(child, relativePath)))).flat();
}

function readTerminalDroppedFile(entry: TerminalFileSystemEntry): Promise<File> {
  return new Promise((resolve, reject) => {
    entry.file?.(resolve, reject);
  });
}

function readTerminalDroppedDirectoryEntries(entry: TerminalFileSystemEntry): Promise<TerminalFileSystemEntry[]> {
  const reader = entry.createReader?.();
  if (!reader) return Promise.resolve([]);
  const entries: TerminalFileSystemEntry[] = [];
  return new Promise((resolve, reject) => {
    const readBatch = () => {
      reader.readEntries((batch) => {
        if (!batch.length) {
          resolve(entries);
          return;
        }
        entries.push(...batch);
        readBatch();
      }, reject);
    };
    readBatch();
  });
}

function getDroppedFileRelativePath(file: File) {
  return (file as File & { webkitRelativePath?: string }).webkitRelativePath || '';
}

function groupTerminalUploadItems(items: TerminalFileUploadItem[]) {
  const groups = new Map<string, TerminalFileUploadItem[]>();
  for (const item of items) {
    const key = item.relativePath ? item.relativePath.replace(/\\/g, '/').split('/')[0] || item.file.name : item.file.name;
    groups.set(key, [...(groups.get(key) ?? []), item]);
  }
  return Array.from(groups, ([name, groupItems]) => ({ name, items: groupItems }));
}

function createTerminalTransferRecord(kind: TerminalTransferKind, name: string, path: string, totalFiles = 0) {
  const now = Date.now();
  const record: TerminalTransferRecord = {
    id: `transfer-${now}-${Math.random().toString(36).slice(2, 8)}`,
    kind,
    status: 'queued',
    name,
    path,
    currentFile: '',
    currentBytes: 0,
    currentTotalBytes: 0,
    completedFiles: 0,
    totalFiles,
    progress: totalFiles > 0 ? 0 : 0,
    error: '',
    canceled: false,
    abortController: new AbortController(),
    createdAt: now,
    updatedAt: now,
  };
  terminalTransferRecords.value = [record, ...terminalTransferRecords.value];
  return record;
}

async function runTerminalTransfer(record: TerminalTransferRecord, work: () => Promise<void>) {
  updateTerminalTransferRecord(record, { status: 'running', error: '' });
  try {
    await work();
    if (record.canceled) {
      updateTerminalTransferRecord(record, { status: 'canceled', progress: record.progress });
      return;
    }
    updateTerminalTransferRecord(record, { status: 'success', progress: 100, currentFile: '' });
  } catch (error) {
    if (isTerminalTransferCancelError(error) || record.canceled) {
      updateTerminalTransferRecord(record, { status: 'canceled' });
      return;
    }
    updateTerminalTransferRecord(record, {
      status: 'error',
      error: error instanceof Error ? error.message : '传输失败',
    });
    throw error;
  }
}

function updateTerminalTransferRecord(record: TerminalTransferRecord, patch: Partial<TerminalTransferRecord>) {
  Object.assign(record, patch, { updatedAt: Date.now() });
  terminalTransferRecords.value = [...terminalTransferRecords.value];
}

function incrementTerminalTransferTotal(record: TerminalTransferRecord | undefined, count: number) {
  if (!record || count <= 0) return;
  updateTerminalTransferRecord(record, {
    totalFiles: record.totalFiles + count,
    progress: calculateTerminalTransferProgress(record.completedFiles, record.totalFiles + count),
  });
}

function setTerminalTransferCurrentFile(record: TerminalTransferRecord | undefined, currentFile: string) {
  if (!record) return;
  updateTerminalTransferRecord(record, { currentFile, currentBytes: 0, currentTotalBytes: 0 });
}

function completeTerminalTransferFile(record: TerminalTransferRecord | undefined) {
  if (!record) return;
  const completedFiles = record.completedFiles + 1;
  const totalFiles = Math.max(record.totalFiles, completedFiles);
  updateTerminalTransferRecord(record, {
    completedFiles,
    totalFiles,
    progress: calculateTerminalTransferProgress(completedFiles, totalFiles),
  });
}

function calculateTerminalTransferProgress(completedFiles: number, totalFiles: number) {
  if (totalFiles <= 0) return 0;
  return Math.max(0, Math.min(100, Math.round((completedFiles / totalFiles) * 100)));
}

function cancelTerminalTransfer(record: TerminalTransferRecord) {
  if (!isTerminalTransferActive(record)) return;
  updateTerminalTransferRecord(record, { canceled: true, status: 'canceled' });
  record.abortController.abort();
}

function cancelAllTerminalTransfers() {
  for (const record of terminalTransferRecords.value) {
    if (isTerminalTransferActive(record)) cancelTerminalTransfer(record);
  }
}

function clearTerminalTransferRecords() {
  terminalTransferRecords.value = terminalTransferRecords.value.filter(isTerminalTransferActive);
}

function isTerminalTransferActive(record: TerminalTransferRecord) {
  return record.status === 'queued' || record.status === 'running';
}

function throwIfTerminalTransferCanceled(record?: TerminalTransferRecord) {
  if (record?.canceled || record?.abortController.signal.aborted) throw new DOMException('传输已取消', 'AbortError');
}

function isTerminalTransferCancelError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError';
}

function getTerminalTransferRequestOptions(record?: TerminalTransferRecord): RequestInit {
  return record ? { signal: record.abortController.signal } : {};
}

function getTerminalDownloadProtocolLabel(protocol = terminalDownloadProtocol.value) {
  if (protocol === 'sftp') return 'SFTP';
  if (protocol === 'scp') return 'SCP';
  return '自动';
}

function getTerminalTransferStatusText(record: TerminalTransferRecord) {
  if (record.status === 'queued') return '等待中';
  if (record.status === 'running') {
    if (!record.currentFile) return '传输中';
    const bytesText =
      record.currentTotalBytes > 0
        ? `（${formatTerminalFileSizeValue(record.currentBytes)} / ${formatTerminalFileSizeValue(record.currentTotalBytes)}）`
        : record.currentBytes > 0
          ? `（${formatTerminalFileSizeValue(record.currentBytes)}）`
          : '';
    return `传输中：${record.currentFile}${bytesText}`;
  }
  if (record.status === 'success') return '已完成';
  if (record.status === 'canceled') return '已取消';
  return record.error || '传输失败';
}

function getTerminalTransferCountText(record: TerminalTransferRecord) {
  if (!record.totalFiles) return record.status === 'running' ? '扫描中' : '0 / 0';
  return `${record.completedFiles} / ${record.totalFiles}`;
}

function getTerminalTransferProgressStyle(record: TerminalTransferRecord): Record<string, string> {
  return { width: `${Math.max(0, Math.min(100, record.progress))}%` };
}

function startTerminalTransferPanelResize(event: MouseEvent) {
  if (event.button !== 0) return;
  event.preventDefault();
  isTerminalTransferPanelResizing.value = true;
  terminalTransferResizeStartY = event.clientY;
  terminalTransferResizeStartHeight = terminalTransferPanelHeight.value;
  window.addEventListener('mousemove', resizeTerminalTransferPanel);
  window.addEventListener('mouseup', stopTerminalTransferPanelResize);
}

function resizeTerminalTransferPanel(event: MouseEvent) {
  if (!isTerminalTransferPanelResizing.value) return;
  const delta = terminalTransferResizeStartY - event.clientY;
  terminalTransferPanelHeight.value = clampTerminalTransferPanelHeight(terminalTransferResizeStartHeight + delta);
}

function stopTerminalTransferPanelResize() {
  if (!isTerminalTransferPanelResizing.value) return;
  isTerminalTransferPanelResizing.value = false;
  window.removeEventListener('mousemove', resizeTerminalTransferPanel);
  window.removeEventListener('mouseup', stopTerminalTransferPanelResize);
}

function syncTerminalTransferPanelHeight() {
  const nextHeight = clampTerminalTransferPanelHeight(terminalTransferPanelHeight.value);
  if (nextHeight !== terminalTransferPanelHeight.value) terminalTransferPanelHeight.value = nextHeight;
}

function clampTerminalTransferPanelHeight(height: number) {
  const browserHeight = terminalFileBrowserRef.value?.getBoundingClientRect().height ?? 0;
  const maxByBrowser = browserHeight ? Math.floor(browserHeight * 0.45) : TERMINAL_TRANSFER_PANEL_MAX_HEIGHT;
  const maxHeight = Math.max(TERMINAL_TRANSFER_PANEL_MIN_HEIGHT, Math.min(TERMINAL_TRANSFER_PANEL_MAX_HEIGHT, maxByBrowser));
  return Math.min(Math.max(height, TERMINAL_TRANSFER_PANEL_MIN_HEIGHT), maxHeight);
}

function toggleTerminalQuickCommandPanel() {
  isTerminalQuickCommandPanelCollapsed.value = !isTerminalQuickCommandPanelCollapsed.value;
  window.localStorage.setItem(
    TERMINAL_QUICK_COMMAND_PANEL_COLLAPSED_STORAGE_KEY,
    isTerminalQuickCommandPanelCollapsed.value ? '1' : '0',
  );
  fitActiveTerminalSoon();
}

function startTerminalQuickCommandPanelResize(event: MouseEvent) {
  if (event.button !== 0 || isTerminalQuickCommandPanelCollapsed.value) return;
  event.preventDefault();
  isTerminalQuickCommandPanelResizing.value = true;
  terminalQuickCommandResizeStartY = event.clientY;
  terminalQuickCommandResizeStartHeight = terminalQuickCommandPanelHeight.value;
  window.addEventListener('mousemove', resizeTerminalQuickCommandPanel);
  window.addEventListener('mouseup', stopTerminalQuickCommandPanelResize);
}

function resizeTerminalQuickCommandPanel(event: MouseEvent) {
  if (!isTerminalQuickCommandPanelResizing.value) return;
  const delta = terminalQuickCommandResizeStartY - event.clientY;
  const nextHeight = clampTerminalQuickCommandPanelHeight(terminalQuickCommandResizeStartHeight + delta);
  terminalQuickCommandPanelHeight.value = nextHeight;
  window.localStorage.setItem(TERMINAL_QUICK_COMMAND_PANEL_HEIGHT_STORAGE_KEY, String(nextHeight));
  fitActiveTerminalSoon();
}

function stopTerminalQuickCommandPanelResize() {
  if (!isTerminalQuickCommandPanelResizing.value) return;
  isTerminalQuickCommandPanelResizing.value = false;
  window.removeEventListener('mousemove', resizeTerminalQuickCommandPanel);
  window.removeEventListener('mouseup', stopTerminalQuickCommandPanelResize);
  fitActiveTerminalSoon();
}

function syncTerminalQuickCommandPanelHeight() {
  const nextHeight = clampTerminalQuickCommandPanelHeight(terminalQuickCommandPanelHeight.value);
  if (nextHeight !== terminalQuickCommandPanelHeight.value) {
    terminalQuickCommandPanelHeight.value = nextHeight;
    window.localStorage.setItem(TERMINAL_QUICK_COMMAND_PANEL_HEIGHT_STORAGE_KEY, String(nextHeight));
  }
}

function clampTerminalQuickCommandPanelHeight(height: number) {
  const viewportHeight = typeof window === 'undefined' ? 0 : window.innerHeight;
  const maxByViewport = viewportHeight ? Math.floor(viewportHeight * 0.46) : TERMINAL_QUICK_COMMAND_PANEL_MAX_HEIGHT;
  const maxHeight = Math.max(
    TERMINAL_QUICK_COMMAND_PANEL_MIN_HEIGHT,
    Math.min(TERMINAL_QUICK_COMMAND_PANEL_MAX_HEIGHT, maxByViewport),
  );
  return Math.min(Math.max(height, TERMINAL_QUICK_COMMAND_PANEL_MIN_HEIGHT), maxHeight);
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

async function loadTerminalMonitor() {
  if (!isTerminalMonitorVisible()) {
    terminalMonitorRequestId += 1;
    isTerminalMonitorLoading.value = false;
    if (!activeTab.value) {
      terminalMonitorData.value = null;
      terminalMonitorError.value = '';
    }
    return;
  }

  const tab = activeTab.value;
  if (!tab) return;

  const requestId = ++terminalMonitorRequestId;
  isTerminalMonitorLoading.value = true;
  try {
    const response = await apiPost<TerminalMonitorResponse>(`/api/web-terminal/hosts/${tab.host.id}/monitor/`, {});
    if (requestId !== terminalMonitorRequestId) return;
    terminalMonitorData.value = response;
    terminalMonitorError.value = '';
  } catch (error) {
    if (handleTerminalAuthExpired(error)) return;
    if (requestId !== terminalMonitorRequestId) return;
    terminalMonitorError.value = error instanceof Error ? error.message : '资源监控读取失败';
  } finally {
    if (requestId === terminalMonitorRequestId) {
      isTerminalMonitorLoading.value = false;
    }
  }
}

function isTerminalMonitorVisible() {
  return (
    isTerminalMonitorPanelOpen.value &&
    document.visibilityState === 'visible' &&
    Boolean(activeTab.value)
  );
}

function syncTerminalMonitorPolling() {
  if (!isTerminalMonitorVisible()) {
    stopTerminalMonitorPolling();
    terminalMonitorRequestId += 1;
    isTerminalMonitorLoading.value = false;
    if (!activeTab.value) {
      terminalMonitorData.value = null;
      terminalMonitorError.value = '';
    }
    return;
  }

  void loadTerminalMonitor();
  startTerminalMonitorPolling();
}

function startTerminalMonitorPolling() {
  if (terminalMonitorTimer) return;
  terminalMonitorTimer = window.setInterval(() => {
    if (isTerminalMonitorVisible()) {
      void loadTerminalMonitor();
    } else {
      syncTerminalMonitorPolling();
    }
  }, TERMINAL_MONITOR_REFRESH_MS);
}

function stopTerminalMonitorPolling() {
  if (!terminalMonitorTimer) return;
  window.clearInterval(terminalMonitorTimer);
  terminalMonitorTimer = null;
}

function formatMonitorPercent(value: number) {
  return `${formatMonitorNumber(value, 1)}%`;
}

function formatMonitorNumber(value: number, digits = 1) {
  if (!Number.isFinite(value)) return '0';
  return Number(value).toFixed(digits).replace(/\.0$/, '');
}

function formatMonitorBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${formatMonitorNumber(value, unitIndex >= 3 ? 2 : 1)} ${units[unitIndex]}`;
}

function formatMonitorRate(bytesPerSecond: number) {
  return `${formatMonitorBytes(bytesPerSecond)}/s`;
}

function formatMonitorUptime(seconds: number) {
  const totalDays = Math.floor(Math.max(0, seconds) / 86400);
  if (totalDays >= 1) return `${totalDays}天`;
  const hours = Math.floor(Math.max(0, seconds) / 3600);
  if (hours >= 1) return `${hours}小时`;
  const minutes = Math.floor(Math.max(0, seconds) / 60);
  return `${minutes}分钟`;
}

function monitorProgressStyle(value: number): Record<string, string> {
  const percent = Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0));
  return {
    '--value': String(percent),
    width: `${percent}%`,
  };
}

watch([activeTabId, terminalSidebarMode], () => {
  closeTerminalContextMenus();
  if (activeTab.value && terminalSidebarMode.value === 'files') {
    terminalFilePath.value = '.';
    void loadTerminalDirectory('.');
    void nextTick(syncTerminalTransferPanelHeight);
  }
  if (
    canUseTerminalQuickCommands.value &&
    terminalSidebarMode.value === 'commands' &&
    !terminalQuickCommands.value.length &&
    !isTerminalQuickCommandLoading.value
  ) {
    void loadTerminalQuickCommands();
  }
  syncTerminalMonitorPolling();
});

watch(activeTabId, (_tabId, previousTabId) => {
  terminalMonitorData.value = null;
  terminalMonitorError.value = '';
  if (previousTabId) clearTerminalSearchDecorations(getTabById(previousTabId));
  resetTerminalSearchResultState();
  if (!activeTab.value) {
    isTerminalSearchOpen.value = false;
    return;
  }
  if (isTerminalSearchOpen.value && terminalSearchQuery.value.trim()) {
    void nextTick(() => searchCurrentTerminal('next', true));
  }
});

watch(terminalSearchQuery, () => {
  if (!isTerminalSearchOpen.value) return;
  searchCurrentTerminal('next', true);
});

watch(isTerminalMonitorPanelOpen, () => {
  syncTerminalMonitorPolling();
  fitActiveTerminalSoon();
});

watch([terminalSplitMode, visibleTerminalTabs], () => {
  void nextTick(fitVisibleTerminalsSoon);
});

const terminalShellStyle = computed<Record<string, string>>(() => ({
  '--terminal-sidebar-width': `${isTerminalSidebarCollapsed.value ? 42 : sidebarWidth.value}px`,
  '--terminal-quick-command-height':
    !shouldShowTerminalQuickCommandPanel.value || isTerminalQuickCommandPanelCollapsed.value ? '0px' : `${terminalQuickCommandPanelHeight.value}px`,
}));
onMounted(async () => {
  window.addEventListener('click', closeTerminalContextMenus);
  window.addEventListener('keydown', closeTerminalFileContextMenuOnEscape);
  window.addEventListener('resize', syncTerminalSidebarWidth);
  window.addEventListener('resize', syncTerminalQuickCommandPanelHeight);
  window.addEventListener('resize', syncTerminalTabsScrollStateSoon);
  window.addEventListener('storage', handleTerminalAuthStorageEvent);
  document.addEventListener('visibilitychange', syncTerminalMonitorPolling);
  try {
    const current = await getCurrentUser();
    terminalCurrentUser.value = current.user;
    if (canUseTerminalQuickCommands.value) await loadTerminalQuickCommands();
    await loadTree();
    if (terminalAuthRedirecting) return;
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
  } catch (error) {
    if (handleTerminalAuthExpired(error)) return;
    throw error;
  }
});

onBeforeUnmount(() => {
  stopSidebarResize();
  stopTerminalTransferPanelResize();
  stopTerminalQuickCommandPanelResize();
  stopTerminalMonitorPolling();
  window.removeEventListener('click', closeTerminalContextMenus);
  window.removeEventListener('keydown', closeTerminalFileContextMenuOnEscape);
  window.removeEventListener('resize', syncTerminalSidebarWidth);
  window.removeEventListener('resize', syncTerminalQuickCommandPanelHeight);
  window.removeEventListener('resize', syncTerminalTabsScrollStateSoon);
  window.removeEventListener('storage', handleTerminalAuthStorageEvent);
  document.removeEventListener('visibilitychange', syncTerminalMonitorPolling);
  for (const tab of tabs.value) disposeTab(tab);
});

function closeTerminalFileContextMenuOnEscape(event: KeyboardEvent) {
  if (event.key !== 'Escape') return;
  if (isTerminalSearchOpen.value) {
    closeTerminalSearch();
    return;
  }
  closeTerminalContextMenus();
  closeTerminalFileDeleteDialog();
  closeTerminalFileCreateDialog();
  cancelTerminalFileRename();
  closeTerminalFilePropertiesDialog();
}

async function loadTree() {
  isLoadingTree.value = true;
  treeError.value = '';
  try {
    groups.value = await apiGet<TerminalGroup[]>('/api/web-terminal/tree/');
  } catch (error) {
    if (handleTerminalAuthExpired(error)) return;
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
  scrollActiveTerminalTabIntoView();
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
  scrollActiveTerminalTabIntoView();
  const tab = tabs.value.find((item) => item.id === tabId);
  if (tab) {
    tab.hasUnreadOutput = false;
    mountTerminal(tab);
    fitTerminal(tab);
    tab.terminal.focus();
    if (isTerminalFileFollowingCwd.value && tab.currentCwd) {
      void loadTerminalDirectory(tab.currentCwd);
    }
  }
}

function createTerminalTab(
  host: TerminalHost,
  tabId = createTerminalTabId(host.id),
  options: { customTitle?: string; colorId?: TerminalTabColorId | null } = {},
): TerminalTab {
  const terminal = markRaw(
    new Terminal({
      cursorBlink: true,
      convertEol: false,
      fontFamily: 'Consolas, "Courier New", monospace',
      fontSize: terminalFontSize.value,
      lineHeight: 1.25,
      scrollback: 5000,
      theme: {
        background: '#000000',
        foreground: '#f5f7fb',
        cursor: '#f5f7fb',
        selectionBackground: '#7e22ce',
      },
    }),
  );
  const fitAddon = markRaw(new FitAddon());
  const searchAddon = markRaw(new SearchAddon({ highlightLimit: 2000 }));
  terminal.loadAddon(fitAddon);
  terminal.loadAddon(searchAddon);
  terminal.attachCustomKeyEventHandler((event) => handleTerminalKey(event, terminal));
  terminal.writeln('CAPTAIN WEB TERMINAL');
  terminal.writeln(`正在连接 ${host.name} (${host.publicIp || host.privateIp}:${host.port})...`);

  const tab: TerminalTab = {
    id: tabId,
    host,
    customTitle: normalizeTerminalTabTitle(options.customTitle),
    colorId: normalizeTerminalTabColorId(options.colorId),
    status: 'connecting',
    terminal,
    fitAddon,
    searchAddon,
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
    currentCwd: '',
    reconnectHintShown: false,
  };
  return tab;
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
      if (tab.status === 'closed' || tab.status === 'error') {
        if (data.includes('\r')) reconnectTerminalTab(tab);
        return;
      }
      if (tab.status === 'connecting') return;

      const sendableData = getSendableTerminalData(tab, data);
      if (!sendableData) return;

      if (sendTerminalInput(tab, sendableData)) {
        broadcastTerminalInputToMultiExecutionTargets(sendableData, tab);
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

function resetTerminalHighlightState(tab: TerminalTab) {
  tab.highlightState = {
    sgrActive: false,
    pendingControl: '',
  };
}

function showTerminalReconnectHint(tab: TerminalTab, reason = '') {
  if (tab.reconnectHintShown) return;
  if (reason) {
    tab.terminal.writeln(`\r\n\x1b[33m${reason}\x1b[0m`);
  }
  tab.terminal.writeln('\x1b[32m[会话已断开]\x1b[0m');
  tab.terminal.writeln('\x1b[32m[按回车键重新连接]\x1b[0m');
  tab.reconnectHintShown = true;
}

function reconnectTerminalTab(tab: TerminalTab) {
  if (terminalAuthRedirecting) return;
  if (tab.status !== 'closed' && tab.status !== 'error') return;
  tab.status = 'connecting';
  tab.sessionId = null;
  tab.currentCwd = '';
  tab.socket = null;
  tab.reconnectHintShown = false;
  resetTerminalHighlightState(tab);
  removePendingConnectTab(tab.id);
  finishConnectingTab(tab);
  tab.terminal.writeln('\r\n\x1b[32m[正在重新连接...]\x1b[0m');
  enqueueConnectTab(tab);
}

function disconnectTerminalTab(tab: TerminalTab) {
  if (!canDisconnectTerminalTab(tab)) return;
  removePendingConnectTab(tab.id);
  finishConnectingTab(tab);
  if (tab.socket && tab.socket.readyState !== WebSocket.CLOSED) {
    tab.socket.close();
  }
  tab.socket = null;
  tab.status = 'closed';
  showTerminalReconnectHint(tab, '连接已手动断开。');
}

function connectTab(tab: TerminalTab) {
  if (terminalAuthRedirecting) return;
  tab.reconnectHintShown = false;
  const socket = new WebSocket(buildWebSocketUrl(tab.host.id));
  tab.socket = socket;

  socket.addEventListener('open', () => fitTerminal(tab));
  socket.addEventListener('message', (event) => handleSocketMessage(tab, event));
  socket.addEventListener('error', () => {
    if (tab.status !== 'closed') {
      tab.status = 'error';
      showTerminalReconnectHint(tab, 'WebSocket 连接失败。');
    }
    finishConnectingTab(tab);
  });
  socket.addEventListener('close', () => {
    tab.socket = null;
    finishConnectingTab(tab);
    if (tab.status === 'connected' || tab.status === 'connecting') {
      tab.status = 'closed';
      showTerminalReconnectHint(tab, '连接已关闭。');
      void confirmTerminalSessionStillAuthenticated();
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
    tab.reconnectHintShown = false;
    finishConnectingTab(tab);
    fitTerminal(tab);
    if (tab.id === activeTabId.value) openTerminalMonitorPanel();
    return;
  }

  if (message.type === 'output') {
    tab.terminal.write(highlightTerminalOutput(message.data ?? '', tab.highlightState));
    if (tab.id !== activeTabId.value) {
      markTabUnread(tab.id);
    }
    return;
  }

  if (message.type === 'cwd') {
    const path = String(message.path || '').trim();
    if (!path) return;
    tab.currentCwd = path;
    if (isTerminalFileFollowingCwd.value && tab.id === activeTabId.value) {
      void loadTerminalDirectory(path);
    }
    return;
  }

  if (message.type === 'error') {
    if (message.message === '请先登录') {
      handleTerminalAuthExpired(new ApiUnauthorizedError(message.message));
      return;
    }
    tab.status = 'error';
    finishConnectingTab(tab);
    showTerminalReconnectHint(tab, message.message ?? '终端连接失败');
    return;
  }

  if (message.type === 'closed') {
    tab.status = 'closed';
    finishConnectingTab(tab);
    showTerminalReconnectHint(tab, message.reason ?? '连接已关闭');
  }
}

async function confirmTerminalSessionStillAuthenticated() {
  try {
    const current = await getCurrentUser();
    terminalCurrentUser.value = current.user;
  } catch (error) {
    handleTerminalAuthExpired(error);
  }
}

function getTabById(tabId: string) {
  return tabs.value.find((item) => item.id === tabId) ?? null;
}

function markTabUnread(tabId: string) {
  const tab = getTabById(tabId);
  if (tab && tab.id !== activeTabId.value && !isTerminalTabVisible(tab)) {
    tab.hasUnreadOutput = true;
  }
}

function isTerminalTabVisible(tab: TerminalTab) {
  return visibleTerminalTabs.value.some((item) => item.id === tab.id);
}

function fitTerminal(tab: TerminalTab) {
  if (!tab.mounted || !isTerminalTabVisible(tab)) return;
  try {
    tab.fitAddon.fit();
    if (tab.socket?.readyState === WebSocket.OPEN) {
      tab.socket.send(JSON.stringify({ type: 'resize', cols: tab.terminal.cols, rows: tab.terminal.rows }));
    }
  } catch {
    // xterm cannot fit until the container has a measurable size.
  }
}

function startSidebarResize(event: MouseEvent, options: { alignToPointer?: boolean } = {}) {
  event.preventDefault();
  if (isTerminalSidebarCollapsed.value) setTerminalSidebarCollapsed(false);
  sidebarResizeStartX = event.clientX;
  sidebarResizeStartWidth = sidebarWidth.value;
  isResizingSidebar.value = true;
  if (options.alignToPointer) {
    sidebarWidth.value = clampTerminalSidebarWidth(event.clientX);
    sidebarResizeStartWidth = sidebarWidth.value;
  }
  window.addEventListener('mousemove', resizeSidebar);
  window.addEventListener('mouseup', stopSidebarResize);
  document.body.classList.add('terminal-resizing');
}

function resizeSidebar(event: MouseEvent) {
  if (!isResizingSidebar.value) return;
  const nextWidth = clampTerminalSidebarWidth(sidebarResizeStartWidth + event.clientX - sidebarResizeStartX);
  sidebarWidth.value = nextWidth;
  window.localStorage.setItem(TERMINAL_SIDEBAR_WIDTH_STORAGE_KEY, String(nextWidth));
  fitActiveTerminalSoon();
}

function clampTerminalSidebarWidth(width: number) {
  const viewportWidth = typeof window === 'undefined' ? 0 : window.innerWidth;
  const maxWidth = Math.max(
    TERMINAL_SIDEBAR_MIN_WIDTH,
    viewportWidth - TERMINAL_WORKSPACE_MIN_WIDTH,
  );
  return Math.min(Math.max(width, TERMINAL_SIDEBAR_MIN_WIDTH), maxWidth);
}

function syncTerminalSidebarWidth() {
  if (isTerminalSidebarCollapsed.value) {
    fitActiveTerminalSoon();
    syncTerminalTransferPanelHeight();
    return;
  }
  const nextWidth = clampTerminalSidebarWidth(sidebarWidth.value);
  if (nextWidth !== sidebarWidth.value) {
    sidebarWidth.value = nextWidth;
    window.localStorage.setItem(TERMINAL_SIDEBAR_WIDTH_STORAGE_KEY, String(nextWidth));
  }
  syncTerminalTransferPanelHeight();
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

function selectTerminalSidebarMode(mode: TerminalSidebarMode) {
  if (mode === 'commands' && !shouldShowTerminalQuickCommandPanel.value) return;
  terminalSidebarMode.value = mode;
  if (mode === 'commands' && isTerminalQuickCommandPanelCollapsed.value) {
    toggleTerminalQuickCommandPanel();
  }
  if (mode === 'commands') {
    setTerminalSidebarCollapsed(true);
    return;
  }
  if (isTerminalSidebarCollapsed.value) setTerminalSidebarCollapsed(false);
}

function toggleTerminalQuickCommandFromRail() {
  if (!shouldShowTerminalQuickCommandPanel.value) return;
  toggleTerminalQuickCommandPanel();
}

function openTerminalMonitorPanel() {
  if (isTerminalMonitorPanelOpen.value) {
    syncTerminalMonitorPolling();
    fitActiveTerminalSoon();
    return;
  }
  isTerminalMonitorPanelOpen.value = true;
}

function closeTerminalMonitorPanel() {
  if (!isTerminalMonitorPanelOpen.value) return;
  isTerminalMonitorPanelOpen.value = false;
}

function toggleTerminalMonitorPanel() {
  if (isTerminalMonitorPanelOpen.value) {
    closeTerminalMonitorPanel();
  } else {
    openTerminalMonitorPanel();
  }
}

function toggleTerminalSidebar() {
  setTerminalSidebarCollapsed(!isTerminalSidebarCollapsed.value);
}

function setTerminalSidebarCollapsed(collapsed: boolean) {
  isTerminalSidebarCollapsed.value = collapsed;
  window.localStorage.setItem(TERMINAL_SIDEBAR_COLLAPSED_STORAGE_KEY, collapsed ? '1' : '0');
  if (collapsed) stopSidebarResize();
  closeTerminalContextMenus();
  fitActiveTerminalSoon();
}

function fitActiveTerminalSoon() {
  fitVisibleTerminalsSoon();
}

function fitVisibleTerminalsSoon() {
  window.requestAnimationFrame(() => {
    for (const tab of visibleTerminalTabs.value) fitTerminal(tab);
  });
}

function setTerminalFontSize(nextSize: number) {
  const normalized = clampTerminalFontSize(nextSize);
  if (normalized === terminalFontSize.value) return;
  terminalFontSize.value = normalized;
  window.localStorage.setItem(TERMINAL_FONT_SIZE_STORAGE_KEY, String(normalized));
  for (const tab of tabs.value) {
    tab.terminal.options.fontSize = normalized;
  }
  fitActiveTerminalSoon();
}

function decreaseTerminalFontSize() {
  setTerminalFontSize(terminalFontSize.value - 1);
}

function increaseTerminalFontSize() {
  setTerminalFontSize(terminalFontSize.value + 1);
}

async function closeTab(tab: TerminalTab) {
  closeTerminalTabMenu();
  closeTerminalTabContextMenu();
  await closeTerminalTabs([tab]);
}

async function closeTerminalTabs(targetTabs: TerminalTab[]) {
  const closingIds = new Set(targetTabs.map((tab) => tab.id));
  if (!closingIds.size) return;

  const currentTabs = tabs.value;
  const firstClosingIndex = currentTabs.findIndex((tab) => closingIds.has(tab.id));
  const previousActiveId = activeTabId.value;
  const remainingTabs = currentTabs.filter((tab) => !closingIds.has(tab.id));
  for (const tab of currentTabs) {
    if (!closingIds.has(tab.id)) continue;
    disposeTab(tab);
    terminalContainers.delete(tab.id);
  }
  tabs.value = remainingTabs;
  pruneTerminalMultiExecutionExclusions();
  await nextTick();

  if (previousActiveId && !closingIds.has(previousActiveId) && remainingTabs.some((tab) => tab.id === previousActiveId)) {
    activeTabId.value = previousActiveId;
    await activateTab(previousActiveId);
  } else {
    const nextTab = remainingTabs[Math.min(Math.max(firstClosingIndex, 0), remainingTabs.length - 1)] ?? null;
    activeTabId.value = nextTab?.id ?? null;
    if (nextTab) await activateTab(nextTab.id);
  }
  if (!activeTabId.value) closeTerminalMonitorPanel();
  saveTerminalWorkspace();
  syncTerminalTabsScrollStateSoon();
}

async function restoreTerminalWorkspace() {
  const workspace = loadTerminalWorkspace();
  if (!workspace?.tabs.length || treeError.value) return;

  const restoredTabs = workspace.tabs
    .map((item) => {
      const host = findHostById(groups.value, item.hostId);
      return host ? createTerminalTab(host, item.id, { customTitle: item.title, colorId: item.colorId ?? null }) : null;
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
  scrollActiveTerminalTabIntoView();
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
      const title = normalizeTerminalTabTitle((item as Partial<PersistedTerminalTab>).title);
      const colorId = normalizeTerminalTabColorId((item as Partial<PersistedTerminalTab>).colorId);
      return [{
        id,
        hostId,
        ...(title ? { title } : {}),
        ...(colorId ? { colorId } : {}),
      }];
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
    tabs: tabs.value.map((tab) => ({
      id: tab.id,
      hostId: tab.host.id,
      ...(tab.customTitle ? { title: tab.customTitle } : {}),
      ...(tab.colorId ? { colorId: tab.colorId } : {}),
    })),
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
  if (typeof window === 'undefined') return TERMINAL_SIDEBAR_DEFAULT_WIDTH;
  const saved = Number(window.localStorage.getItem(TERMINAL_SIDEBAR_WIDTH_STORAGE_KEY));
  if (!Number.isFinite(saved)) return TERMINAL_SIDEBAR_DEFAULT_WIDTH;
  return clampTerminalSidebarWidth(saved);
}

function readTerminalSidebarCollapsed() {
  if (typeof window === 'undefined') return false;
  return window.localStorage.getItem(TERMINAL_SIDEBAR_COLLAPSED_STORAGE_KEY) === '1';
}

function readTerminalFontSize() {
  if (typeof window === 'undefined') return TERMINAL_FONT_SIZE_DEFAULT;
  return readStoredTerminalFontSize(window.localStorage.getItem(TERMINAL_FONT_SIZE_STORAGE_KEY));
}

function readTerminalSplitMode(): TerminalSplitMode {
  if (typeof window === 'undefined') return 'single';
  const saved = window.localStorage.getItem(TERMINAL_SPLIT_MODE_STORAGE_KEY);
  return saved === 'auto' || saved === 'horizontal' || saved === 'vertical' ? saved : 'single';
}

function readTerminalQuickCommandPanelHeight() {
  if (typeof window === 'undefined') return TERMINAL_QUICK_COMMAND_PANEL_DEFAULT_HEIGHT;
  const saved = Number(window.localStorage.getItem(TERMINAL_QUICK_COMMAND_PANEL_HEIGHT_STORAGE_KEY));
  if (!Number.isFinite(saved)) return TERMINAL_QUICK_COMMAND_PANEL_DEFAULT_HEIGHT;
  return clampTerminalQuickCommandPanelHeight(saved);
}

function readTerminalQuickCommandPanelCollapsed() {
  if (typeof window === 'undefined') return false;
  return window.localStorage.getItem(TERMINAL_QUICK_COMMAND_PANEL_COLLAPSED_STORAGE_KEY) === '1';
}
</script>

<template>
  <main class="terminal-shell" :class="{ resizing: isResizingSidebar, 'sidebar-collapsed': isTerminalSidebarCollapsed }" :style="terminalShellStyle">
    <aside class="terminal-sidebar">
      <nav class="terminal-side-switch" aria-label="终端侧栏切换" @mousedown.self="startSidebarResize" @dblclick.stop="toggleTerminalSidebar">
        <button
          type="button"
          title="服务器列表"
          aria-label="服务器列表"
          :class="{ active: terminalSidebarMode === 'hosts' }"
          @click="selectTerminalSidebarMode('hosts')"
        >
          <AppIcon name="server" :size="18" />
        </button>
        <button
          type="button"
          title="FTP 文件夹"
          aria-label="FTP 文件夹"
          :class="{ active: terminalSidebarMode === 'files' }"
          @click="selectTerminalSidebarMode('files')"
        >
          <AppIcon name="folder" :size="19" />
        </button>
        <button
          type="button"
          :title="isTerminalMonitorPanelOpen ? '关闭资源监控' : '打开资源监控'"
          :aria-label="isTerminalMonitorPanelOpen ? '关闭资源监控' : '打开资源监控'"
          :aria-pressed="isTerminalMonitorPanelOpen"
          :class="{ active: isTerminalMonitorPanelOpen }"
          @click="toggleTerminalMonitorPanel"
        >
          <AppIcon name="monitor" :size="18" />
        </button>
        <button
          class="terminal-sidebar-collapse-button"
          type="button"
          :title="terminalSidebarToggleLabel"
          :aria-label="terminalSidebarToggleLabel"
          :aria-pressed="isTerminalSidebarCollapsed"
          @click="toggleTerminalSidebar"
        >
          <AppIcon name="chevronsRight" :size="17" />
        </button>
        <button
          v-if="shouldShowTerminalQuickCommandPanel"
          class="terminal-quick-toggle-button"
          type="button"
          title="打开/关闭快捷命令"
          aria-label="打开/关闭快捷命令"
          :aria-pressed="!isTerminalQuickCommandPanelCollapsed"
          :class="{ active: !isTerminalQuickCommandPanelCollapsed }"
          @click.stop="toggleTerminalQuickCommandFromRail"
          @dblclick.stop
        >
          <AppIcon name="zap" :size="18" />
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
        <template v-else-if="terminalSidebarMode === 'files'">
          <div ref="terminalFileBrowserRef" class="terminal-file-browser" :style="terminalTransferPanelStyle">
            <header class="terminal-file-title">
              <strong>文件浏览器</strong>
              <span class="terminal-file-node">{{ activeTerminalNodeName }}</span>
            </header>
            <div class="terminal-file-toolbar">
              <button type="button" title="新建文件" aria-label="新建文件" @click="openTerminalFileCreateDialog('file')"><AppIcon name="plus" :size="15" /></button>
              <button type="button" title="新建文件夹" aria-label="新建文件夹" @click="openTerminalFileCreateDialog('directory')"><AppIcon name="folderPlus" :size="15" /></button>
              <span></span>
              <button type="button" title="上传" aria-label="上传" @click="openTerminalUpload"><AppIcon name="upload" :size="15" /></button>
              <button type="button" title="下载" aria-label="下载" :disabled="!canDownloadSelectedTerminalFiles" @click="downloadTerminalFiles()"><AppIcon name="download" :size="15" /></button>
              <button
                type="button"
                title="删除"
                aria-label="删除"
                :disabled="!selectedTerminalFileCount"
                @click="openTerminalFileDeleteDialog()"
              >
                <AppIcon name="trash" :size="15" />
              </button>
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
                <span>大小</span>
                <span>权限</span>
                <span>所有者</span>
                <span>组</span>
              </div>
              <div
                ref="terminalFileListRef"
                class="terminal-file-list"
                :class="{ 'drag-over': isTerminalFileDragOver, selecting: terminalFileMarquee.active }"
                @contextmenu="openTerminalDirectoryContextMenu"
                @mousedown="startTerminalFileMarquee"
                @dragenter="onTerminalFileDragEnter"
                @dragover="onTerminalFileDragOver"
                @dragleave="onTerminalFileDragLeave"
                @drop="onTerminalFileDrop"
              >
                <div
                  v-for="entry in terminalFileEntries"
                  :key="entry.name"
                  class="terminal-file-item"
                  :class="{ selected: isTerminalFileSelected(entry), parent: isParentDirectoryEntry(entry) }"
                  :data-terminal-file-path="entry.path"
                  :draggable="Boolean(activeTab) && entry.type === 'file' && isTerminalFileSelected(entry)"
                  role="button"
                  :tabindex="activeTab ? 0 : -1"
                  :aria-disabled="!activeTab"
                  @click="selectTerminalFile(entry, $event)"
                  @contextmenu="openTerminalFileContextMenu(entry, $event)"
                  @mousedown="!isTerminalFileSelected(entry) && startTerminalFileMarquee($event)"
                  @dragstart="startTerminalFileDragDownload(entry, $event)"
                  @dblclick="!isTerminalFileRenaming(entry) && entry.type === 'directory' && openTerminalDirectory(entry)"
                  @keydown.enter.prevent="!isTerminalFileRenaming(entry) && entry.type === 'directory' && openTerminalDirectory(entry)"
                >
                  <span class="terminal-file-name">
                    <AppIcon :name="entry.type === 'directory' ? 'folder' : 'settings'" :size="15" />
                    <input
                      v-if="isTerminalFileRenaming(entry)"
                      :ref="setTerminalFileRenameInput"
                      v-model="terminalFileRename!.draftName"
                      class="terminal-file-rename-input"
                      type="text"
                      :disabled="terminalFileRename?.saving"
                      @click.stop
                      @dblclick.stop
                      @keydown.enter.prevent.stop="saveTerminalFileRename"
                      @keydown.esc.prevent.stop="cancelTerminalFileRename"
                      @blur="saveTerminalFileRename"
                    />
                    <strong v-else>{{ entry.name }}</strong>
                  </span>
                  <time>{{ entry.modifiedAt }}</time>
                  <span class="terminal-file-size">{{ formatTerminalFileSize(entry) }}</span>
                  <span class="terminal-file-permissions">{{ terminalFileText(entry.permissions) }}</span>
                  <span>{{ terminalFileText(entry.owner) }}</span>
                  <span>{{ terminalFileText(entry.group) }}</span>
                </div>
                <p v-if="!activeTab" class="terminal-tree-empty">请选择服务器</p>
                <p v-else-if="isTerminalFileListLoading" class="terminal-tree-empty">目录加载中...</p>
                <p v-else-if="terminalFileListError" class="terminal-tree-empty">{{ terminalFileListError }}</p>
                <div v-if="isTerminalFileDragOver" class="terminal-file-drop-hint">
                  <AppIcon name="upload" :size="22" />
                  <strong>释放后上传到当前目录</strong>
                </div>
                <div v-if="terminalFileMarquee.active" class="terminal-file-marquee" :style="terminalFileMarqueeStyle"></div>
              </div>
            </div>
            <footer class="terminal-file-status">
              <span>{{ terminalFileSelectionStatusText }}</span>
              <span class="terminal-file-protocol" :class="terminalFileStatus">{{ terminalFileStatusText }}</span>
              <label class="terminal-file-download-protocol" :title="`下载方式：${getTerminalDownloadProtocolLabel()}`">
                <span>下载</span>
                <select v-model="terminalDownloadProtocol" aria-label="下载方式">
                  <option value="auto">自动</option>
                  <option value="sftp">SFTP</option>
                  <option value="scp">SCP</option>
                </select>
              </label>
              <div>
                <button
                  type="button"
                  :title="terminalFileFollowCwdLabel"
                  :aria-label="terminalFileFollowCwdLabel"
                  :aria-pressed="isTerminalFileFollowingCwd"
                  :class="{ active: isTerminalFileFollowingCwd }"
                  @click="toggleTerminalFileCwdFollow"
                >
                  <AppIcon name="refresh" :size="15" />
                </button>
              </div>
            </footer>
            <section class="terminal-transfer-panel" :class="{ resizing: isTerminalTransferPanelResizing }">
              <button
                class="terminal-transfer-resizer"
                type="button"
                title="调整文件传输栏高度"
                aria-label="调整文件传输栏高度"
                @mousedown="startTerminalTransferPanelResize"
              ></button>
              <header class="terminal-transfer-header">
                <strong>文件传输</strong>
                <div>
                  <button type="button" title="取消全部" aria-label="取消全部" :disabled="!hasRunningTerminalTransfers" @click="cancelAllTerminalTransfers">
                    <AppIcon name="x" :size="14" />
                  </button>
                  <button type="button" title="清空记录" aria-label="清空记录" :disabled="!hasClearableTerminalTransfers" @click="clearTerminalTransferRecords">
                    <AppIcon name="trash" :size="14" />
                  </button>
                </div>
              </header>
              <div class="terminal-transfer-list">
                <p v-if="!terminalTransferRecords.length" class="terminal-transfer-empty">无传输记录</p>
                <article
                  v-for="record in terminalTransferRecords"
                  :key="record.id"
                  class="terminal-transfer-item"
                  :class="[record.kind, record.status]"
                >
                  <AppIcon :name="record.kind === 'upload' ? 'upload' : 'download'" :size="15" />
                  <div class="terminal-transfer-main">
                    <div class="terminal-transfer-line">
                      <strong>{{ record.name }}</strong>
                      <span>{{ getTerminalTransferCountText(record) }}</span>
                    </div>
                    <div class="terminal-transfer-progress" aria-hidden="true">
                      <i :style="getTerminalTransferProgressStyle(record)"></i>
                    </div>
                    <p>{{ getTerminalTransferStatusText(record) }}</p>
                  </div>
                  <button
                    type="button"
                    title="取消"
                    aria-label="取消"
                    :disabled="!isTerminalTransferActive(record)"
                    @click="cancelTerminalTransfer(record)"
                  >
                    <AppIcon name="x" :size="13" />
                  </button>
                </article>
              </div>
            </section>
            <input ref="terminalFileUploadInput" hidden type="file" @change="uploadTerminalFile" />
            <input ref="terminalFolderUploadInput" hidden type="file" multiple webkitdirectory @change="uploadTerminalFolder" />
            <div
              v-if="terminalFileContextMenu.visible"
              class="terminal-file-context-menu"
              :class="{ 'submenu-left': isTerminalContextSubmenuLeft(terminalFileContextMenu.x) }"
              :style="{ left: `${terminalFileContextMenu.x}px`, top: `${terminalFileContextMenu.y}px` }"
              role="menu"
              @click.stop
              @contextmenu.prevent.stop
            >
              <div
                v-for="item in terminalFileContextMenuItems"
                :key="item.id"
                class="terminal-file-context-menu-row"
                :class="{ separator: item.separatorBefore }"
              >
                <button
                  type="button"
                  role="menuitem"
                  class="terminal-file-context-menu-item"
                  :class="{ danger: item.danger }"
                  :disabled="!item.enabled"
                  @click="runTerminalFileContextMenuItem(item)"
                >
                  <AppIcon :name="item.icon" :size="15" />
                  <span>{{ item.label }}</span>
                  <AppIcon v-if="item.children?.length" name="chevronRight" :size="14" />
                </button>
                <div v-if="item.children?.length" class="terminal-file-context-submenu" role="menu">
                  <button
                    v-for="child in item.children"
                    :key="child.id"
                    type="button"
                    role="menuitem"
                    class="terminal-file-context-menu-item"
                    :disabled="!child.enabled"
                    @click="runTerminalFileContextMenuItem(child)"
                  >
                    <AppIcon :name="child.icon" :size="15" />
                    <span>{{ child.label }}</span>
                  </button>
                </div>
              </div>
            </div>
            <div
              v-if="terminalDirectoryContextMenu.visible"
              class="terminal-file-context-menu terminal-file-directory-context-menu"
              :class="{ 'submenu-left': isTerminalContextSubmenuLeft(terminalDirectoryContextMenu.x) }"
              :style="{ left: `${terminalDirectoryContextMenu.x}px`, top: `${terminalDirectoryContextMenu.y}px` }"
              role="menu"
              @click.stop
              @contextmenu.prevent.stop
            >
              <div
                v-for="item in terminalDirectoryContextMenuItems"
                :key="item.id"
                class="terminal-file-context-menu-row"
                :class="{ separator: item.separatorBefore }"
              >
                <button
                  type="button"
                  role="menuitem"
                  class="terminal-file-context-menu-item"
                  :disabled="!item.enabled"
                  @click="runTerminalFileContextMenuItem(item)"
                >
                  <AppIcon :name="item.icon" :size="15" />
                  <span>{{ item.label }}</span>
                  <AppIcon v-if="item.children?.length" name="chevronRight" :size="14" />
                </button>
                <div v-if="item.children?.length" class="terminal-file-context-submenu" role="menu">
                  <button
                    v-for="child in item.children"
                    :key="child.id"
                    type="button"
                    role="menuitem"
                    class="terminal-file-context-menu-item"
                    :disabled="!child.enabled"
                    @click="runTerminalFileContextMenuItem(child)"
                  >
                    <AppIcon :name="child.icon" :size="15" />
                    <span>{{ child.label }}</span>
                  </button>
                </div>
              </div>
            </div>
            <Teleport to="body">
              <div
                v-if="terminalFileCreateDialog.visible"
                class="modal-backdrop terminal-file-create-backdrop"
                @click.self="closeTerminalFileCreateDialog"
              >
                <section class="terminal-file-create-modal" role="dialog" aria-modal="true">
                  <header>
                    <h2>{{ terminalFileCreateTitle() }}</h2>
                    <button type="button" aria-label="关闭" :disabled="terminalFileCreateDialog.saving" @click="closeTerminalFileCreateDialog">
                      <AppIcon name="x" :size="16" />
                    </button>
                  </header>
                  <div class="terminal-file-create-body">
                    <label class="terminal-file-create-name-row">
                      <span>{{ terminalFileCreateNameLabel() }}</span>
                      <input v-model="terminalFileCreateDialog.name" type="text" :disabled="terminalFileCreateDialog.saving" autofocus @keydown.enter.prevent="saveTerminalFileCreateDialog" />
                    </label>
                    <label v-if="terminalFileCreateDialog.mode === 'symlink'" class="terminal-file-create-name-row">
                      <span>目标路径：</span>
                      <input v-model="terminalFileCreateDialog.targetPath" type="text" :disabled="terminalFileCreateDialog.saving" @keydown.enter.prevent="saveTerminalFileCreateDialog" />
                    </label>
                    <div v-if="terminalFileCreateDialog.mode !== 'symlink'" class="terminal-file-create-permissions">
                      <span class="terminal-file-create-label">权限：</span>
                      <div class="terminal-file-create-permission-grid" role="group" aria-label="权限">
                        <span></span>
                        <span>用户</span>
                        <label><input type="checkbox" :checked="isTerminalFileCreatePermissionChecked(0o400)" :disabled="terminalFileCreateDialog.saving" @change="setTerminalFileCreatePermissionFromEvent(0o400, $event)" /> R</label>
                        <label><input type="checkbox" :checked="isTerminalFileCreatePermissionChecked(0o200)" :disabled="terminalFileCreateDialog.saving" @change="setTerminalFileCreatePermissionFromEvent(0o200, $event)" /> W</label>
                        <label><input type="checkbox" :checked="isTerminalFileCreatePermissionChecked(0o100)" :disabled="terminalFileCreateDialog.saving" @change="setTerminalFileCreatePermissionFromEvent(0o100, $event)" /> X</label>
                        <label><input type="checkbox" :checked="isTerminalFileCreatePermissionChecked(0o4000)" :disabled="terminalFileCreateDialog.saving" @change="setTerminalFileCreatePermissionFromEvent(0o4000, $event)" /> UID</label>
                        <span></span>
                        <span>组</span>
                        <label><input type="checkbox" :checked="isTerminalFileCreatePermissionChecked(0o040)" :disabled="terminalFileCreateDialog.saving" @change="setTerminalFileCreatePermissionFromEvent(0o040, $event)" /> R</label>
                        <label><input type="checkbox" :checked="isTerminalFileCreatePermissionChecked(0o020)" :disabled="terminalFileCreateDialog.saving" @change="setTerminalFileCreatePermissionFromEvent(0o020, $event)" /> W</label>
                        <label><input type="checkbox" :checked="isTerminalFileCreatePermissionChecked(0o010)" :disabled="terminalFileCreateDialog.saving" @change="setTerminalFileCreatePermissionFromEvent(0o010, $event)" /> X</label>
                        <label><input type="checkbox" :checked="isTerminalFileCreatePermissionChecked(0o2000)" :disabled="terminalFileCreateDialog.saving" @change="setTerminalFileCreatePermissionFromEvent(0o2000, $event)" /> GID</label>
                        <span></span>
                        <span>其他</span>
                        <label><input type="checkbox" :checked="isTerminalFileCreatePermissionChecked(0o004)" :disabled="terminalFileCreateDialog.saving" @change="setTerminalFileCreatePermissionFromEvent(0o004, $event)" /> R</label>
                        <label><input type="checkbox" :checked="isTerminalFileCreatePermissionChecked(0o002)" :disabled="terminalFileCreateDialog.saving" @change="setTerminalFileCreatePermissionFromEvent(0o002, $event)" /> W</label>
                        <label><input type="checkbox" :checked="isTerminalFileCreatePermissionChecked(0o001)" :disabled="terminalFileCreateDialog.saving" @change="setTerminalFileCreatePermissionFromEvent(0o001, $event)" /> X</label>
                        <label><input type="checkbox" :checked="isTerminalFileCreatePermissionChecked(0o1000)" :disabled="terminalFileCreateDialog.saving" @change="setTerminalFileCreatePermissionFromEvent(0o1000, $event)" /> 粘性</label>
                      </div>
                    </div>
                    <label v-if="terminalFileCreateDialog.mode !== 'symlink'" class="terminal-file-create-octal-row">
                      <span>八进制</span>
                      <em>{{ getTerminalFileCreateSpecialOctalDigit() }}</em>
                      <input
                        :value="getTerminalFileCreateStandardOctalMode()"
                        type="text"
                        inputmode="numeric"
                        maxlength="3"
                        :disabled="terminalFileCreateDialog.saving"
                        @input="updateTerminalFileCreateOctalMode"
                        @keydown.enter.prevent="saveTerminalFileCreateDialog"
                      />
                    </label>
                    <p v-if="terminalFileCreateDialog.error" class="terminal-file-create-error">{{ terminalFileCreateDialog.error }}</p>
                  </div>
                  <footer>
                    <label v-if="terminalFileCreateDialog.mode !== 'symlink'" class="terminal-file-create-open-after">
                      <input v-model="terminalFileCreateDialog.openAfterCreate" type="checkbox" :disabled="terminalFileCreateDialog.saving" />
                      <span>{{ terminalFileCreateOpenLabel() }}</span>
                    </label>
                    <div>
                      <button type="button" :disabled="terminalFileCreateDialog.saving" @click="closeTerminalFileCreateDialog">取消</button>
                      <button class="primary" type="button" :disabled="terminalFileCreateDialog.saving" @click="saveTerminalFileCreateDialog">
                        {{ terminalFileCreateDialog.saving ? '创建中...' : '确定' }}
                      </button>
                    </div>
                  </footer>
                </section>
              </div>
            </Teleport>
            <Teleport to="body">
              <div
                v-if="terminalFileDeleteDialog.visible"
                class="modal-backdrop terminal-file-delete-backdrop"
                @click.self="closeTerminalFileDeleteDialog"
              >
                <section class="terminal-file-delete-modal" role="dialog" aria-modal="true">
                  <div class="terminal-file-delete-visual" :class="getTerminalFileDeleteDialogVisualType()">
                    <span class="terminal-file-delete-visual-card">
                      <AppIcon :name="getTerminalFileDeleteDialogVisualType() === 'directory' ? 'folder' : 'file'" :size="34" />
                    </span>
                    <span class="terminal-file-delete-alert"><AppIcon name="alert" :size="18" /></span>
                  </div>
                  <h2>{{ getTerminalFileDeleteDialogTitle() }}</h2>
                  <p>{{ getTerminalFileDeleteDialogDescription() }}</p>
                  <p v-if="terminalFileDeleteDialog.error" class="terminal-file-delete-error">{{ terminalFileDeleteDialog.error }}</p>
                  <div class="terminal-file-delete-actions">
                    <button type="button" :disabled="terminalFileDeleteDialog.deleting" @click="closeTerminalFileDeleteDialog">取消</button>
                    <button class="danger" type="button" :disabled="terminalFileDeleteDialog.deleting" @click="confirmTerminalFileDelete">
                      {{ terminalFileDeleteDialog.deleting ? '删除中...' : '删除' }}
                    </button>
                  </div>
                </section>
              </div>
            </Teleport>
            <Teleport to="body">
              <div
                v-if="terminalFilePropertiesDialog.visible"
                class="modal-backdrop terminal-file-properties-backdrop"
                @click.self="closeTerminalFilePropertiesDialog"
              >
                <section class="terminal-file-properties-modal" role="dialog" aria-modal="true">
                  <header class="terminal-file-properties-head">
                    <span class="terminal-file-properties-icon" :class="terminalFilePropertiesDialog.properties?.type || terminalFilePropertiesDialog.entry?.type">
                      <AppIcon :name="(terminalFilePropertiesDialog.properties?.type || terminalFilePropertiesDialog.entry?.type) === 'directory' ? 'folder' : 'file'" :size="18" />
                    </span>
                    <h2>{{ terminalFilePropertiesDialog.entry?.name || terminalFilePropertiesDialog.properties?.name || '文件' }} 的属性</h2>
                    <button
                      class="terminal-file-properties-close"
                      type="button"
                      aria-label="关闭"
                      :disabled="terminalFilePropertiesDialog.saving"
                      @click="closeTerminalFilePropertiesDialog"
                    >
                      <AppIcon name="x" :size="16" />
                    </button>
                  </header>

                <div v-if="terminalFilePropertiesDialog.loading" class="terminal-file-properties-empty">属性读取中...</div>
                <div v-else-if="terminalFilePropertiesDialog.properties" class="terminal-file-properties-body">
                  <p v-if="terminalFilePropertiesDialog.error" class="terminal-file-properties-error">{{ terminalFilePropertiesDialog.error }}</p>

                  <section class="terminal-file-properties-section">
                    <h3>常规</h3>
                    <dl class="terminal-file-properties-details">
                      <dt>类型：</dt>
                      <dd>{{ getTerminalFilePropertiesTypeLabel(terminalFilePropertiesDialog.properties) }}</dd>
                      <dt>位置：</dt>
                      <dd>{{ terminalFilePropertiesDialog.properties.directory }}</dd>
                      <dt>大小：</dt>
                      <dd>{{ formatTerminalFilePropertiesSize(terminalFilePropertiesDialog.properties) }}</dd>
                      <dt>修改时间：</dt>
                      <dd>{{ terminalFilePropertiesDialog.properties.modifiedAt }}</dd>
                      <dt>访问时间：</dt>
                      <dd>{{ terminalFilePropertiesDialog.properties.accessedAt }}</dd>
                      <dt>所有者：</dt>
                      <dd>{{ getTerminalFileOwnerLabel(terminalFilePropertiesDialog.properties) }} [{{ terminalFilePropertiesDialog.properties.uid }}]</dd>
                      <dt>组：</dt>
                      <dd>{{ getTerminalFileGroupLabel(terminalFilePropertiesDialog.properties) }} [{{ terminalFilePropertiesDialog.properties.gid }}]</dd>
                    </dl>
                  </section>

                  <section class="terminal-file-properties-section">
                    <h3>所有权</h3>
                    <label class="terminal-file-properties-field">
                      <span>所有者：</span>
                      <input v-model="terminalFilePropertiesDialog.draft.owner" type="text" :disabled="terminalFilePropertiesDialog.saving" />
                    </label>
                    <label class="terminal-file-properties-field">
                      <span>组：</span>
                      <input v-model="terminalFilePropertiesDialog.draft.group" type="text" :disabled="terminalFilePropertiesDialog.saving" />
                    </label>
                  </section>

                  <section class="terminal-file-properties-section">
                    <h3>权限</h3>
                    <table class="terminal-file-permission-table">
                      <thead>
                        <tr>
                          <th></th>
                          <th>R</th>
                          <th>W</th>
                          <th>X</th>
                          <th>特殊</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <th>用户</th>
                          <td><input type="checkbox" :checked="isTerminalFilePermissionChecked(0o400)" :disabled="terminalFilePropertiesDialog.saving" @change="setTerminalFilePermissionFromEvent(0o400, $event)" /></td>
                          <td><input type="checkbox" :checked="isTerminalFilePermissionChecked(0o200)" :disabled="terminalFilePropertiesDialog.saving" @change="setTerminalFilePermissionFromEvent(0o200, $event)" /></td>
                          <td><input type="checkbox" :checked="isTerminalFilePermissionChecked(0o100)" :disabled="terminalFilePropertiesDialog.saving" @change="setTerminalFilePermissionFromEvent(0o100, $event)" /></td>
                          <td><label><input type="checkbox" :checked="isTerminalFilePermissionChecked(0o4000)" :disabled="terminalFilePropertiesDialog.saving" @change="setTerminalFilePermissionFromEvent(0o4000, $event)" /> UID</label></td>
                        </tr>
                        <tr>
                          <th>组</th>
                          <td><input type="checkbox" :checked="isTerminalFilePermissionChecked(0o040)" :disabled="terminalFilePropertiesDialog.saving" @change="setTerminalFilePermissionFromEvent(0o040, $event)" /></td>
                          <td><input type="checkbox" :checked="isTerminalFilePermissionChecked(0o020)" :disabled="terminalFilePropertiesDialog.saving" @change="setTerminalFilePermissionFromEvent(0o020, $event)" /></td>
                          <td><input type="checkbox" :checked="isTerminalFilePermissionChecked(0o010)" :disabled="terminalFilePropertiesDialog.saving" @change="setTerminalFilePermissionFromEvent(0o010, $event)" /></td>
                          <td><label><input type="checkbox" :checked="isTerminalFilePermissionChecked(0o2000)" :disabled="terminalFilePropertiesDialog.saving" @change="setTerminalFilePermissionFromEvent(0o2000, $event)" /> GID</label></td>
                        </tr>
                        <tr>
                          <th>其他</th>
                          <td><input type="checkbox" :checked="isTerminalFilePermissionChecked(0o004)" :disabled="terminalFilePropertiesDialog.saving" @change="setTerminalFilePermissionFromEvent(0o004, $event)" /></td>
                          <td><input type="checkbox" :checked="isTerminalFilePermissionChecked(0o002)" :disabled="terminalFilePropertiesDialog.saving" @change="setTerminalFilePermissionFromEvent(0o002, $event)" /></td>
                          <td><input type="checkbox" :checked="isTerminalFilePermissionChecked(0o001)" :disabled="terminalFilePropertiesDialog.saving" @change="setTerminalFilePermissionFromEvent(0o001, $event)" /></td>
                          <td><label><input type="checkbox" :checked="isTerminalFilePermissionChecked(0o1000)" :disabled="terminalFilePropertiesDialog.saving" @change="setTerminalFilePermissionFromEvent(0o1000, $event)" /> 粘性</label></td>
                        </tr>
                      </tbody>
                    </table>
                    <label class="terminal-file-octal-field">
                      <span>八进制：</span>
                      <em>{{ getTerminalFileSpecialOctalDigit() }}</em>
                      <input
                        :value="getTerminalFileStandardOctalMode()"
                        type="text"
                        inputmode="numeric"
                        maxlength="3"
                        :disabled="terminalFilePropertiesDialog.saving"
                        @input="updateTerminalFileOctalMode"
                      />
                    </label>
                    <label v-if="terminalFilePropertiesDialog.properties.type === 'directory'" class="terminal-file-recursive-field">
                      <input v-model="terminalFilePropertiesDialog.recursive" type="checkbox" :disabled="terminalFilePropertiesDialog.saving" />
                      <span>应用到此目录及所有子目录/文件</span>
                    </label>
                  </section>
                </div>
                <div v-else class="terminal-file-properties-empty error">{{ terminalFilePropertiesDialog.error || '属性读取失败' }}</div>

                <footer class="terminal-file-properties-actions">
                  <button type="button" :disabled="terminalFilePropertiesDialog.saving" @click="closeTerminalFilePropertiesDialog">取消</button>
                  <button
                    class="primary"
                    type="button"
                    :disabled="terminalFilePropertiesDialog.loading || terminalFilePropertiesDialog.saving || !terminalFilePropertiesDialog.properties"
                    @click="saveTerminalFileProperties"
                  >
                    {{ terminalFilePropertiesDialog.saving ? '保存中...' : '保存' }}
                  </button>
                </footer>
                </section>
              </div>
            </Teleport>
          </div>
        </template>
      </div>
    </aside>
    <div
      class="terminal-sidebar-resizer"
      role="separator"
      aria-label="调整主机列表宽度"
      aria-orientation="vertical"
      @mousedown="startSidebarResize($event, { alignToPointer: true })"
    ></div>

    <section
      class="terminal-workspace"
      :class="{
        'quick-panel-collapsed': shouldShowTerminalQuickCommandPanel && isTerminalQuickCommandPanelCollapsed,
        'quick-panel-resizing': shouldShowTerminalQuickCommandPanel && isTerminalQuickCommandPanelResizing,
        'multi-execution-enabled': isTerminalMultiExecutionEnabled,
      }"
      :style="terminalQuickCommandPanelStyle"
    >
      <div class="terminal-hint">
        <div class="terminal-hint-actions">
          <button
            type="button"
            class="terminal-multi-execution-toggle"
            :class="{ active: isTerminalMultiExecutionEnabled }"
            :title="isTerminalMultiExecutionEnabled ? '退出多执行模式' : '开启多执行模式'"
            :aria-label="isTerminalMultiExecutionEnabled ? '退出多执行模式' : '开启多执行模式'"
            :aria-pressed="isTerminalMultiExecutionEnabled"
            :disabled="!isTerminalMultiExecutionEnabled && !hasTerminalMultiExecutionCandidates"
            @click="toggleTerminalMultiExecution"
          >
            <AppIcon name="chevronsRight" :size="15" />
          </button>
          <div class="terminal-split-menu" @click.stop>
            <button
              type="button"
              class="terminal-split-trigger"
              :class="{ active: isTerminalSplitMenuOpen || terminalSplitMode !== 'single' }"
              :title="`分屏布局：${terminalSplitModeLabel}`"
              :aria-label="`分屏布局：${terminalSplitModeLabel}`"
              :aria-expanded="isTerminalSplitMenuOpen"
              @click="toggleTerminalSplitMenu"
            >
              <AppIcon name="dashboard" :size="15" />
            </button>
            <div v-if="isTerminalSplitMenuOpen" class="terminal-split-menu-list" role="menu" aria-label="分屏布局">
              <button
                v-for="option in terminalSplitModeOptions"
                :key="option.mode"
                type="button"
                class="terminal-split-menu-item"
                :class="{ active: terminalSplitMode === option.mode }"
                role="menuitem"
                @click="setTerminalSplitMode(option.mode)"
              >
                <AppIcon :name="option.icon" :size="15" />
                <span>{{ option.label }}</span>
                <AppIcon v-if="terminalSplitMode === option.mode" name="check" :size="14" />
              </button>
            </div>
          </div>
          <button
            type="button"
            class="terminal-highlight-toggle"
            :class="{ active: highlightEnabled }"
            :title="highlightEnabled ? '关闭关键词高亮' : '开启关键词高亮'"
            :aria-label="highlightEnabled ? '关闭关键词高亮' : '开启关键词高亮'"
            :aria-pressed="highlightEnabled"
            @click="highlightEnabled = !highlightEnabled"
          >
            <AppIcon name="sun" :size="15" />
          </button>
          <div class="terminal-font-controls" :title="`终端字号 ${terminalFontSize}px`" aria-label="终端字号">
            <button
              type="button"
              title="缩小终端字体"
              aria-label="缩小终端字体"
              :disabled="!canDecreaseTerminalFontSize"
              @click="decreaseTerminalFontSize"
            >
              <AppIcon name="zoomOut" :size="15" />
            </button>
            <span>{{ terminalFontSize }}</span>
            <button
              type="button"
              title="放大终端字体"
              aria-label="放大终端字体"
              :disabled="!canIncreaseTerminalFontSize"
              @click="increaseTerminalFontSize"
            >
              <AppIcon name="zoomIn" :size="15" />
            </button>
          </div>
          <button
            type="button"
            class="terminal-search-toggle"
            :class="{ active: isTerminalSearchOpen }"
            title="查找当前终端"
            aria-label="查找当前终端"
            :aria-pressed="isTerminalSearchOpen"
            :disabled="!activeTab"
            @click="openTerminalSearch()"
          >
            <AppIcon name="search" :size="15" />
          </button>
        </div>
        <span class="terminal-workspace-title">{{ workspaceTitle }}</span>
      </div>
      <div v-if="isTerminalMultiExecutionEnabled" class="terminal-multi-execution-bar">
        <div class="terminal-multi-execution-info">
          <AppIcon name="chevronsRight" :size="16" />
          <strong>多执行模式</strong>
          <span>{{ getTerminalMultiExecutionStatusText() }}</span>
        </div>
        <div class="terminal-multi-execution-actions">
          <button
            type="button"
            title="多粘贴"
            aria-label="多粘贴"
            :disabled="!canSendToTerminalMultiExecutionTargets"
            @click="pasteClipboardToTerminalMultiExecutionTargets"
          >
            <AppIcon name="clipboard" :size="14" />
            <span>多粘贴</span>
          </button>
          <button type="button" title="退出多执行模式" aria-label="退出多执行模式" @click="exitTerminalMultiExecution">
            <AppIcon name="x" :size="14" />
            <span>退出</span>
          </button>
        </div>
      </div>
      <div class="terminal-tabbar">
        <div ref="terminalTabsRef" class="terminal-tabs" @scroll="syncTerminalTabsScrollState">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            type="button"
            class="terminal-tab"
            :data-terminal-tab-id="tab.id"
            :class="{
              active: tab.id === activeTabId,
              closed: tab.status === 'closed',
              error: tab.status === 'error',
              'multi-execution-target': shouldShowTerminalMultiExecutionTabIndicator(tab),
            }"
            :style="getTerminalTabStyle(tab)"
            @click="activateTab(tab.id)"
            @contextmenu="openTerminalTabContextMenu(tab, $event)"
          >
            <span class="terminal-tab-label">{{ getTerminalTabLabel(tab) }}</span>
            <span
              v-if="shouldShowTerminalMultiExecutionTabIndicator(tab)"
              class="terminal-tab-multi-execution-indicator"
              title="多执行控制中"
              aria-label="多执行控制中"
            >
              <AppIcon name="chevronsRight" :size="12" :stroke-width="2.5" />
            </span>
            <span class="terminal-tab-status" :class="[tab.status, { unread: tab.hasUnreadOutput && tab.id !== activeTabId }]"></span>
            <span class="terminal-tab-close" title="关闭" @click.stop="closeTab(tab)"><AppIcon name="x" :size="13" /></span>
          </button>
        </div>
        <div v-if="tabs.length" class="terminal-tab-overview" @click.stop>
          <button
            type="button"
            class="terminal-tab-scroll-button previous"
            title="向左移动标签"
            aria-label="向左移动标签"
            :disabled="!canScrollTerminalTabsLeft"
            @click="scrollTerminalTabs('left')"
          >
            <AppIcon name="chevronRight" :size="15" />
          </button>
          <button
            type="button"
            class="terminal-tab-scroll-button next"
            title="向右移动标签"
            aria-label="向右移动标签"
            :disabled="!canScrollTerminalTabsRight"
            @click="scrollTerminalTabs('right')"
          >
            <AppIcon name="chevronRight" :size="15" />
          </button>
          <button
            type="button"
            class="terminal-tab-menu-trigger"
            :class="{ active: isTerminalTabMenuOpen }"
            title="打开的标签"
            aria-label="打开的标签"
            :aria-expanded="isTerminalTabMenuOpen"
            @click="toggleTerminalTabMenu"
          >
            <AppIcon name="link" :size="16" />
          </button>
          <div v-if="isTerminalTabMenuOpen" class="terminal-tab-menu" role="menu" aria-label="打开的标签">
            <header>打开的标签</header>
            <button
              v-for="(tab, index) in tabs"
              :key="`menu-${tab.id}`"
              type="button"
              class="terminal-tab-menu-item"
              :class="{ active: tab.id === activeTabId, closed: tab.status === 'closed', error: tab.status === 'error' }"
              role="menuitem"
              @click="selectTerminalTabFromMenu(tab)"
            >
              <span class="terminal-tab-menu-check">
                <AppIcon v-if="tab.id === activeTabId" name="check" :size="15" />
              </span>
              <AppIcon name="server" :size="15" />
              <span class="terminal-tab-menu-label">{{ index + 1 }} {{ getTerminalTabLabel(tab) }}</span>
              <span class="terminal-tab-status" :class="[tab.status, { unread: tab.hasUnreadOutput && tab.id !== activeTabId }]"></span>
            </button>
          </div>
        </div>
      </div>
      <div
        v-if="terminalTabContextMenu.visible"
        class="terminal-file-context-menu terminal-context-menu terminal-tab-context-menu"
        :class="{ 'submenu-left': isTerminalContextSubmenuLeft(terminalTabContextMenu.x, TERMINAL_TAB_CONTEXT_MENU_WIDTH) }"
        :style="{ left: `${terminalTabContextMenu.x}px`, top: `${terminalTabContextMenu.y}px` }"
        role="menu"
        aria-label="标签页操作"
        @click.stop
        @contextmenu.prevent.stop
      >
        <div
          v-for="item in terminalTabContextMenuItems"
          :key="item.id"
          class="terminal-file-context-menu-row"
          :class="{ separator: item.separatorBefore }"
        >
          <button
            type="button"
            class="terminal-file-context-menu-item terminal-context-menu-item terminal-tab-context-menu-item"
            :class="{ danger: item.danger, selected: item.selected }"
            :disabled="!item.enabled"
            role="menuitem"
            @click="runTerminalTabContextMenuItem(item)"
          >
            <span v-if="item.swatchColor" class="terminal-tab-color-swatch" :style="{ background: item.swatchColor }">
              <AppIcon v-if="item.selected" name="check" :size="11" :stroke-width="3" />
            </span>
            <AppIcon v-else :name="item.selected ? 'check' : item.icon" :size="14" />
            <span>{{ item.label }}</span>
            <kbd v-if="item.shortcut">{{ item.shortcut }}</kbd>
            <AppIcon v-else-if="item.children?.length" name="chevronRight" :size="13" />
          </button>
          <div v-if="item.children?.length" class="terminal-file-context-submenu terminal-context-submenu terminal-tab-context-submenu">
            <button
              v-for="child in item.children"
              :key="child.id"
              type="button"
              class="terminal-file-context-menu-item terminal-context-menu-item terminal-tab-context-menu-item"
              :class="{ danger: child.danger, selected: child.selected, separator: child.separatorBefore }"
              :disabled="!child.enabled"
              role="menuitem"
              @click="runTerminalTabContextMenuItem(child)"
            >
              <span v-if="child.swatchColor" class="terminal-tab-color-swatch" :style="{ background: child.swatchColor }">
                <AppIcon v-if="child.selected" name="check" :size="11" :stroke-width="3" />
              </span>
              <AppIcon v-else :name="child.selected ? 'check' : child.icon" :size="14" />
              <span>{{ child.label }}</span>
              <kbd v-if="child.shortcut">{{ child.shortcut }}</kbd>
              <AppIcon v-else-if="child.children?.length" name="chevronRight" :size="13" />
            </button>
          </div>
        </div>
      </div>
      <div class="terminal-workspace-body" :class="{ 'monitor-open': isTerminalMonitorPanelOpen }">
        <div
          class="terminal-screen"
          :class="[`split-${terminalSplitMode}`, { 'split-active': isTerminalSplitActive }]"
          :style="terminalScreenStyle"
        >
          <div v-if="!tabs.length" class="terminal-empty">双击左侧主机名连接 SSH 终端。</div>
          <div
            v-for="tab in tabs"
            :key="tab.id"
            class="terminal-panel"
            :class="{
              active: tab.id === activeTabId,
              visible: isTerminalTabVisible(tab),
              excluded: isTerminalMultiExecutionEnabled && isTerminalMultiExecutionExcluded(tab),
            }"
            :aria-hidden="!isTerminalTabVisible(tab)"
            @mousedown.capture="isTerminalTabVisible(tab) && tab.id !== activeTabId && activateTab(tab.id)"
            @contextmenu="openTerminalContextMenu(tab, $event)"
          >
            <div
              v-if="isTerminalSearchOpen && tab.id === activeTabId"
              class="terminal-panel-search"
              @click.stop
              @mousedown.stop
              @contextmenu.stop
            >
              <AppIcon name="search" :size="14" />
              <input
                ref="terminalSearchInputRef"
                v-model="terminalSearchQuery"
                type="search"
                placeholder="查找当前终端"
                @keydown.enter.prevent="searchCurrentTerminal($event.shiftKey ? 'previous' : 'next')"
                @keydown.esc.prevent.stop="closeTerminalSearch"
              />
              <span class="terminal-panel-search-count">{{ terminalSearchResultText }}</span>
              <button type="button" title="上一个" aria-label="上一个" :disabled="!terminalSearchQuery.trim()" @click="searchCurrentTerminal('previous')">
                <AppIcon name="chevronDown" :size="14" />
              </button>
              <button type="button" title="下一个" aria-label="下一个" :disabled="!terminalSearchQuery.trim()" @click="searchCurrentTerminal('next')">
                <AppIcon name="chevronDown" :size="14" />
              </button>
              <button type="button" title="关闭" aria-label="关闭" @click="closeTerminalSearch">
                <AppIcon name="x" :size="14" />
              </button>
            </div>
            <div :ref="(element) => setTerminalContainer(tab.id, element)" class="terminal-xterm-host"></div>
            <label
              v-if="isTerminalMultiExecutionEnabled"
              class="terminal-multi-execution-exclude"
              @click.stop
              @mousedown.stop
              @contextmenu.stop
            >
              <input
                type="checkbox"
                :checked="isTerminalMultiExecutionExcluded(tab)"
                @change="setTerminalMultiExecutionExcludedFromEvent(tab, $event)"
              />
              <span>不控制 {{ getTerminalTabLabel(tab) }}</span>
            </label>
          </div>
        </div>
        <div
          v-if="terminalContextMenu.visible"
          class="terminal-file-context-menu terminal-context-menu"
          :class="{ 'submenu-left': isTerminalContextSubmenuLeft(terminalContextMenu.x) }"
          :style="{ left: `${terminalContextMenu.x}px`, top: `${terminalContextMenu.y}px` }"
          @click.stop
          @contextmenu.prevent.stop
        >
          <div
            v-for="item in terminalContextMenuItems"
            :key="item.id"
            class="terminal-file-context-menu-row"
            :class="{ separator: item.separatorBefore }"
          >
            <button
              type="button"
              class="terminal-file-context-menu-item terminal-context-menu-item"
              :class="{ danger: item.danger }"
              :disabled="!item.enabled"
              @click="runTerminalContextMenuItem(item)"
            >
              <AppIcon :name="item.icon" :size="14" />
              <span>{{ item.label }}</span>
              <kbd v-if="item.shortcut">{{ item.shortcut }}</kbd>
              <AppIcon v-else-if="item.children?.length" name="chevronRight" :size="13" />
            </button>
            <div v-if="item.children?.length" class="terminal-file-context-submenu terminal-context-submenu">
              <button
                v-for="child in item.children"
                :key="child.id"
                type="button"
                class="terminal-file-context-menu-item terminal-context-menu-item"
                :class="{ danger: child.danger, separator: child.separatorBefore }"
                :disabled="!child.enabled"
                @click="runTerminalContextMenuItem(child)"
              >
                <AppIcon :name="child.icon" :size="14" />
                <span>{{ child.label }}</span>
                <kbd v-if="child.shortcut">{{ child.shortcut }}</kbd>
                <AppIcon v-else-if="child.children?.length" name="chevronRight" :size="13" />
              </button>
            </div>
          </div>
        </div>
        <aside v-if="isTerminalMonitorPanelOpen" class="terminal-monitor-panel terminal-monitor-drawer">
          <header class="terminal-monitor-title">
            <strong>资源监控</strong>
            <span>{{ terminalMonitorNodeName }}</span>
            <div class="terminal-monitor-actions">
              <button
                class="terminal-monitor-refresh"
                type="button"
                title="刷新"
                aria-label="刷新"
                :disabled="!activeTab || isTerminalMonitorLoading"
                @click="loadTerminalMonitor"
              >
                <AppIcon name="refresh" :size="15" />
              </button>
              <button
                class="terminal-monitor-refresh"
                type="button"
                title="关闭资源监控"
                aria-label="关闭资源监控"
                @click="closeTerminalMonitorPanel"
              >
                <AppIcon name="x" :size="15" />
              </button>
            </div>
          </header>

          <div v-if="!activeTab" class="terminal-monitor-empty">请选择服务器</div>
          <div v-else class="terminal-monitor-body">
            <p v-if="terminalMonitorError" class="terminal-monitor-error">{{ terminalMonitorError }}</p>

            <template v-if="terminalMonitorData">
              <section class="terminal-monitor-card terminal-monitor-system">
                <h3><AppIcon name="monitor" :size="15" />系统</h3>
                <dl>
                  <div>
                    <dt>主机名称</dt>
                    <dd>{{ terminalMonitorData.system.hostname }}</dd>
                  </div>
                  <div>
                    <dt>系统架构</dt>
                    <dd>{{ terminalMonitorData.system.arch }}</dd>
                  </div>
                  <div>
                    <dt>操作系统</dt>
                    <dd>{{ terminalMonitorData.system.os }}</dd>
                  </div>
                  <div>
                    <dt>运行时长</dt>
                    <dd>{{ formatMonitorUptime(terminalMonitorData.system.uptimeSeconds) }}</dd>
                  </div>
                </dl>
              </section>

              <section class="terminal-monitor-card">
                <h3><AppIcon name="cpu" :size="15" />CPU</h3>
                <div class="terminal-monitor-usage">
                  <div class="terminal-monitor-ring" :style="monitorProgressStyle(terminalMonitorData.cpu.usagePercent)">
                    <span>{{ formatMonitorNumber(terminalMonitorData.cpu.usagePercent, 0) }}%</span>
                  </div>
                  <div class="terminal-monitor-usage-main">
                    <div>
                      <span>平均使用率</span>
                      <strong>{{ formatMonitorPercent(terminalMonitorData.cpu.usagePercent) }}</strong>
                    </div>
                    <i><b :style="monitorProgressStyle(terminalMonitorData.cpu.usagePercent)"></b></i>
                    <em>{{ terminalMonitorData.cpu.cores }} CPU</em>
                  </div>
                </div>
                <div class="terminal-monitor-loads">
                  <span><strong>{{ formatMonitorNumber(terminalMonitorData.cpu.load1, 2) }}</strong><em>1分钟</em></span>
                  <span><strong>{{ formatMonitorNumber(terminalMonitorData.cpu.load5, 2) }}</strong><em>5分钟</em></span>
                  <span><strong>{{ formatMonitorNumber(terminalMonitorData.cpu.load15, 2) }}</strong><em>15分钟</em></span>
                </div>
              </section>

              <section class="terminal-monitor-card">
                <h3><AppIcon name="gauge" :size="15" />内存</h3>
                <div class="terminal-monitor-usage">
                  <div class="terminal-monitor-ring" :style="monitorProgressStyle(terminalMonitorData.memory.usagePercent)">
                    <span>{{ formatMonitorNumber(terminalMonitorData.memory.usagePercent, 0) }}%</span>
                  </div>
                  <div class="terminal-monitor-usage-main">
                    <div>
                      <span>RAM</span>
                      <strong>{{ formatMonitorPercent(terminalMonitorData.memory.usagePercent) }}</strong>
                    </div>
                    <i><b :style="monitorProgressStyle(terminalMonitorData.memory.usagePercent)"></b></i>
                    <em>{{ formatMonitorBytes(terminalMonitorData.memory.usedBytes) }} / {{ formatMonitorBytes(terminalMonitorData.memory.totalBytes) }}</em>
                  </div>
                </div>
                <div class="terminal-monitor-memory-extra">
                  <span>剩余 {{ formatMonitorBytes(terminalMonitorData.memory.availableBytes) }}</span>
                  <span>缓存 {{ formatMonitorBytes(terminalMonitorData.memory.cacheBytes) }}</span>
                </div>
              </section>

              <section class="terminal-monitor-card">
                <h3><AppIcon name="network" :size="15" />网络</h3>
                <div v-if="terminalMonitorData.network.length" class="terminal-monitor-network-list">
                  <div v-for="item in terminalMonitorData.network" :key="item.name" class="terminal-monitor-network-item">
                    <strong>{{ item.name }}</strong>
                    <span><em>↑{{ formatMonitorRate(item.txBytesPerSecond) }}</em><em>↓{{ formatMonitorRate(item.rxBytesPerSecond) }}</em></span>
                    <i><b :style="monitorProgressStyle(Math.min(100, (item.rxBytesPerSecond + item.txBytesPerSecond) / 1024))"></b></i>
                  </div>
                </div>
                <p v-else class="terminal-monitor-muted">暂无网卡数据</p>
              </section>

              <section class="terminal-monitor-card">
                <h3><AppIcon name="hardDrive" :size="15" />磁盘</h3>
                <div v-if="terminalMonitorData.disks.length" class="terminal-monitor-disk-list">
                  <div v-for="disk in terminalMonitorData.disks" :key="`${disk.filesystem}-${disk.mountpoint}`" class="terminal-monitor-disk-item">
                    <div>
                      <strong>{{ disk.mountpoint }}</strong>
                      <em>{{ disk.filesystem }} · {{ disk.type }}</em>
                    </div>
                    <span>{{ formatMonitorPercent(disk.usagePercent) }}</span>
                    <i><b :style="monitorProgressStyle(disk.usagePercent)"></b></i>
                    <p>{{ formatMonitorBytes(disk.usedBytes) }} / {{ formatMonitorBytes(disk.totalBytes) }}，可用 {{ formatMonitorBytes(disk.availableBytes) }}</p>
                  </div>
                </div>
                <p v-else class="terminal-monitor-muted">暂无磁盘数据</p>
              </section>
            </template>
          </div>
        </aside>
      </div>
      <section v-if="shouldShowTerminalQuickCommandPanel" class="terminal-quick-panel">
        <button
          class="terminal-quick-resizer"
          type="button"
          title="调整快捷命令面板高度"
          aria-label="调整快捷命令面板高度"
          :disabled="isTerminalQuickCommandPanelCollapsed"
          @mousedown="startTerminalQuickCommandPanelResize"
        ></button>
        <header class="terminal-quick-header">
          <div>
            <strong><AppIcon name="zap" :size="15" />快捷命令</strong>
            <span v-if="isTerminalMultiExecutionEnabled">多执行目标 {{ terminalMultiExecutionTargetCount }} 个</span>
            <span v-else-if="!activeTerminalReady">请选择已连接的终端</span>
            <span v-else>{{ activeTab?.host.name }}</span>
          </div>
          <div class="terminal-quick-actions">
            <button type="button" title="刷新" aria-label="刷新" :disabled="isTerminalQuickCommandLoading" @click="loadTerminalQuickCommands">
              <AppIcon name="refresh" :size="14" />
            </button>
            <button type="button" title="新增命令" aria-label="新增命令" @click="openTerminalQuickCommandDialog()">
              <AppIcon name="plus" :size="15" />
            </button>
            <button
              type="button"
              :title="isTerminalQuickCommandPanelCollapsed ? '展开快捷命令' : '收起快捷命令'"
              :aria-label="isTerminalQuickCommandPanelCollapsed ? '展开快捷命令' : '收起快捷命令'"
              @click="toggleTerminalQuickCommandPanel"
            >
              <AppIcon name="chevronDown" :size="15" />
            </button>
          </div>
        </header>
        <div v-if="!isTerminalQuickCommandPanelCollapsed" class="terminal-quick-body">
          <aside class="terminal-quick-categories">
            <button
              type="button"
              :class="{ active: terminalQuickCommandCategory === 'all' }"
              @click="terminalQuickCommandCategory = 'all'"
            >
              全部
              <span>{{ terminalQuickCommands.length }}</span>
            </button>
            <button
              v-for="category in terminalQuickCommandCategories"
              :key="category"
              type="button"
              :class="{ active: terminalQuickCommandCategory === category }"
              @click="terminalQuickCommandCategory = category"
            >
              {{ category }}
              <span>{{ terminalQuickCommands.filter((command) => command.category === category).length }}</span>
            </button>
          </aside>
          <div class="terminal-quick-content">
            <div class="terminal-quick-toolbar">
              <label>
                <AppIcon name="search" :size="14" />
                <input v-model="terminalQuickCommandSearch" type="search" placeholder="搜索名称、分类或命令" />
              </label>
              <span>{{ filteredTerminalQuickCommands.length }} 条</span>
            </div>
            <p v-if="terminalQuickCommandError" class="terminal-quick-error">{{ terminalQuickCommandError }}</p>
            <div class="terminal-quick-list">
              <p v-if="isTerminalQuickCommandLoading" class="terminal-quick-empty">加载中...</p>
              <p v-else-if="!filteredTerminalQuickCommands.length" class="terminal-quick-empty">暂无快捷命令</p>
              <template v-else>
                <article
                  v-for="(command, index) in filteredTerminalQuickCommands"
                  :key="command.id"
                  class="terminal-quick-item"
                  :class="{ disabled: !command.enabled }"
                >
                  <div class="terminal-quick-info">
                    <div>
                      <strong>{{ command.name }}</strong>
                      <span>{{ command.category }}</span>
                    </div>
                    <code>{{ command.command }}</code>
                    <p v-if="command.description">{{ command.description }}</p>
                  </div>
                  <div class="terminal-quick-item-actions">
                    <button
                      type="button"
                      title="立即执行"
                      aria-label="立即执行"
                      :disabled="!command.enabled || !terminalQuickCommandReady"
                      @click="sendQuickCommandToTerminal(command, true)"
                    >
                      <AppIcon name="zap" :size="14" />
                      <span>立即执行</span>
                    </button>
                    <button
                      type="button"
                      title="追加输入"
                      aria-label="追加输入"
                      :disabled="!command.enabled || !terminalQuickCommandReady"
                      @click="sendQuickCommandToTerminal(command, false)"
                    >
                      <AppIcon name="cornerDownLeft" :size="14" />
                      <span>追加输入</span>
                    </button>
                    <button
                      type="button"
                      :title="command.enabled ? '禁用' : '启用'"
                      :aria-label="command.enabled ? '禁用' : '启用'"
                      @click="toggleTerminalQuickCommand(command)"
                    >
                      <AppIcon :name="command.enabled ? 'eye' : 'eyeOff'" :size="14" />
                    </button>
                    <button
                      class="move-up"
                      type="button"
                      title="上移"
                      aria-label="上移"
                      :disabled="index === 0"
                      @click="moveTerminalQuickCommand(command, -1)"
                    >
                      <AppIcon name="chevronDown" :size="14" />
                    </button>
                    <button
                      type="button"
                      title="下移"
                      aria-label="下移"
                      :disabled="index === filteredTerminalQuickCommands.length - 1"
                      @click="moveTerminalQuickCommand(command, 1)"
                    >
                      <AppIcon name="chevronDown" :size="14" />
                    </button>
                    <button type="button" title="编辑" aria-label="编辑" @click="openTerminalQuickCommandDialog(command)">
                      <AppIcon name="edit" :size="14" />
                    </button>
                    <button type="button" title="删除" aria-label="删除" @click="deleteTerminalQuickCommand(command)">
                      <AppIcon name="trash" :size="14" />
                    </button>
                  </div>
                </article>
              </template>
            </div>
          </div>
        </div>
      </section>
    </section>
    <Teleport to="body">
      <div v-if="terminalQuickCommandDialog.visible" class="terminal-quick-dialog-backdrop" @click.self="closeTerminalQuickCommandDialog">
        <article class="terminal-quick-dialog">
          <header>
            <strong>{{ terminalQuickCommandDialog.mode === 'create' ? '新增快捷命令' : '编辑快捷命令' }}</strong>
            <button type="button" title="关闭" aria-label="关闭" :disabled="terminalQuickCommandDialog.saving" @click="closeTerminalQuickCommandDialog">
              <AppIcon name="x" :size="16" />
            </button>
          </header>
          <div class="terminal-quick-dialog-body">
            <p v-if="terminalQuickCommandDialog.error" class="terminal-quick-error">{{ terminalQuickCommandDialog.error }}</p>
            <label>
              <span>名称</span>
              <input v-model="terminalQuickCommandDialog.draft.name" type="text" :disabled="terminalQuickCommandDialog.saving" />
            </label>
            <label>
              <span>分类</span>
              <input v-model="terminalQuickCommandDialog.draft.category" type="text" list="terminal-quick-category-options" :disabled="terminalQuickCommandDialog.saving" />
              <datalist id="terminal-quick-category-options">
                <option v-for="category in terminalQuickCommandCategories" :key="category" :value="category"></option>
              </datalist>
            </label>
            <label>
              <span>命令</span>
              <textarea v-model="terminalQuickCommandDialog.draft.command" :disabled="terminalQuickCommandDialog.saving" rows="4"></textarea>
            </label>
            <label>
              <span>说明</span>
              <input v-model="terminalQuickCommandDialog.draft.description" type="text" :disabled="terminalQuickCommandDialog.saving" />
            </label>
            <label class="terminal-quick-enabled-field">
              <input v-model="terminalQuickCommandDialog.draft.enabled" type="checkbox" :disabled="terminalQuickCommandDialog.saving" />
              <span>启用</span>
            </label>
          </div>
          <footer>
            <button type="button" :disabled="terminalQuickCommandDialog.saving" @click="closeTerminalQuickCommandDialog">取消</button>
            <button class="primary" type="button" :disabled="terminalQuickCommandDialog.saving" @click="saveTerminalQuickCommandDialog">
              {{ terminalQuickCommandDialog.saving ? '保存中...' : '保存' }}
            </button>
          </footer>
        </article>
      </div>
    </Teleport>
  </main>
</template>

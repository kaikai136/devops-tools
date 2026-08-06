<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';

import { useAppContext } from '@app/context';
import AppIcon from '@shared/components/AppIcon.vue';
import { errorMessage } from '@shared/utils/errors';
import {
  cancelBulkExecutionTask,
  checkBulkFileUpload,
  createBulkExecutionTask,
  createBulkFileUploadTask,
  deleteBulkExecutionTask,
  getBulkExecutionTask,
  listBulkExecutionTargetTree,
  listBulkExecutionTasks,
} from '../api/bulkExecution';
import type {
  BulkExecutionResult,
  BulkExecutionResultStatus,
  BulkExecutionStatus,
  BulkExecutionTarget,
  BulkExecutionTargetGroup,
  BulkExecutionTask,
  BulkExecutionTaskDetail,
  BulkExecutionType,
  BulkTransferItem,
  BulkUploadCheckResult,
} from '../types';

type BulkView = 'history' | 'execute' | 'upload';
type TargetGroupRow = { group: BulkExecutionTargetGroup; level: number; hasChildren: boolean; expanded: boolean };

const DRAFT_TARGET_IDS_KEY = 'ops-tool.bulk-execution.draft-target-ids';
const uploadTargetIdsKey = 'ops-tool.bulk-execution.upload-target-ids';

const statusLabels: Record<string, string> = {
  queued: '排队中',
  running: '执行中',
  completed: '已完成',
  failed: '失败',
  canceled: '已取消',
  pending: '等待中',
  success: '成功',
  skipped: '已跳过',
};

const historyStatusOptions: Array<{ value: BulkExecutionStatus | ''; label: string }> = [
  { value: '', label: '全部' },
  { value: 'queued', label: '未开始' },
  { value: 'running', label: '执行中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '异常' },
  { value: 'canceled', label: '已停止' },
];

const executionTypeLabels: Record<BulkExecutionType, string> = {
  shell: 'Shell 脚本',
  playbook: 'Playbook 脚本',
  file_upload: '文件上传',
};

const scriptPresets: Array<{ key: string; label: string; type: Exclude<BulkExecutionType, 'file_upload'>; command: string }> = [
  { key: 'shell-health', label: '系统巡检', type: 'shell', command: 'hostname\nuptime\ndf -h\nfree -m' },
  { key: 'shell-service', label: '服务状态', type: 'shell', command: 'systemctl status nginx --no-pager || true' },
  {
    key: 'playbook-ping',
    label: '连通性检查',
    type: 'playbook',
    command: '- hosts: all\n  gather_facts: false\n  tasks:\n    - name: Ping hosts\n      ansible.builtin.ping:\n',
  },
];

const taskPageSizeOptions = [10, 20, 50];
const MAX_SCRIPT_LENGTH = 200000;

const { activeTool, canUsePageAction, showToast, requestConfirm } = useAppContext();

const activeBulkView = ref<BulkView>('history');
const targets = ref<BulkExecutionTarget[]>([]);
const targetGroups = ref<BulkExecutionTargetGroup[]>([]);
const taskHistory = ref<BulkExecutionTask[]>([]);
const taskTotal = ref(0);
const taskPage = ref(1);
const taskPageSize = ref(10);
const selectedTask = ref<BulkExecutionTaskDetail | null>(null);
const selectedTaskId = ref<number | null>(null);
const selectedTargetIds = ref<Set<number>>(new Set());
const isTargetPickerOpen = ref(false);
const draftTargetIds = ref<Set<number>>(new Set());
const targetGroupFilter = ref<number | null>(null);
const targetPickerKeyword = ref('');
const collapsedTargetGroups = ref<Set<number>>(new Set());
const expandedResultIds = ref<Set<number>>(new Set());
const isTaskDetailOpen = ref(false);
const isLoading = ref(false);
const isTargetsLoading = ref(false);
const isCreating = ref(false);
const isUploading = ref(false);
const isCheckingUpload = ref(false);
const isControlBusy = ref(false);
const uploadFileInput = ref<HTMLInputElement | null>(null);
const scriptFileInput = ref<HTMLInputElement | null>(null);
const keyword = ref('');
const statusFilter = ref('');
const hostFilter = ref<number | ''>('');
const taskName = ref('');
const executionType = ref<Exclude<BulkExecutionType, 'file_upload'>>('shell');
const commandInput = ref('');
const scriptSourceName = ref('');
const selectedUploadFiles = ref<File[]>([]);
const remoteDirectory = ref('/tmp/');
const uploadCheckResult = ref<BulkUploadCheckResult | null>(null);
const overwriteConfirmed = ref(false);
let pollTimer: number | null = null;
let taskRequestId = 0;

const canExecute = computed(() => canUsePageAction('bulkExecution', 'execute'));
const canRefresh = computed(() => canUsePageAction('bulkExecution', 'refresh'));
const canCancel = computed(() => canUsePageAction('bulkExecution', 'cancel'));
const canDelete = computed(() => canUsePageAction('bulkExecution', 'delete'));
const hasRunningTask = computed(() => taskHistory.value.some((task) => task.status === 'queued' || task.status === 'running'));
const selectedTargets = computed(() => targets.value.filter((target) => selectedTargetIds.value.has(target.id)));
const draftSelectedTargets = computed(() => targets.value.filter((target) => draftTargetIds.value.has(target.id)));
const targetGroupRows = computed<TargetGroupRow[]>(() => flattenTargetGroupRows(targetGroups.value));
const activeTargetGroupIds = computed(() => {
  if (targetGroupFilter.value === null) return null;
  const group = findTargetGroup(targetGroups.value, targetGroupFilter.value);
  return group ? collectTargetGroupIds(group) : null;
});
const pickerTargets = computed(() => {
  const query = targetPickerKeyword.value.trim().toLowerCase();
  return targets.value.filter((target) => {
    if (activeTargetGroupIds.value && !activeTargetGroupIds.value.has(target.group)) return false;
    if (!query) return true;
    return [target.name, target.privateIp, target.publicIp, target.groupName, target.loginUser, target.os, target.systemType, target.systemArch]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query));
  });
});
const allPickerTargetsSelected = computed(() => pickerTargets.value.length > 0 && pickerTargets.value.every((target) => draftTargetIds.value.has(target.id)));
const uploadTotalSize = computed(() => selectedUploadFiles.value.reduce((total, file) => total + file.size, 0));
const duplicateFiles = computed(() => uploadCheckResult.value?.duplicateFiles ?? []);
const unreachableTargets = computed(() => uploadCheckResult.value?.unreachableTargets ?? []);
const usableUploadTargetIds = computed(() => uploadCheckResult.value?.usableTargetIds ?? [...selectedTargetIds.value]);
const uploadHasWarnings = computed(() => duplicateFiles.value.length > 0 || unreachableTargets.value.length > 0);
const canCreateTask = computed(
  () => canExecute.value && taskName.value.trim().length > 0 && selectedTargetIds.value.size > 0 && commandInput.value.trim().length > 0 && !isCreating.value,
);
const canCheckUpload = computed(
  () => canExecute.value && selectedTargetIds.value.size > 0 && selectedUploadFiles.value.length > 0 && remoteDirectory.value.trim().length > 0 && !isCheckingUpload.value,
);
const canCreateUpload = computed(
  () =>
    canExecute.value &&
    taskName.value.trim().length > 0 &&
    selectedUploadFiles.value.length > 0 &&
    usableUploadTargetIds.value.length > 0 &&
    Boolean(uploadCheckResult.value) &&
    !isUploading.value,
);
const taskTotalPages = computed(() => Math.max(1, Math.ceil(taskTotal.value / taskPageSize.value)));
const taskPageStart = computed(() => (taskTotal.value ? (taskPage.value - 1) * taskPageSize.value + 1 : 0));
const taskPageEnd = computed(() => Math.min(taskPage.value * taskPageSize.value, taskTotal.value));
const pageNumbers = computed(() => {
  const from = Math.max(1, taskPage.value - 2);
  const to = Math.min(taskTotalPages.value, taskPage.value + 2);
  return Array.from({ length: to - from + 1 }, (_, index) => from + index);
});
const selectedTaskCanCancel = computed(() => Boolean(selectedTask.value && ['queued', 'running'].includes(selectedTask.value.status)));
const selectedTaskProgress = computed(() => {
  if (!selectedTask.value || selectedTask.value.targetCount <= 0) return 0;
  return Math.round((selectedTask.value.completedCount / selectedTask.value.targetCount) * 100);
});
const selectedTaskExecutionType = computed(() => selectedTask.value ? executionTypeLabels[selectedTask.value.executionType] : '');
const commandPlaceholder = computed(() =>
  executionType.value === 'playbook'
    ? '- hosts: all\n  gather_facts: false\n  tasks:\n    - name: Check hostname\n      ansible.builtin.command: hostname'
    : 'set -e\nhostname\nuptime',
);
const scriptFileAccept = computed(() => (executionType.value === 'playbook' ? '.yml,.yaml' : '.sh'));
const scriptUploadButtonLabel = computed(() => (executionType.value === 'playbook' ? '上传 YAML' : '上传 SH'));

onMounted(async () => {
  await refreshAll();
  applyDraftTargetIds();
  applyUploadTargetIds();
  startPolling();
});

onUnmounted(() => {
  stopPolling();
});

watch([selectedUploadFiles, remoteDirectory, selectedTargetIds], () => {
  uploadCheckResult.value = null;
  overwriteConfirmed.value = false;
});

watch(
  () => activeTool.value,
  (tool) => {
    if (tool === 'bulkExecution') {
      void refreshAll().then(() => {
        applyDraftTargetIds();
        applyUploadTargetIds();
      });
    }
  },
);

async function refreshAll() {
  if (!canRefresh.value && !canExecute.value) return;
  isLoading.value = true;
  try {
    await Promise.all([loadTargets(), loadTasks()]);
  } finally {
    isLoading.value = false;
  }
}

async function loadTargets() {
  if (!canExecute.value) return;
  isTargetsLoading.value = true;
  try {
    const tree = await listBulkExecutionTargetTree();
    targets.value = tree.targets;
    targetGroups.value = tree.groups;
    if (targetGroupFilter.value !== null && !findTargetGroup(targetGroups.value, targetGroupFilter.value)) targetGroupFilter.value = null;
  } catch (error) {
    showToast('目标主机加载失败', errorMessage(error), 'error');
  } finally {
    isTargetsLoading.value = false;
  }
}

async function loadTasks() {
  if (!canRefresh.value) return;
  try {
    const page = await listBulkExecutionTasks({
      status: statusFilter.value,
      keyword: keyword.value.trim(),
      host: hostFilter.value,
      page: taskPage.value,
      pageSize: taskPageSize.value,
    });
    taskTotal.value = page.count;
    if (taskPage.value > taskTotalPages.value) {
      taskPage.value = taskTotalPages.value;
      await loadTasks();
      return;
    }
    taskHistory.value = page.results;
    if (!taskHistory.value.length) {
      selectedTaskId.value = null;
      selectedTask.value = null;
      expandedResultIds.value = new Set();
      return;
    }
    if (!selectedTaskId.value || !taskHistory.value.some((task) => task.id === selectedTaskId.value)) {
      selectedTaskId.value = taskHistory.value[0].id;
    }
    if (selectedTaskId.value) await selectTask(selectedTaskId.value, false, false);
  } catch (error) {
    showToast('任务历史加载失败', errorMessage(error), 'error');
  }
}

async function selectTask(taskId: number, showError = true, activateHistory = true) {
  const requestId = ++taskRequestId;
  selectedTaskId.value = taskId;
  if (activateHistory) activeBulkView.value = 'history';
  try {
    const detail = await getBulkExecutionTask(taskId);
    if (requestId !== taskRequestId || selectedTaskId.value !== taskId) return;
    selectedTask.value = {
      ...detail,
      uploadFiles: detail.uploadFiles ?? [],
      results: detail.results.map((result) => ({ ...result, transfers: result.transfers ?? [] })),
    };
    expandedResultIds.value = new Set([...expandedResultIds.value].filter((id) => detail.results.some((result) => result.id === id)));
  } catch (error) {
    if (requestId !== taskRequestId || selectedTaskId.value !== taskId) return;
    selectedTask.value = null;
    if (showError) showToast('任务详情加载失败', errorMessage(error), 'error');
  }
}

async function openTaskDetail(taskId: number) {
  await selectTask(taskId, true, false);
  if (selectedTask.value?.id === taskId) isTaskDetailOpen.value = true;
}

function closeTaskDetail() {
  isTaskDetailOpen.value = false;
}

function applyDraftTargetIds() {
  const ids = consumeHandoffIds(DRAFT_TARGET_IDS_KEY);
  if (!ids) return;
  applyHandoffTargets(ids, 'execute');
}

function applyUploadTargetIds() {
  const ids = consumeHandoffIds(uploadTargetIdsKey);
  if (!ids) return;
  applyHandoffTargets(ids, 'upload');
}

function consumeHandoffIds(key: string) {
  if (typeof window === 'undefined') return null;
  const raw = window.sessionStorage.getItem(key);
  if (!raw) return null;
  window.sessionStorage.removeItem(key);
  try {
    const ids = JSON.parse(raw);
    return Array.isArray(ids) ? ids.map((id) => Number(id)) : null;
  } catch {
    return null;
  }
}

function applyHandoffTargets(ids: number[], view: BulkView) {
  const executableIds = new Set(targets.value.map((target) => target.id));
  const next = ids.filter((id) => executableIds.has(id));
  if (!next.length) {
    showToast(view === 'upload' ? '没有可上传主机' : '没有可执行主机', '所选主机中没有已验证的 Linux SSH 主机。', 'error');
    return;
  }
  selectedTargetIds.value = new Set(next);
  activeBulkView.value = view;
}

function switchBulkView(view: BulkView) {
  activeBulkView.value = view;
}

function setHistoryStatus(status: BulkExecutionStatus | '') {
  statusFilter.value = status;
  applyHistoryFilters();
}

function applyHistoryFilters() {
  taskPage.value = 1;
  void loadTasks();
}

function setTaskPage(nextPage: number) {
  const normalized = Math.min(Math.max(1, nextPage), taskTotalPages.value);
  if (taskPage.value === normalized) return;
  taskPage.value = normalized;
  void loadTasks();
}

function setTaskPageSize(event: Event) {
  taskPageSize.value = Number((event.target as HTMLSelectElement).value);
  taskPage.value = 1;
  void loadTasks();
}

function openCreateDialog() {
  switchBulkView('execute');
}

function openUploadDialog() {
  switchBulkView('upload');
}

function flattenTargetGroupRows(groups: BulkExecutionTargetGroup[], level = 0): TargetGroupRow[] {
  return groups.flatMap((group) => {
    const children = group.children ?? [];
    const expanded = !collapsedTargetGroups.value.has(group.key);
    const row: TargetGroupRow = { group, level, hasChildren: children.length > 0, expanded };
    return expanded ? [row, ...flattenTargetGroupRows(children, level + 1)] : [row];
  });
}

function findTargetGroup(groups: BulkExecutionTargetGroup[], groupId: number): BulkExecutionTargetGroup | null {
  for (const group of groups) {
    if (group.key === groupId) return group;
    const child = findTargetGroup(group.children ?? [], groupId);
    if (child) return child;
  }
  return null;
}

function collectTargetGroupIds(group: BulkExecutionTargetGroup): Set<number> {
  const ids = new Set<number>([group.key]);
  for (const child of group.children ?? []) {
    for (const id of collectTargetGroupIds(child)) ids.add(id);
  }
  return ids;
}

function openTargetPicker() {
  draftTargetIds.value = new Set(selectedTargetIds.value);
  targetPickerKeyword.value = '';
  targetGroupFilter.value = null;
  isTargetPickerOpen.value = true;
}

function closeTargetPicker() {
  draftTargetIds.value = new Set(selectedTargetIds.value);
  isTargetPickerOpen.value = false;
}

function confirmTargetSelection() {
  selectedTargetIds.value = new Set(draftTargetIds.value);
  isTargetPickerOpen.value = false;
}

function selectTargetGroup(groupId: number | null) {
  targetGroupFilter.value = groupId;
}

function toggleTargetGroupCollapsed(groupId: number) {
  const next = new Set(collapsedTargetGroups.value);
  if (next.has(groupId)) next.delete(groupId);
  else next.add(groupId);
  collapsedTargetGroups.value = next;
}

function toggleDraftTarget(targetId: number, checked: boolean) {
  const next = new Set(draftTargetIds.value);
  if (checked) next.add(targetId);
  else next.delete(targetId);
  draftTargetIds.value = next;
}

function toggleAllPickerTargets(checked: boolean) {
  const next = new Set(draftTargetIds.value);
  for (const target of pickerTargets.value) {
    if (checked) next.add(target.id);
    else next.delete(target.id);
  }
  draftTargetIds.value = next;
}

function toggleDraftTargetFromEvent(targetId: number, event: Event) {
  toggleDraftTarget(targetId, (event.target as HTMLInputElement).checked);
}

function toggleAllPickerTargetsFromEvent(event: Event) {
  toggleAllPickerTargets((event.target as HTMLInputElement).checked);
}

function removeSelectedTarget(targetId: number) {
  const next = new Set(selectedTargetIds.value);
  next.delete(targetId);
  selectedTargetIds.value = next;
}

function clearSelectedTargets() {
  selectedTargetIds.value = new Set();
}

function createTaskWithConfirmation() {
  if (!canCreateTask.value) return;
  const run = async () => {
    await createTask();
  };
  const message = `将对 ${selectedTargetIds.value.size} 台主机执行 ${executionTypeLabels[executionType.value]}：\n${commandInput.value.trim()}`;
  if (requestConfirm) requestConfirm('确认批量执行', message, '执行脚本', run);
  else if (window.confirm(message)) void run();
}

async function createTask() {
  isCreating.value = true;
  try {
    const task = await createBulkExecutionTask({
      targetIds: [...selectedTargetIds.value],
      command: commandInput.value,
      executionType: executionType.value,
      name: taskName.value.trim(),
    });
    taskName.value = '';
    executionType.value = 'shell';
    commandInput.value = '';
    scriptSourceName.value = '';
    selectedTargetIds.value = new Set();
    taskPage.value = 1;
    await loadTasks();
    await selectTask(task.id);
    showToast('批量执行已创建', '后台正在并发执行所选主机命令。', 'success');
  } catch (error) {
    showToast('任务创建失败', errorMessage(error), 'error');
  } finally {
    isCreating.value = false;
  }
}

function rerunTask(task: BulkExecutionTaskDetail) {
  if (task.executionType === 'file_upload') {
    switchBulkView('upload');
    taskName.value = task.name;
    remoteDirectory.value = task.remoteDirectory || '/tmp/';
    scriptSourceName.value = '';
  } else {
    executionType.value = task.executionType;
    commandInput.value = task.command;
    scriptSourceName.value = '';
    taskName.value = task.name;
    switchBulkView('execute');
  }
  selectedTargetIds.value = new Set(task.results.map((result) => result.host).filter((id): id is number => typeof id === 'number'));
}

async function rerunTaskFromList(taskId: number) {
  await selectTask(taskId, true, false);
  if (selectedTask.value) rerunTask(selectedTask.value);
}

async function deleteTaskFromList(taskId: number) {
  await selectTask(taskId, true, false);
  deleteSelectedTask();
}

function triggerScriptFileSelect() {
  scriptFileInput.value?.click();
}

async function onScriptFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (!file) return;
  if (!isScriptFileAllowed(file.name)) {
    showToast('脚本类型不匹配', executionType.value === 'playbook' ? '请上传 .yml 或 .yaml 文件。' : '请上传 .sh 脚本文件。', 'error');
    return;
  }
  try {
    const content = await file.text();
    if (content.length > MAX_SCRIPT_LENGTH) {
      showToast('脚本过长', `脚本内容不能超过 ${MAX_SCRIPT_LENGTH} 个字符。`, 'error');
      return;
    }
    commandInput.value = content;
    scriptSourceName.value = file.name;
  } catch (error) {
    showToast('脚本读取失败', errorMessage(error), 'error');
  }
}

function isScriptFileAllowed(fileName: string) {
  const normalized = fileName.toLowerCase();
  return executionType.value === 'playbook' ? /\.ya?ml$/.test(normalized) : /\.sh$/.test(normalized);
}

function triggerUploadFileSelect() {
  uploadFileInput.value?.click();
}

function onUploadFileChange(event: Event) {
  const files = Array.from((event.target as HTMLInputElement).files ?? []);
  if (files.length) selectedUploadFiles.value = mergeFiles(selectedUploadFiles.value, files);
  (event.target as HTMLInputElement).value = '';
}

function onUploadDrop(event: DragEvent) {
  const files = Array.from(event.dataTransfer?.files ?? []);
  if (files.length) selectedUploadFiles.value = mergeFiles(selectedUploadFiles.value, files);
}

function mergeFiles(current: File[], incoming: File[]) {
  const next = [...current];
  for (const file of incoming) {
    if (!next.some((item) => item.name === file.name && item.size === file.size && item.lastModified === file.lastModified)) {
      next.push(file);
    }
  }
  return next;
}

function removeUploadFile(index: number) {
  if (isUploading.value) return;
  selectedUploadFiles.value = selectedUploadFiles.value.filter((_, itemIndex) => itemIndex !== index);
}

function clearUploadFiles() {
  if (isUploading.value) return;
  selectedUploadFiles.value = [];
}

async function checkBulkUpload() {
  if (!canCheckUpload.value) return;
  isCheckingUpload.value = true;
  try {
    uploadCheckResult.value = await checkBulkFileUpload({
      targetIds: [...selectedTargetIds.value],
      remoteDirectory: remoteDirectory.value.trim() || '/tmp/',
      filenames: selectedUploadFiles.value.map((file) => file.name),
      totalSize: uploadTotalSize.value,
    });
    overwriteConfirmed.value = !uploadHasWarnings.value;
    if (!uploadCheckResult.value.usableTargetIds.length) showToast('没有可上传主机', '所选主机当前都无法连接。', 'error');
  } catch (error) {
    uploadCheckResult.value = null;
    showToast('上传检查失败', errorMessage(error), 'error');
  } finally {
    isCheckingUpload.value = false;
  }
}

async function submitUploadFlow() {
  if (!uploadCheckResult.value) {
    await checkBulkUpload();
    return;
  }
  await createUploadTask();
}

async function createUploadTask() {
  if (!canCreateUpload.value) return;
  if (uploadHasWarnings.value && !overwriteConfirmed.value) {
    showToast('需要确认覆盖', '请确认后再开始上传。', 'error');
    return;
  }
  isUploading.value = true;
  try {
    const task = await createBulkFileUploadTask({
      targetIds: usableUploadTargetIds.value,
      remoteDirectory: remoteDirectory.value.trim() || '/tmp/',
      files: selectedUploadFiles.value,
      overwrite: overwriteConfirmed.value,
      name: taskName.value.trim(),
    });
    taskName.value = '';
    selectedUploadFiles.value = [];
    remoteDirectory.value = '/tmp/';
    uploadCheckResult.value = null;
    overwriteConfirmed.value = false;
    scriptSourceName.value = '';
    selectedTargetIds.value = new Set();
    taskPage.value = 1;
    await loadTasks();
    await selectTask(task.id);
    showToast('文件上传已创建', '后台正在将文件分发到可连接主机。', 'success');
  } catch (error) {
    showToast('文件上传失败', errorMessage(error), 'error');
  } finally {
    isUploading.value = false;
  }
}

function setExecutionType(type: Exclude<BulkExecutionType, 'file_upload'>) {
  executionType.value = type;
  scriptSourceName.value = '';
  if (!commandInput.value.trim()) {
    commandInput.value = type === 'playbook' ? scriptPresets.find((preset) => preset.type === 'playbook')?.command ?? '' : '';
  }
}

function applyScriptPreset(preset: (typeof scriptPresets)[number]) {
  executionType.value = preset.type;
  commandInput.value = preset.command;
  scriptSourceName.value = '';
}

async function cancelSelectedTask() {
  if (!selectedTaskId.value || !canCancel.value || isControlBusy.value) return;
  isControlBusy.value = true;
  try {
    await cancelBulkExecutionTask(selectedTaskId.value);
    await Promise.all([loadTasks(), selectTask(selectedTaskId.value, false, false)]);
    showToast('已请求取消', '任务会在当前 Ansible 执行结束后停止。', 'success');
  } catch (error) {
    showToast('取消任务失败', errorMessage(error), 'error');
  } finally {
    isControlBusy.value = false;
  }
}

function deleteSelectedTask() {
  if (!selectedTaskId.value || !canDelete.value) return;
  const taskId = selectedTaskId.value;
  const run = async () => {
    isControlBusy.value = true;
    try {
      await deleteBulkExecutionTask(taskId);
      selectedTaskId.value = null;
      selectedTask.value = null;
      isTaskDetailOpen.value = false;
      await loadTasks();
      showToast('任务已删除', '批量执行历史已移除。', 'success');
    } catch (error) {
      showToast('删除任务失败', errorMessage(error), 'error');
    } finally {
      isControlBusy.value = false;
    }
  };
  if (requestConfirm) requestConfirm('删除批量执行任务', '删除后会同时移除每台主机的执行结果。', '删除', run);
  else void run();
}

function toggleResult(resultId: number) {
  const next = new Set(expandedResultIds.value);
  if (next.has(resultId)) next.delete(resultId);
  else next.add(resultId);
  expandedResultIds.value = next;
}

function isResultExpanded(resultId: number) {
  return expandedResultIds.value.has(resultId);
}

function startPolling() {
  stopPolling();
  pollTimer = window.setInterval(async () => {
    if (!hasRunningTask.value) return;
    await loadTasks();
    if (selectedTaskId.value) await selectTask(selectedTaskId.value, false, false);
  }, 3000);
}

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

function statusLabel(status: BulkExecutionStatus | BulkExecutionResultStatus) {
  return statusLabels[status] ?? status;
}

function transferProgress(transfers: BulkTransferItem[]) {
  if (!transfers.length) return 0;
  const done = transfers.filter((transfer) => ['success', 'failed', 'skipped'].includes(transfer.status)).length;
  return Math.round((done / transfers.length) * 100);
}

function formatTime(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : '-';
}

function formatDuration(task: BulkExecutionTask) {
  if (!task.startedAt) return '-';
  const end = task.finishedAt ? new Date(task.finishedAt).getTime() : Date.now();
  const seconds = Math.max(1, Math.round((end - new Date(task.startedAt).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}m ${rest}s`;
}

function taskHostSummary(task: BulkExecutionTask) {
  if (selectedTask.value?.id === task.id && selectedTask.value.results.length) {
    const first = selectedTask.value.results[0];
    return selectedTask.value.results.length > 1 ? `${first.hostName} 等 ${selectedTask.value.results.length} 台` : first.hostName;
  }
  return `${task.targetCount} 台主机`;
}

function taskExitSummary(task: BulkExecutionTask) {
  if (task.status === 'completed' && task.failedCount === 0) return '0';
  if (task.failedCount > 0) return `失败 ${task.failedCount}`;
  if (task.skippedCount > 0) return `跳过 ${task.skippedCount}`;
  return '-';
}

function formatFileSize(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}
</script>

<template>
  <section class="bulk-execution-page">
    <article v-if="canRefresh || canExecute" class="bulk-execution-shell">
      <header class="bulk-execution-head">
        <div>
          <h2>批量执行</h2>
          <p>面向已验证 Linux SSH 主机执行命令、Playbook 和文件分发任务。</p>
        </div>
        <div class="bulk-execution-actions">
          <button v-if="canRefresh || canExecute" type="button" :class="{ active: activeBulkView === 'history' }" @click="switchBulkView('history')"><AppIcon name="rows" :size="16" />执行记录</button>
          <button v-if="canExecute" type="button" :class="{ active: activeBulkView === 'execute' }" @click="openCreateDialog"><AppIcon name="terminal" :size="16" />新建执行</button>
          <button v-if="canExecute" type="button" :class="{ active: activeBulkView === 'upload' }" @click="openUploadDialog"><AppIcon name="upload" :size="16" />批量上传</button>
          <button v-if="canRefresh" type="button" :disabled="isLoading" @click="refreshAll"><AppIcon name="refresh" :size="16" />刷新</button>
        </div>
      </header>

      <section v-show="activeBulkView === 'history'" class="bulk-history-view">
        <section class="bulk-record-panel">
          <header class="bulk-record-toolbar">
            <div class="bulk-record-heading">
              <h3>执行列表</h3>
            </div>
            <div class="bulk-record-actions">
              <label class="bulk-keyword-filter">
                <input v-model="keyword" type="search" placeholder="搜索任务或命令" @keyup.enter="applyHistoryFilters" />
              </label>
              <label class="bulk-host-filter">
                <select v-model="hostFilter" aria-label="目标主机" @change="applyHistoryFilters">
                  <option value="">全部主机</option>
                  <option v-for="target in targets" :key="target.id" :value="target.id">{{ target.name }} / {{ target.privateIp }}</option>
                </select>
              </label>
              <label class="bulk-status-filter">
                <select v-model="statusFilter" aria-label="执行状态" @change="setHistoryStatus(statusFilter)">
                  <option v-for="option in historyStatusOptions" :key="option.value || 'all'" :value="option.value">{{ option.label }}</option>
                </select>
              </label>
              <button class="bulk-query-button" type="button" :disabled="isLoading" @click="applyHistoryFilters"><AppIcon name="search" :size="15" />查询</button>
              <button v-if="canRefresh" type="button" :disabled="isLoading" @click="refreshAll"><AppIcon name="refresh" :size="15" /></button>
            </div>
          </header>

          <div class="bulk-record-table">
            <table class="bulk-record-grid">
              <colgroup>
                <col class="col-check" />
                <col class="col-host" />
                <col class="col-command" />
                <col class="col-status" />
                <col class="col-exit" />
                <col class="col-duration" />
                <col class="col-user" />
                <col class="col-time" />
                <col class="col-desc" />
                <col class="col-ops" />
              </colgroup>
              <thead>
                <tr>
                  <th scope="col"><span class="bulk-sr-only">选择</span></th>
                  <th scope="col">执行机器</th>
                  <th scope="col">执行命令</th>
                  <th scope="col" class="is-center">状态</th>
                  <th scope="col" class="is-center">退出码</th>
                  <th scope="col" class="is-center">持续时间</th>
                  <th scope="col">执行用户</th>
                  <th scope="col">创建时间</th>
                  <th scope="col">描述</th>
                  <th scope="col">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="task in taskHistory"
                  :key="task.id"
                  class="bulk-record-row"
                  :class="{ active: selectedTaskId === task.id }"
                  @click="selectTask(task.id, true, false)"
                >
                  <td class="is-center">
                    <input type="checkbox" :checked="selectedTaskId === task.id" tabindex="-1" readonly />
                  </td>
                  <td class="cell-host" :title="taskHostSummary(task)">{{ taskHostSummary(task) }}</td>
                  <td class="cell-command" :title="task.command">{{ task.command }}</td>
                  <td class="is-center">
                    <span class="bulk-status" :class="`status-${task.status}`">{{ statusLabel(task.status) }}</span>
                  </td>
                  <td class="is-center">{{ taskExitSummary(task) }}</td>
                  <td class="is-center">{{ formatDuration(task) }}</td>
                  <td>{{ task.createdBy || '-' }}</td>
                  <td class="cell-time">{{ formatTime(task.createdAt) }}</td>
                  <td class="cell-desc" :title="task.name">{{ task.name }}</td>
                  <td>
                    <span class="bulk-record-links">
                      <a @click.stop.prevent="openTaskDetail(task.id)">详情</a>
                      <a v-if="canExecute" @click.stop.prevent="rerunTaskFromList(task.id)">再次执行</a>
                      <a v-if="canDelete" class="danger" @click.stop.prevent="deleteTaskFromList(task.id)">删除</a>
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-if="!taskHistory.length" class="bulk-empty">{{ isLoading ? '加载中...' : '暂无批量执行任务' }}</div>
          </div>
          <footer class="bulk-record-footer">
            <div class="host-pagination bulk-record-pagination" aria-label="执行列表分页">
              <div class="bulk-record-pagination-left">
                <div class="host-pagination-summary">
                  <span>共 {{ taskTotal }} 条</span>
                  <span>{{ taskPageStart }}-{{ taskPageEnd }}</span>
                </div>
                <div class="host-pagination-controls">
                  <button class="prev" type="button" :disabled="taskPage <= 1" aria-label="上一页" @click="setTaskPage(taskPage - 1)">
                    <AppIcon name="chevronRight" :size="14" />
                  </button>
                  <button
                    v-for="pageNumber in pageNumbers"
                    :key="pageNumber"
                    type="button"
                    :class="{ active: pageNumber === taskPage }"
                    @click="setTaskPage(pageNumber)"
                  >
                    {{ pageNumber }}
                  </button>
                  <button type="button" :disabled="taskPage >= taskTotalPages" aria-label="下一页" @click="setTaskPage(taskPage + 1)">
                    <AppIcon name="chevronRight" :size="14" />
                  </button>
                  <select :value="taskPageSize" aria-label="每页条数" @change="setTaskPageSize">
                    <option v-for="option in taskPageSizeOptions" :key="option" :value="option">{{ option }} 条/页</option>
                  </select>
                </div>
              </div>
              <div class="bulk-record-stats">{{ taskTotal }} 个任务 · {{ targets.length }} 台可执行主机</div>
            </div>
          </footer>
        </section>

      </section>

      <section v-show="activeBulkView === 'execute'" class="bulk-execute-view">
        <div class="bulk-create-workbench">
          <section class="bulk-script-composer">
            <div class="bulk-mode-tabs" role="tablist" aria-label="执行类型">
              <button type="button" :class="{ active: executionType === 'shell' }" @click="setExecutionType('shell')">
                <AppIcon name="terminal" :size="15" />
                Shell 脚本
              </button>
              <button type="button" :class="{ active: executionType === 'playbook' }" @click="setExecutionType('playbook')">
                <AppIcon name="rows" :size="15" />
                Playbook 脚本
              </button>
            </div>
            <label class="bulk-task-name-field">
              <span>任务名称</span>
              <input v-model="taskName" maxlength="180" placeholder="请输入任务名称" :disabled="isCreating" required />
            </label>
            <div class="bulk-script-presets">
              <button v-for="preset in scriptPresets" :key="preset.key" type="button" @click="applyScriptPreset(preset)">
                {{ preset.label }}
              </button>
            </div>
            <div class="bulk-script-editor">
              <input ref="scriptFileInput" hidden type="file" :accept="scriptFileAccept" @change="onScriptFileChange" />
              <div class="bulk-script-editor-head">
                <span>{{ executionTypeLabels[executionType] }}</span>
                <button class="bulk-script-upload-button" type="button" :disabled="isCreating" @click="triggerScriptFileSelect">
                  <AppIcon name="upload" :size="14" />
                  {{ scriptUploadButtonLabel }}
                </button>
              </div>
              <div v-if="scriptSourceName" class="bulk-script-source">
                <AppIcon name="file" :size="14" />
                <span>{{ scriptSourceName }}</span>
              </div>
              <textarea v-model="commandInput" class="commandInput" rows="16" :maxlength="MAX_SCRIPT_LENGTH" :placeholder="commandPlaceholder" :disabled="isCreating"></textarea>
            </div>
          </section>

          <section class="bulk-target-summary">
            <header>
              <div>
                <h3>目标机器</h3>
                <span>已选 {{ selectedTargets.length }} / {{ targets.length }}</span>
              </div>
              <button type="button" :disabled="isTargetsLoading" @click="openTargetPicker"><AppIcon name="server" :size="15" />选择机器</button>
            </header>
            <div v-if="!selectedTargets.length" class="bulk-target-empty">
              <AppIcon name="server" :size="28" />
              <strong>尚未选择机器</strong>
              <span>{{ isTargetsLoading ? '目标加载中...' : '点击选择机器添加执行目标' }}</span>
            </div>
            <div v-else class="bulk-selected-target-list">
              <div v-for="target in selectedTargets" :key="target.id" class="bulk-selected-target-row">
                <div class="bulk-selected-target-main">
                  <strong class="bulk-selected-target-name">{{ target.name }}</strong>
                  <span class="bulk-selected-target-meta">
                    <span class="bulk-selected-target-ip">{{ target.privateIp || '-' }}</span>
                    <span class="bulk-selected-target-user">{{ target.loginUser || '-' }}</span>
                    <span class="bulk-selected-target-group">{{ target.groupName || '-' }}</span>
                  </span>
                </div>
                <button class="bulk-selected-target-remove" type="button" aria-label="移除目标机器" :disabled="isCreating" @click="removeSelectedTarget(target.id)">
                  <AppIcon name="x" :size="14" />
                </button>
              </div>
              <button class="bulk-clear-targets" type="button" :disabled="isCreating" @click="clearSelectedTargets">清空选择</button>
            </div>
          </section>
        </div>
        <footer class="bulk-workbench-footer">
          <button type="button" :disabled="isCreating" @click="switchBulkView('history')">返回记录</button>
          <button class="primary" type="button" :disabled="!canCreateTask" @click="createTaskWithConfirmation">{{ isCreating ? '创建中...' : '执行脚本' }}</button>
        </footer>
      </section>

      <section v-show="activeBulkView === 'upload'" class="bulk-upload-view">
        <div class="bulk-create-workbench">
          <section class="bulk-script-composer bulk-upload-composer">
            <label class="bulk-task-name-field">
              <span>任务名称</span>
              <input v-model="taskName" maxlength="180" placeholder="请输入任务名称" :disabled="isUploading" required />
            </label>
            <input ref="uploadFileInput" hidden type="file" multiple @change="onUploadFileChange" />
            <button
              class="bulk-upload-dropzone"
              type="button"
              :disabled="isUploading"
              @click="triggerUploadFileSelect"
              @dragover.prevent
              @drop.prevent="onUploadDrop"
            >
              <AppIcon name="upload" :size="38" />
              <strong>{{ selectedUploadFiles.length ? `${selectedUploadFiles.length} 个文件` : '选择文件' }}</strong>
              <span>{{ selectedUploadFiles.length ? formatFileSize(uploadTotalSize) : '支持多个文件上传' }}</span>
            </button>
            <div v-if="selectedUploadFiles.length" class="bulk-upload-file-stack">
              <div v-for="(file, index) in selectedUploadFiles" :key="`${file.name}-${file.size}-${file.lastModified}`" class="bulk-upload-file-row">
                <span>{{ file.name }}</span>
                <em>{{ formatFileSize(file.size) }}</em>
                <button type="button" :disabled="isUploading" @click="removeUploadFile(index)"><AppIcon name="x" :size="14" /></button>
              </div>
              <button type="button" :disabled="isUploading" @click="clearUploadFiles">清空文件</button>
            </div>

            <label class="bulk-upload-path">
              <span>远程目录</span>
              <input v-model="remoteDirectory" :disabled="isUploading" placeholder="/tmp/" />
            </label>
            <p class="bulk-upload-hint">上传前会检查主机连接和同名文件；确认后将覆盖已存在的同名文件。</p>

            <section v-if="uploadCheckResult" class="bulk-upload-check-panel">
              <header>
                <strong>上传检查</strong>
                <span>{{ uploadCheckResult.connectedTargets.length }} 台可连接 · {{ unreachableTargets.length }} 台不可连接</span>
              </header>
              <div v-if="unreachableTargets.length" class="bulk-upload-warning">
                <strong>不可连接主机</strong>
                <span v-for="target in unreachableTargets" :key="target.id">{{ target.name }} / {{ target.privateIp }} · {{ target.error }}</span>
              </div>
              <div v-if="duplicateFiles.length" class="bulk-upload-warning">
                <strong>重复文件</strong>
                <span v-for="item in duplicateFiles" :key="item.targetId">{{ item.hostName }} / {{ item.hostIp }} · {{ item.filenames.join(', ') }}</span>
              </div>
              <label v-if="uploadHasWarnings" class="bulk-upload-overwrite">
                <input v-model="overwriteConfirmed" type="checkbox" />
                确认继续上传，并覆盖重复文件
              </label>
            </section>
          </section>

          <section class="bulk-target-summary">
            <header>
              <div>
                <h3>目标机器</h3>
                <span>已选 {{ selectedTargets.length }} / {{ targets.length }}</span>
              </div>
              <button type="button" :disabled="isTargetsLoading || isUploading" @click="openTargetPicker"><AppIcon name="server" :size="15" />选择机器</button>
            </header>
            <div v-if="!selectedTargets.length" class="bulk-target-empty">
              <AppIcon name="server" :size="28" />
              <strong>尚未选择机器</strong>
              <span>{{ isTargetsLoading ? '目标加载中...' : '点击选择机器添加上传目标' }}</span>
            </div>
            <div v-else class="bulk-selected-target-list">
              <div v-for="target in selectedTargets" :key="target.id" class="bulk-selected-target-row">
                <div class="bulk-selected-target-main">
                  <strong class="bulk-selected-target-name">{{ target.name }}</strong>
                  <span class="bulk-selected-target-meta">
                    <span class="bulk-selected-target-ip">{{ target.privateIp || '-' }}</span>
                    <span class="bulk-selected-target-user">{{ target.loginUser || '-' }}</span>
                    <span class="bulk-selected-target-group">{{ target.groupName || '-' }}</span>
                  </span>
                </div>
                <button class="bulk-selected-target-remove" type="button" aria-label="移除目标机器" :disabled="isUploading || isCheckingUpload" @click="removeSelectedTarget(target.id)">
                  <AppIcon name="x" :size="14" />
                </button>
              </div>
              <button class="bulk-clear-targets" type="button" :disabled="isUploading || isCheckingUpload" @click="clearSelectedTargets">清空选择</button>
            </div>
          </section>
        </div>
        <footer class="bulk-workbench-footer">
          <button type="button" :disabled="isCheckingUpload || isUploading" @click="switchBulkView('history')">返回记录</button>
          <button type="button" :disabled="!canCheckUpload" @click="checkBulkUpload">{{ isCheckingUpload ? '检查中...' : '检查文件' }}</button>
          <button class="primary" type="button" :disabled="!canCreateUpload || (uploadHasWarnings && !overwriteConfirmed)" @click="submitUploadFlow">
            {{ isUploading ? '上传中...' : '开始上传' }}
          </button>
        </footer>
      </section>

      <div v-if="isTargetPickerOpen" class="modal-backdrop bulk-target-picker-backdrop">
        <section class="bulk-target-picker-modal" role="dialog" aria-modal="true" aria-label="选择机器">
          <button class="modal-close" type="button" @click="closeTargetPicker"><AppIcon name="x" :size="16" /></button>
          <header class="bulk-target-picker-title">
            <div>
              <h3>选择机器</h3>
              <p>已选 {{ draftTargetIds.size }} / {{ targets.length }}</p>
            </div>
          </header>
          <div class="bulk-target-picker-body">
            <aside class="bulk-target-group-tree" aria-label="目标分组树">
              <button class="bulk-target-group-row bulk-target-group-root" :class="{ active: targetGroupFilter === null }" type="button" @click="selectTargetGroup(null)">
                <span class="folder-caret"><AppIcon name="chevronDown" :size="15" /></span>
                <span class="folder-icon"><AppIcon name="folder" :size="16" /></span>
                <strong>全部分组</strong>
                <em>{{ targets.length }}</em>
              </button>
              <button
                v-for="row in targetGroupRows"
                :key="row.group.key"
                class="bulk-target-group-row"
                :class="{ active: targetGroupFilter === row.group.key }"
                :style="{ paddingLeft: `${10 + row.level * 10}px` }"
                type="button"
                @click="selectTargetGroup(row.group.key)"
              >
                <span class="folder-caret" :class="{ expandable: row.hasChildren }" @click.stop="row.hasChildren && toggleTargetGroupCollapsed(row.group.key)">
                  <AppIcon v-if="row.hasChildren" :name="row.expanded ? 'chevronDown' : 'chevronRight'" :size="15" />
                </span>
                <span class="folder-icon"><AppIcon name="folder" :size="16" /></span>
                <strong>{{ row.group.label }}</strong>
                <em>{{ row.group.count }}</em>
              </button>
              <div v-if="!targetGroupRows.length" class="bulk-empty">{{ isTargetsLoading ? '加载中...' : '暂无可执行分组' }}</div>
            </aside>
            <section class="bulk-target-picker-list-panel">
              <header>
                <label>
                  <input type="checkbox" :checked="allPickerTargetsSelected" :disabled="!pickerTargets.length" @change="toggleAllPickerTargetsFromEvent" />
                  全选当前列表
                </label>
                <input v-model="targetPickerKeyword" type="search" placeholder="搜索主机 / IP / 分组" />
                <span>已选 {{ draftSelectedTargets.length }} / {{ targets.length }}</span>
              </header>
              <div class="bulk-target-picker-list">
                <label v-for="target in pickerTargets" :key="target.id" class="bulk-target-picker-row">
                  <input type="checkbox" :checked="draftTargetIds.has(target.id)" @change="toggleDraftTargetFromEvent(target.id, $event)" />
                  <strong>{{ target.name }}</strong>
                  <span>{{ target.privateIp }} · {{ target.loginUser }} · {{ target.groupName || '-' }}</span>
                </label>
                <div v-if="!pickerTargets.length" class="bulk-empty">{{ isTargetsLoading ? '加载中...' : '暂无匹配的可执行 Linux SSH 主机' }}</div>
              </div>
            </section>
          </div>
          <footer>
            <button type="button" @click="closeTargetPicker">取消</button>
            <button class="primary" type="button" @click="confirmTargetSelection">确定选择</button>
          </footer>
        </section>
      </div>

      <div v-if="isTaskDetailOpen" class="modal-backdrop bulk-detail-backdrop">
        <section class="bulk-task-detail bulk-task-detail-modal" role="dialog" aria-modal="true" aria-label="执行详情">
          <button class="modal-close" type="button" @click="closeTaskDetail"><AppIcon name="x" :size="16" /></button>
          <template v-if="selectedTask">
            <header>
              <div>
                <h3>{{ selectedTask.name }}</h3>
                <p>{{ selectedTask.createdBy }} · {{ selectedTaskExecutionType }} · {{ statusLabel(selectedTask.status) }} · {{ selectedTaskProgress }}%</p>
              </div>
              <div>
                <button v-if="canExecute" type="button" :disabled="isControlBusy" @click="rerunTask(selectedTask)">再次执行</button>
                <button v-if="canCancel" type="button" :disabled="!selectedTaskCanCancel || isControlBusy" @click="cancelSelectedTask">取消</button>
                <button v-if="canDelete" class="danger" type="button" :disabled="isControlBusy" @click="deleteSelectedTask"><AppIcon name="trash" :size="15" />删除</button>
              </div>
            </header>
            <pre class="bulk-command-block">{{ selectedTask.command }}</pre>
            <div v-if="selectedTask.executionType === 'file_upload'" class="bulk-upload-summary">
              <span>文件 {{ selectedTask.uploadFilename || '-' }}</span>
              <span>目录 {{ selectedTask.remoteDirectory || '-' }}</span>
              <span>大小 {{ formatFileSize(selectedTask.uploadSize || 0) }}</span>
            </div>
            <div v-if="selectedTask.uploadFiles?.length" class="bulk-upload-file-list">
              <span v-for="file in selectedTask.uploadFiles" :key="file.id">{{ file.filename }} · {{ formatFileSize(file.size) }}</span>
            </div>
            <p v-if="selectedTask.error" class="bulk-error">{{ selectedTask.error }}</p>
            <div class="bulk-progress"><span :style="{ width: `${selectedTaskProgress}%` }"></span></div>

            <div class="bulk-result-table">
              <div class="bulk-result-row head">
                <span>主机</span>
                <span>IP</span>
                <span>用户</span>
                <span>状态</span>
                <span>退出码</span>
                <span>进度</span>
                <span>输出</span>
              </div>
              <template v-for="result in selectedTask.results" :key="result.id">
                <div class="bulk-result-row">
                  <strong>{{ result.hostName }}</strong>
                  <span>{{ result.hostIp }}:{{ result.hostPort }}</span>
                  <span>{{ result.loginUser || '-' }}</span>
                  <span class="bulk-status" :class="`status-${result.status}`">{{ statusLabel(result.status) }}</span>
                  <span>{{ result.exitCode ?? '-' }}</span>
                  <span>{{ result.transfers?.length ? `${transferProgress(result.transfers)}%` : formatTime(result.finishedAt || result.startedAt) }}</span>
                  <button type="button" @click="toggleResult(result.id)">
                    <AppIcon :name="isResultExpanded(result.id) ? 'chevronDown' : 'chevronRight'" :size="15" />
                  </button>
                </div>
                <div v-if="isResultExpanded(result.id)" class="bulk-result-output">
                  <div v-if="result.transfers?.length" class="bulk-transfer-matrix">
                    <div v-for="transfer in result.transfers" :key="transfer.id" class="bulk-transfer-row">
                      <strong>{{ transfer.remotePath }}</strong>
                      <span class="bulk-status" :class="`status-${transfer.status}`">{{ statusLabel(transfer.status) }}</span>
                      <span>{{ formatFileSize(transfer.size) }}</span>
                      <em>{{ transfer.error || '-' }}</em>
                    </div>
                  </div>
                  <div>
                    <strong>{{ selectedTask.executionType === 'playbook' ? 'Ansible 日志' : 'stdout' }}</strong>
                    <pre>{{ result.stdout || '无标准输出' }}</pre>
                  </div>
                  <div>
                    <strong>stderr</strong>
                    <pre>{{ result.stderr || result.error || '无错误输出' }}</pre>
                  </div>
                  <span v-if="result.outputTruncated">输出已截断</span>
                </div>
              </template>
            </div>
          </template>
          <div v-else class="bulk-empty">请选择一个任务查看结果。</div>
        </section>
      </div>
    </article>
    <div v-else class="permission-empty">暂无可用功能</div>
  </section>
</template>

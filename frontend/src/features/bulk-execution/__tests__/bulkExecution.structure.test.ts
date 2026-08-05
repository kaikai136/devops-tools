import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

function readSource(relativePath: string) {
  return readFileSync(new URL(`../../../${relativePath}`, import.meta.url), 'utf8');
}

describe('bulk execution frontend contract', () => {
  it('registers bulkExecution as a host-management sibling page in navigation and app shell', () => {
    const types = readSource('types.ts');
    const navigation = readSource('app/navigation.ts');
    const shellState = readSource('composables/app/useShellState.ts');
    const app = readSource('App.vue');

    expect(types).toContain("'bulkExecution'");
    expect(navigation).toContain("key: 'bulkExecution' as const");
    expect(navigation).toMatch(/sessionAudits[\s\S]+bulkExecution[\s\S]+accounts/);
    expect(shellState).toMatch(/bulkExecution:\s*'(terminal|zap)'/);
    expect(app).toContain('BulkExecutionPanel');
    expect(app).toContain("activeTool === 'bulkExecution'");
  });

  it('exposes typed API helpers for targets, task creation, polling, cancel, and delete', () => {
    const api = readSource('features/bulk-execution/api/bulkExecution.ts');
    const types = readSource('features/bulk-execution/types.ts');

    expect(types).toContain('BulkExecutionTarget');
    expect(types).toContain('BulkExecutionTargetGroup');
    expect(types).toContain('BulkExecutionTargetTree');
    expect(types).toContain('BulkExecutionTaskDetail');
    expect(api).toContain('/api/bulk-execution');
    expect(api).toContain('listBulkExecutionTargets');
    expect(api).toContain('listBulkExecutionTargetTree');
    expect(api).toContain('/target-tree/');
    expect(api).toContain('createBulkExecutionTask');
    expect(api).toContain('listBulkExecutionTasks');
    expect(api).toContain('getBulkExecutionTask');
    expect(api).toContain('cancelBulkExecutionTask');
    expect(api).toContain('deleteBulkExecutionTask');
  });

  it('exposes upload check, multipart upload helpers, and typed upload metadata', () => {
    const api = readSource('features/bulk-execution/api/bulkExecution.ts');
    const types = readSource('features/bulk-execution/types.ts');

    expect(types).toContain("BulkExecutionType = 'shell' | 'playbook' | 'file_upload'");
    expect(types).toContain('BulkFileUploadCreatePayload');
    expect(types).toContain('BulkUploadCheckResult');
    expect(types).toContain('BulkExecutionUploadFile');
    expect(types).toContain('BulkTransferItem');
    expect(types).toContain('remoteDirectory');
    expect(types).toContain('uploadFilename');
    expect(types).toContain('uploadSize');
    expect(types).toContain('files: File[]');
    expect(api).toContain('createBulkFileUploadTask');
    expect(api).toContain('checkBulkFileUpload');
    expect(api).toContain('/uploads/check/');
    expect(api).toContain('FormData');
    expect(api).toContain("form.append('executionType', 'file_upload')");
    expect(api).toContain("form.append('files'");
    expect(api).toContain("form.append('overwrite'");
  });

  it('adds host-list shortcuts that store selected hosts and open the bulk execution page', () => {
    const manager = readSource('features/hosts/components/HostManager.vue');
    const table = readSource('features/hosts/components/HostTable.vue');
    const toolbar = readSource('features/hosts/components/HostToolbar.vue');

    expect(manager).toContain('ops-tool.bulk-execution.draft-target-ids');
    expect(manager).toContain('ops-tool.bulk-execution.upload-target-ids');
    expect(manager).toContain("setActiveTool('bulkExecution')");
    expect(manager).toContain("canUsePageAction('bulkExecution', 'execute')");
    expect(table).toContain('bulk-execute-selected');
    expect(table).toContain('upload-file-selected');
    expect(toolbar).toContain('canBulkExecute');
    expect(toolbar).toContain('bulk-execute-selected');
    expect(toolbar).toContain('upload-file-selected');
  });

  it('defines the redesigned page surface with history, execute, and upload views', () => {
    const panel = readSource('features/bulk-execution/components/BulkExecutionPanel.vue');

    expect(panel).toContain('bulk-execution-page');
    expect(panel).toContain('activeBulkView');
    expect(panel).toContain('bulk-execution-actions');
    expect(panel).not.toContain('bulk-view-tabs');
    expect(panel).toContain('bulk-history-view');
    expect(panel).toContain('bulk-record-panel');
    expect(panel).toContain('bulk-record-table');
    expect(panel).toContain('bulk-status-filter');
    expect(panel).toContain('isTaskDetailOpen');
    expect(panel).toContain('bulk-detail-backdrop');
    expect(panel).toContain('role="dialog"');
    expect(panel).toContain('bulk-execute-view');
    expect(panel).toContain('bulk-upload-view');
    expect(panel).toContain('taskHistory');
    expect(panel).toContain('selectedTargetIds');
    expect(panel).toContain('commandInput');
    expect(panel).toContain('requestConfirm');
    expect(panel).toContain('stdout');
    expect(panel).toContain('stderr');
    expect(panel).toContain('setInterval');
  });

  it('uses a confirm-only target picker modal instead of rendering the full host list inline', () => {
    const panel = readSource('features/bulk-execution/components/BulkExecutionPanel.vue');

    const executeView = panel.match(/<section v-show="activeBulkView === 'execute'"[\s\S]*?<footer class="bulk-workbench-footer">/)?.[0] ?? '';
    const uploadView = panel.match(/<section v-show="activeBulkView === 'upload'"[\s\S]*?<footer class="bulk-workbench-footer">/)?.[0] ?? '';
    const pickerModal = panel.match(/<div v-if="isTargetPickerOpen" class="modal-backdrop bulk-target-picker-backdrop">[\s\S]*?<\/div>\s*<div v-if="isTaskDetailOpen"/)?.[0] ?? '';

    expect(panel).toContain('const isTargetPickerOpen = ref(false)');
    expect(panel).toContain('const draftTargetIds = ref<Set<number>>(new Set())');
    expect(panel).toContain('const targetGroupFilter = ref<number | null>(null)');
    expect(panel).toContain("const targetPickerKeyword = ref('')");
    expect(panel).toContain('const targetGroups = ref<BulkExecutionTargetGroup[]>([])');
    expect(panel).toContain('openTargetPicker');
    expect(panel).toContain('confirmTargetSelection');
    expect(panel).toContain('closeTargetPicker');
    expect(panel).toContain('selectedTargetIds.value = new Set(draftTargetIds.value)');
    expect(panel).toContain('draftTargetIds.value = new Set(selectedTargetIds.value)');
    expect(executeView).toContain('bulk-target-summary');
    expect(uploadView).toContain('bulk-target-summary');
    expect(executeView).not.toContain('v-for="target in filteredTargets"');
    expect(uploadView).not.toContain('v-for="target in filteredTargets"');
    expect(pickerModal).toContain('bulk-target-picker-modal');
    expect(pickerModal).toContain('bulk-target-group-tree');
    expect(pickerModal).toContain('targetPickerKeyword');
    expect(pickerModal).toContain('toggleAllPickerTargetsFromEvent');
    expect(pickerModal).toContain('confirmTargetSelection');
    expect(pickerModal).toContain('closeTargetPicker');
    expect(pickerModal).not.toContain('@click.self');
  });

  it('renders selected targets as compact metadata rows with a dedicated remove action', () => {
    const panel = readSource('features/bulk-execution/components/BulkExecutionPanel.vue');
    const styles = readSource('styles/tools/bulk-execution.css');

    expect(panel).toContain('bulk-selected-target-main');
    expect(panel).toContain('bulk-selected-target-name');
    expect(panel).toContain('bulk-selected-target-meta');
    expect(panel).toContain('bulk-selected-target-ip');
    expect(panel).toContain('bulk-selected-target-user');
    expect(panel).toContain('bulk-selected-target-group');
    expect(panel).toContain('bulk-selected-target-remove');
    expect(panel).toContain('aria-label="移除目标机器"');
    expect(styles).toContain('grid-template-columns: minmax(0, 1fr) 34px');
    expect(styles).toContain('.bulk-selected-target-meta');
    expect(styles).toContain('.bulk-selected-target-remove');
  });

  it('keeps view navigation in the top actions with record before execute and upload', () => {
    const panel = readSource('features/bulk-execution/components/BulkExecutionPanel.vue');
    const actions = panel.match(/<div class="bulk-execution-actions">[\s\S]*?<\/div>/)?.[0] ?? '';

    expect(actions).toContain("activeBulkView === 'history'");
    expect(actions).toContain("activeBulkView === 'execute'");
    expect(actions).toContain("activeBulkView === 'upload'");
    expect(actions).toContain('执行记录');
    expect(actions).toContain('新建执行');
    expect(actions).toContain('批量上传');
    expect(actions.indexOf('执行记录')).toBeLessThan(actions.indexOf('新建执行'));
    expect(actions.indexOf('新建执行')).toBeLessThan(actions.indexOf('批量上传'));
    expect(actions.indexOf('批量上传')).toBeLessThan(actions.indexOf('@click="refreshAll"'));
  });

  it('keeps history filters aligned in the record toolbar before refresh without the duplicate execute action', () => {
    const panel = readSource('features/bulk-execution/components/BulkExecutionPanel.vue');
    const toolbar = panel.match(/<header class="bulk-record-toolbar">[\s\S]*?<\/header>/)?.[0] ?? '';
    const actions = panel.match(/<div class="bulk-record-actions">[\s\S]*?<\/div>/)?.[0] ?? '';

    expect(panel).not.toContain('<section class="bulk-execution-filters">');
    expect(actions).toContain('bulk-keyword-filter');
    expect(actions).toContain('bulk-host-filter');
    expect(toolbar).toContain('bulk-status-filter');
    expect(toolbar).toContain('type="search"');
    expect(toolbar).toContain('v-model="keyword"');
    expect(toolbar).toContain('v-model="hostFilter"');
    expect(actions).toContain('bulk-status-filter');
    expect(toolbar).toContain('v-model="statusFilter"');
    expect(toolbar).toContain('@change="setHistoryStatus(statusFilter)"');
    expect(actions.indexOf('bulk-keyword-filter')).toBeLessThan(actions.indexOf('bulk-host-filter'));
    expect(actions.indexOf('bulk-host-filter')).toBeLessThan(actions.indexOf('bulk-status-filter'));
    expect(actions.indexOf('bulk-status-filter')).toBeLessThan(actions.indexOf('@click="refreshAll"'));
    expect(toolbar).not.toContain('bulk-status-tabs');
    expect(toolbar).not.toContain('openCreateDialog');
    expect(toolbar).not.toContain('>批量执行</button>');
  });

  it('paginates bulk task history with the shared footer pattern and right-side task statistics', () => {
    const panel = readSource('features/bulk-execution/components/BulkExecutionPanel.vue');
    const footer = panel.match(/<footer class="bulk-record-footer">[\s\S]*?<\/footer>/)?.[0] ?? '';

    expect(panel).toContain('const taskPage = ref(1)');
    expect(panel).toContain('const taskPageSize = ref(10)');
    expect(panel).toContain('const taskTotal = ref(0)');
    expect(panel).toContain('page: taskPage.value');
    expect(panel).toContain('pageSize: taskPageSize.value');
    expect(panel).toContain('taskTotal.value = page.count');
    expect(panel).toContain('pageNumbers');
    expect(panel).toContain('setTaskPage');
    expect(panel).toContain('setTaskPageSize');
    expect(footer).toContain('host-pagination');
    expect(footer).toContain('host-pagination-controls');
    expect(footer).toContain('bulk-record-stats');
    expect(footer).toContain('{{ taskTotal }} 个任务 · {{ targets.length }} 台可执行主机');
  });

  it('defines the upload page pre-check flow and multi-file target handoff', () => {
    const panel = readSource('features/bulk-execution/components/BulkExecutionPanel.vue');

    expect(panel).toContain('uploadTargetIdsKey');
    expect(panel).toContain('selectedUploadFiles');
    expect(panel).toContain('remoteDirectory');
    expect(panel).toContain('uploadCheckResult');
    expect(panel).toContain('checkBulkUpload');
    expect(panel).toContain('duplicateFiles');
    expect(panel).toContain('unreachableTargets');
    expect(panel).toContain('overwriteConfirmed');
    expect(panel).toContain('createBulkFileUploadTask');
    expect(panel).toContain('bulk-upload-dropzone');
    expect(panel).toContain('bulk-upload-check-panel');
    expect(panel).toContain('type="file"');
    expect(panel).toContain('multiple');
    expect(panel).toContain('开始上传');
  });

  it('renders upload transfer details on each task result', () => {
    const panel = readSource('features/bulk-execution/components/BulkExecutionPanel.vue');
    const types = readSource('features/bulk-execution/types.ts');

    expect(types).toContain('transfers: BulkTransferItem[]');
    expect(panel).toContain('result.transfers');
    expect(panel).toContain('bulk-transfer-matrix');
    expect(panel).toContain('transfer.remotePath');
  });

  it('supports shell scripts and playbook scripts in the task composer', () => {
    const panel = readSource('features/bulk-execution/components/BulkExecutionPanel.vue');
    const types = readSource('features/bulk-execution/types.ts');

    expect(types).toContain("BulkExecutionType = 'shell' | 'playbook'");
    expect(types).toContain('executionType');
    expect(panel).toContain('executionType');
    expect(panel).toContain('Shell');
    expect(panel).toContain('Playbook');
    expect(panel).toContain('scriptPresets');
    expect(panel).toContain('executionType: executionType.value');
  });
});

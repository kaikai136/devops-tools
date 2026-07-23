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
    expect(types).toContain('BulkExecutionTaskDetail');
    expect(api).toContain('/api/bulk-execution');
    expect(api).toContain('listBulkExecutionTargets');
    expect(api).toContain('createBulkExecutionTask');
    expect(api).toContain('listBulkExecutionTasks');
    expect(api).toContain('getBulkExecutionTask');
    expect(api).toContain('cancelBulkExecutionTask');
    expect(api).toContain('deleteBulkExecutionTask');
  });

  it('adds a host-list shortcut that stores selected hosts and opens the bulk execution page', () => {
    const manager = readSource('features/hosts/components/HostManager.vue');
    const table = readSource('features/hosts/components/HostTable.vue');
    const toolbar = readSource('features/hosts/components/HostToolbar.vue');

    expect(manager).toContain('ops-tool.bulk-execution.draft-target-ids');
    expect(manager).toContain("setActiveTool('bulkExecution')");
    expect(manager).toContain("canUsePageAction('bulkExecution', 'execute')");
    expect(table).toContain('bulk-execute-selected');
    expect(toolbar).toContain('canBulkExecute');
    expect(toolbar).toContain('bulk-execute-selected');
  });

  it('defines the bulk execution page surface with task history, target picker, command input, confirmation, and result output', () => {
    const panel = readSource('features/bulk-execution/components/BulkExecutionPanel.vue');

    expect(panel).toContain('bulk-execution-page');
    expect(panel).toContain('taskHistory');
    expect(panel).toContain('selectedTargetIds');
    expect(panel).toContain('commandInput');
    expect(panel).toContain('requestConfirm');
    expect(panel).toContain('stdout');
    expect(panel).toContain('stderr');
    expect(panel).toContain('setInterval');
  });
});

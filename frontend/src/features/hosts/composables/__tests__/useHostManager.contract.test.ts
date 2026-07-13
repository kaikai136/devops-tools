import { effectScope } from 'vue';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { useHostManager } from '../../../../composables/features/useHostManager';

const expectedHostManagerKeys = [
  'addManagedHost',
  'applyCredentialToHostForm',
  'backupHostManagement',
  'cancelHostGroupInlineEdit',
  'clearHostGroupDropTarget',
  'closeHostGroupMenu',
  'deleteHostGroup',
  'deleteManagedHost',
  'deleteManagedHostsInGroup',
  'deleteSelectedManagedHosts',
  'draggedHostGroupId',
  'dropHostGroup',
  'editManagedHost',
  'exportHostManagement',
  'finishHostGroupDrag',
  'flatHostGroups',
  'groupMoveHosts',
  'hostCredentials',
  'hostDialog',
  'hostForm',
  'hostFormErrors',
  'hostGroupDropTarget',
  'hostGroupInlineEdit',
  'hostGroupMenu',
  'hostGroupName',
  'hostGroupRoot',
  'hostGroupRootExpanded',
  'hostGroupRows',
  'hostGroups',
  'hostMoveDialogOpen',
  'hostMoveForm',
  'hostMoveMode',
  'hostSearch',
  'hostSortDirection',
  'hostSortKey',
  'hostSortMark',
  'hostStatusFilter',
  'importHostManagement',
  'isHostGroupExpanded',
  'isLoadingHosts',
  'loadHostCredentials',
  'loadHostManagement',
  'managedHostStats',
  'managedHosts',
  'openAddHostGroup',
  'openAddRootHostGroup',
  'openHostGroupMenu',
  'openMoveHostDialog',
  'openMoveSelectedHostsDialog',
  'openRenameHostGroup',
  'openWebTerminal',
  'removeHostCredential',
  'replaceHostCredential',
  'rootHostGroupDialogOpen',
  'rootHostGroupName',
  'rootHostGroupSortAfter',
  'saveHostGroupInlineEdit',
  'saveManagedHost',
  'saveMoveManagedHost',
  'saveRootHostGroup',
  'selectManagedGroup',
  'selectedHostGroup',
  'selectedManagedHostIds',
  'setHostSort',
  'startHostGroupDrag',
  'toggleHostGroupExpanded',
  'toggleHostGroupRootExpanded',
  'updateHostGroupDropTarget',
  'uploadHostPrivateKey',
  'verifyManagedHost',
  'verifySelectedManagedHosts',
  'verifyVisibleManagedHosts',
  'verifyingHostIds',
  'visibleHostGroups',
  'visibleManagedHosts',
];

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('useHostManager facade contract', () => {
  it('preserves the complete public return contract and representative behavior', () => {
    const getItem = vi.fn(() => null);
    const setItem = vi.fn();
    vi.stubGlobal('window', {
      localStorage: { getItem, setItem },
      open: vi.fn(),
    });

    const scope = effectScope();
    const manager = scope.run(() =>
      useHostManager({
        showToast: vi.fn(),
        requestConfirm: vi.fn(),
        currentUsername: () => 'contract-user',
      }),
    )!;

    expect(Object.keys(manager).sort()).toEqual(expectedHostManagerKeys);
    expect(expectedHostManagerKeys).toHaveLength(75);
    expect(manager.hostSearch.value).toBe('');
    expect(manager.selectedHostGroup.value).toBeNull();
    expect(manager.hostStatusFilter.value).toBe('all');
    expect(manager.hostSortKey.value).toBe('name');
    expect(manager.hostSortDirection.value).toBe('asc');
    expect(manager.hostGroups.value).toEqual([]);
    expect(manager.hostCredentials.value).toEqual([]);
    expect(manager.managedHosts.value).toEqual([]);
    expect(manager.visibleManagedHosts.value).toEqual([]);
    expect(manager.flatHostGroups.value).toEqual([]);
    expect(manager.visibleHostGroups.value).toEqual([]);
    expect(manager.managedHostStats.value).toEqual({ total: 0, verified: 0, unverified: 0 });
    expect(manager.hostGroupRoot.value).toMatchObject({ key: null, label: 'DEFAULT', count: 0, level: 0, isRoot: true });
    expect(manager.hostGroupRootExpanded.value).toBe(true);
    expect(manager.hostDialog.value).toBeNull();
    expect(manager.hostForm.value.name).toBe('host-10');
    expect(manager.hostMoveDialogOpen.value).toBe(false);
    expect(manager.isLoadingHosts.value).toBe(false);
    expect(manager.verifyingHostIds.value).toEqual(new Set());
    expect(manager.selectedManagedHostIds.value).toEqual(new Set());

    expect(manager.loadHostManagement).toBeTypeOf('function');
    expect(manager.backupHostManagement).toBeTypeOf('function');
    expect(manager.importHostManagement).toBeTypeOf('function');
    expect(manager.openWebTerminal).toBeTypeOf('function');
    expect(manager.saveManagedHost).toBeTypeOf('function');
    expect(manager.verifyManagedHost).toBeTypeOf('function');
    expect(manager.deleteSelectedManagedHosts).toBeTypeOf('function');

    manager.selectManagedGroup(42);
    expect(manager.selectedHostGroup.value).toBe(42);
    expect(manager.hostSortMark('name')).toBe('↑');
    manager.setHostSort('name');
    expect(manager.hostSortDirection.value).toBe('desc');
    expect(manager.hostSortMark('name')).toBe('↓');
    manager.setHostSort('ip');
    expect(manager.hostSortKey.value).toBe('ip');
    expect(manager.hostSortDirection.value).toBe('asc');
    expect(manager.hostSortMark('name')).toBe('↕');
    manager.toggleHostGroupRootExpanded();
    expect(manager.hostGroupRootExpanded.value).toBe(false);

    manager.replaceHostCredential({
      id: 1,
      name: 'root',
      username: 'root',
      password: 'secret',
      port: 22,
      privateKeyName: '',
      privateKey: '',
      remark: '',
    });
    expect(manager.hostCredentials.value).toHaveLength(1);
    manager.removeHostCredential(1);
    expect(manager.hostCredentials.value).toEqual([]);
    expect(getItem).toHaveBeenCalledWith('ops-tool.host-manager.root-label');

    scope.stop();
  });
});

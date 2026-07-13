import { computed, ref, type Ref } from 'vue';

import * as hostApi from '@features/hosts/api/hosts';
import type { HostCredential, HostGroup, ManagedHost } from '@features/hosts/types';
import { compareHosts, findGroup, type HostSortKey, type SortDirection } from '@features/hosts/utils/groups';

export type HostStatusFilter = 'all' | 'verified' | 'unverified';
export type HostManagerConfirm = (title: string, message: string, actionText: string, action: () => Promise<void>) => void;

interface UseHostListOptions {
  showToast: (title: string, message: string) => void;
  requestConfirm: HostManagerConfirm;
  selectedHostGroup: Ref<number | null>;
  groupIdsFor: (groupKey: number) => Set<number>;
  loadHostCredentials: () => Promise<HostCredential[]>;
  replaceHostGroups: (groups: HostGroup[]) => void;
  replaceHostCredentials: (credentials: HostCredential[]) => void;
  pruneCollapsedHostGroups: (groups: HostGroup[]) => void;
  refreshGroupsOnly: () => Promise<void>;
}

export function useHostList({
  showToast,
  requestConfirm,
  selectedHostGroup,
  groupIdsFor,
  loadHostCredentials,
  replaceHostGroups,
  replaceHostCredentials,
  pruneCollapsedHostGroups,
  refreshGroupsOnly,
}: UseHostListOptions) {
  const hostSearch = ref('');
  const hostStatusFilter = ref<HostStatusFilter>('all');
  const hostSortKey = ref<HostSortKey>('name');
  const hostSortDirection = ref<SortDirection>('asc');
  const managedHosts = ref<ManagedHost[]>([]);
  const isLoadingHosts = ref(false);
  const selectedManagedHostIds = ref<Set<number>>(new Set());

  const visibleManagedHosts = computed(() => {
    const query = hostSearch.value.trim().toLowerCase();
    const selectedKeys = selectedHostGroup.value ? groupIdsFor(selectedHostGroup.value) : new Set<number>();
    const filtered = managedHosts.value.filter((host) => {
      const groupMatched = selectedKeys.size ? selectedKeys.has(host.group) : true;
      const statusMatched =
        hostStatusFilter.value === 'all' ||
        (hostStatusFilter.value === 'verified' && host.verified) ||
        (hostStatusFilter.value === 'unverified' && !host.verified);
      const searchMatched =
        !query ||
        [host.name, host.machineName, host.systemArch, host.systemType, host.publicIp, host.privateIp, host.creator, host.platformType]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(query));
      return groupMatched && statusMatched && searchMatched;
    });

    return [...filtered].sort((left, right) => compareHosts(left, right, hostSortKey.value, hostSortDirection.value));
  });

  const managedHostStats = computed(() => ({
    total: managedHosts.value.length,
    verified: managedHosts.value.filter((host) => host.verified).length,
    unverified: managedHosts.value.filter((host) => !host.verified).length,
  }));

  async function loadHostManagement() {
    isLoadingHosts.value = true;
    try {
      const [groups, hosts, credentials] = await Promise.all([
        hostApi.listHostGroups(),
        hostApi.listManagedHosts(),
        loadHostCredentials(),
      ]);
      replaceHostGroups(groups);
      managedHosts.value = hosts;
      replaceHostCredentials(credentials);
      pruneCollapsedHostGroups(groups);
      if (selectedHostGroup.value && !findGroup(groups, selectedHostGroup.value)) selectedHostGroup.value = null;
    } catch (error) {
      showToast('加载失败', (error as Error).message);
    } finally {
      isLoadingHosts.value = false;
    }
  }

  function setHostSort(key: HostSortKey) {
    if (hostSortKey.value === key) {
      hostSortDirection.value = hostSortDirection.value === 'asc' ? 'desc' : 'asc';
    } else {
      hostSortKey.value = key;
      hostSortDirection.value = 'asc';
    }
  }

  function hostSortMark(key: HostSortKey) {
    if (hostSortKey.value !== key) return '↕';
    return hostSortDirection.value === 'asc' ? '↑' : '↓';
  }

  function deleteManagedHost(host: ManagedHost) {
    requestConfirm('删除主机', `确定删除主机「${host.name}」吗？`, '确定删除', async () => {
      await deleteHostById(host.id);
      showToast('操作成功', '主机已删除。');
    });
  }

  function deleteSelectedManagedHosts() {
    const hosts = managedHosts.value.filter((host) => selectedManagedHostIds.value.has(host.id));
    if (!hosts.length) {
      showToast('删除失败', '请先选择需要删除的主机。');
      return;
    }
    requestConfirm('删除所选主机', `确定删除所选 ${hosts.length} 台主机吗？`, '确定删除', async () => {
      await Promise.all(hosts.map((host) => hostApi.deleteManagedHost(host.id)));
      const deletedIds = new Set(hosts.map((host) => host.id));
      managedHosts.value = managedHosts.value.filter((host) => !deletedIds.has(host.id));
      selectedManagedHostIds.value = new Set();
      await refreshGroupsOnly();
      showToast('操作成功', `已删除 ${hosts.length} 台主机。`);
    });
  }

  async function deleteHostById(hostId: number) {
    await hostApi.deleteManagedHost(hostId);
    managedHosts.value = managedHosts.value.filter((item) => item.id !== hostId);
    await refreshGroupsOnly();
  }

  function replaceHost(host: ManagedHost) {
    const index = managedHosts.value.findIndex((item) => item.id === host.id);
    if (index >= 0) {
      managedHosts.value.splice(index, 1, host);
    } else {
      managedHosts.value = [host, ...managedHosts.value];
    }
  }

  return {
    hostSearch,
    hostStatusFilter,
    hostSortKey,
    hostSortDirection,
    managedHosts,
    isLoadingHosts,
    selectedManagedHostIds,
    visibleManagedHosts,
    managedHostStats,
    loadHostManagement,
    setHostSort,
    hostSortMark,
    deleteManagedHost,
    deleteSelectedManagedHosts,
    replaceHost,
  };
}

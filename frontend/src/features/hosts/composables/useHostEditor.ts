import { computed, ref, watch, type ComputedRef, type Ref } from 'vue';

import * as hostApi from '@features/hosts/api/hosts';
import type { HostCredential, ManagedHost } from '@features/hosts/types';
import type { FlatHostGroup } from '@features/hosts/utils/groups';
import type { HostGroupMenuGroup } from './useHostGroups';
import type { HostStatusFilter } from './useHostList';

export interface ManagedHostForm {
  name: string;
  group: number | null;
  credential: number | null;
  publicIp: string;
  privateIp: string;
  port: number;
  loginUser: string;
  loginPassword: string;
  privateKeyName: string;
  privateKey: string;
  remark: string;
  cpu: number;
  memory: number;
  os: HostOs;
  verified: boolean;
}

export type HostFormErrors = Partial<Record<'group' | 'name' | 'privateIp' | 'os' | 'port', string>>;

export interface HostMoveForm {
  hostId: number | null;
  targetGroup: number | null;
}

type HostOs = ManagedHost['os'] | '';

interface UseHostEditorOptions {
  showToast: (title: string, message: string) => void;
  currentUsername: () => string | null | undefined;
  selectedHostGroup: Ref<number | null>;
  flatHostGroups: ComputedRef<FlatHostGroup[]>;
  hostGroupMenu: Ref<{ group: HostGroupMenuGroup; x: number; y: number } | null>;
  closeHostGroupMenu: () => void;
  ensureDefaultHostGroup: () => Promise<number | null>;
  refreshGroupsOnly: () => Promise<void>;
  groupIdsFor: (groupKey: number) => Set<number>;
  hostCredentials: Ref<HostCredential[]>;
  loadHostCredentials: () => Promise<HostCredential[]>;
  managedHosts: Ref<ManagedHost[]>;
  selectedManagedHostIds: Ref<Set<number>>;
  replaceHost: (host: ManagedHost) => void;
  hostSearch: Ref<string>;
  hostStatusFilter: Ref<HostStatusFilter>;
}

const selectableHostOsValues: readonly ManagedHost['os'][] = ['centos', 'windows'];
const SSH_DEFAULT_PORT = 22;
const RDP_DEFAULT_PORT = 3389;

export function useHostEditor({
  showToast,
  currentUsername,
  selectedHostGroup,
  flatHostGroups,
  hostGroupMenu,
  closeHostGroupMenu,
  ensureDefaultHostGroup,
  refreshGroupsOnly,
  groupIdsFor,
  hostCredentials,
  loadHostCredentials,
  managedHosts,
  selectedManagedHostIds,
  replaceHost,
  hostSearch,
  hostStatusFilter,
}: UseHostEditorOptions) {
  const hostDialog = ref<{ mode: 'create' | 'edit'; hostId: number | null } | null>(null);
  const hostForm = ref<ManagedHostForm>(emptyHostForm());
  const hostFormErrors = ref<HostFormErrors>({});
  const hostMoveDialogOpen = ref(false);
  const hostMoveMode = ref<'single' | 'selected'>('single');
  const hostMoveForm = ref<HostMoveForm>({ hostId: null, targetGroup: null });
  const hostMoveSourceGroup = ref<number | null>(null);

  const groupMoveHosts = computed(() => {
    if (hostMoveSourceGroup.value === null) return managedHosts.value;
    const ids = groupIdsFor(hostMoveSourceGroup.value);
    return managedHosts.value.filter((host) => ids.has(host.group));
  });

  watch(
    hostForm,
    () => {
      if (Object.keys(hostFormErrors.value).length) validateHostForm();
    },
    { deep: true },
  );
  watch(
    () => hostForm.value.os,
    (nextOs) => {
      if (hostDialog.value?.mode !== 'create') return;
      hostForm.value.port = defaultPortForHostOs(nextOs);
    },
  );

  function openWebTerminal(host?: ManagedHost) {
    const params = new URLSearchParams();
    if (host) {
      params.set('host', String(host.id));
    } else if (selectedHostGroup.value) {
      params.set('group', String(selectedHostGroup.value));
    }
    const url = `/terminal.html${params.toString() ? `?${params.toString()}` : ''}`;
    const target = window.open(url, '_blank', 'noopener,noreferrer');
    if (!target) {
      showToast('Web 终端', '浏览器阻止了新窗口，请允许弹窗后重试。');
    }
  }

  function openSimpleHostTerminal(host: ManagedHost) {
    const params = new URLSearchParams({ host: String(host.id) });
    const width = 980;
    const height = 720;
    const left = Math.max(0, Math.round(window.screenX + (window.outerWidth - width) / 2));
    const top = Math.max(0, Math.round(window.screenY + (window.outerHeight - height) / 2));
    const features = [
      'popup=yes',
      'noopener',
      'noreferrer',
      `width=${width}`,
      `height=${height}`,
      `left=${left}`,
      `top=${top}`,
      'resizable=yes',
      'scrollbars=no',
    ].join(',');
    const target = window.open(`/host-terminal.html?${params.toString()}`, `host-terminal-${host.id}`, features);
    if (!target) {
      showToast('Web 终端', '浏览器阻止了新窗口，请允许弹窗后重试。');
    }
  }

  async function addManagedHost(group: number | null = selectedHostGroup.value ?? flatHostGroups.value[0]?.key ?? null) {
    closeHostGroupMenu();
    try {
      await loadHostCredentials();
    } catch (error) {
      showToast('账号加载失败', (error as Error).message);
    }
    let targetGroup: number | null = group ?? flatHostGroups.value[0]?.key ?? null;
    if (!targetGroup) {
      try {
        targetGroup = await ensureDefaultHostGroup();
      } catch (error) {
        showToast('分组创建失败', (error as Error).message);
        return;
      }
    }
    if (!targetGroup) {
      showToast('分组创建失败', '未返回默认分组。');
      return;
    }
    hostForm.value = emptyHostForm(targetGroup, managedHosts.value.length + 10);
    hostFormErrors.value = {};
    hostDialog.value = { mode: 'create', hostId: null };
  }

  function editManagedHost(host: ManagedHost) {
    hostForm.value = {
      name: host.name,
      group: host.group,
      credential: null,
      publicIp: host.publicIp ?? '',
      privateIp: host.privateIp,
      port: host.port ?? SSH_DEFAULT_PORT,
      loginUser: host.loginUser ?? '',
      loginPassword: host.loginPassword ?? '',
      privateKeyName: host.privateKeyName ?? '',
      privateKey: host.privateKey ?? '',
      remark: host.remark ?? '',
      cpu: host.cpu,
      memory: host.memory,
      os: isSelectableHostOs(host.os) ? host.os : '',
      verified: host.verified,
    };
    hostFormErrors.value = {};
    hostDialog.value = { mode: 'edit', hostId: host.id };
  }

  function validateHostForm() {
    const errors: HostFormErrors = {};
    const privateIp = hostForm.value.privateIp.trim();
    const port = Number(hostForm.value.port);

    if (!hostForm.value.group) {
      errors.group = '请选择主机分组。';
    }
    if (!hostForm.value.name.trim() || !hostForm.value.privateIp.trim()) {
      if (!hostForm.value.name.trim()) errors.name = '请输入节点名称。';
      if (!privateIp) errors.privateIp = '请输入主机 IP。';
    } else if (!isIPv4Address(privateIp)) {
      errors.privateIp = '请输入正确的主机 IP。';
    }
    if (!isSelectableHostOs(hostForm.value.os)) {
      errors.os = '请选择平台类型。';
    }
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      errors.port = '端口范围为 1-65535。';
    }

    hostFormErrors.value = errors;
    return !Object.keys(errors).length;
  }

  async function saveManagedHost() {
    if (!validateHostForm()) {
      return;
    }

    const payload = {
      ...hostForm.value,
      name: hostForm.value.name.trim(),
      publicIp: hostForm.value.publicIp.trim() || null,
      privateIp: hostForm.value.privateIp.trim(),
      loginUser: hostForm.value.loginUser.trim(),
      loginPassword: hostForm.value.loginPassword.trim(),
      privateKeyName: hostForm.value.privateKeyName.trim(),
      privateKey: hostForm.value.privateKey.trim(),
      remark: hostForm.value.remark.trim(),
    };
    delete (payload as Partial<ManagedHostForm>).credential;
    delete (payload as Partial<ManagedHostForm>).verified;
    const mode = hostDialog.value?.mode ?? 'create';
    const creator = currentUsername()?.trim();
    if (mode === 'create' && creator) {
      (payload as typeof payload & { creator: string }).creator = creator;
    }
    const saved =
      mode === 'edit' && hostDialog.value?.hostId
        ? await hostApi.updateManagedHost(hostDialog.value.hostId, payload)
        : await hostApi.createManagedHost(payload);

    replaceHost(saved);
    selectedHostGroup.value = saved.group;
    hostSearch.value = '';
    hostStatusFilter.value = 'all';
    hostFormErrors.value = {};
    hostDialog.value = null;
    await refreshGroupsOnly();
    showToast('操作成功', mode === 'edit' ? '主机已更新。' : '主机已添加。');
  }

  function applyCredentialToHostForm() {
    const credential = hostCredentials.value.find((item) => item.id === hostForm.value.credential);
    if (!credential) return;
    hostForm.value.loginUser = credential.username;
    hostForm.value.loginPassword = credential.password;
    hostForm.value.privateKeyName = credential.privateKeyName;
    hostForm.value.privateKey = credential.privateKey;
  }

  async function uploadHostPrivateKey(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    hostForm.value.privateKeyName = file.name;
    hostForm.value.privateKey = await file.text();
    input.value = '';
  }

  function openMoveHostDialog(group = hostGroupMenu.value?.group) {
    if (!group) return;
    closeHostGroupMenu();
    hostMoveMode.value = 'single';
    hostMoveSourceGroup.value = group.key;
    const sourceHosts = group.key === null ? managedHosts.value : managedHosts.value.filter((host) => groupIdsFor(group.key).has(host.group));
    hostMoveForm.value = {
      hostId: sourceHosts[0]?.id ?? null,
      targetGroup: flatHostGroups.value.find((item) => item.key !== group.key)?.key ?? null,
    };
    hostMoveDialogOpen.value = true;
  }

  function openMoveSelectedHostsDialog() {
    const selectedHosts = managedHosts.value.filter((host) => selectedManagedHostIds.value.has(host.id));
    if (!selectedHosts.length) {
      showToast('更新失败', '请先选择需要更新的主机。');
      return;
    }
    hostMoveMode.value = 'selected';
    hostMoveSourceGroup.value = null;
    const currentGroup = selectedHosts[0]?.group ?? null;
    hostMoveForm.value = {
      hostId: null,
      targetGroup: flatHostGroups.value.find((item) => item.key !== currentGroup)?.key ?? currentGroup,
    };
    hostMoveDialogOpen.value = true;
  }

  async function saveMoveManagedHost() {
    if (hostMoveMode.value === 'selected') {
      const targetGroup = hostMoveForm.value.targetGroup;
      const hosts = managedHosts.value.filter((item) => selectedManagedHostIds.value.has(item.id));
      if (!targetGroup || !hosts.length) {
        showToast('更新失败', '请选择主机和目标分组。');
        return;
      }
      const updatedHosts = await Promise.all(hosts.map((host) => hostApi.updateManagedHost(host.id, { group: targetGroup })));
      updatedHosts.forEach(replaceHost);
      selectedHostGroup.value = targetGroup;
      hostMoveDialogOpen.value = false;
      selectedManagedHostIds.value = new Set();
      await refreshGroupsOnly();
      showToast('操作成功', `已更新 ${updatedHosts.length} 台主机的分组。`);
      return;
    }

    const host = managedHosts.value.find((item) => item.id === hostMoveForm.value.hostId);
    if (!host || !hostMoveForm.value.targetGroup) {
      showToast('移动失败', '请选择主机和目标分组。');
      return;
    }
    const updated = await hostApi.updateManagedHost(host.id, { group: hostMoveForm.value.targetGroup });
    replaceHost(updated);
    selectedHostGroup.value = updated.group;
    hostMoveDialogOpen.value = false;
    await refreshGroupsOnly();
    showToast('操作成功', `${updated.name} 已移动到目标分组。`);
  }

  return {
    hostDialog,
    hostForm,
    hostFormErrors,
    hostMoveDialogOpen,
    hostMoveMode,
    hostMoveForm,
    groupMoveHosts,
    openWebTerminal,
    openSimpleHostTerminal,
    addManagedHost,
    editManagedHost,
    saveManagedHost,
    applyCredentialToHostForm,
    uploadHostPrivateKey,
    openMoveHostDialog,
    openMoveSelectedHostsDialog,
    saveMoveManagedHost,
  };
}

function isSelectableHostOs(value: HostOs): value is ManagedHost['os'] {
  return selectableHostOsValues.some((option) => option === value);
}

function defaultPortForHostOs(value: HostOs) {
  return value === 'windows' ? RDP_DEFAULT_PORT : SSH_DEFAULT_PORT;
}

function isIPv4Address(value: string) {
  const parts = value.split('.');
  return (
    parts.length === 4 &&
    parts.every((part) => {
      if (!/^\d{1,3}$/.test(part)) return false;
      const octet = Number(part);
      return octet >= 0 && octet <= 255;
    })
  );
}

function emptyHostForm(group: number | null = null, sequence = 10): ManagedHostForm {
  return {
    name: `host-${sequence}`,
    group,
    credential: null,
    publicIp: '',
    privateIp: '',
    port: SSH_DEFAULT_PORT,
    loginUser: '',
    loginPassword: '',
    privateKeyName: '',
    privateKey: '',
    remark: '',
    cpu: 2,
    memory: 4,
    os: 'centos',
    verified: false,
  };
}

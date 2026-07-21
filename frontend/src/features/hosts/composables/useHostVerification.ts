import { ref, type ComputedRef, type Ref } from 'vue';

import * as hostApi from '@features/hosts/api/hosts';
import type { ManagedHost } from '@features/hosts/types';

interface UseHostVerificationOptions {
  showToast: (title: string, message: string) => void;
  managedHosts: Ref<ManagedHost[]>;
  visibleManagedHosts: ComputedRef<ManagedHost[]>;
  selectedManagedHostIds: Ref<Set<number>>;
  replaceHost: (host: ManagedHost) => void;
}

export function useHostVerification({
  showToast,
  managedHosts,
  visibleManagedHosts,
  selectedManagedHostIds,
  replaceHost,
}: UseHostVerificationOptions) {
  const verifyingHostIds = ref<Set<number>>(new Set());

  async function verifyManagedHost(host: ManagedHost) {
    if (verifyingHostIds.value.has(host.id)) return null;

    setHostVerifying(host.id, true);
    try {
      const result = await hostApi.verifyManagedHost(host.id);
      replaceHost(result.host);
      if (result.verified) {
        const credentialMessage = result.credentialSaved ? '已保存登录信息。' : '';
        showToast('验证完成', `${result.host.name} 已获取机器配置。${credentialMessage}`);
      } else {
        showToast('验证失败', `${result.host.name} 连接失败，配置信息已清空。${result.error ? ` ${result.error}` : ''}`);
      }
      return result.host;
    } catch (error) {
      const failedHost = { ...host, verified: false, verifyStatus: 'failed' as const, cpu: 0, memory: 0 };
      replaceHost(failedHost);
      showToast('验证失败', `${host.name} 连接失败，配置信息已清空。${(error as Error).message}`);
      return failedHost;
    } finally {
      setHostVerifying(host.id, false);
    }
  }

  async function verifyVisibleManagedHosts() {
    const hosts = [...visibleManagedHosts.value];
    await Promise.all(hosts.map((host) => verifyManagedHost(host)));
  }

  async function verifySelectedManagedHosts() {
    const hosts = managedHosts.value.filter((host) => selectedManagedHostIds.value.has(host.id));
    if (!hosts.length) {
      showToast('验证失败', '请先选择需要验证的主机。');
      return;
    }
    await Promise.all(hosts.map((host) => verifyManagedHost(host)));
  }

  function setHostVerifying(hostId: number, active: boolean) {
    verifyingHostIds.value = setWithValue(verifyingHostIds.value, hostId, active);
  }

  return {
    verifyingHostIds,
    verifyManagedHost,
    verifyVisibleManagedHosts,
    verifySelectedManagedHosts,
  };
}

function setWithValue<T>(source: Set<T>, value: T, active: boolean) {
  const next = new Set(source);
  if (active) {
    next.add(value);
  } else {
    next.delete(value);
  }
  return next;
}

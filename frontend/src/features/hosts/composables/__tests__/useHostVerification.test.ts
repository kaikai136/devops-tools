import { computed, effectScope, ref } from 'vue';
import { describe, expect, it, vi } from 'vitest';

import { useHostVerification } from '../useHostVerification';
import type { ManagedHost } from '../../types';

vi.mock('../../api/hosts', () => ({
  verifyManagedHost: vi.fn(),
}));

import * as hostApi from '../../api/hosts';

function makeHost(id: number): ManagedHost {
  return {
    id,
    name: `host-${id}`,
    group: 1,
    privateIp: `10.0.0.${id}`,
    publicIp: '',
    port: 22,
    loginUser: 'root',
    loginPassword: '',
    privateKeyName: '',
    privateKey: '',
    os: 'centos',
    platformType: 'linux',
    machineName: '',
    systemArch: '',
    systemType: '',
    cpu: 0,
    memory: 0,
    verified: false,
    verifyStatus: 'unverified',
    creator: '',
    remark: '',
    createdAt: '',
    updatedAt: '',
  };
}

describe('useHostVerification', () => {
  it('starts selected host verification concurrently instead of blocking on the first host', async () => {
    const firstHost = makeHost(1);
    const secondHost = makeHost(2);
    const managedHosts = ref([firstHost, secondHost]);
    const selectedManagedHostIds = ref(new Set([1, 2]));
    const resolveByHost = new Map<number, (value: unknown) => void>();
    const verifyManagedHost = vi.mocked(hostApi.verifyManagedHost);
    verifyManagedHost.mockImplementation(
      (hostId) =>
        new Promise((resolve) => {
          resolveByHost.set(hostId, resolve);
        }) as ReturnType<typeof hostApi.verifyManagedHost>,
    );

    const scope = effectScope();
    const manager = scope.run(() =>
      useHostVerification({
        showToast: vi.fn(),
        managedHosts,
        visibleManagedHosts: computed(() => managedHosts.value),
        selectedManagedHostIds,
        replaceHost: vi.fn(),
      }),
    )!;

    const pending = manager.verifySelectedManagedHosts();
    await Promise.resolve();

    expect(verifyManagedHost).toHaveBeenCalledTimes(2);
    expect(manager.verifyingHostIds.value).toEqual(new Set([1, 2]));
    resolveByHost.get(1)?.({ host: { ...firstHost, verified: true }, verified: true, error: null, credentialSaved: false });
    resolveByHost.get(2)?.({ host: { ...secondHost, verified: true }, verified: true, error: null, credentialSaved: false });
    await pending;
    expect(manager.verifyingHostIds.value).toEqual(new Set());
    scope.stop();
  });
});

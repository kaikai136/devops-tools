import { ref } from 'vue';

import * as hostApi from '@features/hosts/api/hosts';
import type { HostCredential } from '@features/hosts/types';

export function useHostCredentials() {
  const hostCredentials = ref<HostCredential[]>([]);

  async function loadHostCredentials() {
    const credentials = await hostApi.listHostCredentials();
    hostCredentials.value = credentials;
    return credentials;
  }

  function replaceHostCredential(credential: HostCredential) {
    const index = hostCredentials.value.findIndex((item) => item.id === credential.id);
    if (index >= 0) {
      hostCredentials.value.splice(index, 1, credential);
    } else {
      hostCredentials.value.push(credential);
    }
  }

  function removeHostCredential(credentialId: number) {
    hostCredentials.value = hostCredentials.value.filter((item) => item.id !== credentialId);
  }

  function replaceHostCredentials(credentials: HostCredential[]) {
    hostCredentials.value = credentials;
  }

  return {
    hostCredentials,
    loadHostCredentials,
    replaceHostCredential,
    removeHostCredential,
    replaceHostCredentials,
  };
}

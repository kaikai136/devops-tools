import { computed, ref } from 'vue';

import { apiPost } from '../../api';
import type { HostResult, IpScanResponse } from '../../types';
import { createHostGrid } from '../../utils/network';

export function useIpScanner({
  showToast,
  selectHost,
}: {
  showToast: (title: string, message: string) => void;
  selectHost: (ip: string) => void;
}) {
  const networkSegment = ref('192.168.1');
  const hosts = ref<HostResult[]>(createHostGrid(networkSegment.value));
  const ipProgress = ref(0);
  const isScanningIp = ref(false);
  const ipScanMessage = ref('');
  const onlineHosts = computed(() => hosts.value.filter((host) => host.status === 'online'));
  const offlineHosts = computed(() => hosts.value.filter((host) => host.status !== 'online'));

  async function scanIp() {
    if (isScanningIp.value) return;
    isScanningIp.value = true;
    ipProgress.value = 6;
    ipScanMessage.value = '';
    const started = performance.now();
    const timer = window.setInterval(() => {
      const elapsed = performance.now() - started;
      const estimatedDuration = 7200;
      const nextProgress = 6 + Math.floor((elapsed / estimatedDuration) * 93);
      ipProgress.value = Math.min(Math.max(ipProgress.value + 1, nextProgress), 99);
    }, 140);
    try {
      const result = await apiPost<HostResult[] | IpScanResponse>('/api/scan/ip/', {
        network: networkSegment.value,
        timeout_ms: 900,
        retries: 2,
        concurrency: 64,
      });
      const scanResults = Array.isArray(result) ? result : result.results;
      hosts.value = scanResults;
      const firstOnline = scanResults.find((host) => host.status === 'online');
      if (firstOnline) selectHost(firstOnline.ip);
      ipProgress.value = 100;
      const duration = Array.isArray(result) ? Math.round(performance.now() - started) : result.duration;
      ipScanMessage.value = `扫描完成：${onlineHosts.value.length}/254 在线，耗时 ${duration} ms`;
    } catch (error) {
      showToast('操作失败', (error as Error).message);
    } finally {
      window.clearInterval(timer);
      isScanningIp.value = false;
    }
  }

  return {
    networkSegment,
    hosts,
    ipProgress,
    isScanningIp,
    ipScanMessage,
    onlineHosts,
    offlineHosts,
    scanIp,
  };
}

import { computed, ref, type Ref } from 'vue';

import { apiPost } from '../../api';
import type { PingDetail, PingSession, PortScanResult } from '../../types';
import { parsePortInput, sleep } from '../../utils/network';
import { buildPingChart, calculatePingMetrics } from '../../utils/ping';

export function useMachineProbe({
  showToast,
  selectedHost,
}: {
  showToast: (title: string, message: string) => void;
  selectedHost: Ref<string>;
}) {
  const portHost = ref('192.168.1.1');
  const portsInput = ref('80,443,8000,8080,8443,9000');
  const portTimeout = ref(600);
  const portConcurrency = ref(300);
  const portResult = ref<PortScanResult | null>(null);
  const portProgress = ref(0);
  const portScanMessage = ref('');
  const portStartedAt = ref(0);
  const isScanningPorts = ref(false);
  const portAbort = ref<AbortController | null>(null);

  const pingHost = ref('192.168.1.1');
  const pingCount = ref(4);
  const pingTimeout = ref(3000);
  const pingInterval = ref(1000);
  const pingContinuous = ref(false);
  const pingDetails = ref<PingDetail[]>([]);
  const isPinging = ref(false);
  const pingAbort = ref<AbortController | null>(null);
  const pingStartedAt = ref(0);
  const pingMetrics = computed(() => calculatePingMetrics(pingDetails.value));
  const pingChart = computed(() => buildPingChart(pingDetails.value, pingMetrics.value.average_response_time));

  function setProbeHost(ip: string) {
    portHost.value = ip;
    pingHost.value = ip;
  }

  function applyPortPreset(value: string) {
    const presets: Record<string, string> = {
      common: '21,22,23,25,53,80,110,143,443,445,993,995,3389',
      top100: Array.from({ length: 100 }, (_, index) => index + 1).join(','),
      top1024: '1-1024',
      all: '1-65535',
      database: '1433,1521,3306,5432,6379,27017',
      web: '80,443,8000,8080,8443,9000',
    };
    portsInput.value = presets[value] ?? portsInput.value;
  }

  async function scanPorts() {
    if (isScanningPorts.value) return;
    let ports: number[] = [];
    try {
      ports = parsePortInput(portsInput.value);
    } catch (error) {
      showToast('操作失败', (error as Error).message);
      return;
    }

    const totalPorts = ports.length;
    const effectiveTimeout = Math.max(100, Math.min(5000, Number(portTimeout.value) || 600));
    const effectiveConcurrency = Math.max(1, Math.min(512, Number(portConcurrency.value) || 300, totalPorts));
    const batchSize = Math.max(1, Math.min(totalPorts, Math.max(effectiveConcurrency, 200)));

    isScanningPorts.value = true;
    portStartedAt.value = performance.now();
    portProgress.value = 0;
    portScanMessage.value = `准备扫描 ${totalPorts} 个端口`;
    portResult.value = {
      host: portHost.value,
      open_ports: [],
      open_details: [],
      scanned_ports: 0,
      total_ports: totalPorts,
      timeout_ms: effectiveTimeout,
      concurrency: effectiveConcurrency,
      duration: 0,
    };
    const controller = new AbortController();
    portAbort.value = controller;

    try {
      for (let index = 0; index < ports.length; index += batchSize) {
        if (controller.signal.aborted) break;
        const batch = ports.slice(index, index + batchSize);
        portScanMessage.value = `扫描中：${portResult.value.scanned_ports}/${totalPorts} · 本批 ${batch.length} 个端口`;
        const batchResult = await apiPost<PortScanResult>(
          '/api/scan/ports/',
          { host: portHost.value, ports: batch.join(','), timeout_ms: effectiveTimeout, concurrency: effectiveConcurrency },
          { signal: controller.signal },
        );

        portResult.value.host = batchResult.host;
        portResult.value.scanned_ports += batchResult.scanned_ports;
        portResult.value.duration = Math.round(performance.now() - portStartedAt.value);
        portResult.value.open_ports = Array.from(new Set([...portResult.value.open_ports, ...batchResult.open_ports])).sort((left, right) => left - right);
        portResult.value.open_details = [...(portResult.value.open_details ?? []), ...(batchResult.open_details ?? [])].sort((left, right) => left.port - right.port);
        portResult.value.error = batchResult.error;
        portProgress.value = Math.round((portResult.value.scanned_ports / totalPorts) * 100);

        if (batchResult.error) break;
      }

      portProgress.value = 100;
      portResult.value.duration = Math.round(performance.now() - portStartedAt.value);
      portScanMessage.value = portResult.value?.error
        ? `扫描异常：${portResult.value.error}`
        : `扫描完成：${portResult.value.scanned_ports}/${portResult.value.total_ports ?? totalPorts} 个端口，发现 ${portResult.value.open_ports.length} 个开放`;
    } catch (error) {
      if ((error as Error).name !== 'AbortError') {
        portScanMessage.value = '';
        showToast('操作失败', (error as Error).message);
      }
    } finally {
      isScanningPorts.value = false;
      portAbort.value = null;
    }
  }

  function stopPortScan() {
    portAbort.value?.abort();
    isScanningPorts.value = false;
    portProgress.value = 0;
    portScanMessage.value = '扫描已停止';
  }

  function setPingPreset(host: string) {
    pingHost.value = host;
  }

  function useSelectedIpForPing() {
    pingHost.value = selectedHost.value;
    portHost.value = selectedHost.value;
    showToast('已使用选中 IP', `目标已切换为 ${selectedHost.value}。`);
  }

  async function runPing() {
    if (isPinging.value) return;
    pingDetails.value = [];
    isPinging.value = true;
    pingStartedAt.value = performance.now();
    const controller = new AbortController();
    pingAbort.value = controller;

    try {
      if (pingContinuous.value) {
        let sequence = 1;
        while (!controller.signal.aborted) {
          const session = await apiPost<PingSession>(
            '/api/ping/',
            { host: pingHost.value, count: 1, timeout_ms: pingTimeout.value, interval_ms: pingInterval.value },
            { signal: controller.signal },
          );
          appendPingDetails(session.details, sequence);
          sequence += session.details.length;
          await sleep(Math.max(100, pingInterval.value), controller.signal);
        }
      } else {
        const session = await apiPost<PingSession>(
          '/api/ping/',
          { host: pingHost.value, count: pingCount.value, timeout_ms: pingTimeout.value, interval_ms: pingInterval.value },
          { signal: controller.signal },
        );
        appendPingDetails(session.details, 1);
      }
    } catch (error) {
      if ((error as Error).name !== 'AbortError') showToast('Ping 失败', (error as Error).message);
    } finally {
      isPinging.value = false;
      pingAbort.value = null;
    }
  }

  function appendPingDetails(details: PingDetail[], startSequence: number) {
    const normalized = details.map((detail, index) => ({
      ...detail,
      sequence: startSequence + index,
      timestamp: detail.timestamp ?? Date.now(),
    }));
    pingDetails.value = [...pingDetails.value, ...normalized];
  }

  function stopPing() {
    pingAbort.value?.abort();
    isPinging.value = false;
  }

  function clearPingResults() {
    pingDetails.value = [];
  }

  function exportPingResults() {
    if (!pingDetails.value.length) {
      showToast('导出失败', '还没有可导出的 Ping 结果。');
      return;
    }
    const rows = [
      ['序号', '目标', '解析 IP', '状态', '延迟(ms)', '时间'],
      ...pingDetails.value.map((item) => [
        String(item.sequence),
        item.target,
        item.ip,
        item.status === 'online' ? '成功' : '超时',
        item.response_time === null ? '' : String(item.response_time),
        new Date(item.timestamp ?? Date.now()).toLocaleString(),
      ]),
    ];
    const csv = rows.map((row) => row.map((cell) => `"${cell.replace(/"/g, '""')}"`).join(',')).join('\n');
    const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `ping-${pingHost.value}-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return {
    portHost,
    portsInput,
    portTimeout,
    portConcurrency,
    portResult,
    portProgress,
    portScanMessage,
    isScanningPorts,
    pingHost,
    pingCount,
    pingTimeout,
    pingInterval,
    pingContinuous,
    pingDetails,
    isPinging,
    pingMetrics,
    pingChart,
    setProbeHost,
    applyPortPreset,
    scanPorts,
    stopPortScan,
    setPingPreset,
    useSelectedIpForPing,
    runPing,
    stopPing,
    clearPingResults,
    exportPingResults,
  };
}

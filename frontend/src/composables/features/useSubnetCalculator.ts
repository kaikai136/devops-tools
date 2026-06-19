import { computed, ref } from 'vue';

import { apiPost } from '../../api';
import type { SubnetResult } from '../../types';
import { prefixToMask, subnetBinaryParts } from '../../utils/subnet';

export function useSubnetCalculator({
  showToast,
}: {
  showToast: (title: string, message: string) => void;
}) {
  const subnetInput = ref('192.168.1.0/24');
  const subnetPrefix = ref(24);
  const subnetTargetPrefix = ref(26);
  const subnetSplitMode = ref<'count' | 'hosts'>('count');
  const subnetResult = ref<SubnetResult | null>(null);
  const subnetPresets = ['192.168.1.0/24', '10.0.0.0/24', '172.16.10.0/24', '192.168.0.0/22', '10.10.0.0/16'];

  const prefixOptions = computed(() =>
    Array.from({ length: 33 }, (_, prefix) => prefix).map((prefix) => ({
      value: prefix,
      label: `/${prefix} (${prefixToMask(prefix)})`,
    })),
  );

  const subnetSplitChoices = computed(() => {
    const start = Math.max(subnetPrefix.value + 1, 1);
    if (start > 32) return [];
    return Array.from({ length: 32 - start + 1 }, (_, index) => start + index).map((prefix) => {
      const count = 2 ** (prefix - subnetPrefix.value);
      const addressCount = 2 ** (32 - prefix);
      const usableHosts = prefix < 31 ? Math.max(addressCount - 2, 0) : addressCount;
      return {
        value: prefix,
        count,
        usableHosts,
        label: subnetSplitMode.value === 'count' ? `${count} 个子网 · /${prefix}` : `${usableHosts} 台主机 / 子网 · /${prefix}`,
      };
    });
  });

  const subnetSplitSummary = computed(() => {
    const prefix = subnetTargetPrefix.value;
    const count = prefix > subnetPrefix.value ? 2 ** (prefix - subnetPrefix.value) : 0;
    const addressCount = 2 ** (32 - prefix);
    return {
      prefix,
      mask: prefixToMask(prefix),
      count,
      usableHosts: prefix < 31 ? Math.max(addressCount - 2, 0) : addressCount,
    };
  });

  const canSplitSubnet = computed(() => subnetPrefix.value < 32 && subnetTargetPrefix.value > subnetPrefix.value);

  const subnetTypeText = computed(() => {
    if (!subnetResult.value) return '未计算';
    if (subnetResult.value.is_loopback) return '回环地址';
    if (subnetResult.value.is_multicast) return '组播地址';
    return subnetResult.value.is_private ? '私有地址' : '公网地址';
  });

  const subnetClassText = computed(() => {
    if (!subnetResult.value) return '--';
    const first = Number(subnetResult.value.ip.split('.')[0]);
    if (first <= 127) return 'A 类';
    if (first <= 191) return 'B 类';
    if (first <= 223) return 'C 类';
    if (first <= 239) return 'D 类';
    return 'E 类';
  });

  function normalizedSubnetInput() {
    const base = subnetInput.value.trim().split('/')[0] || '192.168.1.0';
    return `${base}/${subnetPrefix.value}`;
  }

  async function calculateSubnet(withSplit = false) {
    try {
      subnetInput.value = normalizedSubnetInput();
      if (withSplit && !canSplitSubnet.value) {
        showToast('无法划分', '当前前缀已经不能继续拆分。');
        return;
      }
      subnetResult.value = await apiPost<SubnetResult>('/api/subnet/calculate/', {
        input: subnetInput.value,
        prefix: subnetPrefix.value,
        ...(withSplit ? { target_prefix: subnetTargetPrefix.value } : {}),
      });
      if (withSplit) showToast('操作成功', '子网划分已生成。');
    } catch (error) {
      showToast('计算失败', (error as Error).message);
    }
  }

  async function handlePrefixChange() {
    subnetInput.value = normalizedSubnetInput();
    if (subnetTargetPrefix.value <= subnetPrefix.value) subnetTargetPrefix.value = Math.min(subnetPrefix.value + 1, 32);
    await calculateSubnet(false);
  }

  function setSubnetPreset(value: string) {
    subnetInput.value = value;
    const [, prefix] = value.split('/');
    subnetPrefix.value = Number(prefix || 24);
    subnetTargetPrefix.value = Math.min(subnetPrefix.value + 2, 32);
    calculateSubnet(false);
  }

  function clearSubnet() {
    subnetInput.value = '192.168.1.0/24';
    subnetPrefix.value = 24;
    subnetTargetPrefix.value = 26;
    subnetSplitMode.value = 'count';
    subnetResult.value = null;
  }

  return {
    subnetInput,
    subnetPrefix,
    subnetTargetPrefix,
    subnetSplitMode,
    subnetResult,
    subnetPresets,
    prefixOptions,
    subnetSplitChoices,
    subnetSplitSummary,
    canSplitSubnet,
    subnetTypeText,
    subnetClassText,
    subnetBinaryParts,
    calculateSubnet,
    handlePrefixChange,
    setSubnetPreset,
    clearSubnet,
  };
}

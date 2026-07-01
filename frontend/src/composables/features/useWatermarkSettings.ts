import { computed, ref, watch } from 'vue';

import { dashboardNavItem, navGroups } from '../../navigation';
import { createSystemSetting, getSystemSettingOrNull, updateSystemSetting } from '../../services/system';
import type { SystemSetting, ToolKey, WatermarkConfig } from '../../types';

export const WATERMARK_SETTING_KEY = 'watermark';

export const defaultWatermarkConfig: WatermarkConfig = {
  enabled: false,
  text: 'CAPTAIN',
  pages: [],
};

export const watermarkExtraPages = [{ key: 'webTerminal', label: 'Web 终端', group: '独立页面' }];

export const watermarkPageGroups = [
  {
    key: 'dashboard',
    label: '核心页面',
    pages: [{ key: dashboardNavItem.key, label: dashboardNavItem.label }],
  },
  ...navGroups.map((group) => ({
    key: group.key,
    label: group.label,
    pages: group.items.map((item) => ({ key: item.key, label: item.label })),
  })),
  {
    key: 'standalone',
    label: '独立页面',
    pages: watermarkExtraPages.map((page) => ({ key: page.key, label: page.label })),
  },
];

const allowedWatermarkPages = new Set(watermarkPageGroups.flatMap((group) => group.pages.map((page) => page.key)));

interface WatermarkFeedback {
  showToast?: (title: string, message?: string, tone?: 'success' | 'error' | 'info') => void;
  getWatermarkText?: () => string | null | undefined;
}

function resolveWatermarkText(text?: string | null) {
  return String(text ?? '').trim() || defaultWatermarkConfig.text;
}

function createDefaultWatermarkConfig(text?: string | null): WatermarkConfig {
  return {
    ...defaultWatermarkConfig,
    text: resolveWatermarkText(text),
  };
}

export function normalizeWatermarkConfig(value: unknown, text = defaultWatermarkConfig.text): WatermarkConfig {
  if (!value || typeof value !== 'object') return createDefaultWatermarkConfig(text);
  const raw = value as Partial<WatermarkConfig>;
  const pages = Array.isArray(raw.pages)
    ? raw.pages.map((page) => String(page)).filter((page, index, list) => allowedWatermarkPages.has(page) && list.indexOf(page) === index)
    : [];
  return {
    enabled: Boolean(raw.enabled),
    text: resolveWatermarkText(text),
    pages,
  };
}

export function watermarkAppliesToPage(config: WatermarkConfig, page: ToolKey | 'webTerminal') {
  return Boolean(config.enabled && config.text.trim() && config.pages.includes(page));
}

export function useWatermarkSettings(feedback: WatermarkFeedback = {}) {
  const watermarkText = computed(() => resolveWatermarkText(feedback.getWatermarkText?.()));
  const watermarkConfig = ref<WatermarkConfig>(createDefaultWatermarkConfig(watermarkText.value));
  const watermarkDraft = ref<WatermarkConfig>(createDefaultWatermarkConfig(watermarkText.value));
  const watermarkSettingExists = ref(false);
  const watermarkLoading = ref(false);
  const watermarkSaving = ref(false);
  const watermarkMessage = ref('');

  watch(watermarkText, (text) => {
    watermarkConfig.value.text = text;
    watermarkDraft.value.text = text;
  });

  async function loadWatermarkSetting() {
    watermarkLoading.value = true;
    watermarkMessage.value = '';
    try {
      const setting = await fetchWatermarkSetting();
      watermarkSettingExists.value = Boolean(setting);
      watermarkConfig.value = normalizeWatermarkConfig(setting?.value, watermarkText.value);
      watermarkDraft.value = { ...watermarkConfig.value, pages: [...watermarkConfig.value.pages] };
    } catch (error) {
      watermarkSettingExists.value = false;
      watermarkConfig.value = createDefaultWatermarkConfig(watermarkText.value);
      watermarkDraft.value = createDefaultWatermarkConfig(watermarkText.value);
      watermarkMessage.value = error instanceof Error ? error.message : '水印设置加载失败';
    } finally {
      watermarkLoading.value = false;
    }
  }

  async function saveWatermarkSetting() {
    watermarkDraft.value.text = watermarkText.value;
    const payload = normalizeWatermarkConfig(watermarkDraft.value, watermarkText.value);

    watermarkSaving.value = true;
    watermarkMessage.value = '';
    try {
      const body = {
        key: WATERMARK_SETTING_KEY,
        label: '水印设置',
        description: '页面水印配置',
        value: payload,
      };
      const setting = watermarkSettingExists.value
        ? await updateSystemSetting(WATERMARK_SETTING_KEY, body)
        : await createSystemSetting(body);
      watermarkSettingExists.value = true;
      watermarkConfig.value = normalizeWatermarkConfig(setting.value, watermarkText.value);
      watermarkDraft.value = { ...watermarkConfig.value, pages: [...watermarkConfig.value.pages] };
      feedback.showToast?.('水印设置已保存', '', 'success');
    } catch (error) {
      watermarkMessage.value = error instanceof Error ? error.message : '水印设置保存失败';
    } finally {
      watermarkSaving.value = false;
    }
  }

  function resetWatermarkDraft() {
    watermarkDraft.value = { ...watermarkConfig.value, pages: [...watermarkConfig.value.pages] };
    watermarkMessage.value = '';
  }

  return {
    watermarkConfig,
    watermarkDraft,
    watermarkText,
    watermarkLoading,
    watermarkSaving,
    watermarkMessage,
    loadWatermarkSetting,
    saveWatermarkSetting,
    resetWatermarkDraft,
  };
}

async function fetchWatermarkSetting(): Promise<SystemSetting | null> {
  return getSystemSettingOrNull(WATERMARK_SETTING_KEY);
}

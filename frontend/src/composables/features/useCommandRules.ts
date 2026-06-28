import { computed, ref } from 'vue';

import { apiDelete, apiGet, apiPost, apiPut } from '../../api';
import type { SecurityCommandRecord, SecurityCommandRule, SecurityCommandRuleDraft } from '../../types';

interface CommandRuleFeedback {
  showToast: (title: string, message?: string, tone?: 'success' | 'error' | 'info') => void;
  requestConfirm: (title: string, message: string, confirmText: string, action: () => Promise<void> | void) => void;
}

const defaultDraft: SecurityCommandRuleDraft = {
  name: '',
  matchType: 'command',
  content: '',
  ignoreCase: true,
  action: 'block',
  enabled: true,
  remark: '',
};

export function useCommandRules({ showToast, requestConfirm }: CommandRuleFeedback) {
  const commandRules = ref<SecurityCommandRule[]>([]);
  const commandRecords = ref<SecurityCommandRecord[]>([]);
  const commandRuleSearch = ref('');
  const commandRuleMessage = ref('');
  const isCommandRuleLoading = ref(false);
  const isCommandRecordLoading = ref(false);
  const commandRuleDialog = ref<{
    visible: boolean;
    mode: 'create' | 'edit';
    ruleId: number | null;
    draft: SecurityCommandRuleDraft;
    saving: boolean;
    error: string;
  }>({
    visible: false,
    mode: 'create',
    ruleId: null,
    draft: createCommandRuleDraft(),
    saving: false,
    error: '',
  });

  const filteredCommandRules = computed(() => {
    const query = commandRuleSearch.value.trim().toLowerCase();
    if (!query) return commandRules.value;
    return commandRules.value.filter((rule) =>
      [rule.name, rule.content, rule.remark, rule.action, rule.matchType]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query)),
    );
  });

  const commandRuleStats = computed(() => ({
    total: commandRules.value.length,
    enabled: commandRules.value.filter((rule) => rule.enabled).length,
    blockedRecords: commandRecords.value.filter((record) => record.blocked).length,
  }));

  async function loadCommandRules() {
    isCommandRuleLoading.value = true;
    commandRuleMessage.value = '';
    try {
      commandRules.value = await apiGet<SecurityCommandRule[]>('/api/security/command-rules/');
    } catch (error) {
      commandRuleMessage.value = error instanceof Error ? error.message : '命令规则加载失败';
    } finally {
      isCommandRuleLoading.value = false;
    }
  }

  async function loadCommandRecords() {
    isCommandRecordLoading.value = true;
    try {
      commandRecords.value = await apiGet<SecurityCommandRecord[]>('/api/security/command-records/?limit=100');
    } catch (error) {
      commandRuleMessage.value = error instanceof Error ? error.message : '命令记录加载失败';
    } finally {
      isCommandRecordLoading.value = false;
    }
  }

  async function loadCommandSecurity() {
    await Promise.allSettled([loadCommandRules(), loadCommandRecords()]);
  }

  function openCommandRuleDialog(rule: SecurityCommandRule | null = null) {
    commandRuleDialog.value = {
      visible: true,
      mode: rule ? 'edit' : 'create',
      ruleId: rule?.id ?? null,
      draft: createCommandRuleDraft(rule),
      saving: false,
      error: '',
    };
  }

  function closeCommandRuleDialog() {
    if (commandRuleDialog.value.saving) return;
    commandRuleDialog.value = {
      visible: false,
      mode: 'create',
      ruleId: null,
      draft: createCommandRuleDraft(),
      saving: false,
      error: '',
    };
  }

  async function saveCommandRuleDialog() {
    const dialog = commandRuleDialog.value;
    if (!dialog.visible || dialog.saving) return;
    const payload = normalizeCommandRuleDraft(dialog.draft);
    if (!payload.name || !payload.content) {
      commandRuleDialog.value = { ...dialog, error: '请填写名称和命令内容' };
      return;
    }

    commandRuleDialog.value = { ...dialog, saving: true, error: '' };
    try {
      const saved =
        dialog.mode === 'edit' && dialog.ruleId
          ? await apiPut<SecurityCommandRule>(`/api/security/command-rules/${dialog.ruleId}/`, payload)
          : await apiPost<SecurityCommandRule>('/api/security/command-rules/', payload);
      commandRules.value =
        dialog.mode === 'edit'
          ? commandRules.value.map((rule) => (rule.id === saved.id ? saved : rule))
          : [...commandRules.value, saved];
      closeCommandRuleDialog();
      showToast('命令规则已保存', saved.name, 'success');
    } catch (error) {
      commandRuleDialog.value = {
        ...dialog,
        saving: false,
        error: error instanceof Error ? error.message : '命令规则保存失败',
      };
    }
  }

  async function toggleCommandRule(rule: SecurityCommandRule) {
    try {
      const saved = await apiPost<SecurityCommandRule>(`/api/security/command-rules/${rule.id}/toggle/`, {
        enabled: !rule.enabled,
      });
      commandRules.value = commandRules.value.map((item) => (item.id === saved.id ? saved : item));
      showToast(saved.enabled ? '命令规则已激活' : '命令规则已禁用', saved.name, 'success');
    } catch (error) {
      commandRuleMessage.value = error instanceof Error ? error.message : '命令规则状态更新失败';
    }
  }

  function deleteCommandRule(rule: SecurityCommandRule) {
    requestConfirm('删除命令规则', `确定删除“${rule.name}”吗？已有命令记录会保留。`, '确定删除', async () => {
      await apiDelete<{ deleted: boolean }>(`/api/security/command-rules/${rule.id}/`);
      commandRules.value = commandRules.value.filter((item) => item.id !== rule.id);
      showToast('命令规则已删除', rule.name, 'success');
    });
  }

  return {
    commandRules,
    filteredCommandRules,
    commandRecords,
    commandRuleSearch,
    commandRuleMessage,
    commandRuleStats,
    commandRuleDialog,
    isCommandRuleLoading,
    isCommandRecordLoading,
    loadCommandRules,
    loadCommandRecords,
    loadCommandSecurity,
    openCommandRuleDialog,
    closeCommandRuleDialog,
    saveCommandRuleDialog,
    toggleCommandRule,
    deleteCommandRule,
  };
}

function createCommandRuleDraft(rule?: SecurityCommandRule | null): SecurityCommandRuleDraft {
  return {
    name: rule?.name ?? defaultDraft.name,
    matchType: rule?.matchType ?? defaultDraft.matchType,
    content: rule?.content ?? defaultDraft.content,
    ignoreCase: rule?.ignoreCase ?? defaultDraft.ignoreCase,
    action: rule?.action ?? defaultDraft.action,
    enabled: rule?.enabled ?? defaultDraft.enabled,
    remark: rule?.remark ?? defaultDraft.remark,
  };
}

function normalizeCommandRuleDraft(draft: SecurityCommandRuleDraft): SecurityCommandRuleDraft {
  return {
    name: draft.name.trim(),
    matchType: draft.matchType,
    content: draft.content.trim(),
    ignoreCase: draft.ignoreCase,
    action: draft.action,
    enabled: draft.enabled,
    remark: draft.remark.trim(),
  };
}

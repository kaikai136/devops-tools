import { computed, ref, type Ref } from 'vue';

import type { ToolKey } from '../../types';

export type ConfirmAction = () => Promise<void>;
export type ConfirmFn = (title: string, message: string, actionText: string, action: ConfirmAction) => void;

export interface ToastState {
  title: string;
  message: string;
  visible: boolean;
  leaving: boolean;
  scope: ToolKey;
}

export interface ConfirmDialogState {
  title: string;
  message: string;
  actionText: string;
  action: ConfirmAction;
}

export function useFeedback(activeTool: Ref<ToolKey>) {
  const toast = ref<ToastState | null>(null);
  const confirmDialog = ref<ConfirmDialogState | null>(null);
  let toastTimer: number | undefined;
  let toastLeaveTimer: number | undefined;

  const scopedToastVisible = computed(() => toast.value?.visible && toast.value.scope === activeTool.value);
  const toastTone = computed(() => {
    const title = toast.value?.title || '';
    if (/(失败|错误|异常)/.test(title)) return 'error';
    if (/(无法|警告|跳过|已经)/.test(title)) return 'warning';
    if (/(成功|完成|已)/.test(title)) return 'success';
    return 'info';
  });

  function showToast(title: string, message = '') {
    window.clearTimeout(toastTimer);
    window.clearTimeout(toastLeaveTimer);
    toast.value = { title, message, visible: true, leaving: false, scope: activeTool.value };
    toastTimer = window.setTimeout(() => {
      if (!toast.value) return;
      toast.value.leaving = true;
      toastLeaveTimer = window.setTimeout(() => {
        toast.value = null;
      }, 600);
    }, 5000);
  }

  async function copyText(text: string, message = '已复制到剪贴板。') {
    await navigator.clipboard.writeText(text);
    showToast('操作成功', message);
  }

  function requestConfirm(title: string, message: string, actionText: string, action: ConfirmAction) {
    confirmDialog.value = { title, message, actionText, action };
  }

  async function runConfirmAction() {
    if (!confirmDialog.value) return;
    const action = confirmDialog.value.action;
    confirmDialog.value = null;
    await action();
  }

  function clearFeedback() {
    toast.value = null;
    confirmDialog.value = null;
  }

  function cleanupFeedback() {
    window.clearTimeout(toastTimer);
    window.clearTimeout(toastLeaveTimer);
  }

  return {
    toast,
    confirmDialog,
    scopedToastVisible,
    toastTone,
    showToast,
    copyText,
    requestConfirm,
    runConfirmAction,
    clearFeedback,
    cleanupFeedback,
  };
}

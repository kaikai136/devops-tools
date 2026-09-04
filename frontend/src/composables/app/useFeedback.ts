import { ElMessage, ElMessageBox } from 'element-plus';
import type { Ref } from 'vue';

import type { ToolKey } from '../../types';

export type ConfirmAction = () => Promise<void>;
export type ConfirmFn = (title: string, message: string, actionText: string, action: ConfirmAction) => void;
export type ToastTone = 'success' | 'error' | 'warning' | 'info';

export function useFeedback(_activeTool: Ref<ToolKey>) {
  function resolveTone(title: string, tone?: ToastTone): ToastTone {
    if (tone) return tone;
    if (/(失败|错误|异常)/.test(title)) return 'error';
    if (/(无法|警告|跳过|已经)/.test(title)) return 'warning';
    if (/(成功|完成|已)/.test(title)) return 'success';
    return 'info';
  }

  function showToast(title: string, message = '', tone?: ToastTone) {
    const text = message ? `${title}：${message}` : title;
    ElMessage({ type: resolveTone(title, tone), message: text, grouping: true, duration: 5000 });
  }

  async function copyText(text: string, message = '已复制到剪贴板。') {
    await navigator.clipboard.writeText(text);
    showToast('操作成功', message);
  }

  function requestConfirm(title: string, message: string, actionText: string, action: ConfirmAction) {
    ElMessageBox.confirm(message, title, {
      confirmButtonText: actionText,
      cancelButtonText: '取消',
      type: 'warning',
    })
      .then(() => action())
      .catch(() => undefined);
  }

  function clearFeedback() {
    ElMessage.closeAll();
  }

  function cleanupFeedback() {
    ElMessage.closeAll();
  }

  return {
    showToast,
    copyText,
    requestConfirm,
    clearFeedback,
    cleanupFeedback,
  };
}

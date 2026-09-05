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
    if (typeof document === 'undefined') return;

    const toast = document.createElement('article');
    toast.className = `top-toast ${resolveTone(title, tone)}`;
    toast.setAttribute('role', 'status');

    const icon = document.createElement('span');
    icon.className = 'toast-icon';
    icon.setAttribute('aria-hidden', 'true');
    icon.textContent = '!';

    const content = document.createElement('div');
    content.className = 'toast-content';
    const heading = document.createElement('strong');
    heading.textContent = title;
    content.append(heading);
    if (message) {
      const detail = document.createElement('p');
      detail.textContent = message;
      content.append(detail);
    }

    const close = document.createElement('button');
    close.type = 'button';
    close.setAttribute('aria-label', '关闭提示');
    close.textContent = '×';
    const dismiss = () => {
      toast.classList.add('leaving');
      window.setTimeout(() => toast.remove(), 240);
    };
    close.addEventListener('click', dismiss);
    toast.append(icon, content, close);
    document.body.append(toast);
    window.setTimeout(dismiss, 5000);
  }

  async function copyText(text: string, message = '已复制到剪贴板。') {
    await navigator.clipboard.writeText(text);
    showToast('操作成功', message);
  }

  function requestConfirm(title: string, message: string, actionText: string, action: ConfirmAction) {
    if (typeof document === 'undefined') return;

    const overlay = document.createElement('div');
    overlay.className = 'confirm-panel';
    const panel = document.createElement('article');
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'true');
    const heading = document.createElement('h3');
    heading.textContent = title;
    const detail = document.createElement('p');
    detail.textContent = message;
    const actions = document.createElement('div');
    const cancel = document.createElement('button');
    cancel.type = 'button';
    cancel.textContent = '取消';
    const confirm = document.createElement('button');
    confirm.type = 'button';
    confirm.className = 'primary';
    confirm.textContent = actionText;

    const close = () => {
      document.removeEventListener('keydown', onKeydown);
      overlay.remove();
    };
    const onKeydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close();
    };

    cancel.addEventListener('click', close);
    overlay.addEventListener('click', (event) => {
      if (event.target === overlay) close();
    });
    confirm.addEventListener('click', async () => {
      confirm.disabled = true;
      try {
        await action();
        close();
      } catch (error) {
        confirm.disabled = false;
        showToast('操作失败', error instanceof Error ? error.message : '请求未完成', 'error');
      }
    });

    actions.append(cancel, confirm);
    panel.append(heading, detail, actions);
    overlay.append(panel);
    document.body.append(overlay);
    document.addEventListener('keydown', onKeydown);
    confirm.focus();
  }

  function clearFeedback() {
    document.querySelectorAll('.top-toast, .confirm-panel').forEach((element) => element.remove());
  }

  function cleanupFeedback() {
    clearFeedback();
  }

  return {
    showToast,
    copyText,
    requestConfirm,
    clearFeedback,
    cleanupFeedback,
  };
}

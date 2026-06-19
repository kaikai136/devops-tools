import jsQR from 'jsqr';
import { ref, type Ref } from 'vue';

import { apiDelete, apiGet, apiPost, apiPut } from '../../api';
import type { AuthEntry, QrPreview } from '../../types';
import { buildOtpAuthUri, formatBackupTimestamp, formatTotpAlgorithm, normalizeTotpAlgorithm } from '../../utils/auth';
import { readJsonFile } from '../../utils/files';

type ConfirmFn = (title: string, message: string, actionText: string, action: () => Promise<void>) => void;

export function useAuthenticator({
  showToast,
  copyText,
  requestConfirm,
  authImportFile,
  imageInput,
}: {
  showToast: (title: string, message: string) => void;
  copyText: (text: string, message?: string) => Promise<void>;
  requestConfirm: ConfirmFn;
  authImportFile: Ref<HTMLInputElement | null>;
  imageInput: Ref<HTMLInputElement | null>;
}) {
  const authEntries = ref<AuthEntry[]>([]);
  const authForm = ref({ issuer: '', account_name: '', secret: '', digits: 6, period: 30, algorithm: 'SHA1' });
  const authImport = ref('');
  const editingAuthId = ref<number | null>(null);
  const qrPreview = ref<QrPreview | null>(null);

  async function loadAuthEntries() {
    authEntries.value = await apiGet<AuthEntry[]>('/api/authenticators/');
  }

  async function saveAuthEntry() {
    try {
      if (editingAuthId.value) {
        await apiPut<AuthEntry>(`/api/authenticators/${editingAuthId.value}/`, authForm.value);
      } else {
        await apiPost<AuthEntry>('/api/authenticators/', authForm.value);
      }
      resetAuthForm();
      await loadAuthEntries();
      showToast('操作成功', '动态口令条目已保存。');
    } catch (error) {
      const message = (error as Error).message;
      if (message.includes('已经存在')) {
        await loadAuthEntries();
        showToast('已经添加', `这个二维码已经添加过了：${authForm.value.issuer || authForm.value.account_name || '双因子条目'}。`);
        return;
      }
      showToast('操作失败', message);
    }
  }

  async function saveAuthEntries() {
    if (!authEntries.value.length) {
      showToast('导出失败', '还没有可导出的双因子条目。');
      return;
    }
    const now = new Date();
    const backupDocument = {
      exportedAt: now.toISOString(),
      version: 1,
      entries: authEntries.value.map((entry) => ({
        id: crypto.randomUUID ? crypto.randomUUID() : String(entry.id),
        issuer: entry.issuer,
        accountName: entry.account_name,
        secret: entry.secret,
        digits: entry.digits,
        period: entry.period,
        algorithm: formatTotpAlgorithm(entry.algorithm),
        createdAt: new Date(entry.created_at).getTime() || Date.now(),
        otpauthUri: buildOtpAuthUri(entry),
      })),
    };
    const fileName = `authenticator-backup-${formatBackupTimestamp(now)}.json`;
    const blob = new Blob([JSON.stringify(backupDocument, null, 2)], { type: 'application/json;charset=utf-8' });

    const saveFilePicker = window.showSaveFilePicker;
    if (saveFilePicker) {
      try {
        const handle = await saveFilePicker({
          suggestedName: fileName,
          types: [{ description: 'JSON 文档', accept: { 'application/json': ['.json'] } }],
        });
        const writable = await handle.createWritable();
        await writable.write(blob);
        await writable.close();
        showToast('操作成功', '双因子备份文档已保存。请妥善保管密钥文件。');
        return;
      } catch (error) {
        if ((error as Error).name === 'AbortError') return;
        showToast('保存失败', (error as Error).message);
      }
    }

    const url = URL.createObjectURL(blob);
    const link = window.document.createElement('a');
    link.href = url;
    link.download = fileName;
    link.click();
    URL.revokeObjectURL(url);
    showToast('操作成功', '当前浏览器未开放保存位置选择，已使用默认下载。');
  }

  async function importAuthEntries(event: Event) {
    try {
      const data = await readJsonFile(event);
      if (!data) return;
      const entries = Array.isArray(data) ? data : data.entries;
      if (!Array.isArray(entries)) throw new Error('导入文件格式不正确。');
      let created = 0;
      let skipped = 0;
      for (const item of entries) {
        try {
          let parsedUri: URL | null = null;
          if (item.otpauthUri && String(item.otpauthUri).startsWith('otpauth://')) {
            parsedUri = new URL(String(item.otpauthUri));
          }
          await apiPost<AuthEntry>('/api/authenticators/', {
            issuer: item.issuer || parsedUri?.searchParams.get('issuer') || '',
            account_name: item.accountName || item.account_name || item.account || decodeURIComponent(parsedUri?.pathname.replace(/^\//, '').split(':')[1] || ''),
            secret: item.secret || parsedUri?.searchParams.get('secret') || '',
            digits: item.digits || Number(parsedUri?.searchParams.get('digits') || 6),
            period: item.period || Number(parsedUri?.searchParams.get('period') || 30),
            algorithm: normalizeTotpAlgorithm(item.algorithm || parsedUri?.searchParams.get('algorithm') || 'SHA1'),
          });
          created += 1;
        } catch (error) {
          if ((error as Error).message.includes('已经存在')) skipped += 1;
          else throw error;
        }
      }
      await loadAuthEntries();
      showToast('导入完成', `已导入 ${created} 条，跳过 ${skipped} 条已存在记录。`);
    } catch (error) {
      showToast('导入失败', (error as Error).message);
    }
  }

  function editAuth(entry: AuthEntry) {
    editingAuthId.value = entry.id;
    authForm.value = {
      issuer: entry.issuer,
      account_name: entry.account_name,
      secret: entry.secret,
      digits: entry.digits,
      period: entry.period,
      algorithm: entry.algorithm,
    };
  }

  function deleteAuth(entry: AuthEntry) {
    requestConfirm('删除验证码', `确定删除 ${entry.issuer || '未命名服务'} 的双因子条目吗？`, '确定删除', async () => {
      await apiDelete(`/api/authenticators/${entry.id}/`);
      authEntries.value = authEntries.value.filter((item) => item.id !== entry.id);
      showToast('操作成功', '验证码条目已删除。');
    });
  }

  function clearAuthEntries() {
    requestConfirm('清空验证码', `确定清空全部 ${authEntries.value.length} 条双因子条目吗？`, '确定清空', async () => {
      await Promise.all(authEntries.value.map((entry) => apiDelete(`/api/authenticators/${entry.id}/`)));
      authEntries.value = [];
      showToast('操作成功', '验证码列表已清空。');
    });
  }

  async function copyAuthCode(entry: AuthEntry) {
    if (!entry.totp?.code) return;
    await copyText(entry.totp.code, `已复制 ${entry.issuer || entry.account_name} 的当前验证码。`);
  }

  async function showQr(entry: AuthEntry) {
    const result = await apiGet<{ uri: string; data_url: string }>(`/api/authenticators/${entry.id}/qrcode/`);
    qrPreview.value = {
      dataUrl: result.data_url,
      uri: result.uri,
      issuer: entry.issuer || '未命名服务',
      account: entry.account_name || '未填写账号',
    };
  }

  function resetAuthForm() {
    editingAuthId.value = null;
    authImport.value = '';
    authForm.value = { issuer: '', account_name: '', secret: '', digits: 6, period: 30, algorithm: 'SHA1' };
  }

  function parseAuthImport() {
    const uri = authImport.value.trim();
    if (!uri.startsWith('otpauth://')) {
      showToast('解析失败', '请输入有效的 otpauth:// 链接。');
      return;
    }
    const url = new URL(uri);
    const label = decodeURIComponent(url.pathname.replace(/^\//, ''));
    const [issuerFromLabel, accountFromLabel] = label.includes(':') ? label.split(':') : ['', label];
    authForm.value = {
      issuer: url.searchParams.get('issuer') || issuerFromLabel || authForm.value.issuer,
      account_name: accountFromLabel || authForm.value.account_name,
      secret: url.searchParams.get('secret') || authForm.value.secret,
      digits: Number(url.searchParams.get('digits') || 6),
      period: Number(url.searchParams.get('period') || 30),
      algorithm: (url.searchParams.get('algorithm') || 'SHA1').toUpperCase(),
    };
    showToast('操作成功', '链接已解析到表单。');
  }

  async function scanScreenQr() {
    if (!navigator.mediaDevices?.getDisplayMedia) {
      showToast('识别失败', '当前浏览器不支持屏幕二维码识别。');
      return;
    }
    let stream: MediaStream | null = null;
    try {
      stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
      const video = document.createElement('video');
      video.srcObject = stream;
      video.muted = true;
      await video.play();
      await new Promise((resolve) => window.setTimeout(resolve, 350));

      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const context = canvas.getContext('2d');
      if (!context || !canvas.width || !canvas.height) throw new Error('无法读取屏幕画面。');
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
      const qr = jsQR(imageData.data, imageData.width, imageData.height);
      if (!qr?.data) {
        showToast('识别失败', '当前屏幕画面中没有识别到二维码。');
        return;
      }
      authImport.value = qr.data;
      parseAuthImport();
    } catch (error) {
      if ((error as Error).name !== 'NotAllowedError') showToast('识别失败', (error as Error).message);
    } finally {
      stream?.getTracks().forEach((track) => track.stop());
    }
  }

  function triggerImageImport() {
    imageInput.value?.click();
  }

  function triggerAuthImportFile() {
    authImportFile.value?.click();
  }

  async function handleImageImport(event: Event) {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) return;
    const bitmap = await createImageBitmap(file);
    const canvas = document.createElement('canvas');
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    const context = canvas.getContext('2d');
    if (!context) return;
    context.drawImage(bitmap, 0, 0);
    const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
    const qr = jsQR(imageData.data, imageData.width, imageData.height);
    if (!qr?.data) {
      showToast('识别失败', '图片中没有识别到二维码。');
      return;
    }
    authImport.value = qr.data;
    parseAuthImport();
    (event.target as HTMLInputElement).value = '';
  }

  return {
    authEntries,
    authForm,
    authImport,
    editingAuthId,
    qrPreview,
    loadAuthEntries,
    saveAuthEntry,
    saveAuthEntries,
    importAuthEntries,
    editAuth,
    deleteAuth,
    clearAuthEntries,
    copyAuthCode,
    showQr,
    resetAuthForm,
    parseAuthImport,
    scanScreenQr,
    triggerImageImport,
    triggerAuthImportFile,
    handleImageImport,
  };
}

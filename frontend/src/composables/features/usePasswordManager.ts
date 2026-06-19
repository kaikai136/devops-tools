import { ref, type Ref } from 'vue';

import { apiDelete, apiGet, apiPost } from '../../api';
import type { PasswordImportRecord, PasswordRecord } from '../../types';
import { formatBackupTimestamp } from '../../utils/auth';
import { readFileText } from '../../utils/files';

type ConfirmFn = (title: string, message: string, actionText: string, action: () => Promise<void>) => void;

export function usePasswordManager({
  showToast,
  copyText,
  requestConfirm,
  passwordImportFile,
}: {
  showToast: (title: string, message: string) => void;
  copyText: (text: string, message?: string) => Promise<void>;
  requestConfirm: ConfirmFn;
  passwordImportFile: Ref<HTMLInputElement | null>;
}) {
  const passwordProject = ref('');
  const passwordLength = ref(16);
  const passwordOptions = ref({ include_uppercase: true, include_lowercase: true, include_numbers: true, include_symbols: false });
  const passwordResult = ref('');
  const passwordHistory = ref<PasswordRecord[]>([]);

  async function generatePassword() {
    const record = await apiPost<PasswordRecord>('/api/passwords/generate/', {
      project_name: passwordProject.value || '未命名项目',
      length: passwordLength.value,
      ...passwordOptions.value,
    });
    passwordResult.value = record.password;
    passwordHistory.value = [record, ...passwordHistory.value].slice(0, 20);
    await copyText(record.password, `已复制 ${record.project_name} 的密码。`);
  }

  async function loadPasswords() {
    passwordHistory.value = await apiGet<PasswordRecord[]>('/api/passwords/history/');
  }

  async function deletePassword(record: PasswordRecord) {
    requestConfirm('删除密码记录', `确定删除项目「${record.project_name || '未填写项目名称'}」的密码记录吗？`, '确定删除', async () => {
      await apiDelete(`/api/passwords/history/${record.id}/`);
      passwordHistory.value = passwordHistory.value.filter((item) => item.id !== record.id);
      showToast('操作成功', '密码记录已删除。');
    });
  }

  function togglePasswordOption(key: keyof typeof passwordOptions.value) {
    passwordOptions.value[key] = !passwordOptions.value[key];
  }

  function passwordOptionText(record = passwordOptions.value) {
    const parts = [];
    if (record.include_uppercase) parts.push('大写');
    if (record.include_lowercase) parts.push('小写');
    if (record.include_numbers) parts.push('数字');
    if (record.include_symbols) parts.push('符号');
    return parts.length ? parts.join(' / ') : '未选择字符集';
  }

  function buildPasswordRule(record: Pick<PasswordRecord, 'length' | 'include_uppercase' | 'include_lowercase' | 'include_numbers' | 'include_symbols'>) {
    return `${record.length} 位 · ${passwordOptionText(record)}`;
  }

  function parsePasswordRule(rule: string, password: string): PasswordImportRecord {
    const lengthMatch = rule.match(/(\d+)\s*位/);
    return {
      project_name: '',
      password,
      length: lengthMatch ? Number(lengthMatch[1]) : password.length,
      include_uppercase: rule.includes('大写'),
      include_lowercase: rule.includes('小写'),
      include_numbers: rule.includes('数字'),
      include_symbols: rule.includes('符号'),
    };
  }

  function formatRecordTime(value: string) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '--';
    return `${String(date.getMonth() + 1).padStart(2, '0')}/${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
  }

  function formatPasswordExportTime(date = new Date()) {
    return `${date.getFullYear()}/${String(date.getMonth() + 1).padStart(2, '0')}/${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`;
  }

  function buildPasswordHistoryDocument() {
    const lines = ['密码生成器导出', `导出时间: ${formatPasswordExportTime()}`, ''];
    if (passwordResult.value) {
      lines.push('当前结果', `项目名称: ${passwordProject.value || '未填写项目名称'}`, passwordResult.value, '');
    }
    lines.push('生成记录');
    passwordHistory.value.forEach((record, index) => {
      lines.push(
        `[${index + 1}] ${record.password}`,
        `项目名称: ${record.project_name || '未填写项目名称'}`,
        `规则: ${buildPasswordRule(record)}`,
        `时间: ${formatRecordTime(record.created_at)}`,
        '',
      );
    });
    return lines.join('\n').trimEnd();
  }

  function normalizePasswordImportRecord(item: Partial<PasswordRecord> & Record<string, unknown>): PasswordImportRecord | null {
    const password = String(item.password || '').trim();
    if (!password) return null;
    return {
      project_name: String(item.project_name || item.projectName || '').trim(),
      password,
      length: Number(item.length || password.length),
      include_uppercase: Boolean(item.include_uppercase ?? item.includeUppercase ?? true),
      include_lowercase: Boolean(item.include_lowercase ?? item.includeLowercase ?? true),
      include_numbers: Boolean(item.include_numbers ?? item.includeNumbers ?? true),
      include_symbols: Boolean(item.include_symbols ?? item.includeSymbols ?? false),
    };
  }

  function parsePasswordHistoryDocument(text: string): PasswordImportRecord[] {
    const lines = text.replace(/\r\n/g, '\n').split('\n');
    const records: PasswordImportRecord[] = [];
    for (let index = 0; index < lines.length; index += 1) {
      const match = lines[index].trim().match(/^\[\d+\]\s*(.+)$/);
      if (!match) continue;
      const password = match[1].trim();
      let projectName = '';
      let rule = '';
      for (let cursor = index + 1; cursor < lines.length; cursor += 1) {
        const line = lines[cursor].trim();
        if (!line || /^\[\d+\]/.test(line)) break;
        if (line.startsWith('项目名称:')) projectName = line.replace('项目名称:', '').trim();
        if (line.startsWith('规则:')) rule = line.replace('规则:', '').trim();
      }
      const record = parsePasswordRule(rule, password);
      record.project_name = projectName === '未填写项目名称' ? '' : projectName;
      records.push(record);
    }
    return records;
  }

  async function clearPasswordRecords() {
    requestConfirm('清空密码记录', `确定清空全部 ${passwordHistory.value.length} 条密码记录吗？`, '确定清空', async () => {
      await apiDelete('/api/passwords/history/');
      passwordHistory.value = [];
      passwordResult.value = '';
      showToast('操作成功', '密码记录已清空。');
    });
  }

  async function exportPasswordRecords() {
    if (!passwordHistory.value.length && !passwordResult.value) {
      showToast('导出失败', '还没有可导出的密码记录。');
      return;
    }
    const fileName = `password-history-${formatBackupTimestamp()}.txt`;
    const blob = new Blob([buildPasswordHistoryDocument()], { type: 'text/plain;charset=utf-8' });
    if ('showSaveFilePicker' in window) {
      try {
        const handle = await window.showSaveFilePicker({
          suggestedName: fileName,
          types: [{ description: '密码记录文档', accept: { 'text/plain': ['.txt'] } }],
        });
        const writable = await handle.createWritable();
        await writable.write(blob);
        await writable.close();
        showToast('操作成功', '密码记录文档已保存。');
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

  async function importPasswordRecords(event: Event) {
    try {
      const text = await readFileText(event);
      if (!text) return;
      let records: PasswordImportRecord[] = [];
      try {
        const data = JSON.parse(text);
        const source = Array.isArray(data) ? data : data.records;
        if (!Array.isArray(source)) throw new Error('导入文件格式不正确。');
        records = source
          .map((item) => normalizePasswordImportRecord(item))
          .filter((item): item is PasswordImportRecord => Boolean(item));
      } catch {
        records = parsePasswordHistoryDocument(text);
      }
      if (!records.length) throw new Error('没有识别到可导入的密码记录。');
      await apiPost<PasswordRecord[]>('/api/passwords/history/', { records });
      await loadPasswords();
      showToast('导入完成', `已导入 ${records.length} 条密码记录。`);
    } catch (error) {
      showToast('导入失败', (error as Error).message);
    }
  }

  function triggerPasswordImportFile() {
    passwordImportFile.value?.click();
  }

  return {
    passwordProject,
    passwordLength,
    passwordOptions,
    passwordResult,
    passwordHistory,
    generatePassword,
    loadPasswords,
    deletePassword,
    togglePasswordOption,
    passwordOptionText,
    formatRecordTime,
    clearPasswordRecords,
    exportPasswordRecords,
    importPasswordRecords,
    triggerPasswordImportFile,
  };
}

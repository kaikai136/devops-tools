import type { ComputedRef } from 'vue';

import * as hostApi from '@features/hosts/api/hosts';
import type {
  EncryptedHostBackup,
  HostExportOptions,
  HostManagementExport,
  HostTransferFormat,
  ManagedHost,
} from '@features/hosts/types';
import {
  buildHostImportTemplateWorkbook,
  buildHostTableImportPayload,
  buildHostExportPayload,
  buildXlsxWorkbook,
  hostExportColumnOptions,
  parseHostImportWorkbook,
  parseExcelWorkbook,
} from '@features/hosts/utils/export';
import { readFileBuffer, readFileText } from '../../../utils/files';

const xlsxMimeType = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

export { hostExportColumnOptions, hostImportTemplateColumns } from '@features/hosts/utils/export';
export type {
  HostExportColumnKey,
  HostExportColumnOption,
  HostExportOptions,
  HostExportScope,
  HostTransferFormat,
} from '@features/hosts/types';

interface UseHostImportExportOptions {
  showToast: (title: string, message: string) => void;
  visibleManagedHosts: ComputedRef<ManagedHost[]>;
  hostGroupName: (groupKey: number) => string;
  loadHostManagement: () => Promise<void>;
}

export function useHostImportExport({
  showToast,
  visibleManagedHosts,
  hostGroupName,
  loadHostManagement,
}: UseHostImportExportOptions) {
  async function exportHostManagement(format: HostTransferFormat = 'json', options: HostExportOptions = {}) {
    try {
      const selectedIds = new Set(options.selectedIds ?? []);
      const sourceHosts =
        options.scope === 'selected'
          ? visibleManagedHosts.value.filter((host) => selectedIds.has(host.id))
          : visibleManagedHosts.value;
      if (options.scope === 'selected' && !sourceHosts.length) {
        showToast('导出失败', '请先在主机列表中选择需要导出的机器。');
        return false;
      }
      const columns = hostExportColumnOptions.filter((column) => (options.columns?.length ? options.columns.includes(column.field) : true));
      if (!columns.length) {
        showToast('导出失败', '请至少选择一个需要导出的数据列。');
        return false;
      }
      const payload = buildHostExportPayload(sourceHosts, columns, hostGroupName);
      const date = new Date().toISOString().slice(0, 10);
      if (format === 'excel') {
        downloadFile(buildXlsxWorkbook(payload, columns), `host-management-${date}.xlsx`, xlsxMimeType);
      } else {
        downloadFile(JSON.stringify(payload, null, 2), `host-management-${date}.json`, 'application/json;charset=utf-8');
      }
      showToast('导出成功', `已导出 ${payload.hosts.length} 台主机。`);
      return true;
    } catch (error) {
      showToast('导出失败', (error as Error).message);
      return false;
    }
  }

  async function backupHostManagement() {
    try {
      const payload = await hostApi.exportHostManagementBackup();
      const encryptedPayload = await encryptHostBackup(payload);
      const date = new Date().toISOString().slice(0, 10);
      downloadFile(JSON.stringify(encryptedPayload, null, 2), `host-management-backup-${date}.enc.json`, 'application/json;charset=utf-8');
      showToast('备份成功', `已备份 ${payload.hosts.length} 台主机、${payload.groups.length} 个分组、${payload.credentials.length} 个账号。`);
      return true;
    } catch (error) {
      showToast('备份失败', (error as Error).message);
      return false;
    }
  }

  function downloadHostImportTemplate() {
    try {
      downloadFile(buildHostImportTemplateWorkbook(), 'host-import-template.xlsx', xlsxMimeType);
      showToast('模板已下载', '请按模板填写主机分组、节点、IP地址、平台类型、端口和备注。');
      return true;
    } catch (error) {
      showToast('模板下载失败', (error as Error).message);
      return false;
    }
  }

  async function importHostManagement(event: Event, format: HostTransferFormat = 'json') {
    try {
      const payload = format === 'excel' ? await readHostTableImportFile(event) : await readHostRestoreFile(event);
      if (!payload) return;
      const result = await hostApi.importHostManagementBackup(payload);
      await loadHostManagement();
      if (payload.importMode === 'host-table') {
        showToast('导入完成', `已导入 ${result.imported.hosts} 台主机，跳过 ${result.skipped?.hosts ?? 0} 台。`);
      } else {
        showToast(
          '恢复成功',
          `已处理 ${result.imported.hosts} 台主机、${result.imported.groups} 个分组、${result.imported.credentials} 个账号。`,
        );
      }
    } catch (error) {
      showToast(format === 'excel' ? '导入失败' : '恢复失败', (error as Error).message);
    }
  }

  return {
    backupHostManagement,
    downloadHostImportTemplate,
    exportHostManagement,
    importHostManagement,
  };
}

async function readHostTableImportFile(event: Event) {
  const buffer = await readFileBuffer(event);
  if (!buffer) return null;
  const bytes = new Uint8Array(buffer);
  if (bytes[0] === 0x50 && bytes[1] === 0x4b) {
    return parseHostImportWorkbook(bytes);
  }
  return buildHostTableImportPayload(parseExcelWorkbook(new TextDecoder().decode(bytes)).hosts);
}

async function readHostRestoreFile(event: Event) {
  const text = await readFileText(event);
  if (!text) return null;
  const parsed = JSON.parse(text);
  return isEncryptedHostBackup(parsed) ? decryptHostBackup(parsed) : parsed;
}

function downloadFile(content: BlobPart, filename: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

const hostBackupKeyMaterial = 'django-vue.host-management.backup.v1';

async function encryptHostBackup(payload: HostManagementExport): Promise<EncryptedHostBackup> {
  const cryptoApi = getCryptoApi();
  const salt = cryptoApi.getRandomValues(new Uint8Array(16));
  const iv = cryptoApi.getRandomValues(new Uint8Array(12));
  const iterations = 210000;
  const key = await deriveBackupKey(salt, iterations);
  const plainText = new TextEncoder().encode(JSON.stringify(payload));
  const cipherText = new Uint8Array(await cryptoApi.subtle.encrypt({ name: 'AES-GCM', iv }, key, plainText));
  return {
    version: 2,
    encrypted: true,
    algorithm: 'AES-GCM',
    kdf: 'PBKDF2-SHA-256',
    keyMode: 'app-managed',
    iterations,
    salt: bytesToBase64(salt),
    iv: bytesToBase64(iv),
    data: bytesToBase64(cipherText),
    createdAt: new Date().toISOString(),
  };
}

async function decryptHostBackup(backup: EncryptedHostBackup): Promise<HostManagementExport> {
  const cryptoApi = getCryptoApi();
  const salt = base64ToBytes(backup.salt);
  const iv = base64ToBytes(backup.iv);
  const cipherText = base64ToBytes(backup.data);
  const key = await deriveBackupKey(salt, backup.iterations);
  try {
    const plainText = await cryptoApi.subtle.decrypt({ name: 'AES-GCM', iv }, key, cipherText);
    return JSON.parse(new TextDecoder().decode(plainText));
  } catch {
    throw new Error('备份文件解密失败，请使用当前系统生成的加密备份文件。');
  }
}

async function deriveBackupKey(salt: Uint8Array, iterations: number) {
  const cryptoApi = getCryptoApi();
  const baseKey = await cryptoApi.subtle.importKey('raw', new TextEncoder().encode(hostBackupKeyMaterial), 'PBKDF2', false, ['deriveKey']);
  const saltBuffer = new ArrayBuffer(salt.byteLength);
  new Uint8Array(saltBuffer).set(salt);
  return cryptoApi.subtle.deriveKey(
    { name: 'PBKDF2', hash: 'SHA-256', salt: saltBuffer, iterations },
    baseKey,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt'],
  );
}

function getCryptoApi() {
  const cryptoApi = globalThis.crypto;
  if (!cryptoApi?.subtle) throw new Error('当前浏览器环境不支持安全加密接口。');
  return cryptoApi;
}

function isEncryptedHostBackup(value: unknown): value is EncryptedHostBackup {
  if (!value || typeof value !== 'object') return false;
  const backup = value as Partial<EncryptedHostBackup>;
  return backup.encrypted === true && backup.algorithm === 'AES-GCM' && backup.kdf === 'PBKDF2-SHA-256' && typeof backup.data === 'string';
}

function bytesToBase64(bytes: Uint8Array) {
  let binary = '';
  for (let index = 0; index < bytes.length; index += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
  }
  return btoa(binary);
}

function base64ToBytes(value: string) {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

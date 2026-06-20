<script setup lang="ts">
import { useAppContext } from '../../appContext';
import AppIcon from '../common/AppIcon.vue';

const {
  activeTool,
  networkSegment,
  scanIp,
  isScanningIp,
  ipProgress,
  ipScanMessage,
  onlineHosts,
  offlineHosts,
  hosts,
  selectedHost,
  selectHost,
  openPingFromHost,
  copyText,
  hostGroups,
  selectedHostGroup,
  selectManagedGroup,
  hostSearch,
  hostStatusFilter,
  managedHostStats,
  visibleManagedHosts,
  openWebTerminal,
  addManagedHost,
  verifyManagedHost,
  editManagedHost,
  deleteManagedHost,
  portHost,
  portsInput,
  portTimeout,
  portConcurrency,
  applyPortPreset,
  scanPorts,
  isScanningPorts,
  stopPortScan,
  portProgress,
  portScanMessage,
  setPingPreset,
  pingHost,
  useSelectedIpForPing,
  runPing,
  isPinging,
  stopPing,
  pingCount,
  pingTimeout,
  pingInterval,
  pingContinuous,
  clearPingResults,
  exportPingResults,
  pingMetrics,
  pingChart,
  pingDetails,
  portResult,
  subnetPresets,
  setSubnetPreset,
  subnetInput,
  subnetPrefix,
  prefixOptions,
  handlePrefixChange,
  calculateSubnet,
  clearSubnet,
  subnetResult,
  subnetBinaryParts,
  subnetClassText,
  subnetTypeText,
  subnetSplitMode,
  subnetSplitChoices,
  subnetTargetPrefix,
  canSplitSubnet,
  subnetSplitSummary,
  authImport,
  scanScreenQr,
  triggerImageImport,
  imageInput,
  handleImageImport,
  parseAuthImport,
  resetAuthForm,
  authForm,
  saveAuthEntry,
  editingAuthId,
  authEntries,
  saveAuthEntries,
  clearAuthEntries,
  editAuth,
  deleteAuth,
  copyAuthCode,
  showQr,
  passwordLength,
  passwordOptions,
  togglePasswordOption,
  passwordOptionText,
  passwordProject,
  passwordResult,
  generatePassword,
  clearPasswordRecords,
  passwordHistory,
  formatRecordTime,
  deletePassword
} = useAppContext();
</script>

<template>
      <section v-if="activeTool === 'auth'" class="auth-layout">
        <article class="panel auth-form-panel">
          <div class="scan-card">
            <div>
              <h2>扫码加入</h2>
              <p>支持屏幕框选识别，也可以直接导入二维码截图或图片文件。</p>
            </div>
            <div class="scan-actions">
              <button aria-label="识别屏幕二维码" title="识别屏幕二维码" type="button" @click="scanScreenQr">
                <AppIcon name="scan" :size="18" />
              </button>
              <button aria-label="导入二维码图片" title="导入二维码图片" type="button" @click="triggerImageImport">
                <AppIcon name="image" :size="18" />
              </button>
              <input ref="imageInput" hidden type="file" accept="image/*" @change="handleImageImport" />
            </div>
          </div>
          <label><span>快速导入</span><textarea v-model="authImport" placeholder="粘贴 otpauth://totp/... 链接后，点击下方“解析导入”"></textarea></label>
          <div class="split-actions">
            <button type="button" @click="parseAuthImport">解析导入</button>
            <button type="button" @click="resetAuthForm">重置表单</button>
          </div>
          <div class="form-grid two">
            <label><span>服务名称</span><input v-model="authForm.issuer" placeholder="例如 GitHub / 阿里云" /></label>
            <label><span>账号备注</span><input v-model="authForm.account_name" placeholder="例如 admin@example.com" /></label>
          </div>
          <label><span>Base32 密钥</span><input v-model="authForm.secret" placeholder="输入或粘贴 Base32 Secret，支持空格和短杠" /></label>
          <div class="form-grid three">
            <label><span>位数</span><select v-model.number="authForm.digits"><option :value="6">6 位</option><option :value="8">8 位</option></select></label>
            <label><span>刷新周期</span><select v-model.number="authForm.period"><option :value="30">30 秒</option><option :value="60">60 秒</option></select></label>
            <label><span>算法</span><select v-model="authForm.algorithm"><option value="SHA1">SHA-1</option><option value="SHA256">SHA-256</option><option value="SHA512">SHA-512</option></select></label>
          </div>
          <button class="primary full" type="button" @click="saveAuthEntry">{{ editingAuthId ? '保存修改' : '添加条目' }}</button>
        </article>

        <article class="panel auth-list-panel">
          <div class="panel-title">
            <div>
              <h2>验证码列表</h2>
              <p>点击卡片中的数字即可复制当前验证码。</p>
            </div>
            <div class="title-actions">
              <strong>{{ authEntries.length }} 条</strong>
              <button type="button" @click="saveAuthEntries">保存</button>
              <button class="danger" type="button" @click="clearAuthEntries">清空</button>
            </div>
          </div>
          <div class="auth-card-grid">
            <article v-for="entry in authEntries" :key="entry.id" class="auth-card">
              <div class="auth-card-head">
                <div><h3>{{ entry.issuer || '未命名服务' }}</h3><p>{{ entry.account_name || '未填写账号' }}</p></div>
                <div class="card-actions">
                  <button type="button" @click="editAuth(entry)">编辑</button>
                  <button class="danger" type="button" @click="deleteAuth(entry)">删除</button>
                </div>
              </div>
              <div class="code-row">
                <button class="auth-code" :class="{ expiring: (entry.totp?.remaining_seconds ?? entry.period) <= 5 }" type="button" @click="copyAuthCode(entry)">{{ entry.totp?.code ?? '------' }}</button>
                <div class="countdown" :class="{ expiring: (entry.totp?.remaining_seconds ?? entry.period) <= 5 }" :style="{ '--progress': `${((entry.totp?.remaining_seconds ?? 0) / entry.period) * 360}deg` }">
                  <span>{{ entry.totp?.remaining_seconds ?? '-' }}</span>
                </div>
              </div>
              <p class="copy-hint">点击复制当前验证码</p>
              <div class="tag-line">
                <span>{{ entry.digits }} 位验证码</span>
                <span>{{ entry.period }} 秒刷新</span>
                <span>{{ entry.algorithm.replace('SHA', 'SHA-') }}</span>
                <button class="qr-button" aria-label="查看二维码" title="查看二维码" type="button" @click="showQr(entry)">
                  <AppIcon name="qr" :size="17" />
                </button>
              </div>
            </article>
            <div v-if="!authEntries.length" class="empty-state auth-empty">还没有验证码条目。</div>
          </div>
        </article>
      </section>
</template>

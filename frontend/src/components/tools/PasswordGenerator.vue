<script setup lang="ts">
import { useAppContext } from '../../appContext';

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
      <section v-if="activeTool === 'password'" class="password-page">
        <article class="panel password-generator-panel">
          <div class="password-panel-head">
            <div>
              <h2>密码生成器</h2>
              <p>可通过顶部导出选择保存路径，也可以导入历史记录。</p>
            </div>
          </div>
          <div class="password-length-box">
            <div>
              <span>密码长度</span>
              <strong>{{ passwordLength }} 位</strong>
            </div>
            <input v-model.number="passwordLength" type="range" min="6" max="64" />
          </div>
          <div class="password-option-grid">
            <button :class="{ active: passwordOptions.include_uppercase }" type="button" @click="togglePasswordOption('include_uppercase')">大写字母</button>
            <button :class="{ active: passwordOptions.include_lowercase }" type="button" @click="togglePasswordOption('include_lowercase')">小写字母</button>
            <button :class="{ active: passwordOptions.include_numbers }" type="button" @click="togglePasswordOption('include_numbers')">数字</button>
            <button :class="{ active: passwordOptions.include_symbols }" type="button" @click="togglePasswordOption('include_symbols')">符号</button>
          </div>
          <p class="password-policy">当前规则：{{ passwordLength }} 位 · {{ passwordOptionText() }}</p>
          <div class="password-info-box">
            <div class="password-info-head">
              <h3>密码信息</h3>
              <button type="button" :disabled="!passwordResult" @click="copyText(passwordResult, '已复制生成结果。')">复制</button>
            </div>
            <div class="password-field-grid">
              <label><span>项目名称</span><textarea v-model="passwordProject" placeholder="未填写项目名称"></textarea></label>
              <label><span>生成结果</span><textarea v-model="passwordResult" class="password-result-field" readonly placeholder="点击生成密码"></textarea></label>
            </div>
          </div>
          <div class="password-actions">
            <button class="primary" type="button" @click="generatePassword">生成密码</button>
            <button type="button" :disabled="!passwordHistory.length" @click="clearPasswordRecords">清空记录</button>
          </div>
        </article>

        <article class="panel password-record-panel">
          <div class="password-record-head">
            <h2>生成记录</h2>
            <span>{{ passwordHistory.length }} 条</span>
          </div>
          <div class="password-record-list">
            <article v-for="record in passwordHistory" :key="record.id" class="password-record-card">
              <div>
                <strong
                  class="password-copy-target"
                  title="双击复制密码"
                  @dblclick.stop="copyText(record.password, `已复制 ${record.project_name || '未填写项目名称'} 的密码。`)"
                >{{ record.password }}</strong>
                <span>项目：{{ record.project_name || '未填写项目名称' }}</span>
                <span>{{ record.length }} 位 · {{ passwordOptionText(record) }}</span>
                <span>{{ formatRecordTime(record.created_at) }}</span>
              </div>
              <div class="password-record-actions">
                <button type="button" @click="copyText(record.password, `已复制 ${record.project_name || '未填写项目名称'} 的密码。`)">复制</button>
                <button class="danger" type="button" @click="deletePassword(record)">删除</button>
              </div>
            </article>
            <div v-if="!passwordHistory.length" class="empty-state">还没有生成记录。</div>
          </div>
        </article>
      </section>
</template>

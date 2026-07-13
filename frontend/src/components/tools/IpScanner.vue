<script setup lang="ts">
import { useAppContext } from '@app/context';

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
  deletePassword,
  canUsePageAction,
  canUseAnyPageAction,
} = useAppContext();
</script>

<template>
      <section v-if="activeTool === 'ip'" class="tool-stack ip-page">
        <template v-if="canUseAnyPageAction('ip', ['scan', 'select_host'])">
        <article v-if="canUsePageAction('ip', 'scan')" class="panel ip-toolbar">
          <label class="segment-field"><span>网段</span><input v-model="networkSegment" @keyup.enter="scanIp" /></label>
          <button class="primary" type="button" :disabled="isScanningIp" @click="scanIp">{{ isScanningIp ? '扫描中' : '扫描 IP' }}</button>
          <div class="selected-chip">选中 IP <strong>{{ selectedHost }}</strong></div>
        </article>
        <article v-if="canUsePageAction('ip', 'scan')" class="panel progress-panel">
          <div><span>扫描进度</span><strong>{{ ipProgress }}%</strong></div>
          <div class="progress"><span :style="{ width: `${ipProgress}%` }"></span></div>
        </article>
        <div v-if="canUsePageAction('ip', 'scan') || hosts.length" class="metric-row">
          <article><strong>{{ hosts.length }}/254</strong><span>已扫描</span></article>
          <article><strong class="green">{{ onlineHosts.length }}</strong><span>在线主机</span></article>
          <article><strong class="muted">{{ offlineHosts.length }}</strong><span>离线主机</span></article>
          <article><strong>{{ selectedHost }}</strong><span>当前选中</span></article>
        </div>
        <article class="ip-grid-panel">
          <template v-if="canUsePageAction('ip', 'select_host')">
            <button
              v-for="host in hosts"
              :key="host.ip"
              class="ip-cell"
              :class="{ online: host.status === 'online', selected: selectedHost === host.ip }"
              :title="host.ip"
              type="button"
              @click="selectHost(host.ip)"
              @dblclick="canUsePageAction('ports', 'ping') && openPingFromHost(host.ip)"
            >
              {{ host.host }}
            </button>
          </template>
          <template v-else>
            <div
              v-for="host in hosts"
              :key="host.ip"
              class="ip-cell"
              :class="{ online: host.status === 'online', selected: selectedHost === host.ip }"
              :title="host.ip"
            >
              {{ host.host }}
            </div>
          </template>
        </article>
        </template>
        <div v-else class="permission-empty">暂无可用功能</div>
      </section>
</template>

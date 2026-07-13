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
      <section v-if="activeTool === 'subnet'" class="subnet-workbench">
        <template v-if="canUseAnyPageAction('subnet', ['calculate', 'split', 'clear'])">
        <div class="subnet-top-grid">
          <article class="panel subnet-config-panel">
            <div class="subnet-panel-head">
              <h2>子网计算器</h2>
              <p>点击示例后会直接带入并计算。</p>
            </div>
            <div v-if="canUsePageAction('subnet', 'calculate')" class="subnet-presets">
              <button v-for="preset in subnetPresets" :key="preset" type="button" @click="setSubnetPreset(preset)">{{ preset }}</button>
            </div>
            <div class="subnet-control-grid">
              <label v-if="canUsePageAction('subnet', 'calculate')"><span>IP 地址 / CIDR</span><input v-model="subnetInput" placeholder="例如 192.168.1.0/24" @keyup.enter="calculateSubnet(false)" /></label>
              <label><span>子网掩码</span><select v-model.number="subnetPrefix" @change="handlePrefixChange"><option v-for="item in prefixOptions" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
            </div>
            <div class="subnet-actions">
              <button v-if="canUsePageAction('subnet', 'calculate')" class="primary" type="button" @click="calculateSubnet(false)">计算</button>
              <button v-if="canUsePageAction('subnet', 'clear')" type="button" @click="clearSubnet">清空</button>
            </div>
          </article>

          <article class="panel subnet-binary-panel">
            <div class="subnet-panel-head">
              <h2>二进制表示</h2>
              <p>绿色为网络位，红色为主机位。</p>
            </div>
            <div v-if="subnetResult" class="binary-grid">
              <template v-for="row in [
                { label: 'IP 地址', value: subnetResult.binary.ip },
                { label: '子网掩码', value: subnetResult.binary.mask },
                { label: '网络地址', value: subnetResult.binary.network },
                { label: '广播地址', value: subnetResult.binary.broadcast },
              ]" :key="row.label">
                <span>{{ row.label }}</span>
                <code>
                  <template v-for="(part, index) in subnetBinaryParts(row.value, subnetResult.prefix)" :key="`${row.label}-${index}`">
                    <span class="network-bits">{{ part.network }}</span><span class="host-bits">{{ part.host }}</span><span v-if="index < 3">.</span>
                  </template>
                </code>
              </template>
            </div>
            <div v-else class="empty-state">计算后这里会显示二进制位。</div>
          </article>
        </div>

        <article class="panel subnet-result-panel">
          <div class="subnet-panel-head">
            <h2>计算结果</h2>
            <p v-if="subnetResult">当前地址块共 {{ subnetResult.address_count }} 个地址。</p>
          </div>
          <div v-if="subnetResult" class="subnet-summary-grid">
            <article><span>IP 地址</span><strong>{{ subnetResult.ip }}</strong></article>
            <article><span>子网掩码</span><strong>{{ subnetResult.mask }}</strong></article>
            <article><span>网络地址</span><strong class="green">{{ subnetResult.network }}/{{ subnetResult.prefix }}</strong></article>
            <article><span>广播地址</span><strong class="orange">{{ subnetResult.broadcast }}</strong></article>
            <article><span>可用主机范围</span><strong>{{ subnetResult.first_host }} - {{ subnetResult.last_host }}</strong></article>
            <article><span>可用主机数</span><strong>{{ subnetResult.usable_host_count }}</strong></article>
            <article><span>IP 类型</span><strong>{{ subnetClassText }}</strong></article>
            <article><span>地址类型</span><strong>{{ subnetTypeText }}</strong></article>
          </div>
          <div v-else class="empty-state">输入 IPv4 地址并点击计算后，这里会显示网段摘要。</div>
        </article>

        <article class="panel subnet-list-panel">
          <div class="subnet-panel-head">
            <h2>IPv4 子网划分</h2>
            <p v-if="subnetResult">基于 {{ subnetResult.network }}/{{ subnetResult.prefix }} 继续细分。</p>
          </div>
          <div class="subnet-mode-tabs">
            <button :class="{ active: subnetSplitMode === 'count' }" type="button" @click="subnetSplitMode = 'count'">按子网数量</button>
            <button :class="{ active: subnetSplitMode === 'hosts' }" type="button" @click="subnetSplitMode = 'hosts'">按主机数量</button>
          </div>
          <div v-if="canUsePageAction('subnet', 'split')" class="subnet-split-line">
            <label><span>{{ subnetSplitMode === 'count' ? '划分子网数量' : '每个子网主机数' }}</span><select v-model.number="subnetTargetPrefix"><option v-for="item in subnetSplitChoices" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
            <button class="primary" type="button" :disabled="!subnetResult || !canSplitSubnet" @click="calculateSubnet(true)">划分</button>
          </div>
          <div class="subnet-split-summary">
            <article><span>目标前缀</span><strong>/{{ subnetSplitSummary.prefix }}</strong></article>
            <article><span>子网掩码</span><strong>{{ subnetSplitSummary.mask }}</strong></article>
            <article><span>总子网数</span><strong>{{ subnetSplitSummary.count }}</strong></article>
            <article><span>每个子网可用主机</span><strong>{{ subnetSplitSummary.usableHosts }}</strong></article>
          </div>
          <div v-if="subnetResult?.subnets?.length" class="subnet-table">
            <div class="subnet-table-head">
              <span>#</span><span>网络地址</span><span>可用主机范围</span><span>广播地址</span>
            </div>
            <div v-for="subnet in subnetResult.subnets" :key="subnet.index" class="subnet-table-row">
              <span>#{{ subnet.index }}</span>
              <strong>{{ subnet.cidr }}</strong>
              <span>{{ subnet.first_host }} - {{ subnet.last_host }}</span>
              <span>{{ subnet.broadcast }}</span>
            </div>
          </div>
          <p v-if="subnetResult?.subnets?.length" class="subnet-generated">已生成 {{ subnetResult.subnets.length }} 个子网。</p>
          <div v-else class="empty-state">还没有子网划分结果。</div>
        </article>
        </template>
        <div v-else class="permission-empty">暂无可用功能</div>
      </section>
</template>

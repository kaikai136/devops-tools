<script setup lang="ts">
import { useAppContext } from '@app/context';
import AppIcon from '@shared/components/AppIcon.vue';

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
  <section v-if="activeTool === 'auth'" class="auth-layout">
    <template v-if="canUseAnyPageAction('auth', ['scan', 'import', 'create', 'edit', 'delete', 'export', 'clear'])">
      <article v-if="canUseAnyPageAction('auth', ['scan', 'create', 'edit'])" class="panel auth-form-panel">
        <div class="scan-card">
          <div>
            <h2>扫码加入</h2>
            <p>支持屏幕框选识别，也可以直接导入二维码截图或图片文件。</p>
          </div>
          <div v-if="canUsePageAction('auth', 'scan')" class="scan-actions">
            <el-tooltip content="识别屏幕二维码" placement="top">
              <el-button circle aria-label="识别屏幕二维码" @click="scanScreenQr">
                <AppIcon name="scan" :size="18" />
              </el-button>
            </el-tooltip>
            <el-tooltip content="导入二维码图片" placement="top">
              <el-button circle aria-label="导入二维码图片" @click="triggerImageImport">
                <AppIcon name="image" :size="18" />
              </el-button>
            </el-tooltip>
            <input ref="imageInput" hidden type="file" accept="image/*" @change="handleImageImport" />
          </div>
        </div>
        <label>
          <span>快速导入</span>
          <el-input v-model="authImport" type="textarea" :rows="4" placeholder="粘贴 otpauth://totp/... 链接后，点击下方“解析导入”" />
        </label>
        <div class="split-actions">
          <el-button @click="parseAuthImport">解析导入</el-button>
          <el-button @click="resetAuthForm">重置表单</el-button>
        </div>
        <div class="form-grid two">
          <label>
            <span>服务名称</span>
            <el-input v-model="authForm.issuer" placeholder="例如 GitHub / 阿里云" />
          </label>
          <label>
            <span>账号备注</span>
            <el-input v-model="authForm.account_name" placeholder="例如 admin@example.com" />
          </label>
        </div>
        <label>
          <span>Base32 密钥</span>
          <el-input v-model="authForm.secret" placeholder="输入或粘贴 Base32 Secret，支持空格和短杠" />
        </label>
        <div class="form-grid three">
          <label>
            <span>位数</span>
            <el-select v-model="authForm.digits">
              <el-option :value="6" label="6 位" />
              <el-option :value="8" label="8 位" />
            </el-select>
          </label>
          <label>
            <span>刷新周期</span>
            <el-select v-model="authForm.period">
              <el-option :value="30" label="30 秒" />
              <el-option :value="60" label="60 秒" />
            </el-select>
          </label>
          <label>
            <span>算法</span>
            <el-select v-model="authForm.algorithm">
              <el-option value="SHA1" label="SHA-1" />
              <el-option value="SHA256" label="SHA-256" />
              <el-option value="SHA512" label="SHA-512" />
            </el-select>
          </label>
        </div>
        <el-button v-if="canUsePageAction('auth', editingAuthId ? 'edit' : 'create')" class="full" type="primary" @click="saveAuthEntry">
          {{ editingAuthId ? '保存修改' : '添加条目' }}
        </el-button>
      </article>

      <article class="panel auth-list-panel">
        <div class="panel-title">
          <div>
            <h2>验证码列表</h2>
            <p>点击卡片中的数字即可复制当前验证码。</p>
          </div>
          <div class="title-actions">
            <el-tag type="info" effect="plain">{{ authEntries.length }} 条</el-tag>
            <el-button v-if="canUsePageAction('auth', 'export')" @click="saveAuthEntries">保存</el-button>
            <el-button v-if="canUsePageAction('auth', 'clear')" type="danger" plain @click="clearAuthEntries">清空</el-button>
          </div>
        </div>
        <div class="auth-card-grid">
          <article v-for="entry in authEntries" :key="entry.id" class="auth-card">
            <div class="auth-card-head">
              <div>
                <h3>{{ entry.issuer || '未命名服务' }}</h3>
                <p>{{ entry.account_name || '未填写账号' }}</p>
              </div>
              <div class="card-actions">
                <el-button v-if="canUsePageAction('auth', 'edit')" size="small" @click="editAuth(entry)">编辑</el-button>
                <el-button v-if="canUsePageAction('auth', 'delete')" size="small" type="danger" plain @click="deleteAuth(entry)">删除</el-button>
              </div>
            </div>
            <div class="code-row">
              <el-button
                class="auth-code"
                :class="{ expiring: (entry.totp?.remaining_seconds ?? entry.period) <= 5 }"
                @click="copyAuthCode(entry)"
              >
                {{ entry.totp?.code ?? '------' }}
              </el-button>
              <div
                class="countdown"
                :class="{ expiring: (entry.totp?.remaining_seconds ?? entry.period) <= 5 }"
                :style="{ '--progress': `${((entry.totp?.remaining_seconds ?? 0) / entry.period) * 360}deg` }"
              >
                <span>{{ entry.totp?.remaining_seconds ?? '-' }}</span>
              </div>
            </div>
            <p class="copy-hint">点击复制当前验证码</p>
            <div class="tag-line">
              <el-tag size="small" effect="plain">{{ entry.digits }} 位验证码</el-tag>
              <el-tag size="small" effect="plain">{{ entry.period }} 秒刷新</el-tag>
              <el-tag size="small" effect="plain">{{ entry.algorithm.replace('SHA', 'SHA-') }}</el-tag>
              <el-tooltip content="查看二维码" placement="top">
                <el-button class="qr-button" circle aria-label="查看二维码" @click="showQr(entry)">
                  <AppIcon name="qr" :size="17" />
                </el-button>
              </el-tooltip>
            </div>
          </article>
          <el-empty v-if="!authEntries.length" class="auth-empty" description="还没有验证码条目" />
        </div>
      </article>
    </template>
    <div v-else class="permission-empty">暂无可用功能</div>
  </section>
</template>

<script setup lang="ts">
import * as AsciinemaPlayer from 'asciinema-player';
import type { Player as AsciinemaPlayerInstance } from 'asciinema-player';
import Guacamole from 'guacamole-common-js';
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import 'asciinema-player/dist/bundle/asciinema-player.css';

import { useAppContext } from '@app/context';
import {
  listSessionAudits,
  rdpSessionRecordingUrl,
  sessionRecordingUrl,
  type SessionAuditRiskLevel,
  type TerminalSessionAudit,
} from '../../services/sessionAudit';
import { formatDateTime } from '../../utils/datetime';
import AppIcon from '@shared/components/AppIcon.vue';

interface SessionRecordingDialogState {
  visible: boolean;
  sessionId: string;
  protocol: 'ssh' | 'rdp' | string;
  error: string;
}

const ANSI_ESCAPE_PATTERN = /(?:\x1b|\u001b)\[[0-?]*[ -/]*[@-~]|(?:\x1b|\u001b)\][^\x07]*(?:\x07|\x1b\\)|(?:\x1b|\u001b)[PX^_][\s\S]*?(?:\x1b|\u001b)\\|(?:\x1b|\u001b)[@-_]/g;
const ANSI_RESIDUE_PATTERN = /\[\?2004[hl]|\[(?:\d{1,3}(?:;\d{1,3})*)?[mK]|\[(?:\d{1,3}(?:;\d{1,3})*)?[ABCDGJKH]/g;

const {
  activeTool,
  managedHosts,
  canUsePageAction,
} = useAppContext();

const canUseSessionAudit = computed(() => canUsePageAction('hosts', 'session_audit'));
const sessionAuditRecords = ref<TerminalSessionAudit[]>([]);
const sessionAuditSearch = ref('');
const sessionAuditRiskLevel = ref<SessionAuditRiskLevel | ''>('');
const sessionAuditHostId = ref<number | ''>('');
const sessionAuditPage = ref(1);
const sessionAuditPageSize = ref(20);
const sessionAuditTotal = ref(0);
const isSessionAuditLoading = ref(false);
const sessionAuditError = ref('');
const sessionRecordingDialog = ref<SessionRecordingDialogState>({
  visible: false,
  sessionId: '',
  protocol: 'ssh',
  error: '',
});
const sessionRecordingContainer = ref<HTMLElement | null>(null);
let sessionRecordingPlayer: AsciinemaPlayerInstance | null = null;
let rdpSessionRecordingPlayer: InstanceType<typeof Guacamole.SessionRecording> | null = null;
let sessionAuditRequestId = 0;

const sessionAuditTotalPages = computed(() => Math.max(1, Math.ceil(sessionAuditTotal.value / sessionAuditPageSize.value)));
const sessionAuditPageStart = computed(() => (sessionAuditTotal.value ? (sessionAuditPage.value - 1) * sessionAuditPageSize.value + 1 : 0));
const sessionAuditPageEnd = computed(() => Math.min(sessionAuditPage.value * sessionAuditPageSize.value, sessionAuditTotal.value));

watch(
  [() => activeTool.value, canUseSessionAudit],
  ([tool, allowed]) => {
    if (tool === 'sessionAudits' && allowed) {
      void loadSessionAudits();
    }
  },
  { immediate: true },
);

watch([sessionAuditRiskLevel, sessionAuditHostId, sessionAuditPageSize], () => {
  sessionAuditPage.value = 1;
  if (canUseSessionAudit.value) {
    void loadSessionAudits();
  }
});

watch(sessionAuditPage, () => {
  if (canUseSessionAudit.value) {
    void loadSessionAudits();
  }
});

function setSessionAuditPage(page: number) {
  sessionAuditPage.value = Math.min(Math.max(1, page), sessionAuditTotalPages.value);
}

function setSessionAuditPageSize(pageSize: number) {
  sessionAuditPageSize.value = pageSize;
}

async function loadSessionAudits() {
  if (!canUseSessionAudit.value) return;
  const requestId = ++sessionAuditRequestId;
  isSessionAuditLoading.value = true;
  sessionAuditError.value = '';
  try {
    const data = await listSessionAudits({
      search: sessionAuditSearch.value.trim(),
      riskLevel: sessionAuditRiskLevel.value,
      host: sessionAuditHostId.value,
      page: sessionAuditPage.value,
      pageSize: sessionAuditPageSize.value,
    });
    if (requestId !== sessionAuditRequestId) return;
    sessionAuditRecords.value = data.results;
    sessionAuditTotal.value = data.count;
    sessionAuditPage.value = data.page;
  } catch (error) {
    if (requestId !== sessionAuditRequestId) return;
    sessionAuditError.value = error instanceof Error ? error.message : '会话审计加载失败';
  } finally {
    if (requestId === sessionAuditRequestId) {
      isSessionAuditLoading.value = false;
    }
  }
}

function applySessionAuditFilters() {
  sessionAuditPage.value = 1;
  void loadSessionAudits();
}

function resetSessionAuditFilters() {
  sessionAuditSearch.value = '';
  sessionAuditRiskLevel.value = '';
  sessionAuditHostId.value = '';
  sessionAuditPage.value = 1;
  void loadSessionAudits();
}

function sessionAuditRiskText(riskLevel: SessionAuditRiskLevel) {
  if (riskLevel === 'high') return '高风险';
  if (riskLevel === 'medium') return '中风险';
  return '接受';
}

function sessionAuditRiskType(riskLevel: SessionAuditRiskLevel) {
  if (riskLevel === 'high') return 'danger';
  if (riskLevel === 'medium') return 'warning';
  return 'success';
}

function shortSessionId(sessionId: string) {
  return sessionId ? sessionId.slice(0, 8) : '-';
}

function formatAuditDate(value: string | null | undefined) {
  return formatDateTime(value, '-');
}

function formatAuditOutput(output: string | null | undefined) {
  return String(output ?? '')
    .replace(ANSI_ESCAPE_PATTERN, '')
    .replace(ANSI_RESIDUE_PATTERN, '')
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

async function openSessionRecording(audit: TerminalSessionAudit) {
  if (!audit.sessionId) return;
  disposeSessionRecordingPlayer();
  sessionRecordingDialog.value = { visible: true, sessionId: audit.sessionId, protocol: audit.protocol || 'ssh', error: '' };
  await nextTick();
  if (!sessionRecordingContainer.value) return;
  if (audit.protocol === 'rdp') {
    await openRdpSessionRecording(audit);
    return;
  }
  try {
    sessionRecordingPlayer = AsciinemaPlayer.create(
      {
        url: sessionRecordingUrl(audit.sessionId),
        fetchOpts: { credentials: 'include' },
      },
      sessionRecordingContainer.value,
      {
        autoPlay: true,
        fit: 'both',
        idleTimeLimit: 2,
        theme: 'asciinema',
        controls: true,
      },
    );
  } catch (error) {
    sessionRecordingDialog.value = {
      ...sessionRecordingDialog.value,
      error: error instanceof Error ? error.message : '操作录像加载失败',
    };
  }
}

async function openRdpSessionRecording(audit: TerminalSessionAudit) {
  if (!sessionRecordingContainer.value) return;
  if (!audit.hasRdpRecording) {
    sessionRecordingDialog.value = {
      ...sessionRecordingDialog.value,
      error: 'RDP 录屏不存在或已清理',
    };
    return;
  }
  try {
    const tunnel = new Guacamole.StaticHTTPTunnel(rdpSessionRecordingUrl(audit.sessionId), false, {});
    const recording = new Guacamole.SessionRecording(tunnel, 250);
    rdpSessionRecordingPlayer = recording;
    const displayElement = recording.getDisplay().getElement();
    displayElement.classList.add('host-session-rdp-recording-display');
    sessionRecordingContainer.value.textContent = '';
    sessionRecordingContainer.value.appendChild(displayElement);
    recording.onerror = (message) => {
      sessionRecordingDialog.value = {
        ...sessionRecordingDialog.value,
        error: message || 'RDP 录屏加载失败',
      };
    };
    recording.onload = () => {
      recording.play();
    };
    recording.connect('');
  } catch (error) {
    sessionRecordingDialog.value = {
      ...sessionRecordingDialog.value,
      error: error instanceof Error ? error.message : 'RDP 录屏加载失败',
    };
  }
}

function closeSessionRecording() {
  disposeSessionRecordingPlayer();
  sessionRecordingDialog.value = { visible: false, sessionId: '', protocol: 'ssh', error: '' };
}

function disposeSessionRecordingPlayer() {
  if (rdpSessionRecordingPlayer) {
    try {
      rdpSessionRecordingPlayer.abort();
    } finally {
      rdpSessionRecordingPlayer = null;
    }
  }
  if (!sessionRecordingPlayer) return;
  try {
    sessionRecordingPlayer.dispose();
  } finally {
    sessionRecordingPlayer = null;
  }
}

onBeforeUnmount(() => {
  sessionAuditRequestId += 1;
  disposeSessionRecordingPlayer();
});
</script>

<template>
  <section class="host-session-audit-page">
    <article v-if="canUseSessionAudit" class="panel host-session-audit-list-panel">
      <NativeForm class="host-session-audit-toolbar" inline label-position="left" @submit.prevent="applySessionAuditFilters">
        <NativeFormItem label="审计搜索">
          <NativeInput v-model="sessionAuditSearch" placeholder="输入用户/命令/节点/IP/会话检索" clearable />
        </NativeFormItem>
        <NativeFormItem label="风险等级">
          <NativeSelect v-model="sessionAuditRiskLevel" placeholder="全部风险" clearable>
            <NativeOption value="accept" label="接受" />
            <NativeOption value="medium" label="中风险" />
            <NativeOption value="high" label="高风险" />
          </NativeSelect>
        </NativeFormItem>
        <NativeFormItem label="资产节点">
          <NativeSelect v-model="sessionAuditHostId" placeholder="全部资产" clearable filterable>
            <NativeOption v-for="host in managedHosts" :key="host.id" :value="host.id" :label="`${host.name} / ${host.privateIp}`" />
          </NativeSelect>
        </NativeFormItem>
        <NativeFormItem>
          <NativeButton @click="resetSessionAuditFilters">重置</NativeButton>
          <NativeButton type="primary" :loading="isSessionAuditLoading" @click="applySessionAuditFilters">查询</NativeButton>
          <NativeTooltip content="刷新" placement="top">
            <NativeButton circle :disabled="isSessionAuditLoading" @click="loadSessionAudits">
              <AppIcon name="refresh" :size="16" />
            </NativeButton>
          </NativeTooltip>
        </NativeFormItem>
      </NativeForm>

      <p v-if="sessionAuditError" class="host-session-audit-message">{{ sessionAuditError }}</p>

      <div class="host-session-audit-table-wrap">
        <NativeTable :data="sessionAuditRecords" row-key="id" class="host-session-audit-table" v-loading="isSessionAuditLoading" empty-text="暂无会话审计记录">
          <NativeTableColumn type="expand" width="48">
            <template #default="{ row }">
              <div class="host-session-audit-detail">
                <div>
                  <strong>具体命令</strong>
                  <pre>{{ row.command }}</pre>
                </div>
                <div>
                  <strong>终端输出</strong>
                  <pre>{{ formatAuditOutput(row.output) || '暂无输出' }}</pre>
                </div>
                <div v-if="row.endedAt || row.errorMessage">
                  <strong>会话状态</strong>
                  <pre>{{ row.endedAt ? `结束：${formatAuditDate(row.endedAt)}` : '' }}{{ row.errorMessage ? `\n错误：${row.errorMessage}` : '' }}</pre>
                </div>
              </div>
            </template>
          </NativeTableColumn>
          <NativeTableColumn prop="username" label="用户" min-width="110" show-overflow-tooltip />
          <NativeTableColumn prop="command" label="命令" min-width="220" show-overflow-tooltip />
          <NativeTableColumn label="风险等级" min-width="110">
            <template #default="{ row }">
              <NativeTag :type="sessionAuditRiskType(row.riskLevel)" size="small" effect="dark">{{ sessionAuditRiskText(row.riskLevel) }}</NativeTag>
            </template>
          </NativeTableColumn>
          <NativeTableColumn label="协议" min-width="80">
            <template #default="{ row }">{{ row.protocol === 'rdp' ? 'RDP' : 'SSH' }}</template>
          </NativeTableColumn>
          <NativeTableColumn label="录屏" min-width="110">
            <template #default="{ row }">
              {{ row.protocol === 'rdp' ? (row.hasRdpRecording ? '已录制' : row.recordingEnabled ? '录制中' : '未开启') : '-' }}
            </template>
          </NativeTableColumn>
          <NativeTableColumn prop="assetName" label="资产节点" min-width="150" show-overflow-tooltip />
          <NativeTableColumn prop="ipAddress" label="IP 地址" min-width="130" />
          <NativeTableColumn label="会话" min-width="120">
            <template #default="{ row }">
              <NativeButton text type="primary" :title="row.sessionId" @click="openSessionRecording(row)">
                {{ shortSessionId(row.sessionId) }}
              </NativeButton>
            </template>
          </NativeTableColumn>
          <NativeTableColumn label="日期时间" min-width="170">
            <template #default="{ row }">{{ formatAuditDate(row.executedAt) }}</template>
          </NativeTableColumn>
        </NativeTable>
      </div>

      <div class="host-pagination host-session-audit-pagination" aria-label="会话审计分页">
        <div class="host-pagination-summary">
          <span>共 {{ sessionAuditTotal }} 条</span>
          <span>{{ sessionAuditPageStart }}-{{ sessionAuditPageEnd }}</span>
        </div>
        <NativePagination
          background
          layout="prev, pager, next, sizes"
          :current-page="sessionAuditPage"
          :page-size="sessionAuditPageSize"
          :page-sizes="[10, 20, 50]"
          :total="sessionAuditTotal"
          @current-change="setSessionAuditPage"
          @size-change="setSessionAuditPageSize"
        />
        <div class="host-stats-line host-session-audit-stats">
          <span>共 {{ sessionAuditTotal }} 条审计</span>
          <span>本页 {{ sessionAuditRecords.length }}</span>
          <span v-if="isSessionAuditLoading">加载中</span>
        </div>
      </div>
    </article>
    <div v-else class="permission-empty">暂无可用功能</div>

    <NativeDialog
      :model-value="sessionRecordingDialog.visible"
      title="操作录像"
      width="920px"
      class="host-session-recording-dialog"
      :close-on-click-modal="false"
      @update:model-value="(visible) => { if (!visible) closeSessionRecording(); }"
    >
      <p class="host-session-recording-title">
        <AppIcon name="terminal" :size="16" />
        <span>{{ sessionRecordingDialog.sessionId }}</span>
      </p>
      <p v-if="sessionRecordingDialog.error" class="host-session-audit-message">{{ sessionRecordingDialog.error }}</p>
      <div ref="sessionRecordingContainer" class="host-session-recording-player"></div>
    </NativeDialog>
  </section>
</template>

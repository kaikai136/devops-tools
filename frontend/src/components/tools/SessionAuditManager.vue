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
const expandedSessionAuditIds = ref<Set<number>>(new Set());
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
const sessionAuditPageNumbers = computed(() => {
  const total = sessionAuditTotalPages.value;
  const current = sessionAuditPage.value;
  const from = Math.max(1, current - 2);
  const to = Math.min(total, current + 2);
  return Array.from({ length: to - from + 1 }, (_, index) => from + index);
});

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
    expandedSessionAuditIds.value = new Set(
      [...expandedSessionAuditIds.value].filter((id) => data.results.some((item) => item.id === id)),
    );
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

function toggleSessionAuditExpanded(auditId: number) {
  const next = new Set(expandedSessionAuditIds.value);
  if (next.has(auditId)) {
    next.delete(auditId);
  } else {
    next.add(auditId);
  }
  expandedSessionAuditIds.value = next;
}

function isSessionAuditExpanded(auditId: number) {
  return expandedSessionAuditIds.value.has(auditId);
}

function sessionAuditRiskText(riskLevel: SessionAuditRiskLevel) {
  if (riskLevel === 'high') return '高风险';
  if (riskLevel === 'medium') return '中风险';
  return '接受';
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
      <form class="host-session-audit-toolbar" @submit.prevent="applySessionAuditFilters">
        <input v-model="sessionAuditSearch" type="search" placeholder="输入用户/命令/节点/IP/会话检索" aria-label="会话审计搜索" />
        <div class="host-session-audit-toolbar-actions">
          <select v-model="sessionAuditRiskLevel" aria-label="风险等级">
            <option value="">全部风险</option>
            <option value="accept">接受</option>
            <option value="medium">中风险</option>
            <option value="high">高风险</option>
          </select>
          <select v-model="sessionAuditHostId" aria-label="资产节点">
            <option value="">全部资产</option>
            <option v-for="host in managedHosts" :key="host.id" :value="host.id">{{ host.name }} / {{ host.privateIp }}</option>
          </select>
          <button type="button" @click="resetSessionAuditFilters">重置</button>
          <button class="primary" type="submit" :disabled="isSessionAuditLoading">
            {{ isSessionAuditLoading ? '加载中' : '查询' }}
          </button>
          <button class="icon-only" type="button" title="刷新" aria-label="刷新" :disabled="isSessionAuditLoading" @click="loadSessionAudits">
            <AppIcon name="refresh" :size="16" />
          </button>
        </div>
      </form>

      <p v-if="sessionAuditError" class="host-session-audit-message">{{ sessionAuditError }}</p>

      <div class="host-session-audit-table-wrap">
        <div class="host-session-audit-table">
          <div class="host-session-audit-row head">
            <span>用户</span>
            <span>命令</span>
            <span>风险等级</span>
            <span>协议</span>
            <span>录屏</span>
            <span>资产节点</span>
            <span>IP 地址</span>
            <span>会话</span>
            <span>日期时间</span>
            <span>详情</span>
          </div>
          <template v-for="audit in sessionAuditRecords" :key="audit.id">
            <div class="host-session-audit-row">
              <span :title="audit.username">{{ audit.username || '-' }}</span>
              <code :title="audit.command">{{ audit.command }}</code>
              <span class="host-session-risk" :class="audit.riskLevel">{{ sessionAuditRiskText(audit.riskLevel) }}</span>
              <span>{{ audit.protocol === 'rdp' ? 'RDP' : 'SSH' }}</span>
              <span>{{ audit.protocol === 'rdp' ? (audit.hasRdpRecording ? '已录制' : audit.recordingEnabled ? '录制中' : '未开启') : '-' }}</span>
              <span :title="audit.assetName">{{ audit.assetName || '-' }}</span>
              <span>{{ audit.ipAddress || '-' }}</span>
              <button class="host-session-link" type="button" :title="audit.sessionId" @click="openSessionRecording(audit)">
                {{ shortSessionId(audit.sessionId) }}
              </button>
              <span>{{ formatAuditDate(audit.executedAt) }}</span>
              <button class="host-session-expand" type="button" @click="toggleSessionAuditExpanded(audit.id)">
                <AppIcon :name="isSessionAuditExpanded(audit.id) ? 'chevronDown' : 'chevronRight'" :size="15" />
              </button>
            </div>
            <div v-if="isSessionAuditExpanded(audit.id)" class="host-session-audit-detail">
              <div>
                <strong>具体命令</strong>
                <pre>{{ audit.command }}</pre>
              </div>
              <div>
                <strong>终端输出</strong>
                <pre>{{ formatAuditOutput(audit.output) || '暂无输出' }}</pre>
              </div>
              <div v-if="audit.endedAt || audit.errorMessage">
                <strong>会话状态</strong>
                <pre>{{ audit.endedAt ? `结束：${formatAuditDate(audit.endedAt)}` : '' }}{{ audit.errorMessage ? `\n错误：${audit.errorMessage}` : '' }}</pre>
              </div>
            </div>
          </template>
          <div v-if="!isSessionAuditLoading && !sessionAuditRecords.length" class="host-session-audit-empty">暂无会话审计记录</div>
          <div v-if="isSessionAuditLoading" class="host-session-audit-empty">加载中...</div>
        </div>
      </div>

      <div class="host-pagination host-session-audit-pagination" aria-label="会话审计分页">
        <div class="host-pagination-summary">
          <span>共 {{ sessionAuditTotal }} 条</span>
          <span>{{ sessionAuditPageStart }}-{{ sessionAuditPageEnd }}</span>
        </div>
        <div class="host-pagination-controls">
          <button class="prev" type="button" :disabled="sessionAuditPage <= 1" aria-label="上一页" @click="setSessionAuditPage(sessionAuditPage - 1)">
            <AppIcon name="chevronRight" :size="14" />
          </button>
          <button
            v-for="page in sessionAuditPageNumbers"
            :key="page"
            type="button"
            :class="{ active: page === sessionAuditPage }"
            @click="setSessionAuditPage(page)"
          >
            {{ page }}
          </button>
          <button type="button" :disabled="sessionAuditPage >= sessionAuditTotalPages" aria-label="下一页" @click="setSessionAuditPage(sessionAuditPage + 1)">
            <AppIcon name="chevronRight" :size="14" />
          </button>
          <select v-model.number="sessionAuditPageSize" aria-label="每页条数">
            <option :value="10">10 条/页</option>
            <option :value="20">20 条/页</option>
            <option :value="50">50 条/页</option>
          </select>
        </div>
        <div class="host-stats-line host-session-audit-stats">
          <span>共 {{ sessionAuditTotal }} 条审计</span>
          <span>本页 {{ sessionAuditRecords.length }}</span>
          <span v-if="isSessionAuditLoading">加载中</span>
        </div>
      </div>
    </article>
    <div v-else class="permission-empty">暂无可用功能</div>

    <div v-if="sessionRecordingDialog.visible" class="modal-backdrop host-session-recording-backdrop" @click.self="closeSessionRecording">
      <article class="host-session-recording-modal" @click.stop>
        <header>
          <div>
            <strong><AppIcon name="terminal" :size="16" />操作录像</strong>
            <span>{{ sessionRecordingDialog.sessionId }}</span>
          </div>
          <button type="button" title="关闭" aria-label="关闭" @click="closeSessionRecording">
            <AppIcon name="x" :size="16" />
          </button>
        </header>
        <p v-if="sessionRecordingDialog.error" class="host-session-audit-message">{{ sessionRecordingDialog.error }}</p>
        <div ref="sessionRecordingContainer" class="host-session-recording-player"></div>
      </article>
    </div>
  </section>
</template>

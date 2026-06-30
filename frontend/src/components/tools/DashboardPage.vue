<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import { apiGet } from '../../api';
import { useAppContext } from '../../appContext';
import type { DashboardDistributionItem, DashboardSeriesPoint, DashboardSummary } from '../../types';
import { errorMessage } from '../../utils/errors';
import AppIcon from '../common/AppIcon.vue';

const { currentUser } = useAppContext();

const summary = ref<DashboardSummary | null>(null);
const isLoading = ref(false);
const message = ref('');

const displayName = computed(() => currentUser.value?.first_name || currentUser.value?.username || '船长');
const generatedText = computed(() => (summary.value?.generatedAt ? formatTime(summary.value.generatedAt) : '--'));
const trendMax = computed(() => {
  const points = summary.value?.loginTrend ?? [];
  return Math.max(1, ...points.map((point) => point.success + point.failed));
});
const loginPolyline = computed(() => buildLine(summary.value?.loginTrend ?? []));
const loginArea = computed(() => (loginPolyline.value ? `0,160 ${loginPolyline.value} 360,160` : ''));
const osTopList = computed(() => withPercent(summary.value?.assetDistribution.os ?? []));
const verificationList = computed(() => withPercent(summary.value?.assetDistribution.verification ?? []));
const platformList = computed(() => withPercent(summary.value?.assetDistribution.platform ?? []));

onMounted(loadSummary);

async function loadSummary() {
  isLoading.value = true;
  message.value = '';
  try {
    summary.value = await apiGet<DashboardSummary>('/api/dashboard/summary/');
  } catch (error) {
    message.value = errorMessage(error);
  } finally {
    isLoading.value = false;
  }
}

function buildLine(points: DashboardSeriesPoint[]) {
  if (!points.length) return '';
  const max = Math.max(1, ...points.map((point) => point.success + point.failed));
  return points
    .map((point, index) => {
      const x = points.length === 1 ? 180 : (index / (points.length - 1)) * 360;
      const y = 150 - ((point.success + point.failed) / max) * 122;
      return `${round(x)},${round(y)}`;
    })
    .join(' ');
}

function withPercent(items: DashboardDistributionItem[]) {
  const total = items.reduce((sum, item) => sum + item.value, 0);
  return items.map((item) => ({
    ...item,
    percent: total ? Math.round((item.value / total) * 100) : 0,
  }));
}

function formatNumber(value: number) {
  return new Intl.NumberFormat('zh-CN').format(value);
}

function formatTime(value: string | null) {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.replace('T', ' ').slice(0, 19);
  const pad = (number: number) => String(number).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function statusText(status: string) {
  return status === 'success' ? '成功' : '失败';
}

function cardIcon(key: string) {
  const icons: Record<string, 'users' | 'server' | 'monitor' | 'alert'> = {
    users: 'users',
    assets: 'server',
    sessions: 'monitor',
    failed: 'alert',
  };
  return icons[key] ?? 'dashboard';
}

function round(value: number) {
  return Math.round(value * 10) / 10;
}
</script>

<template>
  <section class="dashboard-page">
    <header class="dashboard-hero">
      <div>
        <span>CAPTAIN OPS</span>
        <h1>中午好，{{ displayName }}，记得好好吃饭，小憩一下 ~</h1>
        <p>这里汇总系统账号、资产与网络出口状态，帮助你快速判断今天的运维态势。</p>
      </div>
      <button class="dashboard-refresh" type="button" :disabled="isLoading" @click="loadSummary">
        <AppIcon name="refresh" :size="16" />
        {{ isLoading ? '刷新中' : '刷新' }}
      </button>
    </header>

    <p v-if="message" class="dashboard-message">{{ message }}</p>

    <div v-if="summary" class="dashboard-content">
      <div class="dashboard-card-grid">
        <article v-for="card in summary.cards" :key="card.key" class="dashboard-stat-card" :class="`tone-${card.tone}`">
          <div>
            <span>{{ card.label }}</span>
            <strong>{{ formatNumber(card.value) }}</strong>
            <em>{{ card.changeLabel }}</em>
          </div>
          <i><AppIcon :name="cardIcon(card.key)" :size="22" /></i>
        </article>
      </div>

      <div class="dashboard-main-grid">
        <article class="dashboard-panel dashboard-user-panel">
          <header>
            <div>
              <h2>用户数据</h2>
              <span>活跃率 {{ summary.users.total ? Math.round((summary.users.active / summary.users.total) * 100) : 0 }}%</span>
            </div>
            <AppIcon name="user" :size="20" />
          </header>
          <div class="dashboard-ring-wrap">
            <div class="dashboard-ring" :style="{ '--ring-value': `${summary.users.total ? Math.round((summary.users.active / summary.users.total) * 100) : 0}%` }">
              <strong>{{ summary.users.active }}</strong>
              <span>可用用户</span>
            </div>
          </div>
          <div class="dashboard-split-metrics">
            <span><strong>{{ summary.users.staff }}</strong> 管理员</span>
            <span><strong>{{ summary.users.disabled }}</strong> 已停用</span>
            <span><strong>{{ summary.users.newThisMonth }}</strong> 本月新增</span>
          </div>
        </article>

        <article class="dashboard-panel dashboard-asset-panel">
          <header>
            <div>
              <h2>资产数据</h2>
              <span>{{ summary.assets.verificationRate }}% 已验证</span>
            </div>
            <AppIcon name="server" :size="20" />
          </header>
          <div class="dashboard-ring-wrap">
            <div class="dashboard-ring asset" :style="{ '--ring-value': `${summary.assets.verificationRate}%` }">
              <strong>{{ summary.assets.total }}</strong>
              <span>资产总数</span>
            </div>
          </div>
          <div class="dashboard-split-metrics">
            <span><strong>{{ summary.assets.cpuCores }}</strong> CPU 核</span>
            <span><strong>{{ summary.assets.memoryGb }}</strong> GB 内存</span>
            <span><strong>{{ summary.assets.credentials }}</strong> 凭据</span>
          </div>
        </article>

        <article class="dashboard-panel dashboard-trend-panel">
          <header>
            <div>
              <h2>访问量</h2>
              <span>近 7 天登录趋势</span>
            </div>
            <AppIcon name="gauge" :size="20" />
          </header>
          <svg class="dashboard-line-chart" viewBox="0 0 360 170" role="img" aria-label="近 7 天登录趋势">
            <defs>
              <linearGradient id="dashboardArea" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stop-color="#18a88f" stop-opacity="0.28" />
                <stop offset="100%" stop-color="#18a88f" stop-opacity="0.02" />
              </linearGradient>
            </defs>
            <g class="dashboard-grid-lines">
              <line v-for="line in 5" :key="line" x1="0" x2="360" :y1="line * 32" :y2="line * 32" />
            </g>
            <polygon v-if="loginArea" :points="loginArea" fill="url(#dashboardArea)" />
            <polyline v-if="loginPolyline" :points="loginPolyline" fill="none" stroke="#18a88f" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <div class="dashboard-chart-labels">
            <span v-for="point in summary.loginTrend" :key="point.date">{{ point.date }}</span>
          </div>
        </article>
      </div>

      <div class="dashboard-lower-grid">
        <article class="dashboard-panel dashboard-bars-panel">
          <header>
            <div>
              <h2>资产类型占比</h2>
              <span>按系统平台统计</span>
            </div>
            <AppIcon name="hardDrive" :size="20" />
          </header>
          <div class="dashboard-stacked-bar">
            <span
              v-for="item in platformList"
              :key="item.label"
              :class="item.label.toLowerCase()"
              :style="{ width: `${item.percent}%` }"
              :title="`${item.label} ${item.percent}%`"
            ></span>
          </div>
          <div class="dashboard-distribution-list">
            <div v-for="item in osTopList" :key="item.label">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
              <i><b :style="{ width: `${item.percent}%` }"></b></i>
            </div>
          </div>
        </article>

        <article class="dashboard-panel dashboard-verification-panel">
          <header>
            <div>
              <h2>验证状态</h2>
              <span>资产可用性概览</span>
            </div>
            <AppIcon name="shield" :size="20" />
          </header>
          <div class="dashboard-distribution-list">
            <div v-for="item in verificationList" :key="item.label">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
              <i><b :style="{ width: `${item.percent}%` }"></b></i>
            </div>
          </div>
        </article>

        <article class="dashboard-panel dashboard-ranking-panel">
          <header>
            <div>
              <h2>资产分组排行</h2>
              <span>Top {{ summary.groupRanking.length }}</span>
            </div>
            <AppIcon name="folder" :size="20" />
          </header>
          <div class="dashboard-ranking-list">
            <div v-for="(group, index) in summary.groupRanking" :key="group.id">
              <em>{{ index + 1 }}</em>
              <span>{{ group.label }}</span>
              <strong>{{ group.value }}</strong>
            </div>
            <p v-if="!summary.groupRanking.length">暂无资产分组数据</p>
          </div>
        </article>

        <article class="dashboard-panel dashboard-egress-panel" :class="{ error: summary.egressNetwork.status !== 'ok' }">
          <header>
            <div>
              <h2>出口网络</h2>
              <span>{{ summary.egressNetwork.status === 'ok' ? '后端机器出口' : '探测异常' }}</span>
            </div>
            <AppIcon name="globe" :size="20" />
          </header>
          <strong class="dashboard-egress-ip">{{ summary.egressNetwork.ip || '--' }}</strong>
          <div class="dashboard-egress-meta">
            <span>{{ summary.egressNetwork.location || '位置未知' }}</span>
            <span>{{ summary.egressNetwork.isp || '运营商未知' }}</span>
          </div>
          <p v-if="summary.egressNetwork.error">{{ summary.egressNetwork.error }}</p>
          <a v-else-if="summary.egressNetwork.url" :href="summary.egressNetwork.url" target="_blank" rel="noreferrer">查看 cip.cc 详情</a>
          <small>检测时间 {{ formatTime(summary.egressNetwork.checkedAt) }}</small>
        </article>

        <article class="dashboard-panel dashboard-recent-panel">
          <header>
            <div>
              <h2>最近登录</h2>
              <span>最新 {{ summary.recentLogins.length }} 条记录</span>
            </div>
            <AppIcon name="bell" :size="20" />
          </header>
          <div class="dashboard-login-list">
            <div v-for="log in summary.recentLogins" :key="log.id">
              <span class="dashboard-login-status" :class="log.status">{{ statusText(log.status) }}</span>
              <strong>{{ log.userDisplay || log.username || '-' }}</strong>
              <em>{{ log.ipAddress || '-' }}</em>
              <time>{{ formatTime(log.createdAt) }}</time>
            </div>
            <p v-if="!summary.recentLogins.length">暂无登录记录</p>
          </div>
        </article>
      </div>

      <footer class="dashboard-footer">数据更新时间 {{ generatedText }}</footer>
    </div>

    <div v-else-if="isLoading" class="dashboard-loading">正在加载仪表盘...</div>
  </section>
</template>

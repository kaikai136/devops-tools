<script setup lang="ts">
import { useAppContext } from '@app/context';

const {
  activeTool,
  networkSegment,
  scanIp,
  isScanningIp,
  ipProgress,
  onlineHosts,
  offlineHosts,
  hosts,
  selectedHost,
  selectHost,
  openPingFromHost,
  canUsePageAction,
  canUseAnyPageAction,
} = useAppContext();
</script>

<template>
  <section v-if="activeTool === 'ip'" class="tool-stack ip-page">
    <template v-if="canUseAnyPageAction('ip', ['scan', 'select_host'])">
      <article v-if="canUsePageAction('ip', 'scan')" class="panel ip-toolbar">
        <NativeForm inline label-position="left" @submit.prevent="scanIp">
          <NativeFormItem label="网段">
            <NativeInput v-model="networkSegment" @keyup.enter="scanIp" />
          </NativeFormItem>
          <NativeFormItem>
            <NativeButton type="primary" :loading="isScanningIp" @click="scanIp">
              {{ isScanningIp ? '扫描中' : '扫描 IP' }}
            </NativeButton>
          </NativeFormItem>
        </NativeForm>
        <NativeTag class="selected-chip" type="info" effect="plain">选中 IP {{ selectedHost }}</NativeTag>
      </article>
      <article v-if="canUsePageAction('ip', 'scan')" class="panel progress-panel">
        <div><span>扫描进度</span><strong>{{ ipProgress }}%</strong></div>
        <NativeProgress :percentage="ipProgress" :stroke-width="10" />
      </article>
      <div v-if="canUsePageAction('ip', 'scan') || hosts.length" class="metric-row">
        <article><strong>{{ hosts.length }}/254</strong><span>已扫描</span></article>
        <article><strong class="green">{{ onlineHosts.length }}</strong><span>在线主机</span></article>
        <article><strong class="muted">{{ offlineHosts.length }}</strong><span>离线主机</span></article>
        <article><strong>{{ selectedHost }}</strong><span>当前选中</span></article>
      </div>
      <article class="ip-grid-panel">
        <template v-if="canUsePageAction('ip', 'select_host')">
          <NativeButton
            v-for="host in hosts"
            :key="host.ip"
            class="ip-cell"
            :class="{ online: host.status === 'online', selected: selectedHost === host.ip }"
            :title="host.ip"
            @click="selectHost(host.ip)"
            @dblclick="canUsePageAction('ports', 'ping') && openPingFromHost(host.ip)"
          >
            {{ host.host }}
          </NativeButton>
        </template>
        <template v-else>
          <NativeTag
            v-for="host in hosts"
            :key="host.ip"
            class="ip-cell"
            :class="{ online: host.status === 'online', selected: selectedHost === host.ip }"
            :title="host.ip"
            effect="plain"
          >
            {{ host.host }}
          </NativeTag>
        </template>
      </article>
    </template>
    <div v-else class="permission-empty">暂无可用功能</div>
  </section>
</template>

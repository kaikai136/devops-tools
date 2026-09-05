<script setup lang="ts">
import { useAppContext } from '@app/context';

const {
  applyPortPreset,
  portHost,
  portTimeout,
  portConcurrency,
  portsInput,
  scanPorts,
  isScanningPorts,
  stopPortScan,
  portProgress,
  portScanMessage,
  portResult,
  copyText,
  canUsePageAction,
} = useAppContext();
</script>

<template>
  <div class="machine-port-column">
    <article class="panel ports-config">
      <h2>端口探测</h2>
      <div class="preset-row port-presets">
        <NativeButton @click="applyPortPreset('common')">常用端口</NativeButton>
        <NativeButton @click="applyPortPreset('top100')">1-100</NativeButton>
        <NativeButton @click="applyPortPreset('top1024')">1-1024</NativeButton>
        <NativeButton @click="applyPortPreset('all')">全端口</NativeButton>
        <NativeButton @click="applyPortPreset('database')">数据库</NativeButton>
        <NativeButton @click="applyPortPreset('web')">Web 服务</NativeButton>
      </div>
      <div class="port-inline-grid">
        <label>
          <span>目标</span>
          <NativeInput v-model="portHost" placeholder="请输入 IP 或域名" @keyup.enter="scanPorts" />
        </label>
        <label>
          <span>超时</span>
          <NativeNumberInput v-model="portTimeout" :min="100" :max="60000" :step="100" @keyup.enter="scanPorts" />
        </label>
        <label>
          <span>并发</span>
          <NativeNumberInput v-model="portConcurrency" :min="1" :max="1000" @keyup.enter="scanPorts" />
        </label>
      </div>
      <label>
        <span>端口</span>
        <NativeInput v-model="portsInput" placeholder="例如 22,80,443 或 1-1024" @keyup.enter="scanPorts" />
      </label>
      <div class="split-actions">
        <NativeButton v-if="canUsePageAction('ports', 'port_scan')" type="primary" :loading="isScanningPorts" @click="scanPorts">
          {{ isScanningPorts ? '扫描中' : '开始扫描' }}
        </NativeButton>
        <NativeButton :disabled="!isScanningPorts" @click="stopPortScan">停止</NativeButton>
      </div>
    </article>

    <article class="panel">
      <h2>扫描结果</h2>
      <NativeProgress :percentage="portProgress" :stroke-width="10" />
      <p v-if="portScanMessage" class="inline-status">{{ portScanMessage }}</p>
      <div v-if="portResult" class="port-summary">
        <article><span>目标</span><strong>{{ portResult.host }}</strong></article>
        <article><span>进度</span><strong>{{ portResult.scanned_ports }}/{{ portResult.total_ports ?? portResult.scanned_ports }}</strong></article>
        <article><span>开放</span><strong class="green">{{ portResult.open_ports.length }}</strong></article>
        <article><span>耗时</span><strong>{{ portResult.duration }} ms</strong></article>
      </div>
      <p v-if="portResult?.error" class="result-warning">{{ portResult.error }}</p>
      <div v-if="portResult && !portResult.error" class="port-open-list">
        <NativeButton
          v-for="item in portResult.open_details"
          :key="item.port"
          class="port-open-item"
          @click="copyText(String(item.port), `已复制端口 ${item.port}。`)"
        >
          <strong>{{ item.port }}</strong>
          <span>{{ item.service }}</span>
          <small>{{ item.duration }} ms</small>
        </NativeButton>
        <NativeEmpty v-if="!portResult.open_ports.length && !isScanningPorts" class="empty-state" description="没有发现开放端口" />
      </div>
    </article>
  </div>
</template>

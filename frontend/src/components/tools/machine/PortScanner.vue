<script setup lang="ts">
import { useAppContext } from '../../../appContext';

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
        <button type="button" @click="applyPortPreset('common')">常用端口</button>
        <button type="button" @click="applyPortPreset('top100')">1-100</button>
        <button type="button" @click="applyPortPreset('top1024')">1-1024</button>
        <button type="button" @click="applyPortPreset('all')">全端口</button>
        <button type="button" @click="applyPortPreset('database')">数据库</button>
        <button type="button" @click="applyPortPreset('web')">Web 服务</button>
      </div>
      <div class="port-inline-grid">
        <label><span>目标</span><input v-model="portHost" @keyup.enter="scanPorts" /></label>
        <label><span>超时</span><input v-model.number="portTimeout" type="number" @keyup.enter="scanPorts" /></label>
        <label><span>并发</span><input v-model.number="portConcurrency" type="number" @keyup.enter="scanPorts" /></label>
      </div>
      <label><span>端口</span><input v-model="portsInput" @keyup.enter="scanPorts" /></label>
      <div class="split-actions">
        <button v-if="canUsePageAction('ports', 'port_scan')" class="primary" type="button" :disabled="isScanningPorts" @click="scanPorts">开始扫描</button>
        <button type="button" :disabled="!isScanningPorts" @click="stopPortScan">停止</button>
      </div>
    </article>

    <article class="panel">
      <h2>扫描结果</h2>
      <div class="progress"><span :style="{ width: `${portProgress}%` }"></span></div>
      <p v-if="portScanMessage" class="inline-status">{{ portScanMessage }}</p>
      <div v-if="portResult" class="port-summary">
        <article><span>目标</span><strong>{{ portResult.host }}</strong></article>
        <article><span>进度</span><strong>{{ portResult.scanned_ports }}/{{ portResult.total_ports ?? portResult.scanned_ports }}</strong></article>
        <article><span>开放</span><strong class="green">{{ portResult.open_ports.length }}</strong></article>
        <article><span>耗时</span><strong>{{ portResult.duration }} ms</strong></article>
      </div>
      <p v-if="portResult?.error" class="result-warning">{{ portResult.error }}</p>
      <div v-if="portResult && !portResult.error" class="port-open-list">
        <button
          v-for="item in portResult.open_details"
          :key="item.port"
          class="port-open-item"
          type="button"
          @click="copyText(String(item.port), `已复制端口 ${item.port}。`)"
        >
          <strong>{{ item.port }}</strong>
          <span>{{ item.service }}</span>
          <small>{{ item.duration }} ms</small>
        </button>
        <p v-if="!portResult.open_ports.length && !isScanningPorts" class="empty-state">没有发现开放端口</p>
      </div>
    </article>
  </div>
</template>

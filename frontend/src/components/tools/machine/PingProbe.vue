<script setup lang="ts">
import { useAppContext } from '@app/context';

const {
  pingContinuous,
  setPingPreset,
  pingHost,
  pingCount,
  pingTimeout,
  pingInterval,
  runPing,
  isPinging,
  stopPing,
  exportPingResults,
  pingMetrics,
  pingChart,
  pingDetails,
  clearPingResults,
  canUsePageAction,
} = useAppContext();
</script>
<template>
        <div class="machine-ping-column">
          <article class="panel ping-config">
            <div class="panel-title compact">
              <h2>Ping 测试</h2>
              <label class="check-line ping-check top-check"><input v-model="pingContinuous" type="checkbox" />连续 Ping（直到手动停止）</label>
            </div>
            <div class="ping-presets">
              <button type="button" @click="setPingPreset('223.5.5.5')">阿里DNS</button>
              <button type="button" @click="setPingPreset('119.29.29.29')">腾讯DNS</button>
              <button type="button" @click="setPingPreset('114.114.114.114')">114DNS</button>
              <button type="button" @click="setPingPreset('8.8.8.8')">Google DNS</button>
              <button type="button" @click="setPingPreset('baidu.com')">百度</button>
            </div>
            <div class="ping-target-block">
              <label><span>目标主机</span><input v-model="pingHost" @keyup.enter="runPing" /></label>
              <label><span>次数</span><input v-model.number="pingCount" min="1" max="200" type="number" @keyup.enter="runPing" /></label>
              <label><span>超时 (ms)</span><input v-model.number="pingTimeout" min="300" max="30000" step="100" type="number" @keyup.enter="runPing" /></label>
              <label><span>间隔 (ms)</span><input v-model.number="pingInterval" min="100" max="10000" step="100" type="number" @keyup.enter="runPing" /></label>
            </div>
            <div class="ping-actions">
              <button v-if="canUsePageAction('ports', 'ping')" class="primary" type="button" :disabled="isPinging" @click="runPing">{{ isPinging ? 'Ping 中' : '开始 Ping' }}</button>
              <button type="button" :disabled="!isPinging" @click="stopPing">停止</button>
              <button v-if="canUsePageAction('ports', 'export_ping')" type="button" :disabled="!pingDetails.length" @click="exportPingResults">导出</button>
            </div>
          </article>

          <article class="panel ping-results">
            <div class="panel-title">
              <h2>Ping 结果</h2>
            </div>
            <div class="ping-metrics">
              <article><strong class="green">{{ pingMetrics.success_count }}</strong><span>成功</span></article>
              <article><strong class="danger-text">{{ pingMetrics.failure_count }}</strong><span>失败</span></article>
              <article><strong class="orange">{{ pingMetrics.loss_rate }}%</strong><span>丢包率</span></article>
              <article><strong>{{ pingMetrics.average_response_time ?? '--' }}</strong><span>平均 (ms)</span></article>
              <article><strong class="green">{{ pingMetrics.min_response_time ?? '--' }}</strong><span>最小 (ms)</span></article>
              <article><strong class="danger-text">{{ pingMetrics.max_response_time ?? '--' }}</strong><span>最大 (ms)</span></article>
              <article><strong class="purple-text">{{ pingMetrics.jitter ?? '--' }}</strong><span>抖动 (ms)</span></article>
              <article><strong>{{ pingMetrics.total_count }}</strong><span>总计</span></article>
            </div>
            <section class="ping-chart-panel">
              <div class="ping-section-title">
                <h3>延迟波形图</h3>
                <div class="ping-legend">
                  <span><i class="latency-dot"></i>延迟</span>
                  <span><i class="average-dot"></i>平均</span>
                  <span><i class="timeout-dot"></i>超时</span>
                </div>
              </div>
              <div class="ping-chart">
                <svg v-if="pingDetails.length" :viewBox="`0 0 ${pingChart.width} ${pingChart.height}`" role="img" aria-label="Ping 延迟波形图">
                  <g class="chart-grid">
                    <g v-for="tick in pingChart.yTicks" :key="tick.value">
                      <text :x="pingChart.padding.left - 10" :y="tick.y + 4" text-anchor="end">{{ tick.value }}</text>
                      <line :x1="pingChart.padding.left" :x2="pingChart.width - pingChart.padding.right" :y1="tick.y" :y2="tick.y" />
                    </g>
                  </g>
                  <line
                    v-if="pingChart.averageY !== null"
                    :x1="pingChart.padding.left"
                    :x2="pingChart.width - pingChart.padding.right"
                    :y1="pingChart.averageY"
                    :y2="pingChart.averageY"
                    class="average-line"
                  />
                  <path :d="pingChart.latencyPath" class="latency-line" />
                  <circle
                    v-for="point in pingChart.points"
                    :key="point.item.sequence"
                    :cx="point.x"
                    :cy="point.y"
                    r="4"
                    :class="point.item.status === 'timeout' ? 'timeout-point' : 'latency-point'"
                  />
                  <g class="chart-x-axis">
                    <text
                      v-for="point in pingChart.points"
                      :key="`label-${point.item.sequence}`"
                      :x="point.x"
                      :y="pingChart.height - 10"
                      text-anchor="middle"
                    >
                      #{{ point.item.sequence }}
                    </text>
                  </g>
                </svg>
                <div v-else class="ping-empty chart-empty">开始测试后，这里会展示延迟波形。</div>
              </div>
            </section>
            <section class="ping-detail-box">
              <div class="ping-section-title">
                <h3>详细结果</h3>
                <button type="button" :disabled="!pingDetails.length || isPinging" @click="clearPingResults">清空</button>
              </div>
              <div class="ping-detail-list">
                <div v-if="!pingDetails.length" class="ping-empty">还没有测试结果。</div>
                <div
                  v-for="row in pingDetails"
                  :key="row.sequence"
                  class="ping-row"
                  :class="{ timeout: row.status === 'timeout' }"
                >
                  <span>#{{ row.sequence }}</span>
                  <strong>{{ row.ip }}</strong>
                  <span>{{ row.status === 'online' ? '成功' : '超时' }}</span>
                  <span>{{ row.response_time ?? '--' }} ms</span>
                </div>
              </div>
            </section>
          </article>
        </div>
</template>

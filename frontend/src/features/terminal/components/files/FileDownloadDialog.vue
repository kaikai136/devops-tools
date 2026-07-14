<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue';
import AppIcon from '@shared/components/AppIcon.vue';
import { formatTerminalFileSizeValue } from '../../utils/protocol';
import { isTransferActive, type SftpTransferRecord } from '../../composables/useSftpBrowser';

const props = defineProps<{
  records: SftpTransferRecord[];
  hasRunning: boolean;
  hasClearable: boolean;
  height: number;
  maxHeight: number;
}>();
const emit = defineEmits<{
  cancel: [record: SftpTransferRecord];
  cancelAll: [];
  clear: [];
  resize: [height: number];
}>();
const resizing = ref(false);
let startY = 0;
let startHeight = 0;

function countText(record: SftpTransferRecord) {
  if (!record.totalFiles) return record.status === 'running' ? '扫描中' : '0 / 0';
  return `${record.completedFiles} / ${record.totalFiles}`;
}
function statusText(record: SftpTransferRecord) {
  if (record.status === 'queued') return '等待中';
  if (record.status === 'running') {
    if (!record.currentFile) return '传输中';
    const bytes = record.currentTotalBytes > 0
      ? `（${formatTerminalFileSizeValue(record.currentBytes)} / ${formatTerminalFileSizeValue(record.currentTotalBytes)}）`
      : record.currentBytes > 0 ? `（${formatTerminalFileSizeValue(record.currentBytes)}）` : '';
    return `传输中：${record.currentFile}${bytes}`;
  }
  if (record.status === 'success') return '已完成';
  if (record.status === 'canceled') return '已取消';
  return record.error || '传输失败';
}
function startResize(event: MouseEvent) {
  if (event.button !== 0) return;
  event.preventDefault();
  resizing.value = true;
  startY = event.clientY;
  startHeight = props.height;
  window.addEventListener('mousemove', resize);
  window.addEventListener('mouseup', stopResize);
}
function resize(event: MouseEvent) {
  if (!resizing.value) return;
  emit('resize', Math.min(Math.max(startHeight + startY - event.clientY, 96), props.maxHeight));
}
function stopResize() {
  resizing.value = false;
  window.removeEventListener('mousemove', resize);
  window.removeEventListener('mouseup', stopResize);
}
onBeforeUnmount(stopResize);
</script>

<template>
  <section class="terminal-transfer-panel" :class="{ resizing }">
    <button class="terminal-transfer-resizer" type="button" title="调整文件传输栏高度" aria-label="调整文件传输栏高度" @mousedown="startResize"></button>
    <header class="terminal-transfer-header">
      <strong>文件传输</strong>
      <div>
        <button type="button" title="取消全部" aria-label="取消全部" :disabled="!hasRunning" @click="emit('cancelAll')"><AppIcon name="x" :size="14" /></button>
        <button type="button" title="清空记录" aria-label="清空记录" :disabled="!hasClearable" @click="emit('clear')"><AppIcon name="trash" :size="14" /></button>
      </div>
    </header>
    <div class="terminal-transfer-list">
      <p v-if="!records.length" class="terminal-transfer-empty">无传输记录</p>
      <article v-for="record in records" :key="record.id" class="terminal-transfer-item" :class="[record.kind, record.status]">
        <AppIcon :name="record.kind === 'upload' ? 'upload' : 'download'" :size="15" />
        <div class="terminal-transfer-main">
          <div class="terminal-transfer-line"><strong>{{ record.name }}</strong><span>{{ countText(record) }}</span></div>
          <div class="terminal-transfer-progress" aria-hidden="true"><i :style="{ width: `${Math.max(0, Math.min(100, record.progress))}%` }"></i></div>
          <p>{{ statusText(record) }}</p>
        </div>
        <button type="button" title="取消" aria-label="取消" :disabled="!isTransferActive(record)" @click="emit('cancel', record)"><AppIcon name="x" :size="13" /></button>
      </article>
    </div>
  </section>
</template>

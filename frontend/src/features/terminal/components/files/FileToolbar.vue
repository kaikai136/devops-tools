<script setup lang="ts">
import AppIcon from '@shared/components/AppIcon.vue';

defineProps<{
  canDownload: boolean;
  selectedCount: number;
}>();

const emit = defineEmits<{
  create: [mode: 'file' | 'directory'];
  upload: [];
  download: [];
  delete: [];
  parent: [];
  refresh: [];
}>();
</script>

<template>
  <div class="terminal-file-toolbar">
    <button type="button" title="新建文件" aria-label="新建文件" @click="emit('create', 'file')"><AppIcon name="plus" :size="15" /></button>
    <button type="button" title="新建文件夹" aria-label="新建文件夹" @click="emit('create', 'directory')"><AppIcon name="folderPlus" :size="15" /></button>
    <span></span>
    <button type="button" title="上传" aria-label="上传" @click="emit('upload')"><AppIcon name="upload" :size="15" /></button>
    <button type="button" title="下载" aria-label="下载" :disabled="!canDownload" @click="emit('download')"><AppIcon name="download" :size="15" /></button>
    <button type="button" title="删除" aria-label="删除" :disabled="!selectedCount" @click="emit('delete')"><AppIcon name="trash" :size="15" /></button>
    <span></span>
    <button type="button" title="返回上级" aria-label="返回上级" @click="emit('parent')"><AppIcon name="chevronRight" :size="15" /></button>
    <button type="button" title="刷新" aria-label="刷新" @click="emit('refresh')"><AppIcon name="refresh" :size="15" /></button>
    <span></span>
    <button type="button" title="搜索" aria-label="搜索"><AppIcon name="search" :size="15" /></button>
  </div>
</template>

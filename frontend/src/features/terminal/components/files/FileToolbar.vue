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
    <NativeTooltip content="新建文件" placement="bottom">
      <NativeButton circle aria-label="新建文件" @click="emit('create', 'file')"><AppIcon name="plus" :size="15" /></NativeButton>
    </NativeTooltip>
    <NativeTooltip content="新建文件夹" placement="bottom">
      <NativeButton circle aria-label="新建文件夹" @click="emit('create', 'directory')"><AppIcon name="folderPlus" :size="15" /></NativeButton>
    </NativeTooltip>
    <span></span>
    <NativeTooltip content="上传" placement="bottom">
      <NativeButton circle aria-label="上传" @click="emit('upload')"><AppIcon name="upload" :size="15" /></NativeButton>
    </NativeTooltip>
    <NativeTooltip content="下载" placement="bottom">
      <NativeButton circle aria-label="下载" :disabled="!canDownload" @click="emit('download')"><AppIcon name="download" :size="15" /></NativeButton>
    </NativeTooltip>
    <NativeTooltip content="删除" placement="bottom">
      <NativeButton circle aria-label="删除" :disabled="!selectedCount" @click="emit('delete')"><AppIcon name="trash" :size="15" /></NativeButton>
    </NativeTooltip>
    <span></span>
    <NativeTooltip content="返回上级" placement="bottom">
      <NativeButton circle aria-label="返回上级" @click="emit('parent')"><AppIcon name="chevronRight" :size="15" /></NativeButton>
    </NativeTooltip>
    <NativeTooltip content="刷新" placement="bottom">
      <NativeButton circle aria-label="刷新" @click="emit('refresh')"><AppIcon name="refresh" :size="15" /></NativeButton>
    </NativeTooltip>
    <span></span>
    <NativeTooltip content="搜索" placement="bottom">
      <NativeButton circle aria-label="搜索"><AppIcon name="search" :size="15" /></NativeButton>
    </NativeTooltip>
  </div>
</template>

<script setup lang="ts">
const previewRows = [{ group: 'default', name: 'host-01', ip: '192.168.1.10', os: 'linux', port: 22, remark: '' }];

const emit = defineEmits<{
  close: [];
  confirm: [];
  'download-template': [];
}>();
</script>

<template>
  <NativeDialog class="host-transfer-modal host-import-modal" :model-value="true" title="导入主机表格" width="720px" @close="emit('close')">
      <h2>导入主机表格</h2>
      <div class="host-import-body">
        <p>模板只导入主机基础信息，已存在的主机将跳过保留。</p>
        <NativeTable :data="previewRows" class="host-import-template-preview" size="small">
          <NativeTableColumn prop="group" label="主机分组" />
          <NativeTableColumn prop="name" label="节点" />
          <NativeTableColumn prop="ip" label="IP地址" />
          <NativeTableColumn prop="os" label="平台类型" />
          <NativeTableColumn prop="port" label="端口" />
          <NativeTableColumn prop="remark" label="备注" />
        </NativeTable>
      </div>
      <template #footer>
        <div class="modal-actions">
          <NativeButton @click="emit('close')">取消</NativeButton>
          <NativeButton @click="emit('download-template')">下载导入模板</NativeButton>
          <NativeButton class="primary" type="primary" @click="emit('confirm')">直接导入</NativeButton>
        </div>
      </template>
  </NativeDialog>
</template>

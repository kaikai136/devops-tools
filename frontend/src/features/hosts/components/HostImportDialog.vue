<script setup lang="ts">
import AppIcon from '@shared/components/AppIcon.vue';

const emit = defineEmits<{
  close: [];
  confirm: [];
  'download-template': [];
}>();
</script>

<template>
  <div class="modal-backdrop" @click.self="emit('close')">
    <article class="host-transfer-modal host-import-modal">
      <button class="modal-close" type="button" @click="emit('close')"><AppIcon name="x" :size="16" /></button>
      <h2>导入主机表格</h2>
      <div class="host-import-body">
        <p>模板只导入主机基础信息，已存在的主机将跳过保留。</p>
        <table class="host-import-template-preview">
          <thead>
            <tr>
              <th>主机分组</th>
              <th>节点</th>
              <th>IP地址</th>
              <th>平台类型</th>
              <th>端口</th>
              <th>备注</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>default</td>
              <td>host-01</td>
              <td>192.168.1.10</td>
              <td>linux</td>
              <td>22</td>
              <td></td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="modal-actions">
        <button type="button" @click="emit('close')">取消</button>
        <button type="button" @click="emit('download-template')">下载导入模板</button>
        <button class="primary" type="button" @click="emit('confirm')">直接导入</button>
      </div>
    </article>
  </div>
</template>

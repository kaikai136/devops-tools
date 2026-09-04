<script setup lang="ts">
import AppIcon from '@shared/components/AppIcon.vue';
import {
  formatPropertiesSize,
  groupLabel,
  normalizeOctalMode,
  ownerLabel,
  propertiesTypeLabel,
  type SftpPropertiesDialogState,
} from '../../composables/useSftpBrowser';

const props = defineProps<{ dialog: SftpPropertiesDialogState }>();
const emit = defineEmits<{
  change: [patch: Partial<SftpPropertiesDialogState>];
  close: [];
  save: [];
}>();

function patch(patchValue: Partial<SftpPropertiesDialogState>) {
  emit('change', patchValue);
}
function patchDraft(patchValue: Partial<SftpPropertiesDialogState['draft']>) {
  patch({ draft: { ...props.dialog.draft, ...patchValue } });
}
function valueFromInput(value: Event | string) {
  return typeof value === 'string' ? value : (value.target as HTMLInputElement).value;
}
function checkedFromControl(value: Event | boolean | string | number) {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'string') return value === 'true';
  if (typeof value === 'number') return value !== 0;
  return (value.target as HTMLInputElement).checked;
}
function onDraftInput(field: 'owner' | 'group', value: Event | string) {
  patchDraft({ [field]: valueFromInput(value) });
}
function onRecursiveChange(value: Event | boolean | string | number) {
  patch({ recursive: checkedFromControl(value) });
}
function isPermissionChecked(mask: number) {
  const mode = Number.parseInt(props.dialog.draft.octalMode || '0', 8) || 0;
  return Boolean(mode & mask);
}
function setPermission(mask: number, value: Event | boolean | string | number) {
  const current = Number.parseInt(props.dialog.draft.octalMode || '0', 8) || 0;
  const checked = checkedFromControl(value);
  const next = checked ? current | mask : current & ~mask;
  patchDraft({ octalMode: (next & 0o7777).toString(8).padStart(4, '0') });
}
function specialOctalDigit() {
  return normalizeOctalMode(props.dialog.draft.octalMode).charAt(0);
}
function standardOctalMode() {
  return normalizeOctalMode(props.dialog.draft.octalMode).slice(1);
}
function updateOctalMode(value: Event | string) {
  const octal = valueFromInput(value).replace(/[^0-7]/g, '').slice(-3).padStart(3, '0');
  patchDraft({ octalMode: `${specialOctalDigit()}${octal}` });
}
</script>

<template>
  <el-dialog
    :model-value="dialog.visible"
    class="terminal-file-properties-backdrop"
    width="640px"
    :show-close="false"
    @close="emit('close')"
  >
    <section class="terminal-file-properties-modal">
      <header class="terminal-file-properties-head">
        <span class="terminal-file-properties-icon" :class="dialog.properties?.type || dialog.entry?.type">
          <AppIcon :name="(dialog.properties?.type || dialog.entry?.type) === 'directory' ? 'folder' : 'file'" :size="18" />
        </span>
        <h2>{{ dialog.entry?.name || dialog.properties?.name || '文件' }} 的属性</h2>
        <el-button class="terminal-file-properties-close" circle aria-label="关闭" :disabled="dialog.saving" @click="emit('close')">
          <AppIcon name="x" :size="16" />
        </el-button>
      </header>

      <el-empty v-if="dialog.loading" class="terminal-file-properties-empty" description="属性读取中..." />
      <div v-else-if="dialog.properties" class="terminal-file-properties-body">
        <el-alert v-if="dialog.error" class="terminal-file-properties-error" type="error" :title="dialog.error" :closable="false" />

        <section class="terminal-file-properties-section">
          <h3>常规</h3>
          <dl class="terminal-file-properties-details">
            <dt>类型</dt><dd>{{ propertiesTypeLabel(dialog.properties) }}</dd>
            <dt>位置</dt><dd>{{ dialog.properties.directory }}</dd>
            <dt>大小</dt><dd>{{ formatPropertiesSize(dialog.properties) }}</dd>
            <dt>修改时间</dt><dd>{{ dialog.properties.modifiedAt }}</dd>
            <dt>访问时间</dt><dd>{{ dialog.properties.accessedAt }}</dd>
            <dt>所有者</dt><dd>{{ ownerLabel(dialog.properties) }} [{{ dialog.properties.uid }}]</dd>
            <dt>组</dt><dd>{{ groupLabel(dialog.properties) }} [{{ dialog.properties.gid }}]</dd>
          </dl>
        </section>

        <section class="terminal-file-properties-section">
          <h3>所有权</h3>
          <label class="terminal-file-properties-field">
            <span>所有者</span>
            <el-input :model-value="dialog.draft.owner" :disabled="dialog.saving" @input="onDraftInput('owner', $event)" />
          </label>
          <label class="terminal-file-properties-field">
            <span>组</span>
            <el-input :model-value="dialog.draft.group" :disabled="dialog.saving" @input="onDraftInput('group', $event)" />
          </label>
        </section>

        <section class="terminal-file-properties-section">
          <h3>权限</h3>
          <div class="terminal-file-permission-table" role="table" aria-label="权限">
            <span></span><strong>R</strong><strong>W</strong><strong>X</strong><strong>特殊</strong>
            <strong>用户</strong>
            <el-checkbox :model-value="isPermissionChecked(0o400)" :disabled="dialog.saving" @change="setPermission(0o400, $event)" />
            <el-checkbox :model-value="isPermissionChecked(0o200)" :disabled="dialog.saving" @change="setPermission(0o200, $event)" />
            <el-checkbox :model-value="isPermissionChecked(0o100)" :disabled="dialog.saving" @change="setPermission(0o100, $event)" />
            <el-checkbox :model-value="isPermissionChecked(0o4000)" :disabled="dialog.saving" @change="setPermission(0o4000, $event)">UID</el-checkbox>
            <strong>组</strong>
            <el-checkbox :model-value="isPermissionChecked(0o040)" :disabled="dialog.saving" @change="setPermission(0o040, $event)" />
            <el-checkbox :model-value="isPermissionChecked(0o020)" :disabled="dialog.saving" @change="setPermission(0o020, $event)" />
            <el-checkbox :model-value="isPermissionChecked(0o010)" :disabled="dialog.saving" @change="setPermission(0o010, $event)" />
            <el-checkbox :model-value="isPermissionChecked(0o2000)" :disabled="dialog.saving" @change="setPermission(0o2000, $event)">GID</el-checkbox>
            <strong>其他</strong>
            <el-checkbox :model-value="isPermissionChecked(0o004)" :disabled="dialog.saving" @change="setPermission(0o004, $event)" />
            <el-checkbox :model-value="isPermissionChecked(0o002)" :disabled="dialog.saving" @change="setPermission(0o002, $event)" />
            <el-checkbox :model-value="isPermissionChecked(0o001)" :disabled="dialog.saving" @change="setPermission(0o001, $event)" />
            <el-checkbox :model-value="isPermissionChecked(0o1000)" :disabled="dialog.saving" @change="setPermission(0o1000, $event)">粘性</el-checkbox>
          </div>
          <label class="terminal-file-octal-field">
            <span>八进制</span>
            <em>{{ specialOctalDigit() }}</em>
            <el-input
              :model-value="standardOctalMode()"
              inputmode="numeric"
              maxlength="3"
              :disabled="dialog.saving"
              @input="updateOctalMode"
            />
          </label>
          <el-checkbox
            v-if="dialog.properties.type === 'directory'"
            class="terminal-file-recursive-field"
            :model-value="dialog.recursive"
            :disabled="dialog.saving"
            @change="onRecursiveChange"
          >
            应用到此目录及所有子目录/文件
          </el-checkbox>
        </section>
      </div>
      <el-empty v-else class="terminal-file-properties-empty error" :description="dialog.error || '属性读取失败'" />

      <footer class="terminal-file-properties-actions">
        <el-button :disabled="dialog.saving" @click="emit('close')">取消</el-button>
        <el-button type="primary" :loading="dialog.saving" :disabled="dialog.loading || dialog.saving || !dialog.properties" @click="emit('save')">
          {{ dialog.saving ? '保存中...' : '保存' }}
        </el-button>
      </footer>
    </section>
  </el-dialog>
</template>

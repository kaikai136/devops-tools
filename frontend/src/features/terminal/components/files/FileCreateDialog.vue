<script setup lang="ts">
import AppIcon from '@shared/components/AppIcon.vue';
import { normalizeOctalMode, type SftpCreateDialogState } from '../../composables/useSftpBrowser';

const props = defineProps<{
  dialog: SftpCreateDialogState;
  title: string;
  nameLabel: string;
  openLabel: string;
}>();
const emit = defineEmits<{
  change: [patch: Partial<SftpCreateDialogState>];
  close: [];
  save: [];
}>();

function patch(patchValue: Partial<SftpCreateDialogState>) {
  emit('change', patchValue);
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
function onTextInput(field: 'name' | 'targetPath', value: Event | string) {
  patch({ [field]: valueFromInput(value) });
}
function isPermissionChecked(mask: number) {
  const mode = Number.parseInt(props.dialog.octalMode || '0', 8) || 0;
  return Boolean(mode & mask);
}
function setPermission(mask: number, value: Event | boolean | string | number) {
  const current = Number.parseInt(props.dialog.octalMode || '0', 8) || 0;
  const checked = checkedFromControl(value);
  const next = checked ? current | mask : current & ~mask;
  patch({ octalMode: (next & 0o7777).toString(8).padStart(4, '0') });
}
function specialOctalDigit() {
  return normalizeOctalMode(props.dialog.octalMode).charAt(0);
}
function standardOctalMode() {
  return normalizeOctalMode(props.dialog.octalMode).slice(1);
}
function updateOctalMode(value: Event | string) {
  const octal = valueFromInput(value).replace(/[^0-7]/g, '').slice(-3).padStart(3, '0');
  patch({ octalMode: `${specialOctalDigit()}${octal}` });
}
function onOpenAfterCreateChange(value: Event | boolean | string | number) {
  patch({ openAfterCreate: checkedFromControl(value) });
}
</script>

<template>
  <NativeDialog
    :model-value="dialog.visible"
    class="terminal-file-create-backdrop"
    width="520px"
    :show-close="false"
    @close="emit('close')"
  >
    <section class="terminal-file-create-modal">
      <header>
        <h2>{{ title }}</h2>
        <NativeButton circle aria-label="关闭" :disabled="dialog.saving" @click="emit('close')">
          <AppIcon name="x" :size="16" />
        </NativeButton>
      </header>
      <div class="terminal-file-create-body">
        <label class="terminal-file-create-name-row">
          <span>{{ nameLabel }}</span>
          <NativeInput
            :model-value="dialog.name"
            :disabled="dialog.saving"
            autofocus
            @input="onTextInput('name', $event)"
            @keydown.enter.prevent="emit('save')"
          />
        </label>
        <label v-if="dialog.mode === 'symlink'" class="terminal-file-create-name-row">
          <span>目标路径</span>
          <NativeInput
            :model-value="dialog.targetPath"
            :disabled="dialog.saving"
            @input="onTextInput('targetPath', $event)"
            @keydown.enter.prevent="emit('save')"
          />
        </label>
        <div v-if="dialog.mode !== 'symlink'" class="terminal-file-create-permissions">
          <span class="terminal-file-create-label">权限</span>
          <div class="terminal-file-create-permission-grid" role="group" aria-label="权限">
            <span></span><span>用户</span>
            <NativeCheckbox :model-value="isPermissionChecked(0o400)" :disabled="dialog.saving" @change="setPermission(0o400, $event)">R</NativeCheckbox>
            <NativeCheckbox :model-value="isPermissionChecked(0o200)" :disabled="dialog.saving" @change="setPermission(0o200, $event)">W</NativeCheckbox>
            <NativeCheckbox :model-value="isPermissionChecked(0o100)" :disabled="dialog.saving" @change="setPermission(0o100, $event)">X</NativeCheckbox>
            <NativeCheckbox :model-value="isPermissionChecked(0o4000)" :disabled="dialog.saving" @change="setPermission(0o4000, $event)">UID</NativeCheckbox>
            <span></span><span>组</span>
            <NativeCheckbox :model-value="isPermissionChecked(0o040)" :disabled="dialog.saving" @change="setPermission(0o040, $event)">R</NativeCheckbox>
            <NativeCheckbox :model-value="isPermissionChecked(0o020)" :disabled="dialog.saving" @change="setPermission(0o020, $event)">W</NativeCheckbox>
            <NativeCheckbox :model-value="isPermissionChecked(0o010)" :disabled="dialog.saving" @change="setPermission(0o010, $event)">X</NativeCheckbox>
            <NativeCheckbox :model-value="isPermissionChecked(0o2000)" :disabled="dialog.saving" @change="setPermission(0o2000, $event)">GID</NativeCheckbox>
            <span></span><span>其他</span>
            <NativeCheckbox :model-value="isPermissionChecked(0o004)" :disabled="dialog.saving" @change="setPermission(0o004, $event)">R</NativeCheckbox>
            <NativeCheckbox :model-value="isPermissionChecked(0o002)" :disabled="dialog.saving" @change="setPermission(0o002, $event)">W</NativeCheckbox>
            <NativeCheckbox :model-value="isPermissionChecked(0o001)" :disabled="dialog.saving" @change="setPermission(0o001, $event)">X</NativeCheckbox>
            <NativeCheckbox :model-value="isPermissionChecked(0o1000)" :disabled="dialog.saving" @change="setPermission(0o1000, $event)">粘性</NativeCheckbox>
          </div>
        </div>
        <label v-if="dialog.mode !== 'symlink'" class="terminal-file-create-octal-row">
          <span>八进制</span>
          <em>{{ specialOctalDigit() }}</em>
          <NativeInput
            :model-value="standardOctalMode()"
            inputmode="numeric"
            maxlength="3"
            :disabled="dialog.saving"
            @input="updateOctalMode"
            @keydown.enter.prevent="emit('save')"
          />
        </label>
        <NativeAlert v-if="dialog.error" class="terminal-file-create-error" type="error" :title="dialog.error" :closable="false" />
      </div>
      <footer>
        <NativeCheckbox
          v-if="dialog.mode !== 'symlink'"
          class="terminal-file-create-open-after"
          :model-value="dialog.openAfterCreate"
          :disabled="dialog.saving"
          @change="onOpenAfterCreateChange"
        >
          {{ openLabel }}
        </NativeCheckbox>
        <div>
          <NativeButton :disabled="dialog.saving" @click="emit('close')">取消</NativeButton>
          <NativeButton type="primary" :loading="dialog.saving" :disabled="dialog.saving" @click="emit('save')">
            {{ dialog.saving ? '创建中...' : '确定' }}
          </NativeButton>
        </div>
      </footer>
    </section>
  </NativeDialog>
</template>

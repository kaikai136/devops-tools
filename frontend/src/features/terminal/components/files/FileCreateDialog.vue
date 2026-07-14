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
function onTextInput(field: 'name' | 'targetPath', event: Event) {
  patch({ [field]: (event.target as HTMLInputElement).value });
}
function isPermissionChecked(mask: number) {
  const mode = Number.parseInt(props.dialog.octalMode || '0', 8) || 0;
  return Boolean(mode & mask);
}
function setPermission(mask: number, event: Event) {
  const current = Number.parseInt(props.dialog.octalMode || '0', 8) || 0;
  const checked = (event.target as HTMLInputElement).checked;
  const next = checked ? current | mask : current & ~mask;
  patch({ octalMode: (next & 0o7777).toString(8).padStart(4, '0') });
}
function specialOctalDigit() {
  return normalizeOctalMode(props.dialog.octalMode).charAt(0);
}
function standardOctalMode() {
  return normalizeOctalMode(props.dialog.octalMode).slice(1);
}
function updateOctalMode(event: Event) {
  const value = (event.target as HTMLInputElement).value.replace(/[^0-7]/g, '').slice(-3).padStart(3, '0');
  patch({ octalMode: `${specialOctalDigit()}${value}` });
}
function onOpenAfterCreateChange(event: Event) {
  patch({ openAfterCreate: (event.target as HTMLInputElement).checked });
}
</script>

<template>
  <Teleport to="body">
    <div v-if="dialog.visible" class="modal-backdrop terminal-file-create-backdrop" @click.self="emit('close')">
      <section class="terminal-file-create-modal" role="dialog" aria-modal="true">
        <header>
          <h2>{{ title }}</h2>
          <button type="button" aria-label="关闭" :disabled="dialog.saving" @click="emit('close')">
            <AppIcon name="x" :size="16" />
          </button>
        </header>
        <div class="terminal-file-create-body">
          <label class="terminal-file-create-name-row">
            <span>{{ nameLabel }}</span>
            <input
              :value="dialog.name"
              type="text"
              :disabled="dialog.saving"
              autofocus
              @input="onTextInput('name', $event)"
              @keydown.enter.prevent="emit('save')"
            />
          </label>
          <label v-if="dialog.mode === 'symlink'" class="terminal-file-create-name-row">
            <span>目标路径：</span>
            <input
              :value="dialog.targetPath"
              type="text"
              :disabled="dialog.saving"
              @input="onTextInput('targetPath', $event)"
              @keydown.enter.prevent="emit('save')"
            />
          </label>
          <div v-if="dialog.mode !== 'symlink'" class="terminal-file-create-permissions">
            <span class="terminal-file-create-label">权限：</span>
            <div class="terminal-file-create-permission-grid" role="group" aria-label="权限">
              <span></span><span>用户</span>
              <label><input type="checkbox" :checked="isPermissionChecked(0o400)" :disabled="dialog.saving" @change="setPermission(0o400, $event)" /> R</label>
              <label><input type="checkbox" :checked="isPermissionChecked(0o200)" :disabled="dialog.saving" @change="setPermission(0o200, $event)" /> W</label>
              <label><input type="checkbox" :checked="isPermissionChecked(0o100)" :disabled="dialog.saving" @change="setPermission(0o100, $event)" /> X</label>
              <label><input type="checkbox" :checked="isPermissionChecked(0o4000)" :disabled="dialog.saving" @change="setPermission(0o4000, $event)" /> UID</label>
              <span></span><span>组</span>
              <label><input type="checkbox" :checked="isPermissionChecked(0o040)" :disabled="dialog.saving" @change="setPermission(0o040, $event)" /> R</label>
              <label><input type="checkbox" :checked="isPermissionChecked(0o020)" :disabled="dialog.saving" @change="setPermission(0o020, $event)" /> W</label>
              <label><input type="checkbox" :checked="isPermissionChecked(0o010)" :disabled="dialog.saving" @change="setPermission(0o010, $event)" /> X</label>
              <label><input type="checkbox" :checked="isPermissionChecked(0o2000)" :disabled="dialog.saving" @change="setPermission(0o2000, $event)" /> GID</label>
              <span></span><span>其他</span>
              <label><input type="checkbox" :checked="isPermissionChecked(0o004)" :disabled="dialog.saving" @change="setPermission(0o004, $event)" /> R</label>
              <label><input type="checkbox" :checked="isPermissionChecked(0o002)" :disabled="dialog.saving" @change="setPermission(0o002, $event)" /> W</label>
              <label><input type="checkbox" :checked="isPermissionChecked(0o001)" :disabled="dialog.saving" @change="setPermission(0o001, $event)" /> X</label>
              <label><input type="checkbox" :checked="isPermissionChecked(0o1000)" :disabled="dialog.saving" @change="setPermission(0o1000, $event)" /> 粘性</label>
            </div>
          </div>
          <label v-if="dialog.mode !== 'symlink'" class="terminal-file-create-octal-row">
            <span>八进制</span>
            <em>{{ specialOctalDigit() }}</em>
            <input
              :value="standardOctalMode()"
              type="text"
              inputmode="numeric"
              maxlength="3"
              :disabled="dialog.saving"
              @input="updateOctalMode"
              @keydown.enter.prevent="emit('save')"
            />
          </label>
          <p v-if="dialog.error" class="terminal-file-create-error">{{ dialog.error }}</p>
        </div>
        <footer>
          <label v-if="dialog.mode !== 'symlink'" class="terminal-file-create-open-after">
            <input
              type="checkbox"
              :checked="dialog.openAfterCreate"
              :disabled="dialog.saving"
              @change="onOpenAfterCreateChange"
            />
            <span>{{ openLabel }}</span>
          </label>
          <div>
            <button type="button" :disabled="dialog.saving" @click="emit('close')">取消</button>
            <button class="primary" type="button" :disabled="dialog.saving" @click="emit('save')">
              {{ dialog.saving ? '创建中...' : '确定' }}
            </button>
          </div>
        </footer>
      </section>
    </div>
  </Teleport>
</template>
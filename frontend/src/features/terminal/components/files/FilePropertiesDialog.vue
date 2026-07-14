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
function onDraftInput(field: 'owner' | 'group', event: Event) {
  patchDraft({ [field]: (event.target as HTMLInputElement).value });
}
function onRecursiveChange(event: Event) {
  patch({ recursive: (event.target as HTMLInputElement).checked });
}
function isPermissionChecked(mask: number) {
  const mode = Number.parseInt(props.dialog.draft.octalMode || '0', 8) || 0;
  return Boolean(mode & mask);
}
function setPermission(mask: number, event: Event) {
  const current = Number.parseInt(props.dialog.draft.octalMode || '0', 8) || 0;
  const checked = (event.target as HTMLInputElement).checked;
  const next = checked ? current | mask : current & ~mask;
  patchDraft({ octalMode: (next & 0o7777).toString(8).padStart(4, '0') });
}
function specialOctalDigit() {
  return normalizeOctalMode(props.dialog.draft.octalMode).charAt(0);
}
function standardOctalMode() {
  return normalizeOctalMode(props.dialog.draft.octalMode).slice(1);
}
function updateOctalMode(event: Event) {
  const value = (event.target as HTMLInputElement).value.replace(/[^0-7]/g, '').slice(-3).padStart(3, '0');
  patchDraft({ octalMode: `${specialOctalDigit()}${value}` });
}
</script>

<template>
  <Teleport to="body">
    <div v-if="dialog.visible" class="modal-backdrop terminal-file-properties-backdrop" @click.self="emit('close')">
      <section class="terminal-file-properties-modal" role="dialog" aria-modal="true">
        <header class="terminal-file-properties-head">
          <span class="terminal-file-properties-icon" :class="dialog.properties?.type || dialog.entry?.type">
            <AppIcon :name="(dialog.properties?.type || dialog.entry?.type) === 'directory' ? 'folder' : 'file'" :size="18" />
          </span>
          <h2>{{ dialog.entry?.name || dialog.properties?.name || '文件' }} 的属性</h2>
          <button class="terminal-file-properties-close" type="button" aria-label="关闭" :disabled="dialog.saving" @click="emit('close')">
            <AppIcon name="x" :size="16" />
          </button>
        </header>

        <div v-if="dialog.loading" class="terminal-file-properties-empty">属性读取中...</div>
        <div v-else-if="dialog.properties" class="terminal-file-properties-body">
          <p v-if="dialog.error" class="terminal-file-properties-error">{{ dialog.error }}</p>

          <section class="terminal-file-properties-section">
            <h3>常规</h3>
            <dl class="terminal-file-properties-details">
              <dt>类型：</dt><dd>{{ propertiesTypeLabel(dialog.properties) }}</dd>
              <dt>位置：</dt><dd>{{ dialog.properties.directory }}</dd>
              <dt>大小：</dt><dd>{{ formatPropertiesSize(dialog.properties) }}</dd>
              <dt>修改时间：</dt><dd>{{ dialog.properties.modifiedAt }}</dd>
              <dt>访问时间：</dt><dd>{{ dialog.properties.accessedAt }}</dd>
              <dt>所有者：</dt><dd>{{ ownerLabel(dialog.properties) }} [{{ dialog.properties.uid }}]</dd>
              <dt>组：</dt><dd>{{ groupLabel(dialog.properties) }} [{{ dialog.properties.gid }}]</dd>
            </dl>
          </section>

          <section class="terminal-file-properties-section">
            <h3>所有权</h3>
            <label class="terminal-file-properties-field">
              <span>所有者：</span>
              <input :value="dialog.draft.owner" type="text" :disabled="dialog.saving" @input="onDraftInput('owner', $event)" />
            </label>
            <label class="terminal-file-properties-field">
              <span>组：</span>
              <input :value="dialog.draft.group" type="text" :disabled="dialog.saving" @input="onDraftInput('group', $event)" />
            </label>
          </section>

          <section class="terminal-file-properties-section">
            <h3>权限</h3>
            <table class="terminal-file-permission-table">
              <thead><tr><th></th><th>R</th><th>W</th><th>X</th><th>特殊</th></tr></thead>
              <tbody>
                <tr>
                  <th>用户</th>
                  <td><input type="checkbox" :checked="isPermissionChecked(0o400)" :disabled="dialog.saving" @change="setPermission(0o400, $event)" /></td>
                  <td><input type="checkbox" :checked="isPermissionChecked(0o200)" :disabled="dialog.saving" @change="setPermission(0o200, $event)" /></td>
                  <td><input type="checkbox" :checked="isPermissionChecked(0o100)" :disabled="dialog.saving" @change="setPermission(0o100, $event)" /></td>
                  <td><label><input type="checkbox" :checked="isPermissionChecked(0o4000)" :disabled="dialog.saving" @change="setPermission(0o4000, $event)" /> UID</label></td>
                </tr>
                <tr>
                  <th>组</th>
                  <td><input type="checkbox" :checked="isPermissionChecked(0o040)" :disabled="dialog.saving" @change="setPermission(0o040, $event)" /></td>
                  <td><input type="checkbox" :checked="isPermissionChecked(0o020)" :disabled="dialog.saving" @change="setPermission(0o020, $event)" /></td>
                  <td><input type="checkbox" :checked="isPermissionChecked(0o010)" :disabled="dialog.saving" @change="setPermission(0o010, $event)" /></td>
                  <td><label><input type="checkbox" :checked="isPermissionChecked(0o2000)" :disabled="dialog.saving" @change="setPermission(0o2000, $event)" /> GID</label></td>
                </tr>
                <tr>
                  <th>其他</th>
                  <td><input type="checkbox" :checked="isPermissionChecked(0o004)" :disabled="dialog.saving" @change="setPermission(0o004, $event)" /></td>
                  <td><input type="checkbox" :checked="isPermissionChecked(0o002)" :disabled="dialog.saving" @change="setPermission(0o002, $event)" /></td>
                  <td><input type="checkbox" :checked="isPermissionChecked(0o001)" :disabled="dialog.saving" @change="setPermission(0o001, $event)" /></td>
                  <td><label><input type="checkbox" :checked="isPermissionChecked(0o1000)" :disabled="dialog.saving" @change="setPermission(0o1000, $event)" /> 粘性</label></td>
                </tr>
              </tbody>
            </table>
            <label class="terminal-file-octal-field">
              <span>八进制：</span>
              <em>{{ specialOctalDigit() }}</em>
              <input
                :value="standardOctalMode()"
                type="text"
                inputmode="numeric"
                maxlength="3"
                :disabled="dialog.saving"
                @input="updateOctalMode"
              />
            </label>
            <label v-if="dialog.properties.type === 'directory'" class="terminal-file-recursive-field">
              <input type="checkbox" :checked="dialog.recursive" :disabled="dialog.saving" @change="onRecursiveChange" />
              <span>应用到此目录及所有子目录/文件</span>
            </label>
          </section>
        </div>
        <div v-else class="terminal-file-properties-empty error">{{ dialog.error || '属性读取失败' }}</div>

        <footer class="terminal-file-properties-actions">
          <button type="button" :disabled="dialog.saving" @click="emit('close')">取消</button>
          <button class="primary" type="button" :disabled="dialog.loading || dialog.saving || !dialog.properties" @click="emit('save')">
            {{ dialog.saving ? '保存中...' : '保存' }}
          </button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>
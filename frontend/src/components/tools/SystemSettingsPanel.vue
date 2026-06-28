<script setup lang="ts">
import { computed } from 'vue';

import { useAppContext } from '../../appContext';
import { watermarkPageGroups } from '../../composables/features/useWatermarkSettings';
import WatermarkOverlay from '../common/WatermarkOverlay.vue';
import AppIcon from '../common/AppIcon.vue';

const {
  watermarkDraft,
  watermarkLoading,
  watermarkSaving,
  watermarkMessage,
  loadWatermarkSetting,
  saveWatermarkSetting,
  resetWatermarkDraft,
} = useAppContext();

const selectedPages = computed(() => new Set(watermarkDraft.value.pages));
const allPageKeys = computed(() => watermarkPageGroups.flatMap((group) => group.pages.map((page) => page.key)));

function toggleWatermarkPage(page: string) {
  const next = new Set(watermarkDraft.value.pages);
  if (next.has(page)) {
    next.delete(page);
  } else {
    next.add(page);
  }
  watermarkDraft.value.pages = [...next];
}

function toggleAllWatermarkPages() {
  watermarkDraft.value.pages = watermarkDraft.value.pages.length === allPageKeys.value.length ? [] : [...allPageKeys.value];
}
</script>

<template>
  <section class="system-settings-page">
    <article class="system-settings-main">
      <header class="system-settings-title">
        <div>
          <h2>水印设置</h2>
          <p>开启后，会在指定页面显示固定文本水印。</p>
        </div>
        <div class="system-settings-actions">
          <button type="button" :disabled="watermarkLoading" @click="loadWatermarkSetting"><AppIcon name="refresh" :size="15" />刷新</button>
          <button type="button" :disabled="watermarkSaving" @click="resetWatermarkDraft">还原</button>
          <button class="primary" type="button" :disabled="watermarkSaving" @click="saveWatermarkSetting">
            {{ watermarkSaving ? '保存中...' : '保存' }}
          </button>
        </div>
      </header>

      <p v-if="watermarkMessage" class="system-settings-message">{{ watermarkMessage }}</p>

      <div class="watermark-form-grid">
        <label class="watermark-switch-row">
          <span>水印功能</span>
          <button
            type="button"
            :class="['watermark-switch', { active: watermarkDraft.enabled }]"
            :aria-pressed="watermarkDraft.enabled"
            @click="watermarkDraft.enabled = !watermarkDraft.enabled"
          >
            <i></i>
          </button>
          <strong>{{ watermarkDraft.enabled ? '已开启' : '已关闭' }}</strong>
        </label>

        <label class="watermark-text-row">
          <span>水印文本</span>
          <input v-model="watermarkDraft.text" type="text" placeholder="请输入固定水印文本" />
        </label>

        <section class="watermark-page-picker">
          <header>
            <div>
              <strong>应用页面</strong>
              <span>已选择 {{ watermarkDraft.pages.length }} 个页面</span>
            </div>
            <button type="button" @click="toggleAllWatermarkPages">
              {{ watermarkDraft.pages.length === allPageKeys.length ? '清空选择' : '全选页面' }}
            </button>
          </header>
          <div class="watermark-page-groups">
            <article v-for="group in watermarkPageGroups" :key="group.key" class="watermark-page-group">
              <h3>{{ group.label }}</h3>
              <button
                v-for="page in group.pages"
                :key="page.key"
                type="button"
                :class="{ active: selectedPages.has(page.key) }"
                @click="toggleWatermarkPage(page.key)"
              >
                <AppIcon :name="selectedPages.has(page.key) ? 'check' : 'circleHelp'" :size="15" />
                {{ page.label }}
              </button>
            </article>
          </div>
        </section>
      </div>
    </article>

    <article class="watermark-preview-panel">
      <header>
        <h2>预览</h2>
        <span>{{ watermarkDraft.enabled ? '开启后效果' : '当前已关闭' }}</span>
      </header>
      <div class="watermark-preview-box">
        <div class="watermark-preview-content">
          <strong>CAPTAIN</strong>
          <span>系统页面</span>
          <p>水印不会阻挡按钮、表格或终端输入。</p>
        </div>
        <WatermarkOverlay v-if="watermarkDraft.enabled" :text="watermarkDraft.text" />
      </div>
    </article>
  </section>
</template>

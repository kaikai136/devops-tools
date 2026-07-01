<script setup lang="ts">
import { computed, ref } from 'vue';

import { useAppContext } from '../../appContext';
import { buildReadmeTypingSvgUrl, buildTemplateVariables, renderTemplate } from '../../composables/features/useSiteSettings';
import { watermarkPageGroups } from '../../composables/features/useWatermarkSettings';
import AppIcon from '../common/AppIcon.vue';
import WatermarkOverlay from '../common/WatermarkOverlay.vue';

type SettingsTabKey = 'identity' | 'dashboard' | 'login' | 'footer' | 'watermark';
type SettingsTabIcon = 'bookmark' | 'dashboard' | 'monitor' | 'rows' | 'image';

const {
  siteIdentityDraft,
  dashboardHeroDraft,
  layoutFooterDraft,
  loginContentDraft,
  siteSettingsLoading,
  siteSettingsSaving,
  siteSettingsMessage,
  loadSiteIdentitySetting,
  loadDashboardHeroSetting,
  loadLayoutFooterSetting,
  loadLoginContentSetting,
  saveSiteIdentitySetting,
  saveDashboardHeroSetting,
  saveLayoutFooterSetting,
  saveLoginContentSetting,
  resetSiteIdentityDraft,
  resetDashboardHeroDraft,
  resetLayoutFooterDraft,
  resetLoginContentDraft,
  watermarkDraft,
  watermarkPreviewText,
  watermarkLoading,
  watermarkSaving,
  watermarkMessage,
  loadWatermarkSetting,
  saveWatermarkSetting,
  resetWatermarkDraft,
  currentUser,
  localIp,
  canUsePageAction,
  canUseAnyPageAction,
} = useAppContext();

const settingsTabs: Array<{ key: SettingsTabKey; label: string; title: string; subtitle: string; icon: SettingsTabIcon }> = [
  { key: 'identity', label: '品牌变量', title: '品牌变量', subtitle: '名称、Logo、图标与 2FA 发行方', icon: 'bookmark' },
  { key: 'dashboard', label: '仪表盘', title: '仪表盘动态文字', subtitle: 'Hero 文案、样式与打字动画', icon: 'dashboard' },
  { key: 'login', label: '登录页', title: '登录页文案', subtitle: '欢迎标题、徽标和版权模板', icon: 'monitor' },
  { key: 'footer', label: '页脚', title: '页脚配置', subtitle: '工作台底部文案、链接与样式', icon: 'rows' },
  { key: 'watermark', label: '水印', title: '水印配置', subtitle: '水印模板与应用页面', icon: 'image' },
];

const activeTab = ref<SettingsTabKey>('identity');
const canSave = computed(() => canUsePageAction('systemSettings', 'save'));
const currentTab = computed(() => settingsTabs.find((tab) => tab.key === activeTab.value) ?? settingsTabs[0]);
const currentBusy = computed(() => (activeTab.value === 'watermark' ? watermarkSaving.value : siteSettingsSaving.value));
const currentLoading = computed(() => (activeTab.value === 'watermark' ? watermarkLoading.value : siteSettingsLoading.value));
const currentMessage = computed(() => (activeTab.value === 'watermark' ? watermarkMessage.value : siteSettingsMessage.value));
const selectedPages = computed(() => new Set(watermarkDraft.value.pages));
const allPageKeys = computed(() => watermarkPageGroups.flatMap((group) => group.pages.map((page) => page.key)));
const previewVariables = computed(() =>
  buildTemplateVariables({
    siteIdentity: siteIdentityDraft.value,
    user: currentUser.value,
    localIp: localIp.value,
    generatedAt: '2026-07-01 12:00',
  }),
);
const previewHeroBadge = computed(() => renderTemplate(dashboardHeroDraft.value.badgeTemplate, previewVariables.value));
const previewHeroLines = computed(() =>
  [dashboardHeroDraft.value.line1Template, dashboardHeroDraft.value.line2Template]
    .map((template) => renderTemplate(template, previewVariables.value))
    .filter(Boolean),
);
const previewHeroSvgUrl = computed(() => buildReadmeTypingSvgUrl(dashboardHeroDraft.value, previewHeroLines.value));
const previewDescription = computed(() => renderTemplate(dashboardHeroDraft.value.descriptionTemplate, previewVariables.value));
const previewFooterText = computed(() => renderTemplate(layoutFooterDraft.value.textTemplate, previewVariables.value));
const previewFooterLink = computed(() => renderTemplate(layoutFooterDraft.value.linkText, previewVariables.value));
const previewLoginBadge = computed(() => renderTemplate(loginContentDraft.value.badgeTemplate, previewVariables.value));
const previewLoginTitle = computed(() => renderTemplate(loginContentDraft.value.title, previewVariables.value));
const previewLoginDescription = computed(() => renderTemplate(loginContentDraft.value.description, previewVariables.value));
const previewLoginCopyright = computed(() => renderTemplate(loginContentDraft.value.copyrightTemplate, previewVariables.value));

async function refreshCurrentTab() {
  if (currentLoading.value) return;
  if (activeTab.value === 'identity') await loadSiteIdentitySetting();
  else if (activeTab.value === 'dashboard') await loadDashboardHeroSetting();
  else if (activeTab.value === 'login') await loadLoginContentSetting();
  else if (activeTab.value === 'footer') await loadLayoutFooterSetting();
  else await loadWatermarkSetting();
}

async function saveCurrentTab() {
  if (!canSave.value || currentBusy.value) return;
  if (activeTab.value === 'identity') await saveSiteIdentitySetting();
  else if (activeTab.value === 'dashboard') await saveDashboardHeroSetting();
  else if (activeTab.value === 'login') await saveLoginContentSetting();
  else if (activeTab.value === 'footer') await saveLayoutFooterSetting();
  else await saveWatermarkSetting();
}

function resetCurrentTab() {
  if (activeTab.value === 'identity') resetSiteIdentityDraft();
  else if (activeTab.value === 'dashboard') resetDashboardHeroDraft();
  else if (activeTab.value === 'login') resetLoginContentDraft();
  else if (activeTab.value === 'footer') resetLayoutFooterDraft();
  else resetWatermarkDraft();
}

function toggleWatermarkPage(page: string) {
  if (!canSave.value) return;
  const next = new Set(watermarkDraft.value.pages);
  if (next.has(page)) {
    next.delete(page);
  } else {
    next.add(page);
  }
  watermarkDraft.value.pages = [...next];
}

function toggleAllWatermarkPages() {
  if (!canSave.value) return;
  watermarkDraft.value.pages = watermarkDraft.value.pages.length === allPageKeys.value.length ? [] : [...allPageKeys.value];
}
</script>

<template>
  <section class="system-settings-page">
    <template v-if="canUseAnyPageAction('systemSettings', ['save', 'reset', 'refresh'])">
      <article class="system-settings-main">
        <header class="system-settings-title">
          <div>
            <h2>界面变量配置</h2>
            <p>{{ currentTab.subtitle }}</p>
          </div>
          <div class="system-settings-actions">
            <button v-if="canUsePageAction('systemSettings', 'refresh')" type="button" :disabled="currentLoading" @click="refreshCurrentTab">
              <AppIcon name="refresh" :size="15" />刷新
            </button>
            <button v-if="canUsePageAction('systemSettings', 'reset')" type="button" :disabled="currentBusy" @click="resetCurrentTab">
              <AppIcon name="reset" :size="15" />还原
            </button>
            <button v-if="canSave" class="primary" type="button" :disabled="currentBusy" @click="saveCurrentTab">
              {{ currentBusy ? '保存中...' : '保存当前' }}
            </button>
          </div>
        </header>

        <nav class="system-settings-tabs" aria-label="系统设置分类">
          <button
            v-for="tab in settingsTabs"
            :key="tab.key"
            type="button"
            :class="{ active: activeTab === tab.key }"
            @click="activeTab = tab.key"
          >
            <AppIcon :name="tab.icon" :size="16" />
            <span>{{ tab.label }}</span>
          </button>
        </nav>

        <p v-if="currentMessage" class="system-settings-message">{{ currentMessage }}</p>

        <section v-if="activeTab === 'identity'" class="settings-section single">
          <header>
            <h3>品牌变量</h3>
            <span>全局品牌与 2FA 发行方</span>
          </header>
          <div class="settings-field-grid">
            <label>
              <span>应用名称</span>
              <input v-model="siteIdentityDraft.appName" :disabled="!canSave" maxlength="80" />
            </label>
            <label>
              <span>短名称</span>
              <input v-model="siteIdentityDraft.appShortName" :disabled="!canSave" maxlength="32" />
            </label>
            <label>
              <span>副标题</span>
              <input v-model="siteIdentityDraft.appSubtitle" :disabled="!canSave" maxlength="80" />
            </label>
            <label>
              <span>浏览器标题</span>
              <input v-model="siteIdentityDraft.browserTitle" :disabled="!canSave" maxlength="80" />
            </label>
            <label>
              <span>Logo 文本</span>
              <input v-model="siteIdentityDraft.logoText" :disabled="!canSave" maxlength="32" />
            </label>
            <label>
              <span>2FA 发行方</span>
              <input v-model="siteIdentityDraft.totpIssuer" :disabled="!canSave" maxlength="80" />
            </label>
            <label class="span-2">
              <span>Logo 图片地址</span>
              <input v-model="siteIdentityDraft.logoImageUrl" :disabled="!canSave" maxlength="500" />
            </label>
            <label class="span-2">
              <span>默认图标地址</span>
              <input v-model="siteIdentityDraft.iconUrl" :disabled="!canSave" maxlength="500" />
            </label>
          </div>
        </section>

        <section v-else-if="activeTab === 'dashboard'" class="settings-section single">
          <header>
            <h3>仪表盘动态文字</h3>
            <span>动态 SVG 参数</span>
          </header>
          <div class="settings-field-grid">
            <label>
              <span>徽标模板</span>
              <input v-model="dashboardHeroDraft.badgeTemplate" :disabled="!canSave" maxlength="160" />
            </label>
            <label>
              <span>第一行动画</span>
              <input v-model="dashboardHeroDraft.line1Template" :disabled="!canSave" maxlength="160" />
            </label>
            <label>
              <span>第二行动画</span>
              <input v-model="dashboardHeroDraft.line2Template" :disabled="!canSave" maxlength="160" />
            </label>
            <label class="span-2">
              <span>说明文案</span>
              <textarea v-model="dashboardHeroDraft.descriptionTemplate" :disabled="!canSave" maxlength="260"></textarea>
            </label>
            <label>
              <span>字体</span>
              <input v-model="dashboardHeroDraft.font" :disabled="!canSave" maxlength="80" />
            </label>
            <label>
              <span>字号</span>
              <input v-model.number="dashboardHeroDraft.fontSize" :disabled="!canSave" type="number" min="16" max="36" />
            </label>
            <label>
              <span>字体加粗</span>
              <select v-model.number="dashboardHeroDraft.fontWeight" :disabled="!canSave">
                <option :value="400">常规 400</option>
                <option :value="500">中等 500</option>
                <option :value="600">半粗 600</option>
                <option :value="700">加粗 700</option>
                <option :value="800">特粗 800</option>
                <option :value="900">最粗 900</option>
              </select>
            </label>
            <label>
              <span>字间距</span>
              <input v-model="dashboardHeroDraft.letterSpacing" :disabled="!canSave" maxlength="40" />
            </label>
            <label>
              <span>每行持续时间 ms</span>
              <input v-model.number="dashboardHeroDraft.durationMs" :disabled="!canSave" type="number" min="100" max="30000" />
            </label>
            <label>
              <span>停顿时间 ms</span>
              <input v-model.number="dashboardHeroDraft.pauseMs" :disabled="!canSave" type="number" min="0" max="10000" />
            </label>
            <label>
              <span>文字颜色</span>
              <input v-model="dashboardHeroDraft.color" :disabled="!canSave" type="color" />
            </label>
            <label>
              <span>背景颜色</span>
              <input v-model="dashboardHeroDraft.backgroundColor" :disabled="!canSave" maxlength="9" placeholder="#00000000" />
            </label>
            <label class="settings-check-row">
              <input v-model="dashboardHeroDraft.centered" :disabled="!canSave" type="checkbox" />
              <span>水平居中</span>
            </label>
            <label class="settings-check-row">
              <input v-model="dashboardHeroDraft.verticalCentered" :disabled="!canSave" type="checkbox" />
              <span>垂直居中</span>
            </label>
            <label class="settings-check-row">
              <input v-model="dashboardHeroDraft.multiline" :disabled="!canSave" type="checkbox" />
              <span>多行显示</span>
            </label>
            <label class="settings-check-row">
              <input v-model="dashboardHeroDraft.repeat" :disabled="!canSave" type="checkbox" />
              <span>循环播放</span>
            </label>
            <label class="settings-check-row">
              <input v-model="dashboardHeroDraft.random" :disabled="!canSave" type="checkbox" />
              <span>随机顺序</span>
            </label>
            <label>
              <span>宽度</span>
              <input v-model.number="dashboardHeroDraft.width" :disabled="!canSave" type="number" min="160" max="1600" />
            </label>
            <label>
              <span>高度</span>
              <input v-model.number="dashboardHeroDraft.height" :disabled="!canSave" type="number" min="30" max="420" />
            </label>
          </div>
        </section>

        <section v-else-if="activeTab === 'login'" class="settings-section single">
          <header>
            <h3>登录页文案</h3>
            <span>未登录页面展示内容</span>
          </header>
          <div class="settings-field-grid">
            <label>
              <span>徽标模板</span>
              <input v-model="loginContentDraft.badgeTemplate" :disabled="!canSave" maxlength="160" />
            </label>
            <label>
              <span>标题</span>
              <input v-model="loginContentDraft.title" :disabled="!canSave" maxlength="80" />
            </label>
            <label class="span-2">
              <span>说明文案</span>
              <textarea v-model="loginContentDraft.description" :disabled="!canSave" maxlength="260"></textarea>
            </label>
            <label class="span-2">
              <span>版权模板</span>
              <input v-model="loginContentDraft.copyrightTemplate" :disabled="!canSave" maxlength="160" />
            </label>
          </div>
        </section>

        <section v-else-if="activeTab === 'footer'" class="settings-section single">
          <header>
            <h3>页脚配置</h3>
            <span>底部文案、链接与显示样式</span>
          </header>
          <div class="settings-field-grid">
            <label class="settings-check-row">
              <input v-model="layoutFooterDraft.enabled" :disabled="!canSave" type="checkbox" />
              <span>显示页脚</span>
            </label>
            <label>
              <span>字号</span>
              <input v-model.number="layoutFooterDraft.fontSize" :disabled="!canSave" type="number" min="10" max="18" />
            </label>
            <label>
              <span>颜色</span>
              <input v-model="layoutFooterDraft.color" :disabled="!canSave" type="color" />
            </label>
            <label class="span-2">
              <span>页脚模板</span>
              <input v-model="layoutFooterDraft.textTemplate" :disabled="!canSave" maxlength="220" />
            </label>
            <label>
              <span>链接文字</span>
              <input v-model="layoutFooterDraft.linkText" :disabled="!canSave" maxlength="80" />
            </label>
            <label>
              <span>链接地址</span>
              <input v-model="layoutFooterDraft.linkUrl" :disabled="!canSave" maxlength="500" />
            </label>
          </div>
        </section>

        <section v-else class="settings-section single">
          <header>
            <h3>水印配置</h3>
            <span>水印模板与应用范围</span>
          </header>
          <div class="watermark-form-grid">
            <div class="settings-field-grid">
              <label class="settings-check-row">
                <input v-model="watermarkDraft.enabled" :disabled="!canSave" type="checkbox" />
                <span>开启水印</span>
              </label>
              <label>
                <span>水印模板</span>
                <input v-model="watermarkDraft.text" :disabled="!canSave" maxlength="160" />
              </label>
            </div>

            <section class="watermark-page-picker">
              <header>
                <div>
                  <strong>应用页面</strong>
                  <span>已选择 {{ watermarkDraft.pages.length }} 个页面</span>
                </div>
                <button v-if="canSave" type="button" @click="toggleAllWatermarkPages">
                  {{ watermarkDraft.pages.length === allPageKeys.length ? '清空选择' : '全选页面' }}
                </button>
              </header>
              <div class="watermark-page-groups">
                <article v-for="group in watermarkPageGroups" :key="group.key" class="watermark-page-group">
                  <h3>{{ group.label }}</h3>
                  <template v-if="canSave">
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
                  </template>
                  <template v-else>
                    <span
                      v-for="page in group.pages"
                      :key="page.key"
                      class="watermark-readonly-page"
                      :class="{ active: selectedPages.has(page.key) }"
                    >
                      <AppIcon :name="selectedPages.has(page.key) ? 'check' : 'circleHelp'" :size="15" />
                      {{ page.label }}
                    </span>
                  </template>
                </article>
              </div>
            </section>
          </div>
        </section>
      </article>

      <article class="settings-preview-panel">
        <header>
          <h2>{{ currentTab.title }}</h2>
          <span>{{ currentTab.label }}</span>
        </header>
        <div class="settings-preview-body">
          <template v-if="activeTab === 'identity'">
            <section class="settings-preview-brand">
              <img :src="siteIdentityDraft.iconUrl" :alt="siteIdentityDraft.appName" />
              <div>
                <strong>{{ siteIdentityDraft.appName }}</strong>
                <span>{{ siteIdentityDraft.appSubtitle }}</span>
              </div>
            </section>
            <section class="settings-preview-meta">
              <span>浏览器标题</span>
              <strong>{{ siteIdentityDraft.browserTitle }}</strong>
              <span>2FA 发行方</span>
              <strong>{{ siteIdentityDraft.totpIssuer }}</strong>
            </section>
          </template>

          <template v-else-if="activeTab === 'dashboard'">
            <section class="settings-preview-hero">
              <span>{{ previewHeroBadge }}</span>
              <img class="settings-preview-typing-svg" :src="previewHeroSvgUrl" :alt="previewHeroLines.join(' / ')" />
              <p>{{ previewDescription }}</p>
            </section>
          </template>

          <template v-else-if="activeTab === 'login'">
            <section class="settings-preview-login">
              <span>{{ previewLoginBadge }}</span>
              <strong>{{ previewLoginTitle }}</strong>
              <p>{{ previewLoginDescription }}</p>
              <em>{{ previewLoginCopyright }}</em>
            </section>
          </template>

          <template v-else-if="activeTab === 'footer'">
            <section class="settings-preview-footer" :style="{ color: layoutFooterDraft.color, fontSize: `${layoutFooterDraft.fontSize}px` }">
              <span>{{ previewFooterText }}</span>
              <a v-if="layoutFooterDraft.linkText && layoutFooterDraft.linkUrl">{{ previewFooterLink }}</a>
            </section>
          </template>

          <template v-else>
            <section class="watermark-preview-box">
              <div class="watermark-preview-content">
                <strong>{{ siteIdentityDraft.appShortName }}</strong>
                <span>系统页面</span>
                <p>{{ watermarkPreviewText }}</p>
              </div>
              <WatermarkOverlay v-if="watermarkDraft.enabled" :text="watermarkPreviewText" />
            </section>
          </template>
        </div>
      </article>
    </template>
    <div v-else class="permission-empty">暂无可用功能</div>
  </section>
</template>

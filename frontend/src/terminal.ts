import { createApp } from 'vue';

import WatermarkOverlay from './components/common/WatermarkOverlay.vue';
import WebTerminalPage from './components/terminal/WebTerminalPage.vue';
import { buildTemplateVariables, normalizeSiteIdentity, renderTemplate, SITE_IDENTITY_SETTING_KEY } from './composables/features/useSiteSettings';
import { normalizeWatermarkConfig, watermarkAppliesToPage, WATERMARK_SETTING_KEY } from './composables/features/useWatermarkSettings';
import { getCurrentUser } from './services/auth';
import { getSystemSetting, getSystemSettingOrNull } from './services/system';
import './styles/terminal.css';

createApp(WebTerminalPage).mount('#terminal-app');

void mountTerminalWatermark();

async function mountTerminalWatermark() {
  try {
    const [setting, session] = await Promise.all([
      getSystemSetting(WATERMARK_SETTING_KEY),
      getCurrentUser(),
    ]);
    const siteSetting = await getSystemSettingOrNull(SITE_IDENTITY_SETTING_KEY);
    const siteIdentity = normalizeSiteIdentity(siteSetting?.value);
    const config = normalizeWatermarkConfig(setting.value);
    if (!watermarkAppliesToPage(config, 'webTerminal')) return;
    const target = document.createElement('div');
    target.id = 'terminal-watermark-app';
    document.body.appendChild(target);
    createApp(WatermarkOverlay, {
      text: renderTemplate(config.text, buildTemplateVariables({ siteIdentity, user: session.user })),
      variant: 'terminal',
    }).mount(target);
  } catch {
    // Watermark is optional for the standalone terminal entry.
  }
}

import { createApp } from 'vue';

import WatermarkOverlay from './components/common/WatermarkOverlay.vue';
import WebTerminalPage from './components/terminal/WebTerminalPage.vue';
import { normalizeWatermarkConfig, watermarkAppliesToPage, WATERMARK_SETTING_KEY } from './composables/features/useWatermarkSettings';
import { apiGet } from './api';
import type { AccountUser, SystemSetting } from './types';
import './styles/terminal.css';

createApp(WebTerminalPage).mount('#terminal-app');

void mountTerminalWatermark();

async function mountTerminalWatermark() {
  try {
    const [setting, session] = await Promise.all([
      apiGet<SystemSetting>(`/api/system/settings/${WATERMARK_SETTING_KEY}/`),
      apiGet<{ user: AccountUser }>('/api/auth/me/'),
    ]);
    const config = normalizeWatermarkConfig(setting.value, session.user.username);
    if (!watermarkAppliesToPage(config, 'webTerminal')) return;
    const target = document.createElement('div');
    target.id = 'terminal-watermark-app';
    document.body.appendChild(target);
    createApp(WatermarkOverlay, { text: config.text, variant: 'terminal' }).mount(target);
  } catch {
    // Watermark is optional for the standalone terminal entry.
  }
}

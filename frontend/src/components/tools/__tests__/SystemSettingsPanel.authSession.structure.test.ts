import { parse as parseSfc } from '@vue/compiler-sfc';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

function panelSource() {
  return readFileSync(fileURLToPath(new URL('../SystemSettingsPanel.vue', import.meta.url)), 'utf8');
}

describe('SystemSettingsPanel merged system settings structure', () => {
  it('merges identity, login, footer, and auth session into one system tab', () => {
    const descriptor = parseSfc(panelSource(), { filename: 'SystemSettingsPanel.vue' }).descriptor;
    const script = descriptor.scriptSetup?.content ?? '';
    const template = descriptor.template?.content ?? '';

    expect(script).toContain("type SettingsTabKey = 'system'");
    expect(script).toContain("{ key: 'system', label: '系统设置'");
    expect(script).not.toContain("{ key: 'identity', label:");
    expect(script).not.toContain("{ key: 'login', label:");
    expect(script).not.toContain("{ key: 'footer', label:");
    expect(template).toContain("activeTab === 'system'");
    expect(template).toContain('品牌信息');
    expect(template).toContain('登录页');
    expect(template).toContain('页脚');
    expect(template).toContain('登录会话');
  });

  it('adds an editable duration value and unit backed by auth_session minutes', () => {
    const descriptor = parseSfc(panelSource(), { filename: 'SystemSettingsPanel.vue' }).descriptor;
    const script = descriptor.scriptSetup?.content ?? '';
    const template = descriptor.template?.content ?? '';

    expect(script).toContain("const AUTH_SESSION_SETTING_KEY = 'auth_session'");
    expect(script).toContain('loginExpiryValue');
    expect(script).toContain('loginExpiryUnit');
    expect(script).toContain('loginExpiryInputMax');
    expect(script).toContain('loginExpiryMinutes');
    expect(template).toContain('系统登录过期时间');
    expect(template).toContain('v-model.number="loginExpiryValue"');
    expect(template).toContain(':max="loginExpiryInputMax"');
    expect(template).toContain('v-model="loginExpiryUnit"');
    expect(template).toContain('<option value="minutes">分钟</option>');
    expect(template).toContain('<option value="hours">小时</option>');
    expect(template).toContain('<option value="days">天</option>');
  });
});

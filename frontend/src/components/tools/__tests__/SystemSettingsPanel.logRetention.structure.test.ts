import { parse as parseSfc } from '@vue/compiler-sfc';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

function panelSource() {
  return readFileSync(fileURLToPath(new URL('../SystemSettingsPanel.vue', import.meta.url)), 'utf8');
}

describe('SystemSettingsPanel log retention structure', () => {
  it('moves RDP recording controls into the log retention tab', () => {
    const source = panelSource();
    const descriptor = parseSfc(source, { filename: 'SystemSettingsPanel.vue' }).descriptor;
    const script = descriptor.scriptSetup?.content ?? '';
    const template = descriptor.template?.content ?? '';

    expect(script).toContain("'logRetention'");
    expect(script).toContain("const LOG_RETENTION_SETTING_KEY = 'log_retention'");
    expect(script).not.toContain("'rdp'");
    expect(script).not.toContain("const RDP_RECORDING_SETTING_KEY = 'rdp_recording'");

    expect(template).toContain("activeTab === 'logRetention'");
    expect(template).toContain('loginLogsDays');
    expect(template).toContain('operationLogsDays');
    expect(template).toContain('terminalCommandAuditDays');
    expect(template).toContain('terminalFileAuditDays');
    expect(template).toContain('terminalSessionDays');
    expect(template).toContain('rdpRecordingDays');
    expect(template).toContain('rdpRecordingEnabled');
    expect(template).not.toContain("activeTab === 'rdp'");
  });

  it('saves log retention with all retention fields and the RDP recording switch', () => {
    const script = parseSfc(panelSource(), { filename: 'SystemSettingsPanel.vue' }).descriptor.scriptSetup?.content ?? '';
    const saveBlock = script.match(/async function saveLogRetentionSetting\(\)[\s\S]*?function resetLogRetentionDraft/)?.[0] ?? '';

    expect(saveBlock).toContain('LOG_RETENTION_SETTING_KEY');
    expect(saveBlock).toContain('loginLogsDays');
    expect(saveBlock).toContain('operationLogsDays');
    expect(saveBlock).toContain('terminalCommandAuditDays');
    expect(saveBlock).toContain('terminalFileAuditDays');
    expect(saveBlock).toContain('terminalSessionDays');
    expect(saveBlock).toContain('rdpRecordingEnabled');
    expect(saveBlock).toContain('rdpRecordingDays');
  });
});

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

function template(relativePath: string) {
  return readFileSync(join(process.cwd(), relativePath), 'utf8');
}

describe('popup visual structure', () => {
  it('keeps priority popups on the shared shell structure', () => {
    expect(template('src/features/hosts/components/HostEditorDialog.vue')).toContain('popup-body');
    expect(template('src/features/hosts/components/HostManager.vue')).toContain('popup-header');
    expect(template('src/features/hosts/components/HostExportDialog.vue')).toContain('popup-footer');
    expect(template('src/features/terminal/components/files/FileCreateDialog.vue')).toContain('popup-body');
  });

  it('keeps management popups on the shared shell structure', () => {
    expect(template('src/features/bulk-execution/components/BulkExecutionPanel.vue')).toContain('popup-body');
    expect(template('src/features/application-market/components/ApplicationMarketPanel.vue')).toContain('popup-footer');
    expect(template('src/App.vue')).toContain('popup-body');
    expect(template('src/components/tools/SecurityScanPanel.vue')).toContain('popup-form-grid');
  });

  it('keeps secondary management dialogs from bypassing the shared popup system', () => {
    for (const relativePath of [
      'src/components/tools/AccountManager.vue',
      'src/components/tools/RoleManager.vue',
      'src/components/tools/SessionAuditManager.vue',
      'src/features/company/components/DeviceManager.vue',
      'src/features/application-market/components/ApplicationMarketPanel.vue',
    ]) {
      const source = template(relativePath);
      expect(source, relativePath).toContain('popup-body');
      expect(source, relativePath).toContain('popup-actions');
    }
  });

  it('keeps terminal file and command overlays on the shared shell structure', () => {
    for (const relativePath of [
      'src/features/terminal/components/files/FilePropertiesDialog.vue',
      'src/features/terminal/components/files/SftpPanel.vue',
      'src/components/terminal/WebTerminalPage.vue',
    ]) {
      const source = template(relativePath);
      expect(source, relativePath).toContain('popup-body');
      expect(source, relativePath).toContain('popup-actions');
    }
  });
});

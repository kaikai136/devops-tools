import { parse as parseSfc } from '@vue/compiler-sfc';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

function panelSource() {
  return readFileSync(fileURLToPath(new URL('../AccountManager.vue', import.meta.url)), 'utf8');
}

describe('AccountManager Element Plus migration', () => {
  it('replaces the native table, dialog, and controls with Element Plus components', () => {
    const template = parseSfc(panelSource(), { filename: 'AccountManager.vue' }).descriptor.template?.content ?? '';

    expect(template).toContain('<el-table');
    expect(template).toContain('<el-table-column');
    expect(template).toContain('<el-tag');
    expect(template).toContain('<el-dialog');
    expect(template).toContain('<el-form');
    expect(template).toContain('<el-form-item');
    expect(template).toContain('<el-button');
    expect(template).toContain('<el-input');
    expect(template).toContain('<el-upload');

    expect(template).not.toContain('<table');
    expect(template).not.toContain('<input');
    expect(template).not.toContain('<select');
    expect(template).not.toContain('<option');
    expect(template).not.toContain('<textarea');
    expect(template).not.toContain('modal-backdrop');
  });

  it('drives the private key upload through el-upload raw file', () => {
    const script = parseSfc(panelSource(), { filename: 'AccountManager.vue' }).descriptor.scriptSetup?.content ?? '';

    expect(script).toContain('function uploadPrivateKey(uploadFile: { raw?: File })');
    expect(script).not.toContain('uploadPrivateKey(event: Event)');
  });
});

import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(__dirname, '..');
const readSource = (relativePath: string) => readFileSync(resolve(root, relativePath), 'utf8');

describe('native UI foundation', () => {
  it('provides the shared primitives used by the migrated screens', () => {
    expect(existsSync(resolve(root, 'shared/ui/native/index.ts'))).toBe(true);
    const index = readSource('shared/ui/native/index.ts');
    expect(index).toContain('NativeDialog');
    expect(index).toContain('NativePagination');
    expect(index).toContain('NativeConfirmDialog');
    expect(index).not.toContain('element-plus');
  });

  it('keeps shared styles independent from Element Plus', () => {
    const styles = readSource('styles/base/native-ui.css');
    expect(styles).toContain('.native-dialog');
    expect(styles).toContain('.native-input');
    expect(styles).not.toContain('.el-');
  });

  it('provides the native component contracts used by migrated pages', () => {
    const index = readSource('shared/ui/native/index.ts');
    const compat = readSource('shared/ui/native/NativeCompat.ts');

    expect(index).toContain('NativeButtonGroup');
    expect(compat).toContain("name: 'NativeButtonGroup'");
    expect(compat).toContain('get input()');
  });
});

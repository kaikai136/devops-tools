import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

function readSource(relativePath: string) {
  return readFileSync(fileURLToPath(new URL(`../${relativePath}`, import.meta.url)), 'utf8');
}

function readProjectFile(relativePath: string) {
  return readFileSync(fileURLToPath(new URL(`../../${relativePath}`, import.meta.url)), 'utf8');
}

describe('app shell upgrade contract', () => {
  it('wires Element Plus as the only UI component library', () => {
    const main = readSource('main.ts');
    const packageJson = readProjectFile('package.json');

    expect(packageJson).toContain('"element-plus"');
    expect(packageJson).not.toContain('"ant-design-vue"');
    expect(main).toContain("import 'element-plus/dist/index.css';");
    expect(main).toContain('app.use(ElementPlus)');
    expect(main).not.toContain('ant-design-vue');
    expect(main).not.toContain('app.use(Antd)');
  });

  it('renders the logged-in shell with Element Plus navigation and quick actions', () => {
    const app = readSource('App.vue');
    const styles = readSource('styles/base/workspace-header.css');
    const navStyles = readSource('styles/base/shell-nav.css');

    expect(app).toContain('<el-menu');
    expect(app).toContain('<el-sub-menu');
    expect(app).toContain('<el-breadcrumb');
    expect(app).toContain('<el-dropdown');
    expect(app).toContain('<el-tooltip');
    expect(app).toContain('<el-button');
    expect(app).not.toContain('<a-float-button');
    expect(navStyles).toContain('.el-menu');
    expect(navStyles).toContain('.workspace-float-actions');
  });

  it('includes a live date and time display at the bottom of the sidebar', () => {
    const app = readSource('App.vue');
    const navStyles = readSource('styles/base/shell-nav.css');

    expect(app).toContain('sidebar-clock');
    expect(app).toContain('sidebar-clock-date');
    expect(app).toContain('sidebar-clock-time');
    expect(app).toContain('onMounted');
    expect(app).toContain('onUnmounted');
    expect(navStyles).toContain('.sidebar-clock');
    expect(navStyles).toContain('flex-direction: column');
    expect(navStyles).toContain('.sidebar-nav');
  });
});

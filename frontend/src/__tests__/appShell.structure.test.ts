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
    const navigation = readSource('shared/components/WorkspaceNavigation.vue');
    const styles = readSource('styles/base/workspace-header.css');
    const navStyles = readSource('styles/base/shell-nav.css');

    expect(app).toContain('<WorkspaceNavigation');
    expect(navigation).toContain('<el-menu');
    expect(navigation).toContain('<el-sub-menu');
    expect(app).toContain('<el-breadcrumb');
    expect(app).toContain('<el-dropdown');
    expect(app).toContain('<el-tooltip');
    expect(app).toContain('<el-button');
    expect(app).not.toContain('<a-float-button');
    expect(styles).toContain('.workspace-topbar');
    expect(navStyles).toContain('.el-menu');
    expect(navStyles).toContain('.workspace-float-actions');
  });

  it('uses a drawer navigation below the shell mobile breakpoint', () => {
    const app = readSource('App.vue');
    const responsive = readSource('styles/responsive.css');

    expect(app).toContain('mobileNavigationOpen');
    expect(app).toContain('<el-drawer');
    expect(app).toContain(':close-on-click-modal="false"');
    expect(app).toContain("window.matchMedia('(max-width: 899px)')");
    expect(app).toContain('@click="handleNavigationToggle"');
    expect(responsive).toContain('@media (max-width: 899px)');
    expect(responsive).toContain('.desktop-sidebar');
    expect(responsive).toContain('display: none');
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

  it('uses larger bold typography for the sidebar navigation labels', () => {
    const navStyles = readSource('styles/base/shell-nav.css');
    const menuRule = navStyles.match(/\.workspace-nav-menu :is\(\.el-menu-item, \.el-sub-menu__title\) \{[\s\S]*?\n\}/)?.[0] ?? '';

    expect(menuRule).toContain('font-size: 16px');
    expect(menuRule).toContain('font-weight: 900');
    expect(menuRule).toContain('height: 44px');
  });
});

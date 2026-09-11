import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

function readSource(relativePath: string) {
  return readFileSync(fileURLToPath(new URL(`../${relativePath}`, import.meta.url)), 'utf8');
}

describe('UI foundation contract', () => {
  it('uses Tailwind v4 through the Vite plugin without Preflight', () => {
    const packageJson = readSource('../package.json');
    const viteConfig = readSource('../vite.config.ts');
    const tailwind = readSource('styles/tailwind.css');

    expect(packageJson).toContain('"tailwindcss"');
    expect(packageJson).toContain('"@tailwindcss/vite"');
    expect(viteConfig).toContain("import tailwindcss from '@tailwindcss/vite';");
    expect(viteConfig).toContain('plugins: [vue(), tailwindcss()]');
    expect(tailwind).toContain('prefix(tw)');
    expect(tailwind).toContain('tailwindcss/utilities.css');
    expect(tailwind).not.toContain('tailwindcss/preflight.css');
  });

  it('keeps app tokens as the color and theme source of truth', () => {
    const tokens = readSource('styles/tokens.css');
    const elementTheme = readSource('styles/base/element-plus-theme.css');
    const popupTheme = readSource('styles/base/popup-system.css');

    expect(tokens).toContain('--app-primary: #2563eb');
    expect(tokens).toContain('html.dark');
    expect(tokens).toContain('--app-page-gutter');
    expect(elementTheme).toContain('--el-color-primary: var(--app-primary)');
    expect(elementTheme).toContain('--el-bg-color: var(--app-surface)');
    expect(popupTheme).toContain('--popup-primary: var(--app-primary)');
  });

  it('loads tokens and Tailwind in every frontend entry', () => {
    const appStyles = readSource('styles.css');
    const terminal = readSource('terminal.ts');
    const hostTerminal = readSource('host-terminal.ts');

    for (const source of [appStyles, terminal, hostTerminal]) {
      expect(source).toContain('styles/tokens.css');
      expect(source).toContain('styles/tailwind.css');
    }
  });

  it('keeps phase 6B admin responsiveness in Vue instead of page-level CSS patches', () => {
    const user = readSource('components/tools/UserManager.vue');
    const role = readSource('components/tools/RoleManager.vue');
    const account = readSource('components/tools/AccountManager.vue');
    const loginLog = readSource('components/tools/LoginLogManager.vue');
    const userStyles = readSource('styles/tools/user-manager.css');
    const roleStyles = readSource('styles/tools/role-manager.css');
    const loginLogStyles = readSource('styles/tools/login-log-manager.css');
    const responsive = readSource('styles/responsive.css');

    expect(user).toContain('user-manager-page tw:flex');
    expect(user).toContain('tw:min-[921px]:flex-row');
    expect(role).toContain('role-manager-page tw:flex');
    expect(role).toContain('tw:min-[901px]:min-w-[980px]');
    expect(account).toContain('account-toolbar tw:mb-4 tw:flex tw:flex-col');
    expect(loginLog).toContain('login-log-page tw:grid');
    expect(loginLog).toContain('tw:min-[901px]:flex-row');
    expect(userStyles).not.toContain('@media');
    expect(roleStyles).not.toContain('@media');
    expect(loginLogStyles.match(/@media[\s\S]*$/)?.[0] ?? '').not.toMatch(/\n\s*\.login-log-(?:filter-panel|toolbar|actions)\s*\{/);
    expect(responsive).not.toContain('.account-page.fullscreen,');
  });

  it('keeps phase 6C complex pages responsive without global page lists', () => {
    const operationLog = readSource('components/tools/OperationLogManager.vue');
    const systemSettings = readSource('components/tools/SystemSettingsPanel.vue');
    const profile = readSource('components/tools/ProfileCenter.vue');
    const dashboard = readSource('components/tools/DashboardPage.vue');
    const loginLogStyles = readSource('styles/tools/login-log-manager.css');
    const systemStyles = readSource('styles/tools/system-settings.css');
    const profileStyles = readSource('styles/tools/profile-center.css');
    const dashboardStyles = readSource('styles/tools/dashboard.css');
    const darkMode = readSource('styles/dark-mode.css');

    expect(operationLog).toContain('operation-log-page tw:grid');
    expect(operationLog).toContain('tw:min-[901px]:grid-cols-5');
    expect(loginLogStyles).not.toContain('@media');
    expect(systemSettings).toContain('system-settings-page tw:grid');
    expect(systemSettings).toContain('tw:min-[981px]:grid-cols-[minmax(0,1160px)]');
    expect(systemSettings).toContain('tw:min-[981px]:grid-cols-4');
    expect(systemStyles).not.toContain('@media (max-width: 980px)');
    expect(profile).toContain('profile-center-page tw:grid');
    expect(profile).toContain('profile-form-grid tw:grid tw:grid-cols-1');
    expect(profileStyles.match(/@media[\s\S]*$/)?.[0] ?? '').not.toContain('.profile-center-page');
    expect(dashboard).toContain('dashboard-card-grid tw:grid tw:grid-cols-1');
    expect(dashboard).toContain('tw:min-[1461px]:grid-cols-[minmax(320px,1.35fr)_repeat(4,minmax(170px,1fr))]');
    expect(dashboardStyles).not.toContain('@media (max-width: 1460px)');
    expect(dashboardStyles).not.toContain('@media (max-width: 1280px)');
    expect(dashboardStyles).not.toContain('.workspace-dark');
    expect(profileStyles.match(/\.workspace-dark/g) ?? []).toHaveLength(2);
    expect(darkMode).not.toContain('.profile-center-page,');
    expect(darkMode).not.toContain('.system-settings-page,');
    expect(darkMode).not.toContain('.system-settings-main,');
    expect(darkMode).not.toContain('.profile-primary-button');
  });

  it('syncs the workspace theme to html.dark for teleported UI', () => {
    const shellState = readSource('composables/app/useShellState.ts');

    expect(shellState).toContain("document.documentElement.classList.toggle('dark', theme === 'dark')");
  });
});

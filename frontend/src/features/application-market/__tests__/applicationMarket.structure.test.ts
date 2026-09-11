import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

function readSource(relativePath: string) {
  return readFileSync(fileURLToPath(new URL(`../../../${relativePath}`, import.meta.url)), 'utf8');
}

describe('application market frontend contract', () => {
  it('registers applicationMarket as an independent navigation module and app shell page', () => {
    const types = readSource('types.ts');
    const navigation = readSource('app/navigation.ts');
    const shell = readSource('composables/app/useShellState.ts');
    const app = readSource('App.vue');
    const styles = readSource('styles.css');

    expect(types).toContain("| 'applicationMarket'");
    expect(navigation).toContain("key: 'market' as const");
    expect(navigation).toContain("key: 'applicationMarket' as const");
    expect(shell).toContain('market: true');
    expect(shell).toMatch(/applicationMarket:\s*'(server|dashboard|settings|globe)'/);
    expect(app).toContain('ApplicationMarketPanel');
    expect(app).toContain("<ApplicationMarketPanel v-if=\"activeTool === 'applicationMarket'\" />");
    expect(styles).toContain('@import "./styles/tools/application-market.css";');
  });

  it('exposes typed API helpers for catalog, targets, previews, tasks, and sources', () => {
    const api = readSource('features/application-market/api/applicationMarket.ts');
    const types = readSource('features/application-market/types.ts');

    expect(types).toContain('ApplicationMarketApp');
    expect(types).toContain('ApplicationMarketTarget');
    expect(types).toContain('ApplicationMarketTask');
    expect(types).toContain('ApplicationMarketSource');
    expect(api).toContain('/api/application-market');
    expect(api).toContain('listApplicationMarketCatalog');
    expect(api).toContain('getApplicationMarketApp');
    expect(api).toContain('listApplicationMarketTargets');
    expect(api).toContain('previewApplicationMarketAction');
    expect(api).toContain('createApplicationMarketTask');
    expect(api).toContain('cancelApplicationMarketTask');
    expect(api).toContain('syncApplicationMarketSources');
  });

  it('renders filters, target selector, dynamic config, confirmation, and task polling', () => {
    const panel = readSource('features/application-market/components/ApplicationMarketPanel.vue');

    expect(panel).toContain('application-market-page');
    expect(panel).toContain('app-market');
    expect(panel).toContain('market-hero');
    expect(panel).toContain('market-stats');
    expect(panel).toContain('market-toolbar');
    expect(panel).toContain('market-segment');
    expect(panel).toContain('market-categories');
    expect(panel).toContain('app-grid');
    expect(panel).toContain('app-card');
    expect(panel).toContain('app-job-banner');
    expect(panel).toContain('install-more-card');
    expect(panel).toContain('targetSelector');
    expect(panel).toContain('capabilityStrip');
    expect(panel).toContain('searchKeyword');
    expect(panel).toContain('categoryFilter');
    expect(panel).toContain('sourceFilter');
    expect(panel).toContain('installStatusFilter');
    expect(panel).toContain('selectedApp');
    expect(panel).toContain('configSchema');
    expect(panel).toContain('previewPlan');
    expect(panel).toContain('planDigest');
    expect(panel).toContain('confirmInstallModal');
    expect(panel).toContain('requestConfirm');
    expect(panel).toContain('setInterval');
    expect(panel).toContain('2000');
    expect(panel).toContain("canUsePageAction('applicationMarket', 'install')");
    expect(panel).toContain("canUsePageAction('applicationMarket', 'manage_sources')");
  });

  it('uses Tailwind utilities for page layout and app tokens for feature styling', () => {
    const panel = readSource('features/application-market/components/ApplicationMarketPanel.vue');
    const styles = readSource('styles/tools/application-market.css');

    expect(panel).toContain('application-market-page app-market tw:flex');
    expect(panel).toContain('market-toolbar tw:grid tw:grid-cols-1');
    expect(panel).toContain('tw:xl:grid-cols-[minmax(240px,1fr)_auto_auto]');
    expect(panel).toContain('market-app-grid tw:grid tw:grid-cols-1');
    expect(panel).toContain('tw:md:grid-cols-2 tw:xl:grid-cols-3 tw:2xl:grid-cols-4');
    expect(panel).toContain('market-config-form tw:grid tw:grid-cols-1');
    expect(panel).toContain('tw:md:grid-cols-2');
    expect(panel).toContain('market-preview-grid popup-body tw:grid tw:grid-cols-1');
    expect(panel).toContain('app-control-panel__status tw:grid tw:grid-cols-1 tw:lg:grid-cols-3');

    expect(styles).toContain('--market-accent: var(--app-primary);');
    expect(styles).toContain('--market-success: var(--app-success);');
    expect(styles).toContain('border-color: var(--app-focus);');
    expect(styles).toContain('background: var(--app-code-surface);');
    expect(styles).not.toContain('@media');
    expect(styles).not.toContain('.workspace-dark');
    expect(styles).not.toMatch(/#[0-9a-f]{3,8}\b/i);
  });
});

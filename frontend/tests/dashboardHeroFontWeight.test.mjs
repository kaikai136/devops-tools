import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const settings = readFileSync(new URL('../src/composables/features/useSiteSettings.ts', import.meta.url), 'utf8');
const panel = readFileSync(new URL('../src/components/tools/SystemSettingsPanel.vue', import.meta.url), 'utf8');
const styles = readFileSync(new URL('../src/styles/tools/system-settings.css', import.meta.url), 'utf8');

const dashboardSection = panel.match(/<section v-else-if="activeTab === 'dashboard'"[\s\S]*?<section v-else-if="activeTab === 'login'"/)?.[0] ?? '';

test('dashboard hero font weights match Chinese fonts supported by the typing SVG service', () => {
  assert.match(settings, /fontWeight:\s*900,/);
  assert.match(settings, /fontWeightChoices\s*=\s*new Set\(\[400,\s*500,\s*600,\s*700,\s*800,\s*900\]\)/);
  assert.match(settings, /cleanInt\(value,\s*fallback,\s*400,\s*900\)/);

  assert.match(panel, /<option :value="700">/);
  assert.match(panel, /<option :value="800">/);
  assert.match(panel, /<option :value="900">/);
});

test('dashboard hero form uses four columns and select controls for font choices', () => {
  assert.match(settings, /export const dashboardHeroFontOptions = \[/);
  assert.match(settings, /export const dashboardHeroLetterSpacingOptions = \[/);
  assert.match(settings, /font:\s*'Noto Sans SC'/);
  assert.match(settings, /'Noto Sans SC'/);
  assert.match(settings, /'Noto Serif SC'/);
  assert.doesNotMatch(settings, /'Poppins'/);
  assert.doesNotMatch(settings, /'Fira Code'/);

  assert.match(dashboardSection, /class="settings-field-grid dashboard-hero-field-grid"/);
  assert.match(dashboardSection, /<select v-model="dashboardHeroDraft\.font"/);
  assert.match(dashboardSection, /v-for="font in dashboardHeroFontOptions"/);
  assert.match(dashboardSection, /<select v-model="dashboardHeroDraft\.letterSpacing"/);
  assert.match(dashboardSection, /v-for="spacing in dashboardHeroLetterSpacingOptions"/);
  assert.doesNotMatch(dashboardSection, /<input v-model="dashboardHeroDraft\.font"/);
  assert.doesNotMatch(dashboardSection, /<input v-model="dashboardHeroDraft\.letterSpacing"/);

  assert.match(styles, /\.dashboard-hero-field-grid\s*\{[^}]*grid-template-columns:\s*repeat\(4,\s*minmax\(0,\s*1fr\)\);/s);
  assert.match(styles, /\.dashboard-hero-field-grid label\.span-4\s*\{[^}]*grid-column:\s*1\s*\/\s*-1;/s);
});

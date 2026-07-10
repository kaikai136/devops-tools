import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const source = readFileSync(new URL('../src/components/tools/SecurityScanPanel.vue', import.meta.url), 'utf8');
const styles = readFileSync(new URL('../src/styles/tools/security-scan.css', import.meta.url), 'utf8');

test('security scan panel exposes four Excel-style report sections', () => {
  for (const sectionTitle of ['综述', '资产风险统计', '漏洞影响统计', '漏洞详情']) {
    assert.match(source, new RegExp(sectionTitle));
  }
});

test('places risk filtering controls above report sections', () => {
  const toolbarIndex = source.indexOf('class="security-scan-filters finding-toolbar"');
  const overviewSectionIndex = source.indexOf('v-if="activeReportTab === \'overview\'"');
  const impactSectionIndex = source.indexOf('v-else-if="activeReportTab === \'impact\'"');

  assert.notEqual(toolbarIndex, -1);
  assert.ok(toolbarIndex < overviewSectionIndex);
  assert.ok(toolbarIndex < impactSectionIndex);
});

test('keeps task and risk filters in one compact toolbar row', () => {
  assert.equal(source.match(/class="security-scan-filters/g)?.length, 1);
});

test('toolbar uses a fitted grid without horizontal scrolling', () => {
  const toolbarRule = styles.slice(styles.indexOf('.security-scan-filters.finding-toolbar'), styles.indexOf('.security-scan-filters label'));

  assert.match(toolbarRule, /display:\s*grid/);
  assert.match(toolbarRule, /grid-template-columns/);
  assert.doesNotMatch(toolbarRule, /overflow-x:\s*auto/);
});

test('renders report sections as a horizontal tab list', () => {
  assert.match(source, /class="report-tabs"/);
  assert.match(source, /v-for="tab in reportTabs"/);
  assert.match(source, /activeReportTab === tab\.key/);
});

test('allows report tabs to scroll horizontally', () => {
  const tabsRule = styles.slice(styles.indexOf('.report-tabs'), styles.indexOf('.report-tabs button'));

  assert.match(tabsRule, /display:\s*flex/);
  assert.match(tabsRule, /overflow-x:\s*auto/);
  assert.match(tabsRule, /flex-wrap:\s*nowrap/);
});

test('shows scrollbars for wide report tables', () => {
  const tableScrollRule = styles.slice(styles.indexOf('.report-table-scroll'), styles.indexOf('.report-table {'));

  assert.match(tableScrollRule, /overflow-x:\s*scroll/);
  assert.match(tableScrollRule, /overflow-y:\s*auto/);
  assert.match(tableScrollRule, /max-height/);
});

test('keeps finding detail table wider than the viewport so horizontal scrolling is available', () => {
  const findingTableRule = styles.slice(styles.indexOf('.finding-detail-table'), styles.indexOf('.report-text-cell'));

  assert.match(findingTableRule, /width:\s*2200px/);
  assert.match(findingTableRule, /min-width:\s*2200px/);
});

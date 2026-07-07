import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const composable = readFileSync(new URL('../src/composables/features/useHostManager.ts', import.meta.url), 'utf8');
const appState = readFileSync(new URL('../src/composables/useAppState.ts', import.meta.url), 'utf8');
const component = readFileSync(new URL('../src/components/tools/HostManager.vue', import.meta.url), 'utf8');
const styles = readFileSync(new URL('../src/styles/tools/host/layout-groups.css', import.meta.url), 'utf8');

test('shows inline validation messages below invalid host form fields', () => {
  assert.match(composable, /hostFormErrors/);
  assert.match(composable, /function validateHostForm\(\)/);
  assert.match(composable, /function isSelectableHostOs\(/);
  assert.match(composable, /watch\(\s*hostForm/);
  assert.match(composable, /请输入主机 IP/);
  assert.match(composable, /请输入正确的主机 IP/);
  assert.match(composable, /端口范围为 1-65535/);

  assert.match(appState, /\bhostFormErrors\b/);
  assert.match(component, /hostFormErrors\.privateIp/);
  assert.match(component, /<option disabled value="">请选择平台类型<\/option>/);
  assert.match(component, /class="host-field-error"/);
  assert.match(component, /:class="\{ invalid: hostFormErrors\.privateIp \}"/);

  assert.match(styles, /\.host-form-modal input\.invalid/);
  assert.match(styles, /#ff4058/);
});

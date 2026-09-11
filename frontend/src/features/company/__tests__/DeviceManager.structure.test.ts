import { NodeTypes, parse as parseTemplate } from '@vue/compiler-dom';
import { parse as parseSfc } from '@vue/compiler-sfc';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

function readSource(relativePath: string) {
  return readFileSync(fileURLToPath(new URL(`../../../${relativePath}`, import.meta.url)), 'utf8');
}

function readSfc(relativePath: string) {
  const parsed = parseSfc(readSource(relativePath), { filename: relativePath });
  expect(parsed.errors).toEqual([]);
  return parsed.descriptor;
}

function templateRoot(relativePath: string) {
  return parseTemplate(readSfc(relativePath).template?.content ?? '');
}

type TemplateChild = ReturnType<typeof templateRoot>['children'][number];

function findElements(root: ReturnType<typeof templateRoot>, tag: string) {
  const elements: Extract<TemplateChild, { type: NodeTypes.ELEMENT }>[] = [];
  const visit = (node: TemplateChild) => {
    if (node.type === NodeTypes.ELEMENT) {
      if (node.tag === tag) elements.push(node);
      node.children.forEach(visit);
      return;
    }
    if (node.type === NodeTypes.IF) node.branches.forEach((branch) => branch.children.forEach(visit));
    if (node.type === NodeTypes.FOR) node.children.forEach(visit);
  };
  root.children.forEach(visit);
  return elements;
}

function staticAttribute(element: ReturnType<typeof findElements>[number], name: string) {
  const attribute = element.props.find((prop) => prop.type === NodeTypes.ATTRIBUTE && prop.name === name);
  return attribute?.type === NodeTypes.ATTRIBUTE ? attribute.value?.content : undefined;
}

function hasStaticClass(element: ReturnType<typeof findElements>[number], className: string) {
  return staticAttribute(element, 'class')?.split(/\s+/).includes(className) ?? false;
}

function findByClass(root: ReturnType<typeof templateRoot>, tag: string, className: string) {
  return findElements(root, tag).filter((element) => hasStaticClass(element, className));
}

describe('DeviceManager page structure', () => {
  it('registers device asset navigation and app rendering', () => {
    const types = readSource('types.ts');
    const navigation = readSource('app/navigation.ts');
    const shell = readSource('composables/app/useShellState.ts');
    const app = readSource('App.vue');
    const styles = readSource('styles.css');

    expect(types).toContain("| 'companyDevices'");
    expect(navigation).toContain("key: 'company' as const");
    expect(navigation).toContain("label: '设备管理'");
    expect(navigation).toContain("{ key: 'companyDevices' as const, label: '设备资产'");
    expect(navigation).not.toContain("label: '公司管理'");
    expect(navigation).not.toContain("{ key: 'companyDevices' as const, label: '设备管理'");
    expect(shell).toContain("companyDevices: 'laptop'");
    expect(shell).toContain("company: 'monitor'");
    expect(shell).not.toContain("companyDevices: 'hardDrive'");
    expect(shell).not.toContain("company: 'users'");
    expect(app).toContain("const DeviceManager = defineAsyncComponent(() => import('./features/company/components/DeviceManager.vue'))");
    expect(app).toContain("<DeviceManager v-if=\"activeTool === 'companyDevices'\" />");
    expect(styles).toContain('@import "./styles/tools/device-manager.css";');
  });

  it('renders persisted device management controls, permissions, and editor fields', () => {
    const root = templateRoot('features/company/components/DeviceManager.vue');
    const source = readSource('features/company/components/DeviceManager.vue');

    expect(findByClass(root, 'section', 'device-manager-page')).toHaveLength(1);
    expect(source).toContain('listCompanyDevices');
    expect(source).toContain('createCompanyDevice');
    expect(source).toContain('updateCompanyDevice');
    expect(source).toContain('deleteCompanyDevice');
    expect(source).toContain('buildCompanyDeviceXlsxWorkbook');
    expect(source).toContain("canUsePageAction('companyDevices', 'create')");
    expect(source).toContain("canUsePageAction('companyDevices', 'edit')");
    expect(source).toContain("canUsePageAction('companyDevices', 'delete')");
    expect(source).toContain("canUsePageAction('companyDevices', 'export')");
    expect(source).toContain("canUsePageAction('companyDevices', 'filter')");
    expect(source).toContain('删除');
    expect(source).toContain('添加');
    expect(source).toContain('导出Excel');
    expect(source).toContain('编辑');
    expect(source).not.toContain('复制');
    expect(source).not.toContain('设置标签');
    expect(source).not.toContain('查看');
    for (const header of ['序号', '资产名称', '资产类别', '资产编码', '规格说明', '资产状态', '使用人员', '品牌名称', '采购时间', '备注', '操作']) {
      expect(source).toContain(`label="${header}"`);
    }
    for (const label of ['资产名称', '资产类别', '资产编码', '规格说明', '资产状态', '使用人员', '品牌名称', '采购时间', '备注']) {
      expect(source).toContain(`label="${label}"`);
    }
    expect(findByClass(root, 'el-form', 'device-form-modal')).toHaveLength(1);
    for (const removedHeader of ['使用部门', '供应商', '采购订单编号', '合同编号', '标签', '添加时间']) {
      expect(source).not.toContain(`<th>${removedHeader}</th>`);
    }
  });

  it('renders closed category and status option sets for filters and form', () => {
    const source = readSource('features/company/components/DeviceManager.vue');

    expect(source).toContain('<el-select v-model="categoryFilter" class="device-toolbar-select tw:');
    expect(source).toContain('placeholder="资产状态" clearable');
    expect(source).toContain('placeholder="资产类别" clearable');
    expect(source).toContain('<el-select v-model="deviceForm.category">');
    expect(source).not.toContain('list="device-category-options"');
    expect(source).not.toContain('<datalist id="device-category-options">');
    expect(source).toContain('<el-option value="固定资产" label="固定资产" />');
    expect(source).toContain('<el-option value="耗材" label="耗材" />');
    expect(source).toContain('<el-option value="using" label="使用中" />');
    expect(source).toContain('<el-option value="idle" label="闲置" />');
    expect(source).toContain('<el-option value="repair" label="维修" />');
    expect(source).toContain('<el-option value="scrapped" label="报废" />');
  });

  it('closes the device dialog after a successful save without being blocked by saving state', () => {
    const source = readSource('features/company/components/DeviceManager.vue');

    expect(source).toContain('function finishDeviceDialog()');
    expect(source).toMatch(/showToast\('保存成功'[\s\S]*?finishDeviceDialog\(\);/);
    expect(source).not.toMatch(/showToast\('保存成功'[\s\S]*?closeDeviceDialog\(\);/);
    expect(source).toContain('if (isSaving.value) return;');
  });

  it('places device toolbar controls in the former title position without rendering the title', () => {
    const source = readSource('features/company/components/DeviceManager.vue');
    const styles = readSource('styles/tools/device-manager.css');

    expect(source).not.toContain('<h2><AppIcon name="hardDrive" :size="18" />资产列表</h2>');
    expect(source).not.toContain('<h2><AppIcon name="hardDrive" :size="18" />璧勪骇鍒楄〃</h2>');
    expect(source).toContain('class="device-list-toolbar tw:grid');
    expect(source).toContain('tw:min-[1181px]:grid-cols-[minmax(0,1fr)_auto]');
    expect(source).toContain('class="device-toolbar-filters tw:flex');
    expect(source).toContain('tw:flex-wrap tw:items-center tw:justify-start');
    expect(source).toContain('class="device-toolbar-actions tw:flex');
    expect(source).toContain('tw:min-[1181px]:justify-end');
    expect(source).toContain('tw:min-[1181px]:h-[calc(100dvh-104px)]');
    expect(source).toContain('class="device-table-wrap tw:min-h-0 tw:flex-1');
    expect(styles).not.toContain('@media');
  });

  it('keeps device toolbar controls responsive with Element Plus control sizing', () => {
    const styles = readSource('styles/tools/device-manager.css');
    const source = readSource('features/company/components/DeviceManager.vue');

    expect(source).not.toContain('>查询</button>');
    expect(source).toContain('height="100%"');
    expect(source).toContain('border');
    expect(source).toContain('stripe');
    expect(source).toContain('highlight-current-row');
    expect(source).toContain('tw:md:flex-nowrap');
    expect(source).toContain('tw:md:w-[136px]');
    expect(source).toContain('tw:md:flex-[0_0_136px]');
    expect(source).toContain('tw:md:w-[260px]');
    expect(source).toContain('tw:md:min-w-[220px]');
    expect(source).toContain('tw:md:flex-[0_1_260px]');
    expect(styles).toMatch(/\.device-toolbar-filters \.el-select__wrapper,[\s\S]*\.device-toolbar-actions \.el-button\s*\{[^}]*min-height:\s*36px;/s);
    expect(styles).toMatch(/\.device-toolbar-actions \.el-button\s*\{[^}]*min-width:\s*82px;/s);
    expect(styles).toMatch(/\.device-row-actions \.el-button \+ \.el-button\s*\{[^}]*margin-left:\s*0;/s);
  });

  it('renders host-style pagination with category counts on the right', () => {
    const source = readSource('features/company/components/DeviceManager.vue');
    const styles = readSource('styles/tools/device-manager.css');

    expect(source).toContain('const pageSize = ref(10);');
    expect(source).toContain('const pageStart = computed(() => (filteredDevices.value.length ? (page.value - 1) * pageSize.value + 1 : 0));');
    expect(source).toContain('const pageEnd = computed(() => Math.min(page.value * pageSize.value, filteredDevices.value.length));');
    expect(source).toContain("const fixedAssetCount = computed(() => filteredDevices.value.filter((device) => device.category === '固定资产').length);");
    expect(source).toContain("const consumableCount = computed(() => filteredDevices.value.filter((device) => device.category === '耗材').length);");
    expect(source).toContain('class="device-pagination-left tw:flex');
    expect(source).toContain('共 {{ filteredDevices.length }} 条');
    expect(source).toContain('{{ pageStart }}-{{ pageEnd }}');
    expect(source).toContain('<el-pagination');
    expect(source).toContain(':page-sizes="[10, 20, 50]"');
    expect(source).toContain('@current-change="setPage"');
    expect(source).toContain('@size-change="setPageSize"');
    expect(source).toContain('class="device-category-summary tw:ml-auto');
    expect(source).toContain('固定资产 {{ fixedAssetCount }}');
    expect(source).toContain('耗材 {{ consumableCount }}');
    expect(source).not.toContain('共{{ totalPages }}页 {{ filteredDevices.length }}条，已选 {{ selectedDeviceCount }} 条');
    expect(source).toContain('class="device-pagination tw:flex');
    expect(source).toContain('tw:bg-app-surface-muted');
    expect(source).toContain('tw:max-[1180px]:justify-start');
    expect(styles).toMatch(/\.device-pagination \.el-pagination\s*\{[^}]*min-width:\s*0;/s);
    expect(styles).toMatch(/\.device-summary-pill\s*\{[^}]*white-space:\s*nowrap;/s);
  });

  it('uses separate category badge colors for fixed assets and consumables', () => {
    const source = readSource('features/company/components/DeviceManager.vue');
    const styles = readSource('styles/tools/device-manager.css');

    expect(source).toContain("categoryClass(row.category)");
    expect(source).toContain("function categoryClass(category: string)");
    expect(source).toContain("category === '耗材' ? 'consumable' : 'fixed'");
    expect(styles).toMatch(/\.device-category-badge\.fixed\s*\{[^}]*background:\s*var\(--app-primary\);/s);
    expect(styles).toMatch(/\.device-category-badge\.consumable\s*\{[^}]*background:\s*var\(--app-accent\);/s);
  });
});

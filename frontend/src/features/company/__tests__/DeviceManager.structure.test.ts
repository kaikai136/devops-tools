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
  it('registers company management navigation and app rendering', () => {
    const types = readSource('types.ts');
    const navigation = readSource('app/navigation.ts');
    const shell = readSource('composables/app/useShellState.ts');
    const app = readSource('App.vue');
    const styles = readSource('styles.css');

    expect(types).toContain("| 'companyDevices'");
    expect(navigation).toContain("key: 'company' as const");
    expect(navigation).toContain("label: '公司管理'");
    expect(navigation).toContain("{ key: 'companyDevices' as const, label: '设备管理'");
    expect(shell).toContain("companyDevices: 'hardDrive'");
    expect(shell).toContain("company: 'users'");
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
    expect(source).toContain('资产列表');
    expect(source).toContain('删除');
    expect(source).toContain('添加');
    expect(source).toContain('导出Excel');
    expect(source).toContain('编辑');
    expect(source).not.toContain('复制');
    expect(source).not.toContain('设置标签');
    expect(source).not.toContain('查看');
    for (const header of ['序号', '资产名称', '资产类别', '资产编码', '规格说明', '资产状态', '使用人员', '品牌名称', '采购时间', '备注', '操作']) {
      expect(source).toContain(`<th>${header}</th>`);
    }
    for (const label of ['资产名称', '资产类别', '资产编码', '规格说明', '资产状态', '使用人员', '品牌名称', '采购时间', '备注']) {
      expect(source).toContain(`<span>${label}</span>`);
    }
    expect(findByClass(root, 'form', 'device-form-modal')).toHaveLength(1);
    for (const removedHeader of ['使用部门', '供应商', '采购订单编号', '合同编号', '标签', '添加时间']) {
      expect(source).not.toContain(`<th>${removedHeader}</th>`);
    }
  });
});

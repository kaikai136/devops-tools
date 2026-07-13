import { ElementTypes, NodeTypes, parse as parseTemplate, type RootNode } from '@vue/compiler-dom';
import { parse as parseSfc } from '@vue/compiler-sfc';
import { describe, expect, it } from 'vitest';
import type { Component } from 'vue';

declare global {
  interface ImportMeta {
    glob(
      pattern: string | string[],
      options: { eager: true; import?: string; query?: string },
    ): Record<string, unknown>;
  }
}

const componentModules = import.meta.glob('../*.vue', {
  eager: true,
  import: 'default',
}) as Record<string, Component & { props?: Record<string, unknown>; emits?: string[] | Record<string, unknown> }>;

const sfcSources = import.meta.glob([
  '../*.vue',
  '../../../../components/tools/HostManager.vue',
  '../../../../App.vue',
], {
  eager: true,
  import: 'default',
  query: '?raw',
}) as Record<string, string>;


const expectedComponents = [
  'CredentialSelector.vue',
  'HostEditorDialog.vue',
  'HostExportDialog.vue',
  'HostGroupTree.vue',
  'HostImportDialog.vue',
  'HostManager.vue',
  'HostMoveDialog.vue',
  'HostTable.vue',
  'HostToolbar.vue',
];

const componentContracts: Record<string, { props: string[]; emits: string[] }> = {
  'CredentialSelector.vue': {
    props: ['credentials', 'modelValue'],
    emits: ['update:modelValue', 'change'],
  },
  'HostEditorDialog.vue': {
    props: ['dialog', 'form', 'errors', 'groups', 'credentials'],
    emits: ['close', 'submit', 'update-form-field', 'apply-credential', 'upload-private-key'],
  },
  'HostExportDialog.vue': {
    props: ['scope', 'format', 'columns', 'selectedColumns', 'allColumnsSelected', 'selectedCount'],
    emits: ['close', 'confirm', 'update:scope', 'update:format', 'toggle-column', 'toggle-all-columns'],
  },
  'HostGroupTree.vue': {
    props: ['groups', 'root', 'rows', 'rootExpanded', 'selectedGroup', 'inlineEdit', 'menu'],
    emits: ['select-group', 'toggle-root', 'toggle-group', 'open-menu', 'update-inline-name', 'save-inline-edit'],
  },
  'HostImportDialog.vue': {
    props: ['format'],
    emits: ['close', 'confirm', 'update:format'],
  },
  'HostMoveDialog.vue': {
    props: ['open', 'mode', 'form', 'hosts', 'root', 'groups', 'selectedCount'],
    emits: ['close', 'submit', 'update-form-field'],
  },
  'HostTable.vue': {
    props: ['hosts', 'visibleHostCount', 'selectedIds', 'visibleIds', 'tableStyle', 'page', 'pageSize', 'totalPages'],
    emits: ['toggle-all-visible', 'toggle-host', 'sort', 'page-change', 'page-size-change', 'clear-selection'],
  },
  'HostToolbar.vue': {
    props: ['search', 'statusFilter', 'selectedCount', 'moreActionsOpen', 'columnSettingsOpen', 'fullscreen'],
    emits: ['update:search', 'create', 'open-quick-commands', 'toggle-more-actions', 'status-filter', 'export', 'refresh'],
  },
};

function runtimePropNames(component: Component & { props?: Record<string, unknown> }) {
  return Object.keys(component.props ?? {});
}

function runtimeEmitNames(component: Component & { emits?: string[] | Record<string, unknown> }) {
  return Array.isArray(component.emits) ? component.emits : Object.keys(component.emits ?? {});
}

function readSfc(relativePath: string) {
  const sourcePath = relativePath === 'src/App.vue'
    ? '../../../../App.vue'
    : relativePath === 'src/components/tools/HostManager.vue'
      ? '../../../../components/tools/HostManager.vue'
      : '../' + relativePath.split('/').slice(-1)[0];
  const source = sfcSources[sourcePath];
  expect(source, 'Missing raw SFC source for ' + relativePath).toBeTypeOf('string');
  const parsed = parseSfc(source, { filename: relativePath });
  expect(parsed.errors).toEqual([]);
  return parsed.descriptor;
}

function findElements(root: RootNode, tag: string) {
  const elements: Extract<RootNode['children'][number], { type: NodeTypes.ELEMENT }>[] = [];
  const visit = (node: RootNode['children'][number]) => {
    if (node.type === NodeTypes.ELEMENT) {
      if (node.tag === tag) elements.push(node);
      node.children.forEach(visit);
      return;
    }
    if (node.type === NodeTypes.IF) {
      node.branches.forEach((branch) => branch.children.forEach(visit));
      return;
    }
    if (node.type === NodeTypes.FOR) node.children.forEach(visit);
  };
  root.children.forEach(visit);
  return elements;
}

function staticAttribute(
  element: ReturnType<typeof findElements>[number],
  name: string,
) {
  const attribute = element.props.find((prop) => prop.type === NodeTypes.ATTRIBUTE && prop.name === name);
  return attribute?.type === NodeTypes.ATTRIBUTE ? attribute.value?.content : undefined;
}

function firstInterpolationExpression(element: ReturnType<typeof findElements>[number]) {
  const interpolation = element.children.find((child) => child.type === NodeTypes.INTERPOLATION);
  return interpolation?.type === NodeTypes.INTERPOLATION && interpolation.content.type === NodeTypes.SIMPLE_EXPRESSION
    ? interpolation.content.content
    : undefined;
}

function directiveExpression(
  element: ReturnType<typeof findElements>[number],
  name: string,
  argument?: string,
) {
  const directive = element.props.find((prop) =>
    prop.type === NodeTypes.DIRECTIVE
      && prop.name === name
      && (argument === undefined || (prop.arg?.type === NodeTypes.SIMPLE_EXPRESSION && prop.arg.content === argument)),
  );
  return directive?.type === NodeTypes.DIRECTIVE && directive.exp?.type === NodeTypes.SIMPLE_EXPRESSION
    ? directive.exp.content
    : undefined;
}

function componentTags(root: RootNode) {
  const tags: string[] = [];
  const visit = (node: RootNode['children'][number]) => {
    if (node.type === NodeTypes.ELEMENT) {
      if (node.tagType === ElementTypes.COMPONENT) tags.push(node.tag);
      node.children.forEach(visit);
      return;
    }
    if (node.type === NodeTypes.IF) {
      node.branches.forEach((branch) => branch.children.forEach(visit));
      return;
    }
    if (node.type === NodeTypes.FOR) node.children.forEach(visit);
  };
  root.children.forEach(visit);
  return tags;
}

describe('HostManager component structure', () => {
  it('creates exactly the nine planned host component modules', () => {
    expect(Object.keys(componentModules).map((path) => path.split('/').slice(-1)[0]).sort()).toEqual(expectedComponents);
  });

  it.each(Object.entries(componentContracts))('%s exposes its typed presentation boundary at runtime', (filename, contract) => {
    const modulePath = Object.keys(componentModules).find((path) => path.split('/').slice(-1)[0] === filename);
    expect(modulePath, `${filename} must exist`).toBeTruthy();
    const component = componentModules[modulePath!];
    expect(runtimePropNames(component)).toEqual(expect.arrayContaining(contract.props));
    expect(runtimeEmitNames(component)).toEqual(expect.arrayContaining(contract.emits));
  });

  it('keeps the old tools entry as a zero-prop compatibility wrapper', () => {
    const descriptor = readSfc('src/components/tools/HostManager.vue');
    expect(descriptor.scriptSetup?.content).toContain("import HostManager from '@features/hosts/components/HostManager.vue'");
    const template = parseTemplate(descriptor.template?.content ?? '');
    expect(template.children).toHaveLength(1);
    expect(template.children[0]).toMatchObject({ type: NodeTypes.ELEMENT, tag: 'HostManager' });
  });

  it('composes host regions without moving the quick-command manager out of the facade', () => {
    const descriptor = readSfc('src/features/hosts/components/HostManager.vue');
    const tags = componentTags(parseTemplate(descriptor.template?.content ?? ''));
    expect(tags).toEqual(expect.arrayContaining([
      'HostGroupTree',
      'HostToolbar',
      'HostTable',
      'HostEditorDialog',
      'HostMoveDialog',
    ]));
    expect(descriptor.template?.content).toContain('host-quick-command-modal');
  });

  it('passes the move permission through the HostTable presentation boundary', () => {
    const descriptor = readSfc('src/features/hosts/components/HostManager.vue');
    const root = parseTemplate(descriptor.template?.content ?? '');
    const hostTable = findElements(root, 'HostTable');
    expect(hostTable).toHaveLength(1);
    expect(directiveExpression(hostTable[0], 'bind', 'can-move')).toBe("canUsePageAction('hosts', 'move')");
  });

  it('preserves the root-group add-host default argument semantics', () => {
    const descriptor = readSfc('src/features/hosts/components/HostGroupTree.vue');
    const root = parseTemplate(descriptor.template?.content ?? '');
    const addHostButton = findElements(root, 'button').find((element) =>
      directiveExpression(element, 'on', 'click')?.includes("emit('add-host'"),
    );
    expect(addHostButton).toBeTruthy();
    expect(directiveExpression(addHostButton!, 'on', 'click')).toBe("emit('add-host', props.menu.group.key ?? undefined)");
  });

  it('keeps the editor modal class contract used by the existing global styles', () => {
    const descriptor = readSfc('src/features/hosts/components/HostEditorDialog.vue');
    const forms = findElements(parseTemplate(descriptor.template?.content ?? ''), 'form');
    expect(forms).toHaveLength(1);
    expect(staticAttribute(forms[0], 'class')).toBe('host-form-modal host-edit-modal host-horizontal-modal');
  });

  it('keeps the original editor dialog title text and mode ordering', () => {
    const descriptor = readSfc('src/features/hosts/components/HostEditorDialog.vue');
    const headings = findElements(parseTemplate(descriptor.template?.content ?? ''), 'h2');
    expect(headings).toHaveLength(1);
    expect(firstInterpolationExpression(headings[0])).toBe("props.dialog.mode === 'edit' ? '编辑主机' : '新增主机'");
  });

  it('uses the dedicated credential selector inside the editor dialog', () => {
    const descriptor = readSfc('src/features/hosts/components/HostEditorDialog.vue');
    expect(componentTags(parseTemplate(descriptor.template?.content ?? ''))).toContain('CredentialSelector');
  });

  it('connects import and export dialogs from App without retaining the old inline transfer modal', () => {
    const descriptor = readSfc('src/App.vue');
    const tags = componentTags(parseTemplate(descriptor.template?.content ?? ''));
    expect(tags).toEqual(expect.arrayContaining(['HostImportDialog', 'HostExportDialog']));
    expect(descriptor.template?.content).not.toContain('class="host-transfer-modal"');
  });
});

import { ElementTypes, NodeTypes, parse as parseTemplate, type RootNode } from '@vue/compiler-dom';
import { parse as parseSfc } from '@vue/compiler-sfc';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
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

const compatibilityModules = import.meta.glob('../../../../components/tools/HostManager.vue', {
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

const plannedComponents = [
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
    props: [],
    emits: ['close', 'confirm', 'download-template'],
  },
  'HostMoveDialog.vue': {
    props: ['open', 'mode', 'form', 'hosts', 'root', 'groups', 'selectedCount'],
    emits: ['close', 'submit', 'update-form-field'],
  },
  'HostTable.vue': {
    props: ['hosts', 'visibleHostCount', 'selectedIds', 'visibleIds', 'tableStyle', 'page', 'pageSize', 'totalPages'],
    emits: ['toggle-all-visible', 'toggle-host', 'sort', 'open-simple-terminal', 'page-change', 'page-size-change', 'clear-selection', 'upload-file-selected'],
  },
  'HostToolbar.vue': {
    props: ['search', 'statusFilter', 'selectedCount', 'moreActionsOpen', 'columnSettingsOpen', 'fullscreen'],
    emits: ['update:search', 'create', 'open-quick-commands', 'toggle-more-actions', 'status-filter', 'upload-file-selected', 'import', 'export', 'refresh'],
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

function readStyle(relativePath: string) {
  const sourceUrl = relativePath === 'src/styles/tools/host/layout-groups.css'
    ? new URL('../../../../styles/tools/host/layout-groups.css', import.meta.url)
    : new URL(relativePath, import.meta.url);
  return readFileSync(fileURLToPath(sourceUrl), 'utf8');
}

function templateRoot(relativePath: string) {
  return parseTemplate(readSfc(relativePath).template?.content ?? '');
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

type TemplateElement = ReturnType<typeof findElements>[number];

function staticAttribute(element: TemplateElement, name: string) {
  const attribute = element.props.find((prop) => prop.type === NodeTypes.ATTRIBUTE && prop.name === name);
  return attribute?.type === NodeTypes.ATTRIBUTE ? attribute.value?.content : undefined;
}

function hasStaticAttribute(element: TemplateElement, name: string) {
  return element.props.some((prop) => prop.type === NodeTypes.ATTRIBUTE && prop.name === name);
}

function hasStaticClass(element: TemplateElement, className: string) {
  return staticAttribute(element, 'class')?.split(/\s+/).includes(className) ?? false;
}

function findByClass(root: RootNode, tag: string, className: string) {
  return findElements(root, tag).filter((element) => hasStaticClass(element, className));
}

function firstInterpolationExpression(element: TemplateElement) {
  const interpolation = element.children.find((child) => child.type === NodeTypes.INTERPOLATION);
  return interpolation?.type === NodeTypes.INTERPOLATION && interpolation.content.type === NodeTypes.SIMPLE_EXPRESSION
    ? interpolation.content.content
    : undefined;
}

function findDirective(
  element: TemplateElement,
  name: string,
  argument?: string,
  modifiers?: string[],
) {
  return element.props.find((prop) =>
    prop.type === NodeTypes.DIRECTIVE
      && prop.name === name
      && (prop.arg?.type === NodeTypes.SIMPLE_EXPRESSION ? prop.arg.content : undefined) === argument
      && (modifiers === undefined || prop.modifiers.map((modifier) => modifier.content).join('.') === modifiers.join('.')),
  );
}

function directiveExpression(
  element: TemplateElement,
  name: string,
  argument?: string,
  modifiers?: string[],
) {
  const directive = findDirective(element, name, argument, modifiers);
  return directive?.type === NodeTypes.DIRECTIVE && directive.exp?.type === NodeTypes.SIMPLE_EXPRESSION
    ? directive.exp.content
    : undefined;
}

function expectDirective(
  element: TemplateElement,
  name: string,
  argument: string | undefined,
  expression: string | undefined,
  modifiers: string[] = [],
) {
  const directive = findDirective(element, name, argument, modifiers);
  expect(directive, `missing v-${name}${argument ? `:${argument}` : ''} on <${element.tag}>`).toBeTruthy();
  expect(directiveExpression(element, name, argument, modifiers)).toBe(expression);
  expect(directive?.type === NodeTypes.DIRECTIVE ? directive.modifiers.map((modifier) => modifier.content) : []).toEqual(modifiers);
  return directive!;
}

function expectNoDirective(element: TemplateElement, name: string, argument?: string) {
  expect(findDirective(element, name, argument)).toBeUndefined();
}

function expectBindings(element: TemplateElement, bindings: Record<string, string>) {
  Object.entries(bindings).forEach(([argument, expression]) => {
    expectDirective(element, 'bind', argument, expression);
  });
}

function expectEvents(element: TemplateElement, events: Record<string, string>) {
  Object.entries(events).forEach(([argument, expression]) => {
    expectDirective(element, 'on', argument, expression);
  });
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
  it('keeps every planned host component in the component module set', () => {
    const actualComponents = Object.keys(componentModules).map((path) => path.split('/').slice(-1)[0]);
    expect(actualComponents).toEqual(expect.arrayContaining(plannedComponents));
  });

  it.each(Object.entries(componentContracts))('%s exposes its typed presentation boundary at runtime', (filename, contract) => {
    const modulePath = Object.keys(componentModules).find((path) => path.split('/').slice(-1)[0] === filename);
    expect(modulePath, `${filename} must exist`).toBeTruthy();
    const component = componentModules[modulePath!];
    expect(runtimePropNames(component)).toEqual(expect.arrayContaining(contract.props));
    expect(runtimeEmitNames(component)).toEqual(expect.arrayContaining(contract.emits));
  });

  it('keeps the old tools entry as a zero-prop compatibility wrapper', () => {
    const template = templateRoot('src/components/tools/HostManager.vue');
    expect(template.children).toHaveLength(1);
    expect(template.children[0]).toMatchObject({ type: NodeTypes.ELEMENT, tag: 'HostManager' });
    const wrapper = Object.values(compatibilityModules)[0];
    expect(wrapper).toBeTruthy();
    expect(runtimePropNames(wrapper)).toEqual([]);
    expect(runtimeEmitNames(wrapper)).toEqual([]);
  });

  it('uses emit-backed native v-model for search and both group-name editors', () => {
    const toolbarRoot = templateRoot('src/features/hosts/components/HostToolbar.vue');
    const searchInput = findElements(toolbarRoot, 'input').find(
      (element) => staticAttribute(element, 'placeholder') === '输入别名/IP检索',
    );
    expect(searchInput).toBeTruthy();
    expectDirective(searchInput!, 'model', undefined, 'searchModel');
    expectNoDirective(searchInput!, 'bind', 'value');
    expectNoDirective(searchInput!, 'on', 'input');

    const groupRoot = templateRoot('src/features/hosts/components/HostGroupTree.vue');
    const groupInputs = findByClass(groupRoot, 'input', 'host-group-inline-input');
    expect(groupInputs).toHaveLength(2);
    groupInputs.forEach((input) => {
      expectDirective(input, 'model', undefined, 'inlineName');
      expectNoDirective(input, 'bind', 'value');
      expectNoDirective(input, 'on', 'input');
      expect(hasStaticAttribute(input, 'autofocus')).toBe(true);
      expectDirective(input, 'on', 'blur', "emit('save-inline-edit')");
      expectDirective(input, 'on', 'keydown', "emit('save-inline-edit')", ['enter', 'prevent']);
      expectDirective(input, 'on', 'keydown', "emit('cancel-inline-edit')", ['esc', 'prevent']);
    });
    expect(staticAttribute(groupInputs[1], 'placeholder')).toBe('输入分组名称');
  });

  it('keeps HostManager child models, bindings, and handler wiring exact', () => {
    const root = templateRoot('src/features/hosts/components/HostManager.vue');
    expect(componentTags(root)).toEqual(expect.arrayContaining([
      'HostGroupTree',
      'HostToolbar',
      'HostTable',
      'HostEditorDialog',
      'HostMoveDialog',
    ]));
    expect(findByClass(root, 'article', 'host-quick-command-modal')).toHaveLength(1);

    const toolbar = findElements(root, 'HostToolbar')[0];
    expectDirective(toolbar, 'model', 'search', 'hostSearch');
    expectBindings(toolbar, {
      'status-filter': 'hostStatusFilter',
      'selected-count': 'selectedManagedHostCount',
      'selected-verifying-count': 'selectedManagedHostVerifyingCount',
      'column-visibility': 'hostColumnVisibility',
      'can-create': "canUsePageAction('hosts', 'create')",
      'can-manage-quick-commands': "canUsePageAction('hosts', 'quick_commands')",
      'can-import': "canUsePageAction('hosts', 'import')",
      'can-export': "canUsePageAction('hosts', 'export')",
    });
    expectEvents(toolbar, {
      create: 'addManagedHost()',
      'open-quick-commands': 'openHostQuickCommandManager',
      'status-filter': 'setHostStatusFilter',
      'upload-file-selected': 'openBulkFileUploadForSelectedHosts',
      'toggle-all-columns': 'toggleAllHostColumns',
      'update-column': 'updateHostColumnVisibility',
      import: "openHostTransferDialog('import')",
      export: "openHostTransferDialog('export')",
      refresh: 'loadHostManagement',
    });

    const groupTree = findElements(root, 'HostGroupTree')[0];
    expectBindings(groupTree, {
      rows: 'hostGroupRows',
      'inline-edit': 'hostGroupInlineEdit',
      menu: 'hostGroupMenu',
      'dragged-group-id': 'draggedHostGroupId',
      'drop-target': 'hostGroupDropTarget',
      'can-manage-groups': "canUsePageAction('hosts', 'group')",
      'can-create-hosts': "canUsePageAction('hosts', 'create')",
      'can-move-hosts': "canUsePageAction('hosts', 'move')",
      'can-delete-hosts': "canUsePageAction('hosts', 'delete')",
    });
    expectEvents(groupTree, {
      'select-group': 'selectManagedGroup',
      'update-inline-name': 'updateHostGroupInlineName',
      'save-inline-edit': 'saveHostGroupInlineEdit',
      'cancel-inline-edit': 'cancelHostGroupInlineEdit',
      'drag-start': 'startHostGroupDrag',
      'drag-over': 'updateHostGroupDropTarget',
      'drag-leave': 'clearHostGroupDropTarget',
      drop: 'dropHostGroup',
      'drag-end': 'finishHostGroupDrag',
      'add-host': 'addManagedHost',
      'move-host': 'openMoveHostDialog',
      'delete-hosts': 'deleteManagedHostsInGroup',
    });

    const table = findElements(root, 'HostTable')[0];
    expectBindings(table, {
      hosts: 'paginatedManagedHosts',
      'selected-ids': 'selectedManagedHostIds',
      'visible-ids': 'visibleHostIds',
      page: 'hostPage',
      'page-size': 'hostPageSize',
      'total-pages': 'hostTotalPages',
      'selected-verifying-count': 'selectedManagedHostVerifyingCount',
      'can-open-terminal': "canUsePageAction('hosts', 'terminal')",
      'can-edit': "canUsePageAction('hosts', 'edit')",
      'can-verify': "canUsePageAction('hosts', 'verify')",
      'can-move': "canUsePageAction('hosts', 'move')",
      'can-delete': "canUsePageAction('hosts', 'delete')",
    });
    expectEvents(table, {
      'toggle-all-visible': 'toggleAllVisibleHosts',
      'toggle-host': 'toggleHostSelected',
      sort: 'setHostSort',
      'open-terminal': 'openWebTerminal',
      'open-simple-terminal': 'openSimpleHostTerminal',
      edit: 'editManagedHost',
      verify: 'verifyManagedHost',
      delete: 'deleteManagedHost',
      'page-change': 'setHostPage',
      'page-size-change': 'hostPageSize = $event',
      'clear-selection': 'clearSelectedManagedHosts',
      'upload-file-selected': 'openBulkFileUploadForSelectedHosts',
    });

    const script = readSfc('src/features/hosts/components/HostManager.vue').scriptSetup?.content ?? '';
    const rowActions = script.match(/const canUseHostRowActions = computed\(\(\) =>([\s\S]*?)\);/);
    expect(rowActions?.[1]).toContain("canUsePageAction('hosts', 'terminal')");

    const editor = findElements(root, 'HostEditorDialog')[0];
    expectBindings(editor, {
      dialog: 'hostDialog',
      form: 'hostForm',
      errors: 'hostFormErrors',
      groups: 'flatHostGroups',
      credentials: 'hostCredentials',
    });
    expectEvents(editor, {
      close: 'hostDialog = null',
      submit: 'saveManagedHost',
      'update-form-field': 'updateHostFormField',
      'apply-credential': 'applyCredentialToHostForm',
      'upload-private-key': 'uploadHostPrivateKey',
    });

    const move = findElements(root, 'HostMoveDialog')[0];
    expectBindings(move, {
      open: 'hostMoveDialogOpen',
      mode: 'hostMoveMode',
      form: 'hostMoveForm',
      hosts: 'groupMoveHosts',
      groups: 'flatHostGroups',
      'selected-count': 'selectedManagedHostCount',
    });
    expectEvents(move, {
      close: 'hostMoveDialogOpen = false',
      submit: 'saveMoveManagedHost',
      'update-form-field': 'updateHostMoveFormField',
    });
  });

  it('keeps the quick command manager as a polished command library surface', () => {
    const root = templateRoot('src/features/hosts/components/HostManager.vue');

    expect(findByClass(root, 'span', 'host-quick-command-head-icon')).toHaveLength(1);
    expect(findByClass(root, 'div', 'host-quick-command-category-title')).toHaveLength(1);
    expect(findByClass(root, 'span', 'host-quick-command-count')).toHaveLength(1);
    expect(findByClass(root, 'div', 'host-quick-command-empty')).toHaveLength(1);
    expect(findByClass(root, 'span', 'host-quick-command-empty-glyph')).toHaveLength(1);
    expect(findByClass(root, 'button', 'host-quick-command-empty-action')).toHaveLength(1);
    expect(findByClass(root, 'div', 'host-quick-command-meta')).toHaveLength(1);
    expect(findByClass(root, 'span', 'host-quick-command-state')).toHaveLength(1);

    const emptyAction = findByClass(root, 'button', 'host-quick-command-empty-action')[0];
    expectDirective(emptyAction, 'on', 'click', 'openHostQuickCommandDialog()');
  });

  it('keeps the host group sidebar compact without letting long names distort the row', () => {
    const styles = readStyle('src/styles/tools/host/layout-groups.css');
    const groupTree = readSfc('src/features/hosts/components/HostGroupTree.vue').template?.content ?? '';

    expect(styles).toMatch(/\.host-manager-page\s*\{[\s\S]*grid-template-columns:\s*minmax\(200px,\s*240px\)\s*minmax\(680px,\s*1fr\);/);
    expect(styles).toMatch(/\.host-groups-panel\s*\{[\s\S]*padding:\s*14px;/);
    expect(styles).toMatch(/\.host-group-row strong\s*\{[\s\S]*min-width:\s*0;[\s\S]*overflow:\s*hidden;[\s\S]*text-overflow:\s*ellipsis;[\s\S]*white-space:\s*nowrap;/);
    expect(groupTree).toContain('`${10 + row.group.level * 8}px`');
    expect(groupTree).toContain('`${10 + row.editor.level * 8}px`');
  });

  it('labels the host navigation as asset management', () => {
    const navigationSource = readFileSync(
      fileURLToPath(new URL('../../../../app/navigation.ts', import.meta.url)),
      'utf8',
    );

    expect(navigationSource).toContain("label: '资产管理'");
    expect(navigationSource.match(/label: '资产管理'/g)).toHaveLength(2);
    expect(navigationSource).not.toContain("label: '主机管理'");
  });

  it('lets successful quick command saves close the saving dialog while blocking manual closes', () => {
    const script = readSfc('src/features/hosts/components/HostManager.vue').scriptSetup?.content ?? '';

    expect(script).toMatch(/function closeHostQuickCommandDialog\(options: \{ force\?: boolean \} = \{\}\)/);
    expect(script).toMatch(/if \(hostQuickCommandDialog\.value\.saving && !options\.force\) return;/);
    expect(script).toMatch(/closeHostQuickCommandDialog\(\{ force: true \}\)/);
  });

  it('preserves stop/self/key modifiers plus group pointer and drag payload order', () => {
    const toolbarRoot = templateRoot('src/features/hosts/components/HostToolbar.vue');
    expectDirective(findByClass(toolbarRoot, 'div', 'host-more-actions')[0], 'on', 'click', undefined, ['stop']);
    expectDirective(findByClass(toolbarRoot, 'div', 'host-column-settings')[0], 'on', 'click', undefined, ['stop']);
    expectDirective(findElements(toolbarRoot, 'button').find((button) => staticAttribute(button, 'title') === undefined
      && directiveExpression(button, 'on', 'click') === "emit('toggle-fullscreen')")!, 'on', 'click', "emit('toggle-fullscreen')", ['stop']);

    const groupRoot = templateRoot('src/features/hosts/components/HostGroupTree.vue');
    const rootRow = findByClass(groupRoot, 'button', 'host-group-root')[0];
    expectDirective(rootRow, 'on', 'click', "emit('select-group', null)", ['stop']);
    expectDirective(rootRow, 'on', 'dblclick', "emit('toggle-root')", ['stop']);
    expectDirective(rootRow, 'on', 'contextmenu', "emit('open-menu', row.group, $event)");

    const draggableRow = findElements(groupRoot, 'button').find((button) => staticAttribute(button, 'draggable') === 'true')!;
    expectDirective(draggableRow, 'on', 'click', "emit('select-group', row.group.key)", ['stop']);
    expectDirective(draggableRow, 'on', 'dblclick', "emit('toggle-group', row.group)", ['stop']);
    expectDirective(draggableRow, 'on', 'contextmenu', "emit('open-menu', row.group, $event)");
    expectEvents(draggableRow, {
      dragstart: "emit('drag-start', row.group, $event)",
      dragover: "emit('drag-over', row.group, $event)",
      dragleave: "emit('drag-leave')",
      drop: "emit('drop', row.group, $event)",
      dragend: "emit('drag-end')",
    });

    const editorBackdrop = findByClass(templateRoot('src/features/hosts/components/HostEditorDialog.vue'), 'div', 'modal-backdrop')[0];
    expectNoDirective(editorBackdrop, 'on', 'click');
    const moveBackdrop = findByClass(templateRoot('src/features/hosts/components/HostMoveDialog.vue'), 'div', 'modal-backdrop')[0];
    expectNoDirective(moveBackdrop, 'on', 'click');
  });

  it('protects HostTable checkbox payloads, pagination, column settings, and permissions', () => {
    const tableRoot = templateRoot('src/features/hosts/components/HostTable.vue');
    const checkboxes = findElements(tableRoot, 'input').filter((input) => staticAttribute(input, 'type') === 'checkbox');
    expect(checkboxes).toHaveLength(2);
    expectDirective(checkboxes[0], 'bind', 'checked', 'props.allVisibleSelected');
    expectDirective(checkboxes[0], 'bind', 'disabled', '!props.visibleIds.length');
    expectDirective(checkboxes[0], 'bind', 'indeterminate', 'props.someVisibleSelected && !props.allVisibleSelected', ['prop']);
    expectDirective(checkboxes[0], 'on', 'change', "emit('toggle-all-visible', $event)");
    expectDirective(checkboxes[1], 'bind', 'checked', 'props.selectedIds.has(host.id)');
    expectDirective(checkboxes[1], 'on', 'change', "emit('toggle-host', host.id, $event)");

    const pagination = findByClass(tableRoot, 'div', 'host-pagination-controls')[0];
    const pageButtons = findElements({ ...tableRoot, children: pagination.children } as RootNode, 'button');
    expectDirective(pageButtons[0], 'on', 'click', "emit('page-change', props.page - 1)");
    expectDirective(pageButtons[1], 'on', 'click', "emit('page-change', pageNumber)");
    expectDirective(pageButtons[2], 'on', 'click', "emit('page-change', props.page + 1)");
    const pageSize = findElements({ ...tableRoot, children: pagination.children } as RootNode, 'select')[0];
    expectDirective(pageSize, 'bind', 'value', 'props.pageSize');
    expectDirective(pageSize, 'on', 'change', 'updatePageSize');

    const toolbarRoot = templateRoot('src/features/hosts/components/HostToolbar.vue');
    const columnCheckboxes = findByClass(toolbarRoot, 'label', 'host-column-all')
      .flatMap((label) => label.children.filter((child): child is TemplateElement => child.type === NodeTypes.ELEMENT && child.tag === 'input'));
    expect(columnCheckboxes).toHaveLength(1);
    expectDirective(columnCheckboxes[0], 'bind', 'checked', 'props.allColumnsVisible');
    expectDirective(columnCheckboxes[0], 'bind', 'indeterminate', 'props.someColumnsVisible && !props.allColumnsVisible', ['prop']);
    expectDirective(columnCheckboxes[0], 'on', 'change', "emit('toggle-all-columns', $event)");
    const perColumn = findByClass(toolbarRoot, 'label', 'host-column-option')[0].children
      .find((child): child is TemplateElement => child.type === NodeTypes.ELEMENT && child.tag === 'input')!;
    expectDirective(perColumn, 'bind', 'checked', 'props.columnVisibility[column.key]');
    expectDirective(perColumn, 'bind', 'disabled', 'props.isOnlyVisibleColumn(column.key)');
    expectDirective(perColumn, 'on', 'change', "emit('update-column', column.key, $event)");
  });

  it('uses icon row actions in edit, verify, terminal, delete order', () => {
    const tableRoot = templateRoot('src/features/hosts/components/HostTable.vue');
    const actionButtons = findElements(tableRoot, 'button').filter((button) => hasStaticClass(button, 'host-action-icon'));

    expect(actionButtons).toHaveLength(4);
    expect(directiveExpression(actionButtons[0], 'on', 'click')).toBe("emit('edit', host)");
    expect(directiveExpression(actionButtons[1], 'on', 'click')).toBe("emit('verify', host)");
    expect(directiveExpression(actionButtons[2], 'on', 'click')).toBe("emit('open-simple-terminal', host)");
    expect(directiveExpression(actionButtons[3], 'on', 'click')).toBe("emit('delete', host)");
    expectDirective(actionButtons[2], 'if', undefined, 'props.canOpenTerminal');
    expect(staticAttribute(actionButtons[2], 'title')).toBe('终端');
    expect(staticAttribute(actionButtons[2], 'aria-label')).toBe('终端');

    const terminalIcon = findElements({ ...tableRoot, children: actionButtons[2].children } as RootNode, 'AppIcon')[0];
    expect(terminalIcon).toBeTruthy();
    expect(staticAttribute(terminalIcon, 'name')).toBe('terminal');
  });

  it('combines system architecture, system type, and config into one host spec table column only', () => {
    const managerScript = readSfc('src/features/hosts/components/HostManager.vue').scriptSetup?.content ?? '';
    const toolbarScript = readSfc('src/features/hosts/components/HostToolbar.vue').scriptSetup?.content ?? '';
    const tableRoot = templateRoot('src/features/hosts/components/HostTable.vue');
    const tableTemplate = readSfc('src/features/hosts/components/HostTable.vue').template?.content ?? '';
    const styles = readStyle('../../../../styles/tools/host/table.css');
    const exportSource = readFileSync(
      fileURLToPath(new URL('../../utils/export.ts', import.meta.url)),
      'utf8',
    );

    expect(managerScript).toContain("{ key: 'spec', label: '主机规格'");
    expect(managerScript).not.toContain("{ key: 'systemArch', label: '系统架构'");
    expect(managerScript).not.toContain("{ key: 'systemType', label: '系统类型'");
    expect(managerScript).not.toContain("{ key: 'config', label: '配置信息'");
    expect(toolbarScript).toContain("| 'spec'");
    expect(tableTemplate).toContain("props.isColumnVisible('spec')");
    expect(tableTemplate).toContain('class="host-spec-cell"');
    expect(tableTemplate).toContain('<strong>规格:</strong>');
    expect(tableTemplate).toContain('<strong>系统:</strong>');
    expect(tableTemplate).toContain('{{ formatHostSpec(host) }}');
    expect(tableTemplate).toContain('{{ formatHostSystem(host) }}');
    const specCell = findByClass(tableRoot, 'div', 'host-spec-cell')[0];
    const specValues = findElements({ ...tableRoot, children: specCell.children } as RootNode, 'em');
    expectDirective(specValues[0], 'bind', 'title', 'formatHostSpec(host)');
    expectDirective(specValues[1], 'bind', 'title', 'formatHostSystem(host)');
    expect(readSfc('src/features/hosts/components/HostTable.vue').scriptSetup?.content).toContain('function formatHostSpec(host: ManagedHost)');
    expect(readSfc('src/features/hosts/components/HostTable.vue').scriptSetup?.content).toContain('function formatHostSystem(host: ManagedHost)');
    expect(styles).toMatch(/\.host-spec-cell\s*\{[\s\S]*display:\s*grid;[\s\S]*gap:\s*8px;/);
    expect(styles).toMatch(/\.host-spec-cell span\s*\{[\s\S]*gap:\s*10px;/);
    expect(exportSource).toContain("{ field: 'systemArch'");
    expect(exportSource).toContain("{ field: 'systemType'");
    expect(exportSource).toContain("{ field: 'config'");
  });

  it('defaults host manager visible columns to the screenshot selection without persistence', () => {
    const managerScript = readSfc('src/features/hosts/components/HostManager.vue').scriptSetup?.content ?? '';
    const defaultVisibleMatch = managerScript.match(/const defaultVisibleHostColumnKeys = \[([\s\S]*?)\] as const satisfies readonly HostColumnKey\[];/);

    expect(defaultVisibleMatch).toBeTruthy();
    const defaultVisibleBlock = defaultVisibleMatch?.[1] ?? '';
    for (const key of ['group', 'name', 'ip', 'machine', 'spec', 'platformType', 'remark', 'status', 'actions']) {
      expect(defaultVisibleBlock).toContain(`'${key}',`);
    }
    for (const key of ['user', 'port', 'createdAt', 'updatedAt', 'creator']) {
      expect(defaultVisibleBlock).not.toContain(`'${key}',`);
    }
    expect(managerScript).toContain('defaultVisibleKeys: defaultVisibleHostColumnKeys');
    expect(managerScript).not.toContain('storageKey: hostColumnStorageKey');
  });

  it('keeps the host table compact while preserving action space', () => {
    const managerScript = readSfc('src/features/hosts/components/HostManager.vue').scriptSetup?.content ?? '';
    const styles = readStyle('../../../../styles/tools/host/table.css');

    expect(managerScript).toContain("{ key: 'group', label: '主机分组', width: 'minmax(84px, 0.7fr)', minWidth: 84 }");
    expect(managerScript).toContain("{ key: 'ip', label: 'IP地址', width: 'minmax(126px, 0.95fr)', minWidth: 126 }");
    expect(managerScript).toContain("{ key: 'spec', label: '主机规格', width: 'minmax(150px, 1fr)', minWidth: 150 }");
    expect(managerScript).toContain("'--host-select-column-width': '32px'");
    expect(managerScript).toContain("'--host-status-column-width': '86px'");
    expect(managerScript).toContain("'--host-actions-column-width': '132px'");
    expect(managerScript).toContain("'--host-status-sticky-right': actionsVisible ? 'calc(var(--host-actions-column-width) + 6px)' : '0px'");
    expect(styles).toMatch(/\.host-table\s*\{[\s\S]*width:\s*100%;[\s\S]*min-width:\s*var\(--host-table-min-width,\s*1300px\);/);
    expect(styles).toMatch(/\.host-table-row\s*\{[\s\S]*gap:\s*6px;[\s\S]*padding:\s*0 10px;/);
  });

  it('wires selected host file upload through the bulk execution handoff key', () => {
    const managerScript = readSfc('src/features/hosts/components/HostManager.vue').scriptSetup?.content ?? '';
    const tableRoot = templateRoot('src/features/hosts/components/HostTable.vue');
    const toolbarRoot = templateRoot('src/features/hosts/components/HostToolbar.vue');

    expect(managerScript).toContain('bulkExecutionUploadTargetIdsKey');
    expect(managerScript).toContain('openBulkFileUploadForSelectedHosts');
    expect(managerScript).toContain("window.sessionStorage.setItem(bulkExecutionUploadTargetIdsKey, JSON.stringify(executableIds))");

    const bulkButtons = findByClass(tableRoot, 'button', 'host-bulk-button-upload');
    expect(bulkButtons).toHaveLength(1);
    expectDirective(bulkButtons[0], 'on', 'click', "emit('upload-file-selected')");

    const toolbarUploadButton = findElements(toolbarRoot, 'button').find((button) =>
      directiveExpression(button, 'on', 'click') === "emit('upload-file-selected')",
    );
    expect(toolbarUploadButton).toBeTruthy();
  });

  it('keeps the selected-host batch action bar roomy enough for file upload actions', () => {
    const styles = readStyle('../../../../styles/tools/host/table.css');

    expect(styles).toMatch(/\.host-bulk-action-bar\s*\{[\s\S]*width:\s*640px;[\s\S]*min-height:\s*108px;[\s\S]*padding:\s*18px 24px 18px 22px;/);
    expect(styles).toMatch(/\.host-bulk-action-buttons\s*\{[\s\S]*gap:\s*10px;/);
    expect(styles).toMatch(/\.host-bulk-action-bar \.host-bulk-button\s*\{[\s\S]*min-height:\s*28px;[\s\S]*padding:\s*0 14px;[\s\S]*line-height:\s*28px;/);
  });

  it('uses the single-arrow rotate icon for the row verify action in every state', () => {
    const tableRoot = templateRoot('src/features/hosts/components/HostTable.vue');
    const verifyButton = findElements(tableRoot, 'button').find(
      (button) => directiveExpression(button, 'on', 'click') === "emit('verify', host)",
    );

    expect(verifyButton).toBeTruthy();
    const verifyIcon = findElements({ ...tableRoot, children: verifyButton!.children } as RootNode, 'AppIcon')[0];
    expect(verifyIcon).toBeTruthy();
    expect(staticAttribute(verifyIcon, 'name')).toBe('rotate');
    expectNoDirective(verifyIcon, 'bind', 'name');
  });

  it('rotates the row verify icon while verification is active', () => {
    const tableRoot = templateRoot('src/features/hosts/components/HostTable.vue');
    const verifyButton = findElements(tableRoot, 'button').find(
      (button) => directiveExpression(button, 'on', 'click') === "emit('verify', host)",
    );
    const styles = readStyle('../../../../styles/tools/host/table.css');

    expect(verifyButton).toBeTruthy();
    expectDirective(verifyButton!, 'bind', 'class', "{ 'is-verifying': props.verifyingIds.has(host.id) }");
    expect(styles).toMatch(/\.host-action-icon\.is-verifying\s+\.app-icon\s*\{[\s\S]*animation:\s*host-action-spin\s+0\.9s\s+linear\s+infinite;/);
    expect(styles).toMatch(/@keyframes\s+host-action-spin\s*\{[\s\S]*transform:\s*rotate\(360deg\);/);
  });

  it('keeps CredentialSelector model update before change and preserves editor forwarding order', () => {
    const selector = findElements(templateRoot('src/features/hosts/components/CredentialSelector.vue'), 'select')[0];
    const selectorModel = expectDirective(selector, 'model', undefined, 'selectedCredential', ['number']);
    const selectorChange = expectDirective(selector, 'on', 'change', "emit('change', $event)");
    expect(selector.props.indexOf(selectorModel)).toBeLessThan(selector.props.indexOf(selectorChange));

    const credentialSelector = findElements(templateRoot('src/features/hosts/components/HostEditorDialog.vue'), 'CredentialSelector')[0];
    expectDirective(credentialSelector, 'bind', 'model-value', 'props.form.credential');
    const update = expectDirective(
      credentialSelector,
      'on',
      'update:model-value',
      "emit('update-form-field', 'credential', $event)",
    );
    const change = expectDirective(credentialSelector, 'on', 'change', "emit('apply-credential', $event)");
    expect(credentialSelector.props.indexOf(update)).toBeLessThan(credentialSelector.props.indexOf(change));
  });

  it('keeps the editor modal class, title, and dedicated credential selector', () => {
    const root = templateRoot('src/features/hosts/components/HostEditorDialog.vue');
    const forms = findElements(root, 'form');
    expect(forms).toHaveLength(1);
    expect(staticAttribute(forms[0], 'class')).toBe('host-form-modal host-edit-modal host-horizontal-modal');
    const headings = findElements(root, 'h2');
    expect(headings).toHaveLength(1);
    expect(firstInterpolationExpression(headings[0])).toBe("props.dialog.mode === 'edit' ? '编辑主机' : '新增主机'");
    expect(componentTags(root)).toContain('CredentialSelector');
  });

  it('preserves the root-group add-host default argument semantics', () => {
    const root = templateRoot('src/features/hosts/components/HostGroupTree.vue');
    const addHostButton = findElements(root, 'button').find((element) =>
      directiveExpression(element, 'on', 'click')?.includes("emit('add-host'"),
    );
    expect(addHostButton).toBeTruthy();
    expectDirective(addHostButton!, 'on', 'click', "emit('add-host', props.menu.group.key ?? undefined)");
  });

  it('exposes table import controls with direct import and template download actions', () => {
    const toolbarRoot = templateRoot('src/features/hosts/components/HostToolbar.vue');
    const importButton = findElements(toolbarRoot, 'button').find((button) => staticAttribute(button, 'title') === '导入');
    expect(importButton).toBeTruthy();
    expectDirective(importButton!, 'on', 'click', "emit('import')");

    const importRoot = templateRoot('src/features/hosts/components/HostImportDialog.vue');
    expect(findByClass(importRoot, 'article', 'host-import-modal')).toHaveLength(1);
    expect(findByClass(importRoot, 'table', 'host-import-template-preview')).toHaveLength(1);
    const headers = findElements(importRoot, 'th').map((header) => header.children[0]?.type === NodeTypes.TEXT ? header.children[0].content : '');
    expect(headers).toEqual(['主机分组', '节点', 'IP地址', '平台类型', '端口', '备注']);
    const buttons = findElements(importRoot, 'button');
    expect(buttons.some((button) => directiveExpression(button, 'on', 'click') === "emit('confirm')")).toBe(true);
    expect(buttons.some((button) => directiveExpression(button, 'on', 'click') === "emit('download-template')")).toBe(true);
  });

  it('connects App import/export dialogs with exact models and event handlers', () => {
    const root = templateRoot('src/App.vue');
    const exportDialog = findElements(root, 'HostExportDialog')[0];
    expectDirective(exportDialog, 'model', 'scope', 'hostExportScope');
    expectDirective(exportDialog, 'model', 'format', 'hostTransferFormat');
    expectEvents(exportDialog, {
      close: 'closeHostTransferDialog',
      confirm: 'confirmHostExport',
      'toggle-column': 'toggleHostExportColumn',
      'toggle-all-columns': 'toggleAllHostExportColumns',
    });

    const importDialog = findElements(root, 'HostImportDialog')[0];
    expectEvents(importDialog, {
      close: 'closeHostTransferDialog',
      confirm: 'confirmHostTransfer',
      'download-template': 'downloadHostImportTemplate',
    });
    expect(findByClass(root, 'article', 'host-transfer-modal')).toHaveLength(0);
  });
});

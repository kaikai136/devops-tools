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
      'column-visibility': 'hostColumnVisibility',
      'can-create': "canUsePageAction('hosts', 'create')",
      'can-manage-quick-commands': "canUsePageAction('hosts', 'quick_commands')",
      'can-export': "canUsePageAction('hosts', 'export')",
    });
    expectEvents(toolbar, {
      create: 'addManagedHost()',
      'open-quick-commands': 'openHostQuickCommandManager',
      'status-filter': 'setHostStatusFilter',
      'toggle-all-columns': 'toggleAllHostColumns',
      'update-column': 'updateHostColumnVisibility',
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
      edit: 'editManagedHost',
      verify: 'verifyManagedHost',
      delete: 'deleteManagedHost',
      'page-change': 'setHostPage',
      'page-size-change': 'hostPageSize = $event',
      'clear-selection': 'clearSelectedManagedHosts',
    });

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

    expect(styles).toMatch(/\.host-manager-page\s*\{[\s\S]*grid-template-columns:\s*minmax\(220px,\s*270px\)\s*minmax\(680px,\s*1fr\);/);
    expect(styles).toMatch(/\.host-groups-panel\s*\{[\s\S]*padding:\s*16px;/);
    expect(styles).toMatch(/\.host-group-row strong\s*\{[\s\S]*min-width:\s*0;[\s\S]*overflow:\s*hidden;[\s\S]*text-overflow:\s*ellipsis;[\s\S]*white-space:\s*nowrap;/);
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
    expectDirective(editorBackdrop, 'on', 'click', "emit('close')", ['self']);
    const moveBackdrop = findByClass(templateRoot('src/features/hosts/components/HostMoveDialog.vue'), 'div', 'modal-backdrop')[0];
    expectDirective(moveBackdrop, 'on', 'click', "emit('close')", ['self']);
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
    expectDirective(importDialog, 'model', 'format', 'hostTransferFormat');
    expectEvents(importDialog, {
      close: 'closeHostTransferDialog',
      confirm: 'confirmHostTransfer',
    });
    expect(findByClass(root, 'article', 'host-transfer-modal')).toHaveLength(0);
  });
});

import {
  computed,
  defineComponent,
  h,
  inject,
  nextTick,
  onBeforeUnmount,
  onMounted,
  provide,
  ref,
  shallowRef,
  watch,
  type App,
  type Component,
  type ComputedRef,
  type PropType,
  type VNode,
} from 'vue';

type Tone = 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'error';

const inheritAttrs = { inheritAttrs: false };

export interface NativeInputInstance {
  input: HTMLInputElement | HTMLTextAreaElement | null;
  focus: () => void;
  blur: () => void;
}

function modelValue<T>(props: { modelValue: T }, emit: (event: 'update:modelValue', value: T) => void) {
  return computed({
    get: () => props.modelValue,
    set: (value: T) => emit('update:modelValue', value),
  });
}

export const NativeButton = defineComponent({
  name: 'NativeButton',
  ...inheritAttrs,
  props: {
    type: { type: String as PropType<Tone | 'default' | 'text'>, default: 'default' },
    nativeType: { type: String as PropType<'button' | 'submit' | 'reset'>, default: 'button' },
    loading: Boolean,
    disabled: Boolean,
    circle: Boolean,
    round: Boolean,
    text: Boolean,
    link: Boolean,
    plain: Boolean,
    size: { type: String as PropType<'small' | 'default' | 'large'>, default: 'default' },
  },
  emits: ['click'],
  setup(props, { attrs, emit, slots }) {
    return () =>
      h(
        'button',
        {
          ...attrs,
          type: props.nativeType,
          disabled: props.disabled || props.loading,
          class: [
            'native-button',
            `native-button-${props.type}`,
            `native-button-${props.size}`,
            { 'is-circle': props.circle, 'is-round': props.round, 'is-text': props.text || props.link, 'is-plain': props.plain, 'is-loading': props.loading },
            attrs.class,
          ],
          onClick: (event: MouseEvent) => emit('click', event),
        },
        [props.loading ? h('span', { class: 'native-spinner', 'aria-hidden': 'true' }) : null, slots.default?.()],
      );
  },
});

export const NativeButtonGroup = defineComponent({
  name: 'NativeButtonGroup',
  ...inheritAttrs,
  setup(_, { attrs, slots }) {
    return () => h('div', { ...attrs, class: ['native-button-group', attrs.class] }, slots.default?.());
  },
});

export const NativeInput = defineComponent({
  name: 'NativeInput',
  ...inheritAttrs,
  props: {
    modelValue: { type: String, default: '' },
    type: { type: String, default: 'text' },
    rows: { type: [String, Number] as PropType<string | number | undefined>, default: undefined },
    showPassword: Boolean,
    clearable: Boolean,
    disabled: Boolean,
    maxlength: { type: [String, Number] as PropType<string | number | undefined>, default: undefined },
  },
  emits: ['update:modelValue', 'input', 'change', 'clear', 'keyup', 'keydown', 'blur', 'focus'],
  setup(props, { attrs, emit, expose, slots }) {
    const input = ref<HTMLInputElement | HTMLTextAreaElement | null>(null);
    const visible = ref(false);
    const value = modelValue(props, (event, next) => emit(event, next));
    expose({
      get input() {
        return input.value;
      },
      focus: () => input.value?.focus(),
      blur: () => input.value?.blur(),
    } satisfies NativeInputInstance);
    return () =>
      h('div', { class: ['native-input', attrs.class] }, [
        slots.prefix ? h('span', { class: 'native-input-prefix' }, slots.prefix()) : null,
        h(props.type === 'textarea' ? 'textarea' : 'input', {
          ...attrs,
          ref: input,
          class: ['native-input-control', { 'has-prefix': Boolean(slots.prefix), 'has-suffix': Boolean(slots.suffix) }],
          value: value.value,
          type: props.type === 'textarea' ? undefined : props.showPassword ? (visible.value ? 'text' : 'password') : props.type,
          rows: props.type === 'textarea' ? props.rows ?? 3 : undefined,
          disabled: props.disabled,
          maxlength: props.maxlength,
          onInput: (event: Event) => {
            const next = (event.target as HTMLInputElement).value;
            value.value = next;
            emit('input', next);
          },
          onChange: (event: Event) => emit('change', (event.target as HTMLInputElement).value),
          onKeyup: (event: KeyboardEvent) => emit('keyup', event),
          onKeydown: (event: KeyboardEvent) => emit('keydown', event),
          onBlur: (event: FocusEvent) => emit('blur', event),
          onFocus: (event: FocusEvent) => emit('focus', event),
        }),
        props.clearable && value.value
          ? h(
              'button',
              {
                type: 'button',
                class: 'native-input-clear',
                'aria-label': '清空',
                onClick: () => {
                  value.value = '';
                  emit('clear');
                },
              },
              '×',
            )
          : null,
        props.showPassword
          ? h(
              'button',
              { type: 'button', class: 'native-input-eye', 'aria-label': visible.value ? '隐藏密码' : '显示密码', onClick: () => (visible.value = !visible.value) },
              visible.value ? '隐藏' : '显示',
            )
          : slots.suffix
            ? h('span', { class: 'native-input-suffix' }, slots.suffix())
            : null,
      ]);
  },
});

export const NativeTextarea = defineComponent({
  name: 'NativeTextarea',
  ...inheritAttrs,
  props: {
    modelValue: { type: String, default: '' },
    rows: { type: [String, Number] as PropType<string | number>, default: 3 },
    disabled: Boolean,
    maxlength: { type: [String, Number] as PropType<string | number | undefined>, default: undefined },
  },
  emits: ['update:modelValue', 'input', 'change', 'blur', 'focus', 'keyup', 'keydown'],
  setup(props, { attrs, emit, expose }) {
    const textarea = ref<HTMLTextAreaElement | null>(null);
    const value = modelValue(props, (event, next) => emit(event, next));
    expose({
      get input() {
        return textarea.value;
      },
      focus: () => textarea.value?.focus(),
      blur: () => textarea.value?.blur(),
    } satisfies NativeInputInstance);
    return () =>
      h('textarea', {
        ...attrs,
        ref: textarea,
        class: ['native-textarea', attrs.class],
        rows: props.rows,
        maxlength: props.maxlength,
        disabled: props.disabled,
        value: value.value,
        onInput: (event: Event) => {
          const next = (event.target as HTMLTextAreaElement).value;
          value.value = next;
          emit('input', next);
        },
        onChange: (event: Event) => emit('change', (event.target as HTMLTextAreaElement).value),
        onBlur: (event: FocusEvent) => emit('blur', event),
        onFocus: (event: FocusEvent) => emit('focus', event),
        onKeyup: (event: KeyboardEvent) => emit('keyup', event),
        onKeydown: (event: KeyboardEvent) => emit('keydown', event),
      });
  },
});

export const NativeNumberInput = defineComponent({
  name: 'NativeNumberInput',
  ...inheritAttrs,
  props: {
    modelValue: { type: Number, default: 0 },
    min: { type: Number, default: undefined },
    max: { type: Number, default: undefined },
    step: { type: Number, default: 1 },
    disabled: Boolean,
  },
  emits: ['update:modelValue', 'change', 'input', 'keyup', 'keydown'],
  setup(props, { attrs, emit }) {
    return () =>
      h('input', {
        ...attrs,
        class: ['native-number-input', attrs.class],
        type: 'number',
        value: props.modelValue,
        min: props.min,
        max: props.max,
        step: props.step,
        disabled: props.disabled,
        onInput: (event: Event) => {
          const raw = Number((event.target as HTMLInputElement).value);
          emit('update:modelValue', Number.isFinite(raw) ? raw : props.modelValue);
          emit('input', raw);
        },
        onChange: (event: Event) => emit('change', Number((event.target as HTMLInputElement).value)),
        onKeyup: (event: KeyboardEvent) => emit('keyup', event),
        onKeydown: (event: KeyboardEvent) => emit('keydown', event),
      });
  },
});

export const NativeOption = defineComponent({
  name: 'NativeOption',
  props: {
    value: { type: [String, Number, Boolean, Object, null] as PropType<unknown>, default: undefined },
    label: { type: String, default: '' },
    disabled: Boolean,
  },
  setup(props, { slots }) {
    return () => h('option', { value: props.value as string | number | undefined, disabled: props.disabled }, slots.default?.() ?? props.label);
  },
});

export const NativeSelect = defineComponent({
  name: 'NativeSelect',
  ...inheritAttrs,
  props: {
    modelValue: { type: [String, Number, Boolean, Object, null] as PropType<unknown>, default: '' },
    disabled: Boolean,
    clearable: Boolean,
  },
  emits: ['update:modelValue', 'change', 'clear', 'visible-change'],
  setup(props, { attrs, emit, slots }) {
    const value = modelValue(props, (event, next) => emit(event, next));
    const options = computed(() =>
      (slots.default?.() ?? [])
        .filter((node) => node.type === NativeOption)
        .map((node) => ({ node, value: (node.props as { value?: unknown } | null)?.value })),
    );
    const optionValue = (selected: unknown) => String(selected ?? '');
    return () =>
      h('select', {
        ...attrs,
        class: ['native-select', attrs.class],
        disabled: props.disabled,
        value: optionValue(value.value),
        onChange: (event: Event) => {
          const raw = (event.target as HTMLSelectElement).value;
          const next = options.value.find((option) => optionValue(option.value) === raw)?.value ?? raw;
          value.value = next;
          emit('change', next);
        },
      }, slots.default?.());
  },
});

export const NativeCheckbox = defineComponent({
  name: 'NativeCheckbox',
  ...inheritAttrs,
  props: { modelValue: Boolean, disabled: Boolean, indeterminate: Boolean, label: { type: String, default: '' } },
  emits: ['update:modelValue', 'change'],
  setup(props, { attrs, emit, slots }) {
    const input = ref<HTMLInputElement | null>(null);
    watch(
      () => props.indeterminate,
      (value) => {
        if (input.value) input.value.indeterminate = value;
      },
      { immediate: true },
    );
    return () =>
      h('label', { ...attrs, class: ['native-checkbox', attrs.class, { disabled: props.disabled }] }, [
        h('input', {
          ref: input,
          type: 'checkbox',
          checked: props.modelValue,
          disabled: props.disabled,
          onChange: (event: Event) => {
            const next = (event.target as HTMLInputElement).checked;
            emit('update:modelValue', next);
            emit('change', next);
          },
        }),
        h('span', { class: 'native-checkmark', 'aria-hidden': 'true' }),
        slots.default?.() ?? props.label,
      ]);
  },
});

export const NativeRadioButton = defineComponent({
  name: 'NativeRadioButton',
  props: { label: { type: [String, Number] as PropType<string | number>, default: '' }, value: { type: [String, Number] as PropType<string | number>, default: '' }, disabled: Boolean },
  setup(props, { slots }) {
    const group = inject<{ value: ComputedRef<string | number>; name: string; choose: (value: string | number) => void } | null>('native-radio-group', null);
    return () =>
      h('label', { class: ['native-radio-button', { active: group?.value.value === props.value, disabled: props.disabled }] }, [
        h('input', {
          type: 'radio',
          name: group?.value.name ?? 'native-radio',
          value: props.value,
          checked: group?.value.value === props.value,
          disabled: props.disabled,
          onChange: () => group?.choose(props.value),
        }),
        slots.default?.() ?? props.label,
      ]);
  },
});

export const NativeRadioGroup = defineComponent({
  name: 'NativeRadioGroup',
  props: { modelValue: { type: [String, Number] as PropType<string | number>, default: '' } },
  emits: ['update:modelValue', 'change'],
  setup(props, { emit, slots }) {
    const value = modelValue(props, (event, next) => emit(event, next));
    const name = `native-radio-${Math.random().toString(36).slice(2)}`;
    provide('native-radio-group', {
      value,
      name,
      choose: (next: string | number) => {
        value.value = next;
        emit('change', next);
      },
    });
    return () => h('div', { class: 'native-radio-group' }, slots.default?.());
  },
});

export const NativeSwitch = defineComponent({
  name: 'NativeSwitch',
  ...inheritAttrs,
  props: { modelValue: Boolean, disabled: Boolean, activeText: String, inactiveText: String },
  emits: ['update:modelValue', 'change'],
  setup(props, { attrs, emit }) {
    return () =>
      h('label', { ...attrs, class: ['native-switch', attrs.class, { disabled: props.disabled }] }, [
        h('input', {
          type: 'checkbox',
          checked: props.modelValue,
          disabled: props.disabled,
          onChange: (event: Event) => {
            const next = (event.target as HTMLInputElement).checked;
            emit('update:modelValue', next);
            emit('change', next);
          },
        }),
        h('span', { class: 'native-switch-track' }, h('span', { class: 'native-switch-thumb' })),
        h('span', { class: 'native-switch-label' }, props.modelValue ? props.activeText : props.inactiveText),
      ]);
  },
});

export const NativeTag = defineComponent({
  name: 'NativeTag',
  props: { type: { type: String as PropType<Tone>, default: 'info' }, effect: String, size: String },
  setup(props, { attrs, slots }) {
    return () => h('span', { ...attrs, class: ['native-tag', `native-tag-${props.type}`, attrs.class] }, slots.default?.());
  },
});

export const NativeAlert = defineComponent({
  name: 'NativeAlert',
  ...inheritAttrs,
  props: { type: { type: String as PropType<Tone>, default: 'info' }, title: { type: String, default: '' }, closable: Boolean },
  emits: ['close'],
  setup(props, { attrs, emit, slots }) {
    return () =>
      h('div', { ...attrs, class: ['native-alert', `native-alert-${props.type}`, attrs.class] }, [
        h('strong', props.title),
        slots.default?.(),
        props.closable ? h('button', { type: 'button', onClick: () => emit('close') }, '×') : null,
      ]);
  },
});

export const NativeEmpty = defineComponent({
  name: 'NativeEmpty',
  ...inheritAttrs,
  props: { description: { type: String, default: '暂无数据' } },
  setup(props, { attrs }) {
    return () => h('div', { ...attrs, class: ['native-empty', attrs.class] }, [h('span', { class: 'native-empty-mark' }, '—'), h('p', props.description)]);
  },
});

export const NativeProgress = defineComponent({
  name: 'NativeProgress',
  ...inheritAttrs,
  props: { percentage: { type: Number, default: 0 }, strokeWidth: { type: Number, default: 8 } },
  setup(props, { attrs }) {
    return () =>
      h('div', { ...attrs, class: ['native-progress', attrs.class] }, h('span', { style: { width: `${Math.min(100, Math.max(0, props.percentage))}%`, height: `${props.strokeWidth}px` } }));
  },
});

export const NativeSlider = defineComponent({
  name: 'NativeSlider',
  ...inheritAttrs,
  props: { modelValue: { type: Number, default: 0 }, min: { type: Number, default: 0 }, max: { type: Number, default: 100 }, step: { type: Number, default: 1 } },
  emits: ['update:modelValue', 'change', 'input'],
  setup(props, { attrs, emit }) {
    return () => h('input', {
      ...attrs,
      class: ['native-slider', attrs.class],
      type: 'range',
      value: props.modelValue,
      min: props.min,
      max: props.max,
      step: props.step,
      onInput: (event: Event) => {
        const next = Number((event.target as HTMLInputElement).value);
        emit('update:modelValue', next);
        emit('input', next);
      },
      onChange: (event: Event) => emit('change', Number((event.target as HTMLInputElement).value)),
    });
  },
});

export const NativeColorPicker = defineComponent({
  name: 'NativeColorPicker',
  props: { modelValue: { type: String, default: '#2563eb' }, disabled: Boolean },
  emits: ['update:modelValue', 'change'],
  setup(props, { emit }) {
    return () => h('input', { class: 'native-color-picker', type: 'color', value: props.modelValue, disabled: props.disabled, onInput: (event: Event) => { const next = (event.target as HTMLInputElement).value; emit('update:modelValue', next); emit('change', next); } });
  },
});

export const NativeDatePicker = defineComponent({
  name: 'NativeDatePicker',
  ...inheritAttrs,
  props: { modelValue: { type: [String, Date, null] as PropType<string | Date | null>, default: null }, disabled: Boolean },
  emits: ['update:modelValue', 'change'],
  setup(props, { attrs, emit }) {
    const value = computed(() => props.modelValue instanceof Date ? props.modelValue.toISOString().slice(0, 10) : props.modelValue ?? '');
    return () => h('input', { ...attrs, class: ['native-date-picker', attrs.class], type: 'date', value: value.value, disabled: props.disabled, onInput: (event: Event) => { const next = (event.target as HTMLInputElement).value || null; emit('update:modelValue', next); emit('change', next); } });
  },
});

export const NativeUpload = defineComponent({
  name: 'NativeUpload',
  props: { autoUpload: Boolean, showFileList: Boolean, onChange: Function as PropType<(file: { raw: File }) => void> },
  setup(props, { slots }) {
    const input = ref<HTMLInputElement | null>(null);
    return () => h('span', { class: 'native-upload', onClick: () => input.value?.click() }, [
      h('input', { ref: input, hidden: true, type: 'file', onChange: (event: Event) => { const file = (event.target as HTMLInputElement).files?.[0]; if (file) props.onChange?.({ raw: file }); } }),
      slots.default?.(),
    ]);
  },
});

export const NativeScrollbar = defineComponent({
  name: 'NativeScrollbar',
  ...inheritAttrs,
  setup(_, { attrs, slots }) {
    return () => h('div', { ...attrs, class: ['native-scrollbar', attrs.class] }, slots.default?.());
  },
});

const tableKey = Symbol('native-table');
interface TableColumn {
  props: Record<string, unknown>;
  slots: Readonly<Record<string, ((...args: any[]) => VNode[]) | undefined>>;
  id: symbol;
}
interface TableContext {
  columns: ReturnType<typeof shallowRef<TableColumn[]>>;
  register: (column: TableColumn) => void;
  unregister: (id: symbol) => void;
}

export const NativeTableColumn = defineComponent({
  name: 'NativeTableColumn',
  props: {
    prop: String,
    label: String,
    type: String,
    width: [String, Number],
    minWidth: [String, Number],
    fixed: String,
    index: Function as PropType<(index: number) => number>,
  },
  setup(props, { slots }) {
    const context = inject<TableContext | null>(tableKey, null);
    const id = Symbol('column');
    onMounted(() => context?.register({ props: props as unknown as Record<string, unknown>, slots, id }));
    onBeforeUnmount(() => context?.unregister(id));
    return () => null;
  },
});

export const NativeTable = defineComponent({
  name: 'NativeTable',
  ...inheritAttrs,
  props: {
    data: { type: Array as PropType<Record<string, any>[]>, default: () => [] },
    rowKey: { type: [String, Function] as PropType<string | ((row: Record<string, any>) => string | number)>, default: 'id' },
    emptyText: { type: String, default: '暂无数据' },
  },
  emits: ['selection-change', 'row-click'],
  setup(props, { attrs, emit, slots }) {
    const columns = shallowRef<TableColumn[]>([]);
    const selected = ref(new Set<string | number>());
    const context: TableContext = {
      columns,
      register: (column) => columns.value = [...columns.value, column],
      unregister: (id) => columns.value = columns.value.filter((column) => column.id !== id),
    };
    provide(tableKey, context);
    const keyOf = (row: Record<string, any>, index: number) => typeof props.rowKey === 'function' ? props.rowKey(row) : row[props.rowKey] ?? index;
    const selectedRows = () => props.data.filter((row, index) => selected.value.has(keyOf(row, index)));
    const toggle = (row: Record<string, any>, index: number, checked: boolean) => {
      const key = keyOf(row, index);
      if (checked) selected.value.add(key); else selected.value.delete(key);
      emit('selection-change', selectedRows());
    };
    return () => {
      const visibleColumns = columns.value;
      const header = visibleColumns.map((column) => h('th', { style: { width: column.props.width ? `${column.props.width}px` : undefined, minWidth: column.props.minWidth ? `${column.props.minWidth}px` : undefined } }, column.props.type === 'selection'
        ? (column.slots.header?.() ?? h('input', { type: 'checkbox', checked: selected.value.size === props.data.length && props.data.length > 0, onChange: (event: Event) => { const checked = (event.target as HTMLInputElement).checked; props.data.forEach((row, index) => toggle(row, index, checked)); } }))
        : column.slots.header?.() ?? String(column.props.label ?? '')));
      const rows = props.data.map((row, index) => h('tr', { key: keyOf(row, index), onClick: (event: MouseEvent) => emit('row-click', row, columnEvent(event)) }, visibleColumns.map((column) => {
        if (column.props.type === 'selection') return h('td', [h('input', { type: 'checkbox', checked: selected.value.has(keyOf(row, index)), onClick: (event: MouseEvent) => event.stopPropagation(), onChange: (event: Event) => toggle(row, index, (event.target as HTMLInputElement).checked) })]);
        const content = column.props.type === 'index'
          ? String(column.props.index ? (column.props.index as (index: number) => number)(index) : index + 1)
          : column.slots.default
            ? column.slots.default({ row, $index: index })
            : column.props.prop
              ? String(row[column.props.prop] ?? '')
              : '';
        return h('td', { title: typeof content === 'string' ? content : undefined }, content as any);
      })));
      return h('div', { ...attrs, class: ['native-table-wrap', attrs.class] }, [
        h('table', { class: 'native-table' }, [h('thead', [h('tr', header)]), h('tbody', rows.length ? rows : [h('tr', [h('td', { colspan: Math.max(1, visibleColumns.length), class: 'native-table-empty' }, props.emptyText)])])]),
        slots.default?.(),
      ]);
    };
  },
});

function columnEvent(event: MouseEvent) {
  return event;
}

export const NativePagination = defineComponent({
  name: 'NativePagination',
  ...inheritAttrs,
  props: {
    currentPage: { type: Number, default: 1 },
    pageSize: { type: Number, default: 10 },
    total: { type: Number, default: 0 },
    pageSizes: { type: Array as PropType<number[]>, default: () => [10, 20, 50] },
  },
  emits: ['current-change', 'size-change'],
  setup(props, { attrs, emit }) {
    const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)));
    return () => h('div', { ...attrs, class: ['native-pagination', attrs.class] }, [
      h('button', { type: 'button', disabled: props.currentPage <= 1, onClick: () => emit('current-change', props.currentPage - 1) }, '‹'),
      ...Array.from({ length: Math.min(totalPages.value, 7) }, (_, index) => h('button', { type: 'button', class: { active: index + 1 === props.currentPage }, onClick: () => emit('current-change', index + 1) }, String(index + 1))),
      h('button', { type: 'button', disabled: props.currentPage >= totalPages.value, onClick: () => emit('current-change', props.currentPage + 1) }, '›'),
      h('select', { value: props.pageSize, onChange: (event: Event) => emit('size-change', Number((event.target as HTMLSelectElement).value)) }, props.pageSizes.map((size) => h('option', { value: size }, `${size} 条/页`))),
    ]);
  },
});

export const NativeForm = defineComponent({
  name: 'NativeForm',
  ...inheritAttrs,
  setup(_, { attrs, slots }) {
    return () => h('form', { ...attrs, class: ['native-form', attrs.class] }, slots.default?.());
  },
});

export const NativeFormItem = defineComponent({
  name: 'NativeFormItem',
  ...inheritAttrs,
  props: { label: String, error: String, required: Boolean },
  setup(props, { attrs, slots }) {
    return () => h('label', { ...attrs, class: ['native-form-item', attrs.class] }, [props.label ? h('span', { class: 'native-form-label' }, [props.label, props.required ? h('b', '*') : null]) : null, slots.default?.(), props.error ? h('small', { class: 'native-form-error' }, props.error) : null]);
  },
});

export const NativeDialog = defineComponent({
  name: 'NativeDialog',
  ...inheritAttrs,
  props: {
    modelValue: Boolean,
    title: { type: String, default: '' },
    width: { type: [String, Number], default: '560px' },
    closeOnClickModal: { type: Boolean, default: true },
    showClose: { type: Boolean, default: true },
  },
  emits: ['update:modelValue', 'close', 'open', 'opened', 'closed'],
  setup(props, { attrs, emit, slots }) {
    const dialog = ref<HTMLElement | null>(null);
    const onKeydown = (event: KeyboardEvent) => {
      if (props.modelValue && event.key === 'Escape') close();
    };
    watch(() => props.modelValue, async (open) => {
      emit(open ? 'open' : 'close');
      if (open) {
        document.addEventListener('keydown', onKeydown);
        await nextTick();
        dialog.value?.querySelector<HTMLElement>('input,select,textarea,button')?.focus();
        emit('opened');
      } else {
        document.removeEventListener('keydown', onKeydown);
        emit('closed');
      }
    }, { immediate: true });
    onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown));
    const close = () => {
      emit('update:modelValue', false);
      emit('close');
    };
    return () => props.modelValue ? h('div', { class: 'native-modal-backdrop', onClick: (event: MouseEvent) => { if (props.closeOnClickModal && event.target === event.currentTarget) close(); } }, h('section', { ...attrs, ref: dialog, class: ['native-dialog', attrs.class], style: { width: typeof props.width === 'number' ? `${props.width}px` : props.width } , role: 'dialog', 'aria-modal': 'true' }, [
      h('header', { class: 'native-dialog-header' }, [h('h2', props.title), props.showClose ? h('button', { type: 'button', class: 'native-dialog-close', 'aria-label': '关闭', onClick: close }, '×') : null]),
      h('div', { class: 'native-dialog-body' }, slots.default?.()),
      slots.footer ? h('footer', { class: 'native-dialog-footer' }, slots.footer()) : null,
    ])) : null;
  },
});

export const NativeDrawer = defineComponent({
  name: 'NativeDrawer',
  ...NativeDialog,
  setup(props, context) {
    const render = (NativeDialog as any).setup(props, context);
    return () => {
      const node = render?.();
      if (!node) return node;
      return h('div', { class: ['native-drawer-shell', context.attrs.class] }, node);
    };
  },
});

export const NativeDescriptionsItem = defineComponent({
  name: 'NativeDescriptionsItem',
  props: { label: String, span: { type: Number, default: 1 } },
  setup(props, { slots }) {
    return () => h('div', { class: 'native-description-item', style: { gridColumn: `span ${props.span}` } }, [h('dt', props.label), h('dd', slots.default?.())]);
  },
});

export const NativeDescriptions = defineComponent({
  name: 'NativeDescriptions',
  ...inheritAttrs,
  props: { column: { type: Number, default: 3 } },
  setup(props, { attrs, slots }) {
    return () => h('dl', { ...attrs, class: ['native-descriptions', attrs.class], style: { gridTemplateColumns: `repeat(${props.column}, minmax(0, 1fr))` } }, slots.default?.());
  },
});

export const NativeTabPane = defineComponent({
  name: 'NativeTabPane',
  props: { name: { type: String, default: '' }, label: { type: String, default: '' } },
  setup() {
    return () => null;
  },
});

export const NativeTabs = defineComponent({
  name: 'NativeTabs',
  ...inheritAttrs,
  props: { modelValue: { type: String, default: '' } },
  emits: ['update:modelValue', 'tab-click'],
  setup(props, { attrs, emit, slots }) {
    const active = modelValue(props, (event, next) => emit(event, next));
    const panes = ref<VNode[]>([]);
    return () => {
      panes.value = (slots.default?.() ?? []).filter((node) => node.type === NativeTabPane);
      return h('div', { ...attrs, class: ['native-tabs', attrs.class] }, [
        h('div', { class: 'native-tabs-nav' }, panes.value.map((pane) => h('button', { type: 'button', class: { active: (pane.props as any)?.name === active.value }, onClick: () => { active.value = (pane.props as any)?.name; emit('tab-click', pane); } }, (pane.props as any)?.label))),
        h('div', { class: 'native-tabs-body' }, panes.value.find((pane) => (pane.props as any)?.name === active.value)?.children ?? slots.default?.()),
      ]);
    };
  },
});

export const NativeTooltip = defineComponent({
  name: 'NativeTooltip',
  props: { content: String },
  setup(props, { attrs, slots }) {
    return () => h('span', { ...attrs, class: ['native-tooltip', attrs.class], title: props.content }, slots.default?.());
  },
});

export const NativePopover = defineComponent({
  name: 'NativePopover',
  ...inheritAttrs,
  props: { visible: Boolean },
  emits: ['update:visible'],
  setup(props, { attrs, emit, slots }) {
    const open = ref(props.visible);
    watch(() => props.visible, (value) => (open.value = value));
    const toggle = () => { open.value = !open.value; emit('update:visible', open.value); };
    return () => h('span', { ...attrs, class: ['native-popover-shell', attrs.class] }, [
      h('span', { class: 'native-popover-reference', onClick: toggle }, slots.reference?.()),
      open.value ? h('div', { class: 'native-popover-panel' }, slots.default?.()) : null,
    ]);
  },
});

export const NativeDropdownItem = defineComponent({
  name: 'NativeDropdownItem',
  props: { command: String, disabled: Boolean, divided: Boolean },
  setup(props, { slots }) {
    const command = inject<(value: string) => void>('native-dropdown-command', () => undefined);
    return () => h('button', { type: 'button', class: ['native-dropdown-item', { disabled: props.disabled, divided: props.divided }], disabled: props.disabled, onClick: () => command(props.command ?? '') }, slots.default?.());
  },
});

export const NativeDropdownMenu = defineComponent({
  name: 'NativeDropdownMenu',
  setup(_, { slots }) {
    return () => h('div', { class: 'native-dropdown-menu' }, slots.default?.());
  },
});

export const NativeDropdown = defineComponent({
  name: 'NativeDropdown',
  ...inheritAttrs,
  emits: ['command'],
  setup(_, { attrs, emit, slots }) {
    const open = ref(false);
    provide('native-dropdown-command', (command: string) => { open.value = false; emit('command', command); });
    return () => h('span', { ...attrs, class: ['native-dropdown-shell', attrs.class] }, [
      h('span', { class: 'native-dropdown-trigger', onClick: () => (open.value = !open.value) }, slots.default?.()),
      open.value ? h('div', { class: 'native-dropdown-panel' }, slots.dropdown?.()) : null,
    ]);
  },
});

export const NativeConfirmDialog = NativeDialog;

export function installNativeUi(app: App) {
  const components: Record<string, Component> = {
    NativeButton, NativeButtonGroup, NativeInput, NativeTextarea, NativeNumberInput, NativeOption, NativeSelect, NativeCheckbox,
    NativeRadioButton, NativeRadioGroup, NativeSwitch, NativeTag, NativeAlert, NativeEmpty, NativeProgress,
    NativeSlider, NativeColorPicker, NativeDatePicker, NativeUpload, NativeScrollbar, NativeTable, NativeTableColumn,
    NativePagination, NativeForm, NativeFormItem, NativeDialog, NativeDrawer, NativeDescriptions, NativeDescriptionsItem,
    NativeTabs, NativeTabPane, NativeTooltip, NativePopover, NativeDropdown, NativeDropdownMenu, NativeDropdownItem,
    NativeConfirmDialog,
  };
  Object.entries(components).forEach(([name, component]) => app.component(name, component));
}

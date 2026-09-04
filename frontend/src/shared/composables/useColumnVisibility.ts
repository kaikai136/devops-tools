import { computed, ref } from 'vue';

export interface TableColumnOption<TKey extends string> {
  key: TKey;
  label: string;
  width: string;
  minWidth?: number;
}

interface ColumnVisibilityOptions<TKey extends string> {
  storageKey?: string;
  fallbackKey?: TKey;
  defaultVisible?: boolean;
  defaultVisibleKeys?: readonly TKey[];
}

export type ColumnVisibility<TKey extends string> = Record<TKey, boolean>;

export function useColumnVisibility<TKey extends string>(
  columns: readonly TableColumnOption<TKey>[],
  options: ColumnVisibilityOptions<TKey> = {},
) {
  const fallbackKey = options.fallbackKey ?? columns[0]?.key;
  const defaultVisibility = createDefaultColumnVisibility(columns, {
    fallbackKey,
    defaultVisible: options.defaultVisible ?? true,
    defaultVisibleKeys: options.defaultVisibleKeys,
  });
  const visibility = ref<ColumnVisibility<TKey>>(
    loadColumnVisibility(columns, {
      storageKey: options.storageKey,
      fallbackKey,
      defaultVisibility,
    }),
  );

  const visibleColumns = computed(() => columns.filter((column) => visibility.value[column.key]));
  const allColumnsVisible = computed(() => visibleColumns.value.length === columns.length);
  const someColumnsVisible = computed(() => visibleColumns.value.length > 0);

  function isColumnVisible(key: TKey) {
    return visibility.value[key];
  }

  function isOnlyVisibleColumn(key: TKey) {
    return visibility.value[key] && visibleColumns.value.length === 1;
  }

  function setColumnVisibility(next: ColumnVisibility<TKey>) {
    const normalized = { ...next };
    if (fallbackKey && !Object.values(normalized).some(Boolean)) {
      normalized[fallbackKey] = true;
    }
    visibility.value = normalized;
    saveColumnVisibility(options.storageKey, normalized);
  }

  function updateColumnVisibility(key: TKey, eventOrChecked: Event | boolean | string | number) {
    const checked = checkedFrom(eventOrChecked);
    if (!checked && isOnlyVisibleColumn(key)) return;
    setColumnVisibility({ ...visibility.value, [key]: checked });
  }

  function toggleAllColumns(eventOrChecked: Event | boolean | string | number) {
    const checked = checkedFrom(eventOrChecked);
    const next = createColumnVisibility(columns, checked);
    if (!checked && fallbackKey) next[fallbackKey] = true;
    setColumnVisibility(next);
  }

  function resetColumns() {
    setColumnVisibility({ ...defaultVisibility });
  }

  return {
    visibility,
    visibleColumns,
    allColumnsVisible,
    someColumnsVisible,
    isColumnVisible,
    isOnlyVisibleColumn,
    setColumnVisibility,
    updateColumnVisibility,
    toggleAllColumns,
    resetColumns,
  };
}

export function createColumnVisibility<TKey extends string>(
  columns: readonly TableColumnOption<TKey>[],
  visible: boolean,
): ColumnVisibility<TKey> {
  return columns.reduce((result, column) => {
    result[column.key] = visible;
    return result;
  }, {} as ColumnVisibility<TKey>);
}

function loadColumnVisibility<TKey extends string>(
  columns: readonly TableColumnOption<TKey>[],
  options: Pick<ColumnVisibilityOptions<TKey>, 'fallbackKey' | 'storageKey'> & {
    defaultVisibility: ColumnVisibility<TKey>;
  },
) {
  if (!options.storageKey || typeof window === 'undefined') return { ...options.defaultVisibility };

  const raw = window.localStorage.getItem(options.storageKey);
  if (!raw) return { ...options.defaultVisibility };

  try {
    const parsed = JSON.parse(raw) as Partial<Record<TKey, unknown>>;
    const next = { ...options.defaultVisibility };
    for (const column of columns) {
      const parsedValue = parsed[column.key];
      if (typeof parsedValue === 'boolean') {
        next[column.key] = parsedValue;
      }
    }
    if (options.fallbackKey && !Object.values(next).some(Boolean)) {
      next[options.fallbackKey] = true;
    }
    return next;
  } catch {
    return { ...options.defaultVisibility };
  }
}

function saveColumnVisibility<TKey extends string>(storageKey: string | undefined, visibility: ColumnVisibility<TKey>) {
  if (!storageKey || typeof window === 'undefined') return;
  window.localStorage.setItem(storageKey, JSON.stringify(visibility));
}

function checkedFrom(eventOrChecked: Event | boolean | string | number) {
  if (typeof eventOrChecked === 'boolean') return eventOrChecked;
  if (typeof eventOrChecked === 'string') return eventOrChecked === 'true';
  if (typeof eventOrChecked === 'number') return eventOrChecked !== 0;
  return (eventOrChecked.target as HTMLInputElement).checked;
}

function createDefaultColumnVisibility<TKey extends string>(
  columns: readonly TableColumnOption<TKey>[],
  options: Pick<ColumnVisibilityOptions<TKey>, 'fallbackKey' | 'defaultVisible' | 'defaultVisibleKeys'>,
) {
  if (options.defaultVisibleKeys) {
    const allowed = new Set(options.defaultVisibleKeys);
    const next = createColumnVisibility(columns, false);
    for (const column of columns) {
      if (allowed.has(column.key)) {
        next[column.key] = true;
      }
    }
    if (options.fallbackKey && !Object.values(next).some(Boolean)) {
      next[options.fallbackKey] = true;
    }
    return next;
  }

  return createColumnVisibility(columns, options.defaultVisible ?? true);
}

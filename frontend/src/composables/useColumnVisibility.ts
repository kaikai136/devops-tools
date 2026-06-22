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
}

export type ColumnVisibility<TKey extends string> = Record<TKey, boolean>;

export function useColumnVisibility<TKey extends string>(
  columns: readonly TableColumnOption<TKey>[],
  options: ColumnVisibilityOptions<TKey> = {},
) {
  const fallbackKey = options.fallbackKey ?? columns[0]?.key;
  const visibility = ref<ColumnVisibility<TKey>>(
    loadColumnVisibility(columns, {
      storageKey: options.storageKey,
      fallbackKey,
      defaultVisible: options.defaultVisible ?? true,
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

  function updateColumnVisibility(key: TKey, eventOrChecked: Event | boolean) {
    const checked = checkedFrom(eventOrChecked);
    if (!checked && isOnlyVisibleColumn(key)) return;
    setColumnVisibility({ ...visibility.value, [key]: checked });
  }

  function toggleAllColumns(eventOrChecked: Event | boolean) {
    const checked = checkedFrom(eventOrChecked);
    const next = createColumnVisibility(columns, checked);
    if (!checked && fallbackKey) next[fallbackKey] = true;
    setColumnVisibility(next);
  }

  function resetColumns() {
    setColumnVisibility(createColumnVisibility(columns, true));
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
  options: Required<Pick<ColumnVisibilityOptions<TKey>, 'defaultVisible'>> & Pick<ColumnVisibilityOptions<TKey>, 'fallbackKey' | 'storageKey'>,
) {
  const fallback = createColumnVisibility(columns, options.defaultVisible);
  if (!options.storageKey || typeof window === 'undefined') return fallback;

  const raw = window.localStorage.getItem(options.storageKey);
  if (!raw) return fallback;

  try {
    const parsed = JSON.parse(raw) as Partial<Record<TKey, unknown>>;
    const next = createColumnVisibility(columns, true);
    for (const column of columns) {
      if (typeof parsed[column.key] === 'boolean') {
        next[column.key] = parsed[column.key];
      }
    }
    if (options.fallbackKey && !Object.values(next).some(Boolean)) {
      next[options.fallbackKey] = true;
    }
    return next;
  } catch {
    return fallback;
  }
}

function saveColumnVisibility<TKey extends string>(storageKey: string | undefined, visibility: ColumnVisibility<TKey>) {
  if (!storageKey || typeof window === 'undefined') return;
  window.localStorage.setItem(storageKey, JSON.stringify(visibility));
}

function checkedFrom(eventOrChecked: Event | boolean) {
  if (typeof eventOrChecked === 'boolean') return eventOrChecked;
  return (eventOrChecked.target as HTMLInputElement).checked;
}

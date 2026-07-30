import { afterEach, describe, expect, it, vi } from 'vitest';

import { useColumnVisibility, type TableColumnOption } from '../useColumnVisibility';

afterEach(() => {
  vi.unstubAllGlobals();
});

type ColumnKey = 'group' | 'name' | 'user' | 'actions';

const columns: readonly TableColumnOption<ColumnKey>[] = [
  { key: 'group', label: 'Group', width: '100px' },
  { key: 'name', label: 'Name', width: '120px' },
  { key: 'user', label: 'User', width: '80px' },
  { key: 'actions', label: 'Actions', width: '132px' },
];

describe('useColumnVisibility', () => {
  it('uses configured default visible keys and resets back to them', () => {
    const manager = useColumnVisibility(columns, {
      fallbackKey: 'name',
      defaultVisibleKeys: ['group', 'name', 'actions'],
    });

    expect(manager.visibility.value).toEqual({
      group: true,
      name: true,
      user: false,
      actions: true,
    });

    manager.toggleAllColumns(true);
    expect(manager.visibility.value.user).toBe(true);

    manager.resetColumns();
    expect(manager.visibility.value).toEqual({
      group: true,
      name: true,
      user: false,
      actions: true,
    });
  });

  it('can ignore previously stored visibility when no storage key is supplied', () => {
    const localStorage = {
      getItem: vi.fn(() => JSON.stringify({ group: false, name: false, user: true, actions: false })),
      setItem: vi.fn(),
    };
    vi.stubGlobal('window', { localStorage });

    const manager = useColumnVisibility(columns, {
      fallbackKey: 'name',
      defaultVisibleKeys: ['group', 'name', 'actions'],
    });

    expect(manager.visibility.value).toEqual({
      group: true,
      name: true,
      user: false,
      actions: true,
    });
    expect(localStorage.getItem).not.toHaveBeenCalled();
  });

  it('still restores stored visibility when a storage key is supplied', () => {
    const localStorage = {
      getItem: vi.fn(() => JSON.stringify({ group: false, name: true, user: true, actions: false })),
      setItem: vi.fn(),
    };
    vi.stubGlobal('window', { localStorage });

    const manager = useColumnVisibility(columns, {
      storageKey: 'test.columns',
      fallbackKey: 'name',
      defaultVisibleKeys: ['group', 'name', 'actions'],
    });

    expect(localStorage.getItem).toHaveBeenCalledWith('test.columns');
    expect(manager.visibility.value).toEqual({
      group: false,
      name: true,
      user: true,
      actions: false,
    });
  });
});

import { describe, expect, it, vi } from 'vitest';

import { useTerminalTabs } from '../useTerminalTabs';

interface TestTab {
  id: string;
  hostId: number;
}

describe('useTerminalTabs', () => {
  it('opens duplicate hosts as separate ordered tabs and activates the newest tab', () => {
    const disposeTab = vi.fn();
    const state = useTerminalTabs<TestTab>({ disposeTab });

    const first = state.openTab(() => ({ id: 'first', hostId: 7 }));
    const second = state.openTab(() => ({ id: 'second', hostId: 7 }));

    expect(first).not.toBe(second);
    expect(state.tabs.value.map((tab) => tab.id)).toEqual(['first', 'second']);
    expect(state.activeTabId.value).toBe('second');
    expect(disposeTab).not.toHaveBeenCalled();
  });

  it('keeps the active tab when a non-active tab closes', () => {
    const disposeTab = vi.fn();
    const state = useTerminalTabs<TestTab>({ disposeTab });
    const first = state.openTab(() => ({ id: 'first', hostId: 1 }));
    state.openTab(() => ({ id: 'second', hostId: 2 }));
    state.activateTab('second');

    const result = state.closeTabs([first]);

    expect(state.tabs.value.map((tab) => tab.id)).toEqual(['second']);
    expect(state.activeTabId.value).toBe('second');
    expect(result.nextActiveId).toBe('second');
    expect(disposeTab).toHaveBeenCalledOnce();
    expect(disposeTab).toHaveBeenCalledWith(first);
  });

  it('activates the tab at the closed active index, then falls back to the previous tab', () => {
    const disposeTab = vi.fn();
    const state = useTerminalTabs<TestTab>({ disposeTab });
    const first = state.openTab(() => ({ id: 'first', hostId: 1 }));
    const second = state.openTab(() => ({ id: 'second', hostId: 2 }));
    const third = state.openTab(() => ({ id: 'third', hostId: 3 }));

    state.activateTab(second.id);
    expect(state.closeTabs([second]).nextActiveId).toBe(third.id);
    expect(state.activeTabId.value).toBe(third.id);

    expect(state.closeTabs([third]).nextActiveId).toBe(first.id);
    expect(state.activeTabId.value).toBe(first.id);
    expect(disposeTab).toHaveBeenCalledTimes(2);
  });

  it('disposes each closed tab once and clears the active id when all tabs close', () => {
    const disposeTab = vi.fn();
    const state = useTerminalTabs<TestTab>({ disposeTab });
    const first = state.openTab(() => ({ id: 'first', hostId: 1 }));
    const second = state.openTab(() => ({ id: 'second', hostId: 2 }));

    const result = state.closeTabs([first, second, second]);

    expect(state.tabs.value).toEqual([]);
    expect(state.activeTabId.value).toBeNull();
    expect(result.nextActiveId).toBeNull();
    expect(disposeTab.mock.calls).toEqual([[first], [second]]);
  });
});

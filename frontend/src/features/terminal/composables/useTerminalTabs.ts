import { computed, ref, type Ref } from 'vue';

interface TerminalTabState {
  id: string;
}

interface UseTerminalTabsOptions<T extends TerminalTabState> {
  disposeTab: (tab: T) => void;
}

export function useTerminalTabs<T extends TerminalTabState>({ disposeTab }: UseTerminalTabsOptions<T>) {
  const tabs = ref<T[]>([]) as Ref<T[]>;
  const activeTabId = ref<string | null>(null);
  const activeTab = computed(() => tabs.value.find((tab) => tab.id === activeTabId.value) ?? null);

  function openTab(createTab: () => T) {
    const tab = createTab();
    tabs.value = [...tabs.value, tab];
    activeTabId.value = tab.id;
    return tab;
  }

  function activateTab(tabId: string) {
    activeTabId.value = tabId;
    return tabs.value.find((tab) => tab.id === tabId) ?? null;
  }

  function replaceTabs(nextTabs: T[], nextActiveId: string | null) {
    tabs.value = nextTabs;
    activeTabId.value = nextTabs.some((tab) => tab.id === nextActiveId) ? nextActiveId : nextTabs[0]?.id ?? null;
  }

  function closeTabs(targetTabs: T[]) {
    const closingIds = new Set(targetTabs.map((tab) => tab.id));
    if (!closingIds.size) return { nextActiveId: activeTabId.value, closedTabs: [] as T[] };

    const currentTabs = tabs.value;
    const firstClosingIndex = currentTabs.findIndex((tab) => closingIds.has(tab.id));
    const previousActiveId = activeTabId.value;
    const closedTabs = currentTabs.filter((tab) => closingIds.has(tab.id));
    const remainingTabs = currentTabs.filter((tab) => !closingIds.has(tab.id));
    for (const tab of closedTabs) disposeTab(tab);
    tabs.value = remainingTabs;

    if (previousActiveId && !closingIds.has(previousActiveId) && remainingTabs.some((tab) => tab.id === previousActiveId)) {
      activeTabId.value = previousActiveId;
    } else {
      activeTabId.value = remainingTabs[Math.min(Math.max(firstClosingIndex, 0), remainingTabs.length - 1)]?.id ?? null;
    }
    return { nextActiveId: activeTabId.value, closedTabs };
  }

  return { tabs, activeTabId, activeTab, openTab, activateTab, replaceTabs, closeTabs };
}

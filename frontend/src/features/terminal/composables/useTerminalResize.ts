interface ResizableTerminalTab {
  id: string;
  kind: 'ssh' | 'rdp';
  mounted: boolean;
  fitAddon: { fit(): void };
  terminal: { cols: number; rows: number };
  socket: { readyState: number; send(data: string): void } | null;
}

interface UseTerminalResizeOptions<T extends ResizableTerminalTab> {
  isVisible: (tab: T) => boolean;
  fitRdp: (tab: T) => void;
}

export function useTerminalResize<T extends ResizableTerminalTab>({ isVisible, fitRdp }: UseTerminalResizeOptions<T>) {
  const observers = new Map<string, ResizeObserver>();

  function fit(tab: T) {
    if (!tab.mounted || !isVisible(tab)) return;
    if (tab.kind === 'rdp') {
      fitRdp(tab);
      return;
    }
    try {
      tab.fitAddon.fit();
      if (tab.socket?.readyState === WebSocket.OPEN) {
        tab.socket.send(JSON.stringify({ type: 'resize', cols: tab.terminal.cols, rows: tab.terminal.rows }));
      }
    } catch {
      // xterm cannot fit until the container has a measurable size.
    }
  }

  function observe(tab: T, container: HTMLElement) {
    dispose(tab.id);
    const observer = new ResizeObserver(() => fit(tab));
    observers.set(tab.id, observer);
    observer.observe(container);
    fit(tab);
    return observer;
  }

  function dispose(tabId: string) {
    observers.get(tabId)?.disconnect();
    observers.delete(tabId);
  }

  function disposeAll() {
    for (const observer of observers.values()) observer.disconnect();
    observers.clear();
  }

  return { fit, observe, dispose, disposeAll };
}

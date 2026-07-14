import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useTerminalResize } from '../useTerminalResize';

interface TestSocket {
  readyState: number;
  send: ReturnType<typeof vi.fn>;
}

interface TestTab {
  id: string;
  kind: 'ssh' | 'rdp';
  mounted: boolean;
  fitAddon: { fit: ReturnType<typeof vi.fn> };
  terminal: { cols: number; rows: number };
  socket: TestSocket | null;
}

class ResizeObserverMock {
  static instances: ResizeObserverMock[] = [];
  readonly observe = vi.fn();
  readonly disconnect = vi.fn();

  constructor(readonly callback: ResizeObserverCallback) {
    ResizeObserverMock.instances.push(this);
  }
}

function createTab(overrides: Partial<TestTab> = {}): TestTab {
  return {
    id: 'tab-1',
    kind: 'ssh',
    mounted: true,
    fitAddon: { fit: vi.fn() },
    terminal: { cols: 120, rows: 40 },
    socket: { readyState: 1, send: vi.fn() },
    ...overrides,
  };
}

describe('useTerminalResize', () => {
  beforeEach(() => {
    ResizeObserverMock.instances = [];
    vi.stubGlobal('ResizeObserver', ResizeObserverMock);
    vi.stubGlobal('WebSocket', { OPEN: 1, CLOSED: 3 });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('fits an observed visible SSH terminal and sends the unchanged resize message', () => {
    const tab = createTab();
    const container = {} as HTMLElement;
    const resize = useTerminalResize<TestTab>({
      isVisible: () => true,
      fitRdp: vi.fn(),
    });

    resize.observe(tab, container);

    expect(ResizeObserverMock.instances).toHaveLength(1);
    expect(ResizeObserverMock.instances[0].observe).toHaveBeenCalledWith(container);
    expect(tab.fitAddon.fit).toHaveBeenCalledOnce();
    expect(tab.socket?.send).toHaveBeenCalledWith(JSON.stringify({ type: 'resize', cols: 120, rows: 40 }));

    ResizeObserverMock.instances[0].callback([], ResizeObserverMock.instances[0] as unknown as ResizeObserver);
    expect(tab.fitAddon.fit).toHaveBeenCalledTimes(2);
  });

  it('does not fit hidden or unmounted tabs', () => {
    const hidden = createTab();
    const unmounted = createTab({ id: 'tab-2', mounted: false });
    const resize = useTerminalResize<TestTab>({ isVisible: (tab) => tab.id !== hidden.id, fitRdp: vi.fn() });

    resize.fit(hidden);
    resize.fit(unmounted);

    expect(hidden.fitAddon.fit).not.toHaveBeenCalled();
    expect(unmounted.fitAddon.fit).not.toHaveBeenCalled();
  });

  it('delegates RDP fitting and disconnects every observer on dispose', () => {
    const fitRdp = vi.fn();
    const ssh = createTab();
    const rdp = createTab({ id: 'rdp', kind: 'rdp' });
    const resize = useTerminalResize<TestTab>({ isVisible: () => true, fitRdp });

    resize.observe(ssh, {} as HTMLElement);
    resize.observe(rdp, {} as HTMLElement);
    resize.dispose(ssh.id);
    resize.disposeAll();

    expect(fitRdp).toHaveBeenCalledWith(rdp);
    expect(ResizeObserverMock.instances[0].disconnect).toHaveBeenCalledOnce();
    expect(ResizeObserverMock.instances[1].disconnect).toHaveBeenCalledOnce();
  });
});

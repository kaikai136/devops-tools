import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useSshTerminal } from '../useSshTerminal';

interface TestTab {
  host: { id: number };
  socket: WebSocket | null;
}

class WebSocketMock {
  static readonly OPEN = 1;
  static readonly CLOSED = 3;
  static instances: WebSocketMock[] = [];

  readonly listeners = new Map<string, Array<(event: Event | MessageEvent<string>) => void>>();
  readonly send = vi.fn();
  readonly close = vi.fn();
  readyState = WebSocketMock.OPEN;

  constructor(readonly url: string) {
    WebSocketMock.instances.push(this);
  }

  addEventListener(type: string, listener: (event: Event | MessageEvent<string>) => void) {
    const listeners = this.listeners.get(type) ?? [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  emit(type: string, event: Event | MessageEvent<string> = new Event(type)) {
    for (const listener of this.listeners.get(type) ?? []) listener(event);
  }
}

function createTab(): TestTab {
  return { host: { id: 7 }, socket: null };
}

describe('useSshTerminal', () => {
  beforeEach(() => {
    WebSocketMock.instances = [];
    vi.stubGlobal('WebSocket', WebSocketMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('connects with the provided URL and forwards the unchanged socket lifecycle events', () => {
    const tab = createTab();
    const onOpen = vi.fn();
    const onMessage = vi.fn();
    const onError = vi.fn();
    const onClose = vi.fn();
    const ssh = useSshTerminal<TestTab>({
      buildUrl: (current) => `wss://ops.test/ws/terminal/${current.host.id}/`,
      onOpen,
      onMessage,
      onError,
      onClose,
    });

    const socket = ssh.connect(tab) as unknown as WebSocketMock;
    const message = new MessageEvent<string>('message', { data: '{"type":"ready"}' });

    expect(socket.url).toBe('wss://ops.test/ws/terminal/7/');
    expect(tab.socket).toBe(socket);
    socket.emit('open');
    socket.emit('message', message);
    socket.emit('error');
    socket.emit('close');

    expect(onOpen).toHaveBeenCalledWith(tab);
    expect(onMessage).toHaveBeenCalledWith(tab, message);
    expect(onError).toHaveBeenCalledWith(tab);
    expect(tab.socket).toBeNull();
    expect(onClose).toHaveBeenCalledWith(tab);
  });

  it('sends the unchanged input message only while the socket is open', () => {
    const tab = createTab();
    const ssh = useSshTerminal<TestTab>({
      buildUrl: () => 'wss://ops.test/ws/terminal/7/',
      onOpen: vi.fn(),
      onMessage: vi.fn(),
      onError: vi.fn(),
      onClose: vi.fn(),
    });
    const socket = ssh.connect(tab) as unknown as WebSocketMock;

    expect(ssh.send(tab, 'ls\r')).toBe(true);
    expect(socket.send).toHaveBeenCalledWith(JSON.stringify({ type: 'input', data: 'ls\r' }));

    socket.readyState = WebSocketMock.CLOSED;
    expect(ssh.send(tab, 'pwd\r')).toBe(false);
    expect(socket.send).toHaveBeenCalledOnce();
  });

  it('closes a live socket once and always clears the tab socket reference', () => {
    const tab = createTab();
    const ssh = useSshTerminal<TestTab>({
      buildUrl: () => 'wss://ops.test/ws/terminal/7/',
      onOpen: vi.fn(),
      onMessage: vi.fn(),
      onError: vi.fn(),
      onClose: vi.fn(),
    });
    const socket = ssh.connect(tab) as unknown as WebSocketMock;

    ssh.disconnect(tab);

    expect(socket.close).toHaveBeenCalledOnce();
    expect(tab.socket).toBeNull();

    tab.socket = socket as unknown as WebSocket;
    socket.readyState = WebSocketMock.CLOSED;
    ssh.disconnect(tab);
    expect(socket.close).toHaveBeenCalledOnce();
    expect(tab.socket).toBeNull();
  });
});

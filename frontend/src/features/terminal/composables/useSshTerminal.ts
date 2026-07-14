interface SshTerminalTab {
  host: { id: number };
  socket: WebSocket | null;
}

interface UseSshTerminalOptions<T extends SshTerminalTab> {
  buildUrl: (tab: T) => string;
  onOpen: (tab: T) => void;
  onMessage: (tab: T, event: MessageEvent<string>) => void;
  onError: (tab: T) => void;
  onClose: (tab: T) => void;
}

export function useSshTerminal<T extends SshTerminalTab>(options: UseSshTerminalOptions<T>) {
  function connect(tab: T) {
    const socket = new WebSocket(options.buildUrl(tab));
    tab.socket = socket;
    socket.addEventListener('open', () => options.onOpen(tab));
    socket.addEventListener('message', (event) => options.onMessage(tab, event as MessageEvent<string>));
    socket.addEventListener('error', () => options.onError(tab));
    socket.addEventListener('close', () => {
      tab.socket = null;
      options.onClose(tab);
    });
    return socket;
  }

  function send(tab: T, data: string) {
    if (tab.socket?.readyState !== WebSocket.OPEN) return false;
    tab.socket.send(JSON.stringify({ type: 'input', data }));
    return true;
  }

  function disconnect(tab: T) {
    if (tab.socket && tab.socket.readyState !== WebSocket.CLOSED) tab.socket.close();
    tab.socket = null;
  }

  return { connect, send, disconnect };
}

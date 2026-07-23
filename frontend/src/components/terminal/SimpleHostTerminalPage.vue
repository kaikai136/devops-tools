<script setup lang="ts">
import Guacamole from 'guacamole-common-js';
import { FitAddon } from '@xterm/addon-fit';
import { Terminal } from '@xterm/xterm';
import { markRaw, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';

import AppIcon from '@shared/components/AppIcon.vue';
import { listTerminalTree } from '@features/terminal/api/terminal';
import type { TerminalHost, TerminalTabKind } from '@features/terminal/types';
import {
  buildRdpConnectionQuery,
  buildRdpWebSocketUrl,
  buildTerminalWebSocketUrl,
  formatRdpConnectionErrorMessage,
  parseTerminalHostQuery,
} from '@features/terminal/utils/protocol';
import {
  canUseSimpleHostTerminal,
  findTerminalHostById,
  getSimpleTerminalProtocol,
} from '@features/terminal/utils/simpleHostTerminal';
import { getCurrentUser } from '../../services/auth';

type Status = 'idle' | 'loading' | 'connecting' | 'connected' | 'closed' | 'error' | 'denied';
type GuacamoleClientInstance = InstanceType<typeof Guacamole.Client>;
type GuacamoleWebSocketTunnelInstance = InstanceType<typeof Guacamole.WebSocketTunnel>;
type GuacamoleMouseInstance = InstanceType<typeof Guacamole.Mouse>;
type GuacamoleKeyboardInstance = InstanceType<typeof Guacamole.Keyboard>;

const host = ref<TerminalHost | null>(null);
const protocol = ref<TerminalTabKind>('ssh');
const status = ref<Status>('idle');
const statusText = ref('准备连接');
const errorMessage = ref('');
const terminalRef = ref<HTMLElement | null>(null);
const rdpRef = ref<HTMLElement | null>(null);

let xterm: Terminal | null = null;
let fitAddon: FitAddon | null = null;
let sshSocket: WebSocket | null = null;
let resizeObserver: ResizeObserver | null = null;
let guacClient: GuacamoleClientInstance | null = null;
let guacTunnel: GuacamoleWebSocketTunnelInstance | null = null;
let guacMouse: GuacamoleMouseInstance | null = null;
let guacKeyboard: GuacamoleKeyboardInstance | null = null;

onMounted(() => {
  window.addEventListener('resize', fitActiveSession);
  void bootstrap();
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', fitActiveSession);
  cleanupConnections();
});

async function bootstrap() {
  status.value = 'loading';
  statusText.value = '正在加载主机';
  errorMessage.value = '';

  const hostId = parseTerminalHostQuery(window.location.search);
  if (!hostId) {
    setError('无效的主机 ID');
    return;
  }

  try {
    const current = await getCurrentUser();
    if (!canUseSimpleHostTerminal(current.user.featurePermissionCodes)) {
      status.value = 'denied';
      statusText.value = '无权限';
      errorMessage.value = '当前角色没有 Web 终端权限。';
      return;
    }

    const groups = await listTerminalTree();
    const selectedHost = findTerminalHostById(groups, hostId);
    if (!selectedHost) {
      setError('主机不可用或无权限访问');
      return;
    }

    host.value = selectedHost;
    protocol.value = getSimpleTerminalProtocol(selectedHost);
    await connect();
  } catch (error) {
    setError(error instanceof Error ? error.message : '终端加载失败');
  }
}

async function connect() {
  const selectedHost = host.value;
  if (!selectedHost) {
    setError('主机不可用或无权限访问');
    return;
  }

  cleanupConnections();
  status.value = 'connecting';
  statusText.value = '连接中';
  errorMessage.value = '';
  await nextTick();

  if (protocol.value === 'rdp') {
    connectRdp(selectedHost);
    return;
  }

  connectSsh(selectedHost);
}

function connectSsh(selectedHost: TerminalHost) {
  const terminal = markRaw(new Terminal({
    cursorBlink: true,
    fontFamily: 'Menlo, Monaco, Consolas, "Courier New", monospace',
    fontSize: 14,
    scrollback: 5000,
    theme: {
      background: '#1f1f1f',
      foreground: '#d8dee9',
      cursor: '#ffffff',
      selectionBackground: '#3b4252',
      green: '#22c55e',
      cyan: '#38bdf8',
      yellow: '#facc15',
      red: '#ef4444',
    },
  }));
  const fit = markRaw(new FitAddon());
  terminal.loadAddon(fit);
  xterm = terminal;
  fitAddon = fit;

  if (!terminalRef.value) {
    setError('终端容器不可用');
    return;
  }

  terminal.open(terminalRef.value);
  terminal.writeln(`正在连接 ${selectedHost.name} (${selectedHost.publicIp || selectedHost.privateIp}:${selectedHost.port})...`);
  terminal.onData((data) => {
    if (sshSocket?.readyState === WebSocket.OPEN) {
      sshSocket.send(JSON.stringify({ type: 'input', data }));
    }
  });
  terminal.onResize(({ cols, rows }) => {
    if (sshSocket?.readyState === WebSocket.OPEN) {
      sshSocket.send(JSON.stringify({ type: 'resize', cols, rows }));
    }
  });

  observeResize(terminalRef.value);
  fitActiveSession();

  const socket = new WebSocket(buildTerminalWebSocketUrl(window.location.protocol, window.location.host, selectedHost.id));
  sshSocket = socket;
  socket.addEventListener('open', () => {
    if (sshSocket !== socket) return;
    fitActiveSession();
  });
  socket.addEventListener('message', (event) => {
    if (sshSocket !== socket) return;
    handleSshMessage(event as MessageEvent<string>);
  });
  socket.addEventListener('error', () => {
    if (sshSocket !== socket) return;
    setError('WebSocket 连接失败');
  });
  socket.addEventListener('close', () => {
    if (sshSocket !== socket) return;
    if (status.value === 'connected' || status.value === 'connecting') {
      status.value = 'closed';
      statusText.value = '已断开';
      terminal.writeln('\r\n连接已断开。');
    }
  });
}

function handleSshMessage(event: MessageEvent<string>) {
  let message: { type?: string; data?: string; message?: string; reason?: string; sessionId?: string };
  try {
    message = JSON.parse(event.data);
  } catch {
    xterm?.write(event.data);
    return;
  }

  if (message.type === 'ready') {
    status.value = 'connected';
    statusText.value = '已连接';
    fitActiveSession();
    xterm?.focus();
    return;
  }
  if (message.type === 'output') {
    xterm?.write(message.data ?? '');
    return;
  }
  if (message.type === 'error') {
    setError(message.message || '终端连接失败');
    return;
  }
  if (message.type === 'closed') {
    status.value = 'closed';
    statusText.value = '已断开';
    xterm?.writeln(`\r\n${message.reason || '连接已关闭'}`);
  }
}

function connectRdp(selectedHost: TerminalHost) {
  const container = rdpRef.value;
  if (!container) {
    setError('RDP 容器不可用');
    return;
  }

  container.textContent = '';
  container.tabIndex = 0;
  observeResize(container);

  const tunnel = markRaw(new Guacamole.WebSocketTunnel(buildRdpWebSocketUrl(window.location.protocol, window.location.host, selectedHost.id)));
  const client = markRaw(new Guacamole.Client(tunnel));
  guacTunnel = tunnel;
  guacClient = client;

  const display = client.getDisplay();
  display.onresize = fitActiveSession;
  const displayElement = display.getElement();
  displayElement.classList.add('simple-host-terminal-rdp-display');
  displayElement.tabIndex = 0;
  container.appendChild(displayElement);
  attachRdpInput(displayElement, client);

  client.onstatechange = (state) => {
    if (guacClient !== client) return;
    if (state === Guacamole.Client.State.CONNECTED) {
      status.value = 'connected';
      statusText.value = '已连接';
      fitActiveSession();
      displayElement.focus();
      return;
    }
    if (state === Guacamole.Client.State.DISCONNECTED && status.value !== 'closed') {
      status.value = 'closed';
      statusText.value = '已断开';
    }
  };
  client.onerror = (error) => {
    if (guacClient !== client) return;
    setError(rdpErrorMessage(error));
  };
  tunnel.onerror = (error) => {
    if (guacTunnel !== tunnel) return;
    setError(rdpErrorMessage(error));
  };

  try {
    client.connect(buildRdpConnectionQuery(container.clientWidth, container.clientHeight));
  } catch (error) {
    setError(rdpErrorMessage(error));
  }
}

function attachRdpInput(displayElement: HTMLElement, client: GuacamoleClientInstance) {
  const mouse = markRaw(new Guacamole.Mouse(displayElement));
  mouse.onEach(['mousedown', 'mousemove', 'mouseup'], (event) => {
    if (status.value !== 'connected') return;
    client.sendMouseState((event as Guacamole.Mouse.Event).state, true);
    displayElement.focus();
  });
  mouse.on('mouseout', () => client.getDisplay().showCursor(false));
  guacMouse = mouse;

  const keyboard = markRaw(new Guacamole.Keyboard(displayElement));
  keyboard.onkeydown = (keysym) => {
    if (status.value !== 'connected') return true;
    client.sendKeyEvent(1, keysym);
    return false;
  };
  keyboard.onkeyup = (keysym) => {
    if (status.value !== 'connected') return;
    client.sendKeyEvent(0, keysym);
  };
  guacKeyboard = keyboard;
}

function clearScreen() {
  if (protocol.value === 'ssh') {
    xterm?.clear();
    return;
  }
  rdpRef.value?.focus();
}

function disconnect() {
  status.value = 'closed';
  statusText.value = '已断开';
  cleanupConnections();
}

function cleanupConnections() {
  resizeObserver?.disconnect();
  resizeObserver = null;

  if (sshSocket && sshSocket.readyState !== WebSocket.CLOSED) sshSocket.close();
  sshSocket = null;

  xterm?.dispose();
  xterm = null;
  fitAddon = null;

  if (guacKeyboard) {
    guacKeyboard.onkeydown = null;
    guacKeyboard.onkeyup = null;
  }
  guacKeyboard = null;
  guacMouse = null;
  try {
    guacClient?.getDisplay().getElement().remove();
    guacClient?.disconnect();
  } catch {
    // Ignore disconnect races.
  }
  guacClient = null;
  guacTunnel = null;
  if (rdpRef.value) rdpRef.value.textContent = '';
}

function observeResize(element: HTMLElement) {
  resizeObserver?.disconnect();
  resizeObserver = new ResizeObserver(fitActiveSession);
  resizeObserver.observe(element);
}

function fitActiveSession() {
  if (protocol.value === 'ssh') {
    try {
      fitAddon?.fit();
    } catch {
      // xterm can briefly report zero-size containers during first paint.
    }
    return;
  }

  const container = rdpRef.value;
  const display = guacClient?.getDisplay();
  if (!container || !display) return;
  const width = display.getWidth();
  const height = display.getHeight();
  if (!width || !height) return;
  const scale = Math.min(container.clientWidth / width, container.clientHeight / height);
  if (Number.isFinite(scale) && scale > 0) display.scale(scale);
}

function setError(message: string) {
  status.value = 'error';
  statusText.value = '错误';
  errorMessage.value = message;
  xterm?.writeln(`\r\n${message}`);
}

function rdpErrorMessage(error?: unknown) {
  return formatRdpConnectionErrorMessage(error);
}
</script>

<template>
  <main class="simple-host-terminal-page">
    <header class="simple-host-terminal-header">
      <div>
        <strong>终端 - {{ host?.name || '主机' }}</strong>
        <span>主机 ID: {{ host?.id || '-' }}</span>
      </div>
      <nav aria-label="终端操作">
        <span class="simple-host-terminal-status" :class="status">
          <AppIcon :name="status === 'connected' ? 'circleCheck' : status === 'connecting' || status === 'loading' ? 'rotate' : 'alert'" :size="15" />
          {{ statusText }}
        </span>
        <button type="button" :disabled="!host || status === 'connecting' || status === 'loading' || status === 'denied'" @click="connect">
          <AppIcon name="rotate" :size="15" />
          重新连接
        </button>
        <button type="button" :disabled="status === 'denied' || protocol === 'rdp'" @click="clearScreen">清屏</button>
        <button type="button" :disabled="status === 'denied' || status === 'closed'" @click="disconnect">断开</button>
      </nav>
    </header>

    <section class="simple-host-terminal-shell" :class="protocol">
      <div v-show="protocol === 'ssh'" ref="terminalRef" class="simple-host-terminal-xterm"></div>
      <div v-show="protocol === 'rdp'" ref="rdpRef" class="simple-host-terminal-rdp"></div>
      <div v-if="errorMessage || status === 'denied'" class="simple-host-terminal-overlay">
        <strong>{{ status === 'denied' ? '没有终端权限' : '连接不可用' }}</strong>
        <span>{{ errorMessage }}</span>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue';

import { apiGet, apiPost } from '../../api';

interface TerminalHost {
  id: number;
  name: string;
  group: number;
  privateIp: string;
  publicIp: string;
  port: number;
  loginUser: string;
  remark: string;
}

interface TerminalGroup {
  id: number;
  name: string;
  hosts: TerminalHost[];
  children: TerminalGroup[];
}

interface TerminalSession {
  id: string;
  host: TerminalHost;
  status: string;
  greeting: string;
  createdAt: string;
}

type TreeRow =
  | { kind: 'group'; group: TerminalGroup; level: number }
  | { kind: 'host'; host: TerminalHost; level: number };

interface TerminalLine {
  type: 'system' | 'input' | 'output' | 'error';
  text: string;
}

const groups = ref<TerminalGroup[]>([]);
const collapsed = ref<Set<number>>(new Set());
const search = ref('');
const session = ref<TerminalSession | null>(null);
const lines = ref<TerminalLine[]>([
  { type: 'system', text: 'SPUG WEB TERMINAL' },
  { type: 'system', text: '双击左侧主机名连接终端。' },
]);
const command = ref('');
const isLoadingTree = ref(false);
const isConnecting = ref(false);
const isRunning = ref(false);
const terminalBody = ref<HTMLElement | null>(null);

const rows = computed(() => {
  const query = search.value.trim().toLowerCase();
  return flattenTerminalRows(groups.value, collapsed.value).filter((row) => {
    if (!query) return true;
    if (row.kind === 'group') return row.group.name.toLowerCase().includes(query);
    return [row.host.name, row.host.privateIp, row.host.publicIp, row.host.loginUser]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query));
  });
});

const prompt = computed(() => {
  if (!session.value) return 'spug@terminal:~$';
  return `${session.value.host.loginUser || 'user'}@${session.value.host.name}:~$`;
});

onMounted(async () => {
  await loadTree();
  const params = new URLSearchParams(window.location.search);
  const hostId = Number(params.get('host'));
  if (hostId) {
    const host = findHostById(groups.value, hostId);
    if (host) await connectHost(host);
  }
});

async function loadTree() {
  isLoadingTree.value = true;
  try {
    groups.value = await apiGet<TerminalGroup[]>('/api/web-terminal/tree/');
  } catch (error) {
    appendLine('error', (error as Error).message);
  } finally {
    isLoadingTree.value = false;
  }
}

function toggleGroup(group: TerminalGroup) {
  const next = new Set(collapsed.value);
  if (next.has(group.id)) {
    next.delete(group.id);
  } else {
    next.add(group.id);
  }
  collapsed.value = next;
}

async function connectHost(host: TerminalHost) {
  isConnecting.value = true;
  try {
    const created = await apiPost<TerminalSession>('/api/web-terminal/sessions/', { host: host.id });
    session.value = created;
    lines.value = [
      { type: 'system', text: 'SPUG WEB TERMINAL' },
      { type: 'system', text: created.greeting },
    ];
    await scrollTerminalToBottom();
  } catch (error) {
    appendLine('error', (error as Error).message);
  } finally {
    isConnecting.value = false;
  }
}

async function runCommand() {
  if (!session.value || isRunning.value) return;
  const value = command.value.trim();
  if (!value) return;
  command.value = '';
  appendLine('input', `${prompt.value} ${value}`);

  try {
    isRunning.value = true;
    const result = await apiPost<{ command: string; output: string; exitCode: number | null }>(`/api/web-terminal/sessions/${session.value.id}/commands/`, {
      command: value,
    });
    if (result.output === '__CLEAR__') {
      lines.value = [];
    } else {
      appendLine(result.exitCode === 0 ? 'output' : 'error', result.output);
    }
  } catch (error) {
    appendLine('error', (error as Error).message);
  } finally {
    isRunning.value = false;
  }
}

function appendLine(type: TerminalLine['type'], text: string) {
  lines.value.push({ type, text });
  scrollTerminalToBottom();
}

async function scrollTerminalToBottom() {
  await nextTick();
  if (terminalBody.value) terminalBody.value.scrollTop = terminalBody.value.scrollHeight;
}

function flattenTerminalRows(source: TerminalGroup[], hidden: Set<number>, level = 0): TreeRow[] {
  return source.flatMap((group) => {
    const current: TreeRow[] = [{ kind: 'group', group, level }];
    if (!hidden.has(group.id)) {
      current.push(...group.hosts.map((host) => ({ kind: 'host' as const, host, level: level + 1 })));
      current.push(...flattenTerminalRows(group.children, hidden, level + 1));
    }
    return current;
  });
}

function findHostById(source: TerminalGroup[], hostId: number): TerminalHost | null {
  for (const group of source) {
    const host = group.hosts.find((item) => item.id === hostId);
    if (host) return host;
    const childHost = findHostById(group.children, hostId);
    if (childHost) return childHost;
  }
  return null;
}
</script>

<template>
  <main class="terminal-shell">
    <aside class="terminal-sidebar">
      <div class="terminal-brand">
        <strong>SPUG</strong>
      </div>
      <div class="terminal-search">
        <input v-model="search" placeholder="输入主机名/IP检索" />
        <button type="button" title="刷新" @click="loadTree">↻</button>
      </div>
      <div class="terminal-tree">
        <button
          v-for="row in rows"
          :key="row.kind === 'group' ? `group-${row.group.id}` : `host-${row.host.id}`"
          class="terminal-tree-row"
          :class="{ host: row.kind === 'host', active: row.kind === 'host' && session?.host.id === row.host.id }"
          :style="{ paddingLeft: `${12 + row.level * 24}px` }"
          type="button"
          @click="row.kind === 'group' && toggleGroup(row.group)"
          @dblclick="row.kind === 'host' && connectHost(row.host)"
        >
          <template v-if="row.kind === 'group'">
            <span>{{ collapsed.has(row.group.id) ? '▸' : '▾' }}</span>
            <strong>▱ {{ row.group.name }}</strong>
          </template>
          <template v-else>
            <span>◎</span>
            <strong>{{ row.host.name }}</strong>
          </template>
        </button>
        <p v-if="isLoadingTree" class="terminal-tree-empty">加载中...</p>
        <p v-else-if="!rows.length" class="terminal-tree-empty">没有匹配的主机。</p>
      </div>
    </aside>

    <section class="terminal-workspace">
      <div class="terminal-hint">
        <span>小提示：双击标签快速复制窗口，右击标签展开更多操作。</span>
        <strong v-if="isConnecting">连接中...</strong>
      </div>
      <div class="terminal-tabs">
        <button class="active" type="button">{{ session ? session.host.name : '未连接' }}</button>
      </div>
      <div ref="terminalBody" class="terminal-screen">
        <pre v-for="(line, index) in lines" :key="index" :class="line.type">{{ line.text }}</pre>
      </div>
      <form class="terminal-command" @submit.prevent="runCommand">
        <span>{{ prompt }}</span>
        <input v-model="command" :disabled="!session || isRunning" autocomplete="off" placeholder="输入命令后回车" />
        <button type="submit" :disabled="!session || isRunning">{{ isRunning ? '执行中' : '发送' }}</button>
      </form>
    </section>
  </main>
</template>

import { defineConfig } from 'vitest/config';
import vue from '@vitejs/plugin-vue';
import { resolve } from 'path';
import { fileURLToPath, URL } from 'node:url';
import { existsSync, readFileSync } from 'node:fs';

const localConfigPath = resolve(__dirname, '../config/local.app.conf');

function readLocalConfig(path: string) {
  if (!existsSync(path)) return {};
  return Object.fromEntries(
    readFileSync(path, 'utf8')
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith('#') && line.includes('='))
      .map((line) => {
        const separator = line.indexOf('=');
        return [line.slice(0, separator).trim(), line.slice(separator + 1).trim()];
      }),
  );
}

const localConfig = readLocalConfig(localConfigPath);
const frontendHost = localConfig.FRONTEND_HOST || '0.0.0.0';
const frontendPort = Number(localConfig.FRONTEND_PORT || 5173);
const apiTarget = localConfig.VITE_API_TARGET || 'http://127.0.0.1:8001';
const wsTarget = localConfig.VITE_WS_TARGET || 'ws://127.0.0.1:8001';

export default defineConfig({
  plugins: [vue()],
  test: {
    include: ['src/**/*.test.ts'],
  },
  resolve: {
    alias: {
      '@app': fileURLToPath(new URL('./src/app', import.meta.url)),
      '@shared': fileURLToPath(new URL('./src/shared', import.meta.url)),
      '@features': fileURLToPath(new URL('./src/features', import.meta.url)),
      '@pages': fileURLToPath(new URL('./src/pages', import.meta.url)),
    },
  },
  server: {
    host: frontendHost,
    port: frontendPort,
    proxy: {
      '/api': apiTarget,
      '/media': apiTarget,
      '/ws': {
        target: wsTarget,
        ws: true,
      },
    },
  },
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        terminal: resolve(__dirname, 'terminal.html'),
        hostTerminal: resolve(__dirname, 'host-terminal.html'),
      },
      output: {
        manualChunks(id) {
          const normalizedId = id.replace(/\\/g, '/');
          if (!normalizedId.includes('node_modules')) return undefined;
          if (normalizedId.includes('/zrender/')) return 'zrender';
          if (normalizedId.includes('/echarts/')) return 'echarts';
          return undefined;
        },
      },
    },
  },
});

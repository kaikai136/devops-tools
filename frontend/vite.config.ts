import { defineConfig } from 'vitest/config';
import vue from '@vitejs/plugin-vue';
import { resolve } from 'path';
import { fileURLToPath, URL } from 'node:url';

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
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8001',
      '/media': 'http://127.0.0.1:8001',
      '/ws': {
        target: 'ws://127.0.0.1:8001',
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

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// 开发模式下把网关请求代理到本地服务端（避免跨域）
// 生产环境请把 VITE_AIGC_PROXY_HOST 指向服务端公网地址
const proxyTarget = process.env.VITE_AIGC_PROXY_HOST || 'http://127.0.0.1:3001';

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/getScenes': { target: proxyTarget, changeOrigin: true },
      '/proxy': { target: proxyTarget, changeOrigin: true },
      '/api': { target: proxyTarget, changeOrigin: true },
      '/debug': { target: proxyTarget, changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 2000,
    rollupOptions: {
      output: {
        manualChunks: {
          rtc: ['@volcengine/rtc'],
          vendor: ['react', 'react-dom', 'react-redux', '@reduxjs/toolkit', 'react-router-dom'],
        },
      },
    },
  },
});

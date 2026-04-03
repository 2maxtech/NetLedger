import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://192.168.40.40:8000',
        changeOrigin: true,
      },
      '/agent': {
        target: 'http://192.168.40.41:8443',
        changeOrigin: true,
        secure: false,
      },
    },
  },
});

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In dev the API runs on :3001; in production Express serves the built client itself.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': { target: 'http://localhost:3001', changeOrigin: true } } },
});

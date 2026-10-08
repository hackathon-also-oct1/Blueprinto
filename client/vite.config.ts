import path from 'node:path';

import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // The reference screenshots live in the repo-root screenshots/ folder.
  server: { fs: { allow: ['..'] } },
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
});

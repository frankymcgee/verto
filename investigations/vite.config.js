import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { lucideIconsPlugin } from 'frappe-ui/vite/lucideIconsPlugin'
import { copyFileSync, mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  base: '/assets/verto/investigations/',
  plugins: [
    vue(),
    lucideIconsPlugin(),
    {
      name: 'investigations-frappe-entry',
      closeBundle() {
        mkdirSync(fileURLToPath(new URL('../verto/www/', import.meta.url)), { recursive: true })
        copyFileSync(
          fileURLToPath(new URL('../verto/public/investigations/index.html', import.meta.url)),
          fileURLToPath(new URL('../verto/www/investigations.html', import.meta.url)),
        )
      },
    },
  ],
  server: {
    proxy: {
      '/api': {
        target: process.env.VERTO_DEV_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
      '/private': {
        target: process.env.VERTO_DEV_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: { outDir: '../verto/public/investigations', emptyOutDir: true, target: 'es2020' },
})

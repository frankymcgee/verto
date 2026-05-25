import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import Icons from 'unplugin-icons/vite'

export default defineConfig(({ command }) => {
  const isDev = command === 'serve'

  return {
    base: isDev
      ? '/verto-mobile/'
      : '/assets/verto/verto-mobile/',

    plugins: [
      vue(),
      Icons({
        compiler: 'vue3',
        autoInstall: true,
      }),
    ],

    server: {
      host: '0.0.0.0',
      proxy: {
        '/api': {
          target: 'https://dashboard.minesitesupport.com.au',
          changeOrigin: true,
          secure: false,
        },
      },
    },

    build: {
      outDir: '../verto/public/verto-mobile',
      emptyOutDir: true,
      rollupOptions: {
        output: {
          entryFileNames: 'assets/index.js',
          chunkFileNames: 'assets/[name].js',
          assetFileNames: (assetInfo) => {
            if (assetInfo.name?.endsWith('.css')) {
              return 'assets/index.css'
            }

            return 'assets/[name][extname]'
          },
        },
      },
    },

    optimizeDeps: {
      include: [
        'frappe-ui > feather-icons',
        'showdown',
        'engine.io-client',
      ],
    },
  }
})
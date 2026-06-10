import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import Icons from 'unplugin-icons/vite'
import { VitePWA } from 'vite-plugin-pwa'

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
      VitePWA({
        registerType: 'autoUpdate',
        strategies: 'injectManifest',
        injectRegister: null,

        // This must stay aligned with build.outDir.
        // VitePWA will output the built service worker into:
        // apps/verto/verto/public/verto-mobile/
        outDir: '../verto/public/verto-mobile',

        // Source service worker file.
        // Place this at: frontend/src/verto-sw.ts
        srcDir: 'src',
        filename: 'verto-sw.ts',

        // The generated service worker will be available at:
        // /assets/verto/verto-mobile/verto-sw.js
        // This scope can control assets under /assets/verto/verto-mobile/.
        // It will not fully control /verto-mobile/ without a root/scope route,
        // but this avoids editing bench-generated nginx config.
        scope: '/assets/verto/verto-mobile/',
        base: '/assets/verto/verto-mobile/',

        manifest: {
          name: 'Verto Mobile',
          short_name: 'Verto',
          description: 'Mobile field operations app for Mine Site Support.',
          start_url: '/verto-mobile/',
          scope: '/verto-mobile/',
          display: 'standalone',
          background_color: '#f9fafb',
          theme_color: '#2563eb',
          icons: [
            {
              src: '/assets/verto/images/verto-icon.png',
              sizes: '192x192',
              type: 'image/png',
              purpose: 'any',
            },
            {
              src: '/assets/verto/images/verto-icon.png',
              sizes: '512x512',
              type: 'image/png',
              purpose: 'any',
            },
            {
              src: '/assets/verto/images/verto-icon.png',
              sizes: '512x512',
              type: 'image/png',
              purpose: 'maskable',
            },
          ],
        },

        injectManifest: {
          maximumFileSizeToCacheInBytes: 8 * 1024 * 1024,
        },

        devOptions: {
          enabled: false,
        },
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

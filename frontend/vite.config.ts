import { copyFileSync, mkdirSync } from 'node:fs'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import Icons from 'unplugin-icons/vite'
import { lucideIconsPlugin } from 'frappe-ui/vite/lucideIconsPlugin'
import { VitePWA } from 'vite-plugin-pwa'

function copyVertoServiceWorkerPlugin(): Plugin {
  return {
    name: 'copy-verto-service-worker',
    apply: 'build',
    enforce: 'post',

    closeBundle: {
      order: 'post',
      sequential: true,

      handler() {
        const source = fileURLToPath(
          new URL(
            '../verto/public/verto-mobile/verto-sw.js',
            import.meta.url
          )
        )

        const destination = fileURLToPath(
          new URL(
            '../verto/public/pwa/verto-mobile-sw.js',
            import.meta.url
          )
        )

        mkdirSync(dirname(destination), { recursive: true })
        copyFileSync(source, destination)
      },
    },
  }
}

export default defineConfig(({ command }) => {
  const isDev = command === 'serve'
  const devProxyTarget = process.env.VERTO_DEV_PROXY_TARGET || 'http://localhost:8000'

  return {
    base: isDev
      ? '/verto-mobile/'
      : '/assets/verto/verto-mobile/',

    plugins: [
      vue(),
      lucideIconsPlugin(),
      Icons({
        compiler: 'vue3',
        autoInstall: true,
      }),
      VitePWA({
        registerType: 'autoUpdate',
        strategies: 'injectManifest',
        injectRegister: null,
        srcDir: 'src',
        filename: 'verto-sw.ts',
        outDir: '../verto/public/verto-mobile',

        injectManifest: {
          modifyURLPrefix: {
            '': '/assets/verto/verto-mobile/',
          },
        },

        integration: {
          beforeBuildServiceWorker(options) {
            const prefix = '/assets/verto/verto-mobile/'
            const entries =
              options.injectManifest.additionalManifestEntries || []

            options.injectManifest.additionalManifestEntries =
              entries.map((entry) => {
                if (typeof entry === 'string') {
                  return entry.startsWith('/')
                    ? entry
                    : `${prefix}${entry}`
                }

                return {
                  ...entry,
                  url: entry.url.startsWith('/')
                    ? entry.url
                    : `${prefix}${entry.url}`,
                }
              })
          },
        },

        // The tenant manifest is served by Frappe at /verto-mobile.webmanifest.
        // Do not inject a second, build-generated manifest into index.html.
        manifest: false,
      }),
      copyVertoServiceWorkerPlugin(),
    ],

    server: {
      host: '0.0.0.0',
      proxy: {
        '/verto-mobile.webmanifest': {
          target: devProxyTarget,
          changeOrigin: true,
          secure: false,
        },
        '/api': {
          target: devProxyTarget,
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
        'engine.io-client',
      ],
    },
  }
})

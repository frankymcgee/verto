import { copyFileSync, mkdirSync } from 'node:fs'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import Icons from 'unplugin-icons/vite'
import { VitePWA } from 'vite-plugin-pwa'
import type { ManifestOptions } from 'vite-plugin-pwa'

const mssManifest = {
  name: 'MSS Dashboard',
  short_name: 'MSS',
  id: '/verto-mobile',
  start_url: '/verto-mobile',
  scope: '/verto-mobile',
  display: 'standalone',
  description: 'PWA Companion app for Mine Site Support',
  lang: 'en-AU',
  dir: 'auto',
  theme_color: '#171717',
  background_color: '#171717',
  orientation: 'portrait-primary',
  prefer_related_applications: false,
  icons: [
    {
      src: '/assets/verto/manifest/mss-pwa-192.png',
      sizes: '192x192',
      type: 'image/png',
      purpose: 'any',
    },
    {
      src: '/assets/verto/manifest/mss-pwa-512.png',
      sizes: '512x512',
      type: 'image/png',
      purpose: 'any',
    },
    {
      src: '/assets/verto/manifest/mss-pwa-maskable-192.png',
      sizes: '192x192',
      type: 'image/png',
      purpose: 'maskable',
    },
    {
      src: '/assets/verto/manifest/mss-pwa-maskable-512.png',
      sizes: '512x512',
      type: 'image/png',
      purpose: 'maskable',
    },
    {
      src: '/assets/verto/manifest/apple-touch-icon.png',
      sizes: '180x180',
      type: 'image/png',
      purpose: 'any',
    },
  ],
  screenshots: [
    {
      src: 'https://dashboard.minesitesupport.com.au/files/screen1.png',
      sizes: '1242x2688',
      type: 'image/png',
      description: 'Companion app for Mine Site Support',
    },
    {
      src: 'https://dashboard.minesitesupport.com.au/files/screen2.png',
      sizes: '1242x2688',
      type: 'image/png',
      description: 'Complete Site Forms online',
    },
    {
      src: 'https://dashboard.minesitesupport.com.au/files/screen3.png',
      sizes: '1242x2688',
      type: 'image/png',
      description: 'Chat with teams on any jobsite',
    },
    {
      src: 'https://dashboard.minesitesupport.com.au/files/screen4.png',
      sizes: '1242x2688',
      type: 'image/png',
      description: 'Direct message other team members',
    },
  ],
  categories: [
    'business',
    'productivity',
  ],
  shortcuts: [
    {
      name: 'Home',
      short_name: 'Home',
      url: '/verto-mobile/',
      description: 'Open the Verto Mobile home page',
    },
    {
      name: 'Shifts',
      short_name: 'Shifts',
      url: '/verto-mobile/shifts',
      description: 'View allocated shifts',
    },
    {
      name: 'Forms',
      short_name: 'Forms',
      url: '/verto-mobile/forms',
      description: 'Open completed forms',
    },
    {
      name: 'Ask PERI',
      short_name: 'PERI',
      url: '/verto-mobile/chat/peri?mode=ai',
      description: 'Open Ask PERI',
    },
  ],
} as unknown as Partial<ManifestOptions>

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

        manifestFilename: 'manifest.webmanifest',
        manifest: mssManifest,
      }),
      copyVertoServiceWorkerPlugin(),
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

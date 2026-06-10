// VERTO_VITE_PWA_PLUGIN_EXAMPLE_RAVEN_STYLE_STAGE_1_2026_06_10
// Add this pattern to your existing frontend/vite.config.ts.
// Do not replace your full Vite config blindly unless it already matches this structure.

import { VitePWA } from 'vite-plugin-pwa'

export function createVertoPwaPlugin() {
  return VitePWA({
    registerType: 'autoUpdate',
    strategies: 'injectManifest',
    injectRegister: null,
    srcDir: 'src/pwa',
    filename: 'verto-sw.ts',
    manifestFilename: 'manifest.webmanifest',
    manifest: {
      name: 'Verto Mobile',
      short_name: 'Verto',
      description: 'Native mobile field app for Verto.',
      start_url: '/verto-mobile/',
      scope: '/verto-mobile/',
      display: 'standalone',
      background_color: '#f8fafc',
      theme_color: '#111827',
      icons: [
        {
          src: '/assets/verto/images/verto-icon.png',
          sizes: '192x192',
          type: 'image/png',
        },
        {
          src: '/assets/verto/images/verto-icon.png',
          sizes: '512x512',
          type: 'image/png',
          purpose: 'any maskable',
        },
      ],
    },
    injectManifest: {
      globPatterns: ['**/*.{js,css,html,ico,png,svg,webp,woff,woff2}'],
      maximumFileSizeToCacheInBytes: 5 * 1024 * 1024,
    },
    devOptions: {
      enabled: false,
    },
  })
}

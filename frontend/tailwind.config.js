import frappeUIPreset, { content as frappeUIContent } from 'frappe-ui/tailwind'

export default {
  presets: [
    frappeUIPreset,
  ],
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
    ...frappeUIContent,
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
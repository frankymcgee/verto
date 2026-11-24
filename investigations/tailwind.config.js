import frappeUIPreset, { content } from "frappe-ui/tailwind";
export default {
  presets: [frappeUIPreset],
  content: [...content, "./index.html", "./src/**/*.{vue,js,ts}", "../frontend/src/components/{PhotoAnnotationEditor,MobileSheet}.vue"],
  theme: {},
  plugins: [],
};

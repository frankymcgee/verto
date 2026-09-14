import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";
import { lucideIconsPlugin } from "frappe-ui/vite/lucideIconsPlugin";
export default defineConfig({
  plugins: [vue(), lucideIconsPlugin()],
  resolve: { dedupe: ["vue"] },
  test: {
    server: { deps: { inline: ["frappe-ui"] } },
    environment: "happy-dom",
    include: ["tests/*.test.js"],
    setupFiles: ["tests/setup.js"],
    pool: "threads",
    poolOptions: { threads: { singleThread: true } },
  },
});
